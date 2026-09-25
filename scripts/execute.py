"""Repository harness primitives (Python 3.10 standard library only)."""
import argparse
import copy
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import posixpath
import re
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import time
from typing import Callable, Iterable, Sequence

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_BLOCKED = 2
EXIT_REVIEW = 3
MAX_ATTEMPTS = 3
MAX_FIX_ROUNDS = 2
GH_ATTEMPTS = 3
TOOL_STATE_DIRS = ("graft/", ".omc/")
REVIEW_CONTRACT: str = (
    "이 리뷰에서 파일을 고치거나 커밋, push, `gh` 쓰기, 외부 게시, 원격 DB 변경을 하지 마라. "
    "출력의 마지막 줄은 정확히 `REVIEW_RESULT: passed` 또는 `REVIEW_RESULT: failed`여야 한다."
)


def parse_verdict(text: str) -> str | None:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    match = re.fullmatch(r"REVIEW_RESULT: (passed|failed)", lines[-1]) if lines else None
    return match.group(1) if match else None


@dataclass
class AttemptOutcome:
    status: str
    summary: str | None = None
    reason: str | None = None
    attempts: int = 0
    pre_sha: str = ""

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


class HarnessInterrupted(BaseException):
    """Termination requested; preserve the attempt marker for recovery."""


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
        self.ac_timeout = 600
        self.gh_timeout = 60
        self.review_timeout = 1800
        self.child_pgid = None
        self.marker = None
        self.resume = None
        self._signal_handlers = {}
        self._review_text = {}
        self._git_guard_paths = None
        self._git_guard_changed = False
        self._guard_pending = None
        self._ignored_baselines = {}
        # Resolve once, before any child can change repository configuration.
        self.git_guard_path = self.root / os.fsdecode(self.git(
            "rev-parse", "--git-path", f"harness/{phase_dir}/git-guard.json").stdout).strip()

    def worktree_tree(self, base_sha: str) -> str:
        temporary = None
        try:
            temporary = Path(tempfile.mkdtemp(prefix="harness-index-"))
            if temporary.resolve().is_relative_to(self.root.resolve()):
                raise HarnessExit(EXIT_ERROR, "임시 index 디렉토리가 저장소 안에 있다")
            env = os.environ.copy()
            env["GIT_INDEX_FILE"] = str(temporary / "index")
            self.git("read-tree", base_sha, env=env)
            self.git("add", "-A", env=env)
            return self.git("write-tree", env=env).stdout.decode().strip()
        except OSError as exc:
            raise HarnessExit(EXIT_ERROR, f"작업 트리 스냅샷 실패: {exc}") from exc
        finally:
            if temporary is not None:
                shutil.rmtree(temporary)

    def snapshot(self, unit: str, k: int, base_sha: str) -> str:
        try:
            tree = self.worktree_tree(base_sha)
            commit = self.git("commit-tree", tree, "-p", base_sha, "-m",
                              f"harness snapshot {self.phase_dir} {unit} attempt{k}")
            ref = f"refs/harness/{self.phase_dir}/{unit}/attempt{k}-{time.time_ns()}"
            self.git("update-ref", ref, commit.stdout.decode().strip(), "")
            return ref
        except OSError as exc:
            raise HarnessExit(EXIT_ERROR, f"스냅샷 실패: {exc}") from exc

    def rollback(self, unit: str, k: int, target_sha: str) -> str:
        ref = self.snapshot(unit, k, target_sha)
        branch = self.git("symbolic-ref", "-q", "HEAD", check=False)
        if branch.returncode or branch.stdout.decode().strip() != f"refs/heads/feat-{self.phase_dir}":
            raise HarnessExit(EXIT_ERROR, f"롤백 브랜치가 feat-{self.phase_dir}가 아니다: {ref}")
        self.git("reset", "--hard", target_sha)
        self.git("clean", "-fd")
        if self.marker and self.marker["unit"] == unit and "ignored_before" in self.marker:
            new_paths = self.ignored_paths() - set(self.marker["ignored_before"])
            for name in sorted(new_paths, key=lambda p: len(Path(p).parts), reverse=True):
                if (not any(name == d.rstrip("/") or name.startswith(d) for d in TOOL_STATE_DIRS)
                        and path_allowed(name, self.marker.get("allowed", []))):
                    path = self.root / name
                    # Never follow a session-created directory symlink outside the scope.
                    parent = path.parent.resolve()
                    if (parent.is_relative_to(self.root.resolve()) and path_allowed(
                            str((parent / path.name).relative_to(self.root.resolve())),
                            self.marker.get("allowed", []))):
                        self.remove_ignored(path)
        if self.git("status", "--porcelain").stdout:
            raise HarnessExit(EXIT_ERROR, f"롤백 뒤 작업 트리가 깨끗하지 않다: {ref}")
        return ref

    @property
    def marker_path(self) -> Path:
        return self.root / os.fsdecode(self.git("rev-parse", "--git-path",
            f"harness/{self.phase_dir}/attempt.json").stdout).strip()

    def save_marker(self, marker: dict) -> None:
        self.marker_path.parent.mkdir(parents=True, exist_ok=True)
        self.marker = marker
        write_json_atomic(self.marker_path, self.marker)

    def load_marker(self) -> dict | None:
        try:
            return read_json(self.marker_path)
        except FileNotFoundError:
            return None

    def clear_marker(self) -> None:
        self.marker_path.unlink(missing_ok=True)
        self.marker = None

    def _kill_stale_codex(self, pgid: int | None) -> None:
        if pgid is None or pgid <= 1 or pgid == os.getpgrp():
            return
        try:
            result = subprocess.run(["ps", "-A", "-o", "pid=,pgid=,command="],
                                    capture_output=True, text=True)
            if result.returncode:
                raise HarnessExit(EXIT_ERROR, "복구 ps 실패: marker 유지, 롤백 중단")
            for line in result.stdout.splitlines():
                fields = line.split(None, 2)
                if len(fields) != 3 or fields[1] != str(pgid):
                    continue
                if any(os.path.basename(token) in {"codex", "codex.js"}
                       for token in fields[2].split()):
                    try:
                        os.killpg(pgid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    return
        except (OSError, ValueError) as exc:
            raise HarnessExit(EXIT_ERROR, f"복구 프로세스 확인/종료 실패: {exc}") from exc

    def recover(self) -> None:
        try:
            marker = self.load_marker()
            if marker is None:
                return
            if (not isinstance(marker.get("unit"), str)
                    or not re.fullmatch(r"[A-Za-z0-9_-]+", marker["unit"])
                    or type(marker.get("k")) is not int or marker["k"] < 1
                    or not isinstance(marker.get("pre_sha"), str)
                    or not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", marker["pre_sha"])
                    or "feat_sha" not in marker
                    or (marker["feat_sha"] is not None and not isinstance(marker["feat_sha"], str))
                    or "pgid" not in marker
                    or (marker["pgid"] is not None and type(marker["pgid"]) is not int)):
                raise ValueError("marker 필드가 잘못되었다")
            if marker.get("stage") == "feat_done":
                match = re.fullmatch(r"(step|fix)(\d+)", marker["unit"])
                result = self.read_result(marker["unit"])
                if (self.head() != marker["feat_sha"] or match is None
                        or result is None or result["status"] != "completed"
                        or not isinstance(result.get("summary"), str)
                        or not result["summary"].strip()
                        or (match[1] == "step" and not any(s["step"] == int(match[2])
                                   for s in self.load_index()["steps"]))):
                    raise ValueError("feat_done의 HEAD, unit 또는 result가 무효다")
            elif marker.get("stage") != "running":
                raise ValueError(f"지원하지 않는 stage: {marker.get('stage')!r}")
            elif self.head() != marker["pre_sha"]:
                raise ValueError("HEAD가 pre_sha와 다르다")
        except (OSError, ValueError, HarnessExit) as exc:
            raise HarnessExit(EXIT_ERROR, f"복구 거부 {self.marker_path}: {exc}") from exc
        self.marker = marker
        env_changed = False
        if "env_before" in marker:
            env_now = self.env_fingerprint()
            if "env_dirs" not in marker:  # Older markers never recorded .env directories.
                env_now = {name: value for name, value in env_now.items() if value != "dir"}
            env_changed = env_now != marker["env_before"]
        if "ignored_before" in marker:
            self._ignored_baselines[marker["unit"]] = set(marker["ignored_before"])
        if marker["stage"] == "feat_done" and not env_changed:
            if match[1] == "fix":
                data = self.load_index()
                path = self.index_path.relative_to(self.root).as_posix()
                committed = json.loads(self.git("show", f"HEAD:{path}").stdout)
                data["review"]["status"] = "pending"
                data["review"]["fixes"] = committed.get("review", {}).get("fixes", 0) + 1
                data["review"].pop("blocked_reason", None)
                self.save_index(data)
                self.commit_meta(f"{marker['unit']} 반영")
                self.clear_marker()
            else:
                self.confirm_step(int(match[2]), "completed", result["summary"])
            return
        self._kill_stale_codex(marker["pgid"])
        self.rollback(marker["unit"], marker["k"], marker["pre_sha"])
        if env_changed:
            reason = "④ 크래시 뒤 .env 지문 변경: 보관 바이트 없음, 수동 복원 필요"
            if marker["unit"].startswith("step"):
                self.confirm_step(int(marker["unit"][4:]), "error", reason)
                self.issue_comment(f"{marker['unit']} error: {reason}")
            else:
                self.finish_fix(int(marker["unit"][3:]), AttemptOutcome("error", reason=reason))
            raise HarnessExit(EXIT_ERROR, reason)
        self.clear_marker()
        self.resume = {"unit": marker["unit"], "next_k": marker["k"] + 1}

    def install_signal_handlers(self) -> None:
        def interrupted(signum, frame):
            raise HarnessInterrupted(f"신호 {signum}")
        for signum in (signal.SIGTERM, signal.SIGHUP):
            if signum not in self._signal_handlers:
                self._signal_handlers[signum] = signal.signal(signum, interrupted)

    def restore_signal_handlers(self) -> None:
        for signum, handler in self._signal_handlers.items():
            signal.signal(signum, handler)
        self._signal_handlers.clear()

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

    def env_fingerprint(self) -> dict[str, str]:
        result = {}
        for path in self.root.iterdir():
            if (path.name != ".env" and not path.name.startswith(".env.")) \
                    or path.name == ".env.example":
                continue
            if path.is_file():
                value = path.read_bytes()
            elif path.is_symlink() or (os.path.lexists(path) and not path.is_dir()):
                value = repr(self.capture_path(path)).encode()
            elif path.is_dir():
                result[path.name] = "dir"  # Presence only; real directories are never captured.
                continue
            else:
                continue
            result[path.name] = hashlib.sha256(value).hexdigest()
        return result

    def ignored_paths(self) -> set[str]:
        paths = set()
        records = iter(self.git("status", "--porcelain=v1", "-z", "--ignored=matching").stdout.split(b"\0"))
        for record in records:
            if record[:2] == b"!!":
                paths.add(os.fsdecode(record[3:]))
            elif b"R" in record[:2] or b"C" in record[:2]:
                next(records)
        return paths

    @staticmethod
    def capture_path(path: Path):
        if path.is_symlink():
            return ("link", os.readlink(path), path.lstat().st_mode & 0o7777)
        if path.is_dir():
            return ("dir", {p.name: Executor.capture_path(p) for p in sorted(path.iterdir())},
                    path.stat().st_mode & 0o7777)
        if path.is_file():
            return ("file", path.read_bytes(), path.stat().st_mode & 0o7777)
        if os.path.lexists(path):
            mode = path.lstat().st_mode
            return ("special", stat.S_IFMT(mode), mode & 0o7777)
        return None

    @staticmethod
    def restore_path(path: Path, saved) -> None:
        # Unlink links themselves, including links substituted for directories.
        if Executor.capture_path(path) == saved:
            return
        if path.is_symlink() or (os.path.lexists(path) and not path.is_dir()):
            path.unlink()
        elif path.is_dir():
            if saved and saved[0] == "dir":
                for child in path.iterdir():
                    if child.name not in saved[1]:
                        Executor.restore_path(child, None)
            else:
                for child in path.iterdir():
                    Executor.restore_path(child, None)
                path.rmdir()
        if saved is None:
            return
        kind, content, mode = saved
        if kind == "dir":
            path.mkdir(exist_ok=True)
            for name, entry in content.items():
                Executor.restore_path(path / name, entry)
            path.chmod(mode)
        elif kind == "link":
            path.symlink_to(content)
            if hasattr(os, "lchmod"):
                os.lchmod(path, mode)
        elif kind == "special":
            if content != stat.S_IFIFO:
                raise OSError(f"복원할 수 없는 특수 파일 종류: {content}")
            os.mkfifo(path, mode)
        else:
            path.write_bytes(content)
            path.chmod(mode)

    def remove_ignored(self, path: Path) -> None:
        if path.name == ".env" or path.name.startswith(".env."):
            print(str(path.relative_to(self.root)), file=sys.stderr)
            return
        if path.is_dir() and not path.is_symlink():
            for child in path.iterdir():
                self.remove_ignored(child)
            try:
                path.rmdir()
            except OSError:
                pass  # A protected .env file can keep this directory alive.
        else:
            path.unlink(missing_ok=True)

    def capture_env(self) -> dict:
        # Files, links and special files only; real .env directories are left alone.
        return {p.name: self.capture_path(p) for p in self.root.iterdir()
                if (p.name == ".env" or p.name.startswith(".env."))
                and p.name != ".env.example" and os.path.lexists(p)
                and (p.is_symlink() or not p.is_dir())}

    def restore_env(self, saved: dict, *, keep_new: bool = False) -> None:
        names = saved.keys() if keep_new else self.capture_env().keys() | saved.keys()
        for name in names:
            self.restore_path(self.root / name, saved.get(name))

    def restore_env_change(self, before: dict[str, str], saved: dict,
                           regular_reason: str, context: str = "", *,
                           keep_new: bool = False) -> str | None:
        after = self.env_fingerprint()
        if after == before:
            return None
        changed = {name for name in before.keys() | after.keys()
                   if before.get(name) != after.get(name)}
        self.restore_env(saved, keep_new=keep_new)
        suffix = f" ({context})" if context else ""
        created = sorted(name for name in changed if name not in before)
        kept_new = (f" (리뷰어가 만든 새 파일은 지우지 않았다: 사람이 확인 {created})"
                    if keep_new and created else "")
        dirs = sorted(name for name in changed if "dir" in (before.get(name), after.get(name)))
        if dirs:
            return (f"④ .env 디렉토리 변경: 수동 복원 필요{suffix} {dirs}. .env·.env.*는 사람이 두는"
                    " 비밀 파일 자리다(가상환경은 .venv). 디렉토리를 확인·정리하고, step error면"
                    f" pending으로 되돌린 뒤 재실행하라{kept_new}")
        if any(saved.get(name) and saved[name][0] == "link" for name in changed):
            return f"④ .env 링크 대상 변경: 수동 복원 필요{suffix}{kept_new}"
        if created:
            if keep_new:
                return f"{regular_reason}{kept_new}"
            return (f"{regular_reason} (새 파일 제거 {created}. 실제 값 파일은 사람이 만들고"
                    " AI(세션·AC)는 .env.example만 만든다)")
        return regular_reason

    def git_env_reason(self, git_reason: str, before: dict[str, str], saved: dict,
                       regular_reason: str, context: str = "") -> str:
        env_reason = self.restore_env_change(before, saved, regular_reason, context)
        self.restore_env(saved)  # Also mode-only changes, which the fingerprint misses.
        return f"{git_reason}\n{env_reason}" if env_reason else git_reason

    def git_fingerprint(self) -> dict:
        if self._git_guard_paths is None:
            self._git_guard_paths = {name: self.root / os.fsdecode(self.git(
                "rev-parse", "--git-path", name).stdout).strip()
                for name in ("config", "hooks", "info")}
        result = {}
        for name, path in self._git_guard_paths.items():
            if name == "config" and path.is_file() and not path.is_symlink():
                # --file outside the repository cannot activate its fsmonitor/hooks.
                env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
                with tempfile.TemporaryDirectory(prefix="harness-config-") as cwd:
                    parsed = subprocess.run(["git", "config", "--file", str(path.absolute()),
                                             "--null", "--list"], cwd=cwd, env=env,
                                            capture_output=True)
                pairs = [record.partition(b"\n") for record in parsed.stdout.split(b"\0") if record]
                values = [(key, value) for key, _, value in pairs
                          if not key.lower().startswith(b"branch.")]
                result[name] = hashlib.sha256(repr((parsed.returncode, values)).encode()).hexdigest()
            else:
                result[name] = hashlib.sha256(repr(self.capture_path(path)).encode()).hexdigest()
        return result

    def capture_git_guard(self):
        fingerprint = self.git_fingerprint()
        return fingerprint, {name: self.capture_path(path)
                             for name, path in (self._git_guard_paths or {}).items()}

    def git_guard_failed(self, before) -> bool:
        # Keep the guard pending until the comparison settles, so a signal mid-way
        # still leaves it for restore_pending_git_guard.
        fingerprint, saved = before
        try:
            if self.git_fingerprint() == fingerprint:
                self.settle_git_guard(before)
                return False
            for name, entry in saved.items():
                self.restore_path(self._git_guard_paths[name], entry)
            if self.git_fingerprint() != fingerprint:
                raise OSError("복원 후 Git 설정 불일치")
        except (OSError, ValueError) as exc:
            self.git_guard_path.parent.mkdir(parents=True, exist_ok=True)
            write_json_atomic(self.git_guard_path, {"baseline": fingerprint, "reason": str(exc)})
            self.settle_git_guard(before)
            raise HarnessExit(EXIT_ERROR,
                f"Git 설정이 복원되지 않았다. 확인 뒤 {self.git_guard_path}를 지워라") from exc
        self._git_guard_changed = True
        self.settle_git_guard(before)
        return True

    def settle_git_guard(self, before) -> None:
        if self._guard_pending is before:
            self._guard_pending = None

    def restore_pending_git_guard(self) -> None:
        if self._guard_pending is not None:
            self.git_guard_failed(self._guard_pending)

    def read_result(self, unit: str) -> dict | None:
        try:
            result = read_json(self.result_path(unit))
        except (OSError, ValueError):
            return None
        if not isinstance(result, dict) or result.get("status") not in (
                "completed", "error", "blocked"):
            return None
        return result

    def run_ac(self, lines: Sequence[str]) -> str | None:
        before = self.head()
        tree = self.worktree_tree(before)
        failure = None
        for line in lines:
            git_before = self.capture_git_guard()
            self._guard_pending = git_before
            result = self.run_child(["bash", "-o", "pipefail", "-c", line],
                                    env=self.child_env(), timeout=self.ac_timeout)
            if self.git_guard_failed(git_before):
                return "④ Git 설정 변경 감지·복원"
            if result.timed_out or result.returncode != 0:
                code = "timeout" if result.timed_out else f"종료 코드 {result.returncode}"
                failure = f"⑥ AC 실패: {line}\n{code}\n{(result.stdout + result.stderr)[-2000:]}"
                break
        after = self.head()
        if after != before or self.worktree_tree(after) != tree:
            mutation = "⑦ AC가 작업 트리를 바꿨다 (HEAD 또는 tree 변경)"
            return f"{failure}\n{mutation}" if failure else mutation
        return failure

    def attempt_unit(self, unit: str, task_text: str, allowed: Sequence[str],
                     ac: Sequence[str], *, start_k: int = 1) -> AttemptOutcome:
        failure = "재개 시 시도 소진"
        if unit not in self._ignored_baselines:
            self._ignored_baselines[unit] = self.ignored_paths()
        ignored_before = self._ignored_baselines[unit]
        for k in range(start_k, MAX_ATTEMPTS + 1):
            if self.changed_paths():
                raise HarnessExit(EXIT_ERROR, "시도 전 작업 트리가 더럽다")
            pre_sha = self.head()
            self.result_path(unit).unlink(missing_ok=True)
            env_before = self.env_fingerprint()
            env_saved = self.capture_env()
            git_before = self.capture_git_guard()
            prompt = self.build_prompt(unit, task_text, allowed,
                                       failure=failure if k != start_k else None)
            self.save_marker({"unit": unit, "k": k, "pre_sha": pre_sha,
                              "stage": "running", "feat_sha": None, "pgid": None,
                              "ignored_before": sorted(ignored_before), "allowed": list(allowed),
                              "env_before": env_before, "env_dirs": True})
            spawned = False

            def on_spawn(pgid: int) -> None:
                nonlocal spawned
                spawned = True
                self.marker["pgid"] = pgid
                self.save_marker(self.marker)

            try:
                self._guard_pending = git_before
                child = self.run_codex(unit, prompt, on_spawn=on_spawn)
            except BaseException:
                if not spawned:
                    self.clear_marker()
                raise
            if self.git_guard_failed(git_before):
                reason = self.git_env_reason("④ Git 설정 변경 감지·복원", env_before, env_saved,
                                             "④ .env 지문 변경: 복원됨")
                self.rollback(unit, k, pre_sha)
                return AttemptOutcome("error", reason=reason, attempts=k)
            self.save_marker(self.marker)
            env_reason = self.restore_env_change(
                env_before, env_saved, "④ .env 지문 변경: 복원됨")
            if env_reason is not None:
                self.rollback(unit, k, pre_sha)
                return AttemptOutcome("error", reason=env_reason, attempts=k)
            result = self.read_result(unit)
            if child.timed_out or child.returncode != 0:
                code = "timeout" if child.timed_out else f"종료 코드 {child.returncode}"
                failure = f"세션 실패: {code}\n{(child.stdout + child.stderr)[-2000:]}"
            elif result is None:
                failure = "result 없음 또는 무효"
            elif result["status"] == "blocked":
                self.rollback(unit, k, pre_sha)
                return AttemptOutcome("blocked", reason=result.get("blocked_reason"), attempts=k - 1)
            elif result["status"] == "error":
                failure = f"세션 error: {result.get('error_message') or '사유 없음'}"
            elif not isinstance(result.get("summary"), str) or not result["summary"].strip():
                failure = "① completed summary가 비었다"
            elif self.head() != pre_sha:
                failure = "② HEAD 변경: 세션이 커밋했다"
            else:
                outside = [p for p in self.changed_paths() if not path_allowed(p, allowed)]
                new_ignored = []
                for path in self.ignored_paths() - ignored_before:
                    parts = Path(path).parts
                    if (any(path == d.rstrip("/") or path.startswith(d) for d in TOOL_STATE_DIRS)
                            or path_allowed(path, allowed) or (parts and parts[0] == "phases" and ".run" in parts[1:])
                            or "__pycache__" in parts or path.endswith(".pyc")):
                        continue
                    new_ignored.append(path)
                if outside:
                    failure = f"③ 변경 허용 경로 위반: {outside}"
                elif new_ignored:
                    self.rollback(unit, k, pre_sha)
                    return AttemptOutcome("error", reason=(
                        f"⑤ 허용 경로 밖 새 무시 경로: 수동 정리 필요 {sorted(new_ignored)}"), attempts=k)
                else:
                    failure = self.run_ac(ac)
                    if self.git_guard_failed(git_before) or (failure and failure.startswith("④ Git")):
                        reason = self.git_env_reason(
                            "④ Git 설정 변경 감지·복원", env_before, env_saved,
                            "④ .env 지문 변경: AC 뒤 복원됨", "AC 뒤")
                        self.rollback(unit, k, pre_sha)
                        return AttemptOutcome("error", reason=reason, attempts=k)
                    env_reason = self.restore_env_change(
                        env_before, env_saved, "④ .env 지문 변경: AC 뒤 복원됨", "AC 뒤")
                    if env_reason is not None:
                        self.rollback(unit, k, pre_sha)
                        return AttemptOutcome("error", reason=env_reason, attempts=k)
                    if failure is None:
                        return AttemptOutcome("completed", summary=result["summary"],
                                              attempts=k, pre_sha=pre_sha)
            self.rollback(unit, k, pre_sha)
        return AttemptOutcome("error", reason=failure, attempts=MAX_ATTEMPTS)

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

    def _gh_pending(self) -> list[list[str]]:
        path = self.run_dir / "gh-pending.json"
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return []
        except (OSError, ValueError) as exc:
            print(f"gh 대기열 읽기 실패: {exc}", file=sys.stderr)
            return []
        if not isinstance(data, list):
            print("gh 대기열이 JSON 배열이 아니므로 버림", file=sys.stderr)
            return []
        issue = str(self.issue)
        valid = []
        for argv in data:
            if (isinstance(argv, list) and all(isinstance(arg, str) for arg in argv)
                    and ((len(argv) == 6 and argv[:5] ==
                          ["gh", "issue", "comment", issue, "--body"])
                         or (len(argv) == 8 and argv[:5] ==
                             ["gh", "issue", "edit", issue, "--remove-label"]
                             and argv[6] == "--add-label"
                             and {argv[5], argv[7]} ==
                             {"ready-for-agent", "ready-for-human"}))):
                valid.append(argv)
            else:
                print(f"허용되지 않은 gh 대기열 항목을 버림: {argv!r}", file=sys.stderr)
        return valid

    def _save_gh_pending(self, pending: list[list[str]]) -> None:
        try:
            path = self.run_dir / "gh-pending.json"
            if pending:
                self.run_dir.mkdir(parents=True, exist_ok=True)
                write_json_atomic(path, pending)
            else:
                path.unlink(missing_ok=True)
        except (OSError, ValueError) as exc:
            print(f"gh 대기열 저장 실패: {exc}", file=sys.stderr)

    def _try_gh(self, argv: list[str]) -> bool:
        for _ in range(GH_ATTEMPTS):
            try:
                result = subprocess.run(argv, cwd=self.root, env=os.environ.copy(),
                                        timeout=self.gh_timeout, capture_output=True)
                if result.returncode == 0:
                    return True
            except (OSError, ValueError, subprocess.SubprocessError):
                pass
        print(f"gh 명령 실패 ({GH_ATTEMPTS}회): {argv!r}", file=sys.stderr)
        return False

    def gh(self, *args: str) -> bool:
        argv = ["gh", *args]
        if self._try_gh(argv):
            return True
        try:
            pending = self._gh_pending()
            pending.append(argv)
            self._save_gh_pending(pending)
        except (OSError, ValueError, KeyError, TypeError) as exc:
            print(f"gh 대기열 갱신 실패: {exc}", file=sys.stderr)
        return False

    def retry_gh_pending(self) -> None:
        try:
            pending = self._gh_pending()
            failed = [argv for argv in pending if not self._try_gh(argv)]
            self._save_gh_pending(failed)
        except (OSError, ValueError, KeyError, TypeError) as exc:
            print(f"gh 대기열 재시도 실패: {exc}", file=sys.stderr)

    def issue_comment(self, body: str) -> None:
        suffix = "\n… [본문 잘림]"
        if len(body) > 60000:
            body = body[:60000 - len(suffix)] + suffix
        self.gh("issue", "comment", str(self.issue), "--body", body)

    def issue_blocked(self, reason: str) -> None:
        self.gh("issue", "edit", str(self.issue), "--remove-label", "ready-for-agent",
                "--add-label", "ready-for-human")
        self.issue_comment(f"blocked: {reason}")

    def issue_resume(self) -> None:
        try:
            result = subprocess.run(
                ["gh", "issue", "view", str(self.issue), "--json", "labels"],
                cwd=self.root, env=os.environ.copy(), timeout=self.gh_timeout,
                capture_output=True)
            if result.returncode:
                raise ValueError(f"view 종료 코드 {result.returncode}")
            data = json.loads(result.stdout)
            labels = {label["name"] for label in data["labels"]}
        except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as exc:
            print(f"gh 라벨 확인 실패, 복원 건너뜀: {exc}", file=sys.stderr)
            return
        if "ready-for-human" in labels and "ready-for-agent" not in labels:
            self.gh("issue", "edit", str(self.issue), "--remove-label", "ready-for-human",
                    "--add-label", "ready-for-agent")

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
        index = self.load_index()
        top_index = self.load_top_index()
        steps = index.get("steps")
        steps_valid = isinstance(steps, list) and bool(steps)
        if not steps_valid:
            errors.append(f"phase index steps: 비어 있지 않은 list가 필요하다; 실제 {steps!r}")
        else:
            names = []
            for position, step in enumerate(steps):
                if not isinstance(step, dict):
                    errors.append(f"phase index steps[{position}]: 객체가 필요하다; 실제 {step!r}")
                    steps_valid = False
                    continue
                number = step.get("step")
                if type(number) is not int or number != position:
                    errors.append(f"phase index steps[{position}].step: {position}이 필요하다; "
                                  f"실제 {number!r}")
                    steps_valid = False
                name = step.get("name")
                if name is None:
                    errors.append(f"phase index steps[{position}].name: 이름이 필요하다; "
                                  f"실제 {name!r}")
                    steps_valid = False
                elif name in names:
                    errors.append(f"phase index steps[{position}].name: 고유한 이름이 필요하다; "
                                  f"중복 {name!r}")
                    steps_valid = False
                else:
                    names.append(name)

        if index.get("phase") != self.phase_dir:
            errors.append(f"phase index phase: {self.phase_dir!r}이 필요하다; "
                          f"실제 {index.get('phase')!r}")
        phases = top_index.get("phases")
        matches = ([phase for phase in phases if isinstance(phase, dict)
                    and phase.get("dir") == self.phase_dir]
                   if isinstance(phases, list) else [])
        if len(matches) != 1:
            errors.append(f"phases/index.json phases: dir={self.phase_dir!r} 항목이 정확히 "
                          f"하나 필요하다; 실제 {len(matches)}개")
        elif matches[0].get("issue") != index.get("issue"):
            errors.append(f"phases/index.json issue: phase index issue "
                          f"{index.get('issue')!r}와 같아야 한다; 실제 {matches[0].get('issue')!r}")

        for step in steps if steps_valid else []:
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
            if key in {"GH_TOKEN", "GITHUB_TOKEN", "SSH_AUTH_SOCK", "BASH_ENV", "ENV"} or key.startswith("ORCA_"):
                del env[key]
        if self._gh_config is None:
            self._gh_config = tempfile.TemporaryDirectory(prefix="harness-gh-")
        count = int(env.get("GIT_CONFIG_COUNT", "0"))
        env[f"GIT_CONFIG_KEY_{count}"] = "credential.helper"
        env[f"GIT_CONFIG_VALUE_{count}"] = ""
        env["GIT_CONFIG_COUNT"] = str(count + 1)
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

    def commit_feat(self, message: str, pre_sha: str) -> str:
        if self.head() != pre_sha:
            raise HarnessExit(EXIT_ERROR, "feat 커밋 전 HEAD가 pre_sha와 다르다")
        changed = self.changed_paths()
        feat_sha = self.commit_paths(changed, message) if changed else pre_sha
        self.save_marker({**self.marker, "stage": "feat_done", "feat_sha": feat_sha})
        return feat_sha

    def confirm_step(self, step: int, status: str, text: str) -> None:
        fields = {"completed": ("summary", "completed_at"),
                  "error": ("error_message", "failed_at"),
                  "blocked": ("blocked_reason", "blocked_at")}
        key, stamp = fields[status]
        data = self.load_index()
        item = next((s for s in data["steps"] if s["step"] == step), None)
        if item is None:
            raise HarnessExit(EXIT_ERROR, f"index에 step{step}이 없다")
        for pair in fields.values():
            for field in pair:
                item.pop(field, None)
        item.update(status=status)
        item[key] = text
        item[stamp] = now_kst()
        self.save_index(data)
        if status in {"error", "blocked"}:
            self.set_top_status(status)
        self.commit_meta(f"step{step} {status}")
        self.clear_marker()

    def run_steps(self, specs: list[StepSpec]) -> None:
        for spec in specs:
            item = next(s for s in self.load_index()["steps"] if s["step"] == spec.step)
            if item["status"] == "completed":
                continue
            if item["status"] != "pending":
                code = EXIT_BLOCKED if item["status"] == "blocked" else EXIT_ERROR
                raise HarnessExit(code, f"step{spec.step} 상태: {item['status']}")
            unit = f"step{spec.step}"
            start_k = 1
            if self.resume and self.resume["unit"] == unit:
                start_k = self.resume["next_k"]
                self.resume = None
            outcome = self.attempt_unit(unit, spec.text, spec.allowed, spec.ac, start_k=start_k)
            if outcome.status == "completed":
                self.commit_feat(f"feat: {self.phase_dir} {unit} {spec.name} (#{self.issue})",
                                 outcome.pre_sha)
                self.confirm_step(spec.step, "completed", outcome.summary)
            else:
                self.confirm_step(spec.step, outcome.status, outcome.reason)
                if outcome.status == "blocked":
                    self.issue_blocked(outcome.reason)
                else:
                    self.issue_comment(f"step{spec.step} error: {outcome.reason}")
                code = EXIT_BLOCKED if outcome.status == "blocked" else EXIT_ERROR
                raise HarnessExit(code, outcome.reason or f"{unit} {outcome.status}")

    @staticmethod
    def _last_step(data: dict) -> dict | None:
        return next((step for step in reversed(data["steps"])
                     if step["status"] != "pending"), None)

    @classmethod
    def _is_pending_reset(cls, before: dict, after: dict) -> bool:
        equivalent_fixes = before != after
        before, after = copy.deepcopy(before), copy.deepcopy(after)
        for data in (before, after):
            if "review" in data:
                data["review"].setdefault("fixes", 0)
        if equivalent_fixes and before == after:
            return True
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
            data.setdefault("review", {"status": "pending", "end_sha": None, "round": 0, "fixes": 0})
            self.save_index(data)
        previous = None
        for phase in self.load_top_index()["phases"]:
            if phase["dir"] == self.phase_dir and phase["status"] in {"error", "blocked"}:
                previous = phase["status"]
                self.set_top_status("pending")
                break
        self.commit_meta("prepare", changed)
        return previous

    def review_argv(self, reviewer: str, scope: str) -> list[str]:
        if reviewer == "claude":
            return ["claude", "-p", "--setting-sources", "project,local",
                    "--dangerously-skip-permissions", "--disallowedTools",
                    "Edit,Write,MultiEdit,NotebookEdit", "--strict-mcp-config",
                    "--output-format", "json", f"/review {scope} {REVIEW_CONTRACT}"]
        if reviewer != "grok":
            raise ValueError(f"알 수 없는 리뷰어: {reviewer}")
        body = (self.root / ".claude/commands/review.md").read_text(encoding="utf-8")
        body = re.sub(r"\A---\s*\n.*?\n---[^\S\n]*(?:\n|$)", "", body,
                      count=1, flags=re.DOTALL)
        if "$ARGUMENTS" in body:
            body = body.replace("$ARGUMENTS", scope)
        else:
            body += f"\n리뷰 범위: {scope}\n"
        return ["grok", "-p", body.rstrip() + "\n" + REVIEW_CONTRACT,
                "--permission-mode", "dontAsk", "--deny", "Write", "--deny", "Edit",
                "--output-format", "json"]

    def run_reviewer(self, reviewer: str, round_no: int, end_sha: str, scope: str) -> str:
        unit = f"review-r{round_no}-{reviewer}"
        self.run_dir.mkdir(parents=True, exist_ok=True)
        report = self.run_dir / f"{unit}.txt"
        notes = []
        for _ in range(2):
            branch = self.git("symbolic-ref", "-q", "HEAD", check=False)
            if (branch.returncode or branch.stdout.decode().strip() != f"refs/heads/{self.branch}"
                    or self.head() != end_sha or self.git("status", "--porcelain").stdout):
                raise HarnessExit(EXIT_ERROR, "리뷰 실행 전 브랜치/HEAD/작업 트리 불일치")
            fingerprint = self.env_fingerprint()
            env_saved = self.capture_env()
            git_before = self.capture_git_guard()
            try:
                self._guard_pending = git_before
                child = self.run_child(self.review_argv(reviewer, scope),
                                       env=self.child_env(), timeout=self.review_timeout)
            except OSError as exc:
                child = ChildResult(None, False, "", str(exc))
            text = child.stdout
            valid_json = False
            try:
                payload = json.loads(child.stdout)
                value = payload.get("result" if reviewer == "claude" else "text")
                if isinstance(value, str):
                    text, valid_json = value, True
            except (ValueError, AttributeError):
                pass
            verdict = parse_verdict(text)
            terminal = False
            branch_error = None
            reasons = []
            if self.git_guard_failed(git_before):
                terminal = True
                reasons.append("Git 설정 변경 감지·복원")
            env_changed = self.env_fingerprint() != fingerprint
            env_reason = self.restore_env_change(
                fingerprint, env_saved, "④ 리뷰어 .env 변경 감지·복원", "리뷰어",
                keep_new=True)
            if env_reason:
                terminal = True
                reasons.append(env_reason)
            branch = self.git("symbolic-ref", "-q", "HEAD", check=False)
            if branch.returncode or branch.stdout.decode().strip() != f"refs/heads/{self.branch}":
                ref = self.snapshot(unit, 1, end_sha)
                branch_error = f"리뷰어가 브랜치를 바꿨다: {ref}"
                reasons.append(branch_error)
            elif (self.head() != end_sha or bool(self.git("status", "--porcelain").stdout)
                  or env_changed):
                ref = self.rollback(unit, 1, end_sha)
                terminal = True
                reasons.append(f"리뷰어가 작업 트리 또는 .env를 바꿔 되돌림: {ref}")
            if child.timed_out:
                reasons.append("리뷰어 timeout")
            if child.returncode != 0:
                reasons.append(f"리뷰어 비정상 종료: {child.returncode}; {child.stderr.strip()}")
            if not valid_json or not verdict:
                reasons.append("리뷰 판정 누락 또는 잘못된 JSON/REVIEW_RESULT")
            for reason in reasons:
                note = "[executor] " + reason.replace("\n", " ")
                notes.append(note)
                print(note, file=sys.stderr)
            body = text + ("\n" + "\n".join(notes) if notes else "")
            report.write_text(body, encoding="utf-8")
            self._review_text[(round_no, reviewer)] = body
            if branch_error:
                raise HarnessExit(EXIT_ERROR, branch_error)
            if terminal:
                return "unverifiable"
            if valid_json and verdict and child.returncode == 0 and not child.timed_out:
                return verdict
        return "unverifiable"

    def run_baseline(self, specs: list[StepSpec]) -> str | None:
        end_sha = self.head()
        env_before = self.env_fingerprint()
        env_saved = self.capture_env()
        git_before = self.capture_git_guard()
        for spec in sorted(specs, key=lambda item: item.step):
            failure = self.run_ac(spec.ac)
            if self.git_guard_failed(git_before) or (failure and failure.startswith("④ Git")):
                reason = self.git_env_reason("④ 기준선 Git 설정 변경 감지·복원", env_before, env_saved,
                                             "④ 기준선 .env 지문 변경: 복원됨", "기준선")
                self.rollback(f"baseline-step{spec.step}", 1, end_sha)
                return reason
            if failure and "⑦" in failure:
                self.rollback(f"baseline-step{spec.step}", 1, end_sha)
            env_reason = self.restore_env_change(
                env_before, env_saved, "④ 기준선 .env 지문 변경: 복원됨", "기준선")
            if env_reason is not None:
                return env_reason
            if failure is not None:
                return f"step{spec.step}: {failure}"
        return None

    def review_round(self, round_no: int, end_sha: str) -> dict[str, str]:
        scope = f"{self.load_index()['base_commit']}..{end_sha}"
        verdicts = {}
        for reviewer in ("claude", "grok"):
            verdicts[reviewer] = self.run_reviewer(reviewer, round_no, end_sha, scope)
            if self._git_guard_changed:
                break
        return verdicts

    def run_fix(self, round_no: int, specs: list[StepSpec], scope: str,
                *, start_k: int = 1) -> AttemptOutcome:
        ordered = sorted(specs, key=lambda spec: spec.step)
        allowed = list(dict.fromkeys(path for spec in ordered for path in spec.allowed))
        ac = [line for spec in ordered for line in spec.ac]
        reports = self.review_reports(round_no)
        task_text = ("리뷰가 지적한 결함만 고친다. 모든 AC가 계속 통과해야 한다.\n"
                     f"리뷰 범위: {scope}\n{reports}\n모든 step AC:\n" + "\n".join(ac))
        return self.attempt_unit(f"fix{round_no}", task_text, allowed, ac, start_k=start_k)

    def review_reports(self, round_no: int) -> str:
        reports = []
        for reviewer in ("claude", "grok"):
            body = self._review_text.get((round_no, reviewer), "리뷰 원문 없음")
            reports.append(f"{reviewer}:\n{body}")
        return "\n\n".join(reports)

    def finish_fix(self, round_no: int, outcome: AttemptOutcome) -> int | None:
        data = self.load_index()
        review = data["review"]
        review.pop("blocked_reason", None)
        if outcome.status == "completed":
            self.commit_feat(f"fix: {self.phase_dir} 리뷰 r{round_no} 반영 (#{self.issue})",
                             outcome.pre_sha)
            review["status"] = "pending"
            review["fixes"] = review.get("fixes", 0) + 1
        elif outcome.status == "blocked":
            review.update(status="blocked", blocked_reason=outcome.reason)
            self.set_top_status("blocked")
        else:
            review["status"] = "failed"
            self.set_top_status("error")
        if outcome.status != "completed":
            print(f"수정 {outcome.status}: {outcome.reason or '사유 없음'}", file=sys.stderr)
        self.save_index(data)
        self.commit_meta(f"fix{round_no} 반영" if outcome.status == "completed"
                         else f"fix{round_no} {outcome.status}")
        self.clear_marker()
        if outcome.status == "completed":
            return None
        if outcome.status == "blocked":
            self.issue_blocked(outcome.reason)
            return EXIT_BLOCKED
        self.issue_comment(self.review_reports(round_no) + f"\n수정 실패: {outcome.reason}")
        return EXIT_ERROR if (outcome.reason or "").startswith(("④", "⑤")) else EXIT_REVIEW

    def review_gate(self, specs: list[StepSpec]) -> int:
        data = self.load_index()
        if (any(step["status"] != "completed" for step in data["steps"])
                or data.get("review", {}).get("status") == "passed"):
            raise HarnessExit(EXIT_ERROR, "리뷰 관문 진입 조건 불일치")
        round_no, fixes_used, start_k = data["review"]["round"] + 1, data["review"].get("fixes", 0), 1
        if self.resume and re.fullmatch(r"fix[1-9]\d*", self.resume["unit"]):
            round_no = max(int(self.resume["unit"][3:]), data["review"]["round"])
            start_k = self.resume["next_k"]
            self.resume = None
            if start_k > MAX_ATTEMPTS:
                return self.finish_fix(round_no, AttemptOutcome("error", reason="재개 시 시도 소진"))
            # Reports in .run are untrusted. Re-review, preserving the fix/attempt budget.
        while True:
            end_sha = self.head()
            failure = self.run_baseline(specs)
            if failure is not None:
                self.set_top_status("error")
                self.commit_meta("review baseline error")
                self.issue_comment(f"review baseline error: {failure}")
                return EXIT_ERROR
            verdicts = self.review_round(round_no, end_sha)
            status = ("unverifiable" if "unverifiable" in verdicts.values() else
                      "passed" if all(v == "passed" for v in verdicts.values()) else "failed")
            data = self.load_index()
            data["review"] = {"status": status, "end_sha": end_sha, "round": round_no,
                              "fixes": fixes_used if status == "failed" and fixes_used < MAX_FIX_ROUNDS else 0}
            if status == "passed":
                data["completed_at"] = now_kst()
            self.save_index(data)
            if status != "failed":
                self.set_top_status("completed" if status == "passed" else "error")
            self.commit_meta("phase completed" if status == "passed" else f"review {status}")
            if status != "failed":
                if status == "passed":
                    self.issue_comment(f"{self.phase_dir} completed\n" + "\n".join(
                        f"step{s['step']}: {s.get('summary', '')}" for s in data["steps"]))
                for reviewer, verdict in verdicts.items():
                    body = self._review_text.get((round_no, reviewer), "리뷰 원문 없음")
                    self.issue_comment(f"{reviewer}: {verdict}\n{body}")
                return EXIT_OK if status == "passed" else EXIT_REVIEW
            if fixes_used >= MAX_FIX_ROUNDS:
                self.set_top_status("error")
                self.commit_meta("review failed")
                self.issue_comment(self.review_reports(round_no))
                return EXIT_REVIEW
            scope = f"{data['base_commit']}..{end_sha}"
            outcome = self.run_fix(round_no, specs, scope, start_k=start_k)
            start_k = 1
            code = self.finish_fix(round_no, outcome)
            if code is not None:
                return code
            fixes_used = self.load_index()["review"].get("fixes", 0)
            round_no += 1

    def push_branch(self) -> int:
        result = self.git("push", "-u", "origin", self.branch, check=False)
        if result.returncode:
            print(result.stderr.decode(errors="replace"), file=sys.stderr)
            return EXIT_ERROR
        return EXIT_OK

    def run(self) -> int:
        try:
            self.acquire_lock()
            if self.git_guard_path.exists():
                raise HarnessExit(EXIT_ERROR,
                    f"Git 설정이 복원되지 않았다. 확인 뒤 {self.git_guard_path}를 지워라")
            self._git_guard_changed = False
            self.install_signal_handlers()
            self.recover()
            self.retry_gh_pending()
            if self.prepare() == "blocked":
                self.issue_resume()
            specs = self.load_step_specs()
            self.run_steps(specs)
            data = self.load_index()
            if (all(s["status"] == "completed" for s in data["steps"])
                    and data.get("review", {}).get("status") == "passed"):
                return self.push_branch() if self.push else EXIT_OK
            code = self.review_gate(specs)
            return self.push_branch() if code == EXIT_OK and self.push else code
        except HarnessExit as exc:
            try:
                self.restore_pending_git_guard()
            except HarnessExit as guard_exc:
                exc = guard_exc
            print(exc.message, file=sys.stderr)
            return exc.code
        except (OSError, ValueError, KeyError, TypeError) as exc:
            try:
                self.restore_pending_git_guard()
            except HarnessExit as guard_exc:
                print(guard_exc.message, file=sys.stderr)
                return guard_exc.code
            print(str(exc), file=sys.stderr)
            return EXIT_ERROR
        except (HarnessInterrupted, KeyboardInterrupt) as exc:
            try:
                self.restore_pending_git_guard()
            except HarnessExit as guard_exc:
                print(guard_exc.message, file=sys.stderr)
                return guard_exc.code
            print(str(exc), file=sys.stderr)
            return EXIT_ERROR
        except BaseException:
            self.restore_pending_git_guard()
            raise
        finally:
            self.restore_signal_handlers()


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
