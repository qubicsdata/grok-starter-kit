"""License checks: Apache-2.0 text in every component, NOTICE per the owner decision."""

import hashlib
import os
import re
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# SHA-256 of the canonical Apache License 2.0 text (the staged reference copy).
APACHE_2_SHA256 = "cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30"

LICENSE_FILES = [
    "LICENSE",
    "runner/LICENSE",
    "vendor/accelerator/LICENSE",
    "second-brain/LICENSE",
]

# The company word is built from fragments so it appears only in NOTICE.
COMPANY = "Qubics" + "Data"

# The only files that may carry the company word: the kit's NOTICE, Folio's NOTICE and
# the NOTICE copy Folio's UI serves. Exact paths, not a name pattern, so a NOTICE file
# anywhere else still fails.
NOTICE_LOCATIONS = (
    "NOTICE",
    os.path.join("vendor", "folio", "NOTICE"),
    os.path.join("vendor", "folio", "folio", "static", "NOTICE.txt"),
)


def read_bytes(rel):
    with open(os.path.join(ROOT, rel), "rb") as handle:
        return handle.read()


def sha256_of(rel):
    return hashlib.sha256(read_bytes(rel)).hexdigest()


def license_files_in_tree():
    found = []
    for base, dirs, files in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in (".git", "__pycache__", "node_modules")]
        for name in files:
            if name in ("LICENSE", "LICENSE.txt", "LICENSE.md"):
                found.append(os.path.relpath(os.path.join(base, name), ROOT))
    return sorted(found)


def company_word_hits(root):
    """Paths under root, other than NOTICE_LOCATIONS and this file, that carry the company word."""
    hits = []
    for base, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in (".git", "__pycache__", "node_modules")]
        for name in files:
            rel = os.path.relpath(os.path.join(base, name), root)
            if rel in NOTICE_LOCATIONS or rel == os.path.join("tests", "test_licenses.py"):
                continue
            with open(os.path.join(base, name), "rb") as handle:
                if COMPANY.encode() in handle.read():
                    hits.append(rel)
    return sorted(hits)


class LicenseTests(unittest.TestCase):
    def test_required_license_files_exist(self):
        for rel in LICENSE_FILES:
            self.assertTrue(os.path.isfile(os.path.join(ROOT, rel)), rel)

    def test_no_pending_in_any_license_file(self):
        for rel in license_files_in_tree():
            text = read_bytes(rel).decode("utf-8", "replace")
            self.assertNotIn("PENDING", text.upper(), rel)

    def test_each_license_is_the_reference_text(self):
        for rel in LICENSE_FILES:
            self.assertEqual(sha256_of(rel), APACHE_2_SHA256, rel)

    def test_license_files_agree_with_top_level(self):
        top = sha256_of("LICENSE")
        for rel in license_files_in_tree():
            if rel.startswith("vendor/folio/"):
                continue
            self.assertEqual(sha256_of(rel), top, rel)


class NoticeTests(unittest.TestCase):
    def setUp(self):
        self.lines = read_bytes("NOTICE").decode("utf-8").splitlines()

    def test_copyright_line_exact(self):
        self.assertIn("Copyright " + COMPANY, self.lines)
        copyright_lines = [l for l in self.lines if "Copyright" in l]
        self.assertEqual(copyright_lines, ["Copyright " + COMPANY])

    def test_no_placeholders(self):
        text = "\n".join(self.lines)
        self.assertNotRegex(text, r"<[a-z-]+>")

    def test_points_to_vendored_and_backlog(self):
        text = "\n".join(self.lines)
        self.assertIn("VENDORED.md", text)
        self.assertIn("Backlog.md is not included", text)

    def test_no_other_proper_names(self):
        allowed = {COMPANY, "Copyright", "NOTICE", "Starter", "This", "Component", "Backlog",
                   "VENDORED", "EXTERNAL", "DEPENDENCIES", "MIT", "Md", "MD", "Apache"}
        for line in self.lines:
            words = re.findall(r"\b[A-Z][A-Za-z]+\b", line)
            for word in words:
                self.assertIn(word, allowed, line)

    def test_company_word_only_in_notice_files(self):
        self.assertEqual(company_word_hits(ROOT), [])

    def test_every_notice_location_exists_with_the_word(self):
        for rel in NOTICE_LOCATIONS:
            self.assertIn(COMPANY.encode(), read_bytes(rel), rel)

    def test_word_in_any_other_notice_file_fails(self):
        planted = [
            "NOTICE.txt",
            os.path.join("docs", "NOTICE.txt"),
            os.path.join("second-brain", "NOTICE"),
            os.path.join("vendor", "folio", "NOTICE.txt"),
            os.path.join("vendor", "folio", "folio", "NOTICE.txt"),
            os.path.join("vendor", "folio", "folio", "static", "NOTICE"),
        ]
        with tempfile.TemporaryDirectory() as root:
            for rel in list(NOTICE_LOCATIONS) + planted:
                os.makedirs(os.path.join(root, os.path.dirname(rel)), exist_ok=True)
                with open(os.path.join(root, rel), "w", encoding="utf-8") as handle:
                    handle.write("Copyright " + COMPANY + "\n")
            self.assertEqual(company_word_hits(root), sorted(planted))


class VendoredTableTests(unittest.TestCase):
    def test_license_column_has_no_pending(self):
        text = read_bytes("VENDORED.md").decode("utf-8")
        self.assertNotIn("pending", text.lower())
        self.assertNotIn("proposed", text.lower())

    def test_apache_listed(self):
        text = read_bytes("VENDORED.md").decode("utf-8")
        self.assertGreaterEqual(text.count("Apache-2.0"), 7)


if __name__ == "__main__":
    unittest.main()
