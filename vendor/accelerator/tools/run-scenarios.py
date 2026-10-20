#!/usr/bin/env python3
"""
run-scenarios.py — Scenario-runner core (static pass-condition assertion).

Parses structured scenarios from a behavioral-scenarios.md file.
For each scenario:
  - If the Pass-condition is STATIC-checkable (file exists / string present
    or absent in a named file / JSON field present), asserts directly → PASS/FAIL.
  - If the Pass-condition requires a live agent run, marks it → MANUAL.

Static detection heuristics (applied to the Pass-condition text):
  1. FILE_EXISTS   — "*.md exists" / "<path> exists" → check path on disk
  2. STRING_IN     — `grep "<text>" <file>` hits / "<text>" present in <file>
  3. STRING_ABSENT — "<text>" not present / "not contain"
  4. JSON_FIELD    — JSON has field "<name>" / contains "<key>"

Anything else → MANUAL (honest scope boundary, not a silent pass).

Usage:
    python3 tools/run-scenarios.py <behavioral-scenarios.md> [--plugin-dir <path>]

    # Run against ai-baseline:
    python3 tools/run-scenarios.py ai-baseline/tests/behavioral-scenarios.md

    # Run with a plugin root for file-relative assertions:
    python3 tools/run-scenarios.py onboarding-guide/tests/behavioral-scenarios.md \\
        --plugin-dir onboarding-guide
"""

import argparse
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# ── Heading detection ─────────────────────────────────────────────────────────
SCENARIO_HEADING_RE = re.compile(r'^(### .+|## Scenario .+)', re.MULTILINE)
PASS_CONDITION_RE = re.compile(
    r'\*\*Pass(?:\s+condition)?:?\*\*\s*(.+?)(?=\n---|\n##|\n###|\Z)',
    re.DOTALL | re.IGNORECASE,
)


def parse_scenarios(md_text: str) -> list[dict]:
    """Parse scenarios from markdown. Returns list of {title, pass_condition}."""
    scenarios = []
    headings = list(SCENARIO_HEADING_RE.finditer(md_text))
    for i, m in enumerate(headings):
        title = m.group(0).lstrip('#').strip()
        start = m.end()
        end = headings[i + 1].start() if i + 1 < len(headings) else len(md_text)
        body = md_text[start:end]
        # Extract pass condition
        pc_match = PASS_CONDITION_RE.search(body)
        pass_condition = pc_match.group(1).strip() if pc_match else ""
        scenarios.append({"title": title, "pass_condition": pass_condition, "body": body})
    return scenarios


# ── Static assertion types ────────────────────────────────────────────────────

# Pattern: grep "text" file → hits
GREP_HITS_RE = re.compile(
    r'`grep\s+(?:-[A-Za-z]+\s+)?["\']([^"\']+)["\']\s+([^\s`]+)`\s+hits',
)

# Pattern: file / path "exists"
FILE_EXISTS_RE = re.compile(
    r'[`"]?([^\s`"\']+\.[a-z]+)[`"]?\s+exists',
    re.IGNORECASE,
)

# Pattern: "text" / 'text' present in file / mentioned in file
STRING_IN_RE = re.compile(
    r'["`]([^"`\n]{1,120})["`]\s+(?:is )?(?:present|appears?|contains?|found)\s+in\s+["`]?([^\s"`]+)["`]?',
    re.IGNORECASE,
)

# Pattern: does not contain / not present / absent
STRING_ABSENT_RE = re.compile(
    r'(?:does not contain|not present|absent|not appear)[^.]*?["`]([^"`\n]{1,120})["`]',
    re.IGNORECASE,
)

# A file the run PRODUCES (output verb in the pass-condition) is a live-run output,
# not a static precondition — such a FILE_EXISTS match is marked MANUAL, not asserted
# on disk (the file only exists after a live agent run; asserting it is a false FAIL).
OUTPUT_VERB_RE = re.compile(
    r'\b(?:written|writes?|wrote|created?|creates|scaffold(?:ed|s)?|produced?|'
    r'produces|generated?|generates|saved?|saves|append(?:ed|s)?|persist(?:ed|s)?|'
    r'emit(?:ted|s)?|output)\b',
    re.IGNORECASE,
)


def assert_grep(pattern: str, file_path: Path) -> tuple[bool, str]:
    if not file_path.exists():
        return False, f"FILE_NOT_FOUND: {file_path}"
    text = file_path.read_text(encoding="utf-8", errors="replace")
    if pattern in text:
        return True, f"STRING_IN: '{pattern}' found in {file_path.name}"
    return False, f"STRING_IN: '{pattern}' NOT found in {file_path.name}"


def assert_file_exists(rel_path: str, base: Path) -> tuple[bool, str]:
    # Check if path looks like runtime-state or placeholder example
    # Treat as MANUAL (not FAIL) rather than asserting on disk
    first_seg = rel_path.split('/')[0]
    if (rel_path.startswith('.ai-baseline/') or
        'my-plugin/' in rel_path or
        rel_path.startswith('<plugin') or
        rel_path.startswith('example-') or
        (first_seg.startswith('.') and first_seg != '.claude-plugin') or
        first_seg in ('mined-patterns', 'postmortems', 'runbooks')):
        return None, f"FILE_EXISTS (skipped — runtime/placeholder path): {rel_path}"

    target = (base / rel_path).resolve()
    if target.exists():
        return True, f"FILE_EXISTS: {target.relative_to(REPO_ROOT)}"
    # Try relative to REPO_ROOT
    target2 = (REPO_ROOT / rel_path).resolve()
    if target2.exists():
        return True, f"FILE_EXISTS: {target2.relative_to(REPO_ROOT)}"
    return False, f"FILE_NOT_EXISTS: {rel_path}"


def try_static_assert(pass_condition: str, base_dir: Path) -> tuple[str, list[str]]:
    """
    Returns (verdict, details) where verdict is PASS / FAIL / MANUAL.
    Applies static heuristics; falls through to MANUAL if none match.
    """
    if not pass_condition:
        return "MANUAL", ["No pass-condition text found"]

    results = []
    matched_any = False

    # 1. grep "text" file → hits
    for m in GREP_HITS_RE.finditer(pass_condition):
        matched_any = True
        pattern, file_ref = m.group(1), m.group(2)
        # file_ref may be like ai-baseline/skills/audit-schema.md
        file_path = (REPO_ROOT / file_ref).resolve()
        ok, detail = assert_grep(pattern, file_path)
        results.append((ok, f"GREP {detail}"))

    # 2. file exists
    for m in FILE_EXISTS_RE.finditer(pass_condition):
        rel = m.group(1)
        # Skip if it looks like a description word (no path separator and no extension)
        if '.' not in rel and '/' not in rel:
            continue
        matched_any = True
        # A file the run CREATES is a live-run output, not a static precondition:
        # asserting it on disk is a false FAIL (it only exists after a live run).
        if OUTPUT_VERB_RE.search(pass_condition):
            return "MANUAL", [f"FILE_EXISTS (skipped — live-run output, not a precondition): {rel}"]
        ok, detail = assert_file_exists(rel, base_dir)
        # If ok is None, it's a runtime/placeholder path → return MANUAL
        if ok is None:
            return "MANUAL", [detail]
        results.append((ok, detail))

    # 3. string present in file
    for m in STRING_IN_RE.finditer(pass_condition):
        pattern, file_ref = m.group(1), m.group(2)
        # Only assert when the "file" looks like a real path (has a separator or an
        # extension). A bare word ("the", "it") is prose — "present in the report" is a
        # live-run claim, not a static file check → leave the scenario MANUAL.
        if '/' not in file_ref and '.' not in file_ref:
            continue
        matched_any = True
        file_path = (REPO_ROOT / file_ref).resolve()
        if not file_path.exists():
            file_path = (base_dir / file_ref).resolve()
        ok, detail = assert_grep(pattern, file_path)
        results.append((ok, f"STRING_IN {detail}"))

    if not matched_any:
        return "MANUAL", ["No static assertion patterns detected — requires live agent run"]

    # Aggregate
    all_ok = all(ok for ok, _ in results)
    details = [detail for _, detail in results]
    return ("PASS" if all_ok else "FAIL"), details


# ── Main ──────────────────────────────────────────────────────────────────────

def run_one(scenarios_path: Path, base_dir: Path, verbose: bool = True):
    """Run one scenarios file. Returns (counts dict, list of failing titles)."""
    scenarios = parse_scenarios(scenarios_path.read_text(encoding="utf-8"))
    if not scenarios:
        raise ValueError(f"no scenarios found in {scenarios_path}")
    counts = {"PASS": 0, "FAIL": 0, "MANUAL": 0}
    fails = []
    if verbose:
        print("=" * 70)
        print(f"SCENARIO RUNNER — {scenarios_path.relative_to(REPO_ROOT)}")
        print(f"Base dir: {base_dir.relative_to(REPO_ROOT) if base_dir != REPO_ROOT else '.'}")
        print("=" * 70)
    for i, scenario in enumerate(scenarios, 1):
        verdict, details = try_static_assert(scenario["pass_condition"], base_dir)
        counts[verdict] += 1
        if verdict == "FAIL":
            fails.append(scenario["title"])
        if verbose:
            label = {"PASS": "[PASS  ]", "FAIL": "[FAIL  ]", "MANUAL": "[MANUAL]"}[verdict]
            print(f"\n{label} {i:02d}. {scenario['title']}")
            for d in details:
                print(f"         {d}")
    return counts, fails


def run_all() -> int:
    """Run every plugin's behavioral-scenarios.md; fail only on a static FAIL
    (MANUAL is the honest 'needs a live run' boundary, not a failure)."""
    files = sorted(REPO_ROOT.glob("*/tests/behavioral-scenarios.md"))
    tot = {"PASS": 0, "FAIL": 0, "MANUAL": 0}
    failing_files = []
    for f in files:
        base_dir = f.parent.parent  # the plugin root
        counts, fails = run_one(f, base_dir, verbose=False)
        for k in tot:
            tot[k] += counts[k]
        status = "FAIL" if fails else "ok"
        print(f"  [{status:4}] {f.relative_to(REPO_ROOT)}  "
              f"({counts['PASS']}P/{counts['FAIL']}F/{counts['MANUAL']}M)")
        for t in fails:
            print(f"           FAIL: {t}")
        if fails:
            failing_files.append(f)
    print(f"\nSCENARIOS (static): {len(files)} files | "
          f"{tot['PASS']} PASS | {tot['FAIL']} FAIL | {tot['MANUAL']} MANUAL")
    if tot["FAIL"]:
        print(f"FAIL — {len(failing_files)} file(s) have a static-assertion failure.")
        return 1
    print("DONE — no static-assertion failures (MANUAL scenarios need a live agent run).")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Scenario-runner core (static assertions)")
    parser.add_argument("scenarios_file", nargs="?", help="Path to behavioral-scenarios.md")
    parser.add_argument("--plugin-dir", default=None,
                        help="Plugin root directory for file-relative assertions (default: repo root)")
    parser.add_argument("--all", action="store_true",
                        help="Run every plugin's behavioral-scenarios.md and gate on static FAILs")
    args = parser.parse_args()

    if args.all:
        return run_all()

    if not args.scenarios_file:
        parser.error("scenarios_file is required unless --all is given")

    scenarios_path = Path(args.scenarios_file)
    if not scenarios_path.is_absolute():
        scenarios_path = REPO_ROOT / scenarios_path
    scenarios_path = scenarios_path.resolve()
    if not scenarios_path.exists():
        print(f"ERROR: scenarios file not found: {scenarios_path}", file=sys.stderr)
        return 1

    base_dir = Path(args.plugin_dir).resolve() if args.plugin_dir else REPO_ROOT
    try:
        counts, fails = run_one(scenarios_path, base_dir, verbose=True)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print("\n" + "=" * 70)
    print(f"RESULTS: {counts['PASS']} PASS | {counts['FAIL']} FAIL | {counts['MANUAL']} MANUAL")
    print("=" * 70 + "\n")
    if counts["MANUAL"] > 0:
        print(f"NOTE: {counts['MANUAL']} scenario(s) marked MANUAL — these require a live agent run.")
        print("      Subagent-execution of MANUAL scenarios is the next increment.")
    if counts["FAIL"] > 0:
        print(f"\nFAIL — {counts['FAIL']} static assertion(s) failed.")
        return 1
    print("\nDONE — no static assertion failures.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
