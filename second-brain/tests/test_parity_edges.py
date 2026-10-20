"""Search parity on the edges where rg and the pure-Python engine could drift:
a NUL byte late in a file, the 2 MiB size limit, byte order marks, invalid
UTF-8 inside a word, decomposed accents, a colon in a file name, overlapping
roots, a file root, raw roots inside a searched root, a router file in a
subfolder, ignore files, upper-case folder and extension names, and an rg
config file named by $RIPGREP_CONFIG_PATH (sb must not honour it).

Every case compares `--engine rg` with `--engine python` (timing and engine
name masked); a few absolute expectations pin the python side too."""

import os
import unittest

import sbsupport
from sbsupport import SbCase, needs_rg, normalize_search, note

MAX_FILESIZE_FOR_TESTS = 2 * 1024 * 1024
NFC_CAFE = "Caf" + chr(0xE9)
NFD_CAFE = "Cafe" + chr(0x301)


def edge_corpus():
    files = sbsupport.clean_brain()
    files.update({
        "dance-school/classes/nfd-cafe.md": note("dance-school", body=NFD_CAFE + " corner meeting\n"),
        "dance-school/classes/nfc-cafe.md": note("dance-school", body=NFC_CAFE + " corner meeting\n"),
        "dance-school/classes/notes: colon.md": note("dance-school", body="colonterm inside\n"),
        "dance-school/classes/with space.md": note("dance-school", body="spaceterm inside\n"),
        "dance-school/Bin/upper.md": "edgeterm upper bin folder\n",
        "dance-school/NOTE.MD": "edgeterm upper extension\n",
        "dance-school/Secrets/plan.md": "edgeterm secret folder\n",
        "dance-school/ok/edge.md": note("dance-school", body="edgeterm visible\n"),
        "dance-school/.gitignore": "ok/\n",
        ".ignore": "dance-school/\n",
        ".rgignore": "*.md\n",
        "archive/old.md": note("dance-school", body="edgeterm archived\n"),
        "docs/INDEX.md": sbsupport.clean_router(),
        "top-level-file.md": note("dance-school", body="edgeterm at the top\n"),
    })
    return files


class EdgeCase(SbCase):
    def setUp(self):
        super().setUp()
        self.write_tree(edge_corpus())
        late = ("latenul matching line\n" * 8000).encode() + b"\x00tail\n"
        self.write("dance-school/classes/late-nul.txt", late)
        self.write("dance-school/classes/bom.md", b"\xef\xbb\xbf# bomterm heading\nbomterm body\n")
        self.write("dance-school/classes/bad-utf8.md", b"lat\xffinword and badterm\n\xffbadterm start\n")
        line = b"sizeterm " + b"x" * 90 + b"\n"
        exact = line * (MAX_FILESIZE_FOR_TESTS // len(line))
        exact += b"y" * (MAX_FILESIZE_FOR_TESTS - len(exact) - 1) + b"\n"
        self.write("dance-school/classes/exact-limit.txt", exact)
        self.write("dance-school/classes/over-limit.txt", exact + b"z\n")
        self.write_config()

    def both(self, args, **env):
        if self.rg_called():
            os.remove(self.marker)
        _, py, py_err = self.run_sb(args + ["--engine", "python"], path=self.fake_rg(passthrough=False), **env)
        self.assertFalse(self.rg_called(), "the python engine spawned rg")
        _, rg, rg_err = self.run_sb(args + ["--engine", "rg"], path=self.fake_rg(), **env)
        self.assertEqual((py_err, rg_err), ("", ""))
        self.assertEqual(self.header(rg).group("engine"), "rg")
        return py, rg

    def assert_parity(self, args, **env):
        py, rg = self.both(args, **env)
        self.assertEqual(normalize_search(rg), normalize_search(py))
        return py


@needs_rg
class EdgeParityTest(EdgeCase):
    QUERIES = ["latenul", "bomterm", "badterm", "inword", "cafe", NFC_CAFE.lower(), "colonterm", "spaceterm",
               "edgeterm", "sizeterm", "timetable", "meeting corner"]

    def test_queries_agree(self):
        for q in self.QUERIES:
            for extra in ([], ["--raw"], ["--limit", "50"]):
                with self.subTest(query=q, extra=extra):
                    self.assert_parity([q] + extra)

    def test_overlapping_and_file_roots_agree(self):
        self.write_config({"roots": [".", "dance-school", "dance-school/", "top-level-file.md", "missing"]})
        for q in ("edgeterm", "timetable", "kiln"):
            with self.subTest(query=q):
                out = self.assert_parity([q, "--limit", "50"])
                paths = self.result_paths(out)
                self.assertEqual(len(paths), len(set(paths)), "each file once")

    def test_raw_roots_inside_a_searched_root_agree(self):
        self.write_config({"roots": ["."], "raw_roots": ["archive"]})
        out = self.assert_parity(["edgeterm", "--limit", "50"])
        self.assertNotIn("archive/old.md", self.result_paths(out))
        out = self.assert_parity(["edgeterm", "--limit", "50", "--raw"])
        self.assertIn("archive/old.md", self.result_paths(out))

    def test_router_file_in_a_subfolder_agrees(self):
        self.write_config({"router_file": "docs/INDEX.md"})
        out = self.assert_parity(["timetable", "--limit", "50"])
        self.assertTrue(any(l.startswith("R ") for l in out.splitlines()))
        self.assertNotIn("docs/INDEX.md", out)

    def test_rg_config_file_is_not_honoured(self):
        # flags sb neither overrides nor filters away: they would change rg's hits
        rc = self.write("rg.conf", "--fixed-strings\n--glob=!*.txt\n--max-depth=2\n", root=self.tmp)
        self.assert_parity(["edgeterm", "--limit", "50"], RIPGREP_CONFIG_PATH=rc)
        self.assert_parity(["latenul"], RIPGREP_CONFIG_PATH=rc)


class EdgePythonTest(EdgeCase):
    """Absolute expectations on the python engine (they hold for rg through
    EdgeParityTest)."""

    def paths(self, *args):
        code, out, _ = self.run_sb(list(args) + ["--engine", "python", "--limit", "50"])
        self.assertEqual(code, 0)
        return self.result_paths(out), out

    def test_late_nul_makes_the_file_binary(self):
        self.assertEqual(self.paths("latenul")[0], [])

    def test_size_limit_is_inclusive(self):
        paths = self.paths("sizeterm")[0]
        self.assertIn("dance-school/classes/exact-limit.txt", paths)
        self.assertNotIn("dance-school/classes/over-limit.txt", paths)

    def test_accents_fold_both_ways(self):
        for q in ("cafe", NFC_CAFE.lower(), NFD_CAFE):
            with self.subTest(query=q):
                paths = self.paths(q)[0]
                self.assertIn("dance-school/classes/nfd-cafe.md", paths)
                self.assertIn("dance-school/classes/nfc-cafe.md", paths)

    def test_invalid_utf8_is_not_a_letter(self):
        paths, out = self.paths("inword")
        self.assertIn("dance-school/classes/bad-utf8.md", paths)
        self.assertNotIn(chr(0xFFFD), out)
        self.assertIn("dance-school/classes/bad-utf8.md", self.paths("badterm")[0])

    def test_ignore_files_and_case_rules(self):
        paths = self.paths("edgeterm")[0]
        self.assertIn("dance-school/ok/edge.md", paths, "ignore files are not honoured")
        self.assertIn("top-level-file.md", paths)
        for rel in ("dance-school/Bin/upper.md", "dance-school/NOTE.MD", "dance-school/Secrets/plan.md"):
            self.assertNotIn(rel, paths)

    def test_bom_line_keeps_its_line_number(self):
        _, out = self.paths("bomterm")
        hit = [m for m in self.results(out) if m.group("path") == "dance-school/classes/bom.md"]
        self.assertEqual(len(hit), 1)
        self.assertEqual(hit[0].group("line"), "1")


if __name__ == "__main__":
    unittest.main()
