#!/usr/bin/env python3
"""
check-marketplace-parity.py — marketplace manifest vs plugin dirs on disk.

registry.json is GENERATED (tools/gen-registry.py) but .claude-plugin/marketplace.json
is HAND-MAINTAINED, so a new plugin dir can be registered yet never exposed for
install. That is exactly how performance-companion and qa-companion sat on disk,
in the registry, and uninstallable. This gate closes that gap.

Checks, against every dir holding .claude-plugin/plugin.json:
  1. every plugin dir has a marketplace entry (no unexposed plugins)
  2. every marketplace entry points at a real plugin dir (no phantom entries)
  3. entry `source` resolves to that plugin's directory
  4. entry `version` agrees with the plugin's own plugin.json
  5. metadata description's plugin count matches reality

Usage:
    python3 tools/check-marketplace-parity.py
Exit 0 = clean, 1 = >=1 finding.
"""
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MARKETPLACE = REPO_ROOT / ".claude-plugin" / "marketplace.json"


def plugin_dirs(root=REPO_ROOT):
    return {p.parent.parent.name: p for p in root.glob("*/.claude-plugin/plugin.json")}


def run_all(root=REPO_ROOT, marketplace_path=MARKETPLACE):
    findings = []
    market = json.loads(Path(marketplace_path).read_text(encoding="utf-8"))
    entries = market.get("plugins", [])
    on_disk = plugin_dirs(root)

    listed = {}
    for i, e in enumerate(entries):
        name = e.get("name")
        if not name:
            findings.append(f"marketplace plugins[{i}]: entry has no 'name'")
            continue
        if name in listed:
            findings.append(f"marketplace: duplicate entry for '{name}'")
        listed[name] = e

    for name in sorted(set(on_disk) - set(listed)):
        findings.append(
            f"{name}: plugin dir exists but has NO marketplace entry — it cannot be installed")
    for name in sorted(set(listed) - set(on_disk)):
        findings.append(
            f"{name}: marketplace entry has no matching plugin dir")

    for name in sorted(set(on_disk) & set(listed)):
        entry = listed[name]
        source = entry.get("source")
        if source != f"./{name}":
            findings.append(f"{name}: marketplace source is {source!r}, expected './{name}'")
        pj = json.loads(on_disk[name].read_text(encoding="utf-8"))
        if entry.get("version") != pj.get("version"):
            findings.append(
                f"{name}: marketplace version {entry.get('version')!r} != "
                f"plugin.json version {pj.get('version')!r}")

    desc = market.get("metadata", {}).get("description", "")
    m = re.search(r"(\d+)\s+composable plugins", desc)
    if m and int(m.group(1)) != len(entries):
        findings.append(
            f"marketplace metadata says {m.group(1)} composable plugins, "
            f"manifest lists {len(entries)}")
    return findings


def main(argv) -> int:
    findings = run_all()
    for f in findings:
        print(f)
    print(f"{'CLEAN' if not findings else 'FINDINGS: ' + str(len(findings))}")
    return 0 if not findings else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
