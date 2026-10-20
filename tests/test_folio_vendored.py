"""Checks for the vendored Folio copy (vendor/folio): what is in, what is out, the NOTICE wording,
the generic placeholders and a clean kit scan.

Every value a scan rule would match (the company word, the owner's channel token) is assembled from
fragments at run time, so this file holds none of them. Stdlib only, Python 3.9+.
"""

import os
import re
import subprocess
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FOLIO = os.path.join(ROOT, "vendor", "folio")
CLEAN_SCAN = os.path.join(ROOT, "tools", "clean_scan.py")
VENDORED_MD = os.path.join(ROOT, "VENDORED.md")

# The company word may appear only in NOTICE files (owner decision 2). Fragments, never the word.
ORG_WORD = "Qubics" + "Data"
ORG_WORD_LOWER = ORG_WORD.lower()
# The owner's channel token: a two-letter prefix, a hyphen, one letter. Fragments only.
CHANNEL_TOKEN = "ch" + "-" + "q"
CHANNEL_TOKEN_UNDERSCORE = CHANNEL_TOKEN.replace("-", "_")
CHANNEL_TOKEN_RE = re.compile(
    r"(?<![A-Za-z0-9])(%s|%s)(?![A-Za-z0-9])" % (re.escape(CHANNEL_TOKEN), re.escape(CHANNEL_TOKEN_UNDERSCORE)),
    re.IGNORECASE,
)
# The internal session-records folder name (the scan flags any mention of it). Fragments only.
RECORDS_DIR = "." + "super" + "powers"

NOTICE_FILES = ("NOTICE", os.path.join("folio", "static", "NOTICE.txt"))

REQUIRED_FILES = (
    "LICENSE",
    "NOTICE",
    "KIT-README.md",
    "README.md",
    "pyproject.toml",
    "bin/folio",
    "folio/__init__.py",
    "folio/web.py",
    "folio/static/app.js",
    "folio/static/index.html",
    "folio/static/LICENSE.txt",
    "folio/static/NOTICE.txt",
    "tests/test_cli.py",
    "docs/local-security.md",
)

# Left out on purpose: internal records, the plan and its reviews, release records, build scripts.
EXCLUDED_PATHS = (
    ".git",
    RECORDS_DIR,
    "docs/acceptance",
    "docs/releases",
    "docs/superpowers",
    "docs/mac-readiness-2026-09-18.md",
    "docs/mac-handoff-checklist.md",
    "scripts/homebrew-formula.py",
    "folio/switchboard",
)
EXCLUDED_NAME_PATTERNS = (
    re.compile(r"^build-.*"),          # scripts/build-* (Homebrew/standalone bundles)
    re.compile(r"^homebrew.*"),
    re.compile(r".*\.(diff|patch)$"),  # review diffs
)

BINARY_EXTENSIONS = (".png", ".ico", ".jpg", ".jpeg", ".gif", ".woff", ".woff2", ".ttf")


def walk_files():
    for dirpath, dirnames, filenames in os.walk(FOLIO):
        dirnames[:] = sorted(d for d in dirnames if d != "__pycache__")
        for name in sorted(filenames):
            if name.endswith(".pyc"):
                continue
            path = os.path.join(dirpath, name)
            yield os.path.relpath(path, FOLIO).replace(os.sep, "/"), path


def read_text(path):
    with open(path, "rb") as handle:
        return handle.read().decode("utf-8", "replace")


class VendoredTreeTest(unittest.TestCase):
    def test_required_files_present(self):
        missing = [p for p in REQUIRED_FILES if not os.path.isfile(os.path.join(FOLIO, p))]
        self.assertEqual(missing, [], "missing vendored Folio files")

    def test_excluded_paths_absent(self):
        present = [p for p in EXCLUDED_PATHS if os.path.exists(os.path.join(FOLIO, p))]
        self.assertEqual(present, [], "excluded paths found in vendor/folio")

    def test_no_excluded_name_patterns(self):
        hits = []
        for rel, _ in walk_files():
            name = rel.rsplit("/", 1)[-1]
            if any(p.match(name) for p in EXCLUDED_NAME_PATTERNS):
                hits.append(rel)
        self.assertEqual(hits, [], "build script or review diff found")

    def test_tree_is_not_a_placeholder(self):
        # The design placeholder was a lone README.md; the vendored tree has real code and tests.
        rels = [rel for rel, _ in walk_files()]
        self.assertGreater(len(rels), 50, "vendor/folio looks like the design placeholder")
        self.assertTrue(any(rel.startswith("tests/") for rel in rels))


class NoticeTest(unittest.TestCase):
    def notice_texts(self):
        return [(rel, read_text(os.path.join(FOLIO, rel))) for rel in NOTICE_FILES]

    def test_notice_files_exist_and_match(self):
        texts = self.notice_texts()
        for rel, text in texts:
            self.assertTrue(text.strip(), "%s is empty" % rel)
        self.assertEqual(texts[0][1], texts[1][1], "NOTICE and the static NOTICE copy differ")

    def test_notice_wording_is_the_company_copyright_line(self):
        for rel, text in self.notice_texts():
            with self.subTest(file=rel):
                lines = [line.strip() for line in text.splitlines()]
                self.assertIn("Copyright " + ORG_WORD, lines, "the decided copyright line is missing")
                lowered = text.lower()
                self.assertNotIn("http", lowered, "no URL in NOTICE")
                self.assertNotIn("originally developed", lowered, "no attribution line in NOTICE")
                self.assertNotIn("contributors", lowered, "no contributor wording in NOTICE")
                self.assertIn("apache license", lowered)

    def test_notice_holds_no_year_or_personal_name(self):
        for rel, text in self.notice_texts():
            with self.subTest(file=rel):
                self.assertIsNone(re.search(r"\b(19|20)\d\d\b", text), "no year in NOTICE")
                # Every line is one of the allowed shapes; a personal name would be another line.
                for line in text.splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    ok = (
                        line == "Folio"
                        or line == "Copyright " + ORG_WORD
                        or "Apache License" in line
                        or line.startswith("See LICENSE")
                        or line.startswith("Version 2.0")
                    )
                    self.assertTrue(ok, "unexpected NOTICE line")


class PlaceholderTest(unittest.TestCase):
    def test_company_word_only_in_notice_files(self):
        hits = []
        for rel, path in walk_files():
            if rel in NOTICE_FILES or rel.endswith(BINARY_EXTENSIONS):
                continue
            if ORG_WORD_LOWER in read_text(path).lower():
                hits.append(rel)
        self.assertEqual(hits, [], "company word outside NOTICE files")

    def test_company_word_not_in_file_names(self):
        hits = [rel for rel, _ in walk_files() if ORG_WORD_LOWER in rel.lower()]
        self.assertEqual(hits, [])

    def test_owner_channel_token_absent(self):
        hits = []
        for rel, path in walk_files():
            if rel.endswith(BINARY_EXTENSIONS):
                continue
            if CHANNEL_TOKEN_RE.search(read_text(path)) or CHANNEL_TOKEN_RE.search(rel):
                hits.append(rel)
        self.assertEqual(hits, [], "owner channel token found")

    def test_channel_token_detector_catches_every_planted_shape(self):
        # The shapes the copy used to hold: bare, as a repo suffix, as a file prefix, with underscores, upper case.
        planted = (
            "the " + CHANNEL_TOKEN + " channel",
            "tasks-" + CHANNEL_TOKEN + ".git",
            CHANNEL_TOKEN + "-allow-list.json",
            "folio_tasks_" + CHANNEL_TOKEN_UNDERSCORE + ".pub",
            CHANNEL_TOKEN.upper(),
        )
        for text in planted:
            with self.subTest(shape=text.replace(CHANNEL_TOKEN, "<token>")):
                self.assertTrue(CHANNEL_TOKEN_RE.search(text))
        self.assertIsNone(CHANNEL_TOKEN_RE.search("example-channel and tasks-example-channel"))

    def test_company_word_detector_is_case_insensitive(self):
        for text in (ORG_WORD, ORG_WORD.lower(), ORG_WORD.upper(), "github.com/" + ORG_WORD.lower() + "/x"):
            with self.subTest(shape=text.replace(ORG_WORD, "<word>").replace(ORG_WORD.lower(), "<word>")):
                self.assertIn(ORG_WORD_LOWER, text.lower())
        self.assertNotIn(ORG_WORD_LOWER, "Example Org and example-org".lower())

    def test_generic_placeholders_are_used(self):
        web = read_text(os.path.join(FOLIO, "folio", "web.py"))
        # The About texts come from Folio's local config (empty by default), never from the code.
        api = read_text(os.path.join(FOLIO, "folio", "api.py"))
        self.assertIn("def product_info(", api)
        for text in (web, api):
            self.assertNotIn("Example Org", text)
        pyproject = read_text(os.path.join(FOLIO, "pyproject.toml"))
        self.assertNotIn("github.com/" + ORG_WORD_LOWER, pyproject.lower())

    def test_kit_readme_carries_the_design_notes(self):
        text = read_text(os.path.join(FOLIO, "KIT-README.md"))
        for needle in ("folio.enabled", "folio.task_sync", "folio.machine_profile", "backlog browser", "127.0.0.1",
                       "Example Org", "kit.author_name"):
            with self.subTest(needle=needle):
                self.assertIn(needle, text)


class ScanTest(unittest.TestCase):
    def test_kit_clean_scan_of_vendor_folio_is_zero(self):
        env = dict(os.environ)
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        proc = subprocess.run(
            [sys.executable, CLEAN_SCAN, FOLIO],
            cwd=ROOT,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            timeout=600,
        )
        lines = proc.stdout.splitlines()
        self.assertEqual(proc.returncode, 0, "scan found something: " + ", ".join(lines))
        self.assertIn("TOTAL 0", lines)

    def test_no_bidi_or_control_characters_in_text_files(self):
        bad = re.compile("[\u202a-\u202e\u2066-\u2069\x00-\x08\x0b\x0c\x0e-\x1f\x7f\x80-\x9f]")
        hits = []
        for rel, path in walk_files():
            if rel.endswith(BINARY_EXTENSIONS):
                continue
            if bad.search(read_text(path)):
                hits.append(rel)
        self.assertEqual(hits, [])


class VendoredRecordTest(unittest.TestCase):
    def test_vendored_md_folio_row_has_the_full_source_sha(self):
        text = read_text(VENDORED_MD)
        rows = [line for line in text.splitlines() if "`vendor/folio/`" in line]
        self.assertEqual(len(rows), 1, "exactly one Folio row in VENDORED.md")
        # Joined at run time: a release tree must hold no build-time placeholder, this file included.
        self.assertNotIn("-".join(("<sha", "filled", "at", "build>")), rows[0])
        cells = [cell.strip() for cell in rows[0].split("|")]
        sha_cell = cells[3]
        self.assertTrue(sha_cell.startswith("`") and sha_cell.endswith("`"), "the Source sha cell is one code span")
        sha = sha_cell[1:-1].strip()
        self.assertIsNotNone(re.fullmatch(r"[0-9a-f]{40}", sha), "the whole Source sha cell is a full 40-character sha")
        self.assertEqual(sha, "45a8d5934c102d9dd8a61f68f3ec70b8398862f8")
        self.assertIn("Apache-2.0", rows[0])


if __name__ == "__main__":
    unittest.main()
