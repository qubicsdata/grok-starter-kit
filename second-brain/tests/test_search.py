"""sb search from config: usage text and --channel validation generated from
second_brain.channels, channel detection (generated channel regexes,
name_hashes, path_defaults), the strict channel filter, roots / raw_roots /
boost_paths, the deny rules, the output shape and the exit codes.

These run on the pure-Python engine; test_parity.py runs the same
behaviour through rg and checks both engines agree."""

import os
import re
import unittest

import sbsupport
from sbsupport import NO_HITS, SbCase, note

PY = ["--engine", "python"]


class SearchCase(SbCase):
    def setUp(self):
        super().setUp()
        self.write_tree(sbsupport.clean_brain())
        self.write_config()

    def search(self, *args, **kwargs):
        return self.run_sb(list(args) + PY, **kwargs)


class UsageAndValidationTest(SearchCase):
    def usage_channels(self, text):
        m = re.search(r"--channel (\S+)", text)
        self.assertIsNotNone(m, "usage names the channels")
        return m.group(1).strip("[]<>").split("|")

    def test_help_names_the_configured_channels(self):
        code, out, _ = self.run_sb(["--help"])
        self.assertEqual(code, 0)
        self.assertEqual(self.usage_channels(out), ["dance-school", "other-activities"])
        self.assertIn("second brain", out)
        self.assertIn("--doctor", out)

    def test_help_follows_custom_channels(self):
        self.write_config({"channels": ["studio", "garden"]})
        code, out, _ = self.run_sb(["--help"])
        self.assertEqual(code, 0)
        self.assertEqual(self.usage_channels(out), ["studio", "garden"])
        self.assertNotIn("dance-school", out)

    def test_help_without_any_config_uses_the_defaults(self):
        code, out, _ = self.run_sb(["-h"], config=False)
        self.assertEqual(code, 0)
        self.assertEqual(self.usage_channels(out), ["dance-school", "other-activities"])

    def test_unknown_channel_exits_2_and_lists_the_channels(self):
        for args in (["timetable", "--channel", "personal"], ["timetable", "--channel=personal"],
                     ["timetable", "-c", "Dance School"], ["timetable", "--channel"]):
            with self.subTest(args=args):
                code, out, err = self.search(*args)
                self.assertEqual(code, 2)
                self.assertEqual(out, "")
                self.assertIn("dance-school", err)
                self.assertIn("other-activities", err)

    def test_configured_channel_is_accepted_in_every_form(self):
        for args in (["timetable", "--channel", "dance-school"], ["timetable", "--channel=dance-school"],
                     ["timetable", "-c", "dance-school"]):
            with self.subTest(args=args):
                code, out, _ = self.search(*args)
                self.assertEqual(code, 0)
                self.assertEqual(self.header(out).group("channel"), "dance-school")

    def test_custom_channels_replace_the_defaults(self):
        self.write_config({"channels": ["studio", "garden"]})
        self.assertEqual(self.search("timetable", "--channel", "studio")[0], 0)
        self.assertEqual(self.search("timetable", "--channel", "dance-school")[0], 2)

    def test_usage_errors_exit_2(self):
        cases = {
            "no query": [],
            "only stop words": ["the", "and", "of"],
            "unknown flag": ["timetable", "--bogus"],
            "bad limit": ["timetable", "--limit", "many"],
            "bad engine": ["timetable", "--engine", "grep"],
        }
        for label, args in cases.items():
            with self.subTest(case=label):
                code, _, err = self.run_sb(args + (PY if "--engine" not in args else []))
                self.assertEqual(code, 2)
                self.assertTrue(err.strip(), "a usage message on stderr")

    def test_engine_rg_without_rg_on_path_exits_2(self):
        code, out, err = self.run_sb(["timetable", "--engine", "rg"], path=self.empty_bin)
        self.assertEqual(code, 2)
        self.assertEqual(out, "")
        self.assertIn("rg", err)


class OutputShapeTest(SearchCase):
    def test_router_rows_come_first(self):
        code, out, _ = self.search("timetable")
        self.assertEqual(code, 0)
        lines = out.splitlines()
        head = self.header(out)
        self.assertEqual(head.group("query"), "timetable")
        self.assertEqual(head.group("engine"), "python")
        self.assertEqual(int(head.group("router")), 1)
        m = sbsupport.ROUTER_LINE.match(lines[1])
        self.assertIsNotNone(m, "router line after the header")
        self.assertEqual(m.group("ch"), "dance-school")
        self.assertEqual(m.group("topic"), "Class schedule")
        self.assertEqual(m.group("paths"), "dance-school/classes/")
        self.assertEqual(self.result_paths(out)[0], "dance-school/classes/term-timetable.md")

    def test_result_line_holds_relative_path_line_and_best_line(self):
        code, out, _ = self.search("kiln")
        self.assertEqual(code, 0)
        results = self.results(out)
        self.assertEqual(len(results), 1)
        m = results[0]
        self.assertEqual(m.group("rank"), "1")
        self.assertEqual(m.group("tag"), "other-activities")
        self.assertEqual(m.group("path"), "other-activities/pottery-workshop.md")
        self.assertEqual(int(m.group("line")), 14)
        self.assertEqual(m.group("text"), "Clay, glazes and kiln dates.")
        self.assertNotIn(self.brain, out, "paths are relative to home")

    def test_path_match(self):
        self.write("dance-school/marketing/flyerdesign.md", note("dance-school", ["dance-school"], body="Nothing here.\n"))
        code, out, _ = self.search("flyerdesign")
        self.assertEqual(code, 0)
        results = self.results(out)
        self.assertEqual([m.group("path") for m in results], ["dance-school/marketing/flyerdesign.md"])
        self.assertIsNone(results[0].group("line"))
        self.assertEqual(results[0].group("text"), "(path match)")

    def test_no_hits(self):
        code, out, _ = self.search("xylophonequartz")
        self.assertEqual(code, 0)
        self.assertTrue(out.splitlines()[-1].startswith(NO_HITS))
        self.assertEqual(self.results(out), [])

    def test_limit(self):
        for i in range(6):
            self.write("dance-school/classes/lesson-%d.md" % i,
                       note("dance-school", ["dance-school"], body="Pirouette drill %d\n" % i))
        code, out, _ = self.search("pirouette", "--limit", "3")
        self.assertEqual(code, 0)
        self.assertEqual(len(self.results(out)), 3)
        head = self.header(out)
        self.assertEqual((head.group("shown"), head.group("total")), ("3", "6"))
        code, out, _ = self.search("pirouette", "--limit=2")
        self.assertEqual(len(self.results(out)), 2)

    def test_credential_lines_are_withheld(self):
        secret_line = "pass" + "word = '" + "Xk29vLq7Zp" + "'  rehearsal"
        self.write("dance-school/admin/login-notes.md", note("dance-school", ["dance-school"], body=secret_line + "\n"))
        code, out, _ = self.search("rehearsal")
        self.assertEqual(code, 0)
        self.assertNotIn("Xk29vLq7Zp", out)
        results = self.results(out)
        self.assertEqual(results[0].group("path"), "dance-school/admin/login-notes.md")
        self.assertEqual(results[0].group("text"), sbsupport.WITHHELD_SECRET)


class ChannelDetectionTest(SearchCase):
    def tag_of(self, rel, body_word):
        code, out, _ = self.search(body_word)
        self.assertEqual(code, 0)
        tags = {m.group("path"): m.group("tag") for m in self.results(out)}
        self.assertIn(rel, tags)
        return tags[rel]

    def test_detection_rules(self):
        cases = [
            ("misc/a.md", note("dance-school"), "dance-school"),
            ("misc/b.md", "- **channel:** other-activities\n", "other-activities"),
            ("misc/c.md", "labels: ['channel:dance-school']\n", "dance-school"),
            ("misc/d.md", note(None, ["other-activities", "topic"]), "other-activities"),
            ("misc/e.md", note("Dance-School"), "dance-school"),
            ("misc/f.md", note("dance-school (moved from other-activities)"), "dance-school"),
            ("misc/g.md", note("dance-school, other-activities"), "dance-school+other-activities"),
            ("misc/h.md", note(None, ["topic"]), "?"),
            ("misc/i.md", note("dance-school-archive"), "?"),
            ("misc/j.md", note("personal"), "?"),
            ("dance-school/k.md", note(None, ["topic"]), "dance-school"),
            ("misc/l.md", note("dance-school", ["dance-school", "other-activities"]), "dance-school"),
        ]
        for rel, text, _ in cases:
            self.write(rel, text + "\nquokkaword\n")
        code, out, _ = self.search("quokkaword", "--limit", "50")
        self.assertEqual(code, 0)
        tags = {m.group("path"): m.group("tag") for m in self.results(out)}
        for rel, _, want in cases:
            with self.subTest(note=rel):
                self.assertEqual(tags.get(rel), want)

    def test_only_the_first_30_lines_count(self):
        text = "\n".join(["filler line"] * 30) + "\nchannel: dance-school\nquokkaword\n"
        self.write("misc/late.md", text)
        self.assertEqual(self.tag_of("misc/late.md", "quokkaword"), "?")

    def test_channel_names_are_escaped_in_the_generated_regexes(self):
        self.write_config({"channels": ["studio.one", "garden"]})
        self.write("misc/x.md", note("studioXone") + "\nquokkaword\n")
        self.write("misc/y.md", note("studio.one") + "\nquokkaword\n")
        code, out, _ = self.search("quokkaword")
        tags = {m.group("path"): m.group("tag") for m in self.results(out)}
        self.assertEqual(tags, {"misc/x.md": "?", "misc/y.md": "studio.one"})

    def test_name_hashes_empty_by_default(self):
        self.write("misc/n.md", note("examplestudio") + "\nquokkaword\n")
        self.assertEqual(self.tag_of("misc/n.md", "quokkaword"), "?")

    def test_name_hashes_from_config(self):
        self.write_scan_key()
        self.write_config({"name_hashes": {sbsupport.name_hash("examplestudio"): "dance-school"}})
        self.write("misc/n.md", note("Examplestudio") + "\nquokkaword\n")
        self.assertEqual(self.tag_of("misc/n.md", "quokkaword"), "dance-school")

    def test_path_defaults_follow_config(self):
        self.write_config({"path_defaults": {"school/": "dance-school", "school/club/": "other-activities"}})
        self.write("school/a.md", "no front matter\nquokkaword\n")
        self.write("school/club/b.md", "no front matter\nquokkaword\n")
        self.write("dance-school/c.md", "no front matter\nquokkaword\n")
        code, out, _ = self.search("quokkaword")
        tags = {m.group("path"): m.group("tag") for m in self.results(out)}
        self.assertEqual(tags, {"school/a.md": "dance-school", "school/club/b.md": "other-activities",
                                "dance-school/c.md": "?"})


class ChannelFilterTest(SearchCase):
    def test_strict_filter_withholds_other_untagged_and_mixed(self):
        self.write("dance-school/a.md", note("dance-school", body="otterbadge\n"))
        self.write("other-activities/b.md", note("other-activities", body="otterbadge\n"))
        self.write("misc/c.md", "otterbadge\n")
        self.write("misc/d.md", note("dance-school, other-activities", body="otterbadge\n"))
        code, out, _ = self.search("otterbadge", "--channel", "dance-school")
        self.assertEqual(code, 0)
        self.assertEqual(self.result_paths(out), ["dance-school/a.md"])
        self.assertEqual(self.header(out).group("withheld"), "3")

    def test_router_rows_are_filtered_too(self):
        code, out, _ = self.search("timetable", "--channel", "other-activities")
        self.assertEqual(code, 0)
        self.assertEqual(self.header(out).group("router"), "0")
        self.assertFalse(any(l.startswith("R ") for l in out.splitlines()))

    def test_no_filter_shows_everything(self):
        self.write("misc/c.md", "otterbadge\n")
        self.write("other-activities/b.md", note("other-activities", body="otterbadge\n"))
        code, out, _ = self.search("otterbadge")
        self.assertEqual(sorted(self.result_paths(out)), ["misc/c.md", "other-activities/b.md"])
        self.assertIsNone(self.header(out).group("withheld"))


class RootsTest(SearchCase):
    def setUp(self):
        super().setUp()
        self.write("dance-school/r1.md", note("dance-school", body="lanternfish\n"))
        self.write("other-activities/r2.md", note("other-activities", body="lanternfish\n"))
        self.write("archive/r3.md", note("dance-school", body="lanternfish\n"))

    def test_default_root_is_the_whole_home(self):
        _, out, _ = self.search("lanternfish")
        self.assertEqual(sorted(self.result_paths(out)),
                         ["archive/r3.md", "dance-school/r1.md", "other-activities/r2.md"])

    def test_roots_limit_the_search(self):
        self.write_config({"roots": ["dance-school", "does-not-exist"]})
        code, out, _ = self.search("lanternfish")
        self.assertEqual(code, 0)
        self.assertEqual(self.result_paths(out), ["dance-school/r1.md"])

    def test_raw_roots_only_with_raw(self):
        self.write_config({"roots": ["dance-school", "other-activities"], "raw_roots": ["archive"]})
        _, out, _ = self.search("lanternfish")
        self.assertNotIn("archive/r3.md", self.result_paths(out))
        _, out, _ = self.search("lanternfish", "--raw")
        self.assertIn("archive/r3.md", self.result_paths(out))

    def test_raw_named_files_only_with_raw(self):
        self.write("dance-school/raw/dump.md", "lanternfish\n")
        self.write("dance-school/raw-export.md", "lanternfish\n")
        self.write("dance-school/_tmp/scratch.md", "lanternfish\n")
        _, out, _ = self.search("lanternfish")
        paths = self.result_paths(out)
        for rel in ("dance-school/raw/dump.md", "dance-school/raw-export.md", "dance-school/_tmp/scratch.md"):
            self.assertNotIn(rel, paths)
        _, out, _ = self.search("lanternfish", "--raw")
        paths = self.result_paths(out)
        for rel in ("dance-school/raw/dump.md", "dance-school/raw-export.md", "dance-school/_tmp/scratch.md"):
            self.assertIn(rel, paths)

    def test_boost_paths(self):
        self.write_config({"roots": ["boost"]})
        body = note("dance-school", body="marmalade recipe\n")
        self.write("boost/a/one.md", body)
        self.write("boost/b/two.md", body)
        _, out, _ = self.search("marmalade")
        self.assertEqual(self.result_paths(out), ["boost/a/one.md", "boost/b/two.md"])
        self.write_config({"roots": ["boost"], "boost_paths": ["boost/b"]})
        _, out, _ = self.search("marmalade")
        self.assertEqual(self.result_paths(out), ["boost/b/two.md", "boost/a/one.md"])


class RankingTest(SearchCase):
    """The shared ranking (both engines feed it): each bonus moves a result."""

    def order(self, *args):
        code, out, _ = self.search(*(list(args) + ["--limit", "50"]))
        self.assertEqual(code, 0)
        return self.result_paths(out), out

    def test_router_row_paths_rank_first(self):
        self.write("aaa/plan.md", note("dance-school", body="timetable notes\n"))
        self.write("dance-school/classes/plan.md", note("dance-school", body="timetable notes\n"))
        paths, _ = self.order("timetable")
        self.assertLess(paths.index("dance-school/classes/plan.md"), paths.index("aaa/plan.md"))

    def test_raw_files_rank_below_curated_ones(self):
        self.write("dance-school/raw/a.md", "penaltyterm\n")
        self.write("dance-school/zz.md", "penaltyterm\n")
        paths, _ = self.order("penaltyterm", "--raw")
        self.assertEqual(paths, ["dance-school/zz.md", "dance-school/raw/a.md"])

    def test_path_match_adds_to_a_content_match(self):
        self.write("misc/a/note.md", "penguinterm\n")
        self.write("misc/b/penguinterm.md", "penguinterm\n")
        paths, _ = self.order("penguinterm")
        self.assertEqual(paths, ["misc/b/penguinterm.md", "misc/a/note.md"])

    def test_heading_is_the_best_line(self):
        self.write("misc/h.md", "albatrossterm in a line\nfiller\n# Albatrossterm heading\n")
        _, out = self.order("albatrossterm")
        m = self.results(out)[0]
        self.assertEqual((m.group("line"), m.group("text")), ("3", "# Albatrossterm heading"))


class DenyRulesTest(SearchCase):
    def test_denied_names_are_never_searched(self):
        denied = [
            "dance-school/api-token-notes.md", "dance-school/my-secret.md", "dance-school/credentials.md",
            "dance-school/local.env", "dance-school/.env.local", "dance-school/bin/tool.md",
            "dance-school/node_modules/pkg/readme.md", "dance-school/.hidden/inside.md",
            "dance-school/.dotfile.md", "dance-school/picture.png",
        ]
        for rel in denied:
            self.write(rel, "walrusgate\n")
        self.write("dance-school/visible.md", "walrusgate\n")
        self.write("dance-school/visible.yaml", "walrusgate: 1\n")
        self.write("dance-school/visible.txt", "walrusgate\n")
        code, out, _ = self.search("walrusgate", "--limit", "50")
        self.assertEqual(code, 0)
        self.assertEqual(sorted(self.result_paths(out)),
                         ["dance-school/visible.md", "dance-school/visible.txt", "dance-school/visible.yaml"])

    def test_router_file_is_not_a_file_hit(self):
        code, out, _ = self.search("timetable")
        self.assertEqual(code, 0)
        paths = self.result_paths(out)
        self.assertIn("dance-school/classes/term-timetable.md", paths)
        self.assertNotIn("ROUTER.md", paths)

    def test_ignore_files_are_not_honoured(self):
        self.write(".gitignore", "dance-school/ignored.md\n")
        self.write("dance-school/.gitignore", "*\n")
        self.write("dance-school/ignored.md", "walrusgate\n")
        _, out, _ = self.search("walrusgate")
        self.assertEqual(self.result_paths(out), ["dance-school/ignored.md"])

    def test_symlinks_are_not_followed(self):
        outside = self.write("outside/target.md", "walrusgate\n", root=self.tmp)
        os.symlink(outside, os.path.join(self.brain, "dance-school", "link.md"))
        os.symlink(os.path.dirname(outside), os.path.join(self.brain, "dance-school", "linkdir"))
        self.write("dance-school/real.md", "walrusgate\n")
        code, out, _ = self.search("walrusgate")
        self.assertEqual(code, 0)
        self.assertEqual(self.result_paths(out), ["dance-school/real.md"])


if __name__ == "__main__":
    unittest.main()
