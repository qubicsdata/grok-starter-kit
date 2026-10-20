"""Identity and homepage from kit.config.yaml.

Covers vendor/accelerator/tools/kit_identity.py (the kit.config.yaml subset
parser, the format-preserving manifest editor, the 24 identity refs of the
docs and the release-check switch) and the two generators that use it,
tools/gen-registry.py (manifests) and tools/gen-readme.py (docs).

Run: python3 -m unittest discover -s tests/accelerator -t tests/accelerator
KIT_ACCEL_VENDOR=<dir> runs it against another copy of the suite (mutation
checks). Stdlib only, Python 3.9+.
"""

import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_scrub import (  # noqa: E402
    EXAMPLE_CONFIG, IDENTITY_DOCS, SUITE_URL_RE, TIMEOUT, VENDOR, TempKit, changed_paths,
    clean_env, load_json, marketplace, plugin_dirs, read_config_section, text_files,
    tree_digest,
)

MODULE_PATH = os.path.join(VENDOR, "tools", "kit_identity.py")

ODD_IDENTITY = {
    "author_name": 'Zoë "Z" Example (Docs) / Team — Two',
    "author_email": "zoe.example+kit@example.net",
    "homepage": "https://github.com/example-user/example-suite",
}
OTHER_IDENTITY = {
    "author_name": "Example Other",
    "author_email": "other@example.org",
    "homepage": "",
}

# 02 §1: 20 README maintainer lines, 2 OpenAPI contact refs (name and email
# each twice in the same prompt), the converter's author and a report footer.
REFS_PER_DOC = {rel: 1 for rel in IDENTITY_DOCS}
REFS_PER_DOC["api-designer/agents/spec-generator.md"] = 2
RELEASE_CHECK_GLOB_NAME = os.path.join("skills", "version-self-check.md")


def load_module():
    spec = importlib.util.spec_from_file_location("kit_identity_under_test", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def release_check_files(root):
    return sorted(
        os.path.join(root, name, RELEASE_CHECK_GLOB_NAME)
        for name in os.listdir(root)
        if os.path.isfile(os.path.join(root, name, RELEASE_CHECK_GLOB_NAME))
    )


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def write_config(kit_home, identity):
    """kit.config.yaml with the given `kit:` keys, double-quoted and escaped."""
    lines = ["kit:"]
    for key, value in identity.items():
        lines.append('  %s: "%s"' % (key, value.replace("\\", "\\\\").replace('"', '\\"')))
    with open(os.path.join(kit_home, "kit.config.yaml"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")


class ModuleCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not os.path.isfile(MODULE_PATH):
            raise AssertionError("tools/kit_identity.py missing")
        cls.mod = load_module()

    def tmpdir(self):
        path = tempfile.mkdtemp(prefix="kit-identity-")
        self.addCleanup(shutil.rmtree, path, True)
        return path


# --- the kit.config.yaml subset parser ---------------------------------------------

class ParserTest(ModuleCase):
    def parse(self, text):
        return self.mod.parse_section(text, "kit")

    def test_quoting_styles_and_comments(self):
        values = self.parse(
            "# top comment\n"
            "kit:   # trailing\n"
            '  author_name: "Example \\"Q\\" Person"   # note\n'
            "  author_email: 'it''s@example.com'\n"
            "  homepage: https://example.org/a#frag  # comment\n"
            "  timezone:\n"
            "  collision_suffix: ~\n"
        )
        self.assertEqual(values["author_name"], 'Example "Q" Person')
        self.assertEqual(values["author_email"], "it's@example.com")
        self.assertEqual(values["homepage"], "https://example.org/a#frag")
        self.assertIsNone(values["timezone"])
        self.assertIsNone(values["collision_suffix"])

    def test_only_the_named_section_and_its_own_level(self):
        values = self.parse(
            "runner:\n"
            '  author_name: "wrong section"\n'
            "kit:\n"
            '  author_name: "right"\n'
            "  nested:\n"
            '    author_email: "deeper@example.com"\n'
            "other:\n"
            '  author_email: "after@example.com"\n'
        )
        self.assertEqual(values, {"author_name": "right", "nested": None})

    def test_crlf_and_missing_section(self):
        self.assertEqual(self.parse('kit:\r\n  homepage: ""\r\n'), {"homepage": ""})
        self.assertEqual(self.parse("runner:\n  enabled: false\n"), {})

    def test_malformed_lines_are_errors(self):
        for text in (
            'kit:\n  author_name: "unterminated\n',
            'kit:\n  author_name: "a" trailing\n',
            'kit:\n  author_name: "a"\n  author_name: "b"\n',
            "kit:\n\tauthor_name: a\n",
            "kit: {author_name: a}\n",
            'kit:\n  author_name: "bad \\q escape"\n',
            "kit:\n  no colon here\n",
        ):
            with self.subTest(text=text):
                with self.assertRaises(self.mod.ConfigError):
                    self.parse(text)

    def test_errors_name_the_line_not_the_value(self):
        with self.assertRaises(self.mod.ConfigError) as ctx:
            self.parse('kit:\n  author_name: "secret-value-xyz\n')
        self.assertIn("line 2", str(ctx.exception))
        self.assertNotIn("secret-value-xyz", str(ctx.exception))


class LoadIdentityTest(ModuleCase):
    def suite_in(self, base):
        suite = os.path.join(base, "vendor", "accelerator")
        os.makedirs(suite)
        return suite

    def write(self, path, text):
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)

    def test_placeholders_match_the_example_config(self):
        kit = read_config_section(EXAMPLE_CONFIG, "kit")
        self.assertEqual(self.mod.PLACEHOLDERS, {
            "author_name": kit["author_name"],
            "author_email": kit["author_email"],
            "homepage": kit["homepage"],
        })

    def test_absent_file_gives_placeholders(self):
        suite = self.suite_in(self.tmpdir())
        self.assertEqual(self.mod.load_identity(suite, environ={}), self.mod.PLACEHOLDERS)

    def test_absent_or_empty_keys_give_placeholders(self):
        base = self.tmpdir()
        suite = self.suite_in(base)
        self.write(os.path.join(base, "kit.config.yaml"),
                   'kit:\n  author_name: ""\n  author_email: ~\n  timezone: "UTC"\n')
        self.assertEqual(self.mod.load_identity(suite, environ={}), self.mod.PLACEHOLDERS)

    def test_values_from_the_kit_home_above_the_suite(self):
        base = self.tmpdir()
        suite = self.suite_in(base)
        self.write(os.path.join(base, "kit.config.yaml"),
                   "kit:\n  author_name: Example Person\n  author_email: p@example.org\n"
                   "  homepage: https://example.org/kit\n")
        self.assertEqual(self.mod.load_identity(suite, environ={}), {
            "author_name": "Example Person",
            "author_email": "p@example.org",
            "homepage": "https://example.org/kit",
        })

    def test_kit_home_environment_wins(self):
        base, other = self.tmpdir(), self.tmpdir()
        suite = self.suite_in(base)
        self.write(os.path.join(base, "kit.config.yaml"), 'kit:\n  author_name: "Below"\n')
        self.write(os.path.join(other, "kit.config.yaml"), 'kit:\n  author_name: "From Env"\n')
        identity = self.mod.load_identity(suite, environ={"KIT_HOME": other})
        self.assertEqual(identity["author_name"], "From Env")

    def test_invalid_values_are_rejected(self):
        base = self.tmpdir()
        suite = self.suite_in(base)
        for line in (
            "author_email: no-at-sign",
            "author_email: two words@example.com",
            "author_email: a@b@example.com",
            "author_email: <a@example.com>",
            "homepage: example.org/no-scheme",
            "homepage: ftp://example.org",
            'homepage: "https://example.org/has space"',
            "author_name: back`tick",
            'author_name: "tab\\there"',
        ):
            with self.subTest(line=line):
                self.write(os.path.join(base, "kit.config.yaml"), "kit:\n  %s\n" % line)
                with self.assertRaises(self.mod.ConfigError) as ctx:
                    self.mod.load_identity(suite, environ={})
                self.assertIn(line.split(":", 1)[0], str(ctx.exception))


# --- the format-preserving manifest editor -----------------------------------------

COMPACT = (
    '{\n  "name": "example-plugin",\n  "version": "1.0.0",\n'
    '  "author": {\n    "name": "Old Name",\n    "email": "old@example.com",\n'
    '    "url": "https://example.com/me"\n  },\n'
    '  "keywords": ["a","b"],\n  "description": "caf\\u00e9 — raw"\n}\n'
)


class ManifestEditTest(ModuleCase):
    IDENT = {"author_name": "New Name", "author_email": "new@example.org", "homepage": ""}

    def test_author_replaced_and_layout_kept(self):
        out = self.mod.apply_plugin_identity(COMPACT, self.IDENT)
        self.assertEqual(out, COMPACT.replace("Old Name", "New Name")
                         .replace("old@example.com", "new@example.org"))
        self.assertEqual(json.loads(out)["author"]["url"], "https://example.com/me")

    def test_homepage_inserted_after_author_and_removed_again(self):
        ident = dict(self.IDENT, homepage="https://example.org/kit")
        with_home = self.mod.apply_plugin_identity(COMPACT, ident)
        data = json.loads(with_home)
        self.assertEqual(data["homepage"], "https://example.org/kit")
        self.assertEqual(list(data).index("homepage"), list(data).index("author") + 1)
        self.assertIn('  },\n  "homepage": "https://example.org/kit",\n  "keywords"', with_home)
        back = self.mod.apply_plugin_identity(with_home, self.IDENT)
        self.assertEqual(back, self.mod.apply_plugin_identity(COMPACT, self.IDENT))

    def test_homepage_removed_wherever_it_sits(self):
        for text in (
            '{\n  "homepage": "https://x.example",\n  "name": "p",\n'
            '  "author": {"name": "n", "email": "e@example.com"}\n}\n',
            '{\n  "name": "p",\n  "author": {"name": "n", "email": "e@example.com"},\n'
            '  "homepage": "https://x.example"\n}\n',
        ):
            with self.subTest(text=text):
                out = self.mod.apply_plugin_identity(text, self.IDENT)
                data = json.loads(out)
                self.assertNotIn("homepage", data)
                self.assertEqual(data["author"], {"name": "New Name", "email": "new@example.org"})
                self.assertFalse(out.startswith("{,") or ",\n}" in out)

    def test_existing_homepage_replaced_in_place(self):
        text = '{"name": "p", "author": {"name": "n", "email": "e@example.com"}, "homepage": "https://a.example"}\n'
        ident = dict(self.IDENT, homepage="https://b.example")
        out = self.mod.apply_plugin_identity(text, ident)
        self.assertTrue(out.rstrip().endswith('"homepage": "https://b.example"}'))

    def test_missing_or_string_author_becomes_an_object(self):
        for text in (
            '{\n  "name": "p",\n  "version": "1.0.0",\n  "description": "d"\n}\n',
            '{\n  "name": "p",\n  "author": "Someone <s@example.com>"\n}\n',
        ):
            with self.subTest(text=text):
                out = self.mod.apply_plugin_identity(text, self.IDENT)
                self.assertEqual(json.loads(out)["author"],
                                 {"name": "New Name", "email": "new@example.org"})
                self.assertIn('\n  "author": {\n    "name": "New Name",\n'
                              '    "email": "new@example.org"\n  }', out)

    def test_special_characters_round_trip(self):
        out = self.mod.apply_plugin_identity(COMPACT, ODD_IDENTITY)
        data = json.loads(out)
        self.assertEqual(data["author"]["name"], ODD_IDENTITY["author_name"])
        self.assertEqual(self.mod.apply_plugin_identity(out, ODD_IDENTITY), out)

    def test_marketplace_owner_and_entries(self):
        text = json.dumps({
            "name": "m", "owner": {"name": "o", "email": "o@example.com"},
            "metadata": {"description": "d", "homepage": "https://keep.example"},
            "plugins": [
                {"name": "a", "author": {"name": "x", "email": "x@example.com"}},
                {"name": "b", "author": {"name": "y", "email": "y@example.com"},
                 "homepage": "https://old.example"},
            ],
        }, indent=2) + "\n"
        ident = dict(self.IDENT, homepage="https://example.org/kit")
        data = json.loads(self.mod.apply_marketplace_identity(text, ident))
        self.assertEqual(data["owner"], {"name": "New Name", "email": "new@example.org"})
        self.assertEqual([p["homepage"] for p in data["plugins"]], ["https://example.org/kit"] * 2)
        self.assertEqual([p["author"]["email"] for p in data["plugins"]], ["new@example.org"] * 2)
        self.assertEqual(data["metadata"]["homepage"], "https://keep.example")
        data = json.loads(self.mod.apply_marketplace_identity(text, self.IDENT))
        self.assertEqual([("homepage" in p) for p in data["plugins"]], [False, False])

    def test_invalid_json_is_an_error(self):
        with self.assertRaises(ValueError):
            self.mod.apply_plugin_identity('{"name": "p",}', self.IDENT)


# --- docs: the 24 refs and the release-check switch ---------------------------------

class DocEditTest(ModuleCase):
    def test_every_identity_doc_is_declared(self):
        declared = sorted({path for path, _, _ in self.mod.IDENTITY_REFS})
        self.assertEqual(declared, sorted(IDENTITY_DOCS))
        self.assertEqual(sum(n for _, _, n in self.mod.IDENTITY_REFS), 24)

    def test_count_mismatch_is_an_error_naming_the_file(self):
        root = self.tmpdir()
        for rel in IDENTITY_DOCS:
            os.makedirs(os.path.dirname(os.path.join(root, rel)), exist_ok=True)
            shutil.copy2(os.path.join(VENDOR, rel), os.path.join(root, rel))
        target = os.path.join(root, "ai-baseline", "README.md")
        text = read(target)
        with open(target, "w", encoding="utf-8") as fh:
            fh.write(text + "\nExample Extra (extra@example.com)\n")
        with self.assertRaises(self.mod.DocError) as ctx:
            self.mod.identity_doc_updates(root, self.mod.PLACEHOLDERS)
        self.assertIn("ai-baseline/README.md", str(ctx.exception))
        self.assertNotIn("extra@example.com", str(ctx.exception))

    def test_release_check_block(self):
        text = ("1. step\n\n<!-- kit:release-check:begin -->\nold\n"
                "<!-- kit:release-check:end -->\n\n3. step\n")
        off = self.mod.render_release_check(text, "example-plugin", "")
        self.assertIn("release check is off", off.lower())
        self.assertNotIn("WebFetch", off)
        gh = self.mod.render_release_check(text, "example-plugin", "https://github.com/example-user/example-suite/")
        self.assertIn("https://api.github.com/repos/example-user/example-suite/releases/latest", gh)
        other = self.mod.render_release_check(text, "example-plugin", "https://example.org/kit")
        self.assertIn("WebFetch https://example.org/kit", other)
        self.assertEqual(self.mod.render_release_check(off, "example-plugin", ""), off)
        self.assertTrue(other.startswith("1. step\n\n") and other.endswith("\n\n3. step\n"))
        with self.assertRaises(self.mod.DocError):
            self.mod.render_release_check("no markers\n", "example-plugin", "")


# --- the committed tree (example config: placeholders, no homepage) ---------------

class CommittedTreeTest(unittest.TestCase):
    def test_empty_homepage_disables_the_release_check(self):
        checks = release_check_files(VENDOR)
        self.assertGreater(len(checks), 0, "no version-self-check skill found")
        for path in checks:
            text = read(path)
            self.assertIn("release check is off", text.lower())
            block = text.split("kit:release-check:begin", 1)[-1].split("kit:release-check:end", 1)[0]
            self.assertNotIn("WebFetch", block)
        self.assertEqual(files_with_homepage(VENDOR), [])

    def test_readme_maintainer_section_has_the_placeholders(self):
        text = read(os.path.join(VENDOR, "README.md"))
        section = text.split("## Maintainer", 1)[-1].split("\n---", 1)[0]
        self.assertIn("<your-name> (you@example.com)", section)
        self.assertNotIn("Homepage", section)


# --- the generators end to end on a temp copy ---------------------------------------

class GeneratorIdentityTest(unittest.TestCase):
    def setUp(self):
        self.kit = TempKit()
        self.addCleanup(self.kit.cleanup)
        self.before = tree_digest(self.kit.vendor)

    def run_ok(self, tool):
        proc = self.kit.run_tool(tool)
        self.assertEqual(proc.returncode, 0, "%s exited %d" % (tool, proc.returncode))
        return proc.stdout

    def regenerate(self):
        return self.run_ok("gen-registry.py") + self.run_ok("gen-readme.py")

    def changed(self):
        return changed_paths(self.before, tree_digest(self.kit.vendor))

    def test_every_identity_ref_follows_the_config(self):
        write_config(self.kit.root, ODD_IDENTITY)
        output = self.regenerate()
        name, email = ODD_IDENTITY["author_name"], ODD_IDENTITY["author_email"]
        bad = []
        for rel, refs in sorted(REFS_PER_DOC.items()):
            text = read(os.path.join(self.kit.vendor, rel))
            names = text.count(name) + text.count(json.dumps(name, ensure_ascii=False)[1:-1])
            if (text.count(email), names) != (refs, refs):
                bad.append(rel)
        self.assertEqual(bad, [], "identity refs not rewritten")
        self.assertNotIn(email, output, "generators print the identity")
        self.assertNotIn(name, output, "generators print the identity")

    def test_homepage_set_fills_manifests_and_enables_the_release_check(self):
        write_config(self.kit.root, ODD_IDENTITY)
        self.regenerate()
        home = ODD_IDENTITY["homepage"]
        missing = [p for p in plugin_dirs(self.kit.vendor) if load_json(os.path.join(
            self.kit.vendor, p, ".claude-plugin", "plugin.json")).get("homepage") != home]
        missing += ["marketplace " + e["name"] for e in marketplace(self.kit.vendor)["plugins"]
                    if e.get("homepage") != home]
        self.assertEqual(missing, [], "homepage not set")
        checks = release_check_files(self.kit.vendor)
        self.assertGreater(len(checks), 0)
        for path in checks:
            self.assertIn("api.github.com/repos/example-user/example-suite/releases/latest", read(path))
        self.assertIn(home, read(os.path.join(self.kit.vendor, "README.md")))

    def test_switching_identities_and_back_restores_the_tree(self):
        for identity in (ODD_IDENTITY, OTHER_IDENTITY, ODD_IDENTITY):
            write_config(self.kit.root, identity)
            self.regenerate()
        self.assertNotEqual(files_with_homepage(self.kit.vendor), [])
        write_config(self.kit.root, OTHER_IDENTITY)
        self.regenerate()
        self.assertEqual(files_with_homepage(self.kit.vendor), [])
        self.assertEqual(files_matching_text(self.kit.vendor, ODD_IDENTITY["author_email"]), [])
        os.remove(os.path.join(self.kit.root, "kit.config.yaml"))
        self.regenerate()
        self.assertEqual(self.changed(), [], "tree not restored")

    def test_kit_home_environment_is_honoured(self):
        other = tempfile.mkdtemp(prefix="kit-home-")
        self.addCleanup(shutil.rmtree, other, True)
        write_config(other, {"author_email": "env@example.org"})
        write_config(self.kit.root, {"author_email": "below@example.org"})
        env = clean_env(self.kit.home)
        env["KIT_HOME"] = other
        for tool in ("gen-registry.py", "gen-readme.py"):
            proc = subprocess.run(
                [sys.executable, os.path.join("tools", tool)], cwd=self.kit.vendor, env=env,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True,
                timeout=TIMEOUT,
            )
            self.assertEqual(proc.returncode, 0, "%s exited %d" % (tool, proc.returncode))
        self.assertEqual(marketplace(self.kit.vendor)["owner"]["email"], "env@example.org")
        self.assertIn("env@example.org", read(os.path.join(self.kit.vendor, "ai-baseline", "README.md")))

    def test_invalid_config_fails_and_writes_nothing(self):
        with open(os.path.join(self.kit.root, "kit.config.yaml"), "w", encoding="utf-8") as fh:
            fh.write('kit:\n  author_email: "not-an-email"\n')
        for tool in ("gen-registry.py", "gen-readme.py"):
            with self.subTest(tool=tool):
                proc = self.kit.run_tool(tool)
                self.assertNotEqual(proc.returncode, 0)
                self.assertIn("author_email", proc.stdout)
                self.assertNotIn("not-an-email", proc.stdout)
        self.assertEqual(self.changed(), [])

    def test_broken_maintainer_line_fails_and_writes_nothing(self):
        write_config(self.kit.root, OTHER_IDENTITY)
        target = os.path.join(self.kit.vendor, "cost-monitor", "README.md")
        text = read(target)
        broken = re.sub(r"^.*\(you@example\.com\)$", "maintainer line removed", text, flags=re.M)
        self.assertNotEqual(broken, text)
        with open(target, "w", encoding="utf-8") as fh:
            fh.write(broken)
        self.before = tree_digest(self.kit.vendor)
        proc = self.kit.run_tool("gen-readme.py")
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("cost-monitor/README.md", proc.stdout)
        self.assertEqual(self.changed(), [])

    def test_removed_plugin_is_skipped(self):
        shutil.rmtree(os.path.join(self.kit.vendor, "workspace-companion"))
        path = os.path.join(self.kit.vendor, ".claude-plugin", "marketplace.json")
        data = load_json(path)
        data["plugins"] = [e for e in data["plugins"] if e["name"] != "workspace-companion"]
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, ensure_ascii=False)
            fh.write("\n")
        write_config(self.kit.root, OTHER_IDENTITY)
        self.regenerate()
        self.assertIn(OTHER_IDENTITY["author_email"],
                      read(os.path.join(self.kit.vendor, "ai-baseline", "README.md")))

    def test_each_generator_owns_its_files(self):
        write_config(self.kit.root, OTHER_IDENTITY)
        self.run_ok("gen-registry.py")
        registry_changed = set(self.changed())
        self.assertTrue(registry_changed)
        self.assertTrue(all(p.endswith(".json") for p in registry_changed), "gen-registry wrote docs")
        self.run_ok("gen-readme.py")
        docs_changed = set(self.changed()) - registry_changed
        self.assertTrue(set(IDENTITY_DOCS) <= docs_changed)
        self.assertTrue(all(p.endswith(".md") for p in docs_changed), "gen-readme wrote manifests")


def files_with_homepage(root):
    found = []
    for plugin in plugin_dirs(root):
        if "homepage" in load_json(os.path.join(root, plugin, ".claude-plugin", "plugin.json")):
            found.append(plugin)
    found += ["marketplace " + e["name"] for e in marketplace(root)["plugins"] if "homepage" in e]
    found += [rel for rel, text in text_files(root) if SUITE_URL_RE.search(text)]
    return found


def files_matching_text(root, needle):
    return [rel for rel, text in text_files(root) if needle in text]


if __name__ == "__main__":
    unittest.main()
