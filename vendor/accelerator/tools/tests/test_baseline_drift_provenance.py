#!/usr/bin/env python3
"""Stdlib tests for provenance handling in tools/check-baseline-drift.py."""
import importlib.util
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
_spec = importlib.util.spec_from_file_location("cbd", REPO / "tools" / "check-baseline-drift.py")
cbd = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cbd)

failures = []

def check(name, cond):
    print(("PASS " if cond else "FAIL ") + name)
    if not cond:
        failures.append(name)

STAMP = "<!-- baseline-provenance: ai-baseline v1.0.0 2026-07-02 -->\n"
BODY = "---\nname: baseline-enforcer\n---\ncontent\n"

check("stamped copy strips to source", cbd.strip_provenance(STAMP + BODY) == BODY)
check("unstamped copy unchanged", cbd.strip_provenance(BODY) == BODY)
check("stamp only stripped at line 1", cbd.strip_provenance(BODY + STAMP) == BODY + STAMP)
check("drifted content still differs after strip",
      cbd.strip_provenance(STAMP + BODY + "extra\n") != BODY)

sys.exit(1 if failures else 0)
