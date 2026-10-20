#!/usr/bin/env python3
"""
check-skill-refs.py — Guard the self-activating-skills + cross-plugin-links invariants.

Phase 3 (self-activating skills):
  - Every discoverable skill (skills/<name>/SKILL.md) must have a trigger-facing
    description (contains "use when").
  - No agent/command may reference a promoted skill by its OLD flat path
    (skills/<name>.md) — that path no longer exists after promotion.

Phase 4 (cross-plugin links):
  - Every authored handoff token ("Next: ... `/cmd`" or "`plugin:agent`") must
    resolve to a real command or agent somewhere in the fleet.

Exits non-zero on any violation.

Usage:
    python3 tools/check-skill-refs.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
NON_PLUGIN_DIRS = {"docs", "benchmarks", "tools", ".git", ".claude", ".claude-plugin"}


def plugin_dirs():
    for child in sorted(REPO_ROOT.iterdir()):
        if not child.is_dir() or child.name in NON_PLUGIN_DIRS or child.name.startswith("."):
            continue
        if (child / ".claude-plugin" / "plugin.json").exists():
            yield child


def frontmatter(text: str) -> str:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return ""
    out = []
    for line in lines[1:]:
        if line.strip() == "---":
            break
        out.append(line)
    return "\n".join(out)


def discoverable_skills():
    """All promoted skills: (plugin_dir, skill_name, skill_path)."""
    for p in plugin_dirs():
        sk = p / "skills"
        if not sk.exists():
            continue
        for skill_md in sk.glob("*/SKILL.md"):
            yield p, skill_md.parent.name, skill_md


def fleet_commands():
    names = set()
    for p in plugin_dirs():
        d = p / "commands"
        if d.exists():
            names.update(f.stem for f in d.glob("*.md"))
    return names


def fleet_agents():
    """Set of {agent-name} and {plugin:agent-name} tokens."""
    names = set()
    for p in plugin_dirs():
        d = p / "agents"
        if d.exists():
            for f in d.glob("*.md"):
                names.add(f.stem)
                names.add(f"{p.name}:{f.stem}")
    return names


def check_trigger_descriptions() -> list[str]:
    errs = []
    for _p, name, path in discoverable_skills():
        desc = frontmatter(path.read_text(encoding="utf-8", errors="replace"))
        m = re.search(r"description:\s*(.*)", desc, re.IGNORECASE | re.DOTALL)
        body = (m.group(1) if m else desc).lower()
        if "use when" not in body:
            errs.append(f"{path.relative_to(REPO_ROOT)}: description is not trigger-facing (missing 'Use when')")
    return errs


def check_no_old_flat_refs() -> list[str]:
    errs = []
    promoted = {name for _p, name, _path in discoverable_skills()}
    for p in plugin_dirs():
        for sub in ("agents", "commands"):
            d = p / sub
            if not d.exists():
                continue
            for f in d.rglob("*.md"):
                text = f.read_text(encoding="utf-8", errors="replace")
                for name in promoted:
                    if f"skills/{name}.md" in text:
                        errs.append(f"{f.relative_to(REPO_ROOT)}: stale flat ref 'skills/{name}.md' (skill was promoted to skills/{name}/SKILL.md)")
    return errs


# Handoff line marker authored in Phase 4. Matches lines like:
#   Next: run `/api-review` ...   |   Next → hand to `dev-companion:security`
HANDOFF_RE = re.compile(r"<!--\s*handoff:\s*(.+?)\s*-->")
TOKEN_RE = re.compile(r"`(/[a-z0-9-]+|[a-z0-9-]+:[a-z0-9-]+)`", re.IGNORECASE)


def check_handoff_targets() -> list[str]:
    errs = []
    commands = fleet_commands()
    agents = fleet_agents()
    for p in plugin_dirs():
        for sub in ("agents", "commands", "skills"):
            d = p / sub
            if not d.exists():
                continue
            for f in d.rglob("*.md"):
                text = f.read_text(encoding="utf-8", errors="replace")
                for marker in HANDOFF_RE.findall(text):
                    for tok in TOKEN_RE.findall(marker):
                        if tok.startswith("/"):
                            if tok[1:] not in commands:
                                errs.append(f"{f.relative_to(REPO_ROOT)}: handoff names command '{tok}' which does not resolve")
                        else:
                            if tok not in agents:
                                errs.append(f"{f.relative_to(REPO_ROOT)}: handoff names agent '{tok}' which does not resolve")
    return errs


def main() -> int:
    all_errs = []
    all_errs += check_trigger_descriptions()
    all_errs += check_no_old_flat_refs()
    all_errs += check_handoff_targets()

    promoted = list(discoverable_skills())
    print(f"check-skill-refs: {len(promoted)} discoverable skill(s) inspected")
    if all_errs:
        for e in all_errs:
            print(f"  FAIL: {e}")
        print(f"check-skill-refs: FAIL ({len(all_errs)} issue(s))")
        return 1
    print("check-skill-refs: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
