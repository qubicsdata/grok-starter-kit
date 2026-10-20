#!/usr/bin/env python3
"""
check-scenario-coverage.py — Scenario coverage checker for the accelerator fleet.

For every plugin that has tests/behavioral-scenarios.md:
  - Counts scenarios (normalises both heading styles: '### ' and '## Scenario ')
  - Reports the per-plugin count
  - Flags plugins with 0 scenarios (EXIT NON-ZERO)

Also computes a basic coverage heuristic: for each plugin agent file that
contains hard-gate lines (NEVER / STOP / DO NOT), check whether the
scenarios file mentions that agent's name or a relevant gate keyword.

Usage:
    python3 tools/check-scenario-coverage.py
"""

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

NON_PLUGIN_DIRS = {"docs", "benchmarks", "tools", ".git", "ai-baseline"}

HARD_GATE_PATTERN = re.compile(r'\b(NEVER|STOP|DO NOT)\b')

# Heading patterns that count as a scenario:
#   1. '### <anything>'          (level-3 heading)
#   2. '## Scenario <anything>'  (level-2 heading starting with "Scenario")
SCENARIO_HEADING_RE = re.compile(
    r'^(### .+|## Scenario .+)',
    re.MULTILINE,
)


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


def count_scenarios(scenarios_path: Path) -> int:
    text = scenarios_path.read_text(encoding="utf-8")
    matches = SCENARIO_HEADING_RE.findall(text)
    return len(matches)


def find_agent_hard_gates(plugin_dir: Path) -> dict[str, list[str]]:
    """Return {agent_name: [gate_lines]} for agents with hard-gate lines."""
    result = {}
    agents_dir = plugin_dir / "agents"
    if not agents_dir.exists():
        return result
    for agent_file in sorted(agents_dir.glob("*.md")):
        text = agent_file.read_text(encoding="utf-8", errors="replace")
        gate_lines = [
            line.strip()
            for line in text.splitlines()
            if HARD_GATE_PATTERN.search(line)
        ]
        if gate_lines:
            result[agent_file.stem] = gate_lines
    return result


def coverage_heuristic(scenarios_text: str, agent_name: str, gate_lines: list[str]) -> str:
    """
    Simple heuristic: does the scenarios file mention the agent name?
    If yes → COVERED. If no → UNCOVERED.
    """
    # Check agent name mention (e.g. 'schema-reviewer' in scenarios text)
    if agent_name.lower() in scenarios_text.lower():
        return "COVERED"
    # Check if any distinctive keyword from gate_lines appears
    for line in gate_lines:
        # Extract key nouns/verbs from gate lines (simplified: last word of NEVER/STOP/DO NOT clause)
        words = re.findall(r'\b[a-z]{4,}\b', line.lower())
        for word in words:
            if word not in {"never", "stop", "before", "after", "every", "agent", "output", "input",
                            "write", "disk", "with", "from", "this", "that", "into", "when", "does",
                            "file", "path", "user", "data", "make", "read", "only", "also", "each"}:
                if word in scenarios_text.lower():
                    return "COVERED (keyword)"
    return "UNCOVERED"


def main() -> int:
    plugin_dirs = find_plugin_dirs()

    print("=" * 70)
    print("SCENARIO COVERAGE CHECKER")
    print("=" * 70)

    zero_scenario_plugins = []
    total_plugins_checked = 0
    total_scenarios = 0

    for pdir in plugin_dirs:
        name = pdir.name
        scenarios_path = pdir / "tests" / "behavioral-scenarios.md"

        if not scenarios_path.exists():
            print(f"\n[SKIP] {name}: no tests/behavioral-scenarios.md")
            continue

        total_plugins_checked += 1
        count = count_scenarios(scenarios_path)
        total_scenarios += count
        scenarios_text = scenarios_path.read_text(encoding="utf-8")

        status = "OK" if count > 0 else "ZERO"
        print(f"\n[{status}] {name}: {count} scenario(s)")

        if count == 0:
            zero_scenario_plugins.append(name)
            print(f"  WARNING: 0 scenarios detected — check heading style")
            print(f"  Expected: '### <Title>' or '## Scenario <N>: ...'")
            # Show first 3 headings to help debug
            lines = scenarios_text.splitlines()
            heading_lines = [l for l in lines if l.startswith("#")][:5]
            for hl in heading_lines:
                print(f"  Found heading: {hl!r}")
            continue

        # Coverage heuristic
        agent_gates = find_agent_hard_gates(pdir)
        if agent_gates:
            covered = 0
            uncovered_agents = []
            for agent_name, gate_lines in agent_gates.items():
                verdict = coverage_heuristic(scenarios_text, agent_name, gate_lines)
                if verdict.startswith("COVERED"):
                    covered += 1
                else:
                    uncovered_agents.append(agent_name)
            total_agents = len(agent_gates)
            pct = int(100 * covered / total_agents) if total_agents > 0 else 0
            print(f"  Coverage heuristic: {covered}/{total_agents} agents with hard-gates mentioned ({pct}%)")
            if uncovered_agents:
                print(f"  Possibly uncovered agents: {', '.join(uncovered_agents)}")
        else:
            print(f"  Coverage heuristic: no agents with hard-gate lines found")

    print()
    print("=" * 70)
    print(f"SUMMARY: {total_plugins_checked} plugin(s) checked | {total_scenarios} total scenario(s)")
    print("=" * 70)

    if zero_scenario_plugins:
        print(f"\nFAIL — {len(zero_scenario_plugins)} plugin(s) have 0 scenarios: {zero_scenario_plugins}")
        print("Fix: ensure headings use '### <Title>' or '## Scenario N: ...' style.")
        return 1

    print("\nPASS — all plugins have at least 1 scenario.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
