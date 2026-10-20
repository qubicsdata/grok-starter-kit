"""The external scanners never see GITLEAKS_* or TRUFFLEHOG_* variables.

gitleaks and trufflehog read settings such as a config file or an allowlist from variables with
those prefixes, so one set in the calling shell could make them drop rules or paths without a
trace. The scanner starts them without any such variable. Fake binaries record the environment
they were started with; no real gitleaks or trufflehog is needed.
"""

import json
import os
import unittest

try:
    from tests.scan import support
except ImportError:  # run with: python3 -m unittest discover -s tests/scan
    import support

# Synthetic variables only; the values name no real file.
TOOL_VARS = {
    "GITLEAKS_CONFIG": "synthetic-gitleaks.toml",
    "GITLEAKS_CONFIG_TOML": "[allowlist]",
    "GITLEAKS_SYNTHETIC_EXTRA": "1",
    "TRUFFLEHOG_EXCLUDE_PATHS": "synthetic-excludes.txt",
    "TRUFFLEHOG_SYNTHETIC_EXTRA": "1",
}
KEEP_VAR = ("KITSCAN_SYNTHETIC_KEEP", "kept")

# Each fake writes the environment it got to `<its own path>.env.json` and reports a clean run.
FAKE_ENV_HEAD = '''
import json, os, sys
argv = sys.argv[1:]
with open(os.path.abspath(sys.argv[0]) + ".env.json", "w") as h:
    json.dump(dict(os.environ), h)
'''

FAKE_GITLEAKS = FAKE_ENV_HEAD + '''
if "--report-path" in argv:
    with open(argv[argv.index("--report-path") + 1], "w") as h:
        json.dump([], h)
sys.exit(0)
'''

FAKE_TRUFFLEHOG = FAKE_ENV_HEAD + '''
sys.exit(0)
'''


@unittest.skipUnless(support.git_available(), "git not installed")
class ToolEnvironmentTest(support.ScanTestCase):
    def setUp(self):
        super().setUp()
        support.init_repo(self.tree)
        self.tree.write("README.md", "Example kit\n")
        support.commit_all(self.tree, "seed")
        self.bin = support.Tree(prefix="kitscan-bin-")
        self.addCleanup(self.bin.cleanup)
        self.home = support.Tree(prefix="kitscan-home-")
        self.addCleanup(self.home.cleanup)

    def fake(self, name, body):
        return support.write_executable(self.bin.path(name), body)

    def seen_env(self, tool):
        path = tool + ".env.json"
        self.assertTrue(os.path.exists(path), "the scanner binary was never run")
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)

    def scan_with_vars(self, *args):
        extra = dict(TOOL_VARS)
        extra[KEEP_VAR[0]] = KEEP_VAR[1]
        result = self.scan_tree(*args, home=self.home.root, env_extra=extra)
        self.assert_clean(result)
        return result

    def assert_no_tool_vars(self, env):
        leaked = sorted(k for k in env if k.startswith(("GITLEAKS_", "TRUFFLEHOG_")))
        self.assertEqual(leaked, [], "a scanner setting variable reached the external tool")

    def test_gitleaks_gets_no_gitleaks_variable(self):
        gl = self.fake("gitleaks", FAKE_GITLEAKS)
        self.scan_with_vars("--gitleaks", gl)
        env = self.seen_env(gl)
        for name in ("GITLEAKS_CONFIG", "GITLEAKS_CONFIG_TOML", "GITLEAKS_SYNTHETIC_EXTRA"):
            self.assertFalse(name in env, name + " reached gitleaks")

    def test_trufflehog_gets_no_trufflehog_variable(self):
        th = self.fake("trufflehog", FAKE_TRUFFLEHOG)
        self.scan_with_vars("--trufflehog", th)
        env = self.seen_env(th)
        for name in ("TRUFFLEHOG_EXCLUDE_PATHS", "TRUFFLEHOG_SYNTHETIC_EXTRA"):
            self.assertFalse(name in env, name + " reached trufflehog")

    def test_neither_tool_gets_either_prefix(self):
        gl = self.fake("gitleaks", FAKE_GITLEAKS)
        th = self.fake("trufflehog", FAKE_TRUFFLEHOG)
        self.scan_with_vars("--gitleaks", gl, "--trufflehog", th)
        for tool in (gl, th):
            with self.subTest(tool=os.path.basename(tool)):
                self.assert_no_tool_vars(self.seen_env(tool))

    def test_other_variables_still_pass_and_home_is_temporary(self):
        gl = self.fake("gitleaks", FAKE_GITLEAKS)
        th = self.fake("trufflehog", FAKE_TRUFFLEHOG)
        self.scan_with_vars("--gitleaks", gl, "--trufflehog", th)
        for tool in (gl, th):
            with self.subTest(tool=os.path.basename(tool)):
                env = self.seen_env(tool)
                self.assertEqual(env.get(KEEP_VAR[0]), KEEP_VAR[1], "an unrelated variable was dropped")
                self.assertEqual(env.get("GIT_TERMINAL_PROMPT"), "0")
                self.assertNotEqual(os.path.realpath(env.get("HOME", "")), os.path.realpath(self.home.root))

    def test_variables_do_not_change_the_scan_result(self):
        gl = self.fake("gitleaks", FAKE_GITLEAKS)
        result = self.scan_with_vars("--gitleaks", gl)
        self.assertNotIn("gitleaks", result.skips)
        self.assert_no_leak(result, list(TOOL_VARS.values()))


if __name__ == "__main__":
    unittest.main()
