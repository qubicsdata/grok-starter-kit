#!/usr/bin/env python3
"""
cost-units.py — cost-weighted roll-up of an audit JSONL.

Operationalizes BENCHMARK-CONVENTIONS.md §1 ("report COST-weighted first, token-count
second") and §3 ("count dispatches"). Reads the enriched audit records (model + tokens
now populated by audit_append.py) and prints the cost scoreboard so a benchmark stops
hand-rolling the arithmetic and cannot accidentally lead with raw token count.

Read-only. Pure stdlib.

Usage:
    python3 tools/cost-units.py                      # newest .ai-baseline/audit.*.jsonl
    python3 tools/cost-units.py --file path.jsonl    # a captured benchmark log
    python3 tools/cost-units.py --by plugin          # group: agent|plugin|model|session
"""

from __future__ import annotations

import glob
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Relative price weights (× Sonnet), blended input+output, per BENCHMARK-CONVENTIONS.md §1.
# One blended weight per tier is the sanctioned approximation; tokens_in already excludes
# cheap cache-read tokens (see transcript_usage.py).
TIER_WEIGHTS = {"opus": 5.0, "sonnet": 1.0, "haiku": 0.25}


def model_tier(model: str | None) -> str | None:
    if not model:
        return None
    m = model.lower()
    for tier in ("opus", "sonnet", "haiku"):
        if tier in m:
            return tier
    return None


def cost_units(records: list[dict]) -> dict:
    total_cost = 0.0
    total_tokens = 0
    dispatches = 0
    by_model: dict[str, dict] = {}
    for r in records:
        toks = (r.get("tokens_in") or 0) + (r.get("tokens_out") or 0)
        model = r.get("model")
        weight = TIER_WEIGHTS.get(model_tier(model), 0.0)
        cost = toks * weight
        total_cost += cost
        total_tokens += toks
        if model and toks:
            dispatches += 1
        if model:
            bm = by_model.setdefault(model, {"tokens": 0, "cost_units": 0.0, "dispatches": 0})
            bm["tokens"] += toks
            bm["cost_units"] = round(bm["cost_units"] + cost, 1)
            if toks:
                bm["dispatches"] += 1
    return {"cost_units": round(total_cost, 1), "tokens": total_tokens,
            "dispatches": dispatches, "by_model": by_model}


def group_by(records: list[dict], field: str) -> dict:
    groups: dict[str, list] = {}
    for r in records:
        groups.setdefault(r.get(field) or "(none)", []).append(r)
    return {k: cost_units(v) for k, v in groups.items()}


def load_records(path: str) -> list[dict]:
    recs = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            recs.append(json.loads(line))
        except Exception:
            continue
    return recs


def _default_file() -> str | None:
    matches = sorted(glob.glob(str(REPO_ROOT / ".ai-baseline" / "audit.*.jsonl")))
    return matches[-1] if matches else None


def main(argv: list[str]) -> int:
    path = None
    by = None
    i = 1
    while i < len(argv):
        if argv[i] == "--file" and i + 1 < len(argv):
            path = argv[i + 1]; i += 2
        elif argv[i] == "--by" and i + 1 < len(argv):
            by = argv[i + 1]; i += 2
        else:
            print(__doc__); return 2
    if path is None:
        path = _default_file()
        if path is None:
            print("no audit log found (.ai-baseline/audit.*.jsonl); pass --file", file=sys.stderr)
            return 1

    records = load_records(path)
    print(f"audit log: {path}  ({len(records)} record(s))")
    print(f"weights (x Sonnet): opus={TIER_WEIGHTS['opus']} sonnet={TIER_WEIGHTS['sonnet']} haiku={TIER_WEIGHTS['haiku']}")

    if by:
        print(f"\n— grouped by {by} —")
        groups = group_by(records, by)
        for k in sorted(groups, key=lambda x: groups[x]["cost_units"], reverse=True):
            g = groups[k]
            print(f"  {k:28} cost_units={g['cost_units']:>12,.1f}  tokens={g['tokens']:>12,}  dispatches={g['dispatches']}")

    out = cost_units(records)
    print("\n=== TOTAL ===")
    print(f"  cost_units (PRIMARY): {out['cost_units']:,.1f}")
    print(f"  tokens (secondary):   {out['tokens']:,}")
    print(f"  dispatches:           {out['dispatches']}")
    print("  by model:")
    for model, bm in sorted(out["by_model"].items(), key=lambda kv: kv[1]["cost_units"], reverse=True):
        print(f"    {model:32} cost_units={bm['cost_units']:>12,.1f}  tokens={bm['tokens']:>12,}  dispatches={bm['dispatches']}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
