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
        with mock.patch.object(executor, 'run_steps') as run_steps:
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
                mock.patch.object(ex, 'run_steps', side_effect=lambda specs: record('steps')):
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
        out = self.attempt(ex, start_k=3)
        self.assertEqual(out.status, 'error')
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
        with mock.patch.object(ex, 'run_steps') as steps:
            self.assertEqual(ex.run(), 0)
            steps.assert_called_once()
        self.assertEqual([args[1] for args in self.calls('gh')], ['view', 'edit'])
        ex.issue_comment('가' * 60000)
        self.assertEqual(self.calls('gh')[-1][-1], '가' * 60000)
        ex.issue_comment('가' * 60001)
        body = self.calls('gh')[-1][-1]
        self.assertEqual(len(body), 60000)
        self.assertTrue(body.endswith('[본문 잘림]'))


if __name__ == "__main__":
    program = unittest.main(exit=False)
    sys.exit(0 if program.result.testsRun and program.result.wasSuccessful() else 1)
