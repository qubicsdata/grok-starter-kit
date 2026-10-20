"""One planted canary per finding code of tools/clean_scan.py, plus negatives.

Every value is built at run time (support.planted()); nothing here is literal.
"""

import os
import unittest

try:
    from tests.scan import support
except ImportError:  # run with: python3 -m unittest discover -s tests/scan
    import support

P = support.planted()


class SecretTest(support.ScanTestCase):
    def test_private_key_block(self):
        self.tree.write("config/key.pem", P["key_block"] + "\n")
        self.assert_single(self.scan_tree(), "SECRET")

    def test_github_token_prefix(self):
        self.tree.write("notes.md", "token for ci: " + P["token_gh"] + "\n")
        self.assert_single(self.scan_tree(), "SECRET")

    def test_sk_token_prefix(self):
        self.tree.write("notes.md", "api " + P["token_sk"] + "\n")
        self.assert_single(self.scan_tree(), "SECRET")

    def test_aws_key_id(self):
        self.tree.write("notes.md", "id " + P["token_aws"] + "\n")
        self.assert_single(self.scan_tree(), "SECRET")

    def test_slack_token_prefix(self):
        self.tree.write("notes.md", "hook " + P["token_slack"] + "\n")
        self.assert_single(self.scan_tree(), "SECRET")

    def test_jwt_looking_string(self):
        self.tree.write("notes.md", "jwt " + P["token_jwt"] + "\n")
        self.assert_single(self.scan_tree(), "SECRET")

    def test_secret_looking_assignment(self):
        self.tree.write("settings.ini", P["assignment"] + "\n")
        self.assert_single(self.scan_tree(), "SECRET")

    def test_placeholder_assignment_is_clean(self):
        self.tree.write("settings.ini", "pass" + "word = <your-value>\napi_key: ${API_KEY}\n")
        self.assert_clean(self.scan_tree())

    def test_unquoted_prose_value_is_clean(self):
        self.tree.write("doc.md", "secret: required\ntoken: optional-string\nauth_token = see-the-notice\n")
        self.assert_clean(self.scan_tree())

    def test_bearer_credential_counts(self):
        self.tree.write("http.txt", "Authorization: Bearer " + "a1b2c3d4" * 4 + "\n")
        self.assert_single(self.scan_tree(), "SECRET")

    def test_assigned_token_prefix_counts_once(self):
        self.tree.write("ci.env", "GITHUB_" + "TOKEN=" + P["token_gh"] + "\n")
        self.assert_single(self.scan_tree(), "SECRET")


class EmailTest(support.ScanTestCase):
    def test_non_example_address(self):
        self.tree.write("contact.md", "mail: " + P["email"] + "\n")
        self.assert_single(self.scan_tree(), "EMAIL")

    def test_example_domains_are_clean(self):
        self.tree.write("contact.md", "\n".join([
            "a: user@example.com",
            "b: user@sub.example.org",
            "c: user@example.net",
            "d: user@host.invalid",
            "",
        ]))
        self.assert_clean(self.scan_tree())

    def test_lookalike_domain_counts(self):
        self.tree.write("contact.md", "user" + support.AT + "example" + ".com.evil" + "\n")
        self.assert_single(self.scan_tree(), "EMAIL")

    def test_address_in_file_name(self):
        self.tree.write("mail-" + P["email"] + ".md", "clean\n")
        self.assert_single(self.scan_tree(), "EMAIL")

    def test_two_addresses_count_two(self):
        self.tree.write("a.md", P["email"] + "\n")
        self.tree.write("b.md", "x " + P["email"] + "\n")
        result = self.scan_tree()
        self.assert_only_count_lines(result)
        self.assertEqual(result.count("EMAIL"), 2)
        self.assertEqual(result.total, 2)

    def test_package_version_is_not_an_address(self):
        self.tree.write("install.md", "npm install example-pkg" + support.AT + "1.53.0\nrun backlog.md" + support.AT + "1.53.0\n")
        self.assert_clean(self.scan_tree())


class NoreplyTest(support.ScanTestCase):
    def test_noreply_address(self):
        self.tree.write("AUTHORS", P["noreply"] + "\n")
        result = self.scan_tree()
        self.assert_single(result, "NOREPLY")
        self.assertEqual(result.count("EMAIL"), 0, "a noreply address is NOREPLY, not EMAIL")

    def test_noreply_without_id_prefix(self):
        self.tree.write("AUTHORS", "login" + support.AT + "users.noreply" + ".github.com\n")
        self.assert_single(self.scan_tree(), "NOREPLY")


class BidiTest(support.ScanTestCase):
    def test_one_override_counts_one_character(self):
        self.tree.write("note.md", "abc" + support.RLO + "def\n")
        self.assert_single(self.scan_tree(), "BIDI")

    def test_three_characters_count_three_not_bytes_or_lines(self):
        self.tree.write("note.md", "a" + support.RLO + support.RLO + "b" + support.RLO + "\n")
        result = self.scan_tree()
        self.assert_only_count_lines(result)
        self.assertEqual(result.count("BIDI"), 3)
        self.assertEqual(result.total, 3)

    def test_isolate_counts(self):
        self.tree.write("note.md", "x" + support.LRI + "y\n")
        self.assert_single(self.scan_tree(), "BIDI")

    def test_every_override_and_isolate_code_point(self):
        points = list(range(0x202A, 0x202F)) + list(range(0x2066, 0x206A))
        self.tree.write("note.md", "".join(chr(p) for p in points) + "\n")
        result = self.scan_tree()
        self.assert_only_count_lines(result)
        self.assertEqual(result.count("BIDI"), len(points))

    def test_bidi_in_file_name(self):
        self.tree.write("no" + support.RLO + "te.md", "clean\n")
        self.assert_single(self.scan_tree(), "BIDI")

    def test_plain_rtl_text_is_clean(self):
        self.tree.write("note.md", "שלום مرحبا\n")
        self.assert_clean(self.scan_tree())


class CtrlTest(support.ScanTestCase):
    def test_bell_counts(self):
        self.tree.write("note.md", "a" + chr(0x07) + "b\n")
        self.assert_single(self.scan_tree(), "CTRL")

    def test_escape_counts(self):
        self.tree.write("note.md", "a" + chr(0x1B) + "[0m\n")
        self.assert_single(self.scan_tree(), "CTRL")

    def test_delete_and_c1_count(self):
        self.tree.write("note.md", "a" + chr(0x7F) + "b" + chr(0x85) + "c\n")
        result = self.scan_tree()
        self.assert_only_count_lines(result)
        self.assertEqual(result.count("CTRL"), 2)

    def test_tab_lf_cr_are_clean(self):
        self.tree.write("note.md", "a\tb\r\nc\n")
        self.assert_clean(self.scan_tree())

    def test_bidi_is_not_also_ctrl(self):
        self.tree.write("note.md", support.RLO + "\n")
        result = self.scan_tree()
        self.assertEqual(result.count("BIDI"), 1)
        self.assertEqual(result.count("CTRL"), 0)


class HomePathTest(support.ScanTestCase):
    def _single(self, text):
        self.tree.write("paths.md", "see " + text + "\n")
        self.assert_single(self.scan_tree(), "HOMEPATH")

    def test_workspace_root(self):
        self._single(P["workspace"])

    def test_box_home(self):
        self._single(P["box_home"])

    def test_mac_home(self):
        self._single(P["mac_home"])

    def test_other_linux_home(self):
        self._single(P["other_home"])

    def test_mac_temp_folder(self):
        self._single(P["mac_tmp"])

    def test_home_user_is_clean(self):
        self.tree.write("paths.md", "/home/user\n/home/user/notes\n${HOME}/notes\n~/notes\n")
        self.assert_clean(self.scan_tree())

    def test_bare_word_workspace_is_clean(self):
        self.tree.write("paths.md", "open the workspace folder\n")
        self.assert_clean(self.scan_tree())

    def test_relative_path_with_home_like_segment_is_clean(self):
        self.tree.write("paths.md", "see docs" + P["other_home"] + " and src" + P["workspace"] + "\n")
        self.assert_clean(self.scan_tree())

    def test_path_in_directory_name(self):
        self.tree.write("docs/" + "ho" + "me-box" + "/x.md", "clean\n")
        self.tree.write("docs/" + P["box_home"].strip("/") + "/x.md", "clean\n")
        result = self.scan_tree()
        self.assertEqual(result.count("HOMEPATH"), 0, "a relative folder named like a home is not a root")
        self.assert_clean(result)


class OpsPathTest(support.ScanTestCase):
    def test_ops_folder_name_in_path(self):
        self.tree.write("paths.md", "/home/user/" + P["opspath"] + "/queue\n")
        self.assert_single(self.scan_tree(), "OPSPATH")

    def test_ops_folder_name_as_word(self):
        self.tree.write("paths.md", "the " + P["opspath"] + " folder\n")
        self.assert_single(self.scan_tree(), "OPSPATH")

    def test_fragments_alone_are_clean(self):
        self.tree.write("paths.md", "forge\nops\nforgeops\nthe ops folder of the forge\n")
        self.assert_clean(self.scan_tree())


class AliasTest(support.ScanTestCase):
    def test_ch_code(self):
        self.tree.write("note.md", "tag: " + P["alias_ch"] + "\n")
        self.assert_single(self.scan_tree(), "ALIAS")

    def test_cl_code(self):
        self.tree.write("note.md", "client " + P["alias_cl"] + "\n")
        self.assert_single(self.scan_tree(), "ALIAS")

    def test_code_in_file_name(self):
        self.tree.write("notes/" + "ch" + "-b" + ".md", "clean\n")
        self.assert_single(self.scan_tree(), "ALIAS")

    def test_not_whole_token_is_clean(self):
        self.tree.write("note.md", "\n".join([
            "search" + "-q",
            "de" + "cl" + "-foo",
            "ch" + "-ab",
            "ch" + "-1",
            "channel-a",
            "ch" + "-",
            "cl" + "-",
            "",
        ]))
        self.assert_clean(self.scan_tree())


class UuidTest(support.ScanTestCase):
    def test_non_zero_uuid(self):
        self.tree.write("ids.md", "id " + P["uuid"] + "\n")
        self.assert_single(self.scan_tree(), "UUID")

    def test_upper_case_uuid(self):
        self.tree.write("ids.md", "id " + P["uuid"].upper() + "\n")
        self.assert_single(self.scan_tree(), "UUID")

    def test_zero_uuid_is_clean(self):
        self.tree.write("ids.md", "id " + support.zero_uuid() + "\n")
        self.assert_clean(self.scan_tree())

    def test_sha_is_not_a_uuid(self):
        self.tree.write("ids.md", "sha " + "1" * 40 + "\n")
        self.assert_clean(self.scan_tree())


class CaptureTest(support.ScanTestCase):
    def test_real_capture_file_name(self):
        self.tree.write("fixtures/" + P["real_name"], "12% used\n")
        self.assert_single(self.scan_tree(), "CAPTURE")

    def test_usage_screen_with_non_example_email(self):
        self.tree.write("fixtures/usage.txt", support.usage_screen(email=P["email"]))
        result = self.scan_tree()
        self.assert_only_count_lines(result)
        self.assertEqual(result.count("CAPTURE"), 1)
        self.assertEqual(result.count("EMAIL"), 1)
        self.assertEqual(result.total, 2)

    def test_usage_screen_with_real_org(self):
        self.tree.write("fixtures/usage.txt", support.usage_screen(org="Acme Robotics"))
        self.assert_single(self.scan_tree(), "CAPTURE")

    def test_usage_screen_with_real_plan(self):
        self.tree.write("fixtures/usage.txt", support.usage_screen(plan="Team Premium"))
        self.assert_single(self.scan_tree(), "CAPTURE")

    def test_synthetic_usage_screen_is_clean(self):
        self.tree.write("fixtures/usage_example_1.txt", support.usage_screen())
        self.assert_clean(self.scan_tree())

    def _status_screen(self, plan):
        sep = " " + chr(0xB7) + " "
        header = sep.join(["Claude Code v0.0.0-example", "example-model", plan, "/home/user/example-project"])
        return header + "\n\n  Current session\n  " + chr(0x2588) * 10 + "   42% used\n  Resets 3:00pm (UTC)\n"

    def test_status_header_with_real_plan(self):
        self.tree.write("fixtures/usage_example_2.txt", self._status_screen("Team Premium"))
        self.assert_single(self.scan_tree(), "CAPTURE")

    def test_status_header_with_example_plan_is_clean(self):
        self.tree.write("fixtures/usage_example_2.txt", self._status_screen("Example Plan"))
        self.assert_clean(self.scan_tree())

    def test_fields_outside_a_usage_screen_are_clean(self):
        self.tree.write("notes/recital.md", "Plan: dress rehearsal on Friday\nOrg: parents committee\n")
        self.assert_clean(self.scan_tree())


class SuperpowersTest(support.ScanTestCase):
    def test_path_in_tree(self):
        self.tree.write(P["superpowers"], "clean\n")
        self.assert_single(self.scan_tree(), "SUPERPOWERS")

    def test_path_mentioned_in_text(self):
        self.tree.write("note.md", "see " + P["superpowers"] + "\n")
        self.assert_single(self.scan_tree(), "SUPERPOWERS")

    def test_word_alone_is_clean(self):
        self.tree.write("note.md", "superpowers are great\n")
        self.assert_clean(self.scan_tree())


needs_git = unittest.skipUnless(support.git_available(), "git not installed")


class StructTest(support.ScanTestCase):
    def test_gitmodules_file(self):
        self.tree.write(".gitmodules", "[submodule \"x\"]\n\tpath = x\n")
        self.assert_single(self.scan_tree(), "STRUCT")

    def test_nested_git_directory(self):
        self.tree.write("vendor/thing/.git/HEAD", "ref: refs/heads/main\n")
        self.assert_single(self.scan_tree(), "STRUCT")

    def test_nested_git_file(self):
        self.tree.write("vendor/thing/.git", "gitdir: ../../.git/modules/thing\n")
        self.assert_single(self.scan_tree(), "STRUCT")

    @needs_git
    def test_gitlink_index_entry(self):
        support.init_repo(self.tree)
        support.git(self.tree.root, "update-index", "--add", "--cacheinfo", "160000," + "1" * 40 + ",sub")
        self.assert_single(self.scan_tree(), "STRUCT")

    @needs_git
    def test_own_git_at_root_is_clean(self):
        support.init_repo(self.tree)
        self.tree.write("README.md", "clean\n")
        support.commit_all(self.tree, "seed")
        self.assert_clean(self.scan_tree())

    @needs_git
    def test_own_git_contents_are_not_scanned(self):
        support.init_repo(self.tree)
        self.tree.write(".git/planted.txt", P["email"] + "\n")
        self.assert_clean(self.scan_tree())


if __name__ == "__main__":
    unittest.main()
