#!/usr/bin/env python3
"""
check-baseline-coverage.py — audit every */agents/*.md file to confirm
the baseline-enforcer import line is present.

Classification per agent:
  IMPORTS_BASELINE   — contains the verbatim import line (either variant)
  EXEMPT_SPEC_ENRICHER — filename is spec-enricher.md (dispatched by
                         enrich-orchestrator which carries the baseline)
  EXEMPT_BASELINE_COPY — verbatim ai-baseline copy: audit-trail-agent.md,
                         cost-gate-agent.md, pii-scrub-agent.md,
                         context-manager-agent.md (infra agents)
  MISSING            — output-emitting agent with no import line

Exits 0 if MISSING == 0; exits 1 otherwise.

Usage:
    python3 tools/check-baseline-coverage.py
"""

import sys
from pathlib import Path
from collections import defaultdict

REPO_ROOT = Path(__file__).resolve().parent.parent

# Top-level plugin directories to EXCLUDE entirely
EXCLUDE_PLUGINS = {"ai-baseline", "benchmarks", ".git", "tools", "docs", ".claude"}

# Import line variants that count as coverage
IMPORT_PHRASES = [
    "Import the baseline-enforcer skill at session start and before any output or Opus call.",
    "Import the baseline-enforcer skill at session start and before any output.",
]

# Filenames that are verbatim ai-baseline infrastructure copies — exempt
VERBATIM_BASELINE_COPIES = {
    "audit-trail-agent.md",
    "cost-gate-agent.md",
    "pii-scrub-agent.md",
    "context-manager-agent.md",
}

# Filename that is the spec-enricher archetype — exempt (dispatched by enrich-orchestrator)
SPEC_ENRICHER_FILENAME = "spec-enricher.md"


def classify(path: Path) -> str:
    filename = path.name

    if filename == SPEC_ENRICHER_FILENAME:
        return "EXEMPT_SPEC_ENRICHER"

    if filename in VERBATIM_BASELINE_COPIES:
        return "EXEMPT_BASELINE_COPY"

    text = path.read_text(encoding="utf-8", errors="replace")
    for phrase in IMPORT_PHRASES:
        if phrase in text:
            return "IMPORTS_BASELINE"

    return "MISSING"


def collect_agents() -> list[Path]:
    """Collect every */agents/*.md (including panel subdirs) excluding exempt plugins."""
    agents = []
    for md in REPO_ROOT.rglob("*.md"):
        rel = md.relative_to(REPO_ROOT)
        parts = rel.parts
        # Skip if any top-level part is an excluded plugin
        if parts[0] in EXCLUDE_PLUGINS:
            continue
        # Must be under an agents/ directory at some level
        if "agents" not in parts:
            continue
        agents.append(md)
    return sorted(agents)


def main() -> int:
    agents = collect_agents()

    by_plugin: dict[str, list[tuple[str, Path]]] = defaultdict(list)
    for path in agents:
        plugin = path.relative_to(REPO_ROOT).parts[0]
        status = classify(path)
        by_plugin[plugin].append((status, path))

    # Print per-plugin table
    total_missing = 0
    missing_paths: list[str] = []

    print("=" * 70)
    print("BASELINE COVERAGE AUDIT")
    print("=" * 70)

    for plugin in sorted(by_plugin):
        rows = by_plugin[plugin]
        plugin_missing = [(s, p) for s, p in rows if s == "MISSING"]
        total_missing += len(plugin_missing)
        print(f"\nPlugin: {plugin}")
        print(f"  {'STATUS':<25} FILE")
        for status, path in rows:
            rel = str(path.relative_to(REPO_ROOT))
            mark = "OK" if status != "MISSING" else "MISSING"
            label = {
                "IMPORTS_BASELINE": "IMPORTS_BASELINE",
                "EXEMPT_SPEC_ENRICHER": "EXEMPT (spec-enricher)",
                "EXEMPT_BASELINE_COPY": "EXEMPT (baseline copy)",
                "MISSING": ">>> MISSING <<<",
            }[status]
            print(f"  {label:<25} {rel}")
        if plugin_missing:
            for _, p in plugin_missing:
                missing_paths.append(str(p.relative_to(REPO_ROOT)))

    print()
    print("=" * 70)
    print(f"TOTAL AGENTS SCANNED : {len(agents)}")
    print(f"MISSING              : {total_missing}")
    print("=" * 70)

    if total_missing > 0:
        print("\nMISSING WORKLIST:")
        for p in missing_paths:
            print(f"  {p}")
        print("\nFAIL — add the import line to every MISSING agent.")
        return 1

    print("\nPASS — all output-emitting agents import baseline-enforcer.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
