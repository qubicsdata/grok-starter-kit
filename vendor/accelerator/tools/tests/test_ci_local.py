#!/usr/bin/env python3
"""Harness tests for scripts/ci-local.sh (post-merge review 2026-10-17, findings A-1..A-6).

Each test builds a small throwaway "accelerator repo" (a git repo with fake tools/run-unit-tests.py,
tools/validate.sh, tools/gen-readme.py, tools/gen-registry.py and a copy of the real scripts/ci-local.sh)
and runs the real script against it. The fake generators rewrite README.md / registry.json in place exactly
like the real ones, so the tests prove the gate never writes the checkout under test. The fake unit-test
runner can change the checkout during the run (FAKE_TOUCH, FAKE_CORRUPT, FAKE_COMMIT) to exercise the
clean-tree stage. Logs go to a temporary CI_LOCAL_LOG_DIR; no network; nothing outside temp dirs is written.
Run: python3 tools/tests/test_ci_local.py  (also picked up by tools/run-unit-tests.py).
"""
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "ci-local.sh"

FAKE_UNIT = r'''import json, os, subprocess, sys
from pathlib import Path
out = os.environ.get("FAKE_ENV_OUT")
if out:
    Path(out).write_text(json.dumps({
        "exe": sys.executable, "cwd": os.getcwd(),
        "PYTHONDONTWRITEBYTECODE": os.environ.get("PYTHONDONTWRITEBYTECODE"),
        "GIT_OPTIONAL_LOCKS": os.environ.get("GIT_OPTIONAL_LOCKS")}))
if os.environ.get("FAKE_TOUCH"):
    Path(os.environ["FAKE_TOUCH"]).write_text("x")
if os.environ.get("FAKE_CORRUPT"):
    Path(os.environ["FAKE_CORRUPT"]).write_bytes(b"garbage")
if os.environ.get("FAKE_COMMIT"):
    subprocess.run(["git", "-C", os.environ["FAKE_COMMIT"], "commit", "-q", "--allow-empty", "-m", "moved"],
                   check=True)
print("run-unit-tests: 1/1 test file(s) passed")
'''
FAKE_GEN_REGISTRY = r'''import json
from pathlib import Path
root = Path(__file__).resolve().parent.parent
(root / "registry.json").write_text(json.dumps([{"name": "alpha"}], indent=2) + "\n")
print("registry.json written (1 plugins)")
'''
FAKE_GEN_README = r'''import json
from pathlib import Path
root = Path(__file__).resolve().parent.parent
names = [e["name"] for e in json.loads((root / "registry.json").read_text())]
(root / "README.md").write_text("# fleet\n\n" + "".join("- %s\n" % n for n in names))
print("README.md written")
'''
FAKE_VALIDATE = r'''#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python3 tools/gen-registry.py
git diff --exit-code registry.json
python3 tools/gen-readme.py > /dev/null
git diff --exit-code README.md
echo "GATE: PASS"
'''
GENERATED_README = "# fleet\n\n- alpha\n"
GENERATED_REGISTRY = json.dumps([{"name": "alpha"}], indent=2) + "\n"


def _env(home):
    return {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": str(home), "LANG": "C.UTF-8",
        "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_AUTHOR_NAME": "Test", "GIT_AUTHOR_EMAIL": "test@example.invalid",
        "GIT_COMMITTER_NAME": "Test", "GIT_COMMITTER_EMAIL": "test@example.invalid",
    }


def git(cwd, *args):
    return subprocess.run(["git", "-C", str(cwd)] + list(args), check=True, capture_output=True, text=True,
                          env=_env(Path(cwd)))


def make_fake_repo(path, git_init=True, readme=GENERATED_README):
    (path / "tools" / "tests").mkdir(parents=True)
    (path / "scripts").mkdir()
    (path / "tools" / "run-unit-tests.py").write_text(FAKE_UNIT)
    (path / "tools" / "gen-registry.py").write_text(FAKE_GEN_REGISTRY)
    (path / "tools" / "gen-readme.py").write_text(FAKE_GEN_README)
    (path / "tools" / "validate.sh").write_text(FAKE_VALIDATE)
    shutil.copy2(str(SCRIPT), str(path / "scripts" / "ci-local.sh"))
    (path / "README.md").write_text(readme)
    (path / "registry.json").write_text(GENERATED_REGISTRY)
    (path / ".gitignore").write_text("__pycache__/\n")
    if git_init:
        git(path, "init", "-q")
        git(path, "add", "-A")
        git(path, "commit", "-q", "-m", "init")
    return path


class CiLocalHarness(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="ci-local-test-")).resolve()
        self.addCleanup(shutil.rmtree, str(self.tmp), True)
        self.home = self.tmp / "home"
        self.home.mkdir()
        self.scratch = self.tmp / "scratch"   # TMPDIR for the gate: must be empty again after every run
        self.scratch.mkdir()
        self.logdir = self.tmp / "logs"
        self.fake = make_fake_repo(self.tmp / "fake")

    def run_gate(self, *args, script=SCRIPT, cwd=None, extra_env=None, logdir=None):
        env = _env(self.home)
        env["CI_LOCAL_LOG_DIR"] = str(logdir if logdir is not None else self.logdir)
        env["TMPDIR"] = str(self.scratch)
        env.update(extra_env or {})
        res = subprocess.run(["bash", str(script)] + list(args), cwd=str(cwd or self.tmp), env=env,
                             capture_output=True, text=True, timeout=120)
        res.out = res.stdout + res.stderr
        return res

    def assert_refused(self, res, needle):
        self.assertEqual(res.returncode, 2, res.out)
        self.assertNotIn("PASSED", res.out)
        self.assertIn(needle, res.out)

    def assert_gate_failed(self, res, needle, stage="clean tree"):
        self.assertEqual(res.returncode, 1, res.out)
        self.assertNotIn("ci-local PASSED", res.out)
        self.assertIn("ci-local FAILED", res.out)
        self.assertIn("=== [%s] FAILED" % stage, res.out)
        self.assertIn(needle, res.out)


class RootTest(CiLocalHarness):
    """A-2: a bad or missing --root fails closed (exit 2), never tests $PWD."""

    def test_good_root_passes(self):
        res = self.run_gate("--root", str(self.fake))
        self.assertEqual(res.returncode, 0, res.out)
        self.assertIn("ci-local PASSED", res.out)
        self.assertIn("root=%s " % self.fake, res.out)

    def test_missing_root_argument(self):
        self.assert_refused(self.run_gate("--root", cwd=self.fake), "--root needs a directory")

    def test_empty_root_argument(self):
        self.assert_refused(self.run_gate("--root", "", cwd=self.fake), "--root needs a directory")

    def test_nonexistent_root(self):
        self.assert_refused(self.run_gate("--root", str(self.tmp / "nope"), cwd=self.fake), "not a directory")

    def test_root_is_a_file(self):
        self.assert_refused(self.run_gate("--root", str(self.fake / "README.md"), cwd=self.fake),
                            "not a directory")

    def test_root_is_a_subdirectory(self):
        self.assert_refused(self.run_gate("--root", str(self.fake / "tools"), cwd=self.fake),
                            "not the top of a git work tree")

    def test_root_is_not_a_git_repo(self):
        plain = make_fake_repo(self.tmp / "plain", git_init=False)
        self.assert_refused(self.run_gate("--root", str(plain), cwd=self.fake), "not the top of a git work tree")

    def test_root_is_another_repo(self):
        other = self.tmp / "other"
        other.mkdir()
        git(other, "init", "-q")
        (other / "f").write_text("x")
        git(other, "add", "-A")
        git(other, "commit", "-q", "-m", "init")
        self.assert_refused(self.run_gate("--root", str(other), cwd=self.fake),
                            "does not have the accelerator layout")

    def test_default_root_is_the_scripts_repo(self):
        res = self.run_gate(script=self.fake / "scripts" / "ci-local.sh", cwd=self.tmp)
        self.assertEqual(res.returncode, 0, res.out)
        self.assertIn("root=%s " % self.fake, res.out)

    def test_default_root_outside_a_repo_fails(self):
        plain = make_fake_repo(self.tmp / "plain", git_init=False)
        self.assert_refused(self.run_gate(script=plain / "scripts" / "ci-local.sh", cwd=self.fake),
                            "not the top of a git work tree")

    def test_unknown_option(self):
        self.assert_refused(self.run_gate("--bogus", cwd=self.fake), "unknown option")


class NoWriteTest(CiLocalHarness):
    """A-1: the gate never writes the checkout under test; generators run only in a throwaway clone."""

    def test_uncommitted_readme_edit_survives(self):
        (self.fake / "README.md").write_text("my uncommitted edit\n")
        for args in ([], ["--quick"]):
            res = self.run_gate("--root", str(self.fake), *args)
            self.assert_gate_failed(res, "README.md")
            self.assertEqual((self.fake / "README.md").read_text(), "my uncommitted edit\n")

    def test_uncommitted_registry_edit_survives(self):
        (self.fake / "registry.json").write_text('[{"name": "mine"}]\n')
        res = self.run_gate("--root", str(self.fake))
        self.assert_gate_failed(res, "registry.json")
        self.assertEqual((self.fake / "registry.json").read_text(), '[{"name": "mine"}]\n')

    def test_stale_committed_readme_fails_without_touching_tree(self):
        stale = make_fake_repo(self.tmp / "stale", readme="# stale\n")
        res = self.run_gate("--root", str(stale), "--quick")
        self.assert_gate_failed(res, "README.md", stage="generated files match HEAD")
        self.assertEqual((stale / "README.md").read_text(), "# stale\n")
        self.assertEqual(git(stale, "status", "--porcelain", "--untracked-files=all").stdout, "")
        self.assertNotIn("=== [clean tree] FAILED", res.out)

    def test_stages_run_outside_the_checkout_with_hardened_env(self):
        envout = self.tmp / "env.json"
        res = self.run_gate("--root", str(self.fake), extra_env={"FAKE_ENV_OUT": str(envout)})
        self.assertEqual(res.returncode, 0, res.out)
        seen = json.loads(envout.read_text())
        self.assertEqual(seen["exe"], "/usr/bin/python3")
        self.assertEqual(seen["PYTHONDONTWRITEBYTECODE"], "1")
        self.assertEqual(seen["GIT_OPTIONAL_LOCKS"], "0")
        self.assertFalse(Path(seen["cwd"]).resolve() == self.fake, seen)

    def test_throwaway_clone_removed(self):
        res = self.run_gate("--root", str(self.fake))
        self.assertEqual(res.returncode, 0, res.out)
        self.assertEqual(list(self.scratch.iterdir()), [])


class CleanTreeTest(CiLocalHarness):
    """A-3: dirty before (untracked included), changed during, HEAD moved, or `git status` failing all fail."""

    def test_untracked_file_before(self):
        (self.fake / "stray.txt").write_text("x")
        self.assert_gate_failed(self.run_gate("--root", str(self.fake)), "stray.txt")

    def test_untracked_file_before_quick(self):
        (self.fake / "stray.txt").write_text("x")
        self.assert_gate_failed(self.run_gate("--root", str(self.fake), "--quick"), "stray.txt")

    def test_untracked_file_in_new_dir_before(self):
        (self.fake / "newdir").mkdir()
        (self.fake / "newdir" / "deep.txt").write_text("x")
        self.assert_gate_failed(self.run_gate("--root", str(self.fake)), "newdir/deep.txt")

    def test_change_during_run(self):
        res = self.run_gate("--root", str(self.fake),
                            extra_env={"FAKE_TOUCH": str(self.fake / "made-during-run.txt")})
        self.assert_gate_failed(res, "made-during-run.txt")

    def test_head_moved_during_run(self):
        res = self.run_gate("--root", str(self.fake), extra_env={"FAKE_COMMIT": str(self.fake)})
        self.assert_gate_failed(res, "HEAD moved during the gate")

    def test_git_status_error_before(self):
        (self.fake / ".git" / "index").write_bytes(b"garbage")
        res = self.run_gate("--root", str(self.fake))
        self.assertIn(res.returncode, (1, 2), res.out)
        self.assertNotIn("ci-local PASSED", res.out)

    def test_git_status_error_during_run(self):
        res = self.run_gate("--root", str(self.fake), extra_env={"FAKE_CORRUPT": str(self.fake / ".git" / "index")})
        self.assert_gate_failed(res, "git status failed")


class LogAndSummaryTest(CiLocalHarness):
    """A-4, A-5, A-6: JSON summary, log dir safety, setup errors."""

    def summary(self):
        files = sorted(self.logdir.glob("default-*.summary.json"))
        self.assertEqual(len(files), 1, files)
        return json.loads(files[0].read_text())

    def test_summary_json_escapes_root(self):
        odd = make_fake_repo(self.tmp / 'we"ird\\dir')
        res = self.run_gate("--root", str(odd))
        self.assertEqual(res.returncode, 0, res.out)
        data = self.summary()
        self.assertEqual(data["root"], str(odd))
        self.assertEqual(data["result"], "pass")
        self.assertEqual([s["stage"] for s in data["stages"]],
                         ["trusted interpreter", "unit tests (tools/run-unit-tests.py)",
                          "fleet gate (tools/validate.sh)", "generated files match HEAD", "clean tree"])

    def test_log_files_private(self):
        res = self.run_gate("--root", str(self.fake))
        self.assertEqual(res.returncode, 0, res.out)
        self.assertEqual(stat.S_IMODE(self.logdir.stat().st_mode), 0o700)
        logs = [p for p in self.logdir.iterdir() if not p.is_symlink()]
        self.assertEqual(len(logs), 2, logs)
        for p in logs:
            self.assertEqual(stat.S_IMODE(p.stat().st_mode), 0o600, p)
        self.assertTrue((self.logdir / "latest-default.log").is_symlink())

    def test_symlinked_log_dir_refused(self):
        real = self.tmp / "real-logs"
        real.mkdir(mode=0o700)
        self.logdir.symlink_to(real)
        self.assert_refused(self.run_gate("--root", str(self.fake)), "symlink")
        self.assertEqual(list(real.iterdir()), [])

    def test_symlinked_log_dir_with_trailing_slash_refused(self):
        real = self.tmp / "real-logs"
        real.mkdir(mode=0o700)
        self.logdir.symlink_to(real)
        self.assert_refused(self.run_gate("--root", str(self.fake), logdir=str(self.logdir) + "//"), "symlink")
        self.assertEqual(list(real.iterdir()), [])

    def test_group_writable_log_dir_refused(self):
        self.logdir.mkdir()
        os.chmod(str(self.logdir), 0o770)
        self.assert_refused(self.run_gate("--root", str(self.fake)), "writable by group/others")
        self.assertEqual(list(self.logdir.iterdir()), [])

    def test_foreign_owned_log_dir_refused(self):
        if os.geteuid() == 0:
            foreign = self.tmp / "foreign"
            foreign.mkdir(mode=0o755)
            os.chown(str(foreign), 65534, 65534)
        else:
            foreign = Path("/usr")   # root-owned, 0755: refused before anything is written
            if foreign.stat().st_uid == os.geteuid() or foreign.stat().st_mode & 0o022:
                self.skipTest("no foreign-owned, non-shared directory available")
        self.assert_refused(self.run_gate("--root", str(self.fake), logdir=str(foreign)), "not owned by")

    def test_log_dir_is_a_file_is_setup_error(self):
        self.logdir.write_text("not a dir")
        self.assert_refused(self.run_gate("--root", str(self.fake)), "not a directory")

    def test_planted_log_symlink_not_followed(self):
        self.logdir.mkdir(mode=0o700)
        sha = git(self.fake, "rev-parse", "HEAD").stdout.strip()
        victim = self.tmp / "victim.txt"
        victim.write_text("keep\n")
        (self.logdir / ("default-%s.log" % sha[:12])).symlink_to(victim)
        (self.logdir / ("default-%s.summary.json" % sha[:12])).symlink_to(victim)
        res = self.run_gate("--root", str(self.fake))
        self.assertEqual(res.returncode, 0, res.out)
        self.assertEqual(victim.read_text(), "keep\n")
        self.assertFalse((self.logdir / ("default-%s.log" % sha[:12])).is_symlink())


if __name__ == "__main__":
    prog = unittest.main(exit=False, verbosity=2)
    sys.exit(0 if prog.result.wasSuccessful() else 1)
