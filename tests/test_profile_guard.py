"""The refuse-to-commit check for the private business profile
(`tools/business_profile.py check`) and the kit's .gitignore guard.

The profile is built at AGENTS.md checkpoint 3b and lives at
`<channel>/private/business-profile.yaml` inside the user's second brain. It
never goes into git: the kit ignores every `private/` folder and every
`business-profile*.yaml`, and the check refuses a commit that stages one,
or any file holding the profile's marker line, whatever its name.

Every repo here is a synthetic temp repo with an invented identity and no
global or system git config; the kit's own repo is only read
(`git ls-files`). `KIT_BUSINESS_PROFILE` points the suite at another copy of
the tool. Stdlib only, Python 3.9+.
"""

import fnmatch
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOL = os.environ.get("KIT_BUSINESS_PROFILE") or os.path.join(ROOT, "tools", "business_profile.py")

# Split so this file never holds the marker as a line of its own.
MARKER = "profile.private" + ": true"
PROFILE = "dance-school/private/business-profile.yaml"
SENTINEL = "quokka-sentinel-value"
IDENTITY = ["-c", "user.name=Example Author", "-c", "user.email=kit@example.com",
            "-c", "commit.gpgsign=false", "-c", "init.defaultBranch=main"]


def profile_text():
    return "%s\nchannel: \"dance-school\"\nschool.name: \"%s\"\n" % (MARKER, SENTINEL)


class Repo:
    """A throwaway git repo with no global or system config."""

    def __init__(self, test):
        self.test = test
        base = tempfile.mkdtemp(prefix="kit-profile-guard-")
        test.addCleanup(shutil.rmtree, base, True)
        self.home = os.path.join(base, "home")
        self.path = os.path.join(base, "repo")
        self.hooks = os.path.join(base, "no-hooks")
        for folder in (self.home, self.path, self.hooks):
            os.makedirs(folder)
        self.env = {
            "HOME": self.home, "PATH": os.environ.get("PATH", ""), "LANG": "C.UTF-8",
            "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.path.join(self.home, "gitconfig"),
            "PYTHONDONTWRITEBYTECODE": "1",
        }
        self.git("init", "-q")

    def git(self, *args, hooks=None, check=True):
        proc = subprocess.run(
            ["git"] + IDENTITY + ["-c", "core.hooksPath=%s" % (hooks or self.hooks)] + list(args),
            cwd=self.path, env=self.env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            universal_newlines=True, timeout=60,
        )
        if check:
            self.test.assertEqual(proc.returncode, 0, "git %s failed" % args[0])
        return proc

    def write(self, rel, text):
        path = os.path.join(self.path, rel)
        os.makedirs(os.path.dirname(path) or self.path, exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)

    def stage(self, rel, text):
        self.write(rel, text)
        self.git("add", "-f", "--", rel)

    def commit(self, message="example"):
        return self.git("commit", "-q", "-m", message)

    def head_count(self):
        proc = self.git("rev-list", "--count", "HEAD", check=False)
        return int(proc.stdout.strip()) if proc.returncode == 0 else 0

    def check(self, *extra, cwd=None):
        return subprocess.run(
            [sys.executable, "-B", TOOL, "check"] + list(extra),
            cwd=cwd or self.path, env=self.env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            universal_newlines=True, timeout=60,
        )


class ToolShipsMixin:
    def setUp(self):
        self.assertTrue(os.path.isfile(TOOL), "tools/business_profile.py is missing")


class CheckStagedTest(ToolShipsMixin, unittest.TestCase):
    def repo(self):
        repo = Repo(self)
        repo.stage("README.md", "Example notes\n")
        repo.commit()
        return repo

    def assert_refused(self, proc, rel):
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        self.assertIn(rel, proc.stderr)
        self.assertNotIn(SENTINEL, proc.stdout + proc.stderr, "the check never prints file contents")

    def test_clean_staged_change_passes(self):
        repo = self.repo()
        repo.stage("dance-school/marketing/post.md", "A draft post\n")
        proc = repo.check()
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)

    def test_refuses_a_staged_profile_in_a_private_folder(self):
        for rel in (PROFILE, "other-activities/private/notes.md", "private/anything.txt"):
            with self.subTest(rel=rel):
                repo = self.repo()
                repo.stage(rel, "plain text without the marker, " + SENTINEL + "\n")
                self.assert_refused(repo.check(), rel)

    def test_refuses_a_profile_file_name_outside_private(self):
        repo = self.repo()
        rel = "dance-school/business-profile.yaml"
        repo.stage(rel, "school.name: \"%s\"\n" % SENTINEL)
        self.assert_refused(repo.check(), rel)

    def test_refuses_the_marker_under_any_name(self):
        repo = self.repo()
        rel = "dance-school/marketing/copied-settings.md"
        repo.stage(rel, "# Notes\n\n" + profile_text())
        self.assert_refused(repo.check(), rel)

    def test_marker_mentioned_inside_a_line_is_not_a_profile(self):
        repo = self.repo()
        repo.stage("docs.md", "The profile starts with `%s`; never commit it.\n" % MARKER)
        proc = repo.check()
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)

    def test_removing_a_committed_profile_is_allowed(self):
        repo = self.repo()
        repo.stage(PROFILE, profile_text())
        repo.commit()
        repo.git("rm", "-q", "--cached", "--", PROFILE)
        proc = repo.check()
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)

    def test_first_commit_on_an_unborn_branch(self):
        repo = Repo(self)
        repo.stage(PROFILE, profile_text())
        self.assert_refused(repo.check(), PROFILE)
        clean = Repo(self)
        clean.stage("README.md", "Example\n")
        self.assertEqual(clean.check().returncode, 0)

    def test_repo_option_and_not_a_repo(self):
        repo = self.repo()
        repo.stage(PROFILE, profile_text())
        elsewhere = tempfile.mkdtemp(prefix="kit-profile-elsewhere-")
        self.addCleanup(shutil.rmtree, elsewhere, True)
        self.assert_refused(repo.check("--repo", repo.path, cwd=elsewhere), PROFILE)
        proc = repo.check(cwd=elsewhere)
        self.assertEqual(proc.returncode, 2, "outside a git repo the check fails closed")


class CheckAllTest(ToolShipsMixin, unittest.TestCase):
    def test_all_flags_a_tracked_profile_and_passes_a_clean_tree(self):
        repo = Repo(self)
        repo.stage("README.md", "Example\n")
        repo.commit()
        self.assertEqual(repo.check("--all").returncode, 0)
        repo.stage(PROFILE, profile_text())
        repo.commit()
        proc = repo.check("--all")
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        self.assertIn(PROFILE, proc.stderr)
        self.assertEqual(repo.check().returncode, 0, "nothing staged now")


class PreCommitHookTest(ToolShipsMixin, unittest.TestCase):
    """The hook a user can install in their own notes repo; installed here
    only in a synthetic temp repo."""

    def install(self, repo):
        hooks = os.path.join(os.path.dirname(repo.path), "hooks")
        os.makedirs(hooks)
        hook = os.path.join(hooks, "pre-commit")
        with open(hook, "w", encoding="utf-8") as fh:
            fh.write("#!/bin/sh\nexec \"%s\" -B \"%s\" check\n" % (sys.executable, TOOL))
        os.chmod(hook, 0o755)
        return hooks

    def test_hook_refuses_a_commit_with_the_profile(self):
        repo = Repo(self)
        hooks = self.install(repo)
        repo.stage("README.md", "Example\n")
        repo.git("commit", "-q", "-m", "clean", hooks=hooks)
        self.assertEqual(repo.head_count(), 1, "a clean commit passes the hook")
        repo.stage(PROFILE, profile_text())
        proc = repo.git("commit", "-q", "-m", "leak", hooks=hooks, check=False)
        self.assertNotEqual(proc.returncode, 0, "the hook let the profile through")
        self.assertEqual(repo.head_count(), 1, "no new commit")
        self.assertIn(PROFILE, proc.stderr)
        self.assertNotIn(SENTINEL, proc.stdout + proc.stderr)


class GitignoreGuardTest(unittest.TestCase):
    """The kit's .gitignore keeps the profile out of a fork of the kit."""

    IGNORED = (
        PROFILE,
        "second-brain/" + PROFILE,
        "other-activities/private/notes.md",
        "private/anything.txt",
        "business-profile.yaml",
        "second-brain/dance-school/business-profile.yaml",
    )
    TRACKABLE = (
        "second-brain/BUSINESS-PROFILE.md",
        "second-brain/dance-school/marketing/README-drafts-only.md",
        "tools/business_profile.py",
        "tests/test_profile_guard.py",
    )

    def setUp(self):
        self.repo = Repo(self)
        with open(os.path.join(ROOT, ".gitignore"), encoding="utf-8") as fh:
            self.repo.write(".gitignore", fh.read())

    def ignored(self, rel):
        proc = self.repo.git("check-ignore", "-q", "--no-index", rel, check=False)
        self.assertIn(proc.returncode, (0, 1), "git check-ignore error")
        return proc.returncode == 0

    def test_profile_paths_are_ignored(self):
        for rel in self.IGNORED:
            with self.subTest(rel=rel):
                self.assertTrue(self.ignored(rel), "not ignored")

    def test_kit_files_stay_trackable(self):
        for rel in self.TRACKABLE:
            with self.subTest(rel=rel):
                self.assertFalse(self.ignored(rel), "wrongly ignored")


class KitTracksNothingPrivateTest(unittest.TestCase):
    def test_no_tracked_private_path_or_profile(self):
        if shutil.which("git") is None:
            self.skipTest("git not installed")
        proc = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE)
        if proc.returncode != 0:
            self.skipTest("not inside a git work tree")
        bad = []
        for raw in proc.stdout.split(b"\0"):
            rel = os.fsdecode(raw)
            parts = rel.split("/")
            if "private" in [p.lower() for p in parts[:-1]] or fnmatch.fnmatch(parts[-1].lower(), "business-profile*.y*ml"):
                bad.append(rel)
        self.assertEqual(bad, [])


if __name__ == "__main__":
    unittest.main()
