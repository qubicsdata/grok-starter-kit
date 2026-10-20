#!/usr/bin/env python3
"""
validate-fleet.py — Enforce every fleet invariant for all plugins.

Checks per plugin:
  (a) plugin.json required fields present + no unknown fields outside allowlist
  (b) runtime plugins have requires: ["ai-baseline"]
  (c) runtime plugins ship skills/baseline-enforcer.md + agents/audit-trail-agent.md
      (verified byte-identical to ai-baseline source via check-baseline-drift logic)
  (d) runtime plugins ship a conformant agents/spec-enricher.md
      (has NOT_APPLICABLE, APPLIES_BECAUSE, a [PREFIX-N] line,
      model: <canonical sonnet per tools/model-ids.json>)
      build tools ship none
  (e) enricher prefix uniqueness across fleet
  (f) no accelerator/ai-baseline path refs in any agent/skill/command file
  (g) model IDs limited to the three current ones

Fleet-wide checks:
  (h) command-name collision — no two plugins may define the same command filename

Prints per-plugin PASS/FAIL table + total. Exits non-zero on any FAIL.

Usage:
    python3 tools/validate-fleet.py
"""

import json
import re
import sys
from pathlib import Path
from collections import defaultdict

REPO_ROOT = Path(__file__).resolve().parent.parent

REQUIRED_FIELDS = {"name", "version", "description", "category", "author", "keywords"}
ALLOWED_FIELDS = REQUIRED_FIELDS | {
    "homepage", "license", "requires", "kind", "commands", "skills", "agents",
    "schema_version", "readme",
}

BUILD_TOOLS = {"agent-builder", "assimilator"}
SUBSTRATE = "ai-baseline"
NON_PLUGIN_DIRS = {"docs", "benchmarks", "tools", ".git"}

def _load_model_ids() -> set:
    p = REPO_ROOT / "tools" / "model-ids.json"
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return set(data["allowed"]) - set(data["deprecated"]), data["canonical"]
    except Exception as e:  # a gate with no allowlist must not silently pass
        print(f"ERROR: cannot load {p}: {e}", file=sys.stderr)
        raise SystemExit(1)

ALLOWED_MODELS, CANONICAL_IDS = _load_model_ids()

# Baseline source files
BASELINE_SOURCE = {
    "skills/baseline-enforcer.md": REPO_ROOT / "ai-baseline" / "skills" / "baseline-enforcer.md",
    "agents/audit-trail-agent.md": REPO_ROOT / "ai-baseline" / "agents" / "audit-trail-agent.md",
}

# Copies carry an injected line-1 provenance stamp (ADR-0001); sources do not.
# Mirrors tools/check-baseline-drift.py's strip_provenance so both gates agree.
PROVENANCE_RE = re.compile(r"^<!-- baseline-provenance:[^\n>]*-->\r?\n")


def strip_provenance(text: str) -> str:
    return PROVENANCE_RE.sub("", text, count=1)


def find_plugin_dirs():
    dirs = []
    for child in REPO_ROOT.iterdir():
        if not child.is_dir():
            continue
        if child.name in NON_PLUGIN_DIRS or child.name.startswith("."):
            continue
        pjson = child / ".claude-plugin" / "plugin.json"
        if not pjson.exists():
            continue
        dirs.append(child)
    return sorted(dirs)


def classify_kind(name, data):
    if name in BUILD_TOOLS:
        return "build-tool"
    return data.get("kind", "runtime")


# ── Check functions ───────────────────────────────────────────────────────────

def check_manifest(name, data):
    """(a) Required fields + no unknown fields."""
    errors = []
    missing = REQUIRED_FIELDS - set(data.keys())
    if missing:
        errors.append(f"missing required fields: {sorted(missing)}")
    unknown = set(data.keys()) - ALLOWED_FIELDS
    if unknown:
        errors.append(f"unknown fields: {sorted(unknown)}")
    return errors


def check_requires(name, data):
    """(b) Runtime plugins must have requires: ['ai-baseline']."""
    req = data.get("requires", [])
    if req != ["ai-baseline"]:
        return [f"requires must be [\"ai-baseline\"], got {req!r}"]
    return []


def check_baseline_files(plugin_dir):
    """(c) Runtime plugins must ship baseline-enforcer.md + audit-trail-agent.md, byte-identical to source."""
    errors = []
    for rel, source_path in BASELINE_SOURCE.items():
        parts = rel.split("/")
        copy_path = plugin_dir / parts[0] / parts[1]
        if not copy_path.exists():
            errors.append(f"missing {rel}")
            continue
        source_text = source_path.read_text(encoding="utf-8")
        copy_text = strip_provenance(copy_path.read_text(encoding="utf-8"))
        if source_text != copy_text:
            errors.append(f"drift detected in {rel} (not byte-identical to ai-baseline source)")
    return errors


def check_spec_enricher(plugin_dir):
    """(d) Runtime plugins must ship a conformant spec-enricher.md."""
    enricher = plugin_dir / "agents" / "spec-enricher.md"
    errors = []
    if not enricher.exists():
        return ["missing agents/spec-enricher.md"]
    text = enricher.read_text(encoding="utf-8")
    if "NOT_APPLICABLE" not in text:
        errors.append("spec-enricher.md missing NOT_APPLICABLE keyword")
    if "APPLIES_BECAUSE" not in text:
        errors.append("spec-enricher.md missing APPLIES_BECAUSE keyword")
    if not re.search(r'\[[A-Z]+-\d+\]', text):
        errors.append("spec-enricher.md missing [PREFIX-N] requirement line")
    expected_model = f"model: {CANONICAL_IDS['sonnet']}"
    if expected_model not in text:
        errors.append(f"spec-enricher.md missing '{expected_model}'")
    return errors


def check_no_enricher_build_tool(plugin_dir):
    """(d) Build tools must NOT ship a spec-enricher.md."""
    enricher = plugin_dir / "agents" / "spec-enricher.md"
    if enricher.exists():
        return ["build-tool must not ship agents/spec-enricher.md"]
    return []


def extract_enricher_prefix(plugin_dir):
    """Extract enricher prefix from spec-enricher.md. Returns None if absent."""
    enricher = plugin_dir / "agents" / "spec-enricher.md"
    if not enricher.exists():
        return None
    text = enricher.read_text(encoding="utf-8")
    m = re.search(r'\[([A-Z]+)-\d+\]', text)
    return m.group(1) if m else None


def check_no_baseline_path_refs(plugin_dir):
    """(f) No 'accelerator/ai-baseline' path refs in any agent/skill/command file."""
    errors = []
    for subdir in ("agents", "skills", "commands"):
        d = plugin_dir / subdir
        if not d.exists():
            continue
        for mdfile in d.rglob("*.md"):
            text = mdfile.read_text(encoding="utf-8", errors="replace")
            if "accelerator/ai-baseline" in text:
                rel = mdfile.relative_to(REPO_ROOT)
                errors.append(f"{rel} contains 'accelerator/ai-baseline' path ref")
    return errors


def extract_frontmatter(text):
    """Extract YAML frontmatter block if present (between leading --- delimiters)."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return ""
    fm_lines = []
    for line in lines[1:]:
        if line.strip() == "---":
            break
        fm_lines.append(line)
    return "\n".join(fm_lines)


def check_model_ids(plugin_dir):
    """(g) Model IDs in frontmatter must be limited to the three current ones."""
    errors = []
    for subdir in ("agents", "skills", "commands"):
        d = plugin_dir / subdir
        if not d.exists():
            continue
        for mdfile in d.rglob("*.md"):
            text = mdfile.read_text(encoding="utf-8", errors="replace")
            frontmatter = extract_frontmatter(text)
            for line in frontmatter.splitlines():
                m = re.match(r'^model:\s*(.+)$', line.strip())
                if m:
                    model_val = m.group(1).strip()
                    # Strip inline comments
                    model_val = re.sub(r'\s*#.*$', '', model_val).strip()
                    if model_val and model_val not in ALLOWED_MODELS:
                        rel = mdfile.relative_to(REPO_ROOT)
                        errors.append(f"{rel}: unknown model ID '{model_val}'")
    return errors


# ── Fleet-wide checks ─────────────────────────────────────────────────────────

def check_command_name_collisions(plugin_dirs):
    """(h) No two plugins may define the same command filename.

    Returns a list of (plugin_name, error_string) tuples — one per offending plugin.
    """
    # Map: command_stem -> list of plugin_names that define it
    command_owners = defaultdict(list)
    for pdir in plugin_dirs:
        cmd_dir = pdir / "commands"
        if not cmd_dir.exists():
            continue
        for f in cmd_dir.iterdir():
            if f.suffix == ".md":
                command_owners[f.name].append(pdir.name)

    # Collect errors per plugin
    per_plugin_errors = defaultdict(list)
    for cmd_name, owners in sorted(command_owners.items()):
        if len(owners) > 1:
            others = [o for o in owners]
            for plugin in others:
                per_plugin_errors[plugin].append(
                    f"command '{cmd_name}' also defined in: {[o for o in others if o != plugin]}"
                )
    return per_plugin_errors


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    plugin_dirs = find_plugin_dirs()

    results = {}  # name -> {'kind': ..., 'checks': [(label, errors_list), ...]}
    prefix_registry = {}  # prefix -> plugin_name

    for pdir in plugin_dirs:
        name = pdir.name
        pjson = pdir / ".claude-plugin" / "plugin.json"
        try:
            data = json.loads(pjson.read_text(encoding="utf-8"))
        except Exception as exc:
            results[name] = {"kind": "unknown", "checks": [("parse plugin.json", [str(exc)])]}
            continue

        kind = classify_kind(name, data)
        checks = []

        # (a) Manifest check — all plugins
        checks.append(("manifest fields", check_manifest(name, data)))

        if kind == "build-tool":
            # (d) Build tools must not have enricher
            checks.append(("no spec-enricher (build-tool)", check_no_enricher_build_tool(pdir)))
        elif name == SUBSTRATE:
            # ai-baseline is validated specially — no enricher requirement, no requires
            pass
        else:
            # Runtime plugin checks
            # (b) requires
            checks.append(("requires ai-baseline", check_requires(name, data)))
            # (c) baseline files
            checks.append(("baseline files present + no drift", check_baseline_files(pdir)))
            # (d) spec-enricher conformance
            checks.append(("spec-enricher conformance", check_spec_enricher(pdir)))
            # Track prefix for (e)
            prefix = extract_enricher_prefix(pdir)
            if prefix is not None:
                if prefix in prefix_registry:
                    other = prefix_registry[prefix]
                    checks.append(("prefix uniqueness", [f"prefix '{prefix}' collides with {other}"]))
                else:
                    prefix_registry[prefix] = name

        # (f) No accelerator/ai-baseline refs
        checks.append(("no ai-baseline path refs", check_no_baseline_path_refs(pdir)))

        # (g) Model IDs
        if name != SUBSTRATE:
            checks.append(("model IDs", check_model_ids(pdir)))

        results[name] = {"kind": kind, "checks": checks}

    # (h) Fleet-wide: command-name collision check
    collision_errors = check_command_name_collisions(plugin_dirs)
    for name, errors in collision_errors.items():
        if name not in results:
            # Plugin dir found but no plugin.json — edge case
            results[name] = {"kind": "unknown", "checks": []}
        results[name]["checks"].append(("command-name collision", errors))

    # ── Print table ───────────────────────────────────────────────────────────
    total_fail = 0
    total_pass = 0

    print("=" * 80)
    print("FLEET VALIDATOR — per-plugin report")
    print("=" * 80)

    for name in sorted(results):
        r = results[name]
        kind = r["kind"]
        checks = r["checks"]

        all_errors = []
        for label, errors in checks:
            all_errors.extend(errors)

        status = "PASS" if not all_errors else "FAIL"
        if status == "PASS":
            total_pass += 1
        else:
            total_fail += 1

        print(f"\n[{status}] {name}  ({kind})")
        for label, errors in checks:
            if errors:
                for err in errors:
                    print(f"  FAIL  [{label}] {err}")
            else:
                print(f"  OK    [{label}]")

    print()
    print("=" * 80)
    print(f"TOTAL: {total_pass + total_fail} plugins  |  PASS: {total_pass}  |  FAIL: {total_fail}")
    print("=" * 80)

    if total_fail > 0:
        print("\nFAIL — fleet has violations.")
        return 1

    print("\nGREEN — all fleet invariants satisfied.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
