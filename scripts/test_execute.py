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
import time
import signal
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
        self.assertEqual(data["review"], {"status": "pending", "end_sha": None, "round": 0, "fixes": 0})
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
        self.assertNotIn("ORCA_SAMPLE", env)
        self.assertEqual(env["GIT_CONFIG_KEY_0"], "credential.helper")
        self.assertEqual(env["GIT_CONFIG_VALUE_0"], "")
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


class StepSpecTests(HarnessTestCase):
    def test_paths_reject_glob_abs_dotdot_magic(self):
        for path in ("src/*.py", "src/?.py", "src/[ab].py", "/etc/passwd",
                     "../x", "src/../x", ":(glob)src", "./src/a.py",
                     "a//b", ".", "src//", "src/./a"):
            with self.subTest(path=path), self.assertRaises(execute.SpecError) as caught:
                execute.parse_allowed_paths(step_md(0, "alpha", [path], ["true"]))
            self.assertIn(path, str(caught.exception))
        self.assertEqual(execute.parse_allowed_paths(
            step_md(0, "alpha", [" src/a.py ", "", "src/"], ["true"])),
            ["src/a.py", "src/"])

    def test_paths_reject_phases_overlap(self):
        for path in ("phases", "phases/", "phases/7-sample/step0.md", "phases/index.json"):
            with self.subTest(path=path), self.assertRaises(execute.SpecError):
                execute.parse_allowed_paths(step_md(0, "alpha", [path], ["true"]))

    def test_path_allowed_file_and_directory_boundaries(self):
        allowed = ("src/a.py", "tests/")
        for path in ("src/a.py", "tests/a.py", "tests/nested/b.py"):
            self.assertTrue(execute.path_allowed(path, allowed))
        for path in ("src/a.pyc", "src/a.py/child", "src/b.py", "tests", "tests-other/a"):
            self.assertFalse(execute.path_allowed(path, allowed))

    def test_paths_require_one_nonempty_section(self):
        for text in ("", "## 변경 허용 경로\n\n## 다음\na.py",
                     "## 변경 허용 경로\na.py\n## 변경 허용 경로\nb.py"):
            with self.subTest(text=text), self.assertRaises(execute.SpecError):
                execute.parse_allowed_paths(text)
        self.assertEqual(execute.parse_allowed_paths(
            "## 변경 허용 경로\na.py\n## 다음\nphases/"), ["a.py"])

    def test_ac_exactly_one_bash_block(self):
        heading = "## Acceptance Criteria\n"
        for text in (heading, heading + "```bash\ntrue\n```\n```bash\ntrue\n```",
                     heading + "```sh\ntrue\n```", "```bash\ntrue\n```",
                     heading + "```bash\ntrue", heading + "```bash\n# comment\n```",
                     heading + "```bash\ntrue\n```\n" + heading,
                     heading + "```bash extra\ntrue\n```"):
            with self.subTest(text=text), self.assertRaises(execute.SpecError):
                execute.parse_ac(text)
        self.assertEqual(execute.parse_ac(
            heading + "```bash\n\n  # comment\n  true  \n! false\n```\n"
            "## 다음\n```sh\nignored\n```"), ["true", "! false"])

    def test_ac_rejects_multiline_constructs(self):
        for command in ("echo hi \\", "cat <<EOF", "if true; then", "for x in a; do",
                        "f() {", "cat <<< hi"):
            with self.subTest(command=command), self.assertRaises(execute.SpecError) as caught:
                execute.parse_ac(step_md(0, "alpha", ["src/"], [command]))
            self.assertIn(repr(command), str(caught.exception))
        commands = ["! false", "false && true", "false | true"]
        self.assertEqual(execute.parse_ac(step_md(0, "alpha", ["src/"], commands)), commands)

    def test_specs_read_from_head(self):
        root = self.make_repo()
        executor = self.make_executor(root)
        path = root / f"phases/{PHASE}/step0.md"
        committed = path.read_text()
        path.write_text(step_md(0, "alpha", ["other/"], ["touch ran.txt"]))
        specs = executor.load_step_specs()
        self.assertIs(specs, executor.specs)
        self.assertEqual([spec.step for spec in specs], [0, 1])
        self.assertEqual(specs[0], execute.StepSpec(
            0, "alpha", committed, ("src/",), ("test -f src/alpha.txt",)))
        with mock.patch.object(executor, "git", side_effect=AssertionError("reread")):
            self.assertIs(executor.load_step_specs(), specs)
        self.assertFalse((root / "ran.txt").exists())

    def test_invalid_spec_runs_nothing(self):
        root = self.make_repo(steps=[
            {"name": "alpha", "ac": ["touch ran.txt"]},
            {"name": "beta", "allowed": ["src/*.py"]}])
        executor = self.make_executor(root)
        self.assertEqual(executor.run(), 1)
        self.assertFalse(hasattr(executor, "specs"))
        for name in ("codex", "claude", "grok", "gh"):
            self.assertEqual(self.calls(name), [])
        self.assertFalse((root / "ran.txt").exists())

    def test_specs_collect_errors_and_missing_head_files(self):
        root = self.make_repo(steps=[
            {"name": "alpha", "allowed": ["../x"], "ac": ["if true; then"]},
            {"name": "beta", "ac": ["cat <<EOF"]}])
        executor = self.make_executor(root)
        data = executor.load_index()
        data["steps"].append({"step": 2, "name": "missing", "status": "pending"})
        executor.save_index(data)
        with self.assertRaises(execute.HarnessExit) as caught:
            executor.load_step_specs()
        self.assertEqual(caught.exception.code, 1)
        for fragment in ("step0.md", "../x", "if true; then", "step1.md", "cat <<EOF",
                         "step2.md"):
            self.assertIn(fragment, str(caught.exception))
        self.assertFalse(hasattr(executor, "specs"))

    def test_run_reads_specs_after_prepare_commit(self):
        root = self.make_repo()
        executor = self.make_executor(root)
        (root / f"phases/{PHASE}/step0.md").write_text(
            step_md(0, "alpha", ["src/"], ["touch ran.txt"]))
        with mock.patch.object(executor, 'run_steps') as run_steps, \
                mock.patch.object(executor, 'review_gate', return_value=0):
            self.assertEqual(executor.run(), 0)
            run_steps.assert_called_once_with(executor.specs)
        self.assertEqual(executor.specs[0].ac, ("touch ran.txt",))
        self.assertFalse((root / "ran.txt").exists())

    def test_ac_syntax_check_has_no_side_effects(self):
        marker = self.temp_dir / "ran.txt"
        startup = self.temp_dir / "startup.sh"
        startup.write_text(f"touch '{marker}'\n")
        commands = [f"touch '{marker}'", f"echo $(touch '{marker}')"]
        with mock.patch.dict(os.environ, {"BASH_ENV": str(startup)}):
            self.assertEqual(execute.parse_ac(step_md(0, "alpha", ["src/"], commands)),
                             commands)
        self.assertFalse(marker.exists())


class SessionRunnerTests(HarnessTestCase):
    def fake_codex(self, listing="print('[]')", body="print('session output')"):
        self.fake_bin("codex", r"""
record = {'argv': sys.argv[1:], 'env': dict(os.environ), 'cwd': os.getcwd()}
if sys.argv[1] == 'exec':
    record['stdin'] = sys.stdin.read()
with (Path(os.environ['HARNESS_CALLS_DIR']) / 'records').open('a') as log:
    log.write(json.dumps(record) + '\n')
if sys.argv[-3:] == ['mcp', 'list', '--json']:
""" +
                      "\n".join("    " + line for line in listing.splitlines()) +
                      "\n    sys.exit(0)\n" + body)

    def records(self):
        return [json.loads(line) for line in (self.log_dir / 'records').read_text().splitlines()]

    def test_codex_argv_verified_flags_no_forbidden(self):
        executor = self.make_executor(self.make_repo())
        self.fake_codex(body="print('session output'); print('diagnostic', file=sys.stderr)")
        spawned = []
        result = executor.run_codex('step2', 'prompt 한글', on_spawn=spawned.append)
        flags = [
            '-c', 'plugins."browser@openai-bundled".enabled=false',
            '-c', 'plugins."unified-computer-use@openai-bundled".enabled=false',
            '-c', 'plugins."computer-use@openai-bundled".enabled=false',
            '--disable', 'apps', '--disable', 'computer_use', '--disable', 'browser_use',
            '--disable', 'in_app_browser', '-c', 'sandbox_workspace_write.network_access=false']
        self.assertEqual(execute.CODEX_CONFIG_FLAGS, flags)
        record = self.records()[-1]
        self.assertEqual(record['argv'], ['exec', *flags, '-s', 'workspace-write',
            '--dangerously-bypass-hook-trust', '--ephemeral', '-C', str(executor.root),
            '--json', '-o', str(executor.run_dir / 'step2-last.txt'), '-'])
        for flag in ('--ignore-user-config', '--dangerously-bypass-approvals-and-sandbox',
                     'danger-full-access', '--full-auto'):
            self.assertNotIn(flag, record['argv'])
        self.assertEqual(record['stdin'], 'prompt 한글')
        self.assertEqual(Path(record['cwd']).resolve(), executor.root.resolve())
        self.assertEqual(len(spawned), 1)
        self.assertIsNone(executor.child_pgid)
        self.assertEqual(result.returncode, 0)
        self.assertFalse(result.timed_out)
        self.assertEqual(result.stderr, 'diagnostic\n')
        self.assertEqual(result.stdout, (executor.run_dir / 'step2-session.jsonl').read_text())

    def test_mcp_overrides_by_transport(self):
        servers = [{'name': 'local_1-x', 'enabled': False, 'transport': {'type': 'stdio'}},
                   {'name': 'remote', 'enabled': True, 'transport': {'type': 'streamable_http'}}]
        self.assertEqual(execute.codex_mcp_overrides(servers), [
            '-c', 'mcp_servers.local_1-x.command="true"',
            '-c', 'mcp_servers.local_1-x.enabled=false', '-c', 'mcp_servers.remote.enabled=false'])
        for name in ('a.b', '"x"', '', 'a\n', 'x y'):
            self.assert_exit(1, execute.codex_mcp_overrides, [{'name': name}])

    def test_preflight_fails_closed(self):
        executor = self.make_executor(self.make_repo())
        server = {'name': 'local', 'enabled': True, 'transport': {'type': 'stdio'}}
        cases = ["print(" + repr(json.dumps([server])) + ")", 'sys.exit(3)',
                 "print('not json')", "print('{}')", "print('[null]')"]
        for output in cases:
            with self.subTest(output=output):
                self.fake_codex(listing="if sys.argv[1] == 'mcp':\n    print(" +
                    repr(json.dumps([server])) + ")\nelse:\n    " + output)
                self.assert_exit(1, executor.run_codex, 'step2', 'prompt')
                self.assertEqual(self.calls('codex')[-1], [*execute.CODEX_CONFIG_FLAGS,
                    '-c', 'mcp_servers.local.command="true"', '-c',
                    'mcp_servers.local.enabled=false', 'mcp', 'list', '--json'])
        self.fake_codex(listing='sys.exit(4)')
        self.assert_exit(1, executor.run_codex, 'step2', 'prompt')
        self.assertFalse(any(args[0] == 'exec' for args in self.calls('codex')))
        self.fake_codex(listing="print('[]')")
        self.assertEqual(executor.run_codex('step2', 'ok').returncode, 0)

    def test_prompt_contents(self):
        executor = self.make_executor(self.make_repo(files={
            'docs/adr/0002-second.md': 'Second decision'}))
        data = executor.load_index()
        data['steps'][0].update(status='completed', summary='accumulated summary')
        data['steps'][1]['summary'] = 'pending summary'
        executor.save_index(data)
        prompt = executor.build_prompt('step2', 'task unique', ['scripts/execute.py'])
        for value in ('Sample agent guardrails', 'Sample glossary', 'Sample architecture decision',
                      'Sample product scope', 'step0 alpha: accumulated summary', 'task unique',
                      'scripts/execute.py', f'phases/{PHASE}/.run/step2-result.json',
                      'completed', 'error', 'blocked', 'push, gh 쓰기', '커밋하지 마라',
                      'phases/index.json', f'phases/{PHASE}/index.json'):
            self.assertIn(value, prompt)
        self.assertLess(prompt.index('Sample architecture decision'), prompt.index('Second decision'))
        self.assertNotIn('pending summary', prompt)
        self.assertNotIn('직전 시도 실패 사유', prompt)
        self.assertIn('## 직전 시도 실패 사유\nfailed unique',
                      executor.build_prompt('fix1', 'task', [], 'failed unique'))
        (executor.root / 'docs/PRD.md').unlink()
        self.assertNotIn('Sample product scope', executor.build_prompt('fix1', 'task', []))

    def assert_gone(self, pid):
        deadline = time.monotonic() + 4
        while time.monotonic() < deadline:
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                return
            time.sleep(0.03)
        self.fail(f'process {pid} survived')

    def test_session_timeout_kills_group(self):
        executor = self.make_executor(self.make_repo())
        executor.session_timeout = 1
        self.fake_codex(body="""
import subprocess, signal, time
child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])
Path(os.environ['HARNESS_CALLS_DIR'], 'grandchild').write_text(str(child.pid))
def terminate(sig, frame):
    child.wait(timeout=2)
    sys.exit(0)
signal.signal(signal.SIGTERM, terminate)
time.sleep(60)
""")
        spawned = []
        start = time.monotonic()
        result = executor.run_codex('step2', 'prompt', on_spawn=spawned.append)
        self.assertTrue(result.timed_out)
        self.assertLess(time.monotonic() - start, 5)
        self.assert_gone(spawned[0])
        self.assert_gone(int((self.log_dir / 'grandchild').read_text()))
        self.assertIsNone(executor.child_pgid)

    def test_session_env_strips_orca_and_tokens(self):
        executor = self.make_executor(self.make_repo())
        os.environ.update(ORCA_TEST='secret', GH_TOKEN='secret', GITHUB_TOKEN='secret',
                          SSH_AUTH_SOCK='secret')
        self.fake_codex()
        executor.run_codex('step2', 'prompt')
        records = self.records()
        self.assertEqual(len(records), 3)
        for record in records:
            env = record['env']
            for key in ('ORCA_TEST', 'GH_TOKEN', 'GITHUB_TOKEN', 'SSH_AUTH_SOCK'):
                self.assertNotIn(key, env)
            self.assertEqual(env['PYTHONDONTWRITEBYTECODE'], '1')
            self.assertEqual(list(Path(env['GH_CONFIG_DIR']).iterdir()), [])
            self.assertEqual(env, records[0]['env'])

    def test_child_cleanup_callback_exception_and_kill_escalation(self):
        executor = self.make_executor(self.make_repo())
        spawned = []
        def fail(pid):
            spawned.append(pid)
            self.assertEqual(executor.child_pgid, pid)
            raise RuntimeError('callback')
        with self.assertRaisesRegex(RuntimeError, 'callback'):
            executor.run_child([sys.executable, '-c', 'import time; time.sleep(60)'],
                env=executor.child_env(), timeout=1, on_spawn=fail)
        self.assert_gone(spawned[0])
        self.assertIsNone(executor.child_pgid)
        result = executor.run_child([sys.executable, '-c',
            'import signal,time; signal.signal(signal.SIGTERM, signal.SIG_IGN); time.sleep(60)'],
            env=executor.child_env(), timeout=0.5)
        self.assertTrue(result.timed_out)
        self.assertEqual(result.returncode, -signal.SIGKILL)

    def test_child_group_signal_safety(self):
        executor = self.make_executor(self.make_repo())
        for pid in (None, 0, 1, os.getpgrp()):
            with self.subTest(pid=pid), mock.patch.object(execute.subprocess, 'Popen') as popen, \
                    mock.patch.object(execute.os, 'killpg') as killpg:
                popen.return_value.pid = pid
                popen.return_value.returncode = 0
                executor.run_child(['fake'], env={}, timeout=1)
                killpg.assert_not_called()
                self.assertIsNone(executor.child_pgid)
        for error in (ProcessLookupError, PermissionError):
            with mock.patch.object(execute.subprocess, 'Popen') as popen, \
                    mock.patch.object(execute.os, 'killpg', side_effect=error):
                popen.return_value.pid = os.getpgrp() + 10000
                executor.run_child(['fake'], env={}, timeout=1)
                self.assertIsNone(executor.child_pgid)


class RollbackTests(HarnessTestCase):
    def setUp(self):
        super().setUp()
        # Recovery tests must never depend on sandbox access to the real ps.
        self.fake_bin('ps', 'sys.exit(97)\n')

    def fixture(self):
        root = self.make_repo()
        self.git(root, 'checkout', '-b', f'feat-{PHASE}')
        return self.make_executor(root)

    def marker_for(self, executor, pgid=None):
        return dict(unit='step3', k=2, pre_sha=executor.head(), stage='running',
                    feat_sha=None, pgid=pgid)

    def record_git(self, fail=''):
        real = shutil.which('git')
        self.fake_bin('git', f"""
with (Path(os.environ['HARNESS_CALLS_DIR']) / 'indexes').open('a') as stream:
    stream.write(json.dumps([sys.argv[1:], os.environ.get('GIT_INDEX_FILE')]) + '\\n')
if sys.argv[1] == {fail!r}:
    sys.exit(41)
os.execv({real!r}, [{real!r}, *sys.argv[1:]])
""")

    def test_snapshot_has_new_binary_and_unstaged(self):
        ex = self.fixture()
        base = ex.head()
        binary = bytes(range(256)) + b'\x00\xff'
        (ex.root / 'new.bin').write_bytes(binary)
        (ex.root / 'src/keep.txt').write_bytes(b'edited\x00\xff')
        (ex.root / '.env').write_text('ignored')
        ref = ex.snapshot('step3', 1, base)
        self.assertEqual(self.git(ex.root, 'rev-parse', ref + '^').decode().strip(), base)
        self.assertEqual(self.git(ex.root, 'show', ref + ':new.bin'), binary)
        self.assertEqual(self.git(ex.root, 'show', ref + ':src/keep.txt'), b'edited\x00\xff')
        self.assertNotIn(b'.env', self.git(ex.root, 'ls-tree', '--name-only', ref))
        self.assertEqual(self.git(ex.root, 'diff', '--cached'), b'')

    def test_temp_index_outside_worktree(self):
        ex = self.fixture()
        index = ex.root / '.git/index'
        before = index.read_bytes()
        base = ex.head()
        self.record_git()
        ex.snapshot('step3', 1, base)
        records = [json.loads(x) for x in (self.log_dir / 'indexes').read_text().splitlines()]
        temporary = [Path(path) for argv, path in records if argv == ['add', '-A']]
        self.assertEqual(len(temporary), 1)
        self.assertFalse(temporary[0].resolve().is_relative_to(ex.root.resolve()))
        self.assertFalse(temporary[0].parent.exists())
        self.assertEqual(index.read_bytes(), before)
        inside = ex.root / 'bad-temp'
        inside.mkdir()
        with mock.patch.object(execute.tempfile, 'mkdtemp', return_value=str(inside)):
            self.assert_exit(1, ex.worktree_tree, base)
        self.assertFalse(inside.exists())

    def test_snapshot_failure_no_destructive_cmd(self):
        ex = self.fixture()
        base = ex.head()
        dirty = ex.root / 'src/keep.txt'
        dirty.write_text('edited')
        self.record_git('update-ref')
        self.assert_exit(1, ex.rollback, 'step3', 1, base)
        self.assertFalse(any(a[0] in ('reset', 'clean') for a in self.calls('git')))
        self.assertEqual(dirty.read_text(), 'edited')
        (self.bin_dir / 'git').unlink()
        self.git(ex.root, 'checkout', 'main')
        self.record_git()
        self.assert_exit(1, ex.rollback, 'step3', 2, base)
        self.assertEqual(self.git(ex.root, 'rev-parse', 'main').decode().strip(), base)
        self.assertEqual(dirty.read_text(), 'edited')
        self.assertTrue(self.git(ex.root, 'for-each-ref', 'refs/harness/'))
        self.assertFalse(any(a[0] in ('reset', 'clean') for a in self.calls('git')))
        self.git(ex.root, 'checkout', '--detach', base)
        self.assert_exit(1, ex.rollback, 'step3', 3, base)
        self.assertFalse(any(a[0] in ('reset', 'clean') for a in self.calls('git')))

    def test_rollback_dirty_postcondition_exits_1(self):
        ex = self.fixture()
        nested = ex.root / 'nested'
        nested.mkdir()
        self.git(nested, 'init', '-q')
        (nested / 'keep').write_text('nested')
        self.git(nested, 'add', '--', 'keep')
        self.git(nested, 'commit', '-qm', 'nested fixture')
        self.record_git()
        self.assert_exit(1, ex.rollback, 'step3', 1, ex.head())
        self.assertTrue(self.git(ex.root, 'for-each-ref', 'refs/harness/'))
        self.assertIn(['clean', '-fd'], self.calls('git'))
        self.assertTrue(any(a[:2] == ['reset', '--hard'] for a in self.calls('git')))
        self.assertTrue(self.git(ex.root, 'status', '--porcelain'))
        self.assertTrue((nested / '.git').exists())

    def wait_file(self, path):
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            if path.exists() and path.read_text():
                return
            time.sleep(.02)
        self.fail(f'no readiness file: {path}')

    def stop_process(self, proc):
        if proc.poll() is None:
            os.killpg(proc.pid, signal.SIGKILL)
        proc.wait(timeout=5)

    def test_recover_running_rolls_back(self):
        for name in ('codex', 'sleeper', None):
            with self.subTest(name=name):
                ex = self.fixture()
                proc = None
                if name:
                    ready = self.temp_dir / (name + '-ready')
                    fake = self.fake_bin(name, f"import time\nPath({str(ready)!r}).write_text('ready')\ntime.sleep(60)\n")
                    proc = subprocess.Popen([str(fake)], start_new_session=True)
                    self.addCleanup(self.stop_process, proc)
                    self.wait_file(ready)
                marker = self.marker_for(ex, proc.pid if proc else 2147483647)
                listing = f'{proc.pid} {proc.pid} {fake}' if proc else ''
                self.fake_bin('ps', f'print({listing!r})\n')
                ex.save_marker(marker)
                (ex.root / 'src/keep.txt').write_text('dirty')
                (ex.root / 'untracked').write_text('new')
                (ex.root / '.env').write_text('preserved')
                rollback = ex.rollback
                def observed(*args):
                    self.assertTrue(ex.marker_path.exists())
                    return rollback(*args)
                with mock.patch.object(ex, 'rollback', side_effect=observed):
                    ex.recover()
                self.assertEqual(self.calls('ps')[-1],
                                 ['-A', '-o', 'pid=,pgid=,command='])
                if name == 'codex':
                    self.assertEqual(proc.wait(timeout=5), -signal.SIGKILL)
                elif proc:
                    self.assertIsNone(proc.poll())
                self.assertFalse(ex.marker_path.exists())
                self.assertIsNone(ex.marker)
                self.assertEqual(ex.resume, {'unit': 'step3', 'next_k': 3})
                self.assertEqual(self.git(ex.root, 'status', '--porcelain'), b'')
                self.assertEqual((ex.root / '.env').read_text(), 'preserved')
                self.assertTrue(self.git(ex.root, 'for-each-ref', 'refs/harness/'))

    def test_recover_ps_failure_keeps_marker_without_rollback(self):
        for mode in ('exit', 'exception'):
            ex = self.fixture()
            ex.save_marker(self.marker_for(ex, os.getpgrp() + 10000))
            before = ex.marker_path.read_bytes()
            (ex.root / 'src/keep.txt').write_text('dirty')
            real_run = execute.subprocess.run
            def run(argv, **kwargs):
                if argv[0] == 'ps':
                    if mode == 'exception':
                        raise OSError('ps unavailable')
                    return subprocess.CompletedProcess(argv, 1, '', 'failed')
                return real_run(argv, **kwargs)
            with mock.patch.object(execute.subprocess, 'run', side_effect=run), \
                    mock.patch.object(ex, 'rollback') as rollback:
                self.assert_exit(1, ex.recover)
                rollback.assert_not_called()
            self.assertEqual(ex.marker_path.read_bytes(), before)
            self.assertEqual((ex.root / 'src/keep.txt').read_text(), 'dirty')

    def test_recover_moved_head_touches_nothing(self):
        ex = self.fixture()
        marker = self.marker_for(ex)
        self.git(ex.root, 'commit', '--allow-empty', '-qm', 'moved')
        ex.save_marker(marker)
        dirty = ex.root / 'src/keep.txt'
        dirty.write_text('dirty')
        cases = [json.dumps(marker), '{bad', '[]', json.dumps({}),
                 json.dumps(dict(marker, pre_sha=ex.head(), stage='feat_done', feat_sha=ex.head())),
                 json.dumps(dict(marker, pre_sha=ex.head(), stage='unknown'))]
        for content in cases:
            ex.marker_path.write_text(content)
            with mock.patch.object(execute.os, 'killpg') as kill:
                with self.assertRaises(execute.HarnessExit) as caught:
                    ex.recover()
                self.assertEqual(caught.exception.code, 1)
                self.assertIn(str(ex.marker_path), str(caught.exception))
                kill.assert_not_called()
            self.assertEqual(dirty.read_text(), 'dirty')
            self.assertEqual(ex.marker_path.read_text(), content)
            self.assertEqual(self.git(ex.root, 'for-each-ref', 'refs/harness/'), b'')

    def test_signal_kills_group_keeps_marker(self):
        for sig in (signal.SIGTERM, signal.SIGHUP):
            with self.subTest(sig=sig):
                ex = self.fixture()
                ready = self.temp_dir / f'ready-{sig}'
                fake = self.fake_bin('codex', f"""
import subprocess, signal, time
child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])
def terminate(sig, frame):
    child.wait(timeout=2)
    sys.exit(0)
signal.signal(signal.SIGTERM, terminate)
Path({str(ready)!r}).write_text(json.dumps([os.getpid(), child.pid]))
time.sleep(60)
""")
                driver = self.fake_bin('driver', f"""
sys.path.insert(0, {str(Path(execute.__file__).parent)!r})
import execute
ex = execute.Executor(Path({str(ex.root)!r}), {PHASE!r})
ex.install_signal_handlers()
ex.save_marker({self.marker_for(ex)!r})
try:
    ex.run_child([{str(fake)!r}], env=dict(os.environ), timeout=60)
finally:
    ex.restore_signal_handlers()
""")
                proc = subprocess.Popen([str(driver)], start_new_session=True,
                                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                self.addCleanup(self.stop_process, proc)
                self.wait_file(ready)
                before = ex.marker_path.read_bytes()
                children = json.loads(ready.read_text())
                os.kill(proc.pid, sig)
                self.assertNotEqual(proc.wait(timeout=5), 0)
                for pid in children:
                    SessionRunnerTests.assert_gone(self, pid)
                self.assertEqual(ex.marker_path.read_bytes(), before)

    def test_run_recovery_order_and_signal_restore(self):
        ex = self.fixture()
        old = {sig: signal.getsignal(sig) for sig in (signal.SIGTERM, signal.SIGHUP)}
        events = []
        def record(name):
            events.append(name)
        with mock.patch.object(ex, 'acquire_lock', side_effect=lambda: record('lock')), \
                mock.patch.object(ex, 'recover', side_effect=lambda: record('recover')), \
                mock.patch.object(ex, 'prepare', side_effect=lambda: record('prepare')), \
                mock.patch.object(ex, 'load_step_specs', side_effect=lambda: record('specs')), \
                mock.patch.object(ex, 'run_steps', side_effect=lambda specs: record('steps')), \
                mock.patch.object(ex, 'review_gate', return_value=0):
            install = ex.install_signal_handlers
            def installed():
                record('signals')
                install()
            with mock.patch.object(ex, 'install_signal_handlers', side_effect=installed):
                self.assertEqual(ex.run(), 0)
        self.assertEqual(events, ['lock', 'signals', 'recover', 'prepare', 'specs', 'steps'])
        for exception in (execute.HarnessInterrupted(), KeyboardInterrupt()):
            with mock.patch.object(ex, 'recover', side_effect=exception):
                self.assertEqual(ex.run(), 1)
        self.assertEqual({sig: signal.getsignal(sig) for sig in old}, old)

    def test_recovery_pgid_guards_and_marker_memory(self):
        ex = self.fixture()
        marker = self.marker_for(ex)
        ex.save_marker(marker)
        ex.marker_path.write_text('{broken')
        ex.marker['pgid'] = 12
        ex.save_marker(ex.marker)
        self.assertEqual(ex.load_marker(), dict(marker, pgid=12))
        for pgid in (None, -1, 0, 1, os.getpgrp()):
            with mock.patch.object(execute.subprocess, 'run') as ps, \
                    mock.patch.object(execute.os, 'killpg') as kill:
                ex._kill_stale_codex(pgid)
                ps.assert_not_called()
                kill.assert_not_called()
        pgid = os.getpgrp() + 10000
        for failure in (ProcessLookupError, PermissionError):
            result = subprocess.CompletedProcess([], 0, f'123 {pgid} node /tmp/codex.js', '')
            with mock.patch.object(execute.subprocess, 'run', return_value=result) as ps, \
                    mock.patch.object(execute.os, 'killpg', side_effect=failure) as kill:
                if failure is PermissionError:
                    self.assert_exit(1, ex._kill_stale_codex, pgid)
                else:
                    ex._kill_stale_codex(pgid)
                self.assertEqual(ps.call_args.args[0], ['ps', '-A', '-o', 'pid=,pgid=,command='])
                kill.assert_called_once_with(pgid, signal.SIGKILL)
        ex.clear_marker()
        ex.clear_marker()
        self.assertIsNone(ex.load_marker())



class AttemptLoopTests(HarnessTestCase):
    def fixture(self, scenarios=None):
        root = self.make_repo()
        self.git(root, 'switch', '-c', f'feat-{PHASE}')
        ex = self.make_executor(root)
        counter = self.temp_dir / ('counter-' + root.name)
        prompts = self.temp_dir / ('prompts-' + root.name)
        os.environ['ATTEMPT_SCENARIOS'] = json.dumps(scenarios or [{}])
        os.environ['ATTEMPT_COUNTER'] = str(counter)
        os.environ['ATTEMPT_PROMPTS'] = str(prompts)
        self.fake_bin('codex', r"""
if 'mcp' in sys.argv:
    print('[]')
    sys.exit(0)
counter = Path(os.environ['ATTEMPT_COUNTER'])
k = int(counter.read_text()) + 1 if counter.exists() else 1
counter.write_text(str(k))
with Path(os.environ['ATTEMPT_PROMPTS']).open('a') as stream:
    stream.write(json.dumps(sys.stdin.read()) + '\n')
scenarios = json.loads(os.environ['ATTEMPT_SCENARIOS'])
scenario = scenarios[min(k - 1, len(scenarios) - 1)]
last = Path(sys.argv[sys.argv.index('-o') + 1])
result = last.with_name(last.name.replace('-last.txt', '-result.json'))
for name, content in scenario.get('files', {}).items():
    path = Path(name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
if scenario.get('rename'):
    import subprocess
    subprocess.run(['git', 'mv', *scenario['rename']], check=True)
if scenario.get('commit'):
    import subprocess
    subprocess.run(['git', 'commit', '--allow-empty', '-qm', 'forbidden'], check=True)
if scenario.get('marker'):
    (last.parent / 'attempt.json').write_text('{tampered')
if not scenario.get('missing'):
    result.write_text(json.dumps(scenario.get('result', {'status': 'completed', 'summary': 'src change'})))
if scenario.get('sleep'):
    import time
    time.sleep(60)
sys.exit(scenario.get('exit', 0))
""")
        return ex, counter, prompts

    def attempt(self, ex, ac=('true',), **kwargs):
        return ex.attempt_unit('step4', 'implement sample', ['src/'], ac, **kwargs)

    def test_stale_result_deleted(self):
        ex, counter, _ = self.fixture([{'missing': True}])
        ex.run_dir.mkdir(parents=True)
        ex.result_path('step4').write_text(json.dumps({'status': 'completed', 'summary': 'stale'}))
        out = self.attempt(ex)
        self.assertEqual(out.status, 'error')
        self.assertIn('result', out.reason)
        self.assertEqual(counter.read_text(), '3')

    def test_ac_and_list_failure_fails(self):
        for line in ('false && true', 'false | true'):
            with self.subTest(line=line):
                ex, _, _ = self.fixture()
                out = self.attempt(ex, [line], start_k=3)
                self.assertEqual(out.status, 'error')
                self.assertIn(line, out.reason)
                self.assertIn('종료 코드 1', out.reason)

    def test_bash_env_cannot_skip_ac(self):
        ex, _, _ = self.fixture()
        startup = self.temp_dir / 'startup'
        startup.write_text('exit 0\n')
        os.environ.update(BASH_ENV=str(startup), ENV=str(startup), ORCA_TOKEN='secret')
        reason = ex.run_ac(['echo RAN; exit 1'])
        self.assertIn('\nRAN\n', reason)
        self.assertIn('종료 코드 1', reason)
        for key in ('BASH_ENV', 'ENV', 'ORCA_TOKEN'):
            self.assertNotIn(key, ex.child_env())

    def test_allowed_ignored_artifact_and_rollback(self):
        for status in ('completed', 'error', 'blocked'):
            with self.subTest(status=status):
                ex, _, _ = self.fixture([{'files': {'src/build.log': 'new', 'tool.log': 'protected'},
                    'result': {'status': status, 'summary': 'ok'}}])
                # The tool state is preexisting and must survive every rollback.
                (ex.root / 'tool.log').write_text('protected')
                (ex.root / 'src/existing.log').write_text('keep')
                out = self.attempt(ex)
                self.assertEqual(out.status, status)
                self.assertEqual((ex.root / 'src/build.log').exists(), status == 'completed')
                self.assertTrue((ex.root / 'tool.log').exists())
                self.assertEqual((ex.root / 'src/existing.log').read_text(), 'keep')
        ex, counter, _ = self.fixture()
        out = self.attempt(ex, ['echo artifact > src/build.log; false'])
        self.assertEqual((out.status, counter.read_text()), ('error', '3'))
        self.assertFalse((ex.root / 'src/build.log').exists())

    def test_allowed_ignored_directory_rollback(self):
        ex, _, _ = self.fixture([{'files': {'src/dist/deep/output': 'built'}}])
        (ex.root / '.gitignore').open('a').write('dist/\n')
        ex.git('add', '--', '.gitignore')
        ex.git('commit', '-qm', 'ignore build fixture')
        out = self.attempt(ex, ['false'])
        self.assertEqual(out.status, 'error')
        self.assertFalse((ex.root / 'src/dist').exists())

    def test_ignored_baseline_survives_crash_recovery(self):
        ex, counter, _ = self.fixture([{'files': {'outside.log': 'new', 'src/build.log': 'new'}}])
        baseline = ex.ignored_paths()
        ex.save_marker({'unit': 'step4', 'k': 1, 'stage': 'running', 'pre_sha': ex.head(),
                        'feat_sha': None, 'pgid': None, 'allowed': ['src/'],
                        'ignored_before': sorted(baseline)})
        (ex.root / 'outside.log').write_text('new')
        (ex.root / 'src/build.log').write_text('new')
        resumed = self.make_executor(ex.root)
        resumed.recover()
        self.assertFalse((ex.root / 'src/build.log').exists())
        self.assertTrue((ex.root / 'outside.log').exists())
        out = self.attempt(resumed, start_k=resumed.resume['next_k'])
        self.assertEqual((out.status, out.attempts, counter.read_text()), ('error', 2, '1'))
        self.assertIn('⑤', out.reason)
        self.assertTrue((ex.root / 'outside.log').exists())

    def test_old_run_marker_is_not_trusted(self):
        ex, _, _ = self.fixture()
        ex.run_dir.mkdir(parents=True)
        (ex.run_dir / 'attempt.json').write_text('{"stage": "feat_done"}')
        ex.recover()
        self.assertIsNone(ex.resume)
        self.assertIsNone(ex.load_marker())
        expected = ex.root / ex.git('rev-parse', '--git-path',
                                   f'harness/{PHASE}/attempt.json').stdout.decode().strip()
        self.assertEqual(ex.marker_path, expected)

    def test_ac_env_change_errors_without_retry(self):
        ex, counter, _ = self.fixture()
        (ex.root / '.env').write_bytes(b'original')
        out = self.attempt(ex, ['echo changed > .env'])
        self.assertEqual((ex.root / '.env').read_bytes(), b'original')
        self.assertEqual((out.status, out.attempts, counter.read_text()), ('error', 1, '1'))
        self.assertIn('④', out.reason)

    def test_spawn_errors_do_not_leave_marker(self):
        ex, _, _ = self.fixture()
        (ex.root / 'docs/adr/0001-sample.md').write_bytes(b'\xff')
        ex.git('add', '--', 'docs/adr/0001-sample.md')
        ex.git('commit', '-qm', 'invalid encoding fixture')
        with self.assertRaises(UnicodeDecodeError):
            self.attempt(ex)
        self.assertFalse(ex.marker_path.exists())
        with mock.patch.object(ex, 'build_prompt', return_value='prompt'), \
                mock.patch.object(ex, 'codex_preflight', return_value=[]), \
                mock.patch.object(execute.subprocess, 'Popen', side_effect=OSError('spawn failed')):
            # Mock only the Codex call so git reads remain real.
            with mock.patch.object(ex, 'changed_paths', return_value=[]), \
                    mock.patch.object(ex, 'head', return_value='a' * 40), \
                    mock.patch.object(ex, 'ignored_paths', return_value=set()), \
                    mock.patch.object(type(ex), 'marker_path', new_callable=mock.PropertyMock,
                                      return_value=ex.root / '.git/harness/attempt.json'), \
                    mock.patch.object(ex, 'git_fingerprint', return_value={}):
                with self.assertRaises(OSError):
                    self.attempt(ex)
        self.assertFalse((ex.root / '.git/harness/attempt.json').exists())

    def test_git_metadata_session_and_ac_stop_without_retry(self):
        for target in ('.git/config', '.git/hooks/new-hook', '.git/info/new-info'):
            for in_ac in (False, True):
                with self.subTest(target=target, in_ac=in_ac):
                    ex, counter, _ = self.fixture()
                    content = '[core]\n\tfsmonitor = false\n' if target == '.git/config' else '# changed\n'
                    if not in_ac:
                        os.environ['ATTEMPT_SCENARIOS'] = json.dumps([{'files': {target: content}}])
                    ac = (["git config core.fsmonitor false"] if target == '.git/config'
                          else [f"echo '# changed' >> {target}"]) if in_ac else ['true']
                    with mock.patch.object(ex, 'rollback', wraps=ex.rollback) as rollback:
                        out = self.attempt(ex, ac)
                        self.assertEqual(out.status, 'error')
                        self.assertIn('④', out.reason)
                        rollback.assert_called_once()
                    self.assertEqual(counter.read_text(), '1')
                    self.assertTrue(ex.marker_path.exists())

    def test_tool_state_ignored_directories_survive(self):
        for existing in (False, True):
            for result in ('completed', 'blocked'):
                ex, _, _ = self.fixture([{'files': {
                    'graft/.cache/session/new.json': '{}', '.omc/session/new.json': '{}'},
                    'result': {'status': result, 'summary': 'ok'}}])
                (ex.root / '.gitignore').open('a').write('graft/\n.omc/\n')
                ex.git('add', '--', '.gitignore')
                ex.git('commit', '-qm', 'tool ignore fixture')
                if existing:
                    (ex.root / 'graft').mkdir()
                    (ex.root / 'graft/old').write_text('old')
                self.assertEqual(self.attempt(ex).status, result)
                for name in ('graft/.cache/session/new.json', '.omc/session/new.json'):
                    self.assertTrue((ex.root / name).exists())

    def test_ignored_directory_keeps_env_and_does_not_follow_links(self):
        ex, _, _ = self.fixture([{'files': {'src/dist/.env.local': 'secret',
                                          'src/dist/build': 'new'}}])
        (ex.root / '.gitignore').open('a').write('dist/\n')
        ex.git('add', '--', '.gitignore')
        ex.git('commit', '-qm', 'ignore directory')
        outside = self.temp_dir / 'outside'
        outside.mkdir()
        (outside / 'keep').write_text('keep')
        original = ex.run_codex
        def session(*args, **kw):
            child = original(*args, **kw)
            (ex.root / 'src/dist/link').symlink_to(outside)
            return child
        with mock.patch.object(ex, 'run_codex', side_effect=session):
            self.assertEqual(self.attempt(ex, ['false']).status, 'error')
        self.assertEqual((ex.root / 'src/dist/.env.local').read_text(), 'secret')
        # After the first rollback the preserved directory is still a new status item.
        self.assertFalse((ex.root / 'src/dist/build').exists())
        self.assertEqual((outside / 'keep').read_text(), 'keep')

    def test_git_branch_config_is_allowed(self):
        ex, _, _ = self.fixture()
        original = ex.run_codex
        def session(*args, **kw):
            child = original(*args, **kw)
            ex.git('config', 'branch.x.remote', 'origin')
            return child
        with mock.patch.object(ex, 'run_codex', side_effect=session):
            self.assertEqual(self.attempt(ex).status, 'completed')

    def test_git_fsmonitor_restored_before_any_repository_git(self):
        for in_ac in (False, True):
            ex, counter, _ = self.fixture()
            ex.prepare()
            config = ex.root / '.git/config'
            before = config.read_bytes()
            canary = self.temp_dir / ('canary-' + ex.root.name)
            hook = self.temp_dir / ('monitor-' + ex.root.name)
            hook.write_text('#!/bin/sh\necho ran > ' + str(canary) + '\n')
            hook.chmod(0o755)
            original = ex.run_codex
            def session(*args, **kw):
                child = original(*args, **kw)
                config.open('a').write('\n[core]\nfsmonitor = ' + str(hook) + '\n')
                return child
            if in_ac:
                out = self.attempt(ex, ['git config core.fsmonitor ' + str(hook)])
            else:
                with mock.patch.object(ex, 'run_codex', side_effect=session):
                    out = self.attempt(ex)
            self.assertEqual((out.status, counter.read_text()), ('error', '1'))
            ex.confirm_step(0, out.status, out.reason)
            self.assertEqual(config.read_bytes(), before)
            self.assertFalse(canary.exists())
            self.assertEqual(ex.changed_paths(), [])
            self.assertFalse(ex.marker_path.exists())
            data = ex.load_index()
            data['steps'][0]['status'] = 'pending'
            ex.save_index(data)
            self.make_executor(ex.root).prepare()
            self.assertEqual(ex.changed_paths(), [])

    def test_git_fifo_restored_without_blocking_and_recovery_is_safe(self):
        ex, counter, _ = self.fixture()
        ex.prepare()
        config = ex.root / '.git/config'
        before = config.read_bytes()
        canary = self.temp_dir / 'fifo-canary'
        monitor = self.temp_dir / 'fifo-monitor'
        monitor.write_text('#!/bin/sh\necho ran > ' + str(canary) + '\n')
        monitor.chmod(0o755)
        original = ex.run_codex
        def session(*args, **kw):
            child = original(*args, **kw)
            os.mkfifo(ex.root / '.git/hooks/0pipe')
            with config.open('a') as stream:
                stream.write('\n[core]\nfsmonitor = ' + str(monitor) + '\n')
            return child
        started = time.monotonic()
        with mock.patch.object(ex, 'run_codex', side_effect=session):
            out = self.attempt(ex)
        self.assertLess(time.monotonic() - started, 5)
        self.assertEqual((out.status, counter.read_text()), ('error', '1'))
        self.assertEqual(config.read_bytes(), before)
        self.assertFalse((ex.root / '.git/hooks/0pipe').exists())
        self.assertFalse(canary.exists())
        marker = ex.load_marker()
        marker['pgid'] = None
        ex.save_marker(marker)
        recovered = self.make_executor(ex.root)
        recovered.recover()
        self.assertFalse(canary.exists())

    def test_interrupted_child_restores_git_before_next_startup(self):
        ex, _, _ = self.fixture([{'files': {'src/alpha.txt': 'alpha'}}])
        canary = self.temp_dir / 'interrupt-canary'
        monitor = self.temp_dir / 'interrupt-monitor'
        monitor.write_text('#!/bin/sh\necho ran > ' + str(canary) + '\n')
        monitor.chmod(0o755)
        command = ("printf '\\n[core]\\nfsmonitor = " + str(monitor)
                   + "\\n' >> .git/config; kill -TERM \"$PPID\"; sleep 5")
        instruction = ex.phase_path / 'step0.md'
        instruction.write_text(step_md(0, 'alpha', ['src/'], [command]))
        ex.git('add', '--', str(instruction.relative_to(ex.root)))
        ex.git('commit', '-qm', 'interrupting AC fixture')
        config = ex.root / '.git/config'
        before = config.read_bytes()
        self.assertEqual(ex.run(), 1)
        self.assertEqual(config.read_bytes(), before)
        self.assertFalse(canary.exists())
        self.assertTrue(ex.marker_path.exists())
        ex._lock_file.close()
        resumed = self.make_executor(ex.root)
        with mock.patch.object(resumed, '_kill_stale_codex'), \
                mock.patch.object(resumed, 'run_steps'), \
                mock.patch.object(resumed, 'review_gate', return_value=0):
            self.assertEqual(resumed.run(), 0)
        self.assertFalse(canary.exists())

    def test_special_env_capture_and_ignored_removal_do_not_read_fifo(self):
        ex, _, _ = self.fixture()
        env_pipe = ex.root / '.env.pipe'
        ignored_pipe = ex.root / 'ignored.pipe'
        os.mkfifo(env_pipe)
        os.mkfifo(ignored_pipe)
        self.assertEqual(ex.capture_env()['.env.pipe'][0], 'special')
        self.assertIn('.env.pipe', ex.env_fingerprint())
        ex.remove_ignored(ignored_pipe)
        self.assertFalse(ignored_pipe.exists())

    def test_git_restore_failure_blocks_recovery_without_index_edits(self):
        ex, _, _ = self.fixture()
        ex.prepare()
        indices = (ex.index_path.read_bytes(), ex.top_index_path.read_bytes())
        canary = self.temp_dir / 'guard-canary'
        hook = self.temp_dir / 'guard-monitor'
        hook.write_text('#!/bin/sh\necho ran > ' + str(canary) + '\n')
        hook.chmod(0o755)
        original = ex.run_codex
        def session(*args, **kw):
            child = original(*args, **kw)
            (ex.root / '.git/config').open('a').write('\n[core]\nfsmonitor = ' + str(hook) + '\n')
            return child
        with mock.patch.object(ex, 'run_codex', side_effect=session), \
                mock.patch.object(ex, 'restore_path', side_effect=OSError('cannot restore')):
            self.assert_exit(1, self.attempt, ex)
        self.assertTrue(ex.git_guard_path.exists())
        self.assertEqual((ex.index_path.read_bytes(), ex.top_index_path.read_bytes()), indices)
        resumed = self.make_executor(ex.root)
        with mock.patch.object(resumed, 'recover') as recover, \
                mock.patch.object(resumed, 'git', side_effect=AssertionError('git after lock')):
            self.assertEqual(resumed.run(), 1)
            recover.assert_not_called()
        self.assertFalse(canary.exists())

    def test_git_hooks_info_restore_kinds_permissions_and_canary(self):
        ex, _, _ = self.fixture()
        ex.prepare()
        canary = self.temp_dir / 'hook-canary'
        external = self.temp_dir / 'hook-external'
        external.mkdir()
        (external / 'keep').write_text('keep')
        hooks, info = ex.root / '.git/hooks', ex.root / '.git/info'
        old = hooks / 'old-hook'
        old.write_bytes(b'old bytes')
        old.chmod(0o751)
        (info / 'old-link').symlink_to(external)
        saved = ex.capture_git_guard()
        original = ex.run_codex
        def session(*args, **kw):
            child = original(*args, **kw)
            old.unlink()
            (info / 'exclude').write_bytes(b'changed')
            (info / 'old-link').unlink()
            (info / 'old-link').mkdir()
            (info / 'new-link').symlink_to(external)
            hook = hooks / 'reference-transaction'
            hook.write_text('#!/bin/sh\necho ran > ' + str(canary) + '\n')
            hook.chmod(0o755)
            return child
        with mock.patch.object(ex, 'run_codex', side_effect=session):
            out = self.attempt(ex)
        self.assertEqual(out.status, 'error')
        ex.confirm_step(0, out.status, out.reason)
        self.assertEqual(ex.capture_git_guard(), saved)
        self.assertEqual((external / 'keep').read_text(), 'keep')
        self.assertFalse(canary.exists())
        self.assertEqual(ex.changed_paths(), [])
        self.assertFalse(ex.marker_path.exists())

    def test_existing_ignored_directory_new_files_are_preserved(self):
        ex, _, _ = self.fixture([{'files': {'src/dist/new': 'new'}}])
        ignore = ex.root / '.gitignore'
        ignore.write_text(ignore.read_text() + 'dist/\n')
        ex.git('add', '--', '.gitignore')
        ex.git('commit', '-qm', 'ignore directory')
        (ex.root / 'src/dist').mkdir()
        (ex.root / 'src/dist/old').write_text('old')
        self.assertEqual(self.attempt(ex, ['false']).status, 'error')
        self.assertEqual((ex.root / 'src/dist/new').read_text(), 'new')

    def test_outside_ignored_error_commits_indices_and_resets_pending(self):
        ex, counter, _ = self.fixture([{'files': {'outside.log': 'new'}}])
        ex.prepare()
        self.assert_exit(1, ex.run_steps, ex.load_step_specs())
        self.assertEqual(counter.read_text(), '1')
        self.assertEqual(ex.load_index()['steps'][0]['status'], 'error')
        self.assertEqual(ex.changed_paths(), [])
        self.assertFalse(ex.marker_path.exists())
        data = ex.load_index()
        data['steps'][0]['status'] = 'pending'
        ex.save_index(data)
        self.make_executor(ex.root).prepare()
        self.assertEqual(ex.changed_paths(), [])

    def test_crash_env_hash_errors_without_retry(self):
        ex, _, _ = self.fixture()
        ex.prepare()
        (ex.root / '.env').write_text('original')
        ex.save_marker({'unit': 'step0', 'k': 1, 'stage': 'running', 'pre_sha': ex.head(),
                        'feat_sha': None, 'pgid': None, 'allowed': ['src/'],
                        'ignored_before': sorted(ex.ignored_paths()),
                        'env_before': ex.env_fingerprint()})
        (ex.root / '.env').write_text('changed during crash')
        (ex.root / 'src/.env.local').write_text('human secret')
        resumed = self.make_executor(ex.root)
        self.assertEqual(resumed.run(), 1)
        self.assertEqual(resumed.load_index()['steps'][0]['status'], 'error')
        self.assertFalse(resumed.marker_path.exists())
        self.assertEqual(resumed.changed_paths(), [])
        self.assertEqual((ex.root / 'src/.env.local').read_text(), 'human secret')
        self.assertIsNone(resumed.resume)
        self.assertTrue(any('수동 복원 필요' in ' '.join(args) for args in self.calls('gh')))

    def test_env_deletion_and_creation_restore_original_set(self):
        ex, counter, _ = self.fixture([{'files': {'.env.new': 'new secret'}}])
        (ex.root / '.env').write_bytes(b'original secret')
        original = ex.run_codex
        def session(*args, **kw):
            child = original(*args, **kw)
            (ex.root / '.env').unlink()
            return child
        with mock.patch.object(ex, 'run_codex', side_effect=session):
            out = self.attempt(ex)
        self.assertEqual((out.status, counter.read_text()), ('error', '1'))
        self.assertEqual((ex.root / '.env').read_bytes(), b'original secret')
        self.assertFalse((ex.root / '.env.new').exists())

    def test_symlink_env_target_change_requires_manual_restore(self):
        ex, _, _ = self.fixture()
        target = self.temp_dir / 'linked-env-target'
        target.write_bytes(b'original')
        (ex.root / '.env').symlink_to(target)
        out = self.attempt(ex, ['echo changed > .env'])
        self.assertEqual(out.status, 'error')
        self.assertIn('④ .env 링크 대상 변경: 수동 복원 필요', out.reason)
        self.assertEqual(target.read_bytes(), b'changed\n')

    def test_feat_done_crash_env_change_rolls_back_and_errors(self):
        ex, _, _ = self.fixture()
        ex.prepare()
        (ex.root / '.env').write_text('original')
        ex.save_marker({'unit': 'step0', 'k': 1, 'stage': 'running', 'pre_sha': ex.head(),
                        'feat_sha': None, 'pgid': None, 'allowed': ['src/'],
                        'ignored_before': sorted(ex.ignored_paths()),
                        'env_before': ex.env_fingerprint()})
        ex.run_dir.mkdir(parents=True, exist_ok=True)
        ex.result_path('step0').write_text(json.dumps({'status': 'completed', 'summary': 'ok'}))
        (ex.root / 'src/new.txt').write_text('completed before crash')
        ex.commit_feat('feat fixture', ex.head())
        (ex.root / '.env').write_text('changed after feat')
        resumed = self.make_executor(ex.root)
        self.assertEqual(resumed.run(), 1)
        self.assertFalse((ex.root / 'src/new.txt').exists())
        self.assertEqual(resumed.load_index()['steps'][0]['status'], 'error')
        self.assertEqual(resumed.changed_paths(), [])
        self.assertFalse(resumed.marker_path.exists())

    def test_change_outside_allowed_fails(self):
        ex, _, _ = self.fixture([{'files': {'AGENTS.md': 'changed'}}])
        original = (ex.root / 'AGENTS.md').read_bytes()
        out = self.attempt(ex)
        self.assertEqual(out.status, 'error')
        self.assertIn('③', out.reason)
        self.assertEqual((ex.root / 'AGENTS.md').read_bytes(), original)

    def test_session_index_edit_fails(self):
        ex, _, _ = self.fixture([{'files': {f'phases/{PHASE}/index.json': '{}'}}])
        original = ex.index_path.read_bytes()
        out = self.attempt(ex)
        self.assertEqual(out.status, 'error')
        self.assertIn('③', out.reason)
        self.assertEqual(ex.index_path.read_bytes(), original)

    def test_ac_tree_change_fails(self):
        ex, _, _ = self.fixture()
        out = self.attempt(ex, ['touch src/new.txt'])
        self.assertEqual(out.status, 'error')
        self.assertIn('⑦', out.reason)
        self.assertFalse((ex.root / 'src/new.txt').exists())

    def test_env_change_errors_without_retry(self):
        ex, counter, _ = self.fixture([{'files': {'.env': 'changed'}}])
        (ex.root / '.env').write_text('before')
        out = self.attempt(ex)
        self.assertEqual(out.status, 'error')
        self.assertEqual(out.attempts, 1)
        self.assertIn('.env', out.reason)
        self.assertEqual(counter.read_text(), '1')
        self.assertEqual(ex.changed_paths(), [])
        self.assertEqual(ex.load_marker(), ex.marker)

    def test_new_ignored_outside_run_fails(self):
        ex, _, _ = self.fixture([{'files': {'build.log': 'new'}}])
        out = self.attempt(ex, start_k=1)
        self.assertEqual((out.status, out.attempts), ('error', 1))
        self.assertEqual(len([a for a in self.calls('codex') if a[0] == 'exec']), 1)
        self.assertTrue((ex.root / 'build.log').exists())
        self.assertIn('⑤', out.reason)
        self.assertIn('build.log', out.reason)
        ex, _, _ = self.fixture([{'files': {
            f'phases/{PHASE}/.run/extra.log': 'ok', '__pycache__/cache': 'ok',
            'src/cache.pyc': 'ok', 'src/keep.txt': 'changed'}}])
        before = ex.head()
        out = self.attempt(ex)
        self.assertEqual(out.status, 'completed')
        self.assertEqual(out.pre_sha, before)
        self.assertEqual(out.summary, 'src change')
        self.assertEqual(ex.marker['stage'], 'running')
        self.assertEqual((ex.root / 'src/keep.txt').read_text(), 'changed')

    def test_blocked_rolls_back_uncounted(self):
        ex, counter, _ = self.fixture([
            {'result': {'status': 'error', 'error_message': 'first'}},
            {'files': {'src/keep.txt': 'partial'},
             'result': {'status': 'blocked', 'blocked_reason': 'human decision'}}])
        out = self.attempt(ex)
        self.assertEqual((out.status, out.attempts, out.reason), ('blocked', 1, 'human decision'))
        self.assertEqual(counter.read_text(), '2')
        self.assertEqual(ex.changed_paths(), [])
        self.assertIn(b'/attempt2-', self.git(ex.root, 'for-each-ref', '--format=%(refname)', 'refs/harness/'))
        self.assertEqual(ex.load_marker()['k'], 2)

    def test_third_failure_error(self):
        ex, counter, _ = self.fixture([{'result': {'status': 'error', 'error_message': 'failure'},
                                      'files': {'src/keep.txt': 'partial'}}])
        out = self.attempt(ex)
        self.assertEqual((out.status, out.attempts), ('error', 3))
        self.assertEqual(counter.read_text(), '3')
        self.assertEqual(len(self.git(ex.root, 'for-each-ref', '--format=%(refname)', 'refs/harness/').splitlines()), 3)
        self.assertEqual(ex.changed_paths(), [])
        self.assertEqual(ex.load_marker()['k'], 3)
        self.assertEqual(len([args for args in self.calls('codex') if args[0] == 'exec']), 3)

    def test_retry_prompt_has_reason(self):
        ex, counter, prompts = self.fixture()
        out = self.attempt(ex, ['if [ "$(cat "$ATTEMPT_COUNTER")" = 1 ]; then echo MARKER-42; exit 1; fi'])
        self.assertEqual((out.status, out.attempts), ('completed', 2))
        second = json.loads(prompts.read_text().splitlines()[1])
        self.assertIn('MARKER-42', second)
        self.assertIn('⑥ AC 실패', second)
        self.assertEqual(counter.read_text(), '2')

    def test_marker_tampering_preflight_and_exhaustion(self):
        ex, _, _ = self.fixture([{'marker': True}])
        self.assertEqual(self.attempt(ex).status, 'completed')
        self.assertEqual(ex.load_marker(), ex.marker)
        self.assertIsInstance(ex.marker['pgid'], int)
        ex.clear_marker()
        with mock.patch.object(ex, 'codex_preflight', side_effect=execute.HarnessExit(1, 'preflight')):
            self.assert_exit(1, self.attempt, ex)
        self.assertIsNone(ex.load_marker())
        with mock.patch.object(ex, 'run_codex') as session:
            out = self.attempt(ex, start_k=4)
            self.assertEqual((out.status, out.attempts), ('error', 3))
            self.assertIn('소진', out.reason)
            session.assert_not_called()
        (ex.root / 'src/keep.txt').write_text('dirty')
        self.assert_exit(1, self.attempt, ex)

    def test_result_validation_and_root_env_scope(self):
        ex, _, _ = self.fixture()
        ex.run_dir.mkdir(parents=True)
        for text in ('{bad', '[]', 'null', '{"status": []}', '{"status": "unknown"}'):
            ex.result_path('step4').write_text(text)
            self.assertIsNone(ex.read_result('step4'))
        (ex.root / '.env.example').write_text('sample')
        (ex.root / 'src/.env').write_text('nested')
        self.assertEqual(ex.env_fingerprint(), {})
        (ex.root / '.env.local').write_text('value')
        before = ex.env_fingerprint()
        self.assertEqual(set(before), {'.env.local'})
        self.assertEqual(len(before['.env.local']), 64)
        (ex.root / '.env.local').unlink()
        self.assertNotEqual(before, ex.env_fingerprint())

    def test_summary_head_rename_and_child_failures(self):
        cases = [({'result': {'status': 'completed', 'summary': '  '}}, '①'),
                 ({'commit': True}, '②'),
                 ({'rename': ['AGENTS.md', 'src/agents.md']}, '③'),
                 ({'exit': 9}, '종료 코드 9'),
                 ({'sleep': True}, 'timeout')]
        for scenario, reason in cases:
            with self.subTest(scenario=scenario):
                ex, _, _ = self.fixture([scenario])
                ex.session_timeout = 0.1
                before = ex.head()
                out = self.attempt(ex, start_k=3)
                self.assertEqual(out.status, 'error')
                self.assertIn(reason, out.reason)
                self.assertEqual(ex.head(), before)
                self.assertEqual(ex.changed_paths(), [])

    def test_ac_separate_shells_timeout_and_head_change(self):
        ex, _, _ = self.fixture()
        self.assertIsNone(ex.run_ac(['export AC_LOCAL_ONLY=value', 'test -z "$AC_LOCAL_ONLY"']))
        ex.ac_timeout = 0.1
        self.assertIn('timeout', ex.run_ac(['echo AC-TIMEOUT; sleep 60']))
        self.assertIn('⑦', ex.run_ac(['git commit --allow-empty -qm ac-change']))



class ScopedCommitTests(HarnessTestCase):
    def fixture(self, scenarios=None, steps=None, files=None):
        ex = self.make_executor(self.make_repo(
            steps=steps or [{'name': 'alpha', 'ac': ['true']}], files=files))
        # Keep scoped-commit assertions isolated from the later review gate.
        gate = mock.patch.object(ex, 'review_gate', return_value=0)
        gate.start()
        self.addCleanup(gate.stop)
        ex.prepare()
        os.environ['UNIT_SCENARIOS'] = json.dumps(scenarios or {})
        self.fake_bin('codex', r"""
if 'mcp' in sys.argv:
    print('[]')
    sys.exit(0)
prompt = sys.stdin.read()
last = Path(sys.argv[sys.argv.index('-o') + 1])
unit = last.name.removesuffix('-last.txt')
scenario = json.loads(os.environ['UNIT_SCENARIOS']).get(unit, {})
for name, content in scenario.get('files', {}).items():
    path = Path(name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
for name in scenario.get('delete', []):
    Path(name).unlink()
if scenario.get('rename'):
    import subprocess
    subprocess.run(['git', 'mv', *scenario['rename']], check=True)
last.with_name(unit + '-result.json').write_text(json.dumps(scenario.get(
    'result', {'status': 'completed', 'summary': unit + ' output'})))
""")
        return ex

    def exec_calls(self):
        return [args for args in self.calls('codex') if args and args[0] == 'exec']

    def commit_files(self, ex, ref='HEAD'):
        return set(self.git(ex.root, 'diff-tree', '--no-commit-id', '--name-only',
                            '--no-renames', '-r', ref).decode().splitlines())

    def test_feat_commit_exact_paths_with_decoy(self):
        ex = self.fixture({'step0': {'files': {
            'src/keep.txt': 'changed', 'src/__pycache__/x.pyc': 'cache',
            f'phases/{PHASE}/.run/extra.txt': 'artifact'}}})
        (ex.root / '.env').write_text('existing fixture value')
        self.assertEqual(ex.run(), 0)
        self.assertEqual(self.commit_files(ex, 'HEAD~1'), {'src/keep.txt'})
        self.assertEqual(self.git(ex.root, 'log', '-1', '--format=%s', 'HEAD~1').strip(),
                         b'feat: 7-sample step0 alpha (#7)')
        self.assertEqual((ex.root / '.env').read_text(), 'existing fixture value')
        self.assertFalse(ex.marker_path.exists())
        self.assertEqual(len(self.exec_calls()), 1)

    def test_delete_and_rename_committed(self):
        ex = self.fixture({'step0': {'delete': ['src/delete.txt'],
                                    'rename': ['src/keep.txt', 'src/moved.txt']}},
                          files={'src/delete.txt': 'delete me'})
        self.assertEqual(ex.run(), 0)
        changes = self.git(ex.root, 'diff-tree', '--no-commit-id', '--name-status',
                           '--no-renames', '-r', 'HEAD~1').decode().splitlines()
        self.assertEqual(set(changes), {'D\tsrc/delete.txt', 'D\tsrc/keep.txt',
                                        'A\tsrc/moved.txt'})

    def test_no_change_skips_feat(self):
        ex = self.fixture()
        before = ex.head()
        self.assertEqual(ex.run(), 0)
        self.assertEqual(self.git(ex.root, 'rev-list', '--count', f'{before}..HEAD').strip(), b'1')
        self.assertEqual(self.git(ex.root, 'log', '-1', '--format=%s').strip(),
                         b'chore: 7-sample step0 completed (#7)')
        self.assertFalse(ex.marker_path.exists())

    def test_chore_only_index_files(self):
        for status in ('completed', 'error', 'blocked'):
            with self.subTest(status=status):
                ex = self.fixture()
                data = ex.load_index()
                data['steps'][0].update(summary='old', completed_at='old',
                    error_message='old', failed_at='old', blocked_reason='old', blocked_at='old')
                ex.save_index(data)
                (ex.root / 'src/keep.txt').write_text('decoy')
                ex.save_marker({'stage': 'running'})
                original = ex.commit_meta
                def commit(label):
                    self.assertTrue(ex.marker_path.exists())
                    return original(label)
                with mock.patch.object(ex, 'commit_meta', side_effect=commit):
                    ex.confirm_step(0, status, 'new')
                expected = {f'phases/{PHASE}/index.json'}
                if status != 'completed':
                    expected.add('phases/index.json')
                self.assertEqual(self.commit_files(ex), expected)
                self.assertTrue(self.git(ex.root, 'log', '-1', '--format=%s').startswith(
                    b'chore: 7-sample'))
                item = ex.load_index()['steps'][0]
                pairs = {'completed': ('summary', 'completed_at'),
                         'error': ('error_message', 'failed_at'),
                         'blocked': ('blocked_reason', 'blocked_at')}
                for state, (key, stamp) in pairs.items():
                    if state == status:
                        self.assertEqual(item[key], 'new')
                        self.assertRegex(item[stamp], r'\+09:00$')
                    else:
                        self.assertNotIn(key, item)
                        self.assertNotIn(stamp, item)
                self.assertEqual(ex.changed_paths(), ['src/keep.txt'])
                self.assertFalse(ex.marker_path.exists())

    def test_recover_feat_done_chore_only(self):
        ex = self.fixture({'step0': {'files': {'src/keep.txt': 'new'}}})
        outcome = ex.attempt_unit('step0', 'task', ['src/'], ['true'])
        feat = ex.commit_feat('feat: 7-sample step0 alpha (#7)', outcome.pre_sha)
        recovered = self.make_executor(ex.root)
        calls = len(self.exec_calls())
        with mock.patch.object(recovered, 'rollback', side_effect=AssertionError('rollback')):
            recovered.recover()
        self.assertEqual(len(self.exec_calls()), calls)
        self.assertEqual(self.git(ex.root, 'rev-parse', 'HEAD~1').decode().strip(), feat)
        self.assertEqual(recovered.load_index()['steps'][0]['summary'], 'step0 output')
        self.assertEqual(recovered.load_index()['steps'][0]['status'], 'completed')
        self.assertEqual(self.commit_files(ex), {f'phases/{PHASE}/index.json'})
        self.assertFalse(recovered.marker_path.exists())

    def test_commit_failure_exits_1_keeps_marker(self):
        ex = self.fixture({'step0': {'files': {'src/keep.txt': 'new'}}})
        before = ex.head()
        hook = ex.root / '.git/hooks/pre-commit'
        hook.write_text('#!/bin/sh\nexit 1\n')
        hook.chmod(0o755)
        self.assertEqual(ex.run(), 1)
        self.assertEqual(ex.head(), before)
        self.assertEqual(ex.load_marker()['stage'], 'running')
        self.assertEqual((ex.root / 'src/keep.txt').read_text(), 'new')
        self.assertEqual(ex.load_index()['steps'][0]['status'], 'pending')

    def test_error_blocked_confirmed_by_chore(self):
        for status, code, count, key, stamp in (
                ('error', 1, 3, 'error_message', 'failed_at'),
                ('blocked', 2, 1, 'blocked_reason', 'blocked_at')):
            with self.subTest(status=status):
                ex = self.fixture({'step0': {'files': {'src/keep.txt': 'dirty'},
                    'result': {'status': status, key: 'reason'}}})
                before = ex.head()
                calls = len(self.exec_calls())
                self.assertEqual(ex.run(), code)
                self.assertEqual(len(self.exec_calls()) - calls, count)
                item = ex.load_index()['steps'][0]
                self.assertEqual(item['status'], status)
                self.assertIn('reason', item[key])
                self.assertRegex(item[stamp], r'\+09:00$')
                top = ex.load_top_index()['phases'][0]
                self.assertEqual(top['status'], status)
                self.assertRegex(top[stamp], r'\+09:00$')
                self.assertEqual(self.commit_files(ex),
                                 {f'phases/{PHASE}/index.json', 'phases/index.json'})
                self.assertEqual(self.git(ex.root, 'rev-list', '--count', f'{before}..HEAD').strip(), b'1')
                self.assertEqual(ex.changed_paths(), [])
                self.assertFalse(ex.marker_path.exists())

    def test_steps_order_skip_completed_and_resume_exhaustion(self):
        ex = self.fixture(steps=[{'name': 'alpha'}, {'name': 'beta'}])
        self.assertEqual(ex.run(), 0)
        self.assertEqual([s['summary'] for s in ex.load_index()['steps']],
                         ['step0 output', 'step1 output'])
        calls = len(self.exec_calls())
        ex.run_steps(ex.specs)
        self.assertEqual(len(self.exec_calls()), calls)
        ex = self.fixture()
        ex.save_marker({'unit': 'step0', 'k': execute.MAX_ATTEMPTS,
                        'pre_sha': ex.head(), 'stage': 'running', 'feat_sha': None, 'pgid': None})
        self.assertEqual(ex.run(), 1)
        self.assertEqual(len(self.exec_calls()), calls)
        self.assertIsNone(ex.resume)
        self.assertIn('소진', ex.load_index()['steps'][0]['error_message'])
        self.assertFalse(ex.marker_path.exists())

    def test_chore_failure_preserves_feat_done_for_recovery(self):
        ex = self.fixture()
        original = ex.commit_paths
        def fail_chore(paths, message):
            if message.startswith('chore:'):
                raise execute.HarnessExit(1, 'chore failed')
            return original(paths, message)
        with mock.patch.object(ex, 'commit_paths', side_effect=fail_chore):
            self.assertEqual(ex.run(), 1)
        self.assertEqual(ex.load_marker()['stage'], 'feat_done')
        self.make_executor(ex.root).recover()
        self.assertFalse(ex.marker_path.exists())
        self.assertEqual(ex.load_index()['steps'][0]['status'], 'completed')

    def test_recover_invalid_feat_result_leaves_state_untouched(self):
        for result in (None, {}, {'status': 'error', 'summary': 'bad'},
                       {'status': 'completed', 'summary': ''}):
            with self.subTest(result=result):
                ex = self.fixture()
                marker = {'unit': 'step0', 'k': 1, 'pre_sha': ex.head(),
                          'stage': 'feat_done', 'feat_sha': ex.head(), 'pgid': None}
                ex.save_marker(marker)
                if result is not None:
                    ex.run_dir.mkdir(parents=True, exist_ok=True)
                    execute.write_json_atomic(ex.result_path('step0'), result)
                before = ex.head()
                self.assert_exit(1, ex.recover)
                self.assertEqual(ex.head(), before)
                self.assertEqual(ex.load_marker(), marker)
                self.assertEqual(ex.changed_paths(), [])
                self.assertEqual(self.exec_calls(), [])

class IssueSyncTests(HarnessTestCase):
    def fixture(self, status="blocked"):
        ex = ScopedCommitTests.fixture(self, {'step0': {'result': {
            'status': status, 'blocked_reason' if status == 'blocked' else 'error_message':
            'human decision needed'}}})
        self.fake_bin('gh', r"""
mode = os.environ.get('GH_SCENARIO', 'ok')
if mode == 'timeout':
    import time
    time.sleep(2)
if mode == 'fail' or (mode == 'partial' and sys.argv[-1] == 'fail'):
    sys.exit(9)
if sys.argv[1:3] == ['issue', 'view']:
    print(os.environ.get('GH_LABELS', '{"labels": []}'))
""")
        return ex

    def test_blocked_swaps_labels_and_comments(self):
        ex = self.fixture()
        original = ex.gh
        def after_commit(*args):
            self.assertEqual(ex.load_index()['steps'][0]['status'], 'blocked')
            self.assertIn('step0 blocked', self.git(ex.root, 'log', '-1', '--format=%s').decode())
            self.assertEqual(ex.changed_paths(), [])
            return original(*args)
        with mock.patch.object(ex, 'gh', side_effect=after_commit):
            self.assertEqual(ex.run(), 2)
        calls = self.calls('gh')
        self.assertEqual(calls, [
            ['issue', 'edit', '7', '--remove-label', 'ready-for-agent',
             '--add-label', 'ready-for-human'],
            ['issue', 'comment', '7', '--body', 'blocked: human decision needed']])
        self.assertFalse((ex.run_dir / 'gh-pending.json').exists())

    def test_resume_restores_label_if_still_human(self):
        ex = self.fixture()
        for labels, edits in ((['ready-for-human', 'bug'], 1),
                              (['ready-for-agent'], 0), (['needs-info'], 0),
                              (['ready-for-human', 'ready-for-agent'], 0)):
            with self.subTest(labels=labels):
                os.environ['GH_LABELS'] = json.dumps({'labels': [{'name': n} for n in labels]})
                before = len(self.calls('gh'))
                ex.issue_resume()
                calls = self.calls('gh')[before:]
                self.assertEqual(calls[0], ['issue', 'view', '7', '--json', 'labels'])
                self.assertEqual(len(calls), 1 + edits)
                if edits:
                    self.assertEqual(calls[1], ['issue', 'edit', '7', '--remove-label',
                        'ready-for-human', '--add-label', 'ready-for-agent'])

    def test_gh_failure_saved_and_retried(self):
        ex = self.fixture()
        os.environ['GH_SCENARIO'] = 'fail'
        edit = ['gh', 'issue', 'edit', '7', '--remove-label', 'ready-for-agent',
                '--add-label', 'ready-for-human']
        comment = ['gh', 'issue', 'comment', '7', '--body', 'reason']
        self.assertFalse(ex.gh(*edit[1:]))
        self.assertFalse(ex.gh(*comment[1:]))
        self.assertEqual(self.calls('gh'), [edit[1:]] * 3 + [comment[1:]] * 3)
        path = ex.run_dir / 'gh-pending.json'
        self.assertEqual(json.loads(path.read_text()), [edit, comment])
        invalid = [['gh', 'issue', 'close', '7'],
                   ['gh', 'issue', 'comment', '8', '--body', 'wrong issue'],
                   ['gh', 'issue', 'edit', '7', '--remove-label', 'bug',
                    '--add-label', 'ready-for-human'],
                   ['gh', 'issue', 'comment', '7', '--body', 123],
                   'not a list', None, {'argv': comment}, comment + ['extra']]
        path.write_text(json.dumps([edit, *invalid, comment]))
        self.seed_state(ex, status='blocked')
        os.environ['GH_SCENARIO'] = 'ok'
        self.assertEqual(ex.run(), 2)
        self.assertEqual(self.calls('gh')[6:], [edit[1:], comment[1:]])
        self.assertFalse(path.exists())

    def test_gh_partial_success(self):
        ex = self.fixture()
        path = ex.run_dir / 'gh-pending.json'
        path.parent.mkdir(parents=True, exist_ok=True)
        good = ['gh', 'issue', 'comment', '7', '--body', 'ok']
        bad = ['gh', 'issue', 'comment', '7', '--body', 'fail']
        path.write_text(json.dumps([good, bad]))
        os.environ['GH_SCENARIO'] = 'partial'
        ex.retry_gh_pending()
        self.assertEqual(self.calls('gh'), [good[1:]] + [bad[1:]] * 3)
        self.assertEqual(json.loads(path.read_text()), [bad])
        ex.retry_gh_pending()
        self.assertEqual(json.loads(path.read_text()), [bad])

    def test_gh_failure_keeps_phase_result(self):
        for status, code in [('blocked', 2), ('error', 1)]:
            with self.subTest(status=status):
                ex = self.fixture(status)
                os.environ['GH_SCENARIO'] = 'fail'
                self.assertEqual(ex.run(), code)
                self.assertEqual(ex.load_index()['steps'][0]['status'], status)
                self.assertEqual(ex.load_top_index()['phases'][0]['status'], status)
                self.assertEqual(ex.changed_paths(), [])
                pending = json.loads((ex.run_dir / 'gh-pending.json').read_text())
                self.assertEqual(len(pending), 2 if status == 'blocked' else 1)
                self.assertIn('human decision needed', pending[-1][-1])
                if status == 'error':
                    self.assertIn('step0', pending[-1][-1])

    def test_gh_timeout_env_and_queue_write_failure(self):
        ex = self.fixture()
        self.assertEqual(ex.gh_timeout, 60)
        os.environ['GH_TOKEN'] = 'fixture-secret'
        self.fake_bin('gh', "assert os.environ['GH_TOKEN'] == 'fixture-secret'\n"
                      "assert Path.cwd() == Path(os.environ['GH_EXPECT_ROOT']).resolve()\n")
        os.environ['GH_EXPECT_ROOT'] = str(ex.root)
        self.assertTrue(ex.gh('issue', 'comment', '7', '--body', 'ok'))
        with mock.patch.object(execute.subprocess, 'run', side_effect=
                subprocess.TimeoutExpired(['gh'], 60)) as run:
            self.assertFalse(ex.gh('issue', 'comment', '7', '--body', 'timeout'))
            self.assertEqual(run.call_count, 3)
            self.assertEqual(run.call_args.kwargs['timeout'], 60)
            self.assertEqual(run.call_args.kwargs['env']['GH_TOKEN'], 'fixture-secret')
        with mock.patch.object(execute.subprocess, 'run', side_effect=OSError('missing')), \
                mock.patch.object(execute, 'write_json_atomic', side_effect=OSError('disk full')):
            self.assertFalse(ex.gh('issue', 'comment', '7', '--body', 'unavailable'))

    def test_invalid_queue_and_resume_view_failure(self):
        ex = self.fixture()
        path = ex.run_dir / 'gh-pending.json'
        path.parent.mkdir(parents=True, exist_ok=True)
        for raw in ('{}', 'null', 'broken json', '[null, 42, ["gh"]]'):
            path.write_text(raw)
            with mock.patch('sys.stderr') as warning:
                ex.retry_gh_pending()
                self.assertTrue(warning.write.called)
            self.assertFalse(path.exists())
        self.assertEqual(self.calls('gh'), [])
        for labels in ('broken', '{}', '{"labels": null}'):
            os.environ['GH_LABELS'] = labels
            ex.issue_resume()
        os.environ['GH_SCENARIO'] = 'fail'
        ex.issue_resume()
        self.assertTrue(all(args[1] == 'view' for args in self.calls('gh')))
        self.assertFalse(path.exists())

    def test_resume_run_hook_and_comment_truncation(self):
        ex = self.fixture()
        self.seed_state(ex, status='blocked')
        data = ex.load_index()
        data['steps'][0]['status'] = 'pending'
        data['steps'][0].pop('error_message')
        data['steps'][0].pop('failed_at')
        ex.save_index(data)
        os.environ['GH_LABELS'] = '{"labels": [{"name": "ready-for-human"}]}'
        with mock.patch.object(ex, 'run_steps') as steps, \
                mock.patch.object(ex, 'review_gate', return_value=0):
            self.assertEqual(ex.run(), 0)
            steps.assert_called_once()
        self.assertEqual([args[1] for args in self.calls('gh')], ['view', 'edit'])
        ex.issue_comment('가' * 60000)
        self.assertEqual(self.calls('gh')[-1][-1], '가' * 60000)
        ex.issue_comment('가' * 60001)
        body = self.calls('gh')[-1][-1]
        self.assertEqual(len(body), 60000)
        self.assertTrue(body.endswith('[본문 잘림]'))



class ReviewGateTests(HarnessTestCase):
    def fixture(self, scenarios=None, ac=None, review='pending'):
        ex = self.make_executor(self.make_repo(
            steps=[{'name': 'alpha', 'ac': ac or ['true']}],
            files={'.claude/commands/review.md': '---\ndescription: hidden metadata\n---\nUnique review body\n'}))
        ex.prepare()
        data = ex.load_index()
        data['steps'][0].update(status='completed', summary='alpha output',
                                completed_at=execute.now_kst())
        data['review']['status'] = review
        ex.save_index(data)
        if review == 'failed':
            ex.set_top_status('error')
        ex.commit_meta('fixture completed steps')
        os.environ['REVIEW_SCENARIOS'] = json.dumps(scenarios or {})
        self.fake_bin('gh', 'pass\n')
        self.fake_bin('codex', "print('[]') if 'mcp' in sys.argv else sys.exit(97)\n")
        for reviewer in ('claude', 'grok'):
            self.fake_bin(reviewer, r"""
import subprocess, time
name = Path(sys.argv[0]).name
log_dir = Path(os.environ['HARNESS_CALLS_DIR'])
count = len((log_dir / name).read_text().splitlines())
options = json.loads(os.environ['REVIEW_SCENARIOS']).get(name, ['passed'])
mode = options[min(count - 1, len(options) - 1)]
head = subprocess.check_output(['git', 'rev-parse', 'HEAD']).decode().strip()
with (log_dir / 'review-records').open('a') as log:
    log.write(json.dumps({'name': name, 'head': head, 'env': dict(os.environ),
                         'gh_empty': not list(Path(os.environ['GH_CONFIG_DIR']).iterdir())}) + '\n')
if mode in ('edit', 'commit'):
    Path('src/keep.txt').write_text('reviewer edit')
    Path('src/new.txt').write_text('reviewer new')
    if mode == 'commit':
        subprocess.run(['git', 'add', '--', 'src/keep.txt', 'src/new.txt'], check=True)
        subprocess.run(['git', 'commit', '-q', '-m', 'reviewer mutation'], check=True)
if mode == 'branch':
    subprocess.run(['git', 'checkout', '-q', 'main'], check=True)
if mode == 'detached':
    subprocess.run(['git', 'checkout', '-q', '--detach', 'HEAD'], check=True)
if mode == 'env':
    Path('.env').write_text('changed')
if mode == 'timeout':
    time.sleep(2)
text = 'Review body\nREVIEW_RESULT: ' + ('failed' if mode == 'failed' else 'passed')
if mode == 'missing':
    text = 'No verdict'
if mode == 'raw':
    print(text)
else:
    print(json.dumps({'result' if name == 'claude' else 'text': text}))
if mode == 'exit':
    sys.exit(9)
""")
        return ex

    def records(self):
        path = self.log_dir / 'review-records'
        return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []

    def review(self, ex, reviewer='claude'):
        end = ex.head()
        return ex.run_reviewer(reviewer, 1, end, f"{ex.load_index()['base_commit']}..{end}")

    def test_both_passed_completes_phase(self):
        ex = self.fixture()
        end = ex.head()
        self.assertEqual(ex.review_gate(ex.load_step_specs()), 0)
        self.assertEqual(ex.load_index()['review'], {'status': 'passed', 'end_sha': end, 'round': 1, 'fixes': 0})
        self.assertIn('completed_at', ex.load_index())
        top = ex.load_top_index()['phases'][0]
        self.assertEqual(top['status'], 'completed')
        self.assertIn('completed_at', top)
        self.assertEqual(ex.git('log', '-1', '--format=%s').stdout.strip(),
                         b'chore: 7-sample phase completed (#7)')
        self.assertNotEqual(ex.head(), end)
        self.assertEqual([(r['name'], r['head']) for r in self.records()],
                         [('claude', end), ('grok', end)])
        comments = self.calls('gh')
        self.assertEqual(len(comments), 3)
        self.assertTrue(all(args[:3] == ['issue', 'comment', '7'] for args in comments))
        self.assertIn('step0: alpha output', comments[0][-1])
        for comment in comments[1:]:
            self.assertIn('Review body\nREVIEW_RESULT: passed', comment[-1])
        self.assertEqual(ex.changed_paths(), [])

    def test_baseline_ac_failure_errors(self):
        ex = self.fixture(ac=['false'])
        self.assertEqual(ex.review_gate(ex.load_step_specs()), 1)
        self.assertEqual(self.records(), [])
        self.assertEqual(ex.load_top_index()['phases'][0]['status'], 'error')
        self.assertIn('step0', self.calls('gh')[0][-1])
        self.assertEqual(ex.load_index()['review']['status'], 'pending')

    def test_baseline_env_and_tree_mutation(self):
        for command in ('echo changed > .env', 'echo changed > src/keep.txt',
                        'git commit --allow-empty -qm ac-mutation'):
            ex = self.fixture(ac=[command])
            before = ex.head()
            (ex.root / '.env').write_bytes(b'original')
            self.assertEqual(ex.review_gate(ex.load_step_specs()), 1)
            self.assertEqual((ex.root / '.env').read_bytes(), b'original')
            self.assertEqual(ex.load_top_index()['phases'][0]['status'], 'error')
            if '.env' not in command:
                self.assertEqual((ex.root / 'src/keep.txt').read_text(), 'keep\n')
                self.assertEqual(ex.git('rev-parse', 'HEAD^').stdout.decode().strip(), before)
                self.assertTrue(ex.git('for-each-ref', 'refs/harness/').stdout)

    def test_review_git_metadata_change_and_reason(self):
        for target in ('.git/config', '.git/hooks/new-hook', '.git/info/new-info'):
            ex = self.fixture()
            self.fake_bin('claude', f"Path({target!r}).open('a').write('[core]\\nfsmonitor = false\\n')\n"
                          "print(json.dumps({'result': 'REVIEW_RESULT: passed'}))\n")
            with mock.patch.object(ex, 'rollback') as rollback:
                self.assertEqual(ex.review_gate(ex.load_step_specs()), 3)
                rollback.assert_not_called()
            self.assertEqual(ex.load_index()['review']['status'], 'unverifiable')
            body = (ex.run_dir / 'review-r1-claude.txt').read_text()
            self.assertIn('[executor] Git 설정 변경 감지·복원', body)
            self.assertIn(body, self.calls('gh')[-1][-1])
            self.assertEqual(self.calls('grok'), [])

    def test_reviewer_fsmonitor_restores_and_rerun_passes_prepare(self):
        ex = self.fixture()
        config = ex.root / '.git/config'
        before = config.read_bytes()
        canary = self.temp_dir / 'review-canary'
        hook = self.temp_dir / 'review-monitor'
        hook.write_text('#!/bin/sh\necho ran > ' + str(canary) + '\n')
        hook.chmod(0o755)
        payload = '\n[core]\nfsmonitor = ' + str(hook) + '\n'
        self.fake_bin('claude', f"Path('.git/config').open('a').write({payload!r})\n"
                      "print(json.dumps({'result': 'REVIEW_RESULT: passed'}))\n")
        self.assertEqual(ex.run(), 3)
        self.assertEqual(config.read_bytes(), before)
        self.assertEqual(ex.changed_paths(), [])
        self.assertEqual(ex.load_index()['review']['status'], 'unverifiable')
        self.assertFalse(canary.exists())
        ex._lock_file.close()
        self.fake_bin('claude', "print(json.dumps({'result': 'REVIEW_RESULT: passed'}))\n")
        self.assertEqual(self.make_executor(ex.root).run(), 0)
        self.assertEqual(len(self.calls('claude')), 2)
        self.assertFalse(canary.exists())

    def test_baseline_git_restoration_commits_indices(self):
        ex = self.fixture(ac=['git config core.fsmonitor false'])
        config = ex.root / '.git/config'
        before = config.read_bytes()
        self.assertEqual(ex.run(), 1)
        self.assertEqual(config.read_bytes(), before)
        self.assertEqual(ex.changed_paths(), [])
        ex._lock_file.close()
        resumed = self.make_executor(ex.root)
        with mock.patch.object(resumed, 'run_baseline', return_value=None):
            self.assertEqual(resumed.run(), 0)

    def test_baseline_restore_failure_leaves_indices_untouched(self):
        ex = self.fixture(ac=['git config core.fsmonitor false'])
        indices = (ex.index_path.read_bytes(), ex.top_index_path.read_bytes())
        with mock.patch.object(ex, 'restore_path', side_effect=OSError('restore failed')):
            self.assertEqual(ex.run(), 1)
        self.assertEqual((ex.index_path.read_bytes(), ex.top_index_path.read_bytes()), indices)
        self.assertTrue(ex.git_guard_path.exists())
        ex._lock_file.close()
        resumed = self.make_executor(ex.root)
        with mock.patch.object(resumed, 'recover') as recover:
            self.assertEqual(resumed.run(), 1)
            recover.assert_not_called()

    def test_reports_use_memory_despite_file_tampering(self):
        ex = self.fixture({'claude': ['failed']})
        self.assertEqual(self.review(ex), 'failed')
        (ex.run_dir / 'review-r1-claude.txt').write_text('FORGED')
        self.assertNotIn('FORGED', ex.review_reports(1))
        self.assertIn('REVIEW_RESULT: failed', ex.review_reports(1))

    def test_credential_helper_is_reset_after_parent_config(self):
        ex = self.fixture()
        helper = self.temp_dir / 'credential-helper'
        helper.write_text('#!/bin/sh\necho username=test\necho password=fake\n')
        helper.chmod(0o755)
        os.environ.update(GIT_CONFIG_COUNT='1', GIT_CONFIG_KEY_0='credential.helper',
                          GIT_CONFIG_VALUE_0=str(helper), GIT_TERMINAL_PROMPT='0')
        env = ex.child_env()
        self.assertEqual(env['GIT_CONFIG_COUNT'], '2')
        self.assertEqual(env['GIT_CONFIG_VALUE_0'], str(helper))
        self.assertEqual(env['GIT_CONFIG_KEY_1'], 'credential.helper')
        self.assertEqual(env['GIT_CONFIG_VALUE_1'], '')
        # credential fill never accesses a network; the parent helper succeeds, child cannot.
        request = b'protocol=https\nhost=example.invalid\n\n'
        parent = subprocess.run(['git', 'credential', 'fill'], cwd=ex.root,
                                input=request, capture_output=True)
        child = subprocess.run(['git', 'credential', 'fill'], cwd=ex.root, env=env,
                               input=request, capture_output=True)
        self.assertEqual(parent.returncode, 0)
        self.assertNotEqual(child.returncode, 0)
        self.assertNotIn(b'password=', child.stdout)

    def test_missing_verdict_retry_then_unverifiable(self):
        ex = self.fixture({'claude': ['missing']})
        self.assertEqual(ex.review_gate(ex.load_step_specs()), 3)
        self.assertEqual(len(self.calls('claude')), 2)
        self.assertEqual(len(self.calls('grok')), 1)
        self.assertEqual(ex.load_index()['review']['status'], 'unverifiable')
        os.environ['REVIEW_SCENARIOS'] = json.dumps({'claude': ['missing', 'passed']})
        (self.log_dir / 'claude').unlink()
        self.assertEqual(self.review(ex), 'passed')
        self.assertEqual(len(self.calls('claude')), 2)

    def test_reviewer_commit_reverted_unverifiable(self):
        ex = self.fixture({'claude': ['commit']})
        end = ex.head()
        self.assertEqual(ex.review_round(1, end), {'claude': 'unverifiable', 'grok': 'passed'})
        self.assertEqual(ex.head(), end)
        self.assertEqual(self.records()[-1]['head'], end)
        refs = ex.git('for-each-ref', '--format=%(refname)',
                      f'refs/harness/{PHASE}/review-r1-claude/').stdout
        self.assertTrue(refs.strip())
        for mode in ('branch', 'detached'):
            with self.subTest(mode=mode):
                other = self.fixture({'claude': [mode]})
                before = {b: other.git('rev-parse', b).stdout for b in ('main', other.branch)}
                self.assert_exit(1, self.review, other)
                self.assertEqual({b: other.git('rev-parse', b).stdout for b in before}, before)
                self.assertTrue(other.git('for-each-ref', '--format=%(refname)',
                                         f'refs/harness/{PHASE}/review-r1-claude/').stdout.strip())

    def test_reviewer_edit_reverted_unverifiable(self):
        ex = self.fixture({'grok': ['edit']})
        self.assertEqual(self.review(ex, 'grok'), 'unverifiable')
        self.assertEqual((ex.root / 'src/keep.txt').read_text(), 'keep\n')
        self.assertFalse((ex.root / 'src/new.txt').exists())
        self.assertEqual(ex.git('status', '--porcelain').stdout, b'')
        self.assertEqual(len(self.calls('grok')), 1)

    def test_reviewer_argv_and_env(self):
        ex = self.fixture()
        scope = f"{ex.load_index()['base_commit']}..{ex.head()}"
        expected = ['claude', '-p', '--setting-sources', 'project,local',
                    '--dangerously-skip-permissions', '--disallowedTools',
                    'Edit,Write,MultiEdit,NotebookEdit', '--strict-mcp-config',
                    '--output-format', 'json', f'/review {scope} {execute.REVIEW_CONTRACT}']
        self.assertEqual(ex.review_argv('claude', scope), expected)
        self.assertNotIn('--bare', expected)
        grok = ex.review_argv('grok', scope)
        self.assertEqual(grok[:2], ['grok', '-p'])
        self.assertEqual(grok[3:], ['--permission-mode', 'dontAsk', '--output-format', 'json'])
        for value in ('Unique review body', scope, 'REVIEW_RESULT: passed'):
            self.assertIn(value, grok[2])
        self.assertNotIn('hidden metadata', grok[2])
        self.assertNotIn('\n', execute.REVIEW_CONTRACT)
        os.environ.update(GH_TOKEN='fake', GITHUB_TOKEN='fake', SSH_AUTH_SOCK='fake',
                          ORCA_REVIEW='secret', BASH_ENV='unused', ENV='unused')
        self.assertEqual(ex.review_round(1, ex.head()), {'claude': 'passed', 'grok': 'passed'})
        self.assertEqual(self.calls('claude')[-1], expected[1:])
        self.assertEqual(self.calls('grok')[-1], grok[1:])
        for record in self.records():
            for key in ('GH_TOKEN', 'GITHUB_TOKEN', 'SSH_AUTH_SOCK', 'ORCA_REVIEW', 'BASH_ENV', 'ENV'):
                self.assertNotIn(key, record['env'])
            self.assertEqual(record['env']['GIT_CONFIG_KEY_0'], 'credential.helper')
            self.assertEqual(record['env']['GIT_CONFIG_VALUE_0'], '')
            self.assertTrue(record['gh_empty'])
            self.assertEqual(record['env']['PYTHONDONTWRITEBYTECODE'], '1')

    def test_rerun_completed_steps_starts_at_gate(self):
        ex = self.fixture(review='failed')
        self.assertEqual(ex.run(), 0)
        self.assertFalse([args for args in self.calls('codex') if args[0] == 'exec'])
        self.assertEqual(ex.load_index()['review']['status'], 'passed')
        self.assertEqual(len(self.calls('claude')), 1)
        self.assertEqual(len(self.calls('grok')), 1)
        head = ex.head()
        self.assertEqual(ex.run(), 0)
        self.assertEqual(ex.head(), head)
        self.assertEqual(len(self.calls('claude')), 1)
        self.assertEqual(len(self.calls('grok')), 1)

    def test_unverifiable_exits_3_no_fix(self):
        ex = self.fixture({'claude': ['missing'], 'grok': ['failed']})
        self.assertEqual(ex.run(), 3)
        self.assertEqual(ex.load_index()['review']['status'], 'unverifiable')
        self.assertEqual(self.calls('codex'), [])
        self.assertNotIn(b'fix:', ex.git('log', '--format=%s').stdout)
        self.assertEqual(ex.changed_paths(), [])
        self.assertEqual(len(self.calls('gh')), 2)

    def test_failed_reviews_keep_original_reports(self):
        ex = self.fixture({'claude': ['failed']})
        self.assertEqual(ex.review_gate(ex.load_step_specs()), 3)
        self.assertEqual(ex.load_index()['review']['status'], 'failed')
        self.assertEqual(len(self.calls('claude')), 1)
        self.assertEqual(ex.load_top_index()['phases'][0]['status'], 'error')
        self.assertIn('Review body\nREVIEW_RESULT: failed', self.calls('gh')[0][-1])

    def test_verdict_strict_last_line(self):
        for text, expected in [('', None), ('REVIEW_RESULT: passed\n\n', 'passed'),
                               ('report\n REVIEW_RESULT: failed \n', 'failed'),
                               ('REVIEW_RESULT: passed\nmore', None),
                               ('REVIEW_RESULT: passed extra', None),
                               ('REVIEW_RESULT: Passed', None)]:
            with self.subTest(text=text):
                self.assertEqual(execute.parse_verdict(text), expected)

    def test_reviewer_invalid_json_exit_timeout_and_missing_command(self):
        for mode in ('raw', 'exit', 'timeout'):
            with self.subTest(mode=mode):
                ex = self.fixture({'claude': [mode]})
                before = len(self.calls('claude'))
                ex.review_timeout = .05 if mode == 'timeout' else 5
                self.assertEqual(self.review(ex), 'unverifiable')
                self.assertEqual(len(self.calls('claude')) - before, 2)
                reason = {'raw': '판정 누락', 'exit': '비정상 종료', 'timeout': 'timeout'}[mode]
                self.assertIn(reason, ex.review_reports(1))
                self.assertIn('[executor]', (ex.run_dir / 'review-r1-claude.txt').read_text())
        ex = self.fixture()
        command = ex.root / '.claude/commands/review.md'
        command.write_text('---\ndescription: secret\n---\nReview $ARGUMENTS\n')
        prompt = ex.review_argv('grok', 'a..b')[2]
        self.assertIn('Review a..b', prompt)
        self.assertNotIn('$ARGUMENTS', prompt)
        self.assertNotIn('리뷰 범위:', prompt)
        command.unlink()
        ex.git('add', '--', '.claude/commands/review.md')
        ex.git('commit', '-q', '-m', 'missing command fixture')
        before = len(self.calls('grok'))
        self.assertEqual(self.review(ex, 'grok'), 'unverifiable')
        self.assertEqual(len(self.calls('grok')), before)

    def test_reviewer_preconditions_and_env_mutation(self):
        ex = self.fixture({'claude': ['env']})
        (ex.root / 'src/keep.txt').write_text('dirty')
        self.assert_exit(1, self.review, ex)
        self.assertEqual(self.calls('claude'), [])
        (ex.root / 'src/keep.txt').write_text('keep\n')
        self.assert_exit(1, ex.run_reviewer, 'claude', 1, 'wrong-sha', 'a..b')
        self.assertEqual(self.review(ex), 'unverifiable')
        self.assertEqual(len(self.calls('claude')), 1)
        self.assertTrue(ex.git('for-each-ref', '--format=%(refname)',
                               f'refs/harness/{PHASE}/review-r1-claude/').stdout.strip())


class FixLoopTests(HarnessTestCase):
    def fixture(self, reviews=None, blocked=None, push=False):
        ex = self.make_executor(self.make_repo(files={
            '.claude/commands/review.md': 'Review the changes.\n'}), push=push)
        os.environ['FIX_REVIEWS'] = json.dumps(reviews or {})
        os.environ['FIX_BLOCKED'] = blocked or ''
        self.fake_bin('gh', "print(json.dumps({'labels': [{'name': 'ready-for-human'}]}))\n")
        self.fake_bin('codex', r"""
if 'mcp' in sys.argv:
    print('[]')
    sys.exit(0)
last = Path(sys.argv[sys.argv.index('-o') + 1])
unit = last.name.removesuffix('-last.txt')
prompt = sys.stdin.read()
with (Path(os.environ['HARNESS_CALLS_DIR']) / 'prompts').open('a') as log:
    import subprocess
    marker = Path(subprocess.check_output(['git', 'rev-parse', '--git-path', 'harness/7-sample/attempt.json']).decode().strip())
    log.write(json.dumps({'unit': unit, 'prompt': prompt, 'k': json.loads(marker.read_text())['k']}) + '\n')
if unit == os.environ['FIX_BLOCKED']:
    result = {'status': 'blocked', 'blocked_reason': 'human decision'}
else:
    target = {'step0': 'alpha', 'step1': 'beta'}.get(unit, unit)
    Path('src/' + target + '.txt').write_text(unit)
    result = {'status': 'completed', 'summary': unit + ' output'}
last.with_name(unit + '-result.json').write_text(json.dumps(result))
""")
        for name in ('claude', 'grok'):
            self.fake_bin(name, r"""
name = Path(sys.argv[0]).name
count = len((Path(os.environ['HARNESS_CALLS_DIR']) / name).read_text().splitlines())
options = json.loads(os.environ['FIX_REVIEWS']).get(name, ['passed'])
verdict = options[min(count - 1, len(options) - 1)]
text = name + ' original report ' + str(count)
if verdict != 'missing':
    text += '\nREVIEW_RESULT: ' + verdict
print(json.dumps({'result' if name == 'claude' else 'text': text}))
""")
        return ex

    def units(self):
        path = self.log_dir / 'prompts'
        return [json.loads(line)['unit'] for line in path.read_text().splitlines()]

    def cli(self, ex, *args):
        return subprocess.run([sys.executable, str(Path(execute.__file__).resolve()), PHASE, *args],
                              cwd=ex.root, capture_output=True, text=True, timeout=60)

    def assert_state(self, ex, review, top):
        self.assertEqual(ex.load_index()['review']['status'], review)
        self.assertEqual(ex.load_top_index()['phases'][0]['status'], top)
        self.assertFalse(ex.marker_path.exists())

    def test_failed_review_fix_and_rereview(self):
        ex = self.fixture({'claude': ['failed', 'passed']})
        self.assertEqual(ex.run(), 0)
        self.assert_state(ex, 'passed', 'completed')
        self.assertEqual([len(self.calls(n)) for n in ('claude', 'grok')], [2, 2])
        self.assertEqual(self.units(), ['step0', 'step1', 'fix1'])
        prompts = [json.loads(line) for line in (self.log_dir / 'prompts').read_text().splitlines()]
        for name in ('claude', 'grok'):
            self.assertIn(name + ' original report 1', prompts[-1]['prompt'])
        self.assertIn('fix: 7-sample 리뷰 r1 반영 (#7)',
                      self.git(ex.root, 'log', '--format=%s').decode())

    def test_two_failed_rounds_exit_3(self):
        ex = self.fixture({'claude': ['failed']})
        self.assertEqual(ex.run(), 3)
        self.assert_state(ex, 'failed', 'error')
        self.assertEqual(self.units(), ['step0', 'step1', 'fix1', 'fix2'])
        self.assertEqual([len(self.calls(n)) for n in ('claude', 'grok')], [3, 3])
        self.assertEqual(ex.load_index()['review']['round'], 3)
        comments = str(self.calls('gh'))
        self.assertIn('claude original report 3', comments)
        self.assertIn('grok original report 3', comments)

    def test_fix_blocked_exits_2(self):
        ex = self.fixture({'claude': ['failed']}, blocked='fix1')
        self.assertEqual(ex.run(), 2)
        self.assert_state(ex, 'blocked', 'blocked')
        data = ex.load_index()
        self.assertEqual(data['review']['blocked_reason'], 'human decision')
        self.assertTrue(any(args[:2] == ['issue', 'edit'] for args in self.calls('gh')))
        data['review']['status'] = 'pending'
        del data['review']['blocked_reason']
        ex.save_index(data)
        os.environ['FIX_REVIEWS'] = '{}'
        count = len(self.calls('claude'))
        ex._lock_file.close()
        self.assertEqual(self.make_executor(ex.root).run(), 0)
        self.assertGreater(len(self.calls('claude')), count)
        self.assert_state(ex, 'passed', 'completed')

    def test_fix2_blocked_resume_counts_completed_fixes_only(self):
        ex = self.fixture({'claude': ['failed']}, blocked='fix2')
        self.assertEqual(ex.run(), 2)
        self.assertEqual(ex.load_index()['review']['fixes'], 1)
        data = ex.load_index()
        data['review']['status'] = 'pending'
        data['review'].pop('blocked_reason')
        ex.save_index(data)
        os.environ['FIX_BLOCKED'] = ''
        ex._lock_file.close()
        self.assertEqual(self.make_executor(ex.root).run(), 3)
        self.assertEqual(self.units(), ['step0', 'step1', 'fix1', 'fix2', 'fix3'])
        self.assertEqual(ex.load_index()['review']['fixes'], 0)
        self.assertEqual(ex.changed_paths(), [])

    def test_fix_spawn_failure_does_not_refresh_budget(self):
        ex = self.fixture({'claude': ['failed']})
        original = ex.run_fix
        def fix(round_no, *args, **kw):
            if round_no == 2:
                raise OSError('preflight failed before spawn')
            return original(round_no, *args, **kw)
        with mock.patch.object(ex, 'run_fix', side_effect=fix):
            self.assertEqual(ex.run(), 1)
        self.assertEqual(ex.load_index()['review']['fixes'], 1)
        self.assertEqual(ex.changed_paths(), [])
        ex._lock_file.close()
        self.assertEqual(self.make_executor(ex.root).run(), 3)
        self.assertEqual(self.units(), ['step0', 'step1', 'fix1', 'fix3'])
        self.assertEqual(ex.load_index()['review']['fixes'], 0)

    def test_fix_git_error_is_committed_and_exits_1(self):
        ex = self.fixture({'claude': ['failed']})
        original = ex.run_codex
        def session(unit, *args, **kw):
            child = original(unit, *args, **kw)
            if unit.startswith('fix'):
                ex.git('config', 'core.fsmonitor', 'false')
            return child
        with mock.patch.object(ex, 'run_codex', side_effect=session):
            self.assertEqual(ex.run(), 1)
        self.assertEqual(self.units(), ['step0', 'step1', 'fix1'])
        self.assertEqual(ex.changed_paths(), [])
        self.assertFalse(ex.marker_path.exists())
        self.assertEqual(ex.load_index()['review']['fixes'], 0)
        ex._lock_file.close()
        os.environ['FIX_REVIEWS'] = '{}'
        self.assertEqual(self.make_executor(ex.root).run(), 0)

    def test_push_no_force(self):
        ex = self.fixture(push=True)
        remote = self.temp_dir / 'remote.git'
        self.git(self.temp_dir, 'init', '--bare', str(remote))
        self.git(ex.root, 'remote', 'add', 'origin', str(remote))
        os.environ['GITHUB_TOKEN'] = 'push-only-credential'
        original = ex.git
        pushes = []
        def record(*args, **kwargs):
            if args[0] == 'push':
                pushes.append((args, kwargs, os.environ.get('GITHUB_TOKEN')))
            return original(*args, **kwargs)
        with mock.patch.object(ex, 'git', side_effect=record):
            self.assertEqual(ex.run(), 0)
        self.assertEqual(pushes, [(('push', '-u', 'origin', 'feat-7-sample'),
                                  {'check': False}, 'push-only-credential')])
        self.assertEqual(self.git(remote, 'rev-parse', 'refs/heads/feat-7-sample').decode().strip(), ex.head())

    def test_push_failure_exits_1(self):
        ex = self.fixture(push=True)
        self.git(ex.root, 'remote', 'add', 'origin', str(self.temp_dir / 'absent.git'))
        self.assertEqual(ex.run(), 1)
        self.assert_state(ex, 'passed', 'completed')
        counts = [len(self.calls(n)) for n in ('codex', 'claude', 'grok')]
        head = ex.head()
        ex._lock_file.close()
        again = self.make_executor(ex.root, push=True)
        with mock.patch.object(again, 'push_branch', wraps=again.push_branch) as push:
            self.assertEqual(again.run(), 1)
            push.assert_called_once_with()
        again._lock_file.close()
        result = self.cli(ex, '--push')
        self.assertEqual(result.returncode, 1)
        self.assertIn('absent.git', result.stderr)
        self.assertEqual([len(self.calls(n)) for n in ('codex', 'claude', 'grok')], counts)
        self.assertEqual(ex.head(), head)
        self.assert_state(ex, 'passed', 'completed')

    def test_e2e_passed_exit_0(self):
        ex = self.fixture()
        result = self.cli(ex)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assert_state(ex, 'passed', 'completed')
        self.assertEqual([s['status'] for s in ex.load_index()['steps']], ['completed'] * 2)
        subjects = self.git(ex.root, 'log', '--format=%s').decode().splitlines()
        self.assertEqual(sum(s.startswith('feat:') for s in subjects), 2)
        self.assertTrue(any(s.startswith('chore:') for s in subjects))
        self.assertEqual(self.git(ex.root, 'status', '--porcelain'), b'')
        counts = [len(self.calls(n)) for n in ('codex', 'claude', 'grok')]
        self.assertEqual(self.cli(ex).returncode, 0)
        self.assertEqual([len(self.calls(n)) for n in ('codex', 'claude', 'grok')], counts)

    def test_e2e_blocked_exit_2(self):
        ex = self.fixture(blocked='step1')
        result = self.cli(ex)
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertEqual([s['status'] for s in ex.load_index()['steps']], ['completed', 'blocked'])
        self.assertEqual(ex.load_top_index()['phases'][0]['status'], 'blocked')
        self.assertTrue(any(args[:2] == ['issue', 'edit'] for args in self.calls('gh')))
        self.assertFalse(self.calls('claude'))

    def test_e2e_unverifiable_exit_3_no_fix_commit(self):
        ex = self.fixture({'grok': ['missing']})
        result = self.cli(ex)
        self.assertEqual(result.returncode, 3, result.stderr)
        self.assert_state(ex, 'unverifiable', 'error')
        self.assertEqual(self.units(), ['step0', 'step1'])
        self.assertEqual(len(self.calls('grok')), 2)
        self.assertNotIn('fix:', self.git(ex.root, 'log', '--format=%s').decode())

    def seed_resume(self, ex, k=1, missing=False):
        ex.prepare()
        for unit, file in [('step0', 'alpha'), ('step1', 'beta')]:
            (ex.root / f'src/{file}.txt').write_text(unit)
        ex.commit_paths(['src/alpha.txt', 'src/beta.txt'], 'fixture outputs')
        data = ex.load_index()
        for step in data['steps']:
            step.update(status='completed', summary='output')
        reviewed = ex.head()
        data['review'] = {'status': 'failed', 'round': 1, 'end_sha': reviewed}
        ex.save_index(data)
        ex.commit_meta('review failed')
        ex.run_dir.mkdir(parents=True, exist_ok=True)
        for name in ('claude', 'grok'):
            if not missing or name == 'claude':
                (ex.run_dir / f'review-r1-{name}.txt').write_text(name + ' saved report')
        ex.save_marker({'unit': 'fix1', 'k': k, 'stage': 'running', 'pre_sha': ex.head(),
                        'feat_sha': None, 'pgid': None})
        return reviewed

    def test_fix_running_recovery_uses_recorded_scope(self):
        ex = self.fixture({'claude': ['failed', 'passed']})
        self.seed_resume(ex)
        reviewed = ex.head()
        self.assertEqual(ex.run(), 0)
        self.assertEqual(self.units(), ['fix1'])
        prompt = json.loads((self.log_dir / 'prompts').read_text().splitlines()[0])['prompt']
        self.assertIn(ex.load_index()['base_commit'] + '..' + reviewed, prompt)
        self.assertNotIn('saved report', prompt)
        self.assertIn('claude original report 1', prompt)
        record = json.loads((self.log_dir / 'prompts').read_text().splitlines()[0])
        self.assertEqual(record['k'], 2)
        self.assertEqual(len(self.calls('claude')), 2)
        self.assert_state(ex, 'passed', 'completed')

    def test_fix2_crash_resume_preserves_round_budget(self):
        ex = self.fixture({'claude': ['failed']})
        self.seed_resume(ex)
        data = ex.load_index()
        data['review']['round'] = 2
        data['review']['fixes'] = 1
        ex.save_index(data)
        ex.commit_meta('second review fixture')
        ex.save_marker({'unit': 'fix2', 'k': 1, 'stage': 'running', 'pre_sha': ex.head(),
                        'feat_sha': None, 'pgid': None})
        resumed = self.make_executor(ex.root)
        self.assertEqual(resumed.run(), 3)
        records = [json.loads(line) for line in (self.log_dir / 'prompts').read_text().splitlines()]
        self.assertEqual([(r['unit'], r['k']) for r in records], [('fix2', 2)])
        self.assertEqual(resumed.load_index()['review']['round'], 3)
        self.assertNotIn('fix3', self.units())

    def test_fix2_completed_crash_resume_has_no_new_budget(self):
        ex = self.fixture({'claude': ['failed']})
        self.seed_resume(ex)
        ex.clear_marker()
        data = ex.load_index()
        data['review'].update(status='pending', round=2, fixes=2)
        ex.save_index(data)
        ex.commit_meta('fix2 completed fixture')
        resumed = self.make_executor(ex.root)
        self.assertEqual(resumed.run(), 3)
        self.assertEqual(self.calls('codex'), [])
        self.assertEqual(resumed.load_index()['review']['round'], 3)
        # A new invocation after finalized failure receives a fresh two-fix budget.
        resumed._lock_file.close()
        self.assertEqual(self.make_executor(ex.root).run(), 3)
        self.assertEqual(self.units(), ['fix1', 'fix2'])

    def test_fix_resume_exhausted_and_missing_reports(self):
        for exhausted in (True, False):
            with self.subTest(exhausted=exhausted):
                ex = self.fixture()
                self.seed_resume(ex, k=3 if exhausted else 1, missing=True)
                self.assertEqual(ex.run(), 3 if exhausted else 0)
                self.assertFalse(ex.marker_path.exists())
                self.assertFalse(self.calls('codex'))
                self.assertEqual(ex.load_index()['review']['status'], 'failed' if exhausted else 'passed')

    def test_fix_feat_done_recovery_only_commits_metadata(self):
        ex = self.fixture()
        self.seed_resume(ex)
        (ex.root / 'src/fix1.txt').write_text('fixed')
        execute.write_json_atomic(ex.result_path('fix1'), {'status': 'completed', 'summary': 'fixed'})
        ex.commit_feat('fix: interrupted', ex.head())
        self.assertEqual(ex.run(), 0)
        self.assertFalse(self.calls('codex'))
        self.assert_state(ex, 'passed', 'completed')
        self.assertEqual((ex.root / 'src/fix1.txt').read_text(), 'fixed')

    def test_fix_feat_done_after_saved_index_counts_once(self):
        ex = self.fixture()
        self.seed_resume(ex)
        (ex.root / 'src/fix1.txt').write_text('fixed')
        execute.write_json_atomic(ex.result_path('fix1'),
                                  {'status': 'completed', 'summary': 'fixed'})
        ex.commit_feat('fix: interrupted after index save', ex.head())
        data = ex.load_index()
        data['review'].update(status='pending', fixes=1)
        ex.save_index(data)
        recovered = self.make_executor(ex.root)
        recovered.recover()
        self.assertEqual(recovered.load_index()['review']['fixes'], 1)
        self.assertFalse(recovered.marker_path.exists())
        self.assertEqual(recovered.changed_paths(), [])

    def test_fix_attempt_exhaustion_clears_marker(self):
        ex = self.fixture({'claude': ['failed']})
        original = ex.run_fix
        def fail(round_no, specs, scope, **kwargs):
            self.fake_bin('codex', "print('[]') if 'mcp' in sys.argv else sys.exit(9)\n")
            return original(round_no, specs, scope, **kwargs)
        with mock.patch.object(ex, 'run_fix', side_effect=fail):
            self.assertEqual(ex.run(), 3)
        self.assert_state(ex, 'failed', 'error')
        self.assertEqual(sum('exec' in args for args in self.calls('codex')), 5)
        self.assertIn('수정 실패', str(self.calls('gh')))


if __name__ == "__main__":
    program = unittest.main(exit=False)
    sys.exit(0 if program.result.testsRun and program.result.wasSuccessful() else 1)
