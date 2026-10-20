"""Shared helpers for the clean-scan tests.

Every planted value is assembled at run time from fragments or chr(), so this
file holds no literal that the scanner would flag: the kit's own tests are
scanned too (see test_output.ScanOwnSourceTest). Keep it that way.

Run the suite with:
    python3 -m unittest discover -s tests/scan -p 'test_*.py'
"""

import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
KIT_ROOT = os.path.dirname(os.path.dirname(HERE))
# KIT_CLEAN_SCAN points the suite at another copy of the scanner (tools/mutation_check.py).
CLEAN_SCAN = os.environ.get("KIT_CLEAN_SCAN") or os.path.join(KIT_ROOT, "tools", "clean_scan.py")

CODES = (
    "SECRET", "EMAIL", "NOREPLY", "BIDI", "CTRL", "HOMEPATH", "OPSPATH", "ALIAS",
    "UUID", "CAPTURE", "SUPERPOWERS", "STRUCT", "TERMS", "HDR", "MSG",
    "GITLEAKS", "TRUFFLEHOG",
)

CODE_LINE = re.compile(r"^([A-Z]+) (\d+)$")
SKIP_LINE = re.compile(r"^SKIP ([a-z]+)$")

ALLOWED_NAME = "Example"
ALLOWED_EMAIL = "dev@example.com"
ALLOWED_IDENTITY = "%s <%s>" % (ALLOWED_NAME, ALLOWED_EMAIL)

AT = "@"
RLO = chr(0x202E)  # right-to-left override
LRI = chr(0x2066)  # left-to-right isolate


def planted():
    """One synthetic canary value per rule, built from fragments at run time."""
    return {
        "key_block": "-----BEGIN" + " RSA PRIVATE" + " KEY-----\nMIIEow\n-----END" + " RSA PRIVATE" + " KEY-----",
        "token_gh": "gh" + "p_" + "A1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6Q7r8",
        "token_sk": "sk" + "-" + "abcdefghijklmnopqrstuvwxyz012345",
        "token_aws": "AK" + "IA" + "ABCDEFGHIJKLMNOP",
        "token_slack": "xo" + "xb-" + "123456789012-abcdefghijkl",
        "token_jwt": "ey" + "J" + "hbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9" + "." + "eyJzdWIiOiIxIn0",
        "assignment": "pass" + "word" + " = " + "'" + "hunter2hunter2" + "'",
        "email": "pat.fixture" + AT + "canary-mail" + ".net",
        "noreply": "12345+example-user" + AT + "users.noreply" + ".github.com",
        "mac_home": "/Us" + "ers/" + "fixture-person/notes",
        "box_home": "/ho" + "me/" + "jane" + "/notes",
        "other_home": "/ho" + "me/" + "fixture-person/notes",
        "workspace": "/" + "work" + "space" + "/project",
        "mac_tmp": "/private/var/" + "folders/" + "ab/cd",
        "opspath": "forge" + "-" + "ops",
        "alias_ch": "ch" + "-q",
        "alias_cl": "cl" + "-acme",
        "uuid": "-".join(["1234abcd", "5678", "4abc", "8def", "0123456789ab"]),
        "real_name": "usage" + "_re" + "al_" + "2026.txt",
        "superpowers": "." + "super" + "powers" + "/x.md",
    }


def zero_uuid():
    return "-".join(["0" * 8, "0" * 4, "0" * 4, "0" * 4, "0" * 12])


def usage_screen(email="user@example.com", org="Example Org", plan="Example Plan"):
    """A synthetic /usage-style screen; the defaults are clean."""
    return "\n".join([
        "/usage",
        "Current session",
        "12% used",
        "Resets 3pm",
        "Email: " + email,
        "Org: " + org,
        "Plan: " + plan,
        "",
    ])


class Tree:
    """A temp folder to plant files in; removed on cleanup()."""

    def __init__(self, prefix="kitscan-"):
        self.root = tempfile.mkdtemp(prefix=prefix)

    def path(self, rel):
        return os.path.join(self.root, rel)

    def write(self, rel, content):
        """Write text (utf-8) or bytes; parent folders are created."""
        full = self.path(rel)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        if isinstance(content, bytes):
            with open(full, "wb") as handle:
                handle.write(content)
        else:
            with open(full, "w", encoding="utf-8", newline="") as handle:
                handle.write(content)
        return full

    def mkdir(self, rel):
        full = self.path(rel)
        os.makedirs(full, exist_ok=True)
        return full

    def cleanup(self):
        shutil.rmtree(self.root, ignore_errors=True)


def clean_env(home):
    """A minimal environment: no inherited git or user configuration."""
    return {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": home,
        "PYTHONUTF8": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_TERMINAL_PROMPT": "0",
    }


class ScanResult:
    def __init__(self, proc):
        self.code = proc.returncode
        self.stdout = proc.stdout
        self.stderr = proc.stderr
        self.counts = {}
        self.skips = set()
        self.total = None
        self.binary = 0  # BINARY <n>: image files known by magic bytes; not a finding, not in TOTAL
        self.bad_lines = []
        for line in self.stdout.splitlines():
            m = CODE_LINE.match(line)
            if m:
                if m.group(1) == "TOTAL":
                    self.total = int(m.group(2))
                elif m.group(1) == "BINARY":
                    self.binary = int(m.group(2))
                else:
                    self.counts[m.group(1)] = int(m.group(2))
                continue
            m = SKIP_LINE.match(line)
            if m:
                self.skips.add(m.group(1))
                continue
            self.bad_lines.append(line)

    def count(self, code):
        return self.counts.get(code, 0)

    @property
    def output(self):
        return self.stdout + "\n" + self.stderr


def run_scan(*args, cwd=None, home=None, timeout=120, env_extra=None):
    """Run the scanner as a subprocess with a clean environment (plus env_extra)."""
    own_home = home is None
    if own_home:
        home = tempfile.mkdtemp(prefix="kitscan-home-")
    env = clean_env(home)
    env.update(env_extra or {})
    try:
        proc = subprocess.run(
            [sys.executable, CLEAN_SCAN, *args],
            cwd=cwd or home,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            timeout=timeout,
        )
    finally:
        if own_home:
            shutil.rmtree(home, ignore_errors=True)
    return ScanResult(proc)


def git_available():
    return shutil.which("git") is not None


def git(repo, *args, name=ALLOWED_NAME, email=ALLOWED_EMAIL, env_extra=None, check=True):
    """Run git in repo with a fixed synthetic identity and no user config."""
    env = clean_env(repo)
    env.update(env_extra or {})
    proc = subprocess.run(
        [
            "git",
            "-c", "user.name=" + name,
            "-c", "user.email=" + email,
            "-c", "commit.gpgsign=false",
            "-c", "tag.gpgsign=false",
            "-c", "init.defaultBranch=main",
            "-c", "core.hooksPath=" + os.devnull,
            *args,
        ],
        cwd=repo,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        timeout=60,
    )
    if check and proc.returncode != 0:
        raise RuntimeError("git %s failed (exit %d)" % (args[0], proc.returncode))
    return proc.stdout


def init_repo(tree):
    git(tree.root, "init", "-q")
    return tree.root


def commit_all(tree, message, name=ALLOWED_NAME, email=ALLOWED_EMAIL, author=None):
    git(tree.root, "add", "-A", name=name, email=email)
    args = ["commit", "-q", "--allow-empty", "-m", message]
    if author:
        args += ["--author", author]
    git(tree.root, *args, name=name, email=email)
    return git(tree.root, "rev-parse", "HEAD").strip()


def write_executable(path, body):
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("#!" + sys.executable + "\n" + body)
    os.chmod(path, os.stat(path).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return path


class ScanTestCase(unittest.TestCase):
    """Base: a fresh Tree per test, removed afterwards."""

    def setUp(self):
        self.tree = Tree()
        self.addCleanup(self.tree.cleanup)

    def scan(self, *args, **kwargs):
        return run_scan(*args, **kwargs)

    def scan_tree(self, *extra, **kwargs):
        return run_scan(self.tree.root, *extra, **kwargs)

    def assert_only_count_lines(self, result):
        self.assertEqual(result.bad_lines, [], "stdout holds a line that is not CODE/TOTAL/SKIP")
        self.assertIsNotNone(result.total, "no TOTAL line")
        self.assertEqual(result.total, sum(result.counts.values()), "TOTAL is not the sum of the codes")

    def assert_single(self, result, code):
        """Exactly one finding, under `code`, and nothing else; exit 1."""
        self.assert_only_count_lines(result)
        self.assertEqual(result.count(code), 1, "%s should count exactly 1" % code)
        self.assertEqual(result.total, 1, "only the planted finding should count")
        self.assertEqual(result.code, 1)

    def assert_clean(self, result):
        self.assert_only_count_lines(result)
        self.assertEqual(result.total, 0, "expected a clean scan")
        self.assertEqual(result.code, 0)

    def assert_no_leak(self, result, values):
        for value in values:
            self.assertNotIn(value, result.output, "a planted value or path was printed")
