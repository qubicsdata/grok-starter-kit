#!/usr/bin/env python3
"""
sync-shipped-hooks.py — copy the canonical hook scripts (tools/hooks/*.py) into the
shipped set the ai-baseline plugin bundles for installed consumers
(ai-baseline/hooks/scripts/).

Canonical source of truth stays tools/hooks/ — this repo runs those live via
.claude/settings.json. Installed consumers run the shipped copies via
ai-baseline/hooks/hooks.json. After editing any canonical hook, run this script so
the shipped set stays byte-identical; tools/check-hooks-drift.py (fleet gate)
fails the build on any divergence.

Copies every tools/hooks/*.py (excluding tests; README.md is not shipped) and
the hook data files at the suite root (pricing.json), and removes any stale
shipped .py with no canonical source. Never touches tools/hooks/ itself, and
never touches ai-baseline/hooks/hooks.json.

Usage:
    python3 tools/sync-shipped-hooks.py
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CANONICAL_DIR = REPO_ROOT / "tools" / "hooks"
SHIPPED_DIR = REPO_ROOT / "ai-baseline" / "hooks" / "scripts"
# Data files the hooks read, canonical at the suite root, shipped beside the scripts.
DATA_FILES = ("pricing.json",)


def canonical_scripts() -> list[Path]:
    """Canonical hook scripts: tools/hooks/*.py, excluding tests."""
    return sorted(p for p in CANONICAL_DIR.glob("*.py") if not p.name.startswith("test_"))


def canonical_data_files() -> list[Path]:
    return [REPO_ROOT / name for name in DATA_FILES]


def main() -> int:
    if not CANONICAL_DIR.is_dir():
        print(f"ERROR: canonical hooks dir not found: {CANONICAL_DIR}", file=sys.stderr)
        return 1

    sources = canonical_scripts()
    if not sources:
        print(f"ERROR: no canonical hook scripts found in {CANONICAL_DIR}", file=sys.stderr)
        return 1
    missing = [p for p in canonical_data_files() if not p.is_file()]
    if missing:
        for path in missing:
            print(f"ERROR: hook data file not found: {path}", file=sys.stderr)
        return 1

    SHIPPED_DIR.mkdir(parents=True, exist_ok=True)
    synced = unchanged = 0
    for source in sources + canonical_data_files():
        target = SHIPPED_DIR / source.name
        if target.is_file() and target.read_bytes() == source.read_bytes():
            print(f"UNCHANGED {target.relative_to(REPO_ROOT)}")
            unchanged += 1
            continue
        shutil.copyfile(source, target)
        print(f"SYNCED    {target.relative_to(REPO_ROOT)}")
        synced += 1

    removed = 0
    canonical_names = {p.name for p in sources}
    for stray in sorted(SHIPPED_DIR.glob("*.py")):
        if stray.name not in canonical_names:
            stray.unlink()
            print(f"REMOVED   {stray.relative_to(REPO_ROOT)} (no canonical source)")
            removed += 1

    print(f"\nsync-shipped-hooks: {synced} synced, {unchanged} unchanged, {removed} removed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
