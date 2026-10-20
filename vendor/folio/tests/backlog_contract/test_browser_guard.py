"""Checks that Folio never starts the Backlog.md web UI subcommand.

(1) BacklogRunner, used by every contract test, refuses any argv whose first word is not allowed.
(2) A static scan of folio/, scripts/ and tests/ fails on any invocation of the subcommand. The
needles are built from fragments so this file does not match itself.
"""

import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

from . import support
from .support import ALLOWED_FIRST_WORDS, BacklogRunner, ForbiddenBacklogCommand

REPO_ROOT = Path(__file__).resolve().parents[2]
SCANNED = ("folio", "scripts", "tests")
SUBCOMMAND = "brow" + "ser"
NEEDLES = (
    # "<tool> <subcommand>" in text, shell strings or split argv: backlog, backlog.md, "backlog", "...
    re.compile(r"\bbacklog(?:\.md)?[\"'\s,]+" + SUBCOMMAND + r"\b", re.IGNORECASE),
    # the subcommand as a quoted argv element: [bin, "<subcommand>"], ('<subcommand>', ...)
    re.compile(r"[\[,(]\s*[\"']" + SUBCOMMAND + r"[\"']\s*[,\])]"),
)


def subcommand_invocations(root, directories=SCANNED):
    hits = []
    for directory in directories:
        for path in sorted((Path(root) / directory).rglob("*")):
            if not path.is_file() or "__pycache__" in path.parts:
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            for number, line in enumerate(text.splitlines(), 1):
                if any(needle.search(line) for needle in NEEDLES):
                    hits.append("%s:%d: %s" % (path.relative_to(root), number, line.strip()))
    return hits


def write_recording_backlog(directory):
    log = Path(directory) / "calls.log"
    fake = Path(directory) / "backlog"
    fake.write_text(
        "#!%s\n"
        "import json, os, sys\n"
        "with open(%r, 'a', encoding='utf-8') as handle:\n"
        "    handle.write(json.dumps({'argv': sys.argv[1:], 'home': os.environ.get('HOME'),\n"
        "                             'keys': sorted(os.environ)}) + '\\n')\n" % (sys.executable, str(log)),
        encoding="utf-8",
    )
    fake.chmod(0o700)
    return fake, log


def calls(log):
    if not log.exists():
        return []
    return [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]


class ArgvGuardTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="folio-backlog-guard-")
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)
        self.home = self.dir / "home"
        self.home.mkdir()
        self.fake, self.log = write_recording_backlog(self.dir)
        self.runner = BacklogRunner(str(self.fake), self.home)

    def test_allowed_first_words_are_exactly_the_pinned_list(self):
        self.assertEqual(ALLOWED_FIRST_WORDS, ("init", "task", "doctor", "config", "doc", "--version"))
        self.assertNotIn(SUBCOMMAND, ALLOWED_FIRST_WORDS)

    def test_refuses_the_subcommand_and_anything_not_allowed_without_spawning(self):
        refused = (
            [SUBCOMMAND],
            [SUBCOMMAND, "--help"],
            [SUBCOMMAND, "--port", "0"],
            ["--help"],
            ["mcp", "start"],
            ["board"],
            ["Task", "list"],
            [" task"],
            [""],
            [],
            ["--project", "x", "task"],
        )
        for argv in refused:
            with self.subTest(argv=argv):
                with self.assertRaises(ForbiddenBacklogCommand):
                    self.runner.run(argv, cwd=self.dir, check=False)
        self.assertEqual(calls(self.log), [])

    def test_allowed_words_reach_the_binary_with_temp_home_and_minimal_env(self):
        for word in ALLOWED_FIRST_WORDS:
            self.runner.run([word, "--help"] if word != "--version" else [word], cwd=self.dir)
        recorded = calls(self.log)
        self.assertEqual([call["argv"][0] for call in recorded], list(ALLOWED_FIRST_WORDS))
        for call in recorded:
            self.assertEqual(call["home"], str(self.home))
            self.assertNotIn("BACKLOG_CWD", call["keys"])
            self.assertNotIn(support.BIN_ENV, call["keys"])

    def test_contract_tests_spawn_backlog_only_through_the_runner(self):
        for path in sorted(Path(__file__).parent.glob("test_*.py")):
            if path.name == Path(__file__).name:
                continue  # this file names the forbidden calls in its own assertions
            with self.subTest(path=path.name):
                source = path.read_text(encoding="utf-8")
                self.assertNotIn("subprocess", source)
                self.assertNotIn("os.system", source)
                self.assertNotIn("shell=True", source)
        support_source = Path(support.__file__).read_text(encoding="utf-8")
        self.assertEqual(support_source.count("[self.binary, *argv]"), 1)
        self.assertNotIn("shell=True", support_source)


class StaticSubcommandScanTests(unittest.TestCase):
    def test_no_invocation_in_folio_scripts_or_tests(self):
        self.assertEqual(subcommand_invocations(REPO_ROOT), [])

    def test_scan_catches_planted_invocations_and_ignores_unrelated_uses(self):
        planted = (
            "backlog " + SUBCOMMAND,
            "npx Backlog.md  " + SUBCOMMAND + " --port 6431",
            'subprocess.run(["backlog", "' + SUBCOMMAND + '"])',
            "spawn(bin, ['" + SUBCOMMAND + "', '--help'])",
            "argv = (BACKLOG_BIN, '" + SUBCOMMAND + "')",
        )
        unrelated = (
            'return "' + SUBCOMMAND + '"',
            'if auth == "' + SUBCOMMAND + '" and token:',
            "a " + SUBCOMMAND + " session opens the board",
            SUBCOMMAND + "_token = secrets.token_hex(n)",
            "backlog " + SUBCOMMAND + "s are mentioned here",
        )
        with tempfile.TemporaryDirectory(prefix="folio-backlog-scan-") as tmp:
            for directory in SCANNED:
                (Path(tmp) / directory).mkdir()
            (Path(tmp) / "scripts" / "planted.py").write_text("\n".join(planted) + "\n", encoding="utf-8")
            (Path(tmp) / "folio" / "unrelated.py").write_text("\n".join(unrelated) + "\n", encoding="utf-8")
            (Path(tmp) / "tests" / "blob.bin").write_bytes(b"\xff\xfe\x00backlog " + SUBCOMMAND.encode())
            hits = subcommand_invocations(tmp)
        self.assertEqual([hit.split(":")[1] for hit in hits], [str(n) for n in range(1, len(planted) + 1)])
        self.assertTrue(all(hit.startswith("scripts/planted.py:") for hit in hits), hits)
