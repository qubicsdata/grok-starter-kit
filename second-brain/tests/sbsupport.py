"""Shared helpers for the sb tests.

Every fixture is synthetic and built in a temp folder at test time: a fake
HOME, a note tree (SB_HOME), a kit.config.yaml written from a dict, and PATH
folders with and without ripgrep. Planted values that a scanner could flag
are assembled from fragments at run time; the kit's own tests are scanned too.

Run the suite with:
    python3 -m unittest discover -s second-brain/tests -p 'test_*.py'
"""

import hashlib
import hmac
import importlib.machinery
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SB_DIR = os.path.dirname(HERE)
KIT_ROOT = os.path.dirname(SB_DIR)
# KIT_SB points the suite at another copy of sb (mutation checks).
SB = os.environ.get("KIT_SB") or os.path.join(SB_DIR, "bin", "sb")
EXAMPLE_CONFIG = os.path.join(KIT_ROOT, "kit.config.example.yaml")
CI_LOCAL = os.path.join(KIT_ROOT, "tools", "ci_local.py")
CLEAN_SCAN = os.path.join(KIT_ROOT, "tools", "clean_scan.py")

REAL_RG = shutil.which("rg")
NO_RG_REASON = "rg not installed: the rg engine path is skipped (ripgrep is optional for sb)"
needs_rg = unittest.skipUnless(REAL_RG, NO_RG_REASON)

DEFAULT_CHANNELS = ["dance-school", "other-activities"]
DEFAULT_DOCTOR = {
    "fail_on_untagged": True,
    "fail_on_multiple_channels": True,
    "fail_on_folder_mismatch": True,
    "fail_on_cross_channel_link": True,
    "fail_on_missing_router_path": True,
}
SETTINGS_KEYS = {
    "home", "router_file", "channels", "roots", "raw_roots", "path_defaults",
    "name_hashes", "boost_paths", "doctor", "config_path",
}

DOCTOR_LINE = re.compile(r"^(FAIL|WARN) ([1-9]) (\S+)$")
DOCTOR_SUMMARY = re.compile(
    r"^sb doctor: (\d+) notes, (\d+) router rows, (\d+) failures, (\d+) warnings$"
)
SEARCH_HEADER = re.compile(
    r'^sb "(?P<query>.*)"(?: --channel (?P<channel>\S+))?: (?P<router>\d+) router \+ '
    r"(?P<shown>\d+) of (?P<total>\d+) file hits, (?P<ms>\d+) ms, engine (?P<engine>rg|python)"
    r"(?:, (?P<withheld>\d+) withheld by channel filter)?$"
)
RESULT_LINE = re.compile(r"^(?P<rank>\d+) \[(?P<tag>[^\]]+)\] (?P<path>[^\s:]+)(?::(?P<line>\d+))?  (?P<text>.*)$")
ROUTER_LINE = re.compile(r"^R \[(?P<ch>[^\]]+)\] (?P<topic>.+?) -> (?P<paths>.+?) \| (?P<desc>.*)$")
NO_HITS = "no hits: not in the second brain"
WITHHELD_SECRET = "[line withheld: looks like a credential]"

AT = "@"


# A synthetic scan key, derived at run time; tests write it into their temp
# HOME and never read or create the real key of the box.
FIXTURE_KEY = hashlib.sha256(b"sb synthetic fixture scan key").digest()
KEY_DIR = os.path.join(".config", "grok-kit")
KEY_NAME = "scan.key"
INIT_KEY_HINT = "sb --init-key"


def name_hash(word, key=FIXTURE_KEY):
    """The 16-hex name hash sb matches for a folded word: the first 16 hex
    chars of HMAC-SHA256(scan key, word)."""
    return hmac.new(key, word.encode("utf-8"), hashlib.sha256).hexdigest()[:16]


def unkeyed_hash(word):
    """The old, unkeyed name hash (sha256 of the word): no longer matched."""
    return hashlib.sha256(word.encode("utf-8")).hexdigest()[:16]


def load_sb():
    """Import bin/sb (no .py suffix) as a module, writing no bytecode."""
    loader = importlib.machinery.SourceFileLoader("sb_under_test", SB)
    spec = importlib.util.spec_from_loader("sb_under_test", loader)
    module = importlib.util.module_from_spec(spec)
    saved = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = saved
    return module


# ---------------------------------------------------------------- YAML out

def yaml_scalar(value):
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    return json.dumps(value, ensure_ascii=False)


PLAIN_KEY = re.compile(r"^[A-Za-z_][A-Za-z0-9_-]*$")


def yaml_key(key):
    return key if PLAIN_KEY.match(key) else json.dumps(key, ensure_ascii=False)


def yaml_lines(mapping, indent=0):
    pad = " " * indent
    out = []
    for key, value in mapping.items():
        if isinstance(value, dict) and value:
            out.append("%s%s:" % (pad, yaml_key(key)))
            out.extend(yaml_lines(value, indent + 2))
        elif isinstance(value, dict):
            out.append("%s%s: {}" % (pad, yaml_key(key)))
        elif isinstance(value, list):
            out.append("%s%s: [%s]" % (pad, yaml_key(key), ", ".join(yaml_scalar(v) for v in value)))
        else:
            out.append("%s%s: %s" % (pad, yaml_key(key), yaml_scalar(value)))
    return out


def dump_config(config):
    return "\n".join(["# synthetic test config"] + yaml_lines(config)) + "\n"


# ---------------------------------------------------------------- notes

def front_matter(channel=None, tags=None, links=None, title="Example note", extra=()):
    lines = ["---", 'title: "%s"' % title, 'type: "note"', 'id: "N-20260105-abc123"',
             'status: "draft"', 'owner: "<your-name>"', 'created: "2026-01-05"']
    if channel is not None:
        lines.append('channel: "%s"' % channel)
    if tags is not None:
        lines.append("tags: [%s]" % ", ".join(tags))
    if links is not None:
        lines.append("links: [%s]" % ", ".join('"%s"' % l for l in links))
    lines.extend(extra)
    lines.append("---")
    return "\n".join(lines) + "\n"


def note(channel=None, tags=None, links=None, body="", title="Example note", extra=()):
    return front_matter(channel, tags, links, title, extra) + "\n" + body.rstrip("\n") + "\n"


ROUTER_HEADER = "| Topic | Keywords | Ch | Path(s) | What's there |\n|---|---|---|---|---|\n"


def router(*areas):
    """areas: (title, [(topic, keywords, ch, [paths], desc), ...])."""
    out = ["# Router (synthetic)", ""]
    for title, rows in areas:
        out.append("## " + title)
        out.append(ROUTER_HEADER.rstrip("\n"))
        for topic, keywords, ch, paths, desc in rows:
            out.append("| %s | %s | %s | %s | %s |" % (
                topic, keywords, ch, ", ".join("`%s`" % p for p in paths), desc))
        out.append("")
    return "\n".join(out)


DANCE_ROWS = [
    ("Class schedule", "timetable, term, classes", "dance-school", ["dance-school/classes/"], "Term timetable"),
    ("Marketing", "campaign, poster", "dance-school", ["dance-school/marketing/"], "Campaigns and posters"),
]
OTHER_ROWS = [
    ("Workshops", "workshop, pottery", "other-activities", ["other-activities/"], "Workshop notes"),
]


def clean_router(extra_dance=(), extra_other=()):
    return router(("Dance school", DANCE_ROWS + list(extra_dance)),
                  ("Other activities", OTHER_ROWS + list(extra_other)))


def clean_brain():
    """A small note tree on which `sb --doctor` reports nothing (exit 0)."""
    return {
        "README.md": "# Example second brain\n\nTop-level files are not notes.\n",
        "ROUTER.md": clean_router(),
        "dance-school/classes/term-timetable.md": note(
            "dance-school", ["dance-school", "schedule"],
            body="# Term timetable\n\nMonday ballet beginners 17:00-18:00\nWednesday jazz 18:30\n",
            title="Term timetable"),
        "dance-school/marketing/open-day-campaign.md": note(
            "dance-school", ["dance-school", "marketing", "campaign"],
            links=["dance-school/classes/term-timetable.md"],
            body="# Open day campaign\n\nPoster plan, see [[term-timetable]] and [[term-timetable|the timetable]].\n",
            title="Open day campaign"),
        "other-activities/pottery-workshop.md": note(
            "other-activities", ["other-activities", "workshop"],
            body="# Pottery workshop\n\nClay, glazes and kiln dates.\n", title="Pottery workshop"),
        "other-activities/admin/supplies.md": note(
            "other-activities", ["other-activities", "admin"],
            links=["../pottery-workshop.md"],
            body="# Supplies\n\nClay order for the workshop.\n", title="Supplies"),
    }


CLEAN_NOTE_COUNT = 4
CLEAN_ROW_COUNT = 3


# ---------------------------------------------------------------- tree digest

def tree_digest(root):
    """{relative path: sha256 of bytes} for files, plus '<dir>/' entries; symlinks by target."""
    digest = {}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames.sort()
        rel_dir = os.path.relpath(dirpath, root)
        if rel_dir != ".":
            digest[rel_dir.replace(os.sep, "/") + "/"] = "dir"
        for name in sorted(filenames):
            path = os.path.join(dirpath, name)
            rel = os.path.relpath(path, root).replace(os.sep, "/")
            if os.path.islink(path):
                digest[rel] = "link:" + os.readlink(path)
                continue
            with open(path, "rb") as fh:
                digest[rel] = hashlib.sha256(fh.read()).hexdigest()
        for name in dirnames:
            path = os.path.join(dirpath, name)
            if os.path.islink(path):
                digest[os.path.relpath(path, root).replace(os.sep, "/")] = "link:" + os.readlink(path)
    return digest


# ---------------------------------------------------------------- base case

class SbCase(unittest.TestCase):
    """A temp world: fake HOME, SB_HOME note tree, config file, PATH folders."""

    maxDiff = None

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="sb-test-")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.home = self._mkdir("home")
        self.brain = self._mkdir("brain")
        self.empty_bin = self._mkdir("bin-empty")
        self.fake_bin = self._mkdir("bin-fake")
        self.marker = os.path.join(self.tmp, "rg-was-called")
        self.config_path = os.path.join(self.tmp, "kit.config.yaml")

    def _mkdir(self, name):
        path = os.path.join(self.tmp, name)
        os.makedirs(path)
        return path

    # -- fixtures

    def write(self, rel, text, root=None):
        path = os.path.join(root or self.brain, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        data = text.encode("utf-8") if isinstance(text, str) else text
        with open(path, "wb") as fh:
            fh.write(data)
        return path

    def write_tree(self, files, root=None):
        for rel, text in files.items():
            self.write(rel, text, root)

    def remove(self, rel):
        os.remove(os.path.join(self.brain, rel))

    def write_config(self, second_brain=None, top=None, raw=None):
        """Write kit.config.yaml: `home` is the temp note tree unless overridden."""
        if raw is not None:
            text = raw
        else:
            block = {"home": self.brain}
            block.update(second_brain or {})
            config = {}
            config.update(top or {})
            config["second_brain"] = block
            text = dump_config(config)
        with open(self.config_path, "w", encoding="utf-8") as fh:
            fh.write(text)
        return self.config_path

    def key_path(self, config_home=None):
        """Where sb looks for the scan key: <config_home or HOME/.config>/grok-kit/scan.key."""
        if config_home is None:
            return os.path.join(self.home, KEY_DIR, KEY_NAME)
        return os.path.join(config_home, "grok-kit", KEY_NAME)

    def write_scan_key(self, key=FIXTURE_KEY, path=None, dir_mode=0o700, file_mode=0o600):
        """Plant a synthetic scan key in the temp HOME (never the real one)."""
        path = path or self.key_path()
        self.assertTrue(os.path.abspath(path).startswith(self.tmp + os.sep), "fixture key outside the temp folder")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        os.chmod(os.path.dirname(path), dir_mode)
        with open(path, "wb") as fh:
            fh.write(key)
        os.chmod(path, file_mode)
        return path

    def fake_rg(self, passthrough=True):
        """An `rg` on self.fake_bin that records each call in self.marker; it
        runs the real rg when passthrough is true, else fails with exit 2."""
        path = os.path.join(self.fake_bin, "rg")
        tail = 'exec "%s" "$@"\n' % REAL_RG if (passthrough and REAL_RG) else "exit 2\n"
        with open(path, "w") as fh:
            fh.write("#!/bin/sh\necho called >> \"%s\"\n%s" % (self.marker, tail))
        os.chmod(path, 0o755)
        return self.fake_bin

    def rg_called(self):
        return os.path.exists(self.marker)

    # -- running sb

    def env(self, path=None, **extra):
        env = {
            "HOME": self.home,
            "PATH": os.environ.get("PATH", "") if path is None else path,
            "LANG": "C.UTF-8",
            "PYTHONIOENCODING": "utf-8",
            "PYTHONDONTWRITEBYTECODE": "1",
        }
        env.update({k: v for k, v in extra.items() if v is not None})
        return env

    def run_sb_bytes(self, args, config=True, path=None, cwd=None, stdin=None, umask=None, **env_extra):
        """Run sb; (exit code, stdout bytes, stderr bytes). stdin is text fed
        to sb, umask the child's umask."""
        argv = [sys.executable, SB]
        if config:
            argv += ["--config", self.config_path if config is True else config]
        argv += list(args)
        env = self.env(path, **env_extra)
        for name in ("HOME", "XDG_CONFIG_HOME"):
            if name in env and os.path.isabs(env[name]):  # a relative one is ignored by sb
                self.assertTrue(env[name].startswith(self.tmp + os.sep), "%s outside the temp folder" % name)
        proc = subprocess.run(
            argv, cwd=cwd or self.tmp, env=env,
            input=None if stdin is None else stdin.encode("utf-8"),
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120,
            preexec_fn=None if umask is None else (lambda: os.umask(umask)),
        )
        return proc.returncode, proc.stdout, proc.stderr

    def run_sb(self, args, config=True, path=None, cwd=None, stdin=None, umask=None, **env_extra):
        code, out, err = self.run_sb_bytes(args, config, path, cwd, stdin, umask, **env_extra)
        return code, out.decode("utf-8", "replace"), err.decode("utf-8", "replace")

    # -- doctor helpers

    def doctor(self, **kwargs):
        code, out, err = self.run_sb(["--doctor"], **kwargs)
        return code, out, err

    def doctor_lines(self, out):
        """(level, check, path) tuples; asserts every line is a finding or the summary."""
        found, summaries = [], []
        for line in out.splitlines():
            m = DOCTOR_LINE.match(line)
            if m:
                found.append((m.group(1), int(m.group(2)), m.group(3)))
                continue
            m = DOCTOR_SUMMARY.match(line)
            self.assertIsNotNone(m, "unexpected doctor output line shape")
            summaries.append(m)
        self.assertEqual(len(summaries), 1, "exactly one doctor summary line")
        self.assertEqual(found, sorted(found, key=lambda f: (f[1], f[2], f[0])), "findings sorted by check, path")
        return found

    def checks(self, out, check):
        return [(level, path) for level, num, path in self.doctor_lines(out) if num == check]

    # -- search helpers

    def results(self, out):
        return [RESULT_LINE.match(l) for l in out.splitlines() if RESULT_LINE.match(l)]

    def result_paths(self, out):
        return [m.group("path") for m in self.results(out)]

    def header(self, out):
        lines = out.splitlines()
        self.assertTrue(lines, "no output")
        m = SEARCH_HEADER.match(lines[0])
        self.assertIsNotNone(m, "first line is not the search header")
        return m


def normalize_search(out):
    """Search output with the timing and engine name masked, for parity checks."""
    lines = out.splitlines()
    if lines:
        lines[0] = re.sub(r", \d+ ms, engine (rg|python)", ", <ms>, engine <x>", lines[0])
    return "\n".join(lines)
