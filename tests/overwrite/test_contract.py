"""The planner's contract beyond the six fixtures (tools/KIT-PLAN-SPEC.md).

Synthetic setups built in a temp folder: a contradicting memory fact, an
empty setup, the discovered-state JSON input, the text output and the help.
"""

import json
import os
import re
import subprocess
import sys
import unittest

from support import (
    COLLISION_SUFFIX, EXIT_OK, KIT_ROOT, KIT_PLAN, KIT_PLAN_MISSING, HarnessCase, agents_checkpoints,
    fact_slug, items_where, load_case, discover_cases, writing_items,
)

SB = os.path.join(KIT_ROOT, "second-brain", "bin", "sb")
SHA_LINE = re.compile(r"^plan sha256: ([0-9a-f]{64})$", re.MULTILINE)

CONTRADICTION = {
    "synthetic": True,
    "memory": ["never posts on Sundays"],
    "kit_facts": ["posts on Sundays", "posts at most once a day"],
    "expect": {"unchanged": ["never posts on Sundays"]},
}

EMPTY = {"synthetic": True, "expect": {}}

# Her coding agent already has the sizing routine, on a schedule that holds
# HH:MM times but is not a daily summary.
SIZING_TAKEN = {
    "synthetic": True,
    "agents": [{"name": "example-coder", "role": "fixes the school website", "skills": ["example-site-fix"]}],
    "routines": [{"name": "dev-lead-sizing", "schedule": "every 4 hours 08:00-20:00"}],
    "expect": {},
}


def with_routines(*routines):
    return {"synthetic": True, "routines": [{"name": n, "schedule": s} for n, s in routines], "expect": {}}

# Her notes already sit where the kit's template files would go: the kit's
# items become skips and her bytes stay, dry run and apply alike.
KIT_PATHS_TAKEN = {
    "synthetic": True,
    "files": [
        {"path": "ROUTER.md", "front_matter": {}},
        {"path": "dance-school/comms/parent-update-template.md",
         "front_matter": {"channel": "dance-school", "tags": ["dance-school", "comms"]}},
    ],
    "expect": {"unchanged": ["ROUTER.md", "dance-school/comms/parent-update-template.md"]},
}


class HelpAndTextOutputTest(HarnessCase):
    def test_help_names_the_flags(self):
        self.require_planner()
        world = self.world(EMPTY)
        code, out, err = world.run("--help")
        self.assertEqual(code, EXIT_OK, err)
        for flag in ("--dry-run", "--apply", "--approved", "--json", "--state", "--setup-dir", "--home",
                     "--config", "--kit", "--choose"):
            with self.subTest(flag=flag):
                self.assertIn(flag, out)

    def test_text_output_lists_every_checkpoint_and_the_hash(self):
        """The default (text) output names every checkpoint of AGENTS.md and
        ends with the same hash the JSON output carries."""
        world = self.world(EMPTY)
        plan = self.dry_run(world)
        code, out, err = world.run("--dry-run")
        self.assertEqual(code, EXIT_OK, err)
        for cid in agents_checkpoints():
            with self.subTest(checkpoint=cid):
                self.assertRegex(out, r"CHECKPOINT %s\b" % cid)
        match = SHA_LINE.search(out)
        self.assertIsNotNone(match, "no 'plan sha256:' line")
        self.assertEqual(match.group(1), plan["sha256"])

    def test_dry_run_is_the_default(self):
        world = self.world(EMPTY)
        before = world.snap(dir_mtime=True)
        self.require_planner()
        code, out, err = world.run("--json")
        self.assertEqual(code, EXIT_OK, err)
        self.assertEqual(json.loads(out).get("mode"), "dry-run")
        self.assertEqual(world.snap(dir_mtime=True), before)

    def test_text_output_never_prints_absolute_paths(self):
        """Proposals name kit-relative and setup-relative targets only."""
        world = self.world(EMPTY)
        self.require_planner()
        code, out, err = world.run("--dry-run")
        self.assertEqual(code, EXIT_OK, err)
        self.assertNotIn(world.tmp, out)
        self.assertNotIn(KIT_ROOT, out)


class ContradictionTest(HarnessCase):
    """A kit fact that negates one of hers is flagged, never added, never
    written over hers."""

    def test_contradiction_is_reported_not_added(self):
        world = self.world(CONTRADICTION)
        plan = self.dry_run(world)
        reports = items_where(plan, type="report", kind="memory")
        self.assertEqual(len(reports), 1, "one contradiction report")
        report = reports[0]
        self.assertIn("contradict", report["reason"].lower())
        self.assertEqual(report.get("fact"), "posts on Sundays")
        self.assertEqual(report.get("contradicts"), "never posts on Sundays")
        self.assertEqual([i.get("fact") for i in items_where(plan, type="add", kind="memory")],
                         ["posts at most once a day"])

    def test_apply_writes_only_the_new_fact(self):
        world = self.world(CONTRADICTION)
        plan = self.dry_run(world)
        before = world.snap()
        code, out, err = self.apply(world, plan["sha256"])
        self.assertEqual(code, EXIT_OK, err.strip()[-400:])
        after = world.snap()
        self.assert_existing_untouched(before, after)
        memory = sorted(k for k in after if k.startswith("setup/memory/") and k not in before)
        self.assertEqual(memory, ["setup/memory/%s.md" % fact_slug("posts at most once a day")])
        self.assertIn("never-posts-on-sundays.md", "".join(after))


class KitPathsTakenTest(HarnessCase):
    """Her router and one of her notes occupy kit target paths: the planner
    skips them and never writes over them, even with the right hash."""

    TAKEN = ("ROUTER.md", "dance-school/comms/parent-update-template.md", "dance-school/", "dance-school/comms/")

    def test_existing_kit_paths_are_skips(self):
        world = self.world(KIT_PATHS_TAKEN)
        plan = self.dry_run(world)
        for target in self.TAKEN:
            with self.subTest(target=target):
                items = [i for i in items_where(plan, root="sb", target=target) if i["type"] != "report"]
                self.assertEqual([i["type"] for i in items], ["skip"], "one skip item, no add")
        self.assertEqual([i["target"] for i in writing_items(plan) if i["target"] in self.TAKEN], [])

    def test_apply_leaves_her_bytes_and_mtimes(self):
        world = self.world(KIT_PATHS_TAKEN)
        plan = self.dry_run(world)
        before = world.snap()
        code, out, err = self.apply(world, plan["sha256"])
        self.assertEqual(code, EXIT_OK, err.strip()[-400:])
        after = world.snap()
        self.assert_existing_untouched(before, after)
        for rel in ("home/ROUTER.md", "home/dance-school/comms/parent-update-template.md"):
            with self.subTest(path=rel):
                self.assertEqual(after[rel], before[rel])
        self.assertIn("home/dance-school/comms/absence-reply-template.md", after, "the missing sibling note was added")


class EmptySetupTest(HarnessCase):
    """Nothing of hers: every kit item is a plain add and the result passes
    `sb --doctor` on the new second brain."""

    def test_everything_is_add_or_skip(self):
        world = self.world(EMPTY)
        plan = self.dry_run(world)
        self.assert_plan_shape(plan)
        for item in plan["items"]:
            with self.subTest(item=item["id"]):
                self.assertIn(item["type"], ("add", "skip", "report"), "nothing to extend, merge or link")
                self.assertNotIn("choice", item, "no collision, no choice")

    def test_kit_items_are_planned(self):
        world = self.world(EMPTY)
        plan = self.dry_run(world)
        for skill in ("sb-lookup", "content-calendar-planner", "comms-template-writer"):
            with self.subTest(skill=skill):
                self.assertEqual(len(items_where(plan, type="add", kind="skill", name=skill, checkpoint="4")), 1)
        routines = items_where(plan, type="add", kind="routine", name="morning-brief")
        self.assertEqual(len(routines), 1)
        self.assertEqual(routines[0]["checkpoint"], "5a")
        self.assertEqual(routines[0].get("enabled"), False, "created disabled")
        agents = items_where(plan, type="add", kind="agent", name="dev-lead")
        self.assertEqual(len(agents), 1)
        self.assertEqual(agents[0]["checkpoint"], "8a")
        self.assertEqual(len(items_where(plan, type="add", kind="router")), 1)
        folders = {i["target"] for i in items_where(plan, type="add", kind="folder", root="sb")}
        for folder in ("dance-school/marketing/campaigns/", "dance-school/comms/", "other-activities/"):
            with self.subTest(folder=folder):
                self.assertIn(folder, folders)

    def test_enable_steps_are_separate_checkpoints(self):
        """Enabling the routine (5b), the sizing routine (8b) and the runner
        (9b) are their own items and never file writes."""
        world = self.world(EMPTY)
        plan = self.dry_run(world)
        for cid in ("5b", "8b", "9b"):
            with self.subTest(checkpoint=cid):
                items = items_where(plan, checkpoint=cid)
                self.assertTrue(items, "an item for checkpoint %s" % cid)
                for item in items:
                    self.assertNotIn(item["type"], ("add", "link"), "enabling is not a file write")

    def test_applied_second_brain_passes_doctor(self):
        world = self.world(EMPTY)
        plan = self.dry_run(world)
        code, out, err = self.apply(world, plan["sha256"])
        self.assertEqual(code, EXIT_OK, err.strip()[-400:])
        proc = subprocess.run(
            [sys.executable, SB, "--doctor", "--config", world.config_path],
            cwd=world.tmp, env=world.env(), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            universal_newlines=True, timeout=120,
        )
        self.assertEqual(proc.returncode, 0, "sb --doctor on the new second brain:\n" + proc.stdout)


class SizingRoutineTakenTest(HarnessCase):
    """She already has `dev-lead-sizing`: the 8b enable step names her
    routine, and its timed schedule does not make it the morning brief."""

    def test_enable_report_names_her_routine(self):
        world = self.world(SIZING_TAKEN)
        plan = self.dry_run(world)
        self.assertEqual([i["target"] for i in items_where(plan, type="skip", kind="routine", checkpoint="8a")],
                         ["routines/dev-lead-sizing.md"])
        self.assertEqual([i["target"] for i in items_where(plan, type="report", kind="routine", checkpoint="8b")],
                         ["routines/dev-lead-sizing.md"])
        self.assertEqual([i["id"] for i in plan["items"] if "dev-lead-sizing" + COLLISION_SUFFIX in i["target"]],
                         [], "nothing names a suffixed sizing routine she does not have")

    def test_timed_sizing_routine_is_not_the_brief_target(self):
        world = self.world(SIZING_TAKEN)
        plan = self.dry_run(world)
        self.assertEqual([i.get("into") for i in items_where(plan, type="merge", kind="routine")], [])
        self.assertEqual([i["name"] for i in items_where(plan, type="add", kind="routine", checkpoint="5a")],
                         ["morning-brief"])


class MorningBriefTargetTest(HarnessCase):
    """The routine the morning brief merges into: `routines.morning_brief.
    merge_into` first, then a routine whose name or schedule says daily,
    morning, brief or summary; never one named `*sizing*` or `*keep-alive*`,
    and a bare HH:MM time is not enough."""

    def merge_targets(self, case):
        self.setUp()  # a fresh world per subTest: routines of the last one must not stay behind
        plan = self.dry_run(self.world(case))
        return ([i.get("into") for i in items_where(plan, type="merge", kind="routine")],
                [i["name"] for i in items_where(plan, type="add", kind="routine", checkpoint="5a")])

    def test_merge_into_comes_first(self):
        self.CONFIG_EXTRA = {"routines": {"morning_brief": {"enabled": False, "name": "morning-brief",
                                                            "merge_into": "example-notes", "time": "07:30"}}}
        case = with_routines(("example-daily-summary", "08:00 daily"), ("example-notes", "weekdays"))
        self.assertEqual(self.merge_targets(case), (["example-notes"], []))

    def test_a_brief_word_in_the_name_or_schedule_is_the_target(self):
        for word in ("daily", "morning", "brief", "summary"):
            for name, schedule in (("example-%s-notes" % word, "weekdays"), ("example-notes", "weekdays, " + word)):
                with self.subTest(name=name, schedule=schedule):
                    self.assertEqual(self.merge_targets(with_routines((name, schedule))), ([name], []))

    def test_a_bare_time_is_not_a_daily_routine(self):
        case = with_routines(("example-backup", "02:00"), ("example-report", "Mondays 18:30"))
        self.assertEqual(self.merge_targets(case), ([], ["morning-brief"]))

    def test_sizing_and_keep_alive_routines_are_never_the_target(self):
        for name in ("example-daily-sizing", "example-morning-keep-alive"):
            with self.subTest(routine=name):
                self.assertEqual(self.merge_targets(with_routines((name, "daily 08:00"))), ([], ["morning-brief"]))

    def test_an_excluded_routine_does_not_hide_a_later_brief(self):
        case = with_routines(("example-a-daily-sizing", "daily"), ("example-b-summary", "weekdays"))
        self.assertEqual(self.merge_targets(case), (["example-b-summary"], []))


def case_named(fragment):
    paths = [p for p in discover_cases() if fragment in os.path.basename(p)]
    if len(paths) != 1:
        raise unittest.SkipTest("no single case named *%s* in the case folder" % fragment)
    return paths[0]


class ChoiceTest(HarnessCase):
    """`--choose <group>=<item id>` applies one option of a choice and only
    its writing items; a bad choice is a usage error that writes nothing."""

    def choice_items(self, plan, group):
        items = [i for i in plan["items"] if i.get("choice") == group]
        self.assertGreaterEqual(len(items), 2, "a choice group with two options")
        return items

    def test_choosing_the_add_option_writes_that_skill_only(self):
        world = self.world(case_path=case_named("case-03"))
        plan = self.dry_run(world)
        items = self.choice_items(plan, "skill:sb-lookup")
        add = [i for i in items if i["type"] == "add"][0]
        before = world.snap()
        code, out, err = self.apply(world, plan["sha256"], "--choose", "skill:sb-lookup=" + add["id"])
        self.assertEqual(code, EXIT_OK, err.strip()[-400:])
        after = world.snap()
        self.assert_existing_untouched(before, after)
        self.assertIn(add["id"], json.loads(out)["written"])
        self.assertIn("setup/skills/sb-lookup-kit/SKILL.md", after)
        with open(os.path.join(world.setup, "skills", "sb-lookup-kit", "SKILL.md"), encoding="utf-8") as fh:
            self.assertIn("name: sb-lookup-kit", fh.read())

    def test_choosing_the_extend_option_writes_nothing_for_it(self):
        world = self.world(case_path=case_named("case-03"))
        plan = self.dry_run(world)
        items = self.choice_items(plan, "skill:sb-lookup")
        extend = [i for i in items if i["type"] == "extend"][0]
        before = world.snap()
        code, out, err = self.apply(world, plan["sha256"], "--choose", "skill:sb-lookup=" + extend["id"])
        self.assertEqual(code, EXIT_OK, err.strip()[-400:])
        after = world.snap()
        self.assert_existing_untouched(before, after)
        new_skills = [k for k in after if k.startswith("setup/skills/sb-lookup") and k not in before]
        self.assertEqual(new_skills, [], "an extend is performed by her Grok Bot, never by the planner")
        self.assertEqual(after["setup/skills/sb-lookup/SKILL.md"], before["setup/skills/sb-lookup/SKILL.md"])
        self.assertNotIn(extend["id"], json.loads(out)["written"])

    def test_choosing_create_writes_the_agent_and_its_sizing_routine(self):
        world = self.world(case_path=case_named("case-05"))
        plan = self.dry_run(world)
        items = self.choice_items(plan, "agent:dev-lead")
        create = [i for i in items if i["type"] == "add" and i["kind"] == "agent"][0]
        before = world.snap()
        code, out, err = self.apply(world, plan["sha256"], "--choose", "agent:dev-lead=" + create["id"])
        self.assertEqual(code, EXIT_OK, err.strip()[-400:])
        after = world.snap()
        self.assert_existing_untouched(before, after)
        self.assertIn("setup/agents/dev-lead/AGENT.md", after)
        self.assertIn("setup/routines/dev-lead-sizing.md", after)
        written = json.loads(out)["written"]
        self.assertIn(create["id"], written)
        for item in items:
            if item.get("option") == create["id"] and item["type"] in ("add", "link"):
                self.assertIn(item["id"], written, "the items of the chosen option are applied with it")
        self.assertEqual([i for i in after if i.startswith("setup/agents/example-coder/") and after[i] != before[i]], [])

    def test_unknown_choice_is_a_usage_error(self):
        world = self.world(case_path=case_named("case-03"))
        plan = self.dry_run(world)
        before = world.snap(dir_mtime=True)
        code, out, err = self.apply(world, plan["sha256"], "--choose", "skill:sb-lookup=skill.add.nope")
        self.assertEqual(code, 2)
        self.assertEqual(world.snap(dir_mtime=True), before)
        code, out, err = self.apply(world, plan["sha256"], "--choose", "no-such-group=skill.add.nope")
        self.assertEqual(code, 2)
        self.assertEqual(world.snap(dir_mtime=True), before)

    def test_choice_options_name_their_option_items(self):
        """Items that only make sense with one option carry `option` = that
        option's id, so `--choose` knows what to apply with it."""
        world = self.world(case_path=case_named("case-05"))
        plan = self.dry_run(world)
        items = self.choice_items(plan, "agent:dev-lead")
        options = {i["id"] for i in items if "option" not in i}
        self.assertEqual(len(options), 2, "two options, the rest are their dependants")
        for item in items:
            if "option" in item:
                self.assertIn(item["option"], options)


class StateInputTest(HarnessCase):
    """A discovered-state JSON with the fixture keys gives the same plan as
    the case YAML."""

    def test_json_state_matches_yaml_state(self):
        path = discover_cases()[0]
        case = load_case(path)
        yaml_world = self.world(case_path=path)
        yaml_plan = self.dry_run(yaml_world)
        json_world = self.world(case)  # written as state.json
        json_plan = self.dry_run(json_world)
        strip = lambda items: [{k: v for k, v in i.items()} for i in items]
        self.assertEqual(strip(json_plan["items"]), strip(yaml_plan["items"]))

    def test_missing_state_file_is_a_usage_error(self):
        world = self.world(EMPTY)
        self.require_planner()
        os.remove(world.state_path)
        before = world.snap(dir_mtime=True)
        code, out, err = world.run("--dry-run", "--json")
        self.assertEqual(code, 2)
        self.assertEqual(world.snap(dir_mtime=True), before)

    def test_fresh_mode_refuses_a_non_empty_setup(self):
        """`existing_setup.mode: fresh` is for an empty setup only."""
        path = discover_cases()[0]
        self.CONFIG_EXTRA = {"existing_setup": {"mode": "fresh"}}
        world = self.world(case_path=path)
        self.require_planner()
        before = world.snap(dir_mtime=True)
        code, out, err = world.run("--dry-run", "--json")
        self.assertEqual(code, 2)
        self.assertEqual(world.snap(dir_mtime=True), before)


if __name__ == "__main__":
    unittest.main()
