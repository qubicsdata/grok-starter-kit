"""Shared helpers for the Backlog.md contract suite.

The binary comes only from the FOLIO_BACKLOG_BIN environment variable; no path is hard-coded.
Every backlog subprocess goes through BacklogRunner, which refuses any argv whose first word is
not in ALLOWED_FIRST_WORDS, runs with a temporary HOME and a minimal environment, and never uses a
shell. The web UI subcommand is never allowed.
"""

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

# TODO(WP-9): read backlog_version from folio/locks/backlog.lock.json instead of this constant.
BACKLOG_VERSION = "1.53.0"
BIN_ENV = "FOLIO_BACKLOG_BIN"
OPT_OUT_ENV = "FOLIO_BACKLOG_CONTRACT"
OPT_OUT_VALUE = "skip"
# R-c (review r1 H-1): an unset FOLIO_BACKLOG_BIN FAILS every contract test. The only way to skip is
# the explicit opt-out FOLIO_BACKLOG_CONTRACT=skip, which is announced on stderr and in each skip.
UNSET_MESSAGE = ("FOLIO_BACKLOG_BIN is not set; set it to the pinned Backlog.md 1.53.0 standalone binary "
                 "(or set FOLIO_BACKLOG_CONTRACT=skip to skip the contract suite explicitly)")
OPT_OUT_REASON = "FOLIO_BACKLOG_CONTRACT=skip: Backlog.md 1.53.0 contract suite explicitly skipped (R-c opt-out)"
_ANNOUNCED = set()
ALLOWED_FIRST_WORDS = ("init", "task", "doctor", "config", "doc", "--version")
TIMEOUT = 60

_VERSIONS = {}


class ForbiddenBacklogCommand(AssertionError):
    pass


def backlog_bin():
    return os.environ.get(BIN_ENV, "")


def base_env(home):
    env = {
        "HOME": str(home),
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "LANG": "C.UTF-8",
        "NO_COLOR": "1",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_AUTHOR_NAME": "Contract Test",
        "GIT_AUTHOR_EMAIL": "contract@example.com",
        "GIT_COMMITTER_NAME": "Contract Test",
        "GIT_COMMITTER_EMAIL": "contract@example.com",
    }
    tmpdir = os.environ.get("TMPDIR")
    if tmpdir:
        env["TMPDIR"] = tmpdir
    return env


class BacklogRunner:
    def __init__(self, binary, home):
        self.binary = binary
        self.home = Path(home)

    def run(self, argv, cwd, check=True):
        argv = list(argv)
        if not argv or argv[0] not in ALLOWED_FIRST_WORDS:
            raise ForbiddenBacklogCommand("refused backlog argv %r; allowed first words: %s" % (argv, ", ".join(ALLOWED_FIRST_WORDS)))
        result = subprocess.run(
            [self.binary, *argv],
            cwd=str(cwd),
            env=base_env(self.home),
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=TIMEOUT,
        )
        if check and result.returncode != 0:
            raise AssertionError("backlog %r exited %d\nstdout: %s\nstderr: %s" % (argv, result.returncode, result.stdout, result.stderr))
        return result

    def version(self):
        if self.binary not in _VERSIONS:
            _VERSIONS[self.binary] = self.run(["--version"], cwd=self.home).stdout.strip()
        return _VERSIONS[self.binary]


def git(cwd, *args, home):
    result = subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        env=base_env(home),
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=TIMEOUT,
    )
    if result.returncode != 0:
        raise AssertionError("git %r exited %d\nstdout: %s\nstderr: %s" % (args, result.returncode, result.stdout, result.stderr))
    return result


class BacklogContractCase(unittest.TestCase):
    """Fails when FOLIO_BACKLOG_BIN is unset or reports any version but 1.53.0.

    Skips only with the explicit opt-out FOLIO_BACKLOG_CONTRACT=skip (printed once on stderr)."""

    def setUp(self):
        binary = backlog_bin()
        if not binary:
            if os.environ.get(OPT_OUT_ENV) == OPT_OUT_VALUE:
                if OPT_OUT_REASON not in _ANNOUNCED:
                    _ANNOUNCED.add(OPT_OUT_REASON)
                    print("backlog contract: " + OPT_OUT_REASON, file=sys.stderr)
                self.skipTest(OPT_OUT_REASON)
            self.fail(UNSET_MESSAGE)
        tmp = tempfile.TemporaryDirectory(prefix="folio-backlog-contract-")
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.home = self.root / "home"
        self.home.mkdir()
        self.backlog = BacklogRunner(binary, self.home)
        version = self.backlog.version()
        self.assertEqual(
            version,
            BACKLOG_VERSION,
            "%s reports Backlog.md %r; the contract suite is pinned to exactly %s" % (BIN_ENV, version, BACKLOG_VERSION),
        )

    def git(self, cwd, *args):
        return git(cwd, *args, home=self.home)

    def init_repo(self, name="repo", git_repo=True, extra=("--check-branches", "false", "--include-remote", "false")):
        repo = self.root / name
        repo.mkdir()
        if git_repo:
            self.git(repo, "init", "-q", "-b", "main")
        self.backlog.run(
            ["init", "Contract", "--defaults", "--auto-open-browser", "false", "--integration-mode", "none", *extra],
            cwd=repo,
        )
        self.assertIn("auto_open_browser: false\n", self.config_text(repo))
        return repo

    def config_path(self, repo):
        return Path(repo) / "backlog" / "config.yml"

    def config_text(self, repo):
        return self.config_path(repo).read_text(encoding="utf-8")

    def set_projects(self, repo, *projects):
        with self.config_path(repo).open("a", encoding="utf-8") as handle:
            handle.write("projects: [%s]\n" % ", ".join('"%s"' % project for project in projects))

    def task_files(self, repo):
        return sorted(path.name for path in (Path(repo) / "backlog" / "tasks").glob("*.md"))

    def task_file(self, repo, prefix):
        matches = [name for name in self.task_files(repo) if name.startswith(prefix + " - ")]
        self.assertEqual(len(matches), 1, matches)
        return Path(repo) / "backlog" / "tasks" / matches[0]

    def front_matter(self, path):
        lines = Path(path).read_text(encoding="utf-8").split("\n")
        self.assertEqual(lines[0], "---")
        return lines[1:lines.index("---", 1)]
