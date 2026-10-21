"""The external term list: --terms-file PATH, `term<TAB>flags`, allow= globs, refusal."""

import os
import unittest

try:
    from tests.scan import support
except ImportError:  # run with: python3 -m unittest discover -s tests/scan
    import support

P = support.planted()

# Invented, test-only words; never real names.
TERM_A = "Quor" + "vane"
TERM_B = "Zen" + "trix"
TERM_C = "Kes" + "trelco"


class TermFileTest(support.ScanTestCase):
    def setUp(self):
        super().setUp()
        self.outside = support.Tree(prefix="kitscan-terms-")
        self.addCleanup(self.outside.cleanup)

    def terms(self, *lines):
        return self.outside.write("terms.tsv", "\n".join(lines) + "\n")

    def scan_terms(self, terms_path, *extra):
        return self.scan_tree("--terms-file", terms_path, *extra)

    def test_term_without_flags_matches_case_insensitively(self):
        terms = self.terms(TERM_A)
        self.tree.write("note.md", "about " + TERM_A.upper() + "\n")
        self.assert_single(self.scan_terms(terms), "TERMS")

    def test_term_without_flags_matches_as_substring(self):
        terms = self.terms(TERM_A)
        self.tree.write("note.md", "the " + TERM_A.lower() + "s\n")
        self.assert_single(self.scan_terms(terms), "TERMS")

    def test_cs_term_is_case_sensitive(self):
        terms = self.terms(TERM_B + "\tcs")
        self.tree.write("note.md", TERM_B.lower() + "\n")
        self.assert_clean(self.scan_terms(terms))

    def test_cs_term_matches_exact_case(self):
        terms = self.terms(TERM_B + "\tcs")
        self.tree.write("note.md", "see " + TERM_B + " here\n")
        self.assert_single(self.scan_terms(terms), "TERMS")

    def test_cs_term_is_whole_word(self):
        terms = self.terms(TERM_B + "\tcs")
        self.tree.write("note.md", TERM_B + "es and pre" + TERM_B + "\n")
        self.assert_clean(self.scan_terms(terms))

    def test_cs_term_hyphen_is_a_word_boundary(self):
        terms = self.terms(TERM_B + "\tcs")
        self.tree.write("note.md", TERM_B + "-ops\n")
        self.assert_single(self.scan_terms(terms), "TERMS")

    def test_each_occurrence_counts(self):
        terms = self.terms(TERM_A)
        self.tree.write("a.md", TERM_A + "\n")
        self.tree.write("b.md", TERM_A + " and " + TERM_A + "\n")
        result = self.scan_terms(terms)
        self.assert_only_count_lines(result)
        self.assertEqual(result.count("TERMS"), 3)

    def test_term_in_file_name_counts(self):
        terms = self.terms(TERM_A)
        self.tree.write("notes/" + TERM_A.lower() + "-plan.md", "clean\n")
        self.assert_single(self.scan_terms(terms), "TERMS")

    def test_comments_and_blank_lines_are_ignored(self):
        terms = self.terms("# " + TERM_C, "", "   ", TERM_A, "# trailing comment")
        self.tree.write("note.md", TERM_C + "\n")
        self.assert_clean(self.scan_terms(terms))

    def test_multiple_terms(self):
        terms = self.terms(TERM_A, TERM_B + "\tcs", TERM_C)
        self.tree.write("note.md", TERM_A + " " + TERM_B + " " + TERM_C + "\n")
        result = self.scan_terms(terms)
        self.assert_only_count_lines(result)
        self.assertEqual(result.count("TERMS"), 3)

    def test_term_with_spaces(self):
        term = TERM_A + " Holdings"
        terms = self.terms(term)
        self.tree.write("note.md", "owner: " + term.lower() + "\n")
        self.assert_single(self.scan_terms(terms), "TERMS")

    def test_term_is_matched_literally_not_as_regex(self):
        terms = self.terms("a.c")
        self.tree.write("note.md", "abc\n")
        self.assert_clean(self.scan_terms(terms))

    def test_no_terms_file_prints_skip_terms(self):
        self.tree.write("note.md", TERM_A + "\n")
        result = self.scan_tree()
        self.assert_clean(result)
        self.assertIn("terms", result.skips)

    def test_with_terms_file_no_skip_terms(self):
        terms = self.terms(TERM_A)
        self.tree.write("note.md", "clean\n")
        result = self.scan_terms(terms)
        self.assert_clean(result)
        self.assertNotIn("terms", result.skips)

    def test_terms_are_never_printed(self):
        terms = self.terms(TERM_A, TERM_B + "\tcs", TERM_C + "\tallow=NOTICE")
        self.tree.write("note.md", TERM_A + " " + TERM_B + "\n")
        result = self.scan_terms(terms)
        self.assertEqual(result.code, 1)
        self.assert_no_leak(result, [TERM_A, TERM_B, TERM_C, TERM_A.lower(), terms, self.tree.root])


class ShortTermTest(support.ScanTestCase):
    """An owner-list term of exactly 4 characters is case-sensitive and whole-word even without the cs flag."""

    SHORT = "Vy" + "rk"  # 4 characters, invented
    THREE = "Q" + "zx"
    FIVE = "Pl" + "umv"

    def setUp(self):
        super().setUp()
        self.outside = support.Tree(prefix="kitscan-terms-")
        self.addCleanup(self.outside.cleanup)

    def terms(self, *lines):
        return self.outside.write("terms.tsv", "\n".join(lines) + "\n")

    def scan_terms(self, *lines):
        return self.scan_tree("--terms-file", self.terms(*lines))

    def test_short_term_inside_a_longer_word_does_not_match(self):
        self.tree.write("note.md", "the " + self.SHORT + "ish and un" + self.SHORT + "ed\n")
        self.assert_clean(self.scan_terms(self.SHORT))

    def test_short_term_in_another_case_does_not_match(self):
        self.tree.write("note.md", self.SHORT.lower() + " " + self.SHORT.upper() + "\n")
        self.assert_clean(self.scan_terms(self.SHORT))

    def test_short_term_exact_whole_word_matches(self):
        self.tree.write("note.md", "see " + self.SHORT + " here\n")
        self.assert_single(self.scan_terms(self.SHORT), "TERMS")

    def test_short_term_hyphen_is_a_word_boundary(self):
        self.tree.write("note.md", self.SHORT + "-ops\n")
        self.assert_single(self.scan_terms(self.SHORT), "TERMS")

    def test_short_term_inside_a_file_name_does_not_match(self):
        self.tree.write("notes/" + self.SHORT.lower() + "ing.md", "clean\n")
        self.assert_clean(self.scan_terms(self.SHORT))

    def test_short_term_with_cs_flag_behaves_the_same(self):
        self.tree.write("note.md", self.SHORT.lower() + " " + self.SHORT + "s " + self.SHORT + "\n")
        self.assert_single(self.scan_terms(self.SHORT + "\tcs"), "TERMS")

    def test_short_term_keeps_allow_globs(self):
        self.tree.write("NOTICE", self.SHORT + "\n")
        self.tree.write("README.md", self.SHORT + "\n")
        self.assert_single(self.scan_terms(self.SHORT + "\tallow=NOTICE"), "TERMS")

    def test_three_character_term_keeps_substring_matching(self):
        self.tree.write("note.md", "the " + self.THREE.upper() + "ish\n")
        self.assert_single(self.scan_terms(self.THREE), "TERMS")

    def test_five_character_term_keeps_substring_matching(self):
        self.tree.write("note.md", "the " + self.FIVE.upper() + "ish\n")
        self.assert_single(self.scan_terms(self.FIVE), "TERMS")

    def test_short_term_in_a_mixed_list(self):
        self.tree.write("note.md", self.SHORT.lower() + "y " + self.SHORT + " " + self.FIVE.lower() + "s\n")
        result = self.scan_terms(self.SHORT, self.FIVE)
        self.assert_only_count_lines(result)
        self.assertEqual(result.count("TERMS"), 2)

    @unittest.skipUnless(support.git_available(), "git not installed")
    def test_short_term_inside_a_word_of_a_commit_message_does_not_match(self):
        support.init_repo(self.tree)
        self.tree.write("note.md", "clean\n")
        support.commit_all(self.tree, "add the " + self.SHORT.lower() + "ish note")
        self.assert_clean(self.scan_tree("--terms-file", self.terms(self.SHORT), "--history",
                                         "--allowed-identity", support.ALLOWED_IDENTITY))


class AllowGlobTest(support.ScanTestCase):
    def setUp(self):
        super().setUp()
        self.outside = support.Tree(prefix="kitscan-terms-")
        self.addCleanup(self.outside.cleanup)

    def terms(self, *lines):
        return self.outside.write("terms.tsv", "\n".join(lines) + "\n")

    def test_term_allowed_in_matching_path(self):
        terms = self.terms(TERM_A + "\tallow=NOTICE")
        self.tree.write("NOTICE", "Copyright " + TERM_A + "\n")
        self.assert_clean(self.scan_tree("--terms-file", terms))

    def test_term_still_counted_elsewhere(self):
        terms = self.terms(TERM_A + "\tallow=NOTICE")
        self.tree.write("NOTICE", "Copyright " + TERM_A + "\n")
        self.tree.write("README.md", "by " + TERM_A + "\n")
        self.assert_single(self.scan_tree("--terms-file", terms), "TERMS")

    def test_several_globs_comma_separated(self):
        terms = self.terms(TERM_A + "\tallow=NOTICE,*/NOTICE")
        self.tree.write("NOTICE", TERM_A + "\n")
        self.tree.write("runner/NOTICE", TERM_A + "\n")
        self.tree.write("runner/README.md", TERM_A + "\n")
        self.assert_single(self.scan_tree("--terms-file", terms), "TERMS")

    def test_glob_is_relative_to_scanned_folder(self):
        terms = self.terms(TERM_A + "\tallow=docs/*.md")
        self.tree.write("docs/a.md", TERM_A + "\n")
        self.tree.write("other/docs/b.md", TERM_A + "\n")
        self.assert_single(self.scan_tree("--terms-file", terms), "TERMS")

    def test_cs_and_allow_together(self):
        terms = self.terms(TERM_B + "\tcs allow=NOTICE")
        self.tree.write("NOTICE", TERM_B + "\n")
        self.tree.write("README.md", TERM_B.lower() + "\n" + TERM_B + "\n")
        self.assert_single(self.scan_tree("--terms-file", terms), "TERMS")

    def test_allow_covers_the_file_name_too(self):
        terms = self.terms(TERM_A + "\tallow=" + TERM_A.lower() + "/*")
        self.tree.write(TERM_A.lower() + "/notes.md", "clean\n")
        self.assert_clean(self.scan_tree("--terms-file", terms))


class RefusalTest(support.ScanTestCase):
    def test_terms_file_inside_scanned_tree_is_refused(self):
        terms = self.tree.write("private/terms.tsv", TERM_A + "\n")
        self.tree.write("note.md", TERM_A + "\n")
        result = self.scan_tree("--terms-file", terms)
        self.assertEqual(result.code, 2)
        self.assertEqual(result.counts, {})
        self.assertIsNone(result.total)

    def test_terms_file_inside_any_scanned_folder_is_refused(self):
        other = support.Tree()
        self.addCleanup(other.cleanup)
        terms = other.write("terms.tsv", TERM_A + "\n")
        result = self.scan(self.tree.root, other.root, "--terms-file", terms)
        self.assertEqual(result.code, 2)

    def test_terms_file_reached_through_symlink_is_refused(self):
        outside = support.Tree()
        self.addCleanup(outside.cleanup)
        terms = self.tree.write("terms.tsv", TERM_A + "\n")
        os.symlink(terms, outside.path("link.tsv"))
        result = self.scan_tree("--terms-file", outside.path("link.tsv"))
        self.assertEqual(result.code, 2)

    def test_missing_terms_file_exits_2(self):
        result = self.scan_tree("--terms-file", self.tree.path("../no-such-terms.tsv"))
        self.assertEqual(result.code, 2)

    def test_terms_file_next_to_tree_is_accepted(self):
        outside = support.Tree()
        self.addCleanup(outside.cleanup)
        terms = outside.write("terms.tsv", TERM_A + "\n")
        self.tree.write("note.md", "clean\n")
        self.assert_clean(self.scan_tree("--terms-file", terms))

    def test_refusal_message_holds_no_term_or_path(self):
        terms = self.tree.write("terms.tsv", TERM_A + "\n")
        result = self.scan_tree("--terms-file", terms)
        self.assertEqual(result.code, 2)
        self.assert_no_leak(result, [TERM_A, self.tree.root])


if __name__ == "__main__":
    unittest.main()
