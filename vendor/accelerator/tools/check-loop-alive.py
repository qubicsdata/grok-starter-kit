#!/usr/bin/env python3
"""
check-loop-alive.py — theater detector for the self-evolution loop (2026-07-03).

The loop stayed empty through two "fix" programs because the review-efficacy wire was
present in prose but (a) not required at any gate and (b) marked best-effort /
skip-silently, so it never fired and no one noticed. This gate asserts the loop is
genuinely wired AND enforced, so a future refactor cannot silently disconnect it again.

Three assertions:
  1. WRITE PATH works end-to-end — feedback-append produces a valid 8-field
     review-efficacy entry with correct `paid`, and rejects malformed input.
  2. GATE enforces it — check-builder-session --require publish BLOCKS a session that
     lacks or skips the `efficacy journaled` checkpoint.
  3. WIRE present and NOT optional — the builder orchestrator and the accelerate arc
     both invoke the emitter, and each carries its "required / not best-effort" marker.

Exit 0 = loop alive; 1 = a wire is missing or unenforced.
"""
import importlib.util
import json
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def _load(name, rel):
    spec = importlib.util.spec_from_file_location(name, REPO / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main() -> int:
    failures = []

    def check(name, cond):
        print(("PASS " if cond else "FAIL ") + name)
        if not cond:
            failures.append(name)

    # 1. WRITE PATH — the emitter actually produces valid entries.
    fa = _load("feedback_append", "tools/feedback-append.py")
    with tempfile.TemporaryDirectory() as td:
        jp = Path(td) / "feedback.jsonl"
        fa.append_efficacy("full", False, False, 0, session_id="t1", path=jp)      # not paid
        fa.append_efficacy("standard", False, True, 0, session_id="t2", path=jp)   # paid
        lines = jp.read_text(encoding="utf-8").strip().splitlines()
        check("write-path: two entries appended", len(lines) == 2)
        rec1, rec2 = json.loads(lines[0]), json.loads(lines[1])
        check("write-path: 8-field review-efficacy entry",
              len(rec1) == 8 and rec1.get("kind") == "review-efficacy")
        check("write-path: paid=false when nothing found", rec1.get("paid") is False)
        check("write-path: paid=true on an important finding", rec2.get("paid") is True)
        rejected = False
        try:
            fa.append_efficacy("bogus-tier", False, False, 0, path=jp)
        except ValueError:
            rejected = True
        check("write-path: malformed tier rejected", rejected)

    # 2. GATE — the publish validator refuses a session that skips/omits efficacy.
    cfs = _load("cfs", "tools/check-builder-session.py")
    fx = REPO / "tools" / "tests" / "builder-session-fixtures"
    missing = (fx / "missing-efficacy.md").read_text(encoding="utf-8")
    skipped = (fx / "efficacy-skipped.md").read_text(encoding="utf-8")
    check("gate: publish blocks a session missing efficacy",
          any("efficacy" in f for f in cfs.validate(missing, "publish")))
    check("gate: publish rejects 'efficacy skipped' in-repo",
          any("efficacy" in f for f in cfs.validate(skipped, "publish")))
    check("gate: 'efficacy journaled' is a canonical checkpoint",
          "efficacy journaled" in cfs.CANONICAL)

    # 3. WIRE — the emit is present in the controllers and marked required, not optional.
    orch = (REPO / "agent-builder/agents/builder-orchestrator.md").read_text(encoding="utf-8")
    check("wire: builder orchestrator invokes the efficacy emitter",
          "feedback-append.py efficacy" in orch)
    check("wire: builder efficacy step marked required (NOT best-effort)",
          "NOT best-effort" in orch and "REQUIRED" in orch)

    arc = (REPO / "ai-baseline/skills/accelerate-arc.md").read_text(encoding="utf-8")
    check("wire: accelerate arc invokes the efficacy emitter",
          "feedback-append.py efficacy" in arc)
    check("wire: arc efficacy section marked required, non-silent",
          "required, non-silent" in arc)

    # 4. QUALITY-CAPTURE half — the Stop hook deterministically queues a pending stub for
    # scoreable subagents (the other half of the loop). Guard it against silent removal too.
    hook = (REPO / "ai-baseline/hooks/scripts/audit_append.py").read_text(encoding="utf-8")
    check("quality-wire: Stop hook queues pending stubs for scoreable subagents",
          "feedback.jsonl.pending" in hook and "is_scoreable(" in hook)
    sa = (REPO / "ai-baseline/hooks/scripts/scoreable_agents.py").read_text(encoding="utf-8")
    check("quality-wire: scoreable filter present", "def is_scoreable" in sa)

    print("LOOP-ALIVE " + ("PASS" if not failures else f"FAIL ({len(failures)} finding(s))"))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
