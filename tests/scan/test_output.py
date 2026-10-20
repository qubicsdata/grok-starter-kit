"""Output hygiene, clean trees, binary and encoding edge cases, exit codes."""

import os
import tempfile
import unittest

try:
    from tests.scan import support
except ImportError:  # run with: python3 -m unittest discover -s tests/scan
    import support

P = support.planted()
needs_git = unittest.skipUnless(support.git_available(), "git not installed")


def plant_everything(tree):
    """Every tree-mode canary in one tree; returns the values that must never be printed."""
    tree.write("config/key.pem", P["key_block"] + "\n")
    tree.write("notes/tokens.md", P["token_gh"] + "\n")
    tree.write("notes/contact.md", P["email"] + "\n")
    tree.write("notes/authors.md", P["noreply"] + "\n")
    tree.write("notes/bidi.md", "a" + support.RLO + "b\n")
    tree.write("notes/ctrl.md", "a" + chr(0x07) + "b\n")
    tree.write("notes/paths.md", P["mac_home"] + "\n" + P["workspace"] + "\n")
    tree.write("notes/ops.md", "/home/user/" + P["opspath"] + "\n")
    tree.write("notes/alias.md", P["alias_ch"] + " " + P["alias_cl"] + "\n")
    tree.write("notes/ids.md", P["uuid"] + "\n")
    tree.write("fixtures/" + P["real_name"], "12% used\n")
    tree.write("fixtures/usage.txt", support.usage_screen(org="Acme Robotics"))
    tree.write(P["superpowers"], "x\n")
    tree.write(".gitmodules", "[submodule \"x\"]\n")
    tree.write("mail-" + P["email"] + ".md", "x\n")
    values = [v for v in P.values()] + ["key.pem", "tokens.md", "contact.md", "authors.md",
                                        "bidi.md", "paths.md", "usage.txt", "Acme Robotics",
                                        "notes/", "fixtures/", support.RLO, chr(0x07)]
    return values


class CleanTreeTest(support.ScanTestCase):
    def _fill_clean(self):
        self.tree.write("README.md", "# Example Kit\n\nContact user@example.com. Home: /home/user/kit\n")
        self.tree.write("kit.config.example.yaml", "owner: Example Org\ntimezone: Europe/Example\n")
        self.tree.write("notes/ids.md", "id " + support.zero_uuid() + "\n")
        self.tree.write("notes/unicode.md", "naïve café – 日本語 — emoji 🙂\n")
        self.tree.write("fixtures/usage_example_1.txt", support.usage_screen())
        self.tree.write("tools/empty.py", "")
        self.tree.mkdir("empty-dir")

    def test_clean_synthetic_tree_is_total_zero(self):
        self._fill_clean()
        self.assert_clean(self.scan_tree())

    def test_clean_tree_prints_skip_lines_for_absent_tools(self):
        self._fill_clean()
        result = self.scan_tree()
        self.assertIn("gitleaks", result.skips)
        self.assertIn("trufflehog", result.skips)
        self.assertIn("terms", result.skips)

    @needs_git
    def test_clean_git_root_is_total_zero(self):
        self._fill_clean()
        support.init_repo(self.tree)
        support.commit_all(self.tree, "seed")
        self.assert_clean(self.scan_tree())

    def test_empty_folder_is_total_zero(self):
        self.assert_clean(self.scan_tree())

    def test_two_folders_are_added_up(self):
        other = support.Tree()
        self.addCleanup(other.cleanup)
        self.tree.write("a.md", P["email"] + "\n")
        other.write("b.md", P["email"] + "\n")
        result = self.scan(self.tree.root, other.root)
        self.assert_only_count_lines(result)
        self.assertEqual(result.count("EMAIL"), 2)
        self.assertEqual(result.total, 2)
        self.assertEqual(result.code, 1)


class BinaryAndEncodingTest(support.ScanTestCase):
    def test_binary_file_is_not_content_scanned(self):
        # No known image magic (images are covered in test_binary): this one must stay SKIP binary.
        payload = b"KITBLOB" + b"\x00" * 64 + P["email"].encode("ascii") + b"\x00\xff\xfe" * 50
        self.tree.write("data/blob.dat", payload)
        result = self.scan_tree()
        self.assert_clean(result)
        self.assertIn("binary", result.skips)

    def test_binary_file_path_rules_still_apply(self):
        self.tree.write("fixtures/" + P["real_name"], b"\x00\x01\x02")
        self.assert_single(self.scan_tree(), "CAPTURE")

    def test_latin1_file_still_finds_ascii_values(self):
        self.tree.write("notes/latin.md", ("caf\xe9 " + P["email"] + "\n").encode("latin-1"))
        self.assert_single(self.scan_tree(), "EMAIL")

    def test_utf8_bom_is_clean(self):
        self.tree.write("notes/bom.md", "\ufeff# Example\n")
        self.assert_clean(self.scan_tree())

    def test_utf16_with_bom_is_decoded(self):
        self.tree.write("notes/wide.txt", ("hello " + P["email"] + "\n").encode("utf-16"))
        result = self.scan_tree()
        self.assert_single(result, "EMAIL")
        self.assertNotIn("binary", result.skips)

    def test_bidi_counted_once_in_multibyte_text(self):
        self.tree.write("notes/mixed.md", ("日本語" + support.RLO + "テキスト\n").encode("utf-8"))
        self.assert_single(self.scan_tree(), "BIDI")

    def test_crlf_file_is_clean(self):
        self.tree.write("notes/dos.txt", b"line one\r\nline two\r\n")
        self.assert_clean(self.scan_tree())

    def test_large_text_file_counts_every_match(self):
        body = ("filler line\n" * 2000 + P["email"] + "\n") * 3
        self.tree.write("notes/big.md", body)
        result = self.scan_tree()
        self.assert_only_count_lines(result)
        self.assertEqual(result.count("EMAIL"), 3)

    def test_symlink_out_of_tree_is_not_followed(self):
        outside = support.Tree()
        self.addCleanup(outside.cleanup)
        target = outside.write("secret-note.md", P["email"] + "\n")
        os.symlink(target, self.tree.path("link.md"))
        os.symlink(outside.root, self.tree.path("linkdir"))
        self.assert_clean(self.scan_tree())

    def test_dangling_symlink_does_not_crash(self):
        os.symlink(self.tree.path("missing.md"), self.tree.path("link.md"))
        self.assert_clean(self.scan_tree())


class OutputHygieneTest(support.ScanTestCase):
    def test_only_code_total_and_skip_lines(self):
        plant_everything(self.tree)
        result = self.scan_tree()
        self.assertEqual(result.code, 1)
        self.assert_only_count_lines(result)
        self.assertGreaterEqual(result.total, 15)

    def test_every_planted_rule_fires(self):
        plant_everything(self.tree)
        result = self.scan_tree()
        for code in ("SECRET", "EMAIL", "NOREPLY", "BIDI", "CTRL", "HOMEPATH", "OPSPATH",
                     "ALIAS", "UUID", "CAPTURE", "SUPERPOWERS", "STRUCT"):
            with self.subTest(code=code):
                self.assertGreaterEqual(result.count(code), 1)

    def test_no_planted_value_or_path_is_printed(self):
        values = plant_everything(self.tree)
        result = self.scan_tree()
        self.assertEqual(result.code, 1)
        self.assert_no_leak(result, values + [self.tree.root, os.path.basename(self.tree.root)])

    def test_no_line_numbers_or_file_names_on_stdout(self):
        plant_everything(self.tree)
        result = self.scan_tree()
        self.assertEqual(result.code, 1)
        self.assertGreater(len(result.stdout.splitlines()), 0)
        for line in result.stdout.splitlines():
            self.assertNotRegex(line, r"[:/\\.]", "stdout must hold no path, file name or line:col")

    def test_total_zero_prints_no_stray_text(self):
        self.tree.write("README.md", "clean\n")
        result = self.scan_tree()
        self.assert_clean(result)
        self.assertEqual(result.stderr, "")

    def test_values_are_not_printed_on_usage_error_either(self):
        values = plant_everything(self.tree)
        terms = self.tree.write("terms.tsv", P["alias_ch"] + "\tcs\n")
        result = self.scan_tree("--terms-file", terms)
        self.assertEqual(result.code, 2)
        self.assert_no_leak(result, values + [self.tree.root])

    def test_stderr_never_echoes_scanned_text(self):
        plant_everything(self.tree)
        values = list(P.values())
        result = self.scan_tree()
        self.assertEqual(result.code, 1)
        for value in values:
            self.assertNotIn(value, result.stderr)


class ExitCodeTest(support.ScanTestCase):
    def test_findings_exit_1(self):
        self.tree.write("a.md", P["email"] + "\n")
        self.assertEqual(self.scan_tree().code, 1)

    def test_clean_exit_0(self):
        self.tree.write("a.md", "clean\n")
        self.assertEqual(self.scan_tree().code, 0)

    def test_no_folder_exits_2(self):
        result = self.scan()
        self.assertEqual(result.code, 2)
        self.assertEqual(result.counts, {})

    def test_missing_folder_exits_2(self):
        result = self.scan(self.tree.path("does-not-exist"))
        self.assertEqual(result.code, 2)
        self.assertIsNone(result.total)

    def test_unknown_flag_exits_2(self):
        self.assertEqual(self.scan_tree("--no-such-flag").code, 2)

    def test_help_exits_0_and_names_the_flags(self):
        result = self.scan("--help")
        self.assertEqual(result.code, 0)
        for flag in ("--terms-file", "--history", "--allowed-identity", "--gitleaks", "--trufflehog"):
            self.assertIn(flag, result.stdout)

    def test_history_without_identity_exits_2(self):
        self.assertEqual(self.scan_tree("--history").code, 2)

    def test_malformed_identity_exits_2(self):
        result = self.scan_tree("--history", "--allowed-identity", "no-angle-brackets")
        self.assertEqual(result.code, 2)

    def test_history_outside_a_repo_exits_2(self):
        self.tree.write("a.md", "clean\n")
        result = self.scan_tree("--history", "--allowed-identity", support.ALLOWED_IDENTITY)
        self.assertEqual(result.code, 2)

    def test_missing_scanner_binary_exits_2(self):
        self.tree.write("a.md", "clean\n")
        result = self.scan_tree("--gitleaks", self.tree.path("absent-tool"))
        self.assertEqual(result.code, 2)


class SupportCleanupTest(support.ScanTestCase):
    """run_scan must not leave its throwaway home behind (mutation runs call it thousands of times)."""

    def test_run_scan_removes_its_temp_home(self):
        self.tree.write("a.md", "clean\n")
        private = support.Tree(prefix="kitscan-tmp-")
        self.addCleanup(private.cleanup)
        saved = tempfile.tempdir
        tempfile.tempdir = private.root
        try:
            result = self.scan_tree()
        finally:
            tempfile.tempdir = saved
        self.assert_clean(result)
        self.assertEqual(os.listdir(private.root), [], "run_scan left a temp folder behind")


class ScanOwnSourceTest(support.ScanTestCase):
    """The scanner and these tests are scanned too: they must be clean themselves."""

    def test_tools_folder_is_clean(self):
        self.assert_clean(self.scan(os.path.join(support.KIT_ROOT, "tools")))

    def test_scan_tests_folder_is_clean(self):
        self.assert_clean(self.scan(support.HERE))


if __name__ == "__main__":
    unittest.main()
