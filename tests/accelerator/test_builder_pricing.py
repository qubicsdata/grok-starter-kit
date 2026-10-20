"""Builder rename leftovers, data-file pricing and the suite's own gate.

Adds to test_scrub.py: no builder identifier still says "forge" (only plain
English words such as "forget" or "forgery" may remain), the registry and the
builder's own validators follow the rename, the hook pricing lives in a data
file that ships next to the hook scripts and stays in lockstep with the model
tiers, and every Python step of the suite's tools/validate.sh is green on a
temp copy.

Run: python3 -m unittest discover -s tests/accelerator -t tests/accelerator
KIT_ACCEL_VENDOR=<dir> runs it against another copy of the suite (mutation
checks). Failure messages name files, plugins and fields only. Stdlib only,
Python 3.9+.
"""

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
    NEW_BUILDER, NEW_COMMAND, TIMEOUT, VENDOR, TempKit, clean_env, configured_path,
    load_json, text_files,
)

# Every word holding "forge" that may stay: plain English, not the builder.
ENGLISH_FORGE_WORDS = {"forget", "forgetting", "fire-and-forget", "forgery"}
# "forge"/"forged" in the security sense (forging a token or a certificate).
SECURITY_SENSE_FILES = {os.path.join("security-companion", "skills", "stride-taxonomy.md")}
SECURITY_SENSE_WORDS = {"forge", "forged"}
FORGE_WORD_RE = re.compile(r"[\w.-]*forge[\w-]*", re.IGNORECASE)

SHIPPED_SCRIPTS = os.path.join("ai-baseline", "hooks", "scripts")
PRICING_NAME = "pricing.json"

# The Python steps of tools/validate.sh plus the builder's own validators.
GATE_STEPS = [
    ("check-baseline-drift.py",),
    ("check-baseline-coverage.py",),
    ("validate-fleet.py",),
    ("check-scenario-coverage.py",),
    ("check-calibration.py",),
    ("check-output-hygiene.py", "--calibrate"),
    ("check-craft-packs.py",),
    ("check-skill-refs.py",),
    ("check-stray-artifacts.py",),
    ("run-unit-tests.py",),
    ("check-hooks-drift.py",),
    ("check-installed-runtime.py",),
    ("check-passport.py", "--selftest"),
    ("check-model-ids.py",),
    ("check-model-ids.py", "--calibrate"),
    ("check-loop-alive.py",),
    ("run-scenarios.py", "--all"),
    ("check-marketplace-parity.py",),
    ("validate-plugin.py",),
    ("check-builder-session.py", "--calibrate"),
]


def forge_words(root=VENDOR):
    """{(relative path, lowercased word)} for every word holding "forge" in a
    file name or a text file under root, minus the allowed English words."""
    left = set()
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d != "__pycache__"]
        for name in dirnames + filenames:
            rel = os.path.relpath(os.path.join(dirpath, name), root)
            for word in FORGE_WORD_RE.findall(name):
                if os.path.splitext(word.lower())[0] not in ENGLISH_FORGE_WORDS:
                    left.add((rel, "name:" + word.lower()))
    for rel, text in text_files(root):
        for word in FORGE_WORD_RE.findall(text):
            word = word.lower().strip(".-")
            if word in ENGLISH_FORGE_WORDS:
                continue
            if rel in SECURITY_SENSE_FILES and word in SECURITY_SENSE_WORDS:
                continue
            left.add((rel, word))
    return left


def hooklib_probe(script_dir, home, code):
    """Run `code` in a fresh interpreter with `mod` = the _hooklib.py in
    script_dir; returns the CompletedProcess."""
    prelude = (
        "import importlib.util, json, sys\n"
        "spec = importlib.util.spec_from_file_location('kit_hooklib_probe', sys.argv[1])\n"
        "mod = importlib.util.module_from_spec(spec)\n"
        "spec.loader.exec_module(mod)\n"
    )
    return subprocess.run(
        [sys.executable, "-I", "-c", prelude + code, os.path.join(script_dir, "_hooklib.py")],
        cwd=home, env=clean_env(home), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        universal_newlines=True, timeout=TIMEOUT,
    )


def rates_from_data(data, model):
    entry = data["models"][model]
    return [entry["input"], entry["output"]]


# --- builder rename ----------------------------------------------------------------

class ForgeLeftoverTest(unittest.TestCase):
    def test_only_english_forge_words_left(self):
        left = sorted("%s (%s)" % item for item in forge_words())
        self.assertEqual(left, [], "builder identifiers still say forge")

    def test_registry_lists_the_builder_as_build_tool(self):
        registry = load_json(os.path.join(VENDOR, "registry.json"))
        entries = [e for e in registry if e.get("name") == NEW_BUILDER]
        self.assertEqual(len(entries), 1, "registry entry for the builder")
        self.assertEqual(entries[0].get("kind"), "build-tool")
        self.assertIn(NEW_COMMAND + ".md", entries[0].get("commands", []))

    def test_every_baseline_enforcer_says_agent_builder_injects(self):
        copies, missing = 0, []
        for rel, text in text_files():
            if os.path.basename(rel) != "baseline-enforcer.md":
                continue
            copies += 1
            if (NEW_BUILDER + " injects this skill") not in text:
                missing.append(rel)
        self.assertGreater(copies, 1)
        self.assertEqual(missing, [], "baseline-enforcer copies without the new sentence")

    def test_session_file_and_checker_renamed(self):
        tools = os.path.join(VENDOR, "tools")
        self.assertTrue(os.path.isfile(os.path.join(tools, "check-builder-session.py")))
        self.assertTrue(os.path.isfile(os.path.join(tools, "hooks", "builder_gate.py")))
        self.assertTrue(os.path.isdir(os.path.join(tools, "tests", "builder-session-fixtures")))
        hooks = load_json(os.path.join(VENDOR, "ai-baseline", "hooks", "hooks.json"))
        commands = json.dumps(hooks)
        self.assertIn("builder_gate.py", commands)


# --- pricing as data -----------------------------------------------------------------

class PricingDataTest(unittest.TestCase):
    def setUp(self):
        self.path = configured_path("pricing_table_file")
        self.assertTrue(os.path.isfile(self.path), "pricing data file missing")
        self.data = load_json(self.path)

    def test_schema(self):
        self.assertEqual(self.data.get("unit"), "usd_per_token")
        models = self.data.get("models")
        self.assertIsInstance(models, dict)
        self.assertGreater(len(models), 0)
        for model, entry in models.items():
            with self.subTest(model=model):
                self.assertTrue(model.startswith("claude-"))
                self.assertEqual(sorted(entry), ["input", "output"])
                for value in entry.values():
                    self.assertIsInstance(value, float)
                    self.assertGreater(value, 0)
        for tier, model in self.data.get("tiers", {}).items():
            self.assertIn(model, models, "tier %s points at an unknown model" % tier)
        self.assertIn(self.data.get("default"), models, "default model not priced")

    def test_tiers_match_the_model_id_tiers(self):
        model_ids = load_json(configured_path("model_ids_file"))
        self.assertEqual(sorted(self.data.get("tiers", {})), sorted(model_ids["canonical"]))

    def test_shipped_copy_is_byte_identical(self):
        shipped = os.path.join(VENDOR, SHIPPED_SCRIPTS, PRICING_NAME)
        self.assertTrue(os.path.isfile(shipped), "ai-baseline ships no pricing data file")
        with open(self.path, "rb") as a, open(shipped, "rb") as b:
            self.assertEqual(a.read(), b.read(), "shipped pricing data differs")

    def test_hook_readme_names_the_data_file(self):
        with open(os.path.join(VENDOR, "tools", "hooks", "README.md"), encoding="utf-8") as fh:
            text = fh.read()
        self.assertIn(PRICING_NAME, text)
        self.assertNotIn("_hooklib.PRICING", text)


class PricingRuntimeTest(unittest.TestCase):
    def setUp(self):
        self.kit = TempKit()
        self.addCleanup(self.kit.cleanup)
        self.pricing = configured_path("pricing_table_file", kit_home=self.kit.root,
                                       vendor=self.kit.vendor)
        self.assertTrue(os.path.isfile(self.pricing), "pricing data file missing")
        self.data = load_json(self.pricing)

    def rates(self, script_dir, models):
        proc = hooklib_probe(
            script_dir, self.kit.home,
            "print(json.dumps({m: list(mod.model_pricing(m)) for m in %r}))" % (models,))
        self.assertEqual(proc.returncode, 0, "model_pricing failed")
        return json.loads(proc.stdout)

    def test_installed_ai_baseline_reads_its_shipped_copy(self):
        # An installed plugin is ai-baseline alone: no suite root above it.
        alone = os.path.join(self.kit.base, "installed", "ai-baseline")
        shutil.copytree(os.path.join(self.kit.vendor, "ai-baseline"), alone)
        os.remove(self.pricing)
        models = sorted(self.data["models"])
        got = self.rates(os.path.join(alone, "hooks", "scripts"), models + ["example-unknown"])
        for model in models:
            self.assertEqual(got[model], rates_from_data(self.data, model))
        self.assertEqual(got["example-unknown"], rates_from_data(self.data, self.data["default"]))

    def test_tier_and_default_fallbacks_come_from_the_file(self):
        got = self.rates(os.path.join(self.kit.vendor, "tools", "hooks"),
                         ["claude-opus-9-example", "example-sonnet-alias", "haiku", "gpt-example", None])
        tiers = self.data["tiers"]
        self.assertEqual(got["claude-opus-9-example"], rates_from_data(self.data, tiers["opus"]))
        self.assertEqual(got["example-sonnet-alias"], rates_from_data(self.data, tiers["sonnet"]))
        self.assertEqual(got["haiku"], rates_from_data(self.data, tiers["haiku"]))
        self.assertEqual(got["gpt-example"], rates_from_data(self.data, self.data["default"]))
        self.assertEqual(got["null"], rates_from_data(self.data, self.data["default"]))

    def test_missing_file_raises_a_named_error_but_import_works(self):
        os.remove(self.pricing)
        proc = hooklib_probe(
            os.path.join(self.kit.vendor, "tools", "hooks"), self.kit.home,
            "print(mod.deny_response('PreToolUse', 'r', 's')[:1])\n"
            "try:\n"
            "    mod.model_pricing('claude-opus-4-8')\n"
            "except mod.PricingError as exc:\n"
            "    print('PricingError', 'pricing.json' in str(exc))\n")
        self.assertEqual(proc.returncode, 0, "import or probe failed")
        self.assertEqual(proc.stdout.split(), ["{", "PricingError", "True"])

    def test_malformed_file_raises_a_named_error(self):
        per_million = dict(self.data, unit="usd_per_million_tokens")
        negative = json.loads(json.dumps(self.data))
        negative["models"][self.data["default"]]["input"] = -1.0
        for body in ("{not json", json.dumps({"models": {"claude-x": {"input": "a"}}}),
                     json.dumps({"unit": "usd_per_token", "models": {}, "default": "claude-x"}),
                     json.dumps(per_million), json.dumps(negative), "[]"):
            with self.subTest(body=len(body)):
                with open(self.pricing, "w", encoding="utf-8") as fh:
                    fh.write(body)
                proc = hooklib_probe(
                    os.path.join(self.kit.vendor, "tools", "hooks"), self.kit.home,
                    "try:\n"
                    "    mod.cost_usd('claude-opus-4-8', 10, 10)\n"
                    "except mod.PricingError:\n"
                    "    print('PricingError')\n")
                self.assertEqual(proc.stdout.split(), ["PricingError"])

    def test_audit_append_stays_fail_open_without_pricing(self):
        os.remove(self.pricing)
        project = os.path.join(self.kit.base, "project")
        os.makedirs(project)
        fixture = os.path.join(self.kit.vendor, "tools", "tests", "transcript-fixtures", "sample.jsonl")
        env = clean_env(self.kit.home)
        env["CLAUDE_PROJECT_DIR"] = project
        proc = subprocess.run(
            [sys.executable, os.path.join(self.kit.vendor, "tools", "hooks", "audit_append.py"),
             "--event", "stop"],
            input=json.dumps({"session_id": "example-session", "transcript_path": fixture}),
            cwd=project, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            universal_newlines=True, timeout=TIMEOUT,
        )
        self.assertEqual(proc.returncode, 0)
        self.assertIn("pricing", proc.stderr)
        budget = os.path.join(project, ".ai-baseline", "budget.json")
        self.assertFalse(os.path.exists(budget) and load_json(budget).get("spent_usd"),
                         "spend accrued without a pricing file")

    def test_hooks_drift_catches_pricing_drift_and_sync_fixes_it(self):
        shipped = os.path.join(self.kit.vendor, SHIPPED_SCRIPTS, PRICING_NAME)
        with open(shipped, "a", encoding="utf-8") as fh:
            fh.write("\n")
        self.assertEqual(self.kit.run_tool("check-hooks-drift.py").returncode, 1, "drift missed")
        os.remove(shipped)
        self.assertEqual(self.kit.run_tool("check-hooks-drift.py").returncode, 1, "missing copy missed")
        self.assertEqual(self.kit.run_tool("sync-shipped-hooks.py").returncode, 0)
        self.assertEqual(self.kit.run_tool("check-hooks-drift.py").returncode, 0, "sync did not fix it")
        with open(self.pricing, "rb") as a, open(shipped, "rb") as b:
            self.assertEqual(a.read(), b.read())

    def test_model_ids_check_catches_a_missing_pricing_tier(self):
        data = dict(self.data)
        data["tiers"] = {k: v for k, v in data["tiers"].items() if k != "haiku"}
        with open(self.pricing, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2)
        self.assertEqual(self.kit.run_tool("check-model-ids.py").returncode, 1)

    def test_installed_self_check_requires_the_pricing_file(self):
        scripts = os.path.join(self.kit.vendor, SHIPPED_SCRIPTS)
        ok = self.kit.run([sys.executable, os.path.join(scripts, "self_check.py")])
        self.assertEqual(ok.returncode, 0, "self_check fails on the intact copy")
        os.remove(os.path.join(scripts, PRICING_NAME))
        broken = self.kit.run([sys.executable, os.path.join(scripts, "self_check.py")])
        self.assertNotEqual(broken.returncode, 0, "self_check passes without pricing data")


# --- the suite's own gate ------------------------------------------------------------

class SuiteGateTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.kit = TempKit()

    @classmethod
    def tearDownClass(cls):
        cls.kit.cleanup()

    def test_python_gate_steps_green(self):
        for step in GATE_STEPS:
            with self.subTest(step=" ".join(step)):
                self.assertTrue(os.path.isfile(os.path.join(self.kit.vendor, "tools", step[0])),
                                "%s missing" % step[0])
                proc = self.kit.run_tool(*step)
                self.assertEqual(proc.returncode, 0, "%s exited %d" % (" ".join(step), proc.returncode))

    def test_unit_test_runner_reports_all_files(self):
        proc = self.kit.run_tool("run-unit-tests.py")
        match = re.search(r"run-unit-tests: (\d+)/(\d+) test file", proc.stdout)
        self.assertIsNotNone(match)
        self.assertEqual(match.group(1), match.group(2))
        self.assertEqual(int(match.group(2)), 19)


if __name__ == "__main__":
    unittest.main()
