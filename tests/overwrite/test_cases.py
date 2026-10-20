"""The six existing-setup cases against the reference planner.

For every `case-*.yaml` in the case folder (the fixtures by default,
`KIT_OVERWRITE_TARGET` or `--existing-dir` to override) a test class is
generated: the synthetic setup is materialized in a temp folder, bytes and
mtimes are snapshotted, the dry run must match the case's `expect` block
exactly and change nothing, `--apply` without approval or with a wrong hash
must refuse and write nothing, and `--apply` with the right hash may create
only the planned new files while every existing byte and mtime stays.

The `expect` keys and how they map onto the plan (tools/KIT-PLAN-SPEC.md):

  routines_created: N        N `add` items of kind routine at checkpoint 5a
  proposals: [...]           merge/into -> routine merge; extend/skill, add/skill;
                             extend/agent (+add_skills, add_routines); create/agent -> add
  unchanged: [...]           every entry under the path is identical afterwards and
                             nothing was added inside it
  copies: 0                  no new file repeats the bytes of one of hers
  link_notes: [...]          exactly these `link` items; each names her file
  added / duplicates_added   memory facts added as files, duplicates skipped
  agents_created_before_ok   no new entry under setup/agents after dry-run or apply
  doctor_findings: [...]     the `report` item of kind doctor lists exactly these
"""

import json
import os
import re
import unittest

from support import (
    EXIT_OK, EXIT_USAGE, EXIT_PLAN_CHANGED, REFUSALS, WRITING_TYPES,
    HarnessCase, case_label, discover_cases, fact_slug, items_where, load_case,
    plan_sha256, unchanged_targets, under, writing_items,
)


def file_targets(world, plan):
    """tmp-relative paths of the files `--apply` must create."""
    out = set()
    for item in writing_items(plan):
        if item["root"] not in ("sb", "setup"):
            continue
        if not item["target"].endswith("/"):
            out.add(world.rel(world.item_path(item)))
    return out


def folder_targets(world, plan):
    out = set()
    for item in writing_items(plan):
        if item["root"] in ("sb", "setup") and item["target"].endswith("/"):
            out.add(world.rel(world.item_path(item)) + "/")
    return out


def parents(rel):
    out = set()
    while "/" in rel:
        rel = rel.rsplit("/", 1)[0]
        out.add(rel + "/")
    return out


def new_entries(before, after):
    return {k: v for k, v in after.items() if k not in before}


def her_digests(before):
    return {v[1] for k, v in before.items() if k.startswith("home/") and v[0] == "file"}


class CaseTests(HarnessCase):
    """Generated per case; CASE_PATH names the case file."""

    # ---------------------------------------------------------------- dry run

    def test_dry_run_plan_shape(self):
        world = self.world()
        plan = self.dry_run(world)
        self.assert_plan_shape(plan)

    def test_dry_run_writes_nothing(self):
        world = self.world()
        before = world.snap(dir_mtime=True)
        self.dry_run(world)
        self.assertEqual(world.snap(dir_mtime=True), before, "a dry run changed or created something")

    def test_dry_run_is_deterministic(self):
        world = self.world()
        first = self.dry_run(world)
        second = self.dry_run(world)
        self.assertEqual(first["items"], second["items"])
        self.assertEqual(first["sha256"], second["sha256"])

    def test_dry_run_never_targets_existing(self):
        world = self.world()
        plan = self.dry_run(world)
        self.assert_never_touches_existing(world, plan)

    def test_dry_run_keeps_her_things_unchanged(self):
        world = self.world()
        before = world.snap(dir_mtime=True)
        self.dry_run(world)
        self.assert_unchanged(before, world.snap(dir_mtime=True),
                              unchanged_targets(world, world.case["expect"].get("unchanged", [])))

    def test_choices_come_in_groups(self):
        """Alternatives for one decision share a `choice` group of two or more
        items; every grouped item carries a non-empty group name."""
        world = self.world()
        plan = self.dry_run(world)
        groups = {}
        for item in plan["items"]:
            if "choice" in item:
                self.assertTrue(item["choice"], "empty choice group")
                groups.setdefault(item["choice"], []).append(item)
        for name, members in groups.items():
            with self.subTest(choice=name):
                self.assertGreaterEqual(len(members), 2, "a choice needs at least two options")

    # ---------------------------------------------------------------- expect

    def check_routines_created(self, world, plan, expected):
        routines = [i for i in items_where(plan, type="add", kind="routine") if i["checkpoint"].startswith("5")]
        self.assertEqual(len(routines), expected, "routine add items at checkpoint 5a: %r" % routines)

    def check_proposals(self, world, plan, expected):
        for proposal in expected:
            with self.subTest(proposal=proposal):
                kind = "routine" if "into" in proposal else "skill" if "skill" in proposal else "agent"
                name = proposal.get("into") or proposal.get("skill") or proposal.get("agent")
                ptype = {"create": "add"}.get(proposal["type"], proposal["type"])
                matches = [i for i in items_where(plan, type=ptype, kind=kind)
                           if i.get("name") == name or (ptype == "merge" and i.get("into") == name)]
                self.assertEqual(len(matches), 1, "exactly one %s item for %s %s" % (ptype, kind, name))
                item = matches[0]
                if ptype == "merge":
                    self.assertEqual(item.get("into"), name)
                    self.assertEqual(item["root"], "setup")
                    self.assertEqual(item["target"], "routines/%s.md" % name)
                    self.assertEqual(item["checkpoint"], "5a")
                    self.assertTrue(item.get("sections"), "a merge lists the sections it adds")
                    self.assertEqual(items_where(plan, type="add", kind="routine", name="morning-brief"), [],
                                     "no second routine doing the same job")
                if kind == "skill":
                    self.assertEqual(item["checkpoint"], "4")
                    self.assertEqual(item["root"], "setup")
                    self.assertEqual(item["target"], "skills/%s/SKILL.md" % name)
                    if ptype == "extend":
                        self.assertTrue(item.get("additions"), "an extend lists the steps it proposes")
                    else:
                        self.assertEqual(item.get("source"), "grok-skills/%s/SKILL.md" % name.replace("-kit", ""))
                if kind == "agent":
                    self.assertEqual(item["checkpoint"], "8a")
                    self.assertEqual(item["root"], "setup")
                    self.assertEqual(item["target"], "agents/%s/AGENT.md" % name)
                    if "add_skills" in proposal:
                        self.assertEqual(sorted(item.get("add_skills") or []), sorted(proposal["add_skills"]))
                    if "add_routines" in proposal:
                        self.assertEqual(sorted(item.get("add_routines") or []), sorted(proposal["add_routines"]))
        # two proposals about the same decision are one choice group
        by_kind = {}
        for proposal in expected:
            kind = "routine" if "into" in proposal else "skill" if "skill" in proposal else "agent"
            by_kind.setdefault(kind, []).append(proposal)
        for kind, group in by_kind.items():
            if len(group) < 2:
                continue
            names = [p.get("skill") or p.get("agent") for p in group]
            items = [i for i in plan["items"] if i["kind"] == kind and i.get("name") in names
                     and i["type"] in ("add", "extend")]
            choices = {i.get("choice") for i in items}
            self.assertEqual(len(choices), 1, "the options of one decision share a choice group")
            self.assertTrue(choices.pop(), "options need a named choice group")

    def check_copies(self, world, plan, expected):
        self.assertEqual(expected, 0, "the fixtures only ever expect zero copies")
        for item in plan["items"]:
            if item["type"] == "add":
                self.assertNotIn(item.get("source"), world.her_files,
                                 "an add item would copy one of her files")

    def check_link_notes(self, world, plan, expected):
        links = items_where(plan, type="link")
        self.assertEqual(sorted(i["target"] for i in links), sorted(expected))
        for item in links:
            with self.subTest(link=item["target"]):
                self.assertEqual(item["root"], "sb")
                self.assertEqual(item["checkpoint"], "3")
                self.assertEqual(item["kind"], "note")
                self.assertIn(item.get("links_to"), world.her_files, "a link names one of her files")

    def check_added(self, world, plan, expected):
        facts = [i.get("fact") for i in items_where(plan, type="add", kind="memory")]
        self.assertEqual(sorted(facts), sorted(expected))
        for item in items_where(plan, type="add", kind="memory"):
            self.assertEqual(item["root"], "setup")
            self.assertEqual(item["target"], "memory/%s.md" % fact_slug(item["fact"]))

    def check_duplicates_added(self, world, plan, expected):
        self.assertEqual(expected, 0)
        existing = {fact_slug(f) for f in world.case.get("memory") or []}
        kit = world.case.get("kit_facts") or []
        duplicates = [f for f in kit if fact_slug(f) in existing]
        added = [i for i in items_where(plan, type="add", kind="memory") if fact_slug(i.get("fact", "")) in existing]
        self.assertEqual(added, [], "a duplicate fact would be added")
        skipped = items_where(plan, type="skip", kind="memory")
        self.assertEqual(sorted(i.get("fact") for i in skipped), sorted(duplicates),
                         "every duplicate is a skip item")
        for item in skipped:
            self.assertIn("duplicate", item["reason"].lower())

    def check_agents_created_before_ok(self, world, plan, expected, before):
        self.assertEqual(expected, 0)
        created = [k for k in new_entries(before, world.snap()) if k.startswith("setup/agents/")]
        self.assertEqual(created, [], "an agent appeared before any OK")
        agent_adds = items_where(plan, type="add", kind="agent")
        for item in agent_adds:
            self.assertTrue(item.get("choice"), "creating an agent next to her coding agent is a choice")

    def check_doctor_findings(self, world, plan, expected):
        reports = items_where(plan, type="report", kind="doctor")
        self.assertEqual(len(reports), 1, "exactly one doctor report item")
        report = reports[0]
        self.assertEqual(report["checkpoint"], "3")
        found = sorted((f["path"], f["check"]) for f in report.get("findings") or [])
        self.assertEqual(found, sorted((f["path"], f["check"]) for f in expected))
        for path, _ in found:
            self.assertIn(path, world.her_files, "a doctor finding names one of her existing notes")

    EXPECT_CHECKS = {
        "routines_created": check_routines_created,
        "proposals": check_proposals,
        "copies": check_copies,
        "link_notes": check_link_notes,
        "added": check_added,
        "duplicates_added": check_duplicates_added,
        "agents_created_before_ok": check_agents_created_before_ok,
        "doctor_findings": check_doctor_findings,
    }

    # ---------------------------------------------------------------- apply

    def test_apply_without_approval_is_refused(self):
        world = self.world()
        self.require_planner()
        before = world.snap(dir_mtime=True)
        code, out, err = world.run("--apply", "--json")
        self.assertEqual(code, EXIT_USAGE, "apply without --approved must be a usage error")
        self.assertEqual(world.snap(dir_mtime=True), before, "a refused apply wrote something")

    def test_apply_with_wrong_sha_is_refused(self):
        world = self.world()
        self.dry_run(world)
        before = world.snap(dir_mtime=True)
        code, out, err = self.apply(world, "0" * 64)
        self.assertEqual(code, EXIT_PLAN_CHANGED)
        self.assertEqual(world.snap(dir_mtime=True), before, "a refused apply wrote something")

    def test_apply_and_dry_run_together_is_a_usage_error(self):
        world = self.world()
        plan = self.dry_run(world)
        before = world.snap(dir_mtime=True)
        code, out, err = world.run("--dry-run", "--apply", "--approved", plan["sha256"])
        self.assertEqual(code, EXIT_USAGE)
        self.assertEqual(world.snap(dir_mtime=True), before)

    def test_apply_with_the_right_sha_creates_only_new_files(self):
        world = self.world()
        plan = self.dry_run(world)
        before = world.snap()
        code, out, err = self.apply(world, plan["sha256"])
        self.assertEqual(code, EXIT_OK, "apply failed: " + err.strip()[-400:])
        after = world.snap()
        self.assert_existing_untouched(before, after)
        created = new_entries(before, after)
        new_files = {k for k, v in created.items() if v[0] == "file"}
        new_dirs = {k for k, v in created.items() if v[0] == "dir"}
        planned_files = file_targets(world, plan)
        self.assertEqual(new_files, planned_files, "the new files are exactly the planned add/link files")
        allowed_dirs = folder_targets(world, plan)
        for rel in planned_files:
            allowed_dirs |= parents(rel)
        self.assertEqual(new_dirs - allowed_dirs, set(), "a folder outside the plan was created")
        for rel in new_files:
            self.assertGreater(os.path.getsize(os.path.join(world.tmp, rel)), 0, "an empty file was created")
        result = json.loads(out)
        self.assertEqual(result.get("mode"), "apply")
        self.assertEqual(sorted(result.get("written") or []),
                         sorted(i["id"] for i in writing_items(plan) if i["root"] in ("sb", "setup")))
        self.assert_unchanged(before, after, unchanged_targets(world, world.case["expect"].get("unchanged", [])))
        self.assertEqual(her_digests(before) & {v[1] for k, v in created.items() if v[0] == "file"}, set(),
                         "a new file is a byte copy of one of her files")

    def test_apply_leaves_choices_untouched(self):
        """Items in a choice group are not applied without an explicit choice."""
        world = self.world()
        plan = self.dry_run(world)
        before = world.snap()
        code, out, err = self.apply(world, plan["sha256"])
        self.assertEqual(code, EXIT_OK, err.strip()[-400:])
        after = world.snap()
        for item in plan["items"]:
            if item.get("choice") and item["root"] in ("sb", "setup"):
                with self.subTest(item=item["id"]):
                    rel = world.rel(world.item_path(item))
                    self.assertEqual(rel in after, rel in before, "a choice option was applied: %s" % rel)

    def test_apply_twice_is_refused(self):
        world = self.world()
        plan = self.dry_run(world)
        code, out, err = self.apply(world, plan["sha256"])
        self.assertEqual(code, EXIT_OK, err.strip()[-400:])
        middle = world.snap(dir_mtime=True)
        code, out, err = self.apply(world, plan["sha256"])
        self.assertIn(code, REFUSALS, "a second apply must refuse: the targets exist")
        self.assertEqual(world.snap(dir_mtime=True), middle, "a refused apply wrote something")

    def test_apply_refuses_when_a_target_appeared(self):
        """Between the OK and the apply one planned target appeared: nothing is
        written, the appeared file keeps its bytes."""
        world = self.world()
        plan = self.dry_run(world)
        files = sorted(file_targets(world, plan))
        self.assertTrue(files, "the case plans at least one new file")
        appeared = os.path.join(world.tmp, files[-1])
        os.makedirs(os.path.dirname(appeared), exist_ok=True)
        with open(appeared, "w", encoding="utf-8") as fh:
            fh.write("hers now\n")
        before = world.snap(dir_mtime=True)
        code, out, err = self.apply(world, plan["sha256"])
        self.assertIn(code, REFUSALS)
        self.assertEqual(world.snap(dir_mtime=True), before, "a refused apply wrote something")

    def test_apply_then_dry_run_shows_everything_as_skip(self):
        """After an apply the same dry run proposes no further file writes."""
        world = self.world()
        plan = self.dry_run(world)
        code, out, err = self.apply(world, plan["sha256"])
        self.assertEqual(code, EXIT_OK, err.strip()[-400:])
        again = self.dry_run(world)
        remaining = [i for i in writing_items(again) if i["root"] in ("sb", "setup")]
        self.assertEqual(remaining, [], "applied items must now be skips")
        self.assertNotEqual(again["sha256"], plan["sha256"], "the plan hash changes with the state")


def make_expect_test(key, check):
    def test(self):
        world = self.world()
        before = world.snap()  # before any planner run
        plan = self.dry_run(world)
        if key == "agents_created_before_ok":
            check(self, world, plan, world.case["expect"][key], before)
        else:
            check(self, world, plan, world.case["expect"][key])

    test.__name__ = "test_expect_" + key
    test.__doc__ = "expect.%s of the case file" % key
    return test


def build_case_classes(namespace):
    for path in discover_cases():
        case = load_case(path)
        label = case_label(path)
        name = "Test" + re.sub(r"[^0-9A-Za-z]+", "_", label).title().replace("_", "")
        attrs = {"CASE_PATH": path, "__doc__": label}
        unknown = set(case["expect"]) - set(CaseTests.EXPECT_CHECKS) - {"unchanged"}
        if unknown:
            raise RuntimeError("%s: unknown expect keys %s" % (label, sorted(unknown)))
        for key, check in CaseTests.EXPECT_CHECKS.items():
            if key in case["expect"]:
                attrs["test_expect_" + key] = make_expect_test(key, check)
        namespace[name] = type(name, (CaseTests,), attrs)


build_case_classes(globals())
del CaseTests.EXPECT_CHECKS  # keep the base class out of discovery
CaseTests = None


if __name__ == "__main__":
    unittest.main()
