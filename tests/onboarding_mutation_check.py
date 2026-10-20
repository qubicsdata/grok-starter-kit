#!/usr/bin/env python3
"""Dev check for tests/test_onboarding.py: break the onboarding docs one way
at a time in a temporary copy of the kit and confirm the suite goes red.

    python3 tests/onboarding_mutation_check.py [--only LABEL ...]

Prints `KILLED <label>` or `SURVIVED <label>` per mutant; exit 0 when every
mutant is killed, 1 when one survives or a mutation no longer applies (update
MUTANTS after changing the docs). The real kit is never touched. Stdlib only.
"""

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AGENTS = "AGENTS.md"
PARAMETERS = "PARAMETERS.md"
CHECKLIST = os.path.join("onboarding", "setup-checklist.md")
SKILL = os.path.join("grok-skills", "sb-lookup", "SKILL.md")
BRIEF = os.path.join("routines", "morning-brief.md")
NOTE = os.path.join("second-brain", "other-activities", "admin", "activity-notes-example.md")


def replace_once(rel, old, new):
    """A mutation: replace exactly one occurrence of `old` in `rel`."""
    def apply(kit):
        path = os.path.join(kit, rel)
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        if text.count(old) < 1:
            raise ValueError("pattern not found in %s" % rel)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text.replace(old, new, 1))
    return apply


def move_write_before_checkpoint(kit):
    """Phase 3: put its `After your OK:` step before `CHECKPOINT 3`."""
    path = os.path.join(kit, AGENTS)
    with open(path, encoding="utf-8") as fh:
        lines = fh.read().splitlines(True)
    phase = [i for i, l in enumerate(lines) if l.startswith("## Phase 3:")][0]
    checkpoint = [i for i in range(phase, len(lines)) if "**CHECKPOINT 3:**" in lines[i]][0]
    write = [i for i in range(checkpoint, len(lines)) if lines[i].startswith("- After your OK:")][0]
    line = lines.pop(write)
    lines.insert(checkpoint, line)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("".join(lines))


MUTANTS = [
    ("write-before-checkpoint", move_write_before_checkpoint),
    ("duplicate-checkpoint-id", replace_once(AGENTS, "**CHECKPOINT 4:**", "**CHECKPOINT 3:**")),
    ("checkpoint-out-of-order", replace_once(AGENTS, "**CHECKPOINT 6:**", "**CHECKPOINT 11:**")),
    ("unclassified-step", replace_once(AGENTS, "- Show: the whole file in chat", "- Install: the whole file in chat")),
    ("runner-enabled-at-9a", replace_once(AGENTS, "- After OK 9a: write the config file with `runner.enabled: false`.",
                                          "- After OK 9a: write the config file with `runner.enabled: true`.")),
    ("no-9b-step", replace_once(AGENTS, "- After OK 9b: set", "- After OK 9a: set")),
    ("terms-notice-after-9a", replace_once(AGENTS, "- Show: `runner/TERMS-NOTICE.md`", "- Show: the runner terms")),
    ("no-planner", replace_once(AGENTS, "python3 tools/kit_plan.py --dry-run", "the planner")),
    ("unknown-key-in-agents", replace_once(AGENTS, "`second_brain.home`", "`second_brain.notes_home`")),
    ("file-key-not-excused", replace_once(AGENTS, "`kit.collision_suffix` is applied", "`kit.collision.suffix` is applied")),
    ("ripgrep-required", replace_once(AGENTS, "ripgrep is optional:", "ripgrep is required:")),
    ("ripgrep-prerequisite-box", replace_once(CHECKLIST, "- [ ] git.", "- [ ] ripgrep.\n- [ ] git.")),
    ("privacy-dropped", replace_once(AGENTS, "mostly minors", "mostly adults")),
    ("parameters-row-removed", replace_once(PARAMETERS, "| `accelerator.enabled` |", "| `accelerator.plugins` |")),
    ("parameters-unknown-key", replace_once(PARAMETERS, "| `kit.home` (KIT_HOME) |", "| `kit.root` (KIT_HOME) |")),
    ("parameters-sibling-unknown", replace_once(PARAMETERS, "`kit.author_name` / `author_email`", "`kit.author_name` / `author_mail`")),
    ("parameters-duplicate-key", replace_once(PARAMETERS, "| `experiments` |",
                                              "| `usage.probe_unset_env` | empty | `runner/DESIGN.md` | add-only-if-missing | |\n"
                                              "| `experiments` |")),
    ("parameters-job-id-note", replace_once(PARAMETERS, "| keep your own routes if you have them |",
                                            "| keep your own routes if you have them (KIT-X9-1) |")),
    ("skill-name-mismatch", replace_once(SKILL, "name: sb-lookup", "name: sb-search")),
    ("skill-no-front-matter", replace_once(SKILL, "---\nname:", "name:")),
    ("routine-key-missing", replace_once(BRIEF, "`routines.morning_brief.weekdays_only`", "`routines.morning_brief.weekdays`")),
    ("template-note-untagged", replace_once(NOTE, 'channel: "other-activities"', 'channel: "dance-school"')),
    ("conflict-row-dropped", replace_once(AGENTS, "| Duplicate memory fact |", "| Duplicate fact |")),
]


def run_suite(kit):
    env = dict(os.environ)
    env["KIT_ONBOARDING_ROOT"] = kit
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        [sys.executable, "-m", "unittest", "tests.test_onboarding"],
        cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        universal_newlines=True, timeout=600,
    )
    failing = sorted(set(re.findall(r"^(?:FAIL|ERROR): (test_\w+)", proc.stdout, re.MULTILINE)))
    return proc.returncode, failing


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--only", nargs="*", metavar="LABEL")
    args = parser.parse_args(argv)
    survived = 0
    for label, mutate in MUTANTS:
        if args.only and label not in args.only:
            continue
        tmp = tempfile.mkdtemp(prefix="onboarding-mutant-")
        try:
            kit = os.path.join(tmp, "kit")
            shutil.copytree(ROOT, kit, ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"))
            try:
                mutate(kit)
            except ValueError as exc:
                print("STALE %s (%s)" % (label, exc))
                survived += 1
                continue
            code, failing = run_suite(kit)
            if code != 0 and failing:
                print("KILLED %s (%d failing tests: %s)" % (label, len(failing), ", ".join(failing)))
            else:
                print("SURVIVED %s" % label)
                survived += 1
        finally:
            shutil.rmtree(tmp, True)
    return 1 if survived else 0


if __name__ == "__main__":
    sys.exit(main())
