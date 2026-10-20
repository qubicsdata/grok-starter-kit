#!/usr/bin/env python3
"""
check-stray-artifacts.py — Fleet CI gate: a published plugin directory contains only
its legitimate structure.

Catches the build-artifact leak class (a lesson of the horizontal-layer session): per-task build
reports, misfiled process-output dirs, and OS/editor cruft committed into a plugin —
the exact anti-pattern behind the leaked `cost-monitor/TASK-1-REPORT.md`.

Conservative + calibrated. Flags a curated, case-sensitive leak-pattern set (build
reports are an UPPERCASE convention, so a lowercase `task-scoring.md` skill is never
flagged) and errs toward silence — zero false positives is the bar. The `--calibrate`
self-test asserts clean:0 / dirty:>=1, mirroring check-output-hygiene.

Usage:
    python3 tools/check-stray-artifacts.py             # scan the fleet
    python3 tools/check-stray-artifacts.py --calibrate  # self-test (gate)

Exit codes:
    scan:      0 = no stray artifacts, 1 = stray artifact(s) found
    calibrate: 0 = clean:0 & dirty:>=1, 1 = false-positive or miss
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CALIBRATION_DIR = REPO_ROOT / "tools" / "calibration"

# Shared discovery-exclusion set — keep identical to check-skill-refs /
# validate-fleet so no checker walks benchmarks/, .claude/worktrees, etc.
NON_PLUGIN_DIRS = {"docs", "benchmarks", "tools", ".git", ".claude", ".claude-plugin"}

# Filenames that must never live inside a published plugin dir.
# TASK-/-REPORT/-REBENCHMARK are matched CASE-SENSITIVELY (uppercase build-artifact
# convention) so legitimate lowercase files like `task-scoring.md` are not flagged.
STRAY_FILE_PATTERNS = [
    re.compile(r"^TASK-.*\.md$"),            # TASK-1-REPORT.md, TASK-2.md
    re.compile(r".*-REPORT\.md$"),           # BUILDER-REPORT.md
    re.compile(r".*-REBENCHMARK\.md$"),      # X-REBENCHMARK.md
    re.compile(r".*\.(tmp|bak|orig)$", re.IGNORECASE),  # unambiguous scratch/backup cruft
    re.compile(r"^(\.DS_Store|Thumbs\.db)$"),
    re.compile(r".*~$"),                     # editor backups
]

# Directory names that should never be nested inside a plugin (misfiled process output).
STRAY_DIRS = {"scratch", "superpowers"}


def is_stray_file(name: str) -> bool:
    return any(p.match(name) for p in STRAY_FILE_PATTERNS)


def scan_plugin(plugin_dir: Path) -> list[str]:
    """Return a list of stray-artifact findings inside one plugin directory."""
    findings = []
    for path in sorted(plugin_dir.rglob("*")):
        rel = path.relative_to(plugin_dir)
        if path.is_dir():
            if path.name in STRAY_DIRS:
                findings.append(f"{plugin_dir.name}/{rel}/ — misfiled process-output dir")
            continue
        if is_stray_file(path.name):
            findings.append(f"{plugin_dir.name}/{rel} — stray build artifact")
    return findings


def plugin_dirs():
    for child in sorted(REPO_ROOT.iterdir()):
        if not child.is_dir() or child.name in NON_PLUGIN_DIRS or child.name.startswith("."):
            continue
        if (child / ".claude-plugin" / "plugin.json").exists():
            yield child


def _scan_mode() -> int:
    findings = []
    for p in plugin_dirs():
        findings += scan_plugin(p)
    if findings:
        for f in findings:
            print(f"  FAIL: {f}")
        print(f"check-stray-artifacts: FAIL ({len(findings)} stray artifact(s))")
        return 1
    print("check-stray-artifacts: PASS (no stray artifacts)")
    return 0


def _calibrate_mode() -> int:
    clean_dir = CALIBRATION_DIR / "stray-clean"
    dirty_dir = CALIBRATION_DIR / "stray-dirty"
    for d in (clean_dir, dirty_dir):
        if not d.exists():
            print(f"ERROR: stray fixture not found: {d}", file=sys.stderr)
            return 1

    print("=" * 70)
    print("STRAY-ARTIFACT CALIBRATION")
    print("=" * 70)

    print("\n[FIXTURE] stray-clean (expected: 0 findings)")
    clean = scan_plugin(clean_dir)
    for f in clean:
        print(f"  FINDING: {f}")
    print("  RESULT: PASS — 0 findings" if not clean
          else f"  RESULT: FAIL — {len(clean)} finding(s) [FALSE POSITIVE]")

    print("\n[FIXTURE] stray-dirty (expected: >=1 finding)")
    dirty = scan_plugin(dirty_dir)
    for f in dirty:
        print(f"  FINDING: {f}")
    print(f"  RESULT: PASS — {len(dirty)} finding(s) caught" if dirty
          else "  RESULT: FAIL — 0 findings [MISSED SEEDED ARTIFACTS]")

    print("\n" + "=" * 70)
    false_positive = len(clean) > 0
    missed = len(dirty) < 1
    if false_positive or missed:
        if false_positive:
            print(f"FAIL — clean fixture got {len(clean)} false finding(s)")
        if missed:
            print("FAIL — dirty fixture yielded 0 findings")
        return 1
    print(f"PASS — clean: 0 findings, dirty: {len(dirty)} finding(s) caught")
    return 0


def main(argv: list[str]) -> int:
    if len(argv) == 2 and argv[1] == "--calibrate":
        return _calibrate_mode()
    if len(argv) == 1:
        return _scan_mode()
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
