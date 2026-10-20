"""sb --doctor, checks 1-9 of second-brain/DOCTOR-SPEC.md: one pass and one
fail fixture (at least) per check, the exact exit codes (1 for check 1, 3
for checks 2-6 and 9, 0 for the warnings 7 and 8; 3 wins over 1), the
doctor.fail_on_* switches, and the output rule: paths and check numbers
only, never the matching line."""

import os
import shutil
import unittest

import sbsupport
from sbsupport import CLEAN_NOTE_COUNT, CLEAN_ROW_COUNT, SbCase, clean_router, note, router

AT = sbsupport.AT


class DoctorCase(SbCase):
    def setUp(self):
        super().setUp()
        self.write_tree(sbsupport.clean_brain())
        self.write_config()

    def assert_clean(self, code, out, check=None):
        """Exit 0 and no finding at all (or none for `check`)."""
        found = self.doctor_lines(out)
        if check is None:
            self.assertEqual(found, [])
            self.assertEqual(code, 0)
        else:
            self.assertEqual([f for f in found if f[1] == check], [])

    def assert_only(self, out, expected):
        """The findings are exactly `expected`: a set of (level, check, path)."""
        self.assertEqual(set(self.doctor_lines(out)), set(expected))


class CleanTreeTest(DoctorCase):
    def test_clean_tree_passes(self):
        code, out, err = self.doctor()
        self.assertEqual(err, "")
        self.assert_clean(code, out)
        summary = sbsupport.DOCTOR_SUMMARY.match(out.splitlines()[-1])
        self.assertIsNotNone(summary, "the summary is the last line")
        self.assertEqual(summary.groups(), (str(CLEAN_NOTE_COUNT), str(CLEAN_ROW_COUNT), "0", "0"))

    def test_kit_template_passes(self):
        template = os.path.join(self.tmp, "template")
        shutil.copytree(sbsupport.SB_DIR, template, ignore=shutil.ignore_patterns("bin", "tests"))
        code, out, err = self.run_sb(["--doctor"], config=False, SB_HOME=template)
        self.assertEqual(err, "")
        self.assert_clean(code, out)

    def test_doctor_never_spawns_rg(self):
        self.write("dance-school/classes/untagged.md", "no channel here\n")
        for passthrough in (False, True):
            code, out, _ = self.doctor(path=self.fake_rg(passthrough=passthrough))
            self.assertEqual(code, 3)
            self.assertEqual(self.checks(out, 2), [("FAIL", "dance-school/classes/untagged.md")])
        self.assertFalse(self.rg_called())

    def test_doctor_runs_without_rg(self):
        code, out, _ = self.doctor(path=self.empty_bin)
        self.assert_clean(code, out)


class Check1RouterPathsTest(DoctorCase):
    def test_pass_file_and_folder_paths_exist(self):
        rows = [("Pottery", "pottery", "other-activities", ["other-activities/pottery-workshop.md"], "One note")]
        self.write("ROUTER.md", clean_router(extra_other=rows))
        self.assert_clean(*self.doctor()[:2])

    def test_fail_missing_router_path_exits_1(self):
        rows = [("Recitals", "recital", "dance-school", ["dance-school/recitals/"], "Not created yet")]
        self.write("ROUTER.md", clean_router(extra_dance=rows))
        code, out, _ = self.doctor()
        self.assertEqual(code, 1)
        self.assert_only(out, {("FAIL", 1, "dance-school/recitals/")})

    def test_fail_missing_router_file_exits_1(self):
        self.remove("ROUTER.md")
        code, out, _ = self.doctor()
        self.assertEqual(code, 1)
        self.assertIn(("FAIL", 1, "ROUTER.md"), self.doctor_lines(out))
        self.assertEqual({f[1] for f in self.doctor_lines(out)} - {1, 7}, set())

    def test_router_file_name_from_config(self):
        os.rename(os.path.join(self.brain, "ROUTER.md"), os.path.join(self.brain, "INDEX.md"))
        self.write_config({"router_file": "INDEX.md"})
        self.assert_clean(*self.doctor()[:2])

    def test_switch_off_turns_it_into_a_warning(self):
        rows = [("Recitals", "recital", "dance-school", ["dance-school/recitals/"], "Not created yet")]
        self.write("ROUTER.md", clean_router(extra_dance=rows))
        self.write_config({"doctor": {"fail_on_missing_router_path": False}})
        code, out, _ = self.doctor()
        self.assertEqual(code, 0)
        self.assert_only(out, {("WARN", 1, "dance-school/recitals/")})


class Check2MissingChannelTest(DoctorCase):
    def test_pass_channel_from_line_label_or_tags(self):
        self.write("dance-school/classes/a.md", "- **channel:** dance-school\n\nbody\n")
        self.write("dance-school/classes/b.md", "labels: ['channel:dance-school']\n\nbody\n")
        self.write("dance-school/classes/c.md", note(None, ["dance-school", "schedule"]))
        code, out, _ = self.doctor()
        self.assert_clean(code, out)

    def test_fail_no_channel_exits_3(self):
        self.write("dance-school/classes/untagged.md", note(None, ["schedule"]))
        self.write("dance-school/classes/bare.md", "# Just a heading\n\nNo front matter.\n")
        code, out, _ = self.doctor()
        self.assertEqual(code, 3)
        self.assert_only(out, {("FAIL", 2, "dance-school/classes/untagged.md"),
                               ("FAIL", 2, "dance-school/classes/bare.md")})

    def test_path_default_does_not_excuse_a_missing_channel(self):
        self.write("other-activities/loose.md", "body only\n")
        code, out, _ = self.doctor()
        self.assertEqual(code, 3)
        self.assertEqual(self.checks(out, 2), [("FAIL", "other-activities/loose.md")])

    def test_channel_line_after_line_30_does_not_count(self):
        self.write("dance-school/classes/late.md", "\n".join(["filler"] * 30) + "\nchannel: dance-school\n")
        code, out, _ = self.doctor()
        self.assertEqual(code, 3)
        self.assertEqual(self.checks(out, 2), [("FAIL", "dance-school/classes/late.md")])

    def test_top_level_files_and_denied_folders_are_not_notes(self):
        self.write("NOTES-INDEX.md", "no channel, but top-level\n")
        self.write("dance-school/bin/helper.md", "no channel, under bin/\n")
        self.write("dance-school/.drafts/x.md", "no channel, hidden folder\n")
        self.write("dance-school/node_modules/pkg/readme.md", "no channel\n")
        self.write("dance-school/classes/plan.txt", "not a markdown note\n")
        code, out, _ = self.doctor()
        self.assert_clean(code, out)

    def test_switch_off_turns_it_into_a_warning(self):
        self.write("dance-school/classes/untagged.md", note(None, ["schedule"]))
        self.write_config({"doctor": {"fail_on_untagged": False}})
        code, out, _ = self.doctor()
        self.assertEqual(code, 0)
        self.assert_only(out, {("WARN", 2, "dance-school/classes/untagged.md")})


class Check3OneChannelTest(DoctorCase):
    def test_pass_topic_tags_asides_and_body_mentions(self):
        self.write("dance-school/classes/a.md", note("dance-school", ["dance-school", "schedule", "term"]))
        self.write("dance-school/classes/b.md", note("dance-school (not other-activities)", ["dance-school"]))
        self.write("dance-school/classes/c.md", note("dance-school", ["dance-school"],
                                                     body="See the other-activities folder for workshops.\n"))
        self.assert_clean(*self.doctor()[:2])

    def test_fail_two_channels_exits_3(self):
        self.write("dance-school/classes/tags.md", note("dance-school", ["dance-school", "other-activities"]))
        self.write("dance-school/classes/line.md", note("dance-school, other-activities", ["dance-school"]))
        self.write("dance-school/classes/plus.md", note("dance-school+other-activities"))
        code, out, _ = self.doctor()
        self.assertEqual(code, 3)
        self.assertEqual(sorted(self.checks(out, 3)), [
            ("FAIL", "dance-school/classes/line.md"), ("FAIL", "dance-school/classes/plus.md"),
            ("FAIL", "dance-school/classes/tags.md")])
        self.assertEqual(self.checks(out, 2) + self.checks(out, 9), [])

    def test_fail_tags_disagree_with_channel(self):
        self.write("dance-school/classes/odd.md", note("dance-school", ["other-activities"]))
        code, out, _ = self.doctor()
        self.assertEqual(code, 3)
        self.assertEqual(self.checks(out, 3), [("FAIL", "dance-school/classes/odd.md")])

    def test_switch_off_turns_it_into_a_warning(self):
        self.write("dance-school/classes/tags.md", note("dance-school", ["dance-school", "other-activities"]))
        self.write_config({"doctor": {"fail_on_multiple_channels": False}})
        code, out, _ = self.doctor()
        self.assertEqual(code, 0)
        self.assert_only(out, {("WARN", 3, "dance-school/classes/tags.md")})


class Check4FolderAgreesTest(DoctorCase):
    def test_pass_folder_from_custom_path_defaults(self):
        self.write_config({"path_defaults": {"school/": "dance-school", "other-activities/": "other-activities",
                                             "dance-school/": "dance-school"}})
        self.write("school/a.md", note("dance-school", ["dance-school"]))
        self.write("ROUTER.md", clean_router(extra_dance=[("School", "school", "dance-school", ["school/"], "Renamed folder")]))
        self.assert_clean(*self.doctor()[:2])

    def test_fail_note_in_another_channel_folder_exits_3(self):
        self.write("other-activities/admin/stray.md", note("dance-school", ["dance-school"]))
        code, out, _ = self.doctor()
        self.assertEqual(code, 3)
        self.assert_only(out, {("FAIL", 4, "other-activities/admin/stray.md")})

    def test_fail_similar_folder_name(self):
        self.write("dance-school-archive/old.md", note("dance-school", ["dance-school"]))
        code, out, _ = self.doctor()
        self.assertEqual(code, 3)
        self.assertEqual(self.checks(out, 4), [("FAIL", "dance-school-archive/old.md")])

    def test_fail_path_default_points_elsewhere(self):
        self.write_config({"path_defaults": {"dance-school/": "dance-school", "other-activities/": "other-activities",
                                             "dance-school/club/": "other-activities"}})
        self.write("dance-school/club/meet.md", note("dance-school", ["dance-school"]))
        self.write("ROUTER.md", clean_router(extra_dance=[("Club", "club", "dance-school", ["dance-school/club/"], "x")]))
        code, out, _ = self.doctor()
        self.assertEqual(code, 3)
        self.assertEqual(self.checks(out, 4), [("FAIL", "dance-school/club/meet.md")])

    def test_switch_off_turns_it_into_a_warning(self):
        self.write("other-activities/admin/stray.md", note("dance-school", ["dance-school"]))
        self.write_config({"doctor": {"fail_on_folder_mismatch": False}})
        code, out, _ = self.doctor()
        self.assertEqual(code, 0)
        self.assert_only(out, {("WARN", 4, "other-activities/admin/stray.md")})


class Check5CrossChannelLinkTest(DoctorCase):
    def test_pass_same_channel_and_unresolved_links(self):
        # the clean tree already links by path, by relative path, by stem and with a label
        self.write("dance-school/classes/x.md", note("dance-school", ["dance-school"],
                                                     body="See [[nowhere-at-all]] and [[term-timetable#monday]].\n"))
        self.assert_clean(*self.doctor()[:2])

    def test_fail_cross_channel_links_exit_3(self):
        cases = {
            "front-matter path": note("dance-school", ["dance-school"], links=["other-activities/pottery-workshop.md"]),
            "front-matter path without .md": note("dance-school", ["dance-school"], links=["other-activities/pottery-workshop"]),
            "front-matter relative path": note("dance-school", ["dance-school"], links=["../../other-activities/pottery-workshop.md"]),
            "front-matter block list": note("dance-school", ["dance-school"],
                                            extra=["links:", '  - "other-activities/admin/supplies.md"']),
            "wiki stem": note("dance-school", ["dance-school"], body="Ask about [[pottery-workshop]].\n"),
            "wiki path with label": note("dance-school", ["dance-school"],
                                         body="See [[other-activities/pottery-workshop|the workshop]].\n"),
            "wiki with anchor": note("dance-school", ["dance-school"], body="See [[supplies#clay]].\n"),
        }
        for label, text in cases.items():
            with self.subTest(case=label):
                self.write("dance-school/marketing/linker.md", text)
                code, out, _ = self.doctor()
                self.assertEqual(code, 3)
                self.assert_only(out, {("FAIL", 5, "dance-school/marketing/linker.md")})

    def test_one_line_per_note(self):
        self.write("dance-school/marketing/linker.md", note(
            "dance-school", ["dance-school"], links=["other-activities/pottery-workshop.md"],
            body="[[pottery-workshop]] [[supplies]]\n"))
        _, out, _ = self.doctor()
        self.assertEqual(self.checks(out, 5), [("FAIL", "dance-school/marketing/linker.md")])

    def test_switch_off_turns_it_into_a_warning(self):
        self.write("dance-school/marketing/linker.md", note("dance-school", ["dance-school"],
                                                            body="[[pottery-workshop]]\n"))
        self.write_config({"doctor": {"fail_on_cross_channel_link": False}})
        code, out, _ = self.doctor()
        self.assertEqual(code, 0)
        self.assert_only(out, {("WARN", 5, "dance-school/marketing/linker.md")})


class Check6RouterRowScopeTest(DoctorCase):
    def test_pass_rows_inside_their_channel_folder(self):
        rows = [("Supplies", "supplies", "other-activities", ["other-activities/admin/"], "Supplies")]
        self.write("ROUTER.md", clean_router(extra_other=rows))
        self.assert_clean(*self.doctor()[:2])

    def test_fail_row_path_outside_its_channel_exits_3(self):
        rows = [("Supplies", "supplies", "dance-school", ["other-activities/admin/"], "Wrong channel")]
        self.write("ROUTER.md", clean_router(extra_dance=rows))
        code, out, _ = self.doctor()
        self.assertEqual(code, 3)
        self.assert_only(out, {("FAIL", 6, "other-activities/admin/")})

    def test_fail_row_with_two_or_unknown_channels(self):
        for ch in ("dance-school+other-activities", "personal", ""):
            with self.subTest(ch=ch):
                rows = [("Odd row", "odd", ch, ["dance-school/classes/"], "Odd")]
                self.write("ROUTER.md", clean_router(extra_dance=rows))
                code, out, _ = self.doctor()
                self.assertEqual(code, 3)
                self.assertEqual(self.checks(out, 6), [("FAIL", "dance-school/classes/")])

    def test_fail_similar_folder_prefix(self):
        rows = [("Archive", "archive", "dance-school", ["dance-school-archive/"], "Look-alike")]
        self.write("dance-school-archive/.keep", "")
        self.write("ROUTER.md", clean_router(extra_dance=rows))
        code, out, _ = self.doctor()
        self.assertEqual(code, 3)
        self.assertEqual(self.checks(out, 6), [("FAIL", "dance-school-archive/")])


class Check7NotRoutedTest(DoctorCase):
    def test_pass_subfolder_covered_by_an_ancestor_row(self):
        self.write("dance-school/marketing/social/post.md", note("dance-school", ["dance-school"]))
        self.write("dance-school/assets/readme.txt", "only a text file\n")
        self.assert_clean(*self.doctor()[:2])

    def test_warn_unrouted_folder_exits_0(self):
        self.write("dance-school/costumes/list.md", note("dance-school", ["dance-school"]))
        self.write("dance-school/costumes/sizes/chart.md", note("dance-school", ["dance-school"]))
        code, out, _ = self.doctor()
        self.assertEqual(code, 0)
        self.assert_only(out, {("WARN", 7, "dance-school/costumes/"), ("WARN", 7, "dance-school/costumes/sizes/")})
        summary = sbsupport.DOCTOR_SUMMARY.match(out.splitlines()[-1])
        self.assertEqual(summary.group(3, 4), ("0", "2"))


class Check8PersonalDataTest(DoctorCase):
    def planted(self):
        return {
            "email": "parent.example" + AT + "example.com",
            "phone": "+44 " + "7700 900" + "123",
            "phone-local": "(555) " + "010-" + "4477",
            "iban": "GB82 " + "WEST 1234 " + "5698 7654 32",
            "iban-compact": "GB82" + "WEST1234" + "5698765432",
            "dob-iso": "Date of birth: " + "2015-04-12",
            "dob-short": "DOB " + "12/04/" + "2015",
            "dob-born": "born on " + "12.04." + "2015",
        }

    def test_pass_dates_ids_times_and_prices(self):
        self.write("dance-school/classes/plain.md", note(
            "dance-school", ["dance-school"],
            body="Term 2 2026 starts 2026-04-13.\nClass 17:00-18:30, room 4.\nFee EUR 1,250.00 per term.\n"
                 "Version 1.53.0, ticket N-20260105-mkt001.\n"))
        self.assert_clean(*self.doctor()[:2])

    def test_warn_each_hint_exits_0_and_never_prints_it(self):
        for label, value in self.planted().items():
            with self.subTest(hint=label):
                self.write("dance-school/classes/contact.md", note(
                    "dance-school", ["dance-school"], body="Contact line: %s\n" % value))
                code, out, err = self.doctor()
                self.assertEqual(code, 0)
                self.assert_only(out, {("WARN", 8, "dance-school/classes/contact.md")})
                self.assertNotIn(value, out + err)
                self.assertNotIn("Contact line", out + err)

    def test_warning_does_not_hide_a_failure(self):
        self.write("dance-school/classes/contact.md", "Contact: %s\n" % self.planted()["email"])
        code, out, _ = self.doctor()
        self.assertEqual(code, 3)
        self.assert_only(out, {("FAIL", 2, "dance-school/classes/contact.md"),
                               ("WARN", 8, "dance-school/classes/contact.md")})


class Check9UnknownChannelTest(DoctorCase):
    def test_pass_case_folded_and_name_hash_channels(self):
        self.write("dance-school/classes/a.md", note("Dance-School", ["dance-school"]))
        self.write_scan_key()
        self.write_config({"name_hashes": {sbsupport.name_hash("examplestudio"): "dance-school"}})
        self.write("dance-school/classes/b.md", note("examplestudio"))
        self.assert_clean(*self.doctor()[:2])

    def test_fail_unknown_channel_exits_3(self):
        for value in ("personal", "dance-school-archive", "dance-school, personal", "examplestudio"):
            with self.subTest(channel=value):
                self.write("dance-school/classes/odd.md", note(value, ["dance-school"]))
                code, out, _ = self.doctor()
                self.assertEqual(code, 3)
                self.assert_only(out, {("FAIL", 9, "dance-school/classes/odd.md")})

    def test_custom_channels(self):
        self.write_config({"channels": ["studio", "garden"]})
        code, out, _ = self.doctor()
        self.assertEqual(code, 3)
        nine = {path for _, path in self.checks(out, 9)}
        self.assertEqual(len(nine), CLEAN_NOTE_COUNT, "every default-channel note is unknown now")


class DoctorEdgeCaseTest(DoctorCase):
    """Edge cases of the resolution and heuristic rules."""

    def test_check4_skips_untagged_and_mixed_notes(self):
        self.write("other-activities/admin/none.md", "body only\n")
        self.write("other-activities/admin/mixed.md", note("dance-school", ["dance-school", "other-activities"]))
        _, out, _ = self.doctor()
        self.assertEqual(self.checks(out, 4), [])
        self.assertEqual(self.checks(out, 2), [("FAIL", "other-activities/admin/none.md")])
        self.assertEqual(self.checks(out, 3), [("FAIL", "other-activities/admin/mixed.md")])

    def test_check5_ignores_ambiguous_stems_self_links_and_top_level_files(self):
        self.write("dance-school/classes/notes.md", note("dance-school", ["dance-school"]))
        self.write("other-activities/notes.md", note("other-activities", ["other-activities"]))
        self.write("dance-school/marketing/linker.md", note(
            "dance-school", ["dance-school"], links=["README.md", "dance-school/marketing/linker.md"],
            body="[[notes]] [[README]] [[linker]]\n"))
        self.assert_clean(*self.doctor()[:2])

    def test_check5_ambiguous_stem_is_ignored_from_either_side(self):
        self.write("dance-school/classes/notes.md", note("dance-school", ["dance-school"]))
        self.write("other-activities/notes.md", note("other-activities", ["other-activities"]))
        self.write("other-activities/admin/linker.md", note("other-activities", ["other-activities"],
                                                          body="See [[notes]].\n"))
        self.assert_clean(*self.doctor()[:2])

    def test_check5_relative_path_beats_an_ambiguous_stem(self):
        self.write("dance-school/classes/notes.md", note("dance-school", ["dance-school"]))
        self.write("other-activities/notes.md", note("other-activities", ["other-activities"]))
        self.write("dance-school/marketing/same.md", note("dance-school", ["dance-school"],
                                                        links=["../classes/notes.md"]))
        self.assert_clean(*self.doctor()[:2])
        self.write("dance-school/marketing/other.md", note("dance-school", ["dance-school"],
                                                         links=["../../other-activities/notes"]))
        code, out, _ = self.doctor()
        self.assertEqual(code, 3)
        self.assert_only(out, {("FAIL", 5, "dance-school/marketing/other.md")})

    def test_check6_two_channel_row_flags_every_path(self):
        rows = [("Both", "both", "dance-school+other-activities",
                 ["dance-school/classes/", "other-activities/admin/"], "Two channels")]
        self.write("ROUTER.md", clean_router(extra_dance=rows))
        code, out, _ = self.doctor()
        self.assertEqual(code, 3)
        self.assert_only(out, {("FAIL", 6, "dance-school/classes/"), ("FAIL", 6, "other-activities/admin/")})

    def test_check5_untagged_linker_is_not_cross_channel(self):
        self.write("dance-school/marketing/linker.md", "See [[pottery-workshop]].\n")
        _, out, _ = self.doctor()
        self.assertEqual(self.checks(out, 5), [])
        self.assertEqual(self.checks(out, 2), [("FAIL", "dance-school/marketing/linker.md")])

    def test_check5_links_block_list_without_indentation_ends_the_list(self):
        self.write("dance-school/marketing/linker.md", note(
            "dance-school", ["dance-school"],
            extra=["links:", '  - "dance-school/classes/term-timetable.md"', 'notes: "[[pottery-workshop]] is quoted here"']))
        _, out, _ = self.doctor()
        # the [[...]] in another field still counts: wiki links are read from the whole text
        self.assertEqual(self.checks(out, 5), [("FAIL", "dance-school/marketing/linker.md")])

    def test_check5_flow_list_with_trailing_comment(self):
        self.write("dance-school/marketing/linker.md", note(
            "dance-school", ["dance-school"],
            extra=['links: ["dance-school/classes/term-timetable.md", "other-activities/pottery-workshop.md"]  # two']))
        code, out, _ = self.doctor()
        self.assertEqual(code, 3)
        self.assert_only(out, {("FAIL", 5, "dance-school/marketing/linker.md")})

    def test_check6_row_routing_the_whole_tree_is_out_of_scope(self):
        rows = [("Everything", "all", "dance-school", ["."], "Too wide")]
        self.write("ROUTER.md", clean_router(extra_dance=rows))
        code, out, _ = self.doctor()
        self.assertEqual(code, 3)
        self.assertEqual(self.checks(out, 6), [("FAIL", ".")])

    def test_check6_channel_cell_is_case_folded(self):
        rows = [("Supplies", "supplies", "Other-Activities", ["other-activities/admin/"], "Supplies")]
        self.write("ROUTER.md", clean_router(extra_other=rows))
        self.assert_clean(*self.doctor()[:2])

    def test_check8_date_ranges_and_ids_are_not_phone_numbers(self):
        self.write("dance-school/classes/plain.md", note(
            "dance-school", ["dance-school"],
            body="Term: 2026-04-13 - 2026-07-10, then 13.04.2026 to 10.07.2026.\n"
                 "Booking 20260413-123456 and invoice INV-2026-0413-0001.\nStarts 2026-04-13 09:00 sharp.\n"
                 "Birthdays are never stored here.\n"))
        self.assert_clean(*self.doctor()[:2])

    def test_check8_plain_digit_run_counts_as_a_phone_number(self):
        self.write("dance-school/classes/contact.md", note(
            "dance-school", ["dance-school"], body="Ring " + "0" + "7700 " + "900 " + "123" + "\n"))
        _, out, _ = self.doctor()
        self.assertEqual(self.checks(out, 8), [("WARN", "dance-school/classes/contact.md")])

    def test_check9_quoted_value_with_comment_and_unknown_label(self):
        self.write("dance-school/classes/a.md", 'channel: "dance-school"  # main channel\n\nbody\n')
        self.write("dance-school/classes/b.md", "labels: ['channel:personal']\n\nbody\n")
        code, out, _ = self.doctor()
        self.assertEqual(code, 3)
        self.assert_only(out, {("FAIL", 9, "dance-school/classes/b.md")})


class ExitCodeAndOutputTest(DoctorCase):
    def break_everything(self):
        rows = [("Recitals", "recital", "dance-school", ["dance-school/recitals/"], "missing"),
                ("Supplies", "supplies", "dance-school", ["other-activities/admin/"], "wrong channel")]
        self.write("ROUTER.md", clean_router(extra_dance=rows))
        self.write("dance-school/classes/untagged.md", "Sentinel body line one\n")
        self.write("dance-school/classes/mixed.md", note("dance-school", ["dance-school", "other-activities"],
                                                         body="Sentinel body line two\n"))
        self.write("other-activities/admin/stray.md", note("dance-school", ["dance-school"]))
        self.write("dance-school/marketing/linker.md", note("dance-school", ["dance-school"], body="[[supplies]]\n"))
        self.write("dance-school/costumes/list.md", note("dance-school", ["dance-school"]))
        self.write("dance-school/classes/contact.md", note("dance-school", ["dance-school"],
                                                          body="Mail " + "kid.example" + AT + "example.org\n"))
        self.write("dance-school/classes/odd.md", note("personal"))

    def test_every_check_fires_once(self):
        self.break_everything()
        code, out, _ = self.doctor()
        self.assertEqual(code, 3)
        self.assertEqual(sorted({f[1] for f in self.doctor_lines(out)}), list(range(1, 10)))

    def test_output_holds_paths_and_check_numbers_only(self):
        self.break_everything()
        code, out, err = self.doctor()
        self.assertEqual(err, "")
        for line in out.splitlines():
            self.assertTrue(sbsupport.DOCTOR_LINE.match(line) or sbsupport.DOCTOR_SUMMARY.match(line))
        for text in ("Sentinel body", "kid.example", "personal", "Recitals", "wrong channel", self.brain):
            self.assertNotIn(text, out)

    def test_summary_counts(self):
        self.break_everything()
        _, out, _ = self.doctor()
        found = self.doctor_lines(out)
        summary = sbsupport.DOCTOR_SUMMARY.match(out.splitlines()[-1])
        fails = sum(1 for f in found if f[0] == "FAIL")
        warns = sum(1 for f in found if f[0] == "WARN")
        self.assertEqual(summary.group(3, 4), (str(fails), str(warns)))
        self.assertEqual(summary.group(2), str(CLEAN_ROW_COUNT + 2))

    def test_exit_3_wins_over_exit_1(self):
        rows = [("Recitals", "recital", "dance-school", ["dance-school/recitals/"], "missing")]
        self.write("ROUTER.md", clean_router(extra_dance=rows))
        self.write("dance-school/classes/untagged.md", "no channel\n")
        code, out, _ = self.doctor()
        self.assertEqual(code, 3)
        self.assert_only(out, {("FAIL", 1, "dance-school/recitals/"), ("FAIL", 2, "dance-school/classes/untagged.md")})

    def test_warnings_only_exit_0(self):
        self.write("dance-school/costumes/list.md", note("dance-school", ["dance-school"],
                                                         body="Mail " + "kid.example" + AT + "example.org\n"))
        code, out, _ = self.doctor()
        self.assertEqual(code, 0)
        self.assert_only(out, {("WARN", 7, "dance-school/costumes/"), ("WARN", 8, "dance-school/costumes/list.md")})

    def test_raw_roots_are_not_doctored(self):
        self.write_config({"roots": ["dance-school", "other-activities"], "raw_roots": ["archive"]})
        self.write("archive/dump.md", "no channel\n")
        self.write("dance-school/raw/dump.md", "no channel\n")
        self.assert_clean(*self.doctor()[:2])

    def test_roots_limit_the_doctor(self):
        self.write_config({"roots": ["dance-school"]})
        self.write("other-activities/loose.md", "no channel\n")
        code, out, _ = self.doctor()
        self.assertEqual(self.checks(out, 2), [])


if __name__ == "__main__":
    unittest.main()
