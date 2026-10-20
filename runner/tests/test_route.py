import unittest
from helpers import TempEnv
from crlib.route import route, RouteError


class RouteTests(unittest.TestCase):
    def setUp(self):
        self.t = TempEnv().__enter__(); self.cfg = self.t.cfg

    def tearDown(self):
        self.t.__exit__()

    def test_table(self):
        exp = {"security": "opus", "implement": "opus", "architecture": "opus", "hard-debug": "opus", "plan": "opus",
               "review-fix": "opus", "pre-review": "opus", "review": "opus", "test-hardening": "opus",
               "medium": "opusplan", "test": "opus", "refactor": "sonnet",
               "rebase": "sonnet", "rename": "sonnet", "pr-body": "sonnet", "mechanical": "sonnet", "rebase-fallout": "sonnet",
               "docs": "sonnet", "test-hardening-nonsecurity": "sonnet",
               "format": "sonnet", "log-triage": "sonnet", "log-summary": "sonnet", "fable-implement": "fable"}
        for tt, m in exp.items():
            r = route(self.cfg, task_type=tt)
            self.assertEqual((tt, r["model"], r["source"]), (tt, m, "route"))

    def test_haiku_is_opt_in_only(self):
        self.assertEqual(route(self.cfg, task_type="log-triage", allow_haiku=True)["model"], "haiku")
        self.assertEqual(route(self.cfg, task_type="format", allow_haiku=True)["model"], "haiku")
        self.assertEqual(route(self.cfg, task_type="rebase", allow_haiku=True)["model"], "sonnet")  # not trivial

    def test_override_wins_and_is_labelled(self):
        r = route(self.cfg, task_type="rebase", model_flag="opus")
        self.assertEqual((r["model"], r["source"]), ("opus", "override-flag"))
        self.assertIn("route would be sonnet", r["reason"])
        r = route(self.cfg, task_type="security", env_model="haiku")
        self.assertEqual((r["model"], r["source"]), ("haiku", "override-env"))
        r = route(self.cfg, task_type="security", model_flag="sonnet", env_model="haiku")
        self.assertEqual((r["model"], r["source"]), ("sonnet", "override-flag"))

    def test_default_no_options_passes_no_model(self):
        r = route(self.cfg)
        self.assertEqual((r["model"], r["fallback_model"], r["source"]), (None, None, "default"))

    def test_fallback(self):
        self.assertEqual(route(self.cfg, task_type="security")["fallback_model"], "sonnet")
        self.assertEqual(route(self.cfg, task_type="rebase")["fallback_model"], "opus")
        self.assertEqual(route(self.cfg, task_type="rebase", fallback_flag="haiku")["fallback_model"], "haiku")
        self.assertIsNone(route(self.cfg, task_type="rebase", fallback_flag="sonnet")["fallback_model"])  # == primary
        self.assertEqual(route(self.cfg, model_flag="claude-opus-5-5")["fallback_model"], "sonnet")

    def test_unknown_and_invalid(self):
        with self.assertRaises(RouteError):
            route(self.cfg, task_type="rebsae")
        with self.assertRaises(RouteError):
            route(self.cfg, model_flag="opus; rm -rf /")

    def test_subagent_default_inherits(self):
        self.assertIsNone(route(self.cfg, task_type="implement")["subagent_model"])
        self.assertEqual(route(self.cfg, task_type="implement", env_subagent="sonnet")["subagent_model"], "sonnet")


class ProfileTests(unittest.TestCase):
    def setUp(self):
        self.t = TempEnv().__enter__(); self.cfg = self.t.cfg

    def tearDown(self):
        self.t.__exit__()

    def plugins_off(self, tt):
        r = route(self.cfg, task_type=tt)
        return {k for k, v in r["settings"]["enabledPlugins"].items() if v is False}

    def test_superpowers_only_for_security_and_core(self):
        for tt in ("security", "implement", "review-fix", "hard-debug"):
            self.assertNotIn("superpowers@claude-plugins-official", self.plugins_off(tt), tt)
        for tt in ("rebase", "mechanical", "pr-body", "docs", "medium", "pre-review", "log-triage", "plan"):
            self.assertIn("superpowers@claude-plugins-official", self.plugins_off(tt), tt)
        self.assertNotIn("pr-review-toolkit@claude-plugins-official", self.plugins_off("pre-review"))
        self.assertIn("pr-review-toolkit@claude-plugins-official", self.plugins_off("rebase"))

    def test_lean_settings_and_strict_mcp(self):
        r = route(self.cfg, task_type="rebase")
        self.assertEqual(r["settings"]["skillListingMaxDescChars"], 80)
        self.assertEqual(r["extra_flags"], ["--strict-mcp-config"])
        self.assertEqual((r["effort"], r["profile"]), ("medium", "lean_no_superpowers"))
        self.assertEqual(route(self.cfg, task_type="security")["effort"], "high")
        self.assertEqual(route(self.cfg, task_type="rebase", effort_flag="low")["effort"], "low")
        with self.assertRaises(RouteError):
            route(self.cfg, task_type="rebase", effort_flag="extreme")

    def test_experiments_default_off(self):
        r = route(self.cfg, task_type="implement")
        self.assertEqual(r["experiments"], [])
        self.assertNotIn("--autocompact", r["extra_flags"])
        self.assertNotIn("promptCacheTtl", r["settings"])

    def test_experiments_opt_in(self):
        r = route(self.cfg, task_type="implement", experiments=["autocompact", "prompt_cache_ttl"])
        self.assertEqual(r["extra_flags"], ["--strict-mcp-config", "--autocompact", "200k"])
        self.assertEqual(r["settings"]["promptCacheTtl"], "5m")
        self.cfg["experiments"]["autocompact"]["enabled"] = True
        self.assertIn("--autocompact", route(self.cfg, task_type="review-fix")["extra_flags"])
        self.assertNotIn("--autocompact", route(self.cfg, task_type="rebase")["extra_flags"])  # apply_to
        with self.assertRaises(RouteError):
            route(self.cfg, task_type="rebase", experiments=["nope"])

    def test_settings_allowlist(self):
        self.cfg["profiles"]["lean"]["settings"]["permissions"] = {"allow": ["Bash(*)"]}
        with self.assertRaises(RouteError):
            route(self.cfg, task_type="security")
        del self.cfg["profiles"]["lean"]["settings"]["permissions"]
        self.cfg["profiles"]["lean"]["settings"]["hooks"] = {}
        with self.assertRaises(RouteError):
            route(self.cfg, task_type="security")
        del self.cfg["profiles"]["lean"]["settings"]["hooks"]
        self.cfg["profiles"]["lean"]["extra_flags"].append("--dangerously-skip-permissions")
        with self.assertRaises(RouteError):
            route(self.cfg, task_type="security")

    def test_aliases(self):
        self.assertEqual(route(self.cfg, task_type="analysis/docs")["task_type"], "docs")
        self.assertEqual(route(self.cfg, task_type="feature+tests")["model"], "opus")

    def test_no_options_no_profile(self):
        r = route(self.cfg)
        self.assertEqual((r["settings"], r["extra_flags"], r["effort"]), (None, [], None))


if __name__ == "__main__":
    unittest.main()
