#!/usr/bin/env python3
"""Stdlib tests for tools/check-builder-session.py validate(). Run directly."""
import importlib.util
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
_spec = importlib.util.spec_from_file_location("cfs", REPO / "tools" / "check-builder-session.py")
cfs = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cfs)

FX = REPO / "tools" / "tests" / "builder-session-fixtures"
complete = (FX / "complete.md").read_text(encoding="utf-8")
failures = []

def check(name, cond):
    print(("PASS " if cond else "FAIL ") + name)
    if not cond:
        failures.append(name)

check("complete passes publish", cfs.validate(complete, "publish") == [])
check("complete passes design", cfs.validate(complete, "design") == [])
check("design gate does not require gate-2",
      cfs.validate((FX / "missing-gate2.md").read_text(encoding="utf-8"), "design") == [])
check("blocked fails publish",
      any("BLOCKED" in f for f in cfs.validate((FX / "blocked.md").read_text(encoding="utf-8"), "publish")))
check("out-of-order fails",
      any("order" in f for f in cfs.validate((FX / "out-of-order.md").read_text(encoding="utf-8"), "publish")))
check("efficacy skipped is NOT counted as journaled",
      cfs._tokens("- efficacy skipped — t") == [])
check("no Mode line rejected", cfs.validate("# x\n## Checkpoints\n", "design")
      == ["no 'Mode:' line — not a builder session file"])

# Loop-closure enforcement: efficacy MUST be journaled to publish (gate-enforced,
# 2026-07-03 spec). Design gate does not require it; skipping it is a publish BLOCK.
_missing_eff = (FX / "missing-efficacy.md").read_text(encoding="utf-8")
_skipped_eff = (FX / "efficacy-skipped.md").read_text(encoding="utf-8")
check("missing-efficacy fails publish",
      any("efficacy" in f for f in cfs.validate(_missing_eff, "publish")))
check("missing-efficacy passes design (design gate does not require efficacy)",
      cfs.validate(_missing_eff, "design") == [])
check("efficacy-skipped fails publish (skip is not permitted in-repo)",
      any("efficacy" in f for f in cfs.validate(_skipped_eff, "publish")))

blocked_then_cleared = complete.replace(
    "Gate 2: CLEARED",
    "Gate 2: BLOCKED — panel fail unresolved\n\n## Gate 2 — Pre-Publish Reflection (rerun)\n2026-07-02T11:00:00Z\n\n### Panel blockers\nNone\n\n### API safety\nNone flagged\n\n### Version correctness\n1.0.0 initial release\n\nGate 2: CLEARED")
check("blocked-then-cleared passes publish (last-status semantics)",
      cfs.validate(blocked_then_cleared, "publish") == [])
decoy = complete + "\n## Panel Notes\n- critic pass\n"
check("token-like list item outside Checkpoints ignored",
      cfs.validate(decoy, "publish") == [])
esc_override = complete + "\n## Escalation\nCRITIC REVIEW: ESCALATE\n"
check("escalation after last critic pass still fails",
      any("ESCALATE" in f for f in cfs.validate(esc_override, "publish")))

sys.exit(1 if failures else 0)
