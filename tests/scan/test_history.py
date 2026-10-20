"""History mode (--history, --allowed-identity) and the optional external scanners.

Every repo is created by the test in a temp dir with a synthetic identity.
"""

import json
import os
import unittest

try:
    from tests.scan import support
except ImportError:  # run with: python3 -m unittest discover -s tests/scan
    import support

P = support.planted()
OTHER_NAME = "Other Person"
OTHER_EMAIL = "other@example.org"
OTHER_IDENTITY = "%s <%s>" % (OTHER_NAME, OTHER_EMAIL)


@unittest.skipUnless(support.git_available(), "git not installed")
class HistoryTestCase(support.ScanTestCase):
    def setUp(self):
        super().setUp()
        support.init_repo(self.tree)
        self.tree.write("README.md", "Example kit\n")
        support.commit_all(self.tree, "seed")

    def scan_history(self, *extra):
        return self.scan_tree("--history", "--allowed-identity", support.ALLOWED_IDENTITY, *extra)


class HeaderTest(HistoryTestCase):
    def test_allowed_identity_everywhere_is_clean(self):
        self.tree.write("a.md", "more\n")
        support.commit_all(self.tree, "second")
        self.assert_clean(self.scan_history())

    def test_other_author_counts_one_header(self):
        self.tree.write("a.md", "more\n")
        support.commit_all(self.tree, "second", author=OTHER_IDENTITY)
        self.assert_single(self.scan_history(), "HDR")

    def test_other_author_and_committer_count_two(self):
        self.tree.write("a.md", "more\n")
        support.commit_all(self.tree, "second", name=OTHER_NAME, email=OTHER_EMAIL)
        result = self.scan_history()
        self.assert_only_count_lines(result)
        self.assertEqual(result.count("HDR"), 2)
        self.assertEqual(result.total, 2)

    def test_allowed_email_under_another_name_counts(self):
        self.tree.write("a.md", "more\n")
        support.commit_all(self.tree, "second", author="Someone Else <" + support.ALLOWED_EMAIL + ">")
        self.assert_single(self.scan_history(), "HDR")

    def test_identity_is_taken_from_the_command_line_only(self):
        self.tree.write("a.md", "more\n")
        support.commit_all(self.tree, "second")
        result = self.scan_tree("--history", "--allowed-identity", OTHER_IDENTITY)
        self.assert_only_count_lines(result)
        self.assertEqual(result.count("HDR"), 4)

    def test_commits_on_other_branches_are_checked(self):
        support.git(self.tree.root, "checkout", "-q", "-b", "side")
        self.tree.write("side.md", "side\n")
        support.commit_all(self.tree, "side work", author=OTHER_IDENTITY)
        support.git(self.tree.root, "checkout", "-q", "main")
        self.assert_single(self.scan_history(), "HDR")

    def test_allowed_identity_is_never_printed(self):
        self.tree.write("a.md", "more\n")
        support.commit_all(self.tree, "second", author=OTHER_IDENTITY)
        result = self.scan_history()
        self.assertEqual(result.code, 1)
        self.assert_no_leak(result, [support.ALLOWED_NAME, support.ALLOWED_EMAIL, OTHER_NAME, OTHER_EMAIL])

    def test_without_history_headers_are_not_checked(self):
        self.tree.write("a.md", "more\n")
        support.commit_all(self.tree, "second", author=OTHER_IDENTITY)
        self.assert_clean(self.scan_tree())

    def test_history_without_identity_exits_2_inside_a_repo(self):
        result = self.scan_tree("--history")
        self.assertEqual(result.code, 2)
        self.assertIsNone(result.total)

    def test_malformed_identity_exits_2_inside_a_repo(self):
        result = self.scan_tree("--history", "--allowed-identity", "no-angle-brackets")
        self.assertEqual(result.code, 2)
        self.assertIsNone(result.total)

    def test_tagger_other_than_allowed_counts(self):
        support.git(self.tree.root, "tag", "-a", "v1", "-m", "release", name=OTHER_NAME, email=OTHER_EMAIL)
        self.assert_single(self.scan_history(), "HDR")


class MessageTest(HistoryTestCase):
    def test_email_in_commit_message(self):
        support.commit_all(self.tree, "contact " + P["email"])
        self.assert_single(self.scan_history(), "MSG")

    def test_noreply_in_co_authored_by_trailer(self):
        support.commit_all(self.tree, "pair work\n\nCo-authored-by: Pair <" + P["noreply"] + ">")
        self.assert_single(self.scan_history(), "MSG")

    def test_alias_code_in_message(self):
        support.commit_all(self.tree, "notes for " + P["alias_ch"])
        self.assert_single(self.scan_history(), "MSG")

    def test_home_path_in_message(self):
        support.commit_all(self.tree, "moved from " + P["box_home"])
        self.assert_single(self.scan_history(), "MSG")

    def test_bidi_in_message(self):
        support.commit_all(self.tree, "tidy" + support.RLO + "up")
        self.assert_single(self.scan_history(), "MSG")

    def test_annotated_tag_message(self):
        support.git(self.tree.root, "tag", "-a", "v1", "-m", "release for " + P["alias_cl"])
        self.assert_single(self.scan_history(), "MSG")

    def test_two_messages_count_two(self):
        support.commit_all(self.tree, "one " + P["email"])
        support.commit_all(self.tree, "two " + P["uuid"])
        result = self.scan_history()
        self.assert_only_count_lines(result)
        self.assertEqual(result.count("MSG"), 2)

    def test_term_in_message(self):
        outside = support.Tree()
        self.addCleanup(outside.cleanup)
        term = "Quor" + "vane"
        terms = outside.write("terms.tsv", term + "\n")
        support.commit_all(self.tree, "meeting with " + term.lower())
        self.assert_single(self.scan_history("--terms-file", terms), "MSG")

    def test_clean_messages_with_allowed_trailer(self):
        support.commit_all(self.tree, "feat: x\n\nCo-authored-by: Pair <pair@example.com>")
        self.assert_clean(self.scan_history())

    def test_message_text_is_never_printed(self):
        support.commit_all(self.tree, "contact " + P["email"])
        result = self.scan_history()
        self.assertEqual(result.code, 1)
        self.assert_no_leak(result, [P["email"], "contact", self.tree.root])


class HistoryBlobTest(HistoryTestCase):
    def test_deleted_file_still_counts_with_history(self):
        self.tree.write("old.md", P["email"] + "\n")
        support.commit_all(self.tree, "add")
        os.remove(self.tree.path("old.md"))
        support.commit_all(self.tree, "remove")
        self.assert_clean(self.scan_tree())
        self.assert_single(self.scan_history(), "EMAIL")

    def test_old_file_name_still_counts_with_history(self):
        self.tree.write(P["superpowers"], "x\n")
        support.commit_all(self.tree, "add")
        os.remove(self.tree.path(P["superpowers"]))
        support.commit_all(self.tree, "remove")
        self.assert_single(self.scan_history(), "SUPERPOWERS")

    def test_same_blob_in_many_commits_counts_once(self):
        self.tree.write("old.md", P["email"] + "\n")
        support.commit_all(self.tree, "add")
        for n in range(3):
            self.tree.write("other%d.md" % n, "x\n")
            support.commit_all(self.tree, "more %d" % n)
        self.assert_single(self.scan_history(), "EMAIL")

    def test_commit_count_is_not_a_finding(self):
        for n in range(3):
            self.tree.write("f%d.md" % n, "x\n")
            support.commit_all(self.tree, "c %d" % n)
        self.assert_clean(self.scan_history())

    def test_uncommitted_work_tree_is_still_scanned(self):
        self.tree.write("new.md", P["email"] + "\n")
        self.assert_single(self.scan_history(), "EMAIL")

    def test_file_present_in_tree_and_history_counts_once(self):
        self.tree.write("old.md", P["email"] + "\n")
        support.commit_all(self.tree, "add")
        self.assert_single(self.scan_history(), "EMAIL")

    def test_gitmodules_in_history_counts_struct(self):
        self.tree.write(".gitmodules", "[submodule \"x\"]\n\tpath = x\n")
        support.commit_all(self.tree, "add")
        os.remove(self.tree.path(".gitmodules"))
        support.commit_all(self.tree, "remove")
        self.assert_clean(self.scan_tree())
        self.assert_single(self.scan_history(), "STRUCT")

    def _commit_gitlink(self):
        # `git add -A` would drop a gitlink whose folder is absent, so commit the index as is.
        support.git(self.tree.root, "update-index", "--add", "--cacheinfo", "160000," + "1" * 40 + ",sub")
        support.git(self.tree.root, "commit", "-q", "-m", "add sub")

    def test_gitlink_in_history_counts_struct_once(self):
        self._commit_gitlink()
        self.assert_single(self.scan_tree(), "STRUCT")
        self.assert_single(self.scan_history(), "STRUCT")

    def test_removed_gitlink_still_counts_with_history(self):
        self._commit_gitlink()
        support.git(self.tree.root, "update-index", "--force-remove", "sub")
        support.git(self.tree.root, "commit", "-q", "-m", "drop sub")
        self.assert_clean(self.scan_tree())
        self.assert_single(self.scan_history(), "STRUCT")


# Fake scanners: each reads `<its own path>.cfg.json` ({"log": path, "findings": [...]}),
# so they need no environment from the scanner (which may run them with a minimal one).
FAKE_HEAD = '''
import json, os, sys
argv = sys.argv[1:]
with open(os.path.abspath(sys.argv[0]) + ".cfg.json") as h:
    cfg = json.load(h)
with open(cfg["log"], "w") as h:
    json.dump(argv, h)
findings = cfg.get("findings", [])
'''

FAKE_GITLEAKS = FAKE_HEAD + '''
if "--report-path" in argv:
    with open(argv[argv.index("--report-path") + 1], "w") as h:
        json.dump(findings, h)
code = int(argv[argv.index("--exit-code") + 1]) if "--exit-code" in argv else 1
sys.exit(code if findings else 0)
'''

FAKE_TRUFFLEHOG = FAKE_HEAD + '''
for item in findings:
    print(json.dumps(item))
sys.exit(183 if findings and "--fail" in argv else 0)
'''

FAKE_BROKEN = '''
import sys
sys.exit(3)
'''


def gitleaks_finding(n):
    return {"RuleID": "generic-api-key", "File": "f%d.txt" % n, "Commit": "a" * 40, "Secret": "x"}


def trufflehog_finding(n):
    return {"DetectorName": "Generic",
            "SourceMetadata": {"Data": {"Git": {"file": "f%d.txt" % n, "commit": "a" * 40}}}}


@unittest.skipUnless(support.git_available(), "git not installed")
class ScannerTest(support.ScanTestCase):
    def setUp(self):
        super().setUp()
        support.init_repo(self.tree)
        self.tree.write("README.md", "Example kit\n")
        support.commit_all(self.tree, "seed")
        self.bin = support.Tree(prefix="kitscan-bin-")
        self.addCleanup(self.bin.cleanup)
        self.log = self.bin.path("argv.json")

    def fake(self, name, body, findings=None):
        path = support.write_executable(self.bin.path(name), body)
        with open(path + ".cfg.json", "w", encoding="utf-8") as handle:
            json.dump({"log": self.log, "findings": findings or []}, handle)
        return path

    def argv(self):
        self.assertTrue(os.path.exists(self.log), "the scanner binary was never run")
        with open(self.log, encoding="utf-8") as handle:
            return json.load(handle)

    def test_absent_scanners_print_skip(self):
        result = self.scan_tree()
        self.assert_clean(result)
        self.assertIn("gitleaks", result.skips)
        self.assertIn("trufflehog", result.skips)

    def test_gitleaks_findings_are_counted(self):
        gl = self.fake("gitleaks", FAKE_GITLEAKS, [gitleaks_finding(1), gitleaks_finding(2)])
        result = self.scan_tree("--gitleaks", gl)
        self.assert_only_count_lines(result)
        self.assertEqual(result.count("GITLEAKS"), 2)
        self.assertEqual(result.code, 1)
        self.assertNotIn("gitleaks", result.skips)

    def test_gitleaks_clean_run(self):
        gl = self.fake("gitleaks", FAKE_GITLEAKS)
        result = self.scan_tree("--gitleaks", gl)
        self.assert_clean(result)
        self.assertNotIn("gitleaks", result.skips)
        self.assertIn("trufflehog", result.skips)

    def test_gitleaks_fixed_argv(self):
        gl = self.fake("gitleaks", FAKE_GITLEAKS)
        self.scan_tree("--gitleaks", gl)
        argv = self.argv()
        self.assertEqual(argv[0], "git")
        self.assertIn("--log-opts=--all", argv)
        self.assertIn("--redact", argv)
        self.assertIn("--report-path", argv)
        absolute = [os.path.realpath(a) for a in argv if a.startswith("/")]
        self.assertIn(os.path.realpath(self.tree.root), absolute, "repo not passed")

    def test_gitleaks_runs_without_a_shell(self):
        spaced = support.Tree(prefix="kitscan-sp aced;echo-")
        self.addCleanup(spaced.cleanup)
        support.init_repo(spaced)
        spaced.write("README.md", "x\n")
        support.commit_all(spaced, "seed")
        gl = self.fake("gitleaks", FAKE_GITLEAKS)
        self.scan(spaced.root, "--gitleaks", gl)
        absolute = [os.path.realpath(a) for a in self.argv() if a.startswith("/")]
        self.assertIn(os.path.realpath(spaced.root), absolute, "repo path split or quoted")

    def test_gitleaks_output_holds_no_finding_text(self):
        gl = self.fake("gitleaks", FAKE_GITLEAKS, [gitleaks_finding(1)])
        result = self.scan_tree("--gitleaks", gl)
        self.assertEqual(result.code, 1)
        self.assert_no_leak(result, ["generic-api-key", "f1.txt", "a" * 40, self.tree.root])

    def test_trufflehog_findings_are_counted(self):
        th = self.fake("trufflehog", FAKE_TRUFFLEHOG, [trufflehog_finding(1)])
        result = self.scan_tree("--trufflehog", th)
        self.assert_single(result, "TRUFFLEHOG")
        self.assertNotIn("trufflehog", result.skips)

    def test_trufflehog_fixed_argv(self):
        th = self.fake("trufflehog", FAKE_TRUFFLEHOG)
        self.scan_tree("--trufflehog", th)
        argv = self.argv()
        self.assertEqual(argv[0], "git")
        for flag in ("--no-verification", "--no-update", "--json"):
            self.assertIn(flag, argv)
        self.assertTrue(any(os.path.realpath(self.tree.root) in a for a in argv), "repo not passed")

    def test_trufflehog_output_holds_no_finding_text(self):
        th = self.fake("trufflehog", FAKE_TRUFFLEHOG, [trufflehog_finding(1)])
        result = self.scan_tree("--trufflehog", th)
        self.assertEqual(result.code, 1)
        self.assert_no_leak(result, ["Generic", "f1.txt", "a" * 40, self.tree.root])

    def test_both_scanners_together(self):
        gl = self.fake("gitleaks", FAKE_GITLEAKS, [gitleaks_finding(1)])
        th = self.fake("trufflehog", FAKE_TRUFFLEHOG)
        result = self.scan_tree("--gitleaks", gl, "--trufflehog", th)
        self.assert_only_count_lines(result)
        self.assertEqual(result.count("GITLEAKS"), 1)
        self.assertEqual(result.count("TRUFFLEHOG"), 0)
        self.assertEqual(result.skips, set(["terms"]))

    def test_broken_scanner_fails_closed(self):
        gl = self.fake("gitleaks", FAKE_BROKEN)
        result = self.scan_tree("--gitleaks", gl)
        self.assertEqual(result.code, 2)
        self.assertIsNone(result.total)

    def test_scanner_outside_a_repo_exits_2(self):
        plain = support.Tree()
        self.addCleanup(plain.cleanup)
        plain.write("a.md", "x\n")
        gl = self.fake("gitleaks", FAKE_GITLEAKS)
        result = self.scan(plain.root, "--gitleaks", gl)
        self.assertEqual(result.code, 2)


if __name__ == "__main__":
    unittest.main()
