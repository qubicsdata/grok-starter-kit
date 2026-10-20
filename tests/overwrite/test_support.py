"""The harness's own plumbing: the case reader, case discovery and the
target override. These pass without the planner."""

import os
import shutil
import tempfile
import unittest

import caseyaml
from support import (
    DEFAULT_CASES_DIR, World, case_label, cases_dir, discover_cases, fact_slug,
    load_case, snapshot, unchanged_targets,
)

EXPECTED_CASES = 6
EXPECT_KEYS = {
    "routines_created", "proposals", "unchanged", "copies", "link_notes", "added",
    "duplicates_added", "agents_created_before_ok", "doctor_findings",
}


class CaseYamlTest(unittest.TestCase):
    def test_flow_collections(self):
        data = caseyaml.load('a: {name: x, list: [1, "two", three], empty: {}, none: []}\nb:\n  - {k: v}\n  - "q"\n')
        self.assertEqual(data, {
            "a": {"name": "x", "list": [1, "two", "three"], "empty": {}, "none": []},
            "b": [{"k": "v"}, "q"],
        })

    def test_scalars_and_comments(self):
        data = caseyaml.load("# head\nt: true\nf: false\nn: ~\ni: -12\ns: plain text  # tail\nq: 'it''s'\n")
        self.assertEqual(data, {"t": True, "f": False, "n": None, "i": -12, "s": "plain text", "q": "it's"})

    def test_nested_block_mappings(self):
        data = caseyaml.load("expect:\n  inner:\n    k: v\n  list:\n    - a\n    - b\nnext: 1\n")
        self.assertEqual(data, {"expect": {"inner": {"k": "v"}, "list": ["a", "b"]}, "next": 1})

    def test_rejects_block_mapping_in_list(self):
        with self.assertRaises(caseyaml.CaseYamlError):
            caseyaml.load("l:\n  - name: x\n    role: y\n")

    def test_rejects_duplicate_keys_and_tabs(self):
        with self.assertRaises(caseyaml.CaseYamlError):
            caseyaml.load("a: 1\na: 2\n")
        with self.assertRaises(caseyaml.CaseYamlError):
            caseyaml.load("a:\n\tb: 1\n")


class FixtureTest(unittest.TestCase):
    def test_six_cases_with_expect_blocks(self):
        paths = discover_cases(DEFAULT_CASES_DIR)
        self.assertEqual(len(paths), EXPECTED_CASES)
        for path in paths:
            with self.subTest(case=case_label(path)):
                case = load_case(path)
                self.assertIs(case.get("synthetic"), True, "every case declares itself synthetic")
                self.assertTrue(case["expect"])
                self.assertEqual(set(case["expect"]) - EXPECT_KEYS, set(), "unknown expect key")

    def test_case_05_has_a_coding_agent(self):
        paths = [p for p in discover_cases(DEFAULT_CASES_DIR) if "case-05" in p]
        self.assertEqual(len(paths), 1)
        case = load_case(paths[0])
        self.assertEqual([a["name"] for a in case["agents"]], ["example-coder"])
        self.assertEqual(case["expect"]["agents_created_before_ok"], 0)


class OverrideTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="kit-overwrite-override-")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.saved = os.environ.get("KIT_OVERWRITE_TARGET")
        self.addCleanup(self.restore)

    def restore(self):
        if self.saved is None:
            os.environ.pop("KIT_OVERWRITE_TARGET", None)
        else:
            os.environ["KIT_OVERWRITE_TARGET"] = self.saved

    def test_default_is_the_fixture_folder(self):
        os.environ.pop("KIT_OVERWRITE_TARGET", None)
        self.assertEqual(cases_dir(), DEFAULT_CASES_DIR)

    def test_env_override_points_at_another_case_folder(self):
        src = discover_cases(DEFAULT_CASES_DIR)[0]
        shutil.copyfile(src, os.path.join(self.tmp, "case-99-copy.yaml"))
        with open(os.path.join(self.tmp, "not-a-case.yaml"), "w") as fh:
            fh.write("x: 1\n")
        os.environ["KIT_OVERWRITE_TARGET"] = self.tmp
        self.assertEqual(discover_cases(), [os.path.join(self.tmp, "case-99-copy.yaml")])

    def test_missing_override_folder_is_an_error(self):
        os.environ["KIT_OVERWRITE_TARGET"] = os.path.join(self.tmp, "nowhere")
        with self.assertRaises(RuntimeError):
            discover_cases()


class WorldTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="kit-overwrite-world-")
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def test_materializes_every_kind_as_files(self):
        case = {
            "synthetic": True,
            "agents": [{"name": "example-coder", "role": "code", "skills": ["example-site-fix"]}],
            "skills": [{"name": "sb-lookup", "purpose": "p"}],
            "routines": [{"name": "example-daily-summary", "schedule": "08:00 daily"}],
            "memory": ["never posts on Sundays"],
            "files": ["my-marketing/campaigns/example.md"],
            "expect": {},
        }
        world = World(self.tmp, case)
        world.materialize()
        snap = world.snap()
        for rel in (
            "setup/agents/example-coder/AGENT.md", "setup/skills/example-site-fix/SKILL.md",
            "setup/skills/sb-lookup/SKILL.md", "setup/routines/example-daily-summary.md",
            "setup/memory/never-posts-on-sundays.md", "home/my-marketing/campaigns/example.md",
            "kit.config.yaml", "state.json",
        ):
            with self.subTest(path=rel):
                self.assertIn(rel, snap)
        self.assertNotEqual(world.sb, world.home, "files without front matter live outside the second brain")
        self.assertEqual(world.marketing_links(), {"my-marketing/campaigns/": "dance-school/marketing/campaigns/"})

    def test_notes_with_front_matter_put_the_second_brain_in_home(self):
        case = {"synthetic": True, "files": [{"path": "notes/x.md", "front_matter": {}}], "expect": {}}
        world = World(self.tmp, case)
        world.materialize()
        self.assertEqual(world.sb, world.home)
        with open(os.path.join(world.home, "notes", "x.md"), encoding="utf-8") as fh:
            self.assertTrue(fh.read().startswith("---\n---\n"))

    def test_snapshot_sees_bytes_and_mtimes(self):
        case = {"synthetic": True, "memory": ["a fact"], "expect": {}}
        world = World(self.tmp, case)
        world.materialize()
        before = world.snap()
        path = os.path.join(world.setup, "memory", "a-fact.md")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("a fact\n")  # same bytes, new mtime
        self.assertNotEqual(world.snap(), before, "a rewrite with identical bytes must show")

    def test_unchanged_targets_resolve(self):
        world = World(self.tmp, {"synthetic": True, "expect": {}})
        self.assertEqual(
            unchanged_targets(world, ["routines/r", "skills/s", "agents/a", "my-marketing/", "notes/n.md", "a Fact!"]),
            ["setup/routines/r.md", "setup/skills/s/", "setup/agents/a/", "home/my-marketing/",
             "home/notes/n.md", "setup/memory/a-fact.md"],
        )

    def test_fact_slug(self):
        self.assertEqual(fact_slug("Never posts on Sundays."), "never-posts-on-sundays")


if __name__ == "__main__":
    unittest.main()
