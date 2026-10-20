#!/usr/bin/env python3
"""
check-calibration.py — Reviewer calibration checker.

Runs static pitfall checks against two fixtures:
  - tools/calibration/clean-plugin/  → must produce 0 findings (false-positive test)
  - tools/calibration/buggy-plugin/  → must produce ≥1 finding (true-positive test)

Checks applied (subset of PIT-1..PIT-11 that are statically checkable):
  PIT-1: authored agents must import baseline-enforcer
  PIT-2: no [$ARGUMENTS] in any agent/skill/command file
  PIT-6: plugin.json must not contain phantom fields

Exits non-zero if:
  - clean fixture has ≥1 finding (false positive)
  - buggy fixture has 0 findings (missed seeded defect)

Usage:
    python3 tools/check-calibration.py
"""

import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

CALIBRATION_DIR = REPO_ROOT / "tools" / "calibration"

ALLOWED_PLUGIN_JSON_FIELDS = {
    "name", "version", "description", "category", "author",
    "keywords", "requires", "kind", "commands", "skills", "agents",
    "schema_version", "readme", "homepage", "license",
}

# Agents exempt from baseline-enforcer import (spec-enrichers + audit-trail copies)
EXEMPT_AGENT_NAMES = {"spec-enricher", "audit-trail-agent"}


def check_pit1_baseline_import(plugin_dir: Path) -> list[str]:
    """PIT-1: Every authored agent must import baseline-enforcer."""
    findings = []
    agents_dir = plugin_dir / "agents"
    if not agents_dir.exists():
        return findings
    for agent_file in sorted(agents_dir.glob("*.md")):
        if agent_file.stem in EXEMPT_AGENT_NAMES:
            continue
        text = agent_file.read_text(encoding="utf-8")
        if "baseline-enforcer" not in text:
            findings.append(
                f"PIT-1: {agent_file.name} does not import baseline-enforcer "
                f"(missing 'Import the baseline-enforcer skill...' line)"
            )
    return findings


def check_pit2_arguments_brackets(plugin_dir: Path) -> list[str]:
    """PIT-2: No [$ARGUMENTS] in any agent/skill/command file."""
    findings = []
    for subdir in ("agents", "skills", "commands"):
        d = plugin_dir / subdir
        if not d.exists():
            continue
        for f in sorted(d.rglob("*.md")):
            text = f.read_text(encoding="utf-8")
            count = text.count("[$ARGUMENTS]")
            if count > 0:
                rel = f.relative_to(plugin_dir)
                findings.append(
                    f"PIT-2: {rel} contains [$ARGUMENTS] (brackets) {count} time(s) — "
                    f"use bare $ARGUMENTS instead"
                )
    return findings


def check_pit6_phantom_fields(plugin_dir: Path) -> list[str]:
    """PIT-6: plugin.json must not contain phantom fields."""
    findings = []
    pjson_path = plugin_dir / ".claude-plugin" / "plugin.json"
    if not pjson_path.exists():
        findings.append("PIT-6: .claude-plugin/plugin.json not found")
        return findings
    try:
        data = json.loads(pjson_path.read_text(encoding="utf-8"))
    except Exception as e:
        findings.append(f"PIT-6: could not parse plugin.json: {e}")
        return findings
    phantom = set(data.keys()) - ALLOWED_PLUGIN_JSON_FIELDS
    if phantom:
        findings.append(
            f"PIT-6: plugin.json contains phantom field(s): {sorted(phantom)} "
            f"— not in the canonical field set"
        )
    return findings


def run_checks(plugin_dir: Path) -> list[str]:
    """Run all static checks against a plugin fixture. Returns list of findings."""
    findings = []
    findings.extend(check_pit1_baseline_import(plugin_dir))
    findings.extend(check_pit2_arguments_brackets(plugin_dir))
    findings.extend(check_pit6_phantom_fields(plugin_dir))
    return findings


def main() -> int:
    clean_dir = CALIBRATION_DIR / "clean-plugin"
    buggy_dir = CALIBRATION_DIR / "buggy-plugin"

    for d in (clean_dir, buggy_dir):
        if not d.exists():
            print(f"ERROR: calibration fixture not found: {d}", file=sys.stderr)
            return 1

    print("=" * 70)
    print("CALIBRATION CHECKER")
    print("=" * 70)

    # ── Clean fixture ─────────────────────────────────────────────────────────
    print(f"\n[FIXTURE] clean-plugin (expected: 0 findings)")
    clean_findings = run_checks(clean_dir)
    if clean_findings:
        print(f"  RESULT: FAIL — {len(clean_findings)} finding(s) [FALSE POSITIVE]")
        for f in clean_findings:
            print(f"  FINDING: {f}")
    else:
        print(f"  RESULT: PASS — 0 findings (no false positives)")

    # ── Buggy fixture ─────────────────────────────────────────────────────────
    print(f"\n[FIXTURE] buggy-plugin (expected: ≥2 findings)")
    buggy_findings = run_checks(buggy_dir)
    if buggy_findings:
        print(f"  RESULT: PASS — {len(buggy_findings)} finding(s) caught (seeded defects detected)")
        for f in buggy_findings:
            print(f"  FINDING: {f}")
    else:
        print(f"  RESULT: FAIL — 0 findings [MISSED SEEDED DEFECT]")

    # ── Summary ───────────────────────────────────────────────────────────────
    print()
    print("=" * 70)
    false_positive = len(clean_findings) > 0
    missed_defect = len(buggy_findings) == 0
    if false_positive or missed_defect:
        if false_positive:
            print(f"FAIL — clean fixture got {len(clean_findings)} false finding(s)")
        if missed_defect:
            print("FAIL — buggy fixture seeded defect was not caught")
        return 1

    print(f"PASS — clean: 0 findings, buggy: {len(buggy_findings)} finding(s) caught")
    print("Calibration check succeeded: no false positives, no missed defects.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
