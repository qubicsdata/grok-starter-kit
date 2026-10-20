"""Search parity (owner decision 3: no ripgrep dependency).

The same queries give the same ranked output with rg on PATH and with rg
hidden: PATH without rg (auto engine), `--engine python` and
`SB_ENGINE=python`. The python engine never spawns rg: a fake `rg` that
records every call sits first on PATH and must stay untouched. The rg-path
tests skip with a clear reason when ripgrep is not installed."""

import os
import unittest

import sbsupport
from sbsupport import SbCase, needs_rg, normalize_search, note

QUERIES = [
    "timetable", "ballet beginners", "BALLET", "allet", "workshops", "open day poster",
    "cafe", "café", "kiln clay", "longlineterm", "manyhits", "binaryterm", "latinterm",
    "crlfterm", "bigfileterm", "walrusgate", "c++ jazz", "yamlterm", "nothingmatcheszz",
    "term", "pottery-workshop",
]
VARIANTS = [
    ["--channel", "dance-school"],
    ["--channel", "other-activities"],
    ["--raw"],
    ["--limit", "3"],
]
VARIANT_QUERIES = ["timetable", "ballet beginners", "workshops", "walrusgate", "term"]


def corpus():
    files = sbsupport.clean_brain()
    files.update({
        "dance-school/classes/ballet-beginners.md": note(
            "dance-school", ["dance-school", "ballet"],
            body="# Ballet beginners\n\nBarre work, then centre.\nBeginners bring ballet shoes.\n"
                 "C++ jazz fusion (jazz) is a joke class.\n"),
        "dance-school/classes/cafe-notes.md": note(
            "dance-school", body="Café after class.\nCafe tables booked.\nterm notes\n"),
        "dance-school/marketing/poster-ideas.md": note(
            "dance-school", ["dance-school", "marketing"],
            body="# Poster ideas\n\nOpen day poster with the term dates.\nDay two poster.\n"),
        "dance-school/marketing/long-line.md": note(
            "dance-school", body=("filler " * 70) + "longlineterm " + ("tail " * 40) + "\n"),
        "dance-school/classes/many-hits.md": note(
            "dance-school",
            body="\n".join("manyhits line %d" % i for i in range(44)) + "\n# Manyhits heading\n"
                 + "\n".join("manyhits after %d" % i for i in range(10)) + "\n"),
        "dance-school/classes/crlf.md": note("dance-school", body="x").replace("\n", "\r\n")
            + "crlfterm in a windows file\r\nsecond crlfterm line\r\n",
        "dance-school/classes/settings.yaml": "channel: dance-school\nyamlterm: on\n",
        "other-activities/workshops-2026.md": note(
            "other-activities", ["other-activities", "workshop"],
            body="# Workshops\n\nThree workshops this term.\nwalrusgate\n"),
        "misc/untagged.md": "walrusgate and workshop notes without a channel\nterm\n",
        "misc/mixed.md": note("dance-school, other-activities", body="walrusgate mixed\nterm\n"),
        "dance-school/raw/dump.md": "walrusgate raw dump\nterm\n",
        "dance-school/.hidden/inside.md": "walrusgate hidden\n",
        "dance-school/api-token-notes.md": "walrusgate denied\n",
    })
    return files


class ParityCase(SbCase):
    def setUp(self):
        super().setUp()
        self.write_tree(corpus())
        self.write("dance-school/classes/binary.txt", b"binaryterm\x00\x01\x02 binaryterm\n")
        self.write("dance-school/classes/latin.md", b"latinterm caf\xe9 au lait\n\xff\xfe latinterm\n")
        self.write("dance-school/classes/big.txt", ("bigfileterm " + "x" * 99 + "\n") * 22000)
        outside = self.write("outside/linked.md", "walrusgate linked\n", root=self.tmp)
        os.symlink(outside, os.path.join(self.brain, "dance-school", "linked.md"))
        self.write_config()

    def arg_sets(self):
        sets = [[q] for q in QUERIES]
        for variant in VARIANTS:
            sets += [[q] + variant for q in VARIANT_QUERIES]
        return sets

    def run_mode(self, args, mode):
        """mode -> (path, extra argv, env); returns (code, out, engine or None)."""
        if mode == "python-flag":
            code, out, err = self.run_sb(args + ["--engine", "python"], path=self.fake_rg(passthrough=False))
        elif mode == "python-env":
            code, out, err = self.run_sb(args, path=self.fake_rg(passthrough=False), SB_ENGINE="python")
        elif mode == "auto-no-rg":
            code, out, err = self.run_sb(args, path=self.empty_bin)
        elif mode == "rg-flag":
            code, out, err = self.run_sb(args + ["--engine", "rg"], path=self.fake_rg())
        elif mode == "auto-rg":
            code, out, err = self.run_sb(args, path=self.fake_rg())
        elif mode == "rg-env":
            code, out, err = self.run_sb(args, path=self.fake_rg(), SB_ENGINE="rg")
        else:
            raise AssertionError("unknown mode")
        self.assertEqual(err, "", "no stderr on a search")
        return code, out, self.header(out).group("engine")

    def reference(self):
        out = {}
        for args in self.arg_sets():
            code, text, engine = self.run_mode(args, "python-flag")
            self.assertEqual(code, 0)
            self.assertEqual(engine, "python")
            out[tuple(args)] = text
        self.assertFalse(self.rg_called(), "the python engine spawned rg")
        return out

    def assert_mode_matches(self, mode, engine):
        ref = self.reference()
        for args in self.arg_sets():
            with self.subTest(mode=mode, args=args):
                code, text, used = self.run_mode(args, mode)
                self.assertEqual(code, 0)
                self.assertEqual(used, engine)
                self.assertEqual(normalize_search(text), normalize_search(ref[tuple(args)]))


class PythonEngineTest(ParityCase):
    def test_env_switch_matches_flag_and_never_spawns_rg(self):
        self.assert_mode_matches("python-env", "python")
        self.assertFalse(self.rg_called(), "SB_ENGINE=python spawned rg")

    def test_auto_without_rg_on_path_uses_python(self):
        self.assert_mode_matches("auto-no-rg", "python")

    def test_flag_wins_over_env(self):
        code, out, _ = self.run_sb(["timetable", "--engine", "python"],
                                   path=self.fake_rg(passthrough=False), SB_ENGINE="rg")
        self.assertEqual(code, 0)
        self.assertEqual(self.header(out).group("engine"), "python")
        self.assertFalse(self.rg_called())

    def test_absolute_expectations_on_the_python_engine(self):
        def paths(*args):
            code, out, _ = self.run_mode(list(args), "python-flag")
            self.assertEqual(code, 0)
            return self.result_paths(out)

        self.assertEqual(paths("bigfileterm"), [], "files over 2 MiB are skipped")
        self.assertEqual(paths("binaryterm"), [], "binary files are skipped")
        self.assertIn("dance-school/marketing/long-line.md", paths("longlineterm"))
        self.assertIn("dance-school/classes/latin.md", paths("latinterm"))
        self.assertIn("dance-school/classes/crlf.md", paths("crlfterm"))
        self.assertIn("dance-school/classes/settings.yaml", paths("yamlterm"))
        self.assertIn("dance-school/classes/ballet-beginners.md", paths("BALLET"))
        self.assertNotIn("dance-school/classes/ballet-beginners.md", paths("allet"), "terms are word-start anchored")
        walrus = paths("walrusgate", "--limit", "50")
        for rel in ("dance-school/raw/dump.md", "dance-school/.hidden/inside.md",
                    "dance-school/api-token-notes.md", "dance-school/linked.md"):
            self.assertNotIn(rel, walrus)
        self.assertIn("dance-school/raw/dump.md", paths("walrusgate", "--raw", "--limit", "50"))
        self.assertIn("other-activities/workshops-2026.md", paths("workshops"))

    def test_crlf_is_not_in_the_output(self):
        code, out, _ = self.run_mode(["crlfterm"], "python-flag")
        self.assertNotIn("\r", out)


@needs_rg
class RgEngineTest(ParityCase):
    def test_rg_flag_matches_python(self):
        self.assert_mode_matches("rg-flag", "rg")
        self.assertTrue(self.rg_called(), "--engine rg did not run rg")

    def test_auto_with_rg_on_path_uses_rg(self):
        self.assert_mode_matches("auto-rg", "rg")
        self.assertTrue(self.rg_called())

    def test_env_switch_rg(self):
        code, out, _ = self.run_mode(["timetable"], "rg-env")
        self.assertEqual(code, 0)
        self.assertEqual(self.header(out).group("engine"), "rg")
        self.assertTrue(self.rg_called())

    def test_flag_wins_over_env(self):
        code, out, _ = self.run_sb(["timetable", "--engine", "rg"], path=self.fake_rg(), SB_ENGINE="python")
        self.assertEqual(code, 0)
        self.assertEqual(self.header(out).group("engine"), "rg")
        self.assertTrue(self.rg_called())

    def test_rg_engine_in_custom_roots_and_raw_roots(self):
        self.write_config({"roots": ["dance-school", "missing-root"], "raw_roots": ["other-activities"]})
        for args in (["walrusgate", "--limit", "50"], ["walrusgate", "--raw", "--limit", "50"], ["term"]):
            with self.subTest(args=args):
                _, ref, _ = self.run_mode(args, "python-flag")
                _, got, _ = self.run_mode(args, "rg-flag")
                self.assertEqual(normalize_search(got), normalize_search(ref))


if __name__ == "__main__":
    unittest.main()
