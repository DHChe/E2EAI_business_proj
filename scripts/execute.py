"""Repository harness primitives (Python 3.10 standard library only)."""
import argparse
import copy
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import fcntl
import json
import os
from pathlib import Path
import posixpath
import re
import signal
import subprocess
import sys
import tempfile
import time
from typing import Callable, Iterable, Sequence

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_BLOCKED = 2
EXIT_REVIEW = 3

CODEX_CONFIG_FLAGS: list[str] = [
    '-c', 'plugins."browser@openai-bundled".enabled=false',
    '-c', 'plugins."unified-computer-use@openai-bundled".enabled=false',
    '-c', 'plugins."computer-use@openai-bundled".enabled=false',
    '--disable', 'apps', '--disable', 'computer_use',
    '--disable', 'browser_use', '--disable', 'in_app_browser',
    '-c', 'sandbox_workspace_write.network_access=false',
]


@dataclass
class ChildResult:
    returncode: int | None
    timed_out: bool
    stdout: str
    stderr: str


def codex_mcp_overrides(servers: list[dict]) -> list[str]:
    overrides = []
    for server in servers:
        name = server.get("name") if isinstance(server, dict) else None
        if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", name):
            raise HarnessExit(EXIT_ERROR, f"MCP 서버 이름을 안전하게 끌 수 없다: {name!r}")
        transport = server.get("transport", {})
        if not isinstance(transport, dict):
            raise HarnessExit(EXIT_ERROR, "잘못된 MCP transport")
        if transport.get("type") == "stdio":
            overrides.extend(["-c", f'mcp_servers.{name}.command="true"'])
        overrides.extend(["-c", f"mcp_servers.{name}.enabled=false"])
    return overrides


class HarnessExit(Exception):
    def __init__(self, code: int, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


class SpecError(ValueError):
    """Invalid step instruction, with the offending source line."""


@dataclass(frozen=True)
class StepSpec:
    step: int
    name: str
    text: str
    allowed: tuple[str, ...]
    ac: tuple[str, ...]


def _section(text: str, heading: str) -> list[tuple[int, str]]:
    lines = text.splitlines()
    starts = [i for i, line in enumerate(lines) if line == heading]
    if len(starts) != 1:
        raise SpecError(f"절이 정확히 하나여야 한다: {heading!r} (줄: "
                        f"{[i + 1 for i in starts]})")
    start = starts[0] + 1
    end = next((i for i in range(start, len(lines)) if lines[i].startswith("## ")),
               len(lines))
    return list(enumerate(lines[start:end], start + 1))


def parse_allowed_paths(text: str) -> list[str]:
    heading = "## 변경 허용 경로"
    paths = []
    for number, line in _section(text, heading):
        path = line.strip()
        if not path:
            continue
        base = path[:-1] if path.endswith("/") else path
        if (any(char in path for char in "*?[") or path.startswith(("/", ":"))
                or ".." in path.split("/") or base in {"", "."}
                or base != posixpath.normpath(base)
                or base == "phases" or path.startswith("phases/")):
            raise SpecError(f"허용되지 않은 경로 (줄 {number}): {line!r}")
        paths.append(path)
    if not paths:
        raise SpecError(f"경로가 비었다: {heading!r}")
    return paths


def path_allowed(path: str, allowed: Sequence[str]) -> bool:
    return any(path.startswith(item) if item.endswith("/") else path == item
               for item in allowed)


def parse_ac(text: str) -> list[str]:
    heading = "## Acceptance Criteria"
    lines = _section(text, heading)
    fences = [(i, number, line) for i, (number, line) in enumerate(lines)
              if line.startswith("```")]
    if len(fences) != 2:
        raise SpecError(f"닫힌 펜스 블록이 정확히 하나여야 한다: {heading!r}; "
                        f"펜스 줄: {[(n, line) for _, n, line in fences]!r}")
    start, number, opening = fences[0]
    if opening[3:] != "bash":
        raise SpecError(f"bash 블록이어야 한다 (줄 {number}): {opening!r}")
    commands = []
    # Even syntax-only noninteractive bash can source BASH_ENV before parsing.
    env = os.environ.copy()
    env.pop("BASH_ENV", None)
    for number, line in lines[start + 1:fences[1][0]]:
        command = line.strip()
        if not command or command.startswith("#"):
            continue
        if command.endswith("\\") or "<<" in command:
            raise SpecError(f"여러 줄 AC는 허용하지 않는다 (줄 {number}): {line!r}")
        result = subprocess.run(["bash", "-n", "-c", command], env=env,
                                capture_output=True)
        if result.returncode:
            raise SpecError(f"AC 문법 오류 (줄 {number}): {line!r}: "
                            f"{result.stderr.decode(errors='replace').strip()}")
        commands.append(command)
    if not commands:
        raise SpecError(f"커맨드가 비었다: {heading!r}; {opening!r}")
    return commands


def now_kst() -> str:
    return datetime.now(timezone(timedelta(hours=9))).isoformat(timespec="seconds")


def read_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as stream:
        data = json.load(stream)
    if not isinstance(data, dict):
        raise ValueError(f"JSON 객체가 아니다: {path}")
    return data


def write_json_atomic(path: Path, data: dict) -> None:
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         prefix=f".{path.name}.", delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(data, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    except BaseException:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
        raise


def repo_root(cwd: Path) -> Path:
    result = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=cwd,
                            capture_output=True)
    if result.returncode:
        raise HarnessExit(EXIT_ERROR, result.stderr.decode(errors="replace"))
    return Path(os.fsdecode(result.stdout).rstrip("\n"))


class Executor:
    def __init__(self, root: Path, phase_dir: str, *, push: bool = False):
        self.root = root
        self.phase_dir = phase_dir
        self.push = push
        self.phase_path = root / "phases" / phase_dir
        self.index_path = self.phase_path / "index.json"
        self.top_index_path = root / "phases/index.json"
        self.run_dir = self.phase_path / ".run"
        self.lock_path = root / "phases/.run/lock"
        self.branch = f"feat-{phase_dir}"
        self._lock_file = None
        self._gh_config = None
        self.session_timeout = 1800
        self.child_pgid = None

    def run_child(self, argv: list[str], *, env: dict[str, str], timeout: float,
                  stdin_text: str | None = None, stdout_path: Path | None = None,
                  on_spawn: Callable[[int], None] | None = None) -> ChildResult:
        # Files avoid pipe deadlocks, including inherited pipes held by descendants.
        with tempfile.TemporaryFile() as out, tempfile.TemporaryFile() as err:
            child = subprocess.Popen(
                argv, cwd=self.root, env=env, start_new_session=True,
                stdin=subprocess.PIPE if stdin_text is not None else subprocess.DEVNULL,
                stdout=out, stderr=err)
            pgid = child.pid
            self.child_pgid = pgid
            timed_out = False

            def send_group(sig: int) -> bool:
                if pgid is None or pgid <= 1 or pgid == os.getpgrp():
                    return False
                try:
                    os.killpg(pgid, sig)
                    return True
                except (ProcessLookupError, PermissionError):
                    return False

            try:
                if on_spawn is not None:
                    on_spawn(pgid)
                try:
                    child.communicate(
                        input=stdin_text.encode("utf-8") if stdin_text is not None else None,
                        timeout=timeout)
                except subprocess.TimeoutExpired:
                    timed_out = True
            finally:
                try:
                    if send_group(signal.SIGTERM):
                        deadline = time.monotonic() + 0.3
                        while time.monotonic() < deadline and send_group(0):
                            child.poll()  # Reap the leader while descendants terminate.
                            time.sleep(0.02)
                        if send_group(0):
                            send_group(signal.SIGKILL)
                    child.wait()
                    if child.stdin is not None:
                        child.stdin.close()
                finally:
                    self.child_pgid = None
            out.seek(0)
            err.seek(0)
            stdout = out.read().decode("utf-8", errors="replace")
            stderr = err.read().decode("utf-8", errors="replace")
            if stdout_path is not None:
                stdout_path.write_text(stdout, encoding="utf-8")
            return ChildResult(child.returncode, timed_out, stdout, stderr)

    def codex_preflight(self) -> list[str]:
        env = self.child_env(strip_orca=True)

        def listing(flags: list[str]) -> list[dict]:
            try:
                result = self.run_child(["codex", *flags, "mcp", "list", "--json"],
                                        env=env, timeout=120)
                if result.timed_out or result.returncode != 0:
                    raise ValueError(f"MCP 목록 명령 실패: {result.stderr}")
                servers = json.loads(result.stdout)
                if not isinstance(servers, list) or any(
                        not isinstance(s, dict) or type(s.get("enabled")) is not bool
                        for s in servers):
                    raise ValueError("MCP 목록은 enabled 불리언을 가진 객체의 JSON 배열이어야 한다")
                return servers
            except (OSError, ValueError) as exc:
                raise HarnessExit(EXIT_ERROR, f"Codex preflight 실패: {exc}") from exc

        overrides = codex_mcp_overrides(listing([]))
        if any(s["enabled"] for s in listing([*CODEX_CONFIG_FLAGS, *overrides])):
            raise HarnessExit(EXIT_ERROR, "Codex preflight: 켜진 MCP 서버가 남아 있다")
        return overrides

    def codex_argv(self, overrides: list[str], last_path: Path) -> list[str]:
        return ["codex", "exec", *CODEX_CONFIG_FLAGS, *overrides,
                "-s", "workspace-write", "--dangerously-bypass-hook-trust", "--ephemeral",
                "-C", str(self.root), "--json", "-o", str(last_path), "-"]

    def result_path(self, unit: str) -> Path:
        return self.run_dir / f"{unit}-result.json"

    def build_prompt(self, unit: str, task_text: str, allowed: Sequence[str],
                     failure: str | None = None) -> str:
        parts = ["너는 이 저장소의 구현 세션이다. 이 세션은 시도 하나다. "
                 "작업하고 AC를 직접 돌려 본 뒤 결과를 한 번 보고하고 끝낸다."]
        docs = [self.root / "AGENTS.md", self.root / "CONTEXT.md",
                *sorted((self.root / "docs/adr").glob("*.md")), self.root / "docs/PRD.md"]
        for path in docs:
            if path.is_file():
                parts.append(f"## {path.relative_to(self.root)}\n{path.read_text(encoding='utf-8')}")
        summaries = [f"step{s['step']} {s['name']}: {s.get('summary', '')}"
                     for s in self.load_index()["steps"] if s["status"] == "completed"]
        parts.extend(["## 완료된 step 요약\n" + "\n".join(summaries),
                      "## 작업 본문\n" + task_text,
                      "## 변경 허용 경로\n" + "\n".join(allowed),
                      f"## 결과 계약\n{self.result_path(unit).relative_to(self.root)}에 JSON 객체 하나를 쓴다. "
                      '필드는 status("completed" | "error" | "blocked"), summary, '
                      'error 상태의 error_message 또는 blocked 상태의 blocked_reason이다. '
                      "blocked는 사람만 풀 수 있는 자격 증명, 외부 인증, 수동 설정에만 쓴다.",
                      f"## 금지\nphases/index.json과 phases/{self.phase_dir}/index.json을 쓰지 마라.\n"
                      "커밋하지 마라.\npush, gh 쓰기, 외부 게시, 원격 DB 변경을 하지 마라.\n"
                      "허용 경로 밖을 바꾸지 마라."])
        if failure is not None:
            parts.append("## 직전 시도 실패 사유\n" + failure)
        return "\n\n".join(parts)

    def run_codex(self, unit: str, prompt: str, *,
                  on_spawn: Callable[[int], None] | None = None) -> ChildResult:
        overrides = self.codex_preflight()
        self.run_dir.mkdir(parents=True, exist_ok=True)
        return self.run_child(
            self.codex_argv(overrides, self.run_dir / f"{unit}-last.txt"),
            env=self.child_env(strip_orca=True), timeout=self.session_timeout,
            stdin_text=prompt, stdout_path=self.run_dir / f"{unit}-session.jsonl",
            on_spawn=on_spawn)

    @property
    def issue(self) -> int:
        return self.load_index()["issue"]

    def git(self, *args: str, env: dict[str, str] | None = None,
            check: bool = True, input: bytes | None = None) -> subprocess.CompletedProcess:
        result = subprocess.run(["git", *args], cwd=self.root, env=env,
                                input=input, capture_output=True)
        if check and result.returncode:
            raise HarnessExit(EXIT_ERROR,
                              f"git {list(args)!r}: {result.stderr.decode(errors='replace')}")
        return result

    def head(self) -> str:
        return self.git("rev-parse", "HEAD").stdout.decode().strip()

    def changed_paths(self) -> list[str]:
        records = iter(self.git("status", "--porcelain=v1", "-z",
                                "--untracked-files=all").stdout.split(b"\0"))
        paths = []
        for record in records:
            if not record:
                continue
            paths.append(os.fsdecode(record[3:]))
            if b"R" in record[:2] or b"C" in record[:2]:
                paths.append(os.fsdecode(next(records)))
        return list(dict.fromkeys(paths))

    def load_index(self) -> dict:
        return read_json(self.index_path)

    def load_step_specs(self) -> list[StepSpec]:
        if hasattr(self, "specs"):
            return self.specs
        specs = []
        errors = []
        for step in self.load_index()["steps"]:
            path = f"phases/{self.phase_dir}/step{step['step']}.md"
            result = self.git("show", f"HEAD:{path}", check=False)
            if result.returncode:
                errors.append(f"{path}: HEAD 파일을 읽을 수 없다: "
                              f"{result.stderr.decode(errors='replace').strip()}")
                continue
            try:
                text = result.stdout.decode("utf-8")
            except UnicodeError as exc:
                errors.append(f"{path}: UTF-8 오류: {exc}")
                continue
            parsed = []
            for parser in (parse_allowed_paths, parse_ac):
                try:
                    parsed.append(tuple(parser(text)))
                except SpecError as exc:
                    errors.append(f"{path}: {exc}")
            if len(parsed) == 2:
                specs.append(StepSpec(step["step"], step["name"], text, *parsed))
        if errors:
            raise HarnessExit(EXIT_ERROR, "step 지시서 위반:\n" + "\n".join(errors))
        self.specs = specs
        return self.specs

    def save_index(self, data: dict) -> None:
        write_json_atomic(self.index_path, data)

    def load_top_index(self) -> dict:
        return read_json(self.top_index_path)

    def save_top_index(self, data: dict) -> None:
        write_json_atomic(self.top_index_path, data)

    def set_top_status(self, status: str) -> None:
        data = self.load_top_index()
        for phase in data["phases"]:
            if phase["dir"] == self.phase_dir:
                phase["status"] = status
                stamps = {"completed": "completed_at", "error": "failed_at",
                          "blocked": "blocked_at"}
                for key in stamps.values():
                    phase.pop(key, None)
                if status in stamps:
                    phase[stamps[status]] = now_kst()
                self.save_top_index(data)
                return
        raise HarnessExit(EXIT_ERROR, f"top index에 phase가 없다: {self.phase_dir}")

    def child_env(self, *, strip_orca: bool = False) -> dict[str, str]:
        env = os.environ.copy()
        for key in list(env):
            if key in {"GH_TOKEN", "GITHUB_TOKEN", "SSH_AUTH_SOCK"} or (
                    strip_orca and key.startswith("ORCA_")):
                del env[key]
        if self._gh_config is None:
            self._gh_config = tempfile.TemporaryDirectory(prefix="harness-gh-")
        env["GH_CONFIG_DIR"] = self._gh_config.name
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        return env

    def acquire_lock(self) -> None:
        if self._lock_file is not None:
            return
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        stream = self.lock_path.open("a+b")
        try:
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            stream.close()
            raise HarnessExit(EXIT_ERROR, "다른 실행기가 이 worktree에서 실행 중이다") from exc
        self._lock_file = stream

    def commit_paths(self, paths: Iterable[str], message: str) -> str:
        ref = self.git("symbolic-ref", "-q", "HEAD", check=False)
        if ref.returncode or ref.stdout.decode().strip() != f"refs/heads/{self.branch}":
            raise HarnessExit(EXIT_ERROR, f"커밋 브랜치가 {self.branch}가 아니다")
        paths = list(paths)
        if not paths:
            raise ValueError("커밋 경로가 비었다")
        env = os.environ.copy()
        env["GIT_LITERAL_PATHSPECS"] = "1"
        # A staged deletion (including a rename source) no longer exists in
        # the index, so git add rejects its literal pathspec. It is already
        # staged correctly unless the worktree has recreated that path.
        deleted = self.git("diff", "--cached", "--name-only", "-z",
                           "--no-renames", "--diff-filter=D")
        staged_deletions = {os.fsdecode(p) for p in deleted.stdout.split(b"\0") if p}
        to_add = [path for path in paths
                  if path not in staged_deletions or os.path.lexists(self.root / path)]
        if to_add:
            self.git("add", "--", *to_add, env=env)
        cached = self.git("diff", "--cached", "--name-only", "-z", "--no-renames")
        staged = {os.fsdecode(p) for p in cached.stdout.split(b"\0") if p}
        if staged != set(paths):
            self.git("reset", "-q")
            raise HarnessExit(EXIT_ERROR, "stage된 경로가 요청한 커밋 경로와 다르다")
        self.git("commit", "-q", "-m", message)
        return self.head()

    def commit_meta(self, label: str, extra_paths: Iterable[str] = ()) -> str | None:
        candidates = {self.index_path.relative_to(self.root).as_posix(),
                      self.top_index_path.relative_to(self.root).as_posix(), *extra_paths}
        paths = sorted(candidates.intersection(self.changed_paths()))
        if not paths:
            return None
        return self.commit_paths(paths, f"chore: {self.phase_dir} {label} (#{self.issue})")

    @staticmethod
    def _last_step(data: dict) -> dict | None:
        return next((step for step in reversed(data["steps"])
                     if step["status"] != "pending"), None)

    @classmethod
    def _is_pending_reset(cls, before: dict, after: dict) -> bool:
        candidate = copy.deepcopy(before)
        step = cls._last_step(candidate)
        if step is not None and step["status"] in {"error", "blocked"}:
            pos = next(i for i, item in enumerate(candidate["steps"]) if item is step)
            step["status"] = "pending"
            for key in ("error_message", "blocked_reason", "failed_at", "blocked_at"):
                if key not in after.get("steps", [{}] * (pos + 1))[pos]:
                    step.pop(key, None)
            if candidate == after:
                return True
        candidate = copy.deepcopy(before)
        review = candidate.get("review", {})
        if review.get("status") == "blocked":
            review["status"] = "pending"
            if "blocked_reason" not in after.get("review", {}):
                review.pop("blocked_reason", None)
            if candidate == after:
                return True
        return False

    def prepare(self) -> str | None:
        current = self.git("symbolic-ref", "-q", "HEAD", check=False)
        if current.stdout.decode().strip() != f"refs/heads/{self.branch}":
            exists = self.git("show-ref", "--verify", "--quiet",
                              f"refs/heads/{self.branch}", check=False)
            if exists.returncode == 0:
                self.git("checkout", self.branch)
            else:
                self.git("checkout", "-b", self.branch)
        changed = self.changed_paths()
        prefix = f"phases/{self.phase_dir}/"
        if any(not path.startswith(prefix) for path in changed):
            raise HarnessExit(EXIT_ERROR, "phase 디렉토리 밖에 변경이 있다")
        try:
            data = self.load_index()
            if f"{prefix}index.json" in changed:
                before = json.loads(self.git("show", f"HEAD:{prefix}index.json").stdout)
                if not self._is_pending_reset(before, data):
                    raise HarnessExit(EXIT_ERROR, "허용되지 않은 phase index 변경이다")
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise HarnessExit(EXIT_ERROR, f"phase index를 읽을 수 없다: {exc}") from exc
        last = self._last_step(data)
        if last and last["status"] in {"error", "blocked"}:
            code = EXIT_ERROR if last["status"] == "error" else EXIT_BLOCKED
            raise HarnessExit(code, f"마지막 step 상태: {last['status']}")
        if data.get("review", {}).get("status") == "blocked":
            raise HarnessExit(EXIT_BLOCKED, "review가 blocked 상태다")
        if "created_at" not in data:
            data["created_at"] = now_kst()
            data["base_commit"] = self.head()
            data.setdefault("review", {"status": "pending", "end_sha": None, "round": 0})
            self.save_index(data)
        previous = None
        for phase in self.load_top_index()["phases"]:
            if phase["dir"] == self.phase_dir and phase["status"] in {"error", "blocked"}:
                previous = phase["status"]
                self.set_top_status("pending")
                break
        self.commit_meta("prepare", changed)
        return previous

    def run(self) -> int:
        try:
            self.acquire_lock()
            self.prepare()
            self.load_step_specs()
            return EXIT_OK
        except HarnessExit as exc:
            print(exc.message, file=sys.stderr)
            return exc.code
        except (OSError, ValueError, KeyError, TypeError) as exc:
            print(str(exc), file=sys.stderr)
            return EXIT_ERROR


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase_dir")
    parser.add_argument("--push", action="store_true")
    args = parser.parse_args(argv)
    try:
        root = repo_root(Path.cwd())
        if not (root / "phases" / args.phase_dir / "index.json").is_file():
            print("phase index가 없다", file=sys.stderr)
            return EXIT_ERROR
        return Executor(root, args.phase_dir, push=args.push).run()
    except (HarnessExit, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return EXIT_ERROR


if __name__ == "__main__":
    sys.exit(main())
