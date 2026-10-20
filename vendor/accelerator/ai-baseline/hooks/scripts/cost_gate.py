#!/usr/bin/env python3
"""
cost_gate.py — PreToolUse hook for Task tool calls.

Checks if the dispatched agent targets an Opus model. If not Opus, exits 0 silently.
If Opus, reads .ai-baseline/budget.json (spent_usd is accrued there by
audit_append.py from per-dispatch transcript usage):

- limit_usd null or absent -> measurement mode: spend is tracked but the gate
  NEVER blocks (fail-open by design; set a numeric limit to arm the gate).
- limit_usd numeric and spent_usd >= limit_usd -> prints deny JSON, exits 0.

Fail-open for a missing budget.json (backwards-compatible).
Fail-closed on script error when on the Opus path (exit 2 + stderr) —
a broken gate must not silently allow unbounded Opus spend.

Usage:
    echo '<hook-json>' | python3 tools/hooks/cost_gate.py
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _hooklib import get_repo_root, read_stdin_json, deny_response


def is_opus(payload: dict) -> bool:
    """Return True if the task targets an Opus model."""
    tool_input = payload.get("tool_input", {})
    model = tool_input.get("model", "") or ""
    subagent_type = tool_input.get("subagent_type", "") or ""
    combined = f"{model} {subagent_type}".lower()
    return "opus" in combined


def main() -> int:
    payload = read_stdin_json()
    if payload is None:
        # Could not parse stdin — fail-open (non-Opus path semantics; we can't know)
        sys.stderr.write("[cost_gate] warning: could not parse stdin JSON — allowing\n")
        return 0

    try:
        if not is_opus(payload):
            # Not targeting Opus — no-op
            return 0

        # On Opus path: check budget
        repo_root = get_repo_root()
        budget_file = Path(repo_root) / ".ai-baseline" / "budget.json"

        if not budget_file.exists():
            # Missing budget.json → fail-open (backwards-compatible)
            return 0

        with open(budget_file, "r", encoding="utf-8") as fh:
            budget = json.load(fh)

        limit_usd = budget.get("limit_usd")
        if limit_usd is None:
            # null (or absent) limit -> measurement mode: never block
            return 0
        limit_usd = float(limit_usd)
        spent_usd = float(budget.get("spent_usd") or 0)

        if spent_usd >= limit_usd:
            reason = (
                f"cost-gate: session budget exceeded (spent ${spent_usd:.2f} of ${limit_usd:.2f}). "
                f"Raise the limit in .ai-baseline/budget.json or review spend."
            )
            system_msg = "baseline cost-gate blocked an Opus dispatch (budget exceeded)"
            print(deny_response("PreToolUse", reason, system_msg))
            return 0

        # Budget OK — allow
        return 0

    except Exception as exc:
        # FAIL-CLOSED on Opus path: a broken gate must not silently allow unbounded spend
        sys.stderr.write(f"[cost_gate] error: gate script error on Opus path — blocking: {exc}\n")
        return 2


if __name__ == "__main__":
    sys.exit(main())
