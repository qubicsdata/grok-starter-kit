"""The client/employer term list (--client-terms-file): strict and allow-free.

A client/employer term ignores `allow=` (and `cs`), and every term of that
list, short or long, uses the same separator-aware, case-insensitive
substring matcher: no short-term relaxation. The owner list (--terms-file)
keeps its own rules; OwnerListUnchangedTest pins them next to the client ones.

Every term below is invented and built at run time; the term files live in
a temp dir outside the scanned tree.
"""

import os
import unittest

try:
    from tests.scan import support
except ImportError:  # run with: python3 -m unittest discover -s tests/scan
    import support

# Invented, test-only words; never real names.
FOUR = "Vo" + "rb"  # exactly 4 characters
THREE = "Z" + "qx"
TWO = "Q" + "j"
LONG = "Quor" + "vane"
SEPARATORS = ("-", " ", "_", ".", "/", "+")


def split(term, sep):
    """The term with `sep` between its two halves, e.g. ab-cd."""
    half = len(term) // 2
    return term[:half] + sep + term[half:]


class TermListCase(support.ScanTestCase):
    def setUp(self):
        super().setUp()
        support.alias_guard(self)
        self.outside = support.Tree(prefix="kitscan-terms-")
        self.addCleanup(self.outside.cleanup)

    def list_file(self, name, *lines):
        return self.outside.write(name, "\n".join(lines) + "\n")

    def scan_client(self, *lines, extra=()):
        return self.scan_tree("--client-terms-file", self.list_file("client.tsv", *lines), *extra)

    def scan_owner(self, *lines, extra=()):
        return self.scan_tree("--terms-file", self.list_file("owner.tsv", *lines), *extra)

    def assert_terms(self, result, n):
        self.assert_only_count_lines(result)
        self.assertEqual(result.count("TERMS"), n)
        self.assertEqual(result.total, n, "only term hits should count")
        self.assertEqual(result.code, 1 if n else 0)


class ClientAllowIgnoredTest(TermListCase):
    """(1) allow= on a client/employer line is never applied; the hit still counts."""

    def test_allow_glob_is_ignored(self):
        self.tree.write("NOTICE", "Copyright " + LONG + "\n")
        self.assert_terms(self.scan_client(LONG + "\tallow=NOTICE"), 1)

    def test_allow_on_a_folder_is_ignored(self):
        self.tree.write("docs/a.md", LONG + "\n")
        self.tree.write("docs/b.md", LONG + "\n")
        self.assert_terms(self.scan_client(LONG + "\tallow=docs/*"), 2)

    def test_several_allow_globs_are_ignored(self):
        self.tree.write("NOTICE", LONG + "\n")
        self.tree.write("runner/NOTICE", LONG + "\n")
        self.assert_terms(self.scan_client(LONG + "\tallow=NOTICE,*/NOTICE"), 2)

    def test_allow_does_not_cover_the_file_name(self):
        self.tree.write(LONG.lower() + "/notes.md", "clean\n")
        self.assert_terms(self.scan_client(LONG + "\tallow=" + LONG.lower() + "/*"), 1)

    def test_allow_is_ignored_for_a_short_term(self):
        self.tree.write("NOTICE", FOUR + "\n")
        self.assert_terms(self.scan_client(FOUR + "\tallow=NOTICE"), 1)

    def test_allow_with_cs_is_ignored(self):
        self.tree.write("NOTICE", LONG + "\n")
        self.assert_terms(self.scan_client(LONG + "\tcs allow=NOTICE"), 1)

    @unittest.skipUnless(support.git_available(), "git not installed")
    def test_allow_is_ignored_for_a_historical_blob(self):
        support.init_repo(self.tree)
        self.tree.write("NOTICE", "Copyright " + LONG + "\n")
        support.commit_all(self.tree, "add notice")
        os.remove(self.tree.path("NOTICE"))
        support.commit_all(self.tree, "drop notice")
        result = self.scan_client(LONG + "\tallow=NOTICE",
                                  extra=("--history", "--allowed-identity", support.ALLOWED_IDENTITY))
        self.assert_terms(result, 1)


class ClientShortTermStrictTest(TermListCase):
    """(2) a client/employer term of up to 4 characters is not relaxed."""

    def test_four_character_term_inside_a_longer_word(self):
        self.tree.write("note.md", "the " + FOUR.lower() + "ish and un" + FOUR + "ed\n")
        self.assert_terms(self.scan_client(FOUR), 2)

    def test_four_character_term_in_any_case(self):
        self.tree.write("note.md", FOUR.lower() + " " + FOUR.upper() + " " + FOUR + "\n")
        self.assert_terms(self.scan_client(FOUR), 3)

    def test_four_character_term_across_a_separator(self):
        self.tree.write("note.md", " ".join(split(FOUR.lower(), sep) for sep in SEPARATORS) + "\n")
        self.assert_terms(self.scan_client(FOUR), len(SEPARATORS))

    def test_four_character_term_inside_a_file_name(self):
        self.tree.write("notes/" + FOUR.lower() + "ing.md", "clean\n")
        self.assert_terms(self.scan_client(FOUR), 1)

    def test_four_character_term_with_cs_flag_is_not_relaxed(self):
        self.tree.write("note.md", FOUR.lower() + "ish\n")
        self.assert_terms(self.scan_client(FOUR + "\tcs"), 1)

    def test_three_character_term_across_a_separator(self):
        self.tree.write("note.md", split(THREE.upper(), "-") + "ish\n")
        self.assert_terms(self.scan_client(THREE), 1)

    def test_two_character_term_inside_a_word(self):
        self.tree.write("note.md", "x" + TWO.lower() + "x\n")
        self.assert_terms(self.scan_client(TWO), 1)

    def test_short_and_long_terms_share_the_matcher(self):
        self.tree.write("note.md", split(LONG.lower(), "-") + "s " + split(FOUR.upper(), "_") + "s\n")
        self.assert_terms(self.scan_client(LONG, FOUR), 2)

    def test_term_with_a_space_matches_joined_and_hyphenated(self):
        term = LONG + " " + FOUR
        self.tree.write("note.md", (LONG + FOUR).lower() + " " + LONG + "-" + FOUR + "\n")
        self.assert_terms(self.scan_client(term), 2)

    @unittest.skipUnless(support.git_available(), "git not installed")
    def test_four_character_term_inside_a_word_of_a_commit_message(self):
        support.init_repo(self.tree)
        self.tree.write("note.md", "clean\n")
        support.commit_all(self.tree, "add the " + FOUR.lower() + "ish note")
        result = self.scan_client(FOUR, extra=("--history", "--allowed-identity", support.ALLOWED_IDENTITY))
        self.assert_only_count_lines(result)
        self.assertEqual(result.count("MSG"), 1)
        self.assertEqual(result.total, 1)


class OwnerListUnchangedTest(TermListCase):
    """(3) the owner list keeps allow= and the exactly-4-character relaxation."""

    def test_owner_allow_glob_still_applies(self):
        self.tree.write("NOTICE", "Copyright " + LONG + "\n")
        self.assert_terms(self.scan_owner(LONG + "\tallow=NOTICE"), 0)

    def test_owner_four_character_term_inside_a_word_does_not_match(self):
        self.tree.write("note.md", "the " + FOUR.lower() + "ish and un" + FOUR + "ed\n")
        self.assert_terms(self.scan_owner(FOUR), 0)

    def test_owner_four_character_term_in_another_case_does_not_match(self):
        self.tree.write("note.md", FOUR.lower() + " " + FOUR.upper() + "\n")
        self.assert_terms(self.scan_owner(FOUR), 0)

    def test_owner_four_character_whole_word_matches(self):
        self.tree.write("note.md", "see " + FOUR + " here\n")
        self.assert_terms(self.scan_owner(FOUR), 1)

    def test_owner_longer_term_is_a_plain_substring(self):
        self.tree.write("note.md", "the " + LONG.upper() + "ish\n")
        self.assert_terms(self.scan_owner(LONG), 1)

    def test_owner_cs_flag_still_applies(self):
        self.tree.write("note.md", LONG.lower() + " " + LONG + "s " + LONG + "\n")
        self.assert_terms(self.scan_owner(LONG + "\tcs"), 1)

    def test_owner_three_character_term_is_a_plain_substring(self):
        self.tree.write("note.md", "the " + THREE.upper() + "ish " + split(THREE, "-") + "\n")
        self.assert_terms(self.scan_owner(THREE), 1)

    def test_owner_term_is_not_separator_aware(self):
        self.tree.write("note.md", split(LONG, "-") + "\n")
        self.assert_terms(self.scan_owner(LONG), 0)

    def test_both_lists_each_keep_their_rules(self):
        owner = self.list_file("owner.tsv", LONG + "\tallow=NOTICE", FOUR)
        client = self.list_file("client.tsv", LONG + "\tallow=NOTICE", FOUR)
        self.tree.write("NOTICE", LONG + "\n")
        self.tree.write("note.md", FOUR.lower() + "ish\n")
        # owner: NOTICE allowed, the 4-character term relaxed -> 0; client: both count -> 2
        self.assert_terms(self.scan_tree("--terms-file", owner, "--client-terms-file", client), 2)


class ClientListFileTest(TermListCase):
    def test_client_list_alone_runs_the_term_check(self):
        self.tree.write("note.md", "clean\n")
        result = self.scan_client(LONG)
        self.assert_terms(result, 0)
        self.assertNotIn("terms", result.skips)

    def test_client_list_inside_the_scanned_tree_is_refused(self):
        inside = self.tree.write("private/client.tsv", LONG + "\n")
        result = self.scan_tree("--client-terms-file", inside)
        self.assertEqual(result.code, 2)
        self.assertIsNone(result.total)

    def test_missing_client_list_exits_2(self):
        result = self.scan_tree("--client-terms-file", self.outside.path("no-such.tsv"))
        self.assertEqual(result.code, 2)
        self.assertIsNone(result.total)

    def test_unknown_flag_on_a_client_line_exits_2(self):
        result = self.scan_client(LONG + "\tsoft")
        self.assertEqual(result.code, 2)
        self.assertIsNone(result.total)

    def test_client_terms_are_never_printed(self):
        self.tree.write("note.md", LONG + " " + FOUR + "\n")
        result = self.scan_client(LONG + "\tallow=note.md", FOUR)
        self.assertEqual(result.code, 1)
        self.assert_no_leak(result, [LONG, FOUR, LONG.lower(), FOUR.lower(), self.outside.root, self.tree.root])


class AliasGuardTest(unittest.TestCase):
    """The term tests run the whole scanner, ALIAS rule included: keep real alias data out."""

    def test_scanner_names_no_alias_list(self):
        support.alias_guard(self)

    def test_scan_environment_carries_no_alias_variable(self):
        self.assertEqual(support.alias_variables(support.clean_env("/tmp")), [])

    def test_run_scan_refuses_an_alias_variable(self):
        with self.assertRaises(RuntimeError):
            support.run_scan("--help", env_extra={"KITSCAN_FAKE_ALIASES": "synthetic"})


if __name__ == "__main__":
    unittest.main()
