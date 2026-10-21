"""A gitleaks config or ignore file at the top of the scanned repo must not zero GITLEAKS.

gitleaks reads `.gitleaks.toml` and `.gitleaksignore` from the folder it
scans, tracked or not. The fake gitleaks below does the same: when either file
sits at the top of the repo it reports nothing, as an allow-all config would.
clean_scan.py fails closed (exit 2, no count line) instead of passing that
silent zero on. Synthetic temp repos only.
"""

import json
import unittest

try:
    from tests.scan import support
    from tests.scan import test_history
except ImportError:  # run with: python3 -m unittest discover -s tests/scan
    import support
    import test_history

CONFIG = "." + "gitleaks" + ".toml"
IGNORE = "." + "gitleaks" + "ignore"
ALLOW_ALL = "[allowlist]\npaths = ['''.*''']\n"

FAKE_GITLEAKS_READS_CONFIG = test_history.FAKE_HEAD + '''
top = argv[-1]
if any(os.path.lexists(os.path.join(top, n)) for n in (".gitleaks" + ".toml", ".gitleaks" + "ignore")):
    findings = []
if "--report-path" in argv:
    with open(argv[argv.index("--report-path") + 1], "w") as h:
        json.dump(findings, h)
code = int(argv[argv.index("--exit-code") + 1]) if "--exit-code" in argv else 1
sys.exit(code if findings else 0)
'''


@unittest.skipUnless(support.git_available(), "git not installed")
class GitleaksConfigTest(support.ScanTestCase):
    def setUp(self):
        super().setUp()
        support.alias_guard(self)
        support.init_repo(self.tree)
        self.tree.write("README.md", "Example kit\n")
        support.commit_all(self.tree, "seed")
        self.bin = support.Tree(prefix="kitscan-bin-")
        self.addCleanup(self.bin.cleanup)
        self.gitleaks = support.write_executable(self.bin.path("gitleaks"), FAKE_GITLEAKS_READS_CONFIG)
        with open(self.gitleaks + ".cfg.json", "w", encoding="utf-8") as handle:
            json.dump({"log": self.bin.path("argv.json"), "findings": [test_history.gitleaks_finding(1)]}, handle)

    def scan_history(self, *extra):
        return self.scan_tree("--history", "--allowed-identity", support.ALLOWED_IDENTITY,
                              "--gitleaks", self.gitleaks, *extra)

    def assert_fails_closed(self, result):
        self.assertEqual(result.code, 2, "a gitleaks config at the repo top must fail closed")
        self.assertEqual(result.counts, {})
        self.assertIsNone(result.total)
        self.assert_no_leak(result, [CONFIG, IGNORE, self.tree.root])

    def test_without_a_config_the_finding_counts(self):
        result = self.scan_history()
        self.assert_single(result, "GITLEAKS")

    def test_untracked_config_fails_closed(self):
        self.tree.write(CONFIG, ALLOW_ALL)
        self.assert_fails_closed(self.scan_history())

    def test_ignored_config_fails_closed(self):
        self.tree.write(".gitignore", CONFIG + "\n")
        support.commit_all(self.tree, "ignore the local config")
        self.tree.write(CONFIG, ALLOW_ALL)
        self.assertEqual(support.git(self.tree.root, "status", "--porcelain"), "", "the config should be ignored")
        self.assert_fails_closed(self.scan_history())

    def test_tracked_config_fails_closed(self):
        self.tree.write(CONFIG, ALLOW_ALL)
        support.commit_all(self.tree, "add a config")
        self.assert_fails_closed(self.scan_history())

    def test_untracked_ignore_file_fails_closed(self):
        self.tree.write(IGNORE, "a" * 40 + ":f1.txt:generic-api-key:1\n")
        self.assert_fails_closed(self.scan_history())

    def test_config_name_in_another_case_fails_closed(self):
        self.tree.write(CONFIG.upper(), ALLOW_ALL)
        self.assert_fails_closed(self.scan_history())

    def test_scanning_a_subfolder_still_checks_the_repo_top(self):
        self.tree.write("sub/note.md", "clean\n")
        self.tree.write(CONFIG, ALLOW_ALL)
        result = self.scan(self.tree.path("sub"), "--history", "--allowed-identity", support.ALLOWED_IDENTITY,
                           "--gitleaks", self.gitleaks)
        self.assert_fails_closed(result)

    def test_config_in_a_subfolder_is_not_read_and_does_not_fail(self):
        self.tree.write("sub/" + CONFIG, ALLOW_ALL)
        result = self.scan_history()
        self.assert_single(result, "GITLEAKS")

    def test_without_gitleaks_a_config_is_not_an_error(self):
        self.tree.write(CONFIG, ALLOW_ALL)
        result = self.scan_tree("--history", "--allowed-identity", support.ALLOWED_IDENTITY)
        self.assert_clean(result)
        self.assertIn("gitleaks", result.skips)


if __name__ == "__main__":
    unittest.main()
