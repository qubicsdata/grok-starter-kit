"""WP-7 red tests: the Switchboard freeze (M-3, D-18).

Acceptance: folio/switchboard/ is deleted with its routes, badges, sync thread, fakes and tests; no
`switchboard` reference remains in folio/ (any file, case-insensitive) except the one reserved-name
declaration in folio/core.py (ALLOWED below, added in WP7-3); the README carries the freeze
note naming tag archive/switchboard-1.1.2; the archive refs resolve to a commit that contains
folio/switchboard/ (verified read-only, only once the maintainer has pushed them: G-1).

The reference scanner is checked against planted hits so a silent miss cannot pass. This module's own
name avoids the word so the tests/ glob below does not match it.
"""

import inspect
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

from wp7_support import FOLIO, REPO_ROOT, TESTS

README = REPO_ROOT / "README.md"
TAG = "archive/switchboard-1.1.2"
BRANCH = "archive/switchboard"
WORD = re.compile(rb"switchboard", re.IGNORECASE)
G1_SKIP = "%s and %s are pushed by the maintainer at the WP-7 merge (G-1); neither ref is in this clone" % (TAG, BRANCH)
# The one sanctioned mention (WP7-3): the frozen integration's name, declared once in folio/core.py so
# that its plugin prefix stays reserved (/api/plugins/switchboard/* 404, WP-7 security test) and Folio
# 1.1.x activity records whose origin is that name still load. Matched on the exact stripped line, so
# any other code, comment or file that spells the name is still reported.
ALLOWED = frozenset({("folio/core.py", b'FROZEN = "switchboard"')})


def references(root=FOLIO, allowed=ALLOWED):
    """["<path>:<line>"] for every line in any file under root that mentions switchboard (minus `allowed`)."""
    hits = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or "__pycache__" in path.parts:
            continue
        relative = path.relative_to(root.parent).as_posix()
        for lineno, line in enumerate(path.read_bytes().splitlines(), 1):
            if WORD.search(line) and (relative, line.strip()) not in allowed:
                hits.append("%s:%d" % (relative, lineno))
    return hits


def git(*args):
    """Read-only git plumbing against the repo (fixed argv, never a mutating command)."""
    assert args[0] in ("rev-parse", "ls-tree", "merge-base"), args
    return subprocess.run(["git", *args], cwd=str(REPO_ROOT), capture_output=True, text=True, timeout=60)


class FreezeTests(unittest.TestCase):
    def test_the_switchboard_package_is_gone(self):
        self.assertFalse((FOLIO / "switchboard").exists(), "folio/switchboard/ is still in the tree")

    def test_no_switchboard_reference_remains_in_folio(self):
        hits = references()
        self.assertEqual(hits, [], "%d switchboard references in folio/ (first 25): %s" % (len(hits), hits[:25]))

    def test_the_switchboard_fakes_and_tests_are_gone(self):
        left = sorted(str(path.relative_to(REPO_ROOT)) for path in TESTS.glob("*switchboard*"))
        self.assertEqual(left, [])

    def test_the_server_app_builder_has_no_sync_switches(self):
        from folio import web
        from folio.api import build_app
        parameters = set(inspect.signature(build_app).parameters)
        self.assertFalse(parameters & {"sync_enabled", "switchboard_home", "notifications"}, parameters)
        self.assertFalse(hasattr(web, "start_sync"), "the sync thread starter is still in folio/web.py")

    def test_the_readme_carries_the_freeze_note(self):
        text = README.read_text(encoding="utf-8")
        lines = [line for line in text.splitlines() if TAG in line]
        self.assertTrue(lines, "README.md does not mention the archive tag %s" % TAG)
        note = " ".join(lines).lower()
        self.assertIn("frozen", note)
        self.assertIn("plugin", note)
        self.assertIn("`%s`" % BRANCH, text, "README.md does not name the archive branch %s" % BRANCH)


class ArchiveRefsTests(unittest.TestCase):
    """The archive refs are pushed by the maintainer at the WP-7 merge (G-1); verified read-only when present."""

    def resolve(self, ref):
        proc = git("rev-parse", "-q", "--verify", ref + "^{commit}")
        return proc.stdout.strip() if proc.returncode == 0 else None

    def test_archive_refs_resolve_to_a_commit_containing_the_switchboard_package(self):
        found = {name: sha for name, sha in ((TAG, self.resolve("refs/tags/" + TAG)), (BRANCH, self.resolve("refs/heads/" + BRANCH))) if sha}
        if not found:
            self.skipTest(G1_SKIP)
        head = self.resolve("HEAD")
        for name, sha in found.items():
            with self.subTest(ref=name):
                self.assertRegex(sha, r"^[0-9a-f]{40}$")
                tree = git("ls-tree", "-d", sha, "--", "folio/switchboard")
                self.assertTrue(tree.stdout.startswith("040000 tree"), "%s -> %s does not contain folio/switchboard/" % (name, sha))
                self.assertEqual(git("merge-base", "--is-ancestor", sha, head).returncode, 0,
                                 "%s -> %s is not an ancestor of HEAD" % (name, sha))
        if len(found) == 2:
            self.assertEqual(found[TAG], found[BRANCH], "the archive tag and branch point at different commits")
        # Once the refs exist, the committed tree must no longer ship the package.
        self.assertEqual(git("ls-tree", "-d", "HEAD", "--", "folio/switchboard").stdout, "")


class ScannerSelfTests(unittest.TestCase):
    def plant(self, files):
        tmp = tempfile.TemporaryDirectory(prefix="folio-wp7-scan-")
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name) / "folio"
        root.mkdir()
        for name, data in files.items():
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data if isinstance(data, bytes) else data.encode("utf-8"))
        return root

    def test_a_clean_tree_has_no_hits(self):
        root = self.plant({"__init__.py": "x = 1\n", "static/app.js": "const sync = 'off';\n", "guide.md": "# Guide\n",
                           "__pycache__/x.cpython-313.pyc": b"Switchboard"})
        self.assertEqual(references(root), [])

    def test_planted_hits_are_reported_in_every_file_type(self):
        root = self.plant({"api.py": "a = 1\n# Switchboard arrives later\n", "static/app.js": "badge('switchboard');\n",
                           "static/styles.css": ".SWITCHBOARD-badge {}\n", "guide.md": "Sync with Switchboard.\n",
                           "switchboard/__init__.py": "", "static/icon.png": b"\x89PNG\x00switchboard\x00"})
        self.assertEqual(references(root), ["folio/api.py:2", "folio/guide.md:1", "folio/static/app.js:1",
                                            "folio/static/icon.png:1", "folio/static/styles.css:1"])

    def test_only_the_exact_declaration_in_core_is_allowed(self):
        root = self.plant({"core.py": 'x = 1\n    FROZEN = "switchboard"  \nFROZEN = "switchboard"  # note\nFROZEN = "Switchboard"\n',
                           "api.py": 'FROZEN = "switchboard"\n', "plugins/core.py": 'FROZEN = "switchboard"\n'})
        self.assertEqual(references(root), ["folio/api.py:1", "folio/core.py:3", "folio/core.py:4", "folio/plugins/core.py:1"])
        self.assertEqual(len(references(root, allowed=frozenset())), 5)

    def test_the_declaration_is_the_reserved_plugin_name(self):
        from folio import core
        from folio.plugins import RESERVED
        self.assertEqual(RESERVED, frozenset({core.FROZEN}))
        declared = [line.strip() for line in (FOLIO / "core.py").read_bytes().splitlines() if WORD.search(line)]
        self.assertEqual(declared, [b'FROZEN = "switchboard"'])


if __name__ == "__main__":
    unittest.main()
