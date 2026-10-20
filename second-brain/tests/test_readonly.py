"""sb is read-only: the byte hashes of the note tree (and of HOME and the config
folder) are unchanged after every command, on both engines and for the
doctor on a clean and on a broken tree; no file or folder is added."""

import os
import unittest

import sbsupport
from sbsupport import REAL_RG, SbCase, note, tree_digest

COMMANDS = [
    ["--help"],
    ["timetable", "--engine", "python"],
    ["ballet beginners", "--engine", "python", "--channel", "dance-school"],
    ["walrusgate", "--engine", "python", "--raw"],
    ["nothingmatcheszz", "--engine", "python"],
    ["--doctor"],
    ["timetable", "--channel", "personal"],
    ["--bogus"],
]
STUB_LINE = "sb: not implemented"
RG_COMMANDS = [
    ["timetable", "--engine", "rg"],
    ["walrusgate", "--engine", "rg", "--raw", "--channel", "other-activities"],
    ["timetable"],
]


class ReadOnlyTest(SbCase):
    def setUp(self):
        super().setUp()
        self.write_tree(sbsupport.clean_brain())
        self.write("dance-school/raw/dump.md", "walrusgate\n")
        self.write("other-activities/w.md", note("other-activities", body="walrusgate\n"))
        self.write_config()

    def snapshot(self):
        return {
            "brain": tree_digest(self.brain),
            "home": tree_digest(self.home),
            "tmp": sorted(os.listdir(self.tmp)),
            "config": tree_digest(os.path.dirname(self.config_path))["kit.config.yaml"],
        }

    def assert_read_only(self, commands, path=None):
        before = self.snapshot()
        for args in commands:
            with self.subTest(args=args):
                _, _, err = self.run_sb(args, path=path)
                self.assertNotIn(STUB_LINE, err, "sb ran the stub")
                self.assertEqual(self.snapshot(), before)

    def test_commands_leave_the_tree_unchanged(self):
        self.assert_read_only(COMMANDS)

    def test_python_engine_without_rg_leaves_the_tree_unchanged(self):
        self.assert_read_only([["timetable"], ["walrusgate", "--raw"]], path=self.empty_bin)

    @unittest.skipUnless(REAL_RG, sbsupport.NO_RG_REASON)
    def test_rg_engine_leaves_the_tree_unchanged(self):
        self.assert_read_only(RG_COMMANDS)

    def test_doctor_on_a_broken_tree_leaves_it_unchanged(self):
        self.write("dance-school/classes/untagged.md", "no channel\n")
        self.write("other-activities/admin/stray.md", note("dance-school", ["dance-school"], body="[[term-timetable]]\n"))
        self.write("dance-school/costumes/list.md", note("dance-school", ["dance-school"]))
        self.assert_read_only([["--doctor"]])

    def test_cwd_inside_the_tree_leaves_it_unchanged(self):
        before = tree_digest(self.brain)
        for args in (["timetable", "--engine", "python"], ["--doctor"]):
            with self.subTest(args=args):
                _, _, err = self.run_sb(args, cwd=self.brain)
                self.assertNotIn(STUB_LINE, err, "sb ran the stub")
                self.assertEqual(tree_digest(self.brain), before)


if __name__ == "__main__":
    unittest.main()
