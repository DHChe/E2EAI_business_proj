import sys
sys.dont_write_bytecode = True
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import execute

import copy
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock

PHASE = "7-sample"
ISSUE = 7


def step_md(n: int, name: str, allowed: list[str], ac: list[str], body: str = "") -> str:
    return (f"# Step {n}: {name}\n\n## 작업\n\n{body}\n\n## 변경 허용 경로\n\n"
            + "\n".join(allowed) + "\n\n## Acceptance Criteria\n\n```bash\n"
            + "\n".join(ac) + "\n```\n")


class HarnessTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp(prefix="harness-test-"))
        self.addCleanup(shutil.rmtree, self.temp_dir)
        self.bin_dir = self.temp_dir / "bin"
        self.bin_dir.mkdir()
        self.log_dir = self.temp_dir / "calls"
        self.log_dir.mkdir()
        patcher = mock.patch.dict(os.environ)
        patcher.start()
        self.addCleanup(patcher.stop)
        # Remove inherited git routing/configuration so only the fixture is touched.
        for key in list(os.environ):
            if key.startswith("GIT_") or key in {"GH_TOKEN", "GITHUB_TOKEN", "SSH_AUTH_SOCK"}:
                del os.environ[key]
        for key in ("HOME", "GH_CONFIG_DIR", "CODEX_HOME"):
            folder = self.temp_dir / key.lower()
            folder.mkdir()
            os.environ[key] = str(folder)
        os.environ.update(PYTHONDONTWRITEBYTECODE="1", GIT_CONFIG_NOSYSTEM="1",
                          GIT_AUTHOR_NAME="Harness Test", GIT_AUTHOR_EMAIL="test@example.invalid",
                          GIT_COMMITTER_NAME="Harness Test", GIT_COMMITTER_EMAIL="test@example.invalid",
                          HARNESS_CALLS_DIR=str(self.log_dir),
                          PATH=str(self.bin_dir) + os.pathsep + os.environ.get("PATH", ""))
        for name in ("codex", "claude", "grok", "gh"):
            self.fake_bin(name, "import sys\nsys.exit(97)\n")

    def fake_bin(self, name: str, source: str) -> Path:
        path = self.bin_dir / name
        # Every replacement is logged too. Scenarios use os.environ, never real CLIs.
        path.write_text(f"#!{sys.executable}\n"
                        "import json, os, sys\nfrom pathlib import Path\n"
                        f"with (Path(os.environ['HARNESS_CALLS_DIR']) / {name!r}).open('a') as log:\n"
                        "    log.write(json.dumps(sys.argv[1:]) + '\\n')\n" + source,
                        encoding="utf-8")
        path.chmod(0o755)
        return path

    def calls(self, name: str) -> list[list[str]]:
        path = self.log_dir / name
        return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []

    def make_repo(self, steps: list[dict] | None = None,
                  files: dict[str, str] | None = None) -> Path:
        root = Path(tempfile.mkdtemp(dir=self.temp_dir, prefix="repo-"))
        if steps is None:
            steps = [{"name": "alpha", "allowed": ["src/"], "ac": ["test -f src/alpha.txt"]},
                     {"name": "beta", "allowed": ["src/"], "ac": ["test -f src/beta.txt"]}]
        contents = {".gitignore": ".env\n.env.*\n!.env.example\n__pycache__/\n*.pyc\nphases/**/.run/\n*.log\n",
                    "AGENTS.md": "Sample agent guardrails\n", "CONTEXT.md": "Sample glossary\n",
                    "docs/adr/0001-sample.md": "Sample architecture decision\n",
                    "docs/PRD.md": "Sample product scope\n", "src/keep.txt": "keep\n"}
        for n, step in enumerate(steps):
            contents[f"phases/{PHASE}/step{n}.md"] = step_md(
                n, step["name"], step.get("allowed", ["src/"]), step.get("ac", ["true"]))
        contents["phases/index.json"] = json.dumps(
            {"phases": [{"dir": PHASE, "issue": ISSUE, "status": "pending"}]})
        contents[f"phases/{PHASE}/index.json"] = json.dumps(
            {"project": "sample", "phase": PHASE, "issue": ISSUE,
             "steps": [{"step": n, "name": s["name"], "status": "pending"}
                       for n, s in enumerate(steps)]})
        contents.update(files or {})
        for name, content in contents.items():
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        self.git(root, "init", "-q", "-b", "main")
        self.git(root, "add", "--", *contents)
        self.git(root, "commit", "-q", "-m", "fixture")
        return root

    def git(self, root, *args):
        return subprocess.run(["git", *args], cwd=root, capture_output=True, check=True).stdout

    def make_executor(self, root: Path, **kw) -> execute.Executor:
        executor = execute.Executor(root, PHASE, **kw)
        def cleanup():
            if executor._lock_file is not None:
                executor._lock_file.close()
            if executor._gh_config is not None:
                executor._gh_config.cleanup()
        self.addCleanup(cleanup)
        return executor

    def seed_state(self, executor, status="error", review=False):
        data = executor.load_index()
        if review:
            data["review"] = {"status": status, "blocked_reason": "ask", "round": 0, "end_sha": None}
        else:
            data["steps"][0].update(status=status, error_message="failure", failed_at="then")
        executor.save_index(data)
        top = executor.load_top_index()
        top["phases"][0].update(status=status)
        executor.save_top_index(top)
        self.git(executor.root, "add", "--", "phases")
        self.git(executor.root, "commit", "-q", "-m", "seed state")
        return data

    def assert_exit(self, code, fn, *args):
        with self.assertRaises(execute.HarnessExit) as caught:
            fn(*args)
        self.assertEqual(caught.exception.code, code)


class PhaseStateTests(HarnessTestCase):
    def test_zero_tests_exit_1(self):
        result = subprocess.run([sys.executable, str(Path(__file__).resolve()),
                                 "-k", "__no_such_test__"], capture_output=True)
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn(b"Ran 0 tests", result.stderr)

    def test_index_write_atomic(self):
        path = self.temp_dir / "index.json"
        original = b'{"original": true}\n'
        path.write_bytes(original)
        names = set(self.temp_dir.iterdir())
        with mock.patch.object(execute.os, "replace", side_effect=OSError("replace failed")):
            with self.assertRaisesRegex(OSError, "replace failed"):
                execute.write_json_atomic(path, {"new": "한글"})
        self.assertEqual(path.read_bytes(), original)
        self.assertEqual(set(self.temp_dir.iterdir()), names)
        execute.write_json_atomic(path, {"new": "한글"})
        self.assertEqual(path.read_text(), '{\n  "new": "한글"\n}\n')

    def test_lock_rejects_second_run(self):
        executor = self.make_executor(self.make_repo())
        source = ("import fcntl, pathlib, sys\n"
                  "p = pathlib.Path(sys.argv[1]); p.parent.mkdir(parents=True, exist_ok=True)\n"
                  "f = p.open('a+b'); fcntl.flock(f, fcntl.LOCK_EX)\n"
                  "print('locked', flush=True); sys.stdin.readline()\n")
        with subprocess.Popen([sys.executable, "-c", source, str(executor.lock_path)],
                              stdin=subprocess.PIPE, stdout=subprocess.PIPE) as proc:
            try:
                self.assertEqual(proc.stdout.readline(), b"locked\n")
                self.assert_exit(1, executor.acquire_lock)
                other = execute.Executor(executor.root, "8-other")
                self.assert_exit(1, other.acquire_lock)
            finally:
                proc.communicate(b"release\n", timeout=5)
        executor.acquire_lock()
        self.assertTrue(executor.lock_path.exists())

    def test_checkout_before_meta_commit(self):
        executor = self.make_executor(self.make_repo())
        data = self.seed_state(executor)
        initial = executor.head()
        data["steps"][0]["status"] = "pending"
        executor.save_index(data)
        self.assertEqual(executor.prepare(), "error")
        self.assertEqual(self.git(executor.root, "rev-parse", "main").decode().strip(), initial)
        self.assertNotEqual(executor.head(), initial)
        self.assertEqual(self.git(executor.root, "branch", "--show-current").decode().strip(), executor.branch)
        self.assertIn(b"chore: 7-sample prepare (#7)", self.git(executor.root, "log", "-1", "--format=%s"))

    def test_meta_diff_allows_pending_reset_only(self):
        for review in (False, True):
            with self.subTest(review=review):
                executor = self.make_executor(self.make_repo())
                data = self.seed_state(executor, "blocked" if review else "error", review)
                target = data["review"] if review else data["steps"][0]
                target["status"] = "pending"
                for key in ("error_message", "failed_at", "blocked_reason"):
                    target.pop(key, None)
                executor.save_index(data)
                (executor.phase_path / "new.md").write_text("new instructions")
                (executor.phase_path / "step0.md").write_text("edited instructions")
                initial = executor.head()
                self.assertEqual(executor.prepare(), "blocked" if review else "error")
                self.assertEqual(executor.changed_paths(), [])
                self.assertEqual(self.git(executor.root, "rev-list", "--count", f"{initial}..HEAD").strip(), b"1")
                self.assertEqual(executor.load_index()["review" if review else "steps"],
                                 data["review" if review else "steps"])

    def test_meta_diff_rejects_other_edits(self):
        for case in ("status", "name", "summary", "completed", "top", "malformed", "both", "removed_step"):
            with self.subTest(case=case):
                executor = self.make_executor(self.make_repo())
                data = self.seed_state(executor, "completed" if case == "completed" else "error")
                initial = executor.head()
                data["steps"][0]["status"] = "pending"
                if case in {"status", "name", "summary"}:
                    data["steps"][1][case] = "completed" if case == "status" else "changed"
                elif case == "top":
                    executor.set_top_status("pending")
                elif case == "both":
                    data["review"] = {"status": "pending"}
                elif case == "removed_step":
                    data["steps"] = []
                executor.save_index(data)
                if case == "malformed":
                    executor.index_path.write_text("{")
                self.assert_exit(1, executor.prepare)
                self.assertEqual(executor.head(), initial)

    def test_dirty_outside_phase_dir_exits_1(self):
        for name in ("src/keep.txt", "new.txt"):
            with self.subTest(name=name):
                executor = self.make_executor(self.make_repo())
                initial = executor.head()
                (executor.root / name).write_text("dirty")
                self.assert_exit(1, executor.prepare)
                self.assertEqual(executor.head(), initial)
                self.assertNotIn("created_at", executor.load_index())

    def test_base_commit_committed_before_attempt(self):
        executor = self.make_executor(self.make_repo())
        initial = executor.head()
        self.assertIsNone(executor.prepare())
        data = json.loads(self.git(executor.root, "show", f"HEAD:phases/{PHASE}/index.json"))
        self.assertEqual(data["base_commit"], initial)
        self.assertRegex(data["created_at"], r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\+09:00$")
        self.assertEqual(data["review"], {"status": "pending", "end_sha": None, "round": 0})
        self.assertEqual(executor.changed_paths(), [])
        head = executor.head()
        executor.prepare()
        self.assertEqual(executor.head(), head)
        self.assertEqual(executor.load_index(), data)

    def test_last_error_exits_1_blocked_exits_2(self):
        for status, review, code in (("error", False, 1), ("blocked", False, 2), ("blocked", True, 2)):
            with self.subTest(status=status, review=review):
                executor = self.make_executor(self.make_repo())
                self.seed_state(executor, status, review)
                initial = executor.head()
                before = executor.top_index_path.read_bytes()
                self.assert_exit(code, executor.prepare)
                self.assertEqual(executor.head(), initial)
                self.assertEqual(executor.top_index_path.read_bytes(), before)
                self.assertNotIn("created_at", executor.load_index())

    def test_commit_paths_rejects_unexpected_cached(self):
        for branch in ("main", f"feat-{PHASE}", "detached"):
            with self.subTest(branch=branch):
                executor = self.make_executor(self.make_repo())
                if branch == "detached":
                    self.git(executor.root, "checkout", "--detach")
                elif branch != "main":
                    self.git(executor.root, "checkout", "-b", branch)
                (executor.root / "src/keep.txt").write_text("bait")
                self.git(executor.root, "add", "--", "src/keep.txt")
                (executor.root / "src/wanted.txt").write_text("wanted")
                initial = executor.head()
                cached = self.git(executor.root, "diff", "--cached")
                self.assert_exit(1, executor.commit_paths, ["src/wanted.txt"], "test")
                self.assertEqual(executor.head(), initial)
                self.assertEqual(self.git(executor.root, "diff", "--cached"),
                                 b"" if branch == executor.branch else cached)
                self.assertEqual((executor.root / "src/keep.txt").read_text(), "bait")

    def test_child_env_sanitized(self):
        executor = self.make_executor(self.make_repo())
        os.environ.update(GH_TOKEN="secret", GITHUB_TOKEN="secret", SSH_AUTH_SOCK="socket",
                          ORCA_SAMPLE="keep")
        original = os.environ.copy()
        env = executor.child_env()
        for key in ("GH_TOKEN", "GITHUB_TOKEN", "SSH_AUTH_SOCK"):
            self.assertNotIn(key, env)
        folder = Path(env["GH_CONFIG_DIR"])
        self.assertNotEqual(str(folder), original["GH_CONFIG_DIR"])
        self.assertTrue(folder.is_dir())
        self.assertEqual(list(folder.iterdir()), [])
        self.assertFalse(folder.is_relative_to(executor.root))
        self.assertEqual(env["PYTHONDONTWRITEBYTECODE"], "1")
        self.assertEqual(env["ORCA_SAMPLE"], "keep")
        stripped = executor.child_env(strip_orca=True)
        self.assertNotIn("ORCA_SAMPLE", stripped)
        self.assertEqual(stripped["GH_CONFIG_DIR"], str(folder))
        self.assertEqual(dict(os.environ), original)

    def test_changed_paths_and_literal_commit(self):
        executor = self.make_executor(self.make_repo(files={"src/old.txt": "old"}))
        self.git(executor.root, "checkout", "-b", executor.branch)
        self.git(executor.root, "mv", "src/old.txt", "src/new name.txt")
        (executor.root / "src/keep.txt").unlink()
        literal = "src/[a]*\n한글.txt"
        (executor.root / literal).write_text("literal")
        (executor.root / "ignored.log").write_text("ignored")
        paths = ["src/old.txt", "src/new name.txt", "src/keep.txt", literal]
        self.assertEqual(set(executor.changed_paths()), set(paths))
        executor.commit_paths(paths, "literal paths")
        self.assertEqual(executor.changed_paths(), [])
        with self.assertRaises(ValueError):
            executor.commit_paths([], "empty")

    def test_commit_already_staged_deletion(self):
        executor = self.make_executor(self.make_repo())
        self.git(executor.root, "checkout", "-b", executor.branch)
        self.git(executor.root, "rm", "--", "src/keep.txt")
        executor.commit_paths(["src/keep.txt"], "delete")
        self.assertEqual(executor.changed_paths(), [])
        self.assertEqual(self.git(executor.root, "diff", "HEAD^", "HEAD",
                                  "--name-status").strip(), b"D\tsrc/keep.txt")

    def test_commit_recreated_staged_deletion(self):
        executor = self.make_executor(self.make_repo())
        self.git(executor.root, "checkout", "-b", executor.branch)
        self.git(executor.root, "rm", "--", "src/keep.txt")
        (executor.root / "src").mkdir(exist_ok=True)
        (executor.root / "src/keep.txt").write_text("recreated")
        executor.commit_paths(["src/keep.txt"], "recreate")
        self.assertEqual(self.git(executor.root, "show", "HEAD:src/keep.txt"), b"recreated")
        self.assertEqual(executor.changed_paths(), [])

    def test_top_status_timestamps_and_missing_phase(self):
        executor = self.make_executor(self.make_repo())
        for status, stamp in (("error", "failed_at"), ("blocked", "blocked_at"),
                              ("completed", "completed_at"), ("pending", None)):
            executor.set_top_status(status)
            phase = executor.load_top_index()["phases"][0]
            self.assertEqual(phase["status"], status)
            self.assertEqual({k for k in phase if k.endswith("_at")}, {stamp} if stamp else set())
        executor.save_top_index({"phases": []})
        self.assert_exit(1, executor.set_top_status, "pending")

    def test_fake_cli_traps(self):
        for name in ("codex", "claude", "grok", "gh"):
            result = subprocess.run([name, "trap-test"], capture_output=True)
            self.assertEqual(result.returncode, 97)
            self.assertEqual(self.calls(name), [["trap-test"]])


if __name__ == "__main__":
    program = unittest.main(exit=False)
    sys.exit(0 if program.result.testsRun and program.result.wasSuccessful() else 1)
