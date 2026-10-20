#!/usr/bin/env python3
"""Dev check: the overwrite harness has teeth.

    python3 tests/overwrite/harness_check.py [-v]

Copies the kit to a temp folder, drops a stub `tools/kit_plan.py` in the copy
and runs the harness against it (KIT_OVERWRITE_KIT). Three stubs:

  empty       a well-formed empty plan; apply writes nothing. Expected: no test
              ERRORs (every harness code path runs), the "writes nothing" tests
              pass, every positive expect test fails (zero-count expectations
              are satisfied by an empty plan, by design).
  toucher     the dry run rewrites every file of hers with identical bytes.
              Expected: the "writes nothing" test fails for every case (the
              mtime snapshot catches a silent rewrite).
  creator     the dry run creates an agent file. Expected: "writes nothing"
              fails for every case and case-05's agents_created_before_ok fails.

Then nine mutants of the real tools/kit_plan.py (one source edit each, in the
copy), with the tests that must go red:

  overwrite   the planner no longer sees existing targets (plan and apply)
              and opens files for writing. Expected: both KitPathsTakenTest
              tests fail (her router and note at kit paths are listed as adds
              and rewritten). The six cases stay green on purpose: none of
              them keeps a file at a kit target path, and the setup-side
              items (skills, routines, agents, memory) are guarded by name
              detection, so a second apply or an appeared target still
              changes the plan hash and refuses with exit 3.
  no-sha      apply no longer compares --approved with the plan hash.
              Expected: every case's test_apply_with_wrong_sha_is_refused fails.
  no-suffix   the collision suffix is dropped. Expected: case-03's
              test_expect_proposals fails (no `sb-lookup-kit` add).
  dup-memory  a duplicate memory fact is added instead of skipped. Expected:
              case-04's test_expect_duplicates_added fails.
  sizing-report    the 8b enable report names a suffixed sizing routine when
              she has hers. Expected: SizingRoutineTakenTest's report test fails.
  bare-time   any HH:MM schedule makes a routine the morning-brief target,
              before the sizing / keep-alive exclusion (the old rule).
              Expected: her timed sizing routine and a bare-time routine are
              proposed as merge targets (two tests fail).
  no-exclude  `*sizing*` / `*keep-alive*` routines are no longer excluded.
              Expected: both exclusion tests of MorningBriefTargetTest fail.
  no-brief-word    a brief word in the name or schedule no longer counts.
              Expected: the brief-word test and case-01's proposals fail.
  merge-into-last  a brief-like routine wins over routines.morning_brief.
              merge_into. Expected: test_merge_into_comes_first fails.

Prints KILLED <label> or SURVIVED <label> per stub and mutant; exit 0 only
when every one behaves as expected. `--only LABEL ...` restricts the run.
Not a CI step. The real kit is never touched.
"""

import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
KIT_ROOT = os.path.dirname(os.path.dirname(HERE))

STUB = r'''#!/usr/bin/env python3
"""Stub planner for tests/overwrite/harness_check.py (never shipped)."""
import argparse, hashlib, json, os, re, sys
BEHAVIOUR = %(behaviour)r

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--apply", action="store_true")
    p.add_argument("--approved")
    p.add_argument("--json", action="store_true")
    p.add_argument("--choose", action="append")
    for flag in ("--kit", "--config", "--state", "--setup-dir", "--home"):
        p.add_argument(flag)
    a = p.parse_args()
    if a.dry_run and a.apply:
        return 2
    if a.apply and not a.approved:
        return 2
    with open(os.path.join(a.kit, "AGENTS.md"), encoding="utf-8") as fh:
        checkpoints = re.findall(r"\*\*CHECKPOINT (\d+[a-z]?)", fh.read())
    items = []
    sha = hashlib.sha256(json.dumps(items, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    if a.apply:
        if a.approved != sha:
            return 3
        print(json.dumps({"mode": "apply", "written": []}))
        return 0
    if BEHAVIOUR == "toucher":
        for root in (a.setup_dir, a.home):
            for dirpath, _, names in os.walk(root):
                for name in names:
                    path = os.path.join(dirpath, name)
                    with open(path, "rb") as fh:
                        data = fh.read()
                    with open(path, "wb") as fh:
                        fh.write(data)
    if BEHAVIOUR == "creator":
        path = os.path.join(a.setup_dir, "agents", "sneaky", "AGENT.md")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as fh:
            fh.write("# sneaky\n")
    plan = {"kit_plan": 1, "mode": "dry-run", "items": items, "checkpoints": checkpoints, "sha256": sha}
    if a.json:
        print(json.dumps(plan))
    else:
        for cid in checkpoints:
            print("CHECKPOINT %%s: nothing" %% cid)
        print("plan sha256: " + sha)
    return 0

if __name__ == "__main__":
    sys.exit(main())
'''

STUBS = ("empty", "toucher", "creator")

# label -> [(old source text, new source text)], each old text occurring
# exactly once in tools/kit_plan.py.
MUTANTS = {
    "overwrite": [
        ('        return os.path.lexists(os.path.join(self.root_path(root), target.rstrip("/")))\n',
         "        return False\n"),
        ("            if os.path.lexists(self.target_path(item)):\n                return EXIT_TARGET_EXISTS, []\n",
         "            if False:\n                return EXIT_TARGET_EXISTS, []\n"),
        ('with open(path, "x", encoding="utf-8", newline="") as fh:',
         'with open(path, "w", encoding="utf-8", newline="") as fh:'),
        ("                os.makedirs(path)\n", "                os.makedirs(path, exist_ok=True)\n"),
    ],
    "no-sha": [
        ('        if args.approved != plan["sha256"]:\n', "        if False:\n"),
    ],
    "no-suffix": [
        ('        self.suffix = str(cfg(self.config, "kit", "collision_suffix", default=DEFAULT_SUFFIX))\n',
         '        self.suffix = ""\n'),
    ],
    "dup-memory": [
        ("            if tokens in hers:\n", "            if False:\n"),
        ('            elif self.exists("setup", target):\n', "            elif False:\n"),
    ],
    "sizing-report": [
        ("        sizing = SIZING_ROUTINE\n",
         "        sizing = free_name(SIZING_ROUTINE, set(self.existing.routines), self.suffix)\n"),
    ],
    "bare-time": [  # the old rule: a time wins before any exclusion is looked at
        ("    if any(fnmatch.fnmatchcase(name.lower(), g) for g in NOT_BRIEF_GLOBS):\n",
         '    if re.search(r"\\b\\d{1,2}:\\d{2}\\b", str(schedule or "")):\n        return True\n'
         "    if any(fnmatch.fnmatchcase(name.lower(), g) for g in NOT_BRIEF_GLOBS):\n"),
    ],
    "no-exclude": [
        ("    if any(fnmatch.fnmatchcase(name.lower(), g) for g in NOT_BRIEF_GLOBS):\n        return False\n", ""),
    ],
    "no-brief-word": [
        ("        if token.startswith(BRIEF_WORDS):\n", "        if False:\n"),
    ],
    "merge-into-last": [
        ("        target_routine = merge_into if merge_into in routines else (daily[0] if daily else None)\n",
         "        target_routine = daily[0] if daily else (merge_into if merge_into in routines else None)\n"),
    ],
}


def mutate(kit, label):
    path = os.path.join(kit, "tools", "kit_plan.py")
    with open(path, encoding="utf-8") as fh:
        source = fh.read()
    for old, new in MUTANTS[label]:
        if source.count(old) != 1:
            raise RuntimeError("%s: the mutant's anchor is not in tools/kit_plan.py exactly once" % label)
        source = source.replace(old, new)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(source)


# `test_x (mod.Cls.test_x) ... ok`, or with a docstring line in between:
# `test_x (mod.Cls.test_x)\nDocstring ... ok`. Python 3.11+ ids end with the
# method name; older ones with the class.
RESULT_RE = re.compile(r"^(test_\w+) \(([^)]+)\)\n?[^\n]*? \.\.\. (ok|FAIL|ERROR|skipped)", re.MULTILINE)


HEADER_RE = re.compile(r"^(FAIL|ERROR): (test_\w+) \(([^)]+)\)", re.MULTILINE)


def class_of(test_id, name):
    parts = test_id.split(".")
    return parts[-2] if parts[-1] == name and len(parts) > 1 else parts[-1]


def run_harness(kit_copy):
    env = dict(os.environ)
    env["KIT_OVERWRITE_KIT"] = kit_copy
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        [sys.executable, "-m", "unittest", "discover", "-s", HERE, "-p", "test_*.py", "-v"],
        cwd=kit_copy, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        universal_newlines=True, timeout=1800,
    )
    results = {}
    for name, test_id, status in RESULT_RE.findall(proc.stdout):
        results[(class_of(test_id, name), name)] = status
    # A test whose failures come from subTests prints no inline status; its
    # `FAIL:` / `ERROR:` headers in the report tell.
    for status, name, test_id in HEADER_RE.findall(proc.stdout):
        key = (class_of(test_id, name), name)
        if results.get(key) != "ERROR":
            results[key] = status
    return results, proc.stdout


def expect(results, pred, status, label, problems):
    picked = [k for k in results if pred(k)]
    if not picked:
        problems.append("%s: no matching tests" % label)
    for key in picked:
        if results[key] != status:
            problems.append("%s: %s.%s is %s, expected %s" % (label, key[0], key[1], results[key], status))


def check(behaviour, verbose):
    tmp = tempfile.mkdtemp(prefix="kit-harness-check-")
    try:
        kit = os.path.join(tmp, "kit")
        shutil.copytree(KIT_ROOT, kit, ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"))
        if behaviour in STUBS:
            with open(os.path.join(kit, "tools", "kit_plan.py"), "w", encoding="utf-8") as fh:
                fh.write(STUB % {"behaviour": behaviour})
        else:
            mutate(kit, behaviour)
        results, output = run_harness(kit)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    problems = []
    if not results:
        problems.append("no test results parsed")
    errors = [k for k, v in results.items() if v == "ERROR"]
    if errors:
        problems.append("ERROR in %d tests (a harness bug, not a planner finding): %s"
                        % (len(errors), ", ".join("%s.%s" % k for k in sorted(errors)[:5])))
    is_case = lambda k: k[0].startswith("TestCase")
    writes_nothing = lambda k: is_case(k) and k[1] == "test_dry_run_writes_nothing"
    if behaviour == "empty":
        expect(results, writes_nothing, "ok", "empty/writes_nothing", problems)
        expect(results, lambda k: is_case(k) and k[1] == "test_dry_run_plan_shape", "ok", "empty/plan_shape", problems)
        # Positive expectations fail on an empty plan; zero-count ones
        # (routines_created: 0, copies: 0, agents_created_before_ok: 0) are
        # satisfied by doing nothing, which is exactly what they guard.
        positive = ("test_expect_proposals", "test_expect_link_notes", "test_expect_added",
                    "test_expect_duplicates_added", "test_expect_doctor_findings")
        expect(results, lambda k: is_case(k) and k[1] in positive, "FAIL", "empty/expect", problems)
        expect(results, lambda k: k[1] == "test_kit_items_are_planned", "FAIL", "empty/kit-items", problems)
        expect(results, lambda k: k[1] == "test_apply_without_approval_is_refused", "ok", "empty/no-approval", problems)
        expect(results, lambda k: k[1] == "test_apply_with_wrong_sha_is_refused", "ok", "empty/wrong-sha", problems)
    elif behaviour == "toucher":
        expect(results, writes_nothing, "FAIL", "toucher/writes_nothing", problems)
        expect(results, lambda k: is_case(k) and k[1] == "test_dry_run_keeps_her_things_unchanged", "FAIL",
               "toucher/unchanged", problems)
    elif behaviour == "creator":
        expect(results, writes_nothing, "FAIL", "creator/writes_nothing", problems)
        expect(results, lambda k: k[0] == "TestCase05HasCodingAgent" and k[1] == "test_expect_agents_created_before_ok",
               "FAIL", "creator/case-05", problems)
    elif behaviour == "overwrite":
        expect(results, lambda k: k[0] == "KitPathsTakenTest", "FAIL", "overwrite/her-files-at-kit-paths", problems)
        expect(results, writes_nothing, "ok", "overwrite/dry-run-still-clean", problems)
    elif behaviour == "no-sha":
        expect(results, lambda k: is_case(k) and k[1] == "test_apply_with_wrong_sha_is_refused", "FAIL",
               "no-sha/wrong-sha", problems)
    elif behaviour == "no-suffix":
        expect(results, lambda k: k[0] == "TestCase03SkillNameClash" and k[1] == "test_expect_proposals", "FAIL",
               "no-suffix/case-03", problems)
    elif behaviour == "dup-memory":
        expect(results, lambda k: k[0] == "TestCase04DuplicateMemory" and k[1] == "test_expect_duplicates_added",
               "FAIL", "dup-memory/case-04", problems)
        expect(results, lambda k: k[0] == "TestCase04DuplicateMemory" and k[1] == "test_dry_run_never_targets_existing",
               "FAIL", "dup-memory/targets-existing", problems)
    elif behaviour == "sizing-report":
        expect(results, lambda k: k == ("SizingRoutineTakenTest", "test_enable_report_names_her_routine"), "FAIL",
               "sizing-report/8b", problems)
    elif behaviour == "bare-time":
        expect(results, lambda k: k in (("SizingRoutineTakenTest", "test_timed_sizing_routine_is_not_the_brief_target"),
                                        ("MorningBriefTargetTest", "test_a_bare_time_is_not_a_daily_routine")),
               "FAIL", "bare-time/5a", problems)
    elif behaviour == "no-exclude":
        expect(results, lambda k: k[0] == "MorningBriefTargetTest" and k[1] in (
            "test_sizing_and_keep_alive_routines_are_never_the_target",
            "test_an_excluded_routine_does_not_hide_a_later_brief"), "FAIL", "no-exclude/5a", problems)
    elif behaviour == "no-brief-word":
        expect(results, lambda k: k == ("MorningBriefTargetTest", "test_a_brief_word_in_the_name_or_schedule_is_the_target"),
               "FAIL", "no-brief-word/5a", problems)
        expect(results, lambda k: k == ("TestCase01HasMorningBrief", "test_expect_proposals"), "FAIL",
               "no-brief-word/case-01", problems)
    elif behaviour == "merge-into-last":
        expect(results, lambda k: k == ("MorningBriefTargetTest", "test_merge_into_comes_first"), "FAIL",
               "merge-into-last/5a", problems)
    if verbose and problems:
        print(output)
    return problems


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    verbose = "-v" in argv
    only = [a for a in argv if a != "-v" and a != "--only"]
    labels = STUBS + tuple(MUTANTS)
    unknown = [a for a in only if a not in labels]
    if unknown:
        print("unknown label(s): %s (known: %s)" % (", ".join(unknown), ", ".join(labels)))
        return 2
    failed = False
    for behaviour in (only or labels):
        problems = check(behaviour, verbose)
        if problems:
            failed = True
            print("SURVIVED %s" % behaviour)
            for p in problems:
                print("  " + p)
        else:
            print("KILLED %s" % behaviour)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
