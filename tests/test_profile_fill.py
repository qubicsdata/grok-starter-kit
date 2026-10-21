"""Template value loading from the private business profile
(`tools/business_profile.py fill`) and the shipped templates that use it.

A template names a profile value as `{{key}}`; `second-brain/BUSINESS-PROFILE.md`
documents every key with a placeholder example. `fill` prints the filled
template and writes nothing; a key that is missing or still `unknown` stays
as it is, is named on stderr and gives exit 1; a malformed profile is exit 2
with a line number, never the line itself.

Profiles and templates here are synthetic and live in a temp dir.
`KIT_BUSINESS_PROFILE` points the suite at another copy of the tool.
Stdlib only, Python 3.9+.
"""

import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOL = os.environ.get("KIT_BUSINESS_PROFILE") or os.path.join(ROOT, "tools", "business_profile.py")

KEYS_DOC = os.path.join("second-brain", "BUSINESS-PROFILE.md")
DANCE = os.path.join("second-brain", "dance-school")
PLACEHOLDER_RE = re.compile(r"\{\{\s*([^{}\s]+)\s*\}\}")
KEY_ROW_RE = re.compile(r"^\|\s*`([a-z][a-z0-9_.]*)`\s*\|\s*`([^`]*)`\s*\|")
MARKER = "profile.private" + ": true"
SENTINEL = "quokka-sentinel-value"

# Templates that must take values from the profile.
PROFILE_TEMPLATES = (
    "classes-schedule/term-schedule-example.md",
    "finances/pass-pricing-table-template.md",
    "marketing/social/bilingual-post-template.md",
    "marketing/social/facebook-event-template.md",
    "marketing/social/whatsapp-broadcast-template.md",
    "marketing/campaigns/new-group-launch-campaign.md",
    "marketing/campaigns/trial-class-funnel.md",
    "marketing/targeting-per-location.md",
)


def read(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as fh:
        return fh.read()


def documented_keys():
    """{key: example value} from the key table of BUSINESS-PROFILE.md."""
    keys = {}
    for line in read(KEYS_DOC).splitlines():
        m = KEY_ROW_RE.match(line)
        if m:
            keys[m.group(1)] = m.group(2)
    return keys


def template_files():
    out = []
    for dirpath, dirnames, filenames in os.walk(os.path.join(ROOT, "second-brain")):
        dirnames[:] = sorted(d for d in dirnames if d not in ("bin", "tests"))
        for name in sorted(filenames):
            if name.endswith(".md"):
                out.append(os.path.relpath(os.path.join(dirpath, name), ROOT))
    return out


def digest(root):
    out = {}
    for dirpath, _, filenames in os.walk(root):
        for name in filenames:
            path = os.path.join(dirpath, name)
            with open(path, "rb") as fh:
                out[os.path.relpath(path, root)] = fh.read()
    return out


class FillTest(unittest.TestCase):
    def setUp(self):
        self.assertTrue(os.path.isfile(TOOL), "tools/business_profile.py is missing")
        self.tmp = tempfile.mkdtemp(prefix="kit-profile-fill-")
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def write(self, name, text):
        path = os.path.join(self.tmp, name)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
        return path

    def fill(self, profile_text, template_text, profile=None):
        prof = profile or self.write("business-profile.yaml", profile_text)
        tmpl = self.write("template.md", template_text)
        return subprocess.run(
            [sys.executable, "-B", TOOL, "fill", "--profile", prof, tmpl],
            cwd=self.tmp, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            universal_newlines=True, timeout=60,
        )

    def test_fills_keys_from_the_profile(self):
        proc = self.fill(
            MARKER + "\nschool.name: \"Example Dance School\"\nstudio.1.name: Studio A\n",
            "Welcome to {{school.name}} in {{ studio.1.name }}!\n",
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout, "Welcome to Example Dance School in Studio A!\n")

    def test_missing_and_unknown_keys_stay_and_are_named(self):
        proc = self.fill(
            MARKER + "\nschool.name: \"%s\"\nstudio.2.town: unknown\n" % SENTINEL,
            "{{school.name}} / {{studio.2.town}} / {{price.single}}\n",
        )
        self.assertEqual(proc.returncode, 1, proc.stderr)
        self.assertEqual(proc.stdout, SENTINEL + " / {{studio.2.town}} / {{price.single}}\n")
        self.assertIn("studio.2.town", proc.stderr)
        self.assertIn("price.single", proc.stderr)
        self.assertNotIn(SENTINEL, proc.stderr, "stderr names keys, never values")

    def test_quoted_values_and_comments(self):
        proc = self.fill(
            "# a comment\n\n" + MARKER + "\n"
            "a.one: \"hash # inside\"\n"
            "a.two: bare value   # trailing comment\n"
            "a.three: 'single'\n"
            "a.four: \"\"\n",
            "[{{a.one}}][{{a.two}}][{{a.three}}][{{a.four}}]\n",
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout, "[hash # inside][bare value][single][]\n")

    def test_malformed_profile_is_a_usage_error(self):
        cases = {
            "no separator": "school.name: \"x\"\n%s and no colon\n" % SENTINEL,
            "duplicate key": "school.name: x\nschool.name: \"%s\"\n" % SENTINEL,
            "bad key": "school.name: x\nSchool Name: \"%s\"\n" % SENTINEL,
            "open quote": "school.name: x\nschool.town: \"%s\n" % SENTINEL,
        }
        for label, text in cases.items():
            with self.subTest(case=label):
                proc = self.fill(text, "{{school.name}}\n")
                self.assertEqual(proc.returncode, 2, proc.stderr)
                self.assertEqual(proc.stdout, "")
                self.assertRegex(proc.stderr, r"line 2\b")
                self.assertNotIn(SENTINEL, proc.stderr, "an error names the line number, never the line")

    def test_fill_writes_nothing(self):
        self.write("business-profile.yaml", "school.name: x\n")
        before = digest(self.tmp)
        proc = self.fill(None, "{{school.name}}\n", profile=os.path.join(self.tmp, "business-profile.yaml"))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        after = digest(self.tmp)
        after.pop("template.md")
        before.pop("template.md", None)
        self.assertEqual(after, before)

    def test_profile_must_be_a_local_file(self):
        for profile in ("https://example.invalid/business-profile.yaml", os.path.join(self.tmp, "missing.yaml")):
            with self.subTest(profile=profile):
                proc = self.fill(None, "{{school.name}}\n", profile=profile)
                self.assertEqual(proc.returncode, 2)
                self.assertEqual(proc.stdout, "")


class ShippedTemplatesTest(unittest.TestCase):
    def test_key_table_documents_the_profile(self):
        keys = documented_keys()
        for key in ("profile.private", "channel", "school.name", "school.website", "studios.count",
                    "studio.1.name", "studio.1.town", "studio.2.name", "styles", "groups.kids",
                    "groups.english", "price.single", "price.couple", "price.pass_4", "price.pass_8",
                    "price.drop_in", "price.benefit_platforms", "offer.first_month",
                    "offer.refund_guarantee", "social.instagram", "social.facebook",
                    "social.whatsapp_broadcast"):
            with self.subTest(key=key):
                self.assertIn(key, keys)
        for key, example in keys.items():
            if key.startswith("price.") and key != "price.benefit_platforms":
                with self.subTest(price=key):
                    self.assertIn(example, ("<amount>", "<currency>"), "prices are placeholders")
            if "://" in example:
                with self.subTest(link=key):
                    self.assertRegex(example, r"^https://example\.invalid(/|$)")

    def test_templates_take_values_from_the_profile(self):
        for rel in PROFILE_TEMPLATES:
            with self.subTest(template=rel):
                self.assertRegex(read(os.path.join(DANCE, rel)), PLACEHOLDER_RE)

    def test_every_template_key_is_documented(self):
        keys = documented_keys()
        undocumented = []
        for rel in template_files():
            for key in PLACEHOLDER_RE.findall(read(rel)):
                if key not in keys:
                    undocumented.append("%s: %s" % (rel, key))
        self.assertEqual(undocumented, [])

    def test_the_documented_example_profile_fills_every_template(self):
        self.assertTrue(os.path.isfile(TOOL), "tools/business_profile.py is missing")
        tmp = tempfile.mkdtemp(prefix="kit-profile-templates-")
        self.addCleanup(shutil.rmtree, tmp, True)
        profile = os.path.join(tmp, "business-profile.yaml")
        with open(profile, "w", encoding="utf-8") as fh:
            for key, example in documented_keys().items():
                fh.write("%s: \"%s\"\n" % (key, example.strip("\"")))
        filled = 0
        for rel in template_files():
            if not PLACEHOLDER_RE.search(read(rel)):
                continue
            with self.subTest(template=rel):
                proc = subprocess.run(
                    [sys.executable, "-B", TOOL, "fill", "--profile", profile, os.path.join(ROOT, rel)],
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True, timeout=60,
                )
                self.assertEqual(proc.returncode, 0, proc.stderr)
                self.assertNotRegex(proc.stdout, PLACEHOLDER_RE)
                filled += 1
        self.assertGreaterEqual(filled, len(PROFILE_TEMPLATES))

    def test_keys_doc_names_the_location_and_the_guard(self):
        text = read(KEYS_DOC)
        for phrase in ("private/business-profile.yaml", "tools/business_profile.py fill",
                       "tools/business_profile.py check", "tools/business_profile.py draft",
                       "pre-commit", ".gitignore", "never goes into git", "checkpoint 3b"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)


if __name__ == "__main__":
    unittest.main()
