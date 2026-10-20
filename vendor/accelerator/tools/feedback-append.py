#!/usr/bin/env python3
"""
feedback-append.py — append-only writer for .ai-evolution/feedback.jsonl.

Closes the self-evolution loop's data path (previously the file never existed). Two
entry kinds, per self-evolution-companion/skills/feedback-schema.md:

  - review-efficacy (8 fields): emitted by the review machinery — pure booleans/numbers,
    NO LLM. Drives /refine tier auto-demotion (a tier that never `paid` demotes itself).
  - quality (9 fields): emitted by /score-pending after the quality-scorer agent runs.

Deterministic, stdlib, append-only. Validates field shapes (rejecting malformed entries
keeps the journal trustworthy and injection-free — efficacy entries carry no free text).

CLI (for the review agents):
    python3 tools/feedback-append.py efficacy --tier full --found-critical true \
        --found-important false --score-delta 0 --session <id>
    python3 tools/feedback-append.py quality --agent memory-writer --completeness 8 \
        --safety 10 --accuracy 9 --reasoning "..." --session <id>
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
VALID_TIERS = {"light", "standard", "full"}


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def _path(path=None) -> Path:
    return Path(path) if path else REPO_ROOT / ".ai-evolution" / "feedback.jsonl"


def _append(entry: dict, path) -> dict:
    p = _path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, separators=(",", ":")) + "\n")
    return entry


def append_efficacy(tier, found_critical, found_important, score_delta,
                    session_id="unknown", path=None) -> dict:
    if tier not in VALID_TIERS:
        raise ValueError(f"tier must be one of {sorted(VALID_TIERS)}, got {tier!r}")
    fc, fi = bool(found_critical), bool(found_important)
    try:
        sd = float(score_delta)
    except (TypeError, ValueError):
        raise ValueError(f"score_delta must be numeric, got {score_delta!r}")
    entry = {
        "ts": _now(),
        "kind": "review-efficacy",
        "tier": tier,
        "found_critical": fc,
        "found_important": fi,
        "score_delta": sd,
        "paid": fc or fi or sd > 0,
        "session_id": session_id or "unknown",
    }
    return _append(entry, path)


def append_quality(agent, completeness, safety, accuracy, reasoning,
                   session_id="unknown", scorer="quality-scorer", path=None) -> dict:
    for name, v in (("completeness", completeness), ("safety", safety), ("accuracy", accuracy)):
        if not isinstance(v, int) or not (0 <= v <= 10):
            raise ValueError(f"{name} must be an int 0-10, got {v!r}")
    overall = round((completeness + safety + accuracy) / 3, 1)
    entry = {
        "ts": _now(),
        "agent": agent,
        "completeness": completeness,
        "safety": safety,
        "accuracy": accuracy,
        "overall": overall,
        "reasoning": reasoning,
        "session_id": session_id or "unknown",
        "scorer": scorer,
    }
    return _append(entry, path)


def _as_bool(s: str) -> bool:
    return str(s).strip().lower() in {"1", "true", "yes", "y"}


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Append a feedback entry")
    sub = parser.add_subparsers(dest="kind", required=True)

    e = sub.add_parser("efficacy")
    e.add_argument("--tier", required=True)
    e.add_argument("--found-critical", required=True)
    e.add_argument("--found-important", required=True)
    e.add_argument("--score-delta", default="0")
    e.add_argument("--session", default="unknown")

    q = sub.add_parser("quality")
    q.add_argument("--agent", required=True)
    q.add_argument("--completeness", type=int, required=True)
    q.add_argument("--safety", type=int, required=True)
    q.add_argument("--accuracy", type=int, required=True)
    q.add_argument("--reasoning", required=True)
    q.add_argument("--session", default="unknown")

    args = parser.parse_args(argv[1:])
    try:
        if args.kind == "efficacy":
            entry = append_efficacy(args.tier, _as_bool(args.found_critical),
                                    _as_bool(args.found_important), args.score_delta,
                                    session_id=args.session)
        else:
            entry = append_quality(args.agent, args.completeness, args.safety,
                                   args.accuracy, args.reasoning, session_id=args.session)
    except ValueError as exc:
        print(f"FEEDBACK_REJECTED: {exc}", file=sys.stderr)
        return 1
    print(f"FEEDBACK_OK: {entry['kind'] if 'kind' in entry else 'quality'}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
