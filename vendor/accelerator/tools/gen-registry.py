#!/usr/bin/env python3
"""
gen-registry.py — Scan every plugin dir and emit registry.json.

Each entry: {name, version, kind, category, requires, enricher_prefix, commands, has_baseline}

Also writes the author identity and homepage from ${KIT_HOME}/kit.config.yaml
(kit.author_name, kit.author_email, kit.homepage; placeholders when absent) into
every plugin.json and .claude-plugin/marketplace.json, in place (see
tools/kit_identity.py). An empty homepage removes the homepage fields.

Exits non-zero if two plugins share the same non-null enricher_prefix (collision),
or if kit.config.yaml or a manifest cannot be used. Writes nothing in those cases.

Usage:
    python3 tools/gen-registry.py
"""

import importlib.util
import json
import re
import sys
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parent.parent


def load_kit_identity():
    """tools/kit_identity.py, loaded by path (works without sys.path)."""
    path = Path(__file__).resolve().parent / "kit_identity.py"
    spec = importlib.util.spec_from_file_location("kit_identity", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

# Directories at repo root that are NOT plugin dirs
NON_PLUGIN_DIRS = {
    "docs", "benchmarks", "tools", ".git", ".claude-plugin",
}

# Build tools: classified as kind=build-tool, no spec-enricher, no requires
BUILD_TOOLS = {"agent-builder", "assimilator"}

# The substrate: validated specially, no spec-enricher
SUBSTRATE = "ai-baseline"


def find_plugin_dirs() -> list[Path]:
    """Return sorted list of plugin dirs (direct children of repo root)."""
    dirs = []
    for child in REPO_ROOT.iterdir():
        if not child.is_dir():
            continue
        if child.name in NON_PLUGIN_DIRS:
            continue
        if child.name.startswith("."):
            continue
        pjson = child / ".claude-plugin" / "plugin.json"
        if not pjson.exists():
            continue
        dirs.append(child)
    return sorted(dirs)


def read_plugin_json(plugin_dir: Path) -> dict:
    pjson = plugin_dir / ".claude-plugin" / "plugin.json"
    return json.loads(pjson.read_text(encoding="utf-8"))


def extract_enricher_prefix(plugin_dir: Path) -> Optional[str]:
    """
    Read agents/spec-enricher.md and extract the requirement-ID prefix.
    The prefix is the alphabetic part of the first [PREFIX-N] pattern found
    in the REQUIREMENTS block.
    Returns None if no spec-enricher or no prefix found.
    """
    enricher = plugin_dir / "agents" / "spec-enricher.md"
    if not enricher.exists():
        return None
    text = enricher.read_text(encoding="utf-8")
    # Find the first [ALPHA-digit] pattern in the file
    m = re.search(r'\[([A-Z]+)-\d+\]', text)
    if m:
        return m.group(1)
    return None


def list_commands(plugin_dir: Path) -> list[str]:
    """Return sorted list of command filenames (stems) from commands/."""
    cmd_dir = plugin_dir / "commands"
    if not cmd_dir.exists():
        return []
    return sorted(p.name for p in cmd_dir.iterdir() if p.suffix == ".md")


def has_baseline(plugin_dir: Path) -> bool:
    """True if plugin ships both baseline-enforcer.md and audit-trail-agent.md."""
    return (
        (plugin_dir / "skills" / "baseline-enforcer.md").exists()
        and (plugin_dir / "agents" / "audit-trail-agent.md").exists()
    )


def classify_kind(name: str, data: dict) -> str:
    if name in BUILD_TOOLS:
        return "build-tool"
    explicit = data.get("kind")
    if explicit:
        return explicit
    return "runtime"


def build_entry(plugin_dir: Path) -> dict:
    name = plugin_dir.name
    data = read_plugin_json(plugin_dir)
    kind = classify_kind(name, data)

    if kind == "build-tool" or name == SUBSTRATE:
        enricher_prefix = None
        requires = []
    else:
        enricher_prefix = extract_enricher_prefix(plugin_dir)
        requires = data.get("requires", [])

    return {
        "name": name,
        "version": data.get("version", ""),
        "kind": kind,
        "category": data.get("category", ""),
        "requires": requires,
        "enricher_prefix": enricher_prefix,
        "commands": list_commands(plugin_dir),
        "has_baseline": has_baseline(plugin_dir),
    }


def check_prefix_collision(entries: list[dict]) -> list[str]:
    """Return list of collision error messages (empty if none)."""
    seen: dict[str, str] = {}
    errors = []
    for entry in entries:
        prefix = entry.get("enricher_prefix")
        if prefix is None:
            continue
        name = entry["name"]
        if prefix in seen:
            errors.append(
                f"COLLISION: prefix '{prefix}' claimed by both "
                f"'{seen[prefix]}' and '{name}'"
            )
        else:
            seen[prefix] = name
    return errors


def main() -> int:
    kit = load_kit_identity()
    try:
        identity = kit.load_identity(REPO_ROOT)
        manifests = kit.manifest_updates(REPO_ROOT, identity)
    except (kit.ConfigError, kit.DocError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        print("ABORT: nothing written.", file=sys.stderr)
        return 2

    plugin_dirs = find_plugin_dirs()
    if not plugin_dirs:
        print("ERROR: no plugin dirs found", file=sys.stderr)
        return 1

    entries = []
    for pdir in plugin_dirs:
        try:
            entry = build_entry(pdir)
            entries.append(entry)
        except Exception as exc:
            print(f"ERROR processing {pdir.name}: {exc}", file=sys.stderr)
            return 1

    # Collision check before writing
    collisions = check_prefix_collision(entries)
    if collisions:
        for msg in collisions:
            print(msg, file=sys.stderr)
        print("ABORT: prefix collision detected — registry.json NOT written.", file=sys.stderr)
        return 1

    # Write registry.json
    out_path = REPO_ROOT / "registry.json"
    out_path.write_text(json.dumps(entries, indent=2) + "\n", encoding="utf-8")
    print(f"registry.json written ({len(entries)} plugins)")
    kit.write_updates(manifests)
    print(f"manifests: author and homepage from kit config ({len(manifests)} file(s) updated)")

    # Print prefix table
    print("\nEnricher prefixes:")
    for entry in entries:
        pfx = entry["enricher_prefix"] or "(none)"
        print(f"  {entry['name']:<35} {pfx}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
