"""Repository harness primitives (Python 3.10 standard library only)."""
import argparse
import copy
from datetime import datetime, timedelta, timezone
import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Iterable

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_BLOCKED = 2
EXIT_REVIEW = 3


class HarnessExit(Exception):
    def __init__(self, code: int, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


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
