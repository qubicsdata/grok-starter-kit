#!/usr/bin/env python3
"""
check-plugin-static.py — statically-checkable PIT rules for ONE plugin directory.

The agent-builder critic runs PIT-1..11 in-LLM. Several of those rules are purely
mechanical — a regex decides them, no judgment needed. This tool enforces that subset
statically so correctness does not DEPEND on the LLM critic noticing them, and the
critic can focus its tokens on judgment. The publisher runs this at publish time as a
hard gate (it is the one agent that writes to disk); the fleet-wide equivalents live in
validate-fleet.py.

Rules checked:
  PIT-2  no [$ARGUMENTS] (brackets) in any agent/skill/command file
  PIT-6  plugin.json contains only the canonical field set
  PIT-8  behavioral-scenarios.md declared count == actual heading count
  PIT-9  every model: value is allowed by tools/model-ids.json
  PIT-13 no @-link force-loads (@skills/..., @agents/...) in any agent/skill/command body

Usage:
    python3 tools/check-plugin-static.py <plugin-dir>
Exit 0 = clean, 1 = >=1 finding.
"""

import json
import re
import sys
from pathlib import Path

ALLOWED_PLUGIN_JSON_FIELDS = {
    "name", "version", "description", "category", "author",
    "keywords", "requires", "kind", "commands", "skills", "agents",
    "schema_version", "readme", "homepage", "license",
}

_REPO_ROOT = Path(__file__).resolve().parent.parent

def _load_model_ids() -> set:
    p = _REPO_ROOT / "tools" / "model-ids.json"
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return set(data["allowed"]) - set(data["deprecated"])
    except Exception as e:  # a gate with no allowlist must not silently pass
        print(f"ERROR: cannot load {p}: {e}", file=sys.stderr)
        raise SystemExit(1)

ALLOWED_MODEL_IDS = _load_model_ids()
HEADING_RE = re.compile(r"^(### .+|## Scenario .+)$", re.MULTILINE)
DECLARED_RE = re.compile(r"(?i)total:\s*(\d+)\s*scenario")
MODEL_RE = re.compile(r"^model:\s*(.+?)\s*$", re.MULTILINE)
ATLINK_RE = re.compile(r"(?<![\w@.])@(?:[\w-]+/)*(?:skills|agents|commands)/[\w./-]+")


def check_pit2(plugin: Path) -> list[str]:
    out = []
    for sub in ("agents", "skills", "commands"):
        d = plugin / sub
        if not d.exists():
            continue
        for f in sorted(d.rglob("*.md")):
            n = f.read_text(encoding="utf-8", errors="replace").count("[$ARGUMENTS]")
            if n:
                out.append(f"PIT-2: {f.relative_to(plugin)} uses [$ARGUMENTS] {n}× — use bare $ARGUMENTS")
    return out


def check_pit6(plugin: Path) -> list[str]:
    p = plugin / ".claude-plugin" / "plugin.json"
    if not p.exists():
        return [f"PIT-6: {p.relative_to(plugin)} not found"]
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        return [f"PIT-6: plugin.json unparseable: {e}"]
    phantom = set(data.keys()) - ALLOWED_PLUGIN_JSON_FIELDS
    return [f"PIT-6: plugin.json has phantom field(s): {sorted(phantom)}"] if phantom else []


def check_pit8(plugin: Path) -> list[str]:
    f = plugin / "tests" / "behavioral-scenarios.md"
    if not f.exists():
        return []  # absence handled by scenario-coverage, not here
    text = f.read_text(encoding="utf-8", errors="replace")
    m = DECLARED_RE.search(text)
    if not m:
        return []  # no declared count to reconcile
    declared = int(m.group(1))
    actual = len(HEADING_RE.findall(text))
    if declared != actual:
        return [f"PIT-8: behavioral-scenarios.md declares {declared} but has {actual} scenario headings"]
    return []


def check_pit9(plugin: Path) -> list[str]:
    out = []
    for sub in ("agents", "skills"):
        d = plugin / sub
        if not d.exists():
            continue
        for f in sorted(d.rglob("*.md")):
            for val in MODEL_RE.findall(f.read_text(encoding="utf-8", errors="replace")):
                if val not in ALLOWED_MODEL_IDS:
                    out.append(f"PIT-9: {f.relative_to(plugin)} has non-canonical model id '{val}'")
    return out


def check_pit13(plugin: Path) -> list[str]:
    out = []
    for sub in ("agents", "skills", "commands"):
        d = plugin / sub
        if not d.exists():
            continue
        for f in sorted(d.rglob("*.md")):
            for m in ATLINK_RE.findall(f.read_text(encoding="utf-8", errors="replace")):
                out.append(f"PIT-13: {f.relative_to(plugin)} uses @-link force-load '{m}' — import skills by name, dispatch agents")
    return out


def scan(plugin: Path) -> list[str]:
    return check_pit2(plugin) + check_pit6(plugin) + check_pit8(plugin) + check_pit9(plugin) + check_pit13(plugin)


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__)
        return 2
    plugin = Path(argv[1]).resolve()
    if not plugin.exists():
        print(f"ERROR: plugin dir not found: {plugin}", file=sys.stderr)
        return 1
    findings = scan(plugin)
    print("=" * 70)
    print(f"STATIC PLUGIN CHECK — {plugin.name}")
    print("=" * 70)
    if findings:
        for f in findings:
            print(f"  FINDING: {f}")
        print(f"\nFAIL — {len(findings)} static finding(s)")
        return 1
    print("  (no findings)")
    print("\nPASS — static PIT checks clean")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
