"""Drafting the private business profile from the user's own site
(`tools/business_profile.py draft`).

At checkpoint 3b the user's Grok Bot proposes a profile from the user's own
website and social accounts. `draft` reads a folder of pages saved from that
site (local files only; it never fetches anything), takes what the pages
declare (schema.org JSON-LD, the `og:site_name` meta tag) and prints a
profile with `unknown` for everything it could not see. It writes nothing.

The site here is a SYNTHETIC fixture written to a temp dir: invented names,
placeholder values and `.invalid` links, no server. `KIT_BUSINESS_PROFILE`
points the suite at another copy of the tool. Stdlib only, Python 3.9+.
"""

import ast
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOL = os.environ.get("KIT_BUSINESS_PROFILE") or os.path.join(ROOT, "tools", "business_profile.py")
KEYS_DOC = os.path.join(ROOT, "second-brain", "BUSINESS-PROFILE.md")
KEY_ROW_RE = re.compile(r"^\|\s*`([a-z][a-z0-9_.]*)`\s*\|")
LINE_RE = re.compile(r"^([a-z][a-z0-9_.]*): \"(.*)\"$")
NETWORK_MODULES = ("socket", "ssl", "http", "urllib", "ftplib", "smtplib", "poplib", "imaplib",
                   "telnetlib", "xmlrpc", "asyncio", "webbrowser", "requests", "selectors")

SCHOOL = {
    "@context": "https://schema.org",
    "@type": "DanceSchool",
    "name": "Example Dance School",
    "url": "https://example.invalid/",
    "sameAs": [
        "https://instagram.example.invalid/example-school",
        "https://facebook.example.invalid/example-school",
        "https://wa.example.invalid/channel/example",
    ],
    "knowsAbout": ["salsa", "bachata", "kizomba"],
    "location": [
        {"@type": "Place", "name": "Studio A",
         "address": {"@type": "PostalAddress", "addressLocality": "<town-a>", "streetAddress": "<address-a>"}},
        {"@type": "Place", "name": "Studio B",
         "address": {"@type": "PostalAddress", "addressLocality": "<town-b>", "streetAddress": "<address-b>"}},
    ],
    "makesOffer": [
        {"@type": "Offer", "name": "Single class", "price": "<amount-single>", "priceCurrency": "<currency>"},
        {"@type": "Offer", "name": "Couple pass", "price": "<amount-couple>"},
        {"@type": "Offer", "name": "4-session pass", "price": "<amount-4>"},
        {"@type": "Offer", "name": "8-session pass", "price": "<amount-8>"},
        {"@type": "Offer", "name": "Drop-in", "price": "<amount-drop-in>"},
    ],
}


def page(blocks=(), meta=None, body="<p>Example page</p>"):
    head = []
    if meta:
        head.append('<meta property="og:site_name" content="%s">' % meta)
    for block in blocks:
        text = block if isinstance(block, str) else json.dumps(block)
        head.append('<script type="application/ld+json">%s</script>' % text)
    return "<!doctype html><html><head>%s</head><body>%s</body></html>\n" % ("".join(head), body)


def documented_keys():
    with open(KEYS_DOC, encoding="utf-8") as fh:
        return [m.group(1) for m in map(KEY_ROW_RE.match, fh.read().splitlines()) if m]


def digest(root):
    out = {}
    for dirpath, _, filenames in os.walk(root):
        for name in filenames:
            path = os.path.join(dirpath, name)
            with open(path, "rb") as fh:
                out[os.path.relpath(path, root)] = fh.read()
    return out


class DraftTest(unittest.TestCase):
    def setUp(self):
        self.assertTrue(os.path.isfile(TOOL), "tools/business_profile.py is missing")
        self.tmp = tempfile.mkdtemp(prefix="kit-profile-draft-")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.site = os.path.join(self.tmp, "site")
        os.makedirs(os.path.join(self.site, "classes"))

    def write(self, rel, text):
        with open(os.path.join(self.site, rel), "w", encoding="utf-8") as fh:
            fh.write(text)

    def draft(self, *args):
        return subprocess.run(
            [sys.executable, "-B", TOOL, "draft"] + list(args or [self.site]),
            cwd=self.tmp, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            universal_newlines=True, timeout=60,
        )

    def values(self, proc):
        self.assertEqual(proc.returncode, 0, proc.stderr)
        lines = proc.stdout.splitlines()
        self.assertEqual(lines[0], "profile.private" + ": true", "the marker comes first")
        out = {}
        for line in lines[1:]:
            if not line or line.startswith("#"):
                continue
            m = LINE_RE.match(line)
            self.assertIsNotNone(m, "not a profile line: %r" % line)
            self.assertNotIn(m.group(1), out, "duplicate key")
            out[m.group(1)] = m.group(2)
        return out

    def test_reads_what_the_site_declares(self):
        self.write("index.html", page([SCHOOL]))
        self.write(os.path.join("classes", "events.htm"), page([{"@type": "Event", "name": "Social night"}]))
        values = self.values(self.draft())
        expected = {
            "channel": "dance-school",
            "school.name": "Example Dance School",
            "school.website": "https://example.invalid/",
            "studios.count": "2",
            "studio.1.name": "Studio A", "studio.1.town": "<town-a>", "studio.1.address": "<address-a>",
            "studio.2.name": "Studio B", "studio.2.town": "<town-b>", "studio.2.address": "<address-b>",
            "styles": "salsa, bachata, kizomba",
            "price.currency": "<currency>",
            "price.single": "<amount-single>", "price.couple": "<amount-couple>",
            "price.pass_4": "<amount-4>", "price.pass_8": "<amount-8>", "price.drop_in": "<amount-drop-in>",
            "social.instagram": "https://instagram.example.invalid/example-school",
            "social.facebook": "https://facebook.example.invalid/example-school",
        }
        for key, value in expected.items():
            with self.subTest(key=key):
                self.assertEqual(values.get(key), value)

    def test_unknown_for_everything_not_on_the_site(self):
        self.write("index.html", page([SCHOOL]))
        values = self.values(self.draft())
        for key in ("term.autumn_start", "term.january_start", "groups.seniors", "groups.kids",
                    "offer.refund_guarantee", "social.whatsapp_broadcast", "price.benefit_platforms"):
            with self.subTest(key=key):
                self.assertEqual(values.get(key), "unknown")

    def test_draft_covers_every_documented_key(self):
        self.write("index.html", page([SCHOOL]))
        values = self.values(self.draft())
        values["profile.private"] = "true"
        documented = documented_keys()
        self.assertTrue(documented, "no key table in BUSINESS-PROFILE.md")
        self.assertEqual(sorted(set(values)), sorted(set(documented)))

    def test_site_name_meta_and_a_broken_block(self):
        self.write("index.html", page(["{not json", {"@type": "WebPage"}], meta="Example Site Name"))
        values = self.values(self.draft())
        self.assertEqual(values["school.name"], "Example Site Name")
        self.assertEqual(values["studios.count"], "unknown")
        self.assertEqual(values["studio.1.name"], "unknown")

    def test_channel_option(self):
        self.write("index.html", page([SCHOOL]))
        values = self.values(self.draft("--channel", "other-activities", self.site))
        self.assertEqual(values["channel"], "other-activities")

    def test_local_files_only(self):
        for arg in ("https://example.invalid/", "http://example.invalid/", os.path.join(self.tmp, "missing")):
            with self.subTest(arg=arg):
                proc = self.draft(arg)
                self.assertEqual(proc.returncode, 2)
                self.assertEqual(proc.stdout, "")

    def test_draft_writes_nothing(self):
        self.write("index.html", page([SCHOOL]))
        before = digest(self.tmp)
        self.values(self.draft())
        self.assertEqual(digest(self.tmp), before)

    def test_the_draft_is_a_profile_fill_can_read(self):
        self.write("index.html", page([SCHOOL]))
        proc = self.draft()
        profile = os.path.join(self.tmp, "business-profile.yaml")
        with open(profile, "w", encoding="utf-8") as fh:
            fh.write(proc.stdout)
        template = os.path.join(self.tmp, "t.md")
        with open(template, "w", encoding="utf-8") as fh:
            fh.write("{{school.name}} {{term.autumn_start}}\n")
        filled = subprocess.run([sys.executable, "-B", TOOL, "fill", "--profile", profile, template],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True, timeout=60)
        self.assertEqual(filled.returncode, 1, filled.stderr)
        self.assertEqual(filled.stdout, "Example Dance School {{term.autumn_start}}\n")


class NoNetworkTest(unittest.TestCase):
    def test_the_tool_imports_no_network_module(self):
        self.assertTrue(os.path.isfile(TOOL), "tools/business_profile.py is missing")
        with open(TOOL, encoding="utf-8") as fh:
            tree = ast.parse(fh.read())
        found = []
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            elif isinstance(node, ast.Call) and getattr(node.func, "id", "") == "__import__":
                names = ["__import__"]
            found += [n for n in names if n == "__import__" or n.split(".")[0] in NETWORK_MODULES]
        self.assertEqual(found, [])


if __name__ == "__main__":
    unittest.main()
