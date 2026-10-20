#!/usr/bin/env python3
"""
check-baseline-drift.py — verify that every plugin copy of baseline-enforcer.md
and audit-trail-agent.md is byte-identical to the ai-baseline source after
stripping the optional line-1 provenance stamp (ADR-0001).

Exits 0 if all copies match; exits 1 if any drift is detected.

Usage:
    python3 tools/check-baseline-drift.py
"""

import difflib
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

SOURCES = {
    "skills/baseline-enforcer.md": REPO_ROOT / "ai-baseline" / "skills" / "baseline-enforcer.md",
    "agents/audit-trail-agent.md": REPO_ROOT / "ai-baseline" / "agents" / "audit-trail-agent.md",
}

EXCLUDE_DIRS = {"ai-baseline", "benchmarks", ".git", "tools"}

PROVENANCE_RE = re.compile(r"^<!-- baseline-provenance:[^\n>]*-->\r?\n")


def strip_provenance(text: str) -> str:
    """Copies carry an injected line-1 provenance stamp (ADR-0001); sources do not."""
    return PROVENANCE_RE.sub("", text, count=1)


def find_copies() -> list[tuple[str, Path]]:
    """Find every plugin copy of the tracked baseline files."""
    copies = []
    for rel_key, source_path in SOURCES.items():
        filename = Path(rel_key).name
        for candidate in REPO_ROOT.rglob(filename):
            # Exclude the source itself and any excluded dirs
            rel = candidate.relative_to(REPO_ROOT)
            parts = rel.parts
            if any(p in EXCLUDE_DIRS for p in parts):
                continue
            # Must match the relative path pattern (e.g. */skills/baseline-enforcer.md)
            expected_suffix = rel_key  # e.g. "skills/baseline-enforcer.md"
            candidate_rel_str = "/".join(parts[-2:]) if len(parts) >= 2 else parts[-1]
            if candidate_rel_str == expected_suffix:
                copies.append((rel_key, candidate, source_path))
    return copies


def check_drift(rel_key: str, copy_path: Path, source_path: Path) -> bool:
    """Return True if drift detected, False if identical."""
    source_text = source_path.read_text(encoding="utf-8")
    copy_text = strip_provenance(copy_path.read_text(encoding="utf-8"))

    if source_text == copy_text:
        print(f"OK {copy_path.relative_to(REPO_ROOT)}")
        return False

    # Show unified diff
    source_lines = source_text.splitlines(keepends=True)
    copy_lines = copy_text.splitlines(keepends=True)
    diff = list(difflib.unified_diff(
        source_lines,
        copy_lines,
        fromfile=f"ai-baseline/{rel_key}",
        tofile=str(copy_path.relative_to(REPO_ROOT)),
    ))
    print(f"DRIFT {copy_path.relative_to(REPO_ROOT)}")
    sys.stdout.writelines(diff)
    return True


def main() -> int:
    if not REPO_ROOT.is_dir():
        print(f"ERROR: repo root not found: {REPO_ROOT}", file=sys.stderr)
        return 1

    # Verify sources exist
    for rel_key, source_path in SOURCES.items():
        if not source_path.exists():
            print(f"ERROR: source not found: {source_path.relative_to(REPO_ROOT)}", file=sys.stderr)
            return 1

    copies = find_copies()
    if not copies:
        print("No plugin copies found — nothing to check.")
        return 0

    drift_found = False
    for rel_key, copy_path, source_path in sorted(copies, key=lambda t: str(t[1])):
        if check_drift(rel_key, copy_path, source_path):
            drift_found = True

    if drift_found:
        print("\nDRIFT DETECTED — plugin copies diverge from ai-baseline source.")
        return 1

    print(f"\nAll {len(copies)} copies match ai-baseline source. No drift.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
