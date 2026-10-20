"""Kit-level scrub tests for the vendored plugin suite (vendor/accelerator).

They pin what the kit delivers on top of the plain copy: a clean scan, the
identity fields from kit.config, the builder plugin renamed, the README plugin
count, pricing and model IDs as data files, and idempotent generators.

Run: python3 -m unittest discover -s tests/accelerator -t tests/accelerator
(no __init__.py here on purpose: the `accelerator` step of tools/ci_local.py
runs this folder, so kit-tests does not run it a second time).
KIT_ACCEL_VENDOR=<dir> runs it against another copy of the suite.

Failure messages name files, plugins and fields only, never their values.
Stdlib only, Python 3.9+.
"""

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# KIT_ACCEL_VENDOR points the suite at another copy (mutation checks).
VENDOR = os.environ.get("KIT_ACCEL_VENDOR") or os.path.join(ROOT, "vendor", "accelerator")
EXAMPLE_CONFIG = os.path.join(ROOT, "kit.config.example.yaml")
CLEAN_SCAN = os.path.join(ROOT, "tools", "clean_scan.py")

TIMEOUT = 600

# Files outside the manifests that carry the author identity (02 §1: 20 plugin
# README maintainer lines, the OpenAPI contact, the converter's author, a footer).
IDENTITY_DOCS = [
    "ai-baseline/README.md",
    "api-designer/README.md",
    "compliance-companion/README.md",
    "content-companion/README.md",
    "cost-monitor/README.md",
    "data-companion/README.md",
    "dependency-auditor/README.md",
    "frontend-companion/README.md",
    "greenfield-project-initializer/README.md",
    "incident-companion/README.md",
    "legacy-modernizer/README.md",
    "memory-companion/README.md",
    "observability-companion/README.md",
    "onboarding-guide/README.md",
    "ops-companion/README.md",
    "release-manager/README.md",
    "sap-migration-companion/README.md",
    "self-evolution-companion/README.md",
    "uiux-companion/README.md",
    "workspace-companion/README.md",
    "api-designer/agents/spec-generator.md",
    "assimilator/agents/conformance-converter.md",
    "dependency-auditor/agents/audit-orchestrator.md",
]

OLD_BUILDER = "agent-forge"
NEW_BUILDER = "agent-builder"
NEW_COMMAND = "build-agent"

FORGE_COMMAND_RE = re.compile(r"(?<![\w/.-])/forge(?![\w/-])")
FORGE_INJECTS_RE = re.compile(r"forge\s+injects", re.IGNORECASE)
SUITE_URL_RE = re.compile(r"github\.com/(?:repos/)?[A-Za-z0-9_.-]+/accelerator(?![\w-])")
INLINE_RATE_RE = re.compile(r"(?<![\w.])0\.0000\d|(?<![\w.])\d+(?:\.\d+)?[eE]-0?[4-9](?!\d)")
NUMBER_PLUGINS_RE = re.compile(r"\b(\d+) (?:composable )?plugins\b")
COMMIT_EXAMPLE_RE = re.compile(r"^- .+ \(([0-9a-f]{7})\) — (.+?)\s*$")
EXAMPLE_COMMIT_AUTHOR = "Example Author"

# The generators' fallback values live here; the only file that may keep them.
PLACEHOLDER_SOURCE = os.path.join("tools", "kit_identity.py")

LEFT_OUT_DIRS = ("docs/superpowers", "benchmarks", "." + "superpowers")

TEST_IDENTITY = {
    "author_name": "Example Person",
    "author_email": "person@example.org",
    "homepage": "https://example.org/kit",
}


# --- helpers -----------------------------------------------------------------

def read_config_section(path, section):
    """Flat `key: value` pairs of one top-level section of the kit's YAML
    subset (quotes and trailing comments stripped)."""
    values, current = {}, None
    with open(path, encoding="utf-8") as fh:
        for raw in fh:
            line = raw.rstrip("\n")
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            if not line.startswith(" "):
                current = line.split(":", 1)[0].strip()
                continue
            if current != section or line.startswith("    "):
                continue
            key, _, rest = line.strip().partition(":")
            rest = rest.strip()
            if rest.startswith('"'):
                value = rest[1:rest.index('"', 1)]
            else:
                value = rest.split(" #", 1)[0].strip()
            values[key.strip()] = value
    return values


def placeholders():
    kit = read_config_section(EXAMPLE_CONFIG, "kit")
    return kit["author_name"], kit["author_email"], kit.get("homepage", "")


def configured_path(key, kit_home=ROOT, vendor=None):
    """A path from the `accelerator:` section, resolved against kit_home (and
    the vendored copy under test for paths inside vendor/accelerator)."""
    value = read_config_section(EXAMPLE_CONFIG, "accelerator")[key]
    value = value.replace("${KIT_HOME}/vendor/accelerator", vendor or VENDOR)
    return value.replace("${KIT_HOME}", kit_home)


def load_json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def plugin_dirs(root=VENDOR):
    return sorted(
        name for name in os.listdir(root)
        if os.path.isfile(os.path.join(root, name, ".claude-plugin", "plugin.json"))
    )


def marketplace(root=VENDOR):
    return load_json(os.path.join(root, ".claude-plugin", "marketplace.json"))


def text_files(root=VENDOR):
    """(relative path, text) for every non-binary file under root."""
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d != "__pycache__")
        for name in sorted(filenames):
            path = os.path.join(dirpath, name)
            if os.path.islink(path):
                continue
            with open(path, "rb") as fh:
                data = fh.read()
            if b"\0" in data[:8000]:
                continue
            yield os.path.relpath(path, root), data.decode("utf-8", "replace")


def files_matching(regex, root=VENDOR):
    return sorted(rel for rel, text in text_files(root) if regex.search(text))


def tree_digest(root):
    digests = {}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d != "__pycache__"]
        for name in filenames:
            path = os.path.join(dirpath, name)
            with open(path, "rb") as fh:
                digests[os.path.relpath(path, root)] = hashlib.sha256(fh.read()).hexdigest()
    return digests


def changed_paths(before, after):
    return sorted(
        rel for rel in set(before) | set(after) if before.get(rel) != after.get(rel)
    )


def clean_env(home):
    env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": home,
        "LANG": "C.UTF-8",
        "PYTHONDONTWRITEBYTECODE": "1",
        "ACCELERATOR_SUPERPOWERS": "0",
    }
    return env


class TempKit:
    """A throwaway kit layout: kit.config.example.yaml plus a copy of
    vendor/accelerator, and an empty HOME next to it."""

    def __init__(self):
        self.base = tempfile.mkdtemp(prefix="kit-accel-")
        self.root = os.path.join(self.base, "kit")
        self.home = os.path.join(self.base, "home")
        os.makedirs(self.home)
        os.makedirs(os.path.join(self.root, "vendor"))
        shutil.copy2(EXAMPLE_CONFIG, os.path.join(self.root, "kit.config.example.yaml"))
        self.vendor = os.path.join(self.root, "vendor", "accelerator")
        shutil.copytree(VENDOR, self.vendor, symlinks=True,
                        ignore=shutil.ignore_patterns("__pycache__"))

    def run(self, argv):
        return subprocess.run(
            argv, cwd=self.vendor, env=clean_env(self.home),
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            universal_newlines=True, timeout=TIMEOUT,
        )

    def run_tool(self, name, *args):
        return self.run([sys.executable, os.path.join("tools", name)] + list(args))

    def regenerate(self, testcase):
        for tool in ("gen-registry.py", "gen-readme.py"):
            proc = self.run_tool(tool)
            testcase.assertEqual(proc.returncode, 0, "%s exited %d" % (tool, proc.returncode))

    def write_config(self, identity):
        lines = ["kit:"]
        for key in ("author_name", "author_email", "homepage"):
            lines.append('  %s: "%s"' % (key, identity[key]))
        with open(os.path.join(self.root, "kit.config.yaml"), "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")

    def cleanup(self):
        shutil.rmtree(self.base, ignore_errors=True)


def hooklib_rates(vendor, home, models):
    """model_pricing() of tools/hooks/_hooklib.py in `vendor`, in a fresh
    interpreter, for each model id; returns {model: [input, output]}."""
    code = (
        "import importlib.util, json, sys\n"
        "spec = importlib.util.spec_from_file_location('kit_hooklib_probe', sys.argv[1])\n"
        "mod = importlib.util.module_from_spec(spec)\n"
        "spec.loader.exec_module(mod)\n"
        "print(json.dumps({m: list(mod.model_pricing(m)) for m in json.loads(sys.argv[2])}))\n"
    )
    proc = subprocess.run(
        [sys.executable, "-I", "-c", code,
         os.path.join(vendor, "tools", "hooks", "_hooklib.py"), json.dumps(models)],
        cwd=vendor, env=clean_env(home), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        universal_newlines=True, timeout=TIMEOUT,
    )
    if proc.returncode != 0:
        raise AssertionError("importing _hooklib failed (exit %d)" % proc.returncode)
    return json.loads(proc.stdout)


def scale_numbers(value, factor):
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value * factor
    if isinstance(value, list):
        return [scale_numbers(v, factor) for v in value]
    if isinstance(value, dict):
        return {k: scale_numbers(v, factor) for k, v in value.items()}
    return value


def string_keys(value):
    if isinstance(value, dict):
        for key, item in value.items():
            yield key
            for sub in string_keys(item):
                yield sub
    elif isinstance(value, list):
        for item in value:
            for sub in string_keys(item):
                yield sub


# --- the copy itself -----------------------------------------------------------

class CopyTest(unittest.TestCase):
    def test_vendor_tree_present(self):
        self.assertTrue(os.path.isfile(os.path.join(VENDOR, ".claude-plugin", "marketplace.json")))
        self.assertTrue(os.path.isfile(os.path.join(VENDOR, "tools", "run-unit-tests.py")))
        self.assertGreater(len(plugin_dirs()), 0)

    def test_left_out_paths_absent(self):
        present = [d for d in LEFT_OUT_DIRS if os.path.exists(os.path.join(VENDOR, d))]
        sessions = [rel for rel, _ in text_files()
                    if os.path.basename(rel).startswith((".forge-session", ".builder-session"))]
        self.assertEqual(present, [], "left-out folders present")
        self.assertEqual(sessions, [], "session logs present")

    def test_generated_readme_and_kit_readme(self):
        with open(os.path.join(VENDOR, "README.md"), encoding="utf-8") as fh:
            first = fh.readline()
        self.assertTrue("AUTO-GENERATED by tools/gen-readme.py" in first, "README.md not generated")
        with open(os.path.join(VENDOR, "KIT-README.md"), encoding="utf-8") as fh:
            kit_readme = fh.read()
        for line in ("/plugin marketplace add ${KIT_HOME}/vendor/accelerator",
                     "/plugin install ai-baseline@accelerator"):
            self.assertTrue(line in kit_readme, "KIT-README.md lacks an install line")
        with open(os.path.join(ROOT, "PARAMETERS.md"), encoding="utf-8") as fh:
            params = fh.read()
        self.assertTrue("vendor/accelerator/KIT-README.md" in params, "PARAMETERS.md misses KIT-README.md")
        self.assertFalse("vendor/accelerator/README.md" in params, "PARAMETERS.md points at README.md")

    def test_project_settings_hold_no_absolute_paths(self):
        path = os.path.join(VENDOR, ".claude", "settings.json")
        if not os.path.exists(path):
            self.skipTest("no project settings vendored")
        commands = []
        for groups in load_json(path).get("hooks", {}).values():
            for group in groups:
                commands += [h.get("command", "") for h in group.get("hooks", [])]
        self.assertGreater(len(commands), 0)
        for command in commands:
            for word in command.split()[1:]:
                self.assertTrue(
                    word.startswith("$CLAUDE_PROJECT_DIR/") or not word.startswith("/"),
                    "absolute path in a hook command",
                )


# --- clean-data scan -------------------------------------------------------------

class ScanTest(unittest.TestCase):
    def test_clean_scan_is_zero(self):
        proc = subprocess.run(
            [sys.executable, CLEAN_SCAN, VENDOR],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            universal_newlines=True, timeout=TIMEOUT,
        )
        lines = proc.stdout.splitlines()
        codes = [l for l in lines if re.match(r"^[A-Z]+ \d+$", l) and not l.startswith("TOTAL ")]
        self.assertEqual(proc.returncode, 0, "scan findings: " + ", ".join(codes))
        self.assertEqual(lines[-1:], ["TOTAL 0"])


# --- identity from kit.config ----------------------------------------------------

class IdentityTest(unittest.TestCase):
    def setUp(self):
        self.name, self.email, self.homepage = placeholders()

    def author_problems(self, author):
        if not isinstance(author, dict):
            return ["author"]
        problems = []
        if author.get("name") != self.name:
            problems.append("author.name")
        if author.get("email") != self.email:
            problems.append("author.email")
        return problems

    def test_placeholders_are_the_documented_ones(self):
        self.assertEqual((self.name, self.email, self.homepage),
                         ("<your-name>", "you@example.com", ""))

    def test_plugin_json_authors_are_placeholders(self):
        bad = []
        for plugin in plugin_dirs():
            data = load_json(os.path.join(VENDOR, plugin, ".claude-plugin", "plugin.json"))
            bad += ["%s: %s" % (plugin, p) for p in self.author_problems(data.get("author"))]
        self.assertEqual(bad, [], "plugin.json author differs from kit.config.example.yaml")

    def test_marketplace_owner_and_authors_are_placeholders(self):
        data = marketplace()
        bad = ["owner: " + p for p in self.author_problems(data.get("owner"))]
        for entry in data["plugins"]:
            bad += ["%s: %s" % (entry.get("name"), p)
                    for p in self.author_problems(entry.get("author"))]
        self.assertEqual(bad, [], "marketplace author differs from kit.config.example.yaml")

    def test_homepage_empty_or_absent(self):
        bad = []
        for plugin in plugin_dirs():
            data = load_json(os.path.join(VENDOR, plugin, ".claude-plugin", "plugin.json"))
            if data.get("homepage"):
                bad.append(plugin + "/plugin.json")
        data = marketplace()
        for where, obj in [("marketplace", data), ("marketplace.metadata", data.get("metadata", {}))]:
            if obj.get("homepage"):
                bad.append(where)
        bad += ["marketplace: " + str(e.get("name")) for e in data["plugins"] if e.get("homepage")]
        self.assertEqual(bad, [], "homepage set")

    def test_no_release_url_for_the_suite(self):
        self.assertEqual(files_matching(SUITE_URL_RE), [], "hard-coded suite URL")

    def test_commit_examples_use_example_author(self):
        path = os.path.join(VENDOR, "release-manager", "skills", "conventional-commits", "SKILL.md")
        with open(path, encoding="utf-8") as fh:
            authors = [m.group(2) for m in map(COMMIT_EXAMPLE_RE.match, fh.read().splitlines()) if m]
        self.assertGreater(len(authors), 0, "no example commit lines found")
        others = sum(1 for a in authors if a != EXAMPLE_COMMIT_AUTHOR)
        self.assertEqual(others, 0, "example commit lines not by the example author")

    def test_synthetic_mac_path_rewritten(self):
        with open(os.path.join(VENDOR, "pattern-miner", "README.md"), encoding="utf-8") as fh:
            text = fh.read()
        self.assertFalse(("/" + "Users/") in text, "macOS home path in pattern-miner/README.md")
        self.assertTrue("/home/user/" in text, "no /home/user/ example in pattern-miner/README.md")


# --- builder plugin rename -------------------------------------------------------

class BuilderRenameTest(unittest.TestCase):
    def test_no_agent_forge_plugin(self):
        problems = []
        if os.path.exists(os.path.join(VENDOR, OLD_BUILDER)):
            problems.append("plugin folder")
        if any(e.get("name") == OLD_BUILDER for e in marketplace()["plugins"]):
            problems.append("marketplace entry")
        for plugin in plugin_dirs():
            data = load_json(os.path.join(VENDOR, plugin, ".claude-plugin", "plugin.json"))
            if data.get("name") == OLD_BUILDER:
                problems.append(plugin + "/plugin.json name")
        registry = load_json(os.path.join(VENDOR, "registry.json"))
        if any(e.get("name") == OLD_BUILDER for e in registry):
            problems.append("registry entry")
        self.assertEqual(problems, [], "old builder plugin still present")

    def test_agent_builder_plugin_present(self):
        manifest = os.path.join(VENDOR, NEW_BUILDER, ".claude-plugin", "plugin.json")
        self.assertTrue(os.path.isfile(manifest), "agent-builder plugin.json missing")
        self.assertEqual(load_json(manifest).get("name"), NEW_BUILDER)
        entries = [e for e in marketplace()["plugins"] if e.get("name") == NEW_BUILDER]
        self.assertEqual([e.get("source") for e in entries], ["./" + NEW_BUILDER])
        self.assertTrue(os.path.isfile(os.path.join(VENDOR, NEW_BUILDER, "commands", NEW_COMMAND + ".md")))

    def test_no_forge_command_file(self):
        found = sorted(
            os.path.relpath(os.path.join(dirpath, "forge.md"), VENDOR)
            for dirpath, _, filenames in os.walk(VENDOR)
            if os.path.basename(dirpath) == "commands" and "forge.md" in filenames
        )
        self.assertEqual(found, [], "forge command file present")
        registry = load_json(os.path.join(VENDOR, "registry.json"))
        self.assertEqual([e["name"] for e in registry if "forge.md" in e.get("commands", [])], [])

    def test_no_forge_command_in_text(self):
        self.assertEqual(files_matching(FORGE_COMMAND_RE), [], "/forge still referenced")

    def test_no_agent_forge_in_text(self):
        self.assertEqual(files_matching(re.compile(re.escape(OLD_BUILDER))), [],
                         "old builder name still referenced")

    def test_no_forge_injects_text(self):
        self.assertEqual(files_matching(FORGE_INJECTS_RE), [], "builder-injects text present")


# --- README plugin count ---------------------------------------------------------

def readme_counts(root):
    with open(os.path.join(root, "README.md"), encoding="utf-8") as fh:
        text = fh.read()
    match = NUMBER_PLUGINS_RE.search(text)
    stated = int(match.group(1)) if match else None
    section = text.split("## Capability catalog", 1)[-1].split("\n---", 1)[0]
    rows = [
        line for line in section.splitlines()
        if re.match(r"^\| [a-z0-9][a-z0-9-]* +\|", line)
    ]
    return stated, len(rows)


class ReadmeCountTest(unittest.TestCase):
    def test_readme_intro_count_matches_marketplace(self):
        stated, _ = readme_counts(VENDOR)
        self.assertEqual(stated, len(marketplace()["plugins"]))

    def test_readme_table_rows_match_marketplace(self):
        _, rows = readme_counts(VENDOR)
        self.assertEqual(rows, len(marketplace()["plugins"]))

    def test_marketplace_description_count_matches(self):
        match = NUMBER_PLUGINS_RE.search(marketplace()["metadata"]["description"])
        self.assertIsNotNone(match)
        self.assertEqual(int(match.group(1)), len(marketplace()["plugins"]))

    def test_readme_count_follows_the_plugins(self):
        kit = TempKit()
        self.addCleanup(kit.cleanup)
        removable = [p for p in plugin_dirs(kit.vendor)
                     if p not in ("ai-baseline", OLD_BUILDER, NEW_BUILDER)][-1]
        shutil.rmtree(os.path.join(kit.vendor, removable))
        path = os.path.join(kit.vendor, ".claude-plugin", "marketplace.json")
        data = load_json(path)
        data["plugins"] = [e for e in data["plugins"] if e.get("name") != removable]
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2)
            fh.write("\n")
        kit.regenerate(self)
        stated, rows = readme_counts(kit.vendor)
        expected = len(plugin_dirs(kit.vendor))
        self.assertEqual((stated, rows), (expected, expected))


# --- pricing and model IDs as data ---------------------------------------------------

class PricingTest(unittest.TestCase):
    def test_pricing_file_at_configured_path(self):
        path = configured_path("pricing_table_file")
        self.assertTrue(os.path.isfile(path), "pricing data file missing")
        data = load_json(path)
        self.assertIsInstance(data, dict)
        self.assertGreater(len(data), 0)

    def test_no_inline_rate_table_in_hooks(self):
        hooklibs = sorted(rel for rel, _ in text_files() if os.path.basename(rel) == "_hooklib.py")
        self.assertGreater(len(hooklibs), 0)
        inline = sorted(rel for rel, text in text_files()
                        if rel in hooklibs and INLINE_RATE_RE.search(text))
        self.assertEqual(inline, [], "rates hard-coded in hook code")

    def test_hooklib_reads_rates_from_the_data_file(self):
        kit = TempKit()
        self.addCleanup(kit.cleanup)
        path = configured_path("pricing_table_file", kit_home=kit.root, vendor=kit.vendor)
        self.assertTrue(os.path.isfile(path), "pricing data file missing")
        data = load_json(path)
        models = sorted({k for k in string_keys(data) if k.startswith("claude-")})
        self.assertGreater(len(models), 0, "no model ids in the pricing data file")
        probe = models + ["opus", "sonnet", "haiku", "example-unknown-model"]
        before = hooklib_rates(kit.vendor, kit.home, probe)
        self.assertTrue(all(any(v) for v in before.values()), "zero rates")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(scale_numbers(data, 2), fh, indent=2)
        after = hooklib_rates(kit.vendor, kit.home, probe)
        for model in probe:
            with self.subTest(model=model):
                self.assertEqual([round(v, 12) for v in after[model]],
                                 [round(2 * v, 12) for v in before[model]])


class ModelIdsTest(unittest.TestCase):
    def test_model_ids_file_at_configured_path(self):
        path = configured_path("model_ids_file")
        self.assertTrue(os.path.isfile(path), "model IDs data file missing")
        data = load_json(path)
        self.assertGreater(len(data.get("allowed", [])), 0)
        self.assertGreater(len(data.get("canonical", {})), 0)


# --- generators and drift checkers ---------------------------------------------------

class GeneratorTest(unittest.TestCase):
    def test_generators_idempotent_on_a_temp_copy(self):
        kit = TempKit()
        self.addCleanup(kit.cleanup)
        before = tree_digest(kit.vendor)
        kit.regenerate(self)
        self.assertEqual(changed_paths(before, tree_digest(kit.vendor)), [],
                         "generators changed the committed tree")
        kit.regenerate(self)
        self.assertEqual(changed_paths(before, tree_digest(kit.vendor)), [],
                         "second run changed the tree")

    def test_generators_fill_identity_from_kit_config(self):
        kit = TempKit()
        self.addCleanup(kit.cleanup)
        before = tree_digest(kit.vendor)
        kit.write_config(TEST_IDENTITY)
        kit.regenerate(self)
        name, email, home = (TEST_IDENTITY[k] for k in ("author_name", "author_email", "homepage"))
        bad = []
        for plugin in plugin_dirs(kit.vendor):
            data = load_json(os.path.join(kit.vendor, plugin, ".claude-plugin", "plugin.json"))
            author = data.get("author") or {}
            if (author.get("name"), author.get("email")) != (name, email):
                bad.append(plugin + "/plugin.json author")
            if data.get("homepage") not in (None, home):
                bad.append(plugin + "/plugin.json homepage")
        data = marketplace(kit.vendor)
        for label, author in [("owner", data.get("owner"))] + [
                (e.get("name"), e.get("author")) for e in data["plugins"]]:
            author = author or {}
            if (author.get("name"), author.get("email")) != (name, email):
                bad.append("marketplace %s author" % label)
        for rel in IDENTITY_DOCS:
            with open(os.path.join(kit.vendor, rel), encoding="utf-8") as fh:
                if email not in fh.read():
                    bad.append(rel)
        _, old_email, _ = placeholders()
        bad += [rel + " (placeholder left)" for rel, text in text_files(kit.vendor)
                if old_email in text and rel != PLACEHOLDER_SOURCE]
        self.assertEqual(bad, [], "identity not taken from kit.config.yaml")

        os.remove(os.path.join(kit.root, "kit.config.yaml"))
        kit.regenerate(self)
        self.assertEqual(changed_paths(before, tree_digest(kit.vendor)), [],
                         "regenerating with the example config does not restore the tree")


class DriftCheckersTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.kit = TempKit()

    @classmethod
    def tearDownClass(cls):
        cls.kit.cleanup()

    def check(self, tool):
        proc = self.kit.run_tool(tool)
        self.assertEqual(proc.returncode, 0, "%s exited %d" % (tool, proc.returncode))

    def test_baseline_drift(self):
        self.check("check-baseline-drift.py")

    def test_hooks_drift(self):
        self.check("check-hooks-drift.py")

    def test_marketplace_parity(self):
        self.check("check-marketplace-parity.py")

    def test_model_ids(self):
        self.check("check-model-ids.py")


if __name__ == "__main__":
    unittest.main()
