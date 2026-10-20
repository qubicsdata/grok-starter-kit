#!/usr/bin/env python3
"""
check-hooks-drift.py — verify that the hooks shipped with the ai-baseline plugin
(ai-baseline/hooks/scripts/) are byte-identical to the canonical sources in
tools/hooks/, and that ai-baseline/hooks/hooks.json is valid.

Canonical source of truth is tools/hooks/ (live in this repo via .claude/settings.json).
The shipped set is what installed consumers actually run. Fix drift with:

    python3 tools/sync-shipped-hooks.py

Checks:
  1. ai-baseline/hooks/hooks.json exists, parses as JSON, and wires all four
     event types: SessionStart, Stop, SubagentStop, PreToolUse.
  2. Every canonical script (tools/hooks/*.py, excluding tests) has a shipped copy.
  3. Every shipped copy is byte-identical to its canonical source.
  4. No stray shipped script exists without a canonical source.
  5. Every hook data file at the suite root (pricing.json) has a byte-identical
     shipped copy beside the scripts.

Exits 0 if all checks pass; exits 1 listing every failure.

Usage:
    python3 tools/check-hooks-drift.py
    python3 tools/check-hooks-drift.py --root <path>   # test/fixture override
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

CANONICAL_REL = Path("tools") / "hooks"
SHIPPED_REL = Path("ai-baseline") / "hooks" / "scripts"
HOOKS_JSON_REL = Path("ai-baseline") / "hooks" / "hooks.json"

REQUIRED_EVENTS = ("SessionStart", "Stop", "SubagentStop", "PreToolUse")
# Data files the hooks read, canonical at the suite root, shipped beside the scripts.
DATA_FILES = ("pricing.json",)


def canonical_scripts(root: Path) -> list[Path]:
    """Canonical hook scripts: tools/hooks/*.py, excluding tests (README.md is not .py)."""
    canonical_dir = root / CANONICAL_REL
    return sorted(p for p in canonical_dir.glob("*.py") if not p.name.startswith("test_"))


def check_hooks_json(root: Path) -> list[str]:
    """Validate ai-baseline/hooks/hooks.json: present, valid JSON, all 4 events wired."""
    findings = []
    hooks_json = root / HOOKS_JSON_REL
    if not hooks_json.is_file():
        findings.append(f"MISSING {HOOKS_JSON_REL} — plugin ships no hook wiring")
        return findings
    try:
        data = json.loads(hooks_json.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        findings.append(f"MALFORMED {HOOKS_JSON_REL} — not valid JSON: {e}")
        return findings
    events = data.get("hooks")
    if not isinstance(events, dict):
        findings.append(f"MALFORMED {HOOKS_JSON_REL} — top-level 'hooks' object missing")
        return findings
    for event in REQUIRED_EVENTS:
        if event not in events:
            findings.append(f"MISSING EVENT {HOOKS_JSON_REL} — '{event}' not wired")
    return findings


def check_scripts(root: Path, quiet: bool = False) -> list[str]:
    """Byte-compare every canonical script against its shipped copy; flag strays."""
    findings = []
    shipped_dir = root / SHIPPED_REL
    canonical = canonical_scripts(root)
    canonical_names = {p.name for p in canonical}

    for source in canonical:
        shipped = shipped_dir / source.name
        if not shipped.is_file():
            findings.append(f"MISSING {SHIPPED_REL / source.name} — canonical script not shipped")
            continue
        if source.read_bytes() != shipped.read_bytes():
            findings.append(
                f"DRIFT {SHIPPED_REL / source.name} — differs from {CANONICAL_REL / source.name}"
            )
        elif not quiet:
            print(f"OK {SHIPPED_REL / source.name}")

    if shipped_dir.is_dir():
        for stray in sorted(shipped_dir.glob("*.py")):
            if stray.name not in canonical_names:
                findings.append(f"STRAY {SHIPPED_REL / stray.name} — no canonical source in {CANONICAL_REL}")
    return findings


def check_data_files(root: Path, quiet: bool = False) -> list[str]:
    """Byte-compare every hook data file at the suite root against its shipped copy."""
    findings = []
    for name in DATA_FILES:
        source, shipped = root / name, root / SHIPPED_REL / name
        if not source.is_file():
            findings.append(f"MISSING {name} — canonical hook data file absent")
        elif not shipped.is_file():
            findings.append(f"MISSING {SHIPPED_REL / name} — hook data file not shipped")
        elif source.read_bytes() != shipped.read_bytes():
            findings.append(f"DRIFT {SHIPPED_REL / name} — differs from {name}")
        elif not quiet:
            print(f"OK {SHIPPED_REL / name}")
    return findings


def run_checks(root: Path, quiet: bool = False) -> list[str]:
    """Run all shipped-hooks checks against `root`; return the list of failures."""
    return (check_hooks_json(root) + check_scripts(root, quiet=quiet)
            + check_data_files(root, quiet=quiet))


def main(argv: list[str]) -> int:
    root = REPO_ROOT
    if len(argv) == 3 and argv[1] == "--root":
        root = Path(argv[2]).resolve()
    elif len(argv) != 1:
        print(__doc__)
        return 2

    if not (root / CANONICAL_REL).is_dir():
        print(f"ERROR: canonical hooks dir not found: {root / CANONICAL_REL}", file=sys.stderr)
        return 1

    findings = run_checks(root)
    if findings:
        for f in findings:
            print(f"  FAIL: {f}")
        print(f"\ncheck-hooks-drift: FAIL ({len(findings)} finding(s)) — "
              f"run 'python3 tools/sync-shipped-hooks.py' to re-sync shipped copies")
        return 1

    print(f"\ncheck-hooks-drift: PASS ({len(canonical_scripts(root))} shipped script(s) and "
          f"{len(DATA_FILES)} data file(s) byte-identical, hooks.json wires all "
          f"{len(REQUIRED_EVENTS)} events)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
