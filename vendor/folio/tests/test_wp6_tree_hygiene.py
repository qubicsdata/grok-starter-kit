"""WP-6 red tests (tree): the internal records folder is absent; the tree holds no Mac home, Linux home or macOS temp
path (the WP-0b BLOCKING rule, run early) and no raw bidi override or isolate character (counted as
decoded code points per file, never bytes or lines); the cut scripts, modules and UI assets are gone;
the app's Python is at most 3,000 lines without plugins; there are 0 runtime dependencies.

Every needle is built from fragments or escapes so this file never matches its own scans; the scanners
are proven against planted files.
"""

import re
import tempfile
import unittest
from pathlib import Path

from wp6_support import (FOLIO, PYPROJECT, REPO_ROOT, SCRIPTS, STATIC, TESTS, app_python_files, bidi_counts, bidi_hits,
                         describe_bidi, line_count, local_path_hits, tree_files)

MAX_APP_LINES = 3000
SUPERPOWERS = REPO_ROOT / (".super" + "powers")
CUT_SCRIPT_GLOBS = ("build-*.py", "install-folio*.py", "homebrew-formula.py", "verify-*.py")
CUT_FILES = ("folio/windows_desktop.py", "folio/folder_picker.py", "folder_picker.py", "folio/guide.py", "folio/guide.md",
             "folio/static/theme.js")
CUT_UI_STRINGS = ("/api/demo", "/api/folders/pick", "/api/doctor", "/api/backup", "/export", "appearance-theme", "FolioTheme", "theme.js")


# WP6-2: the internal records folder is deleted by the maintainer after the records move, not by a job. The two tree-wide
# scans below turn themselves back on once the directory is gone; the absence test keeps an explicit skip
# that the same change removes.
SUPERPOWERS_PENDING = "records move pending; the maintainer removes the internal records folder (and this skip) in the same change"


class SuperpowersAbsentTests(unittest.TestCase):
    @unittest.skip(SUPERPOWERS_PENDING)
    def test_superpowers_directory_is_absent(self):
        self.assertFalse(SUPERPOWERS.exists(), "%s is still in the tree (%d files)"
                         % (SUPERPOWERS.name, len(tree_files(SUPERPOWERS)) if SUPERPOWERS.is_dir() else 0))


def describe_paths(hits):
    by_file = {}
    for hit in hits:
        by_file.setdefault(hit.split(":", 1)[0], []).append(hit)
    return "%d local_path lines in %d files: %s" % (len(hits), len(by_file),
                                                     "; ".join("%s x%d" % (name, len(lines)) for name, lines in sorted(by_file.items())))


class LocalPathTests(unittest.TestCase):
    @unittest.skipIf(SUPERPOWERS.exists(), SUPERPOWERS_PENDING)
    def test_no_local_home_or_mac_temp_path_in_the_tree(self):
        hits = local_path_hits()
        self.assertEqual(hits, [], describe_paths(hits))

    def test_no_local_home_or_mac_temp_path_outside_superpowers(self):
        """The R-b cleanup list (WP-0a: every match outside the internal records folder) is empty: 0 of the 75 at the WP6-1 red."""
        hits = [hit for hit in local_path_hits() if hit.split("/", 1)[0] != SUPERPOWERS.name]
        self.assertEqual(hits, [], describe_paths(hits))

    def test_scanner_catches_planted_paths_and_ignores_linuxbrew(self):
        with tempfile.TemporaryDirectory(prefix="folio-wp6-paths-") as tmp:
            root = Path(tmp)
            (root / "a.md").write_text("see /" + "Users" + "/someone/repo\n", encoding="utf-8")
            (root / "b.log").write_text("Data: /" + "private/var/folders" + "/ab/cdefghijklmnop/T/x\n", encoding="utf-8")
            (root / "c.py").write_text('HOME = "/' + 'home' + '/u"\nBREW = "/' + 'home' + '/linuxbrew/.linuxbrew"\n', encoding="utf-8")
            (root / "d.png").write_bytes(b"\x89PNG\r\n\x1a\n\xff\xfe /" + b"Users" + b"/x")
            hits = local_path_hits(root)
        self.assertEqual(hits, ["a.md:1: local_path.users", "b.log:1: local_path.tmp", "c.py:1: local_path.home"])


class BidiTests(unittest.TestCase):
    @unittest.skipIf(SUPERPOWERS.exists(), SUPERPOWERS_PENDING)
    def test_no_raw_bidi_override_or_isolate_character_in_the_tree(self):
        hits = bidi_hits()
        total = sum(sum(counts.values()) for counts in hits.values())
        self.assertEqual(hits, {}, "%d raw bidi characters in %d files: %s" % (total, len(hits), describe_bidi(hits)))

    def test_no_raw_bidi_character_outside_superpowers(self):
        """The plan v1.1 rule: 0 outside the internal records folder (6 at 7bae758; 0 on this base, recorded in the report)."""
        hits = {path: counts for path, counts in bidi_hits().items() if path.split("/", 1)[0] != SUPERPOWERS.name}
        self.assertEqual(hits, {}, describe_bidi(hits))

    def test_counter_counts_code_points_not_bytes(self):
        text = "a" + "\u202e" * 2 + "b" + "\u2066" + "\u2069" + "\n"
        self.assertEqual(len(text.encode("utf-8")), 3 + 4 * 3, "three ASCII bytes plus four 3-byte characters")
        counts = bidi_counts(text)
        self.assertEqual({ord(char): count for char, count in counts.items()}, {0x202E: 2, 0x2066: 1, 0x2069: 1})
        self.assertEqual(bidi_counts("plain \\u202e escape stays text\n"), {})

    def test_scanner_reports_a_planted_file_and_skips_binaries(self):
        with tempfile.TemporaryDirectory(prefix="folio-wp6-bidi-") as tmp:
            root = Path(tmp)
            (root / "planted.txt").write_text("x\u202ay\u202e\u202ez\u2068\n", encoding="utf-8")
            (root / "clean.py").write_text("print('\\u202e')\n", encoding="utf-8")
            (root / "blob.bin").write_bytes(b"\xff\xfe" + "\u202e".encode("utf-8"))
            hits = bidi_hits(root)
        self.assertEqual({path: {ord(c): n for c, n in counts.items()} for path, counts in hits.items()},
                         {"planted.txt": {0x202A: 1, 0x202E: 2, 0x2068: 1}})


class CutFilesTests(unittest.TestCase):
    def test_cut_scripts_are_absent(self):
        present = sorted(path.name for pattern in CUT_SCRIPT_GLOBS for path in SCRIPTS.glob(pattern)) if SCRIPTS.is_dir() else []
        self.assertEqual(present, [])

    def test_cut_modules_and_assets_are_absent(self):
        present = [name for name in CUT_FILES if (REPO_ROOT / name).exists()]
        self.assertEqual(present, [])

    def test_static_ui_references_no_cut_feature(self):
        index = (STATIC / "index.html").read_text(encoding="utf-8")
        self.assertNotIn("theme.js", index)
        app_js = (STATIC / "app.js").read_text(encoding="utf-8")
        found = [needle for needle in CUT_UI_STRINGS if needle in app_js]
        self.assertEqual(found, [])

    def test_pyproject_ships_no_guide(self):
        text = PYPROJECT.read_text(encoding="utf-8")
        self.assertNotIn("guide.md", text)
        self.assertRegex(text, r'(?m)^folio\s*=\s*\["static/\*"\]', msg="package-data keeps only static/*")

    @unittest.skip("the JSON store (core.py Store, registry.json, migration.py, backup.py) can only leave once the "
                   "Backlog-backed state path exists: WP-4 (wp/4-views-brief) and the WP-11 migrate/ read-only "
                   "reader are not in this stack; WP-6 on top of WP-4 and WP-11 removes this skip")
    def test_json_store_modules_are_absent(self):
        present = [name for name in ("folio/backup.py", "folio/migration.py") if (REPO_ROOT / name).exists()]
        self.assertEqual(present, [])


class SizeAndDependencyTests(unittest.TestCase):
    @unittest.skipIf((FOLIO / "migration.py").exists(),
                     "the <= 3,000-line budget needs the JSON store gone (core.py Store, migration.py, backup.py), which waits "
                     "for WP-4 (wp/4-views-brief) and the WP-11 migrate/ reader; WP-6 on top of WP-4 and WP-11 removes this skip")
    def test_app_python_is_at_most_3000_lines_without_plugins(self):
        files = app_python_files()
        total = line_count(files)
        largest = sorted(((line_count([path]), path.relative_to(REPO_ROOT).as_posix()) for path in files), reverse=True)[:6]
        self.assertLessEqual(total, MAX_APP_LINES, "%d lines in %d files; largest: %s"
                             % (total, len(files), ", ".join("%s %d" % (name, count) for count, name in largest)))

    def test_zero_runtime_dependencies(self):
        text = PYPROJECT.read_text(encoding="utf-8")
        self.assertNotRegex(text, r"^\s*dependencies\s*=\s*\[\s*[^\]\s]", re.MULTILINE)
        self.assertNotIn("optional-dependencies", text)
        for name in ("requirements.txt", "setup.py", "setup.cfg"):
            self.assertFalse((REPO_ROOT / name).exists(), name)


if __name__ == "__main__":
    unittest.main()
