"""Privacy guard over the whole runner/ tree (code, tests, fixtures, docs): everything here must be synthetic.

Rules, applied to file contents AND to every file and folder name:
  EMAIL     an address outside example.com / example.org / example.net and *.invalid
  UUID      a UUID that is not all zeros
  HOMEPATH  a home path other than /home/user (other Linux homes, macOS homes, the macOS per-user temp root,
            the container workspace root)
  BIDI      bidi controls (U+202A-U+202E, U+2066-U+2069, U+200E, U+200F, U+061C)
  CTRL      other control characters (TAB, LF and CR are allowed)
  REALNAME  a `*_real_*` file name (the naming of real captures)
Offenders are reported as "<relative path>: <rule>" only, never with the matched text. Real `claude /usage`
captures and stream logs carry account data and never belong here: regenerate the fixtures with
tests/make_synthetic_fixtures.py instead. Planted values in this file are assembled at run time."""
import os, re, tempfile, unittest
from helpers import RUNNER_DIR


def _j(*parts):
    return "".join(parts)


EXAMPLE_DOMAINS = ("example.com", "example.org", "example.net")
EMAIL = re.compile(r"(?<![A-Za-z0-9._%+-])[A-Za-z0-9._%+-]+@((?:[A-Za-z0-9-]+\.)+[A-Za-z0-9-]+)")
UUID = re.compile(r"(?<![0-9A-Fa-f-])[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12}"
                  r"(?![0-9A-Fa-f-])")
_L = r"(?<![A-Za-z0-9_.~-])"
HOMEPATH = (
    re.compile(_L + "/home/" + r"(?!user(?![A-Za-z0-9._-]))[A-Za-z0-9._-]+"),
    re.compile(_L + re.escape(_j("/Us", "ers/")) + r"[A-Za-z0-9._-]+"),
    re.compile(_L + r"(?:/private)?" + re.escape(_j("/var/", "folders/"))),
    re.compile(_L + re.escape(_j("/work", "space")) + r"(?![A-Za-z0-9_-])"),
)
BIDI = re.compile("[\u202a-\u202e\u2066-\u2069\u200e\u200f\u061c]")
CTRL = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]")
REALNAME = re.compile(r"_real_", re.IGNORECASE)
SKIP_DIRS = {"__pycache__"}


def _example_domain(d):
    d = d.lower().rstrip(".")
    if not re.fullmatch(r"[a-z]{2,}", d.rsplit(".", 1)[-1]):
        return True  # not an address (e.g. a version string or a regex fragment)
    return d.endswith(".invalid") or any(d == x or d.endswith("." + x) for x in EXAMPLE_DOMAINS)


def scan_text(text):
    """Set of rule codes hitting one text."""
    hits = set()
    if any(not _example_domain(m.group(1)) for m in EMAIL.finditer(text)):
        hits.add("EMAIL")
    if any(set(m.group(0)) - set("0-") for m in UUID.finditer(text)):
        hits.add("UUID")
    if any(r.search(text) for r in HOMEPATH):
        hits.add("HOMEPATH")
    if BIDI.search(text):
        hits.add("BIDI")
    if CTRL.search(text):
        hits.add("CTRL")
    return hits


def scan_name(name):
    hits = scan_text(name)
    if REALNAME.search(name):
        hits.add("REALNAME")
    return hits


def scan_tree(root):
    """Sorted ["<relative path>: <RULE>", ...] for every offending file or folder under root."""
    bad = set()
    for dp, dn, fn in os.walk(root):
        dn[:] = sorted(d for d in dn if d not in SKIP_DIRS)
        for n in dn + sorted(fn):
            p = os.path.join(dp, n)
            rel = os.path.relpath(p, root)
            for code in scan_name(n):
                bad.add("%s: %s" % (rel, code))
            if n in fn and not os.path.islink(p):
                with open(p, "rb") as f:
                    text = f.read().decode("utf-8", "replace")
                for code in scan_text(text):
                    bad.add("%s: %s" % (rel, code))
    return sorted(bad)


class RunnerTreePrivacy(unittest.TestCase):
    def test_runner_tree_is_synthetic(self):
        bad = scan_tree(RUNNER_DIR)
        self.assertEqual(bad, [], "non-synthetic data under runner/ (path: rule): %s" % bad)

    def test_fixture_folders_exist_and_are_scanned(self):
        for sub in ("fixtures", os.path.join("tests", "fixtures"), os.path.join("tests", "fakebin")):
            self.assertTrue(os.path.isdir(os.path.join(RUNNER_DIR, sub)), sub)

    def test_no_real_capture_names(self):
        names = [n for _, dn, fn in os.walk(RUNNER_DIR) for n in dn + fn]
        self.assertEqual([n for n in names if REALNAME.search(n)], [])

    def test_usage_fixtures_are_marked_synthetic(self):
        for dp, _, fn in os.walk(RUNNER_DIR):
            for n in fn:
                if n.startswith("usage_") and n.endswith(".txt"):
                    with open(os.path.join(dp, n), encoding="utf-8") as f:
                        self.assertIn("example", f.read().lower(), "%s does not look synthetic" % n)


class GuardCatchesPlantedData(unittest.TestCase):
    """Each rule fires on a planted value and stays quiet on the synthetic look-alike."""
    BAD = {
        "EMAIL": [_j("jane.doe", "@", "corp-mail.test.io"), _j("Email: someone", "@", "gmail.com")],
        "UUID": [_j("12345678", "-1234-5678-9abc-", "def012345678")],
        "HOMEPATH": [_j("/home/", "jane/notes"), _j("//home/", "jane/.claude"), _j("/Us", "ers/jane/x"),
                     _j("/private/var/", "folders/xy/T"), _j("cd ", "/work", "space/x")],
        "BIDI": ["a\u202eb", "a\u2066b", "a\u200fb"],
        "CTRL": ["a\x1b[0mb", "a\x00b", "a\x7fb", "a\x85b"],
    }
    GOOD = ["user@example.com", "a@sub.example.org", "x@example.net", "user@example.invalid", "backlog@localhost",
            "00000000-0000-0000-0000-000000000000", "/home/user/example-project", "~/example-project",
            "tab\there\r\n", "v2.1@0.0", "Current week (Fable): 4% used"]

    def test_each_rule_fires(self):
        for code, samples in self.BAD.items():
            for s in samples:
                with self.subTest(code=code, n=samples.index(s)):
                    self.assertIn(code, scan_text(s))

    def test_synthetic_values_pass(self):
        for s in self.GOOD:
            with self.subTest(n=self.GOOD.index(s)):
                self.assertEqual(scan_text(s), set())

    def test_real_capture_name_and_tree_report(self):
        self.assertEqual(scan_name(_j("usage_screen", "_real_", "1744.txt")), {"REALNAME"})
        self.assertEqual(scan_name("usage_screen_synthetic_1744.txt"), set())
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "ok.txt"), "w") as f:
                f.write("Email: user@example.invalid\nalso someone@example.com\n")
            self.assertEqual(scan_tree(d), [])
            with open(os.path.join(d, "bad.txt"), "w") as f:
                f.write("Email: " + _j("jane.doe", "@", "corp-mail.test.io") + "\n")
            os.makedirs(os.path.join(d, _j("x", "_real_", "y")))
            report = scan_tree(d)
            self.assertEqual(report, ["bad.txt: EMAIL", _j("x", "_real_", "y") + ": REALNAME"])
            self.assertNotIn("corp-mail", " ".join(report))  # path and rule only, never the value


if __name__ == "__main__":
    unittest.main()
