#!/usr/bin/env python3
"""Stdlib tests for tools/run-scenarios.py static heuristics. Run directly.

Locks the false-positive fixes (2026-07-03): a file the run *produces* is a live-run
output (MANUAL), not a static precondition; a prose "in the <word>" is not a file check.
"""
import importlib.util
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
_spec = importlib.util.spec_from_file_location("rs", REPO / "tools" / "run-scenarios.py")
rs = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rs)

failures = []


def check(name, cond):
    print(("PASS " if cond else "FAIL ") + name)
    if not cond:
        failures.append(name)


def verdict(pc):
    return rs.try_static_assert(pc, REPO)[0]


# Output-file phrasing must be MANUAL, not a false FILE_EXISTS FAIL.
check("output-file (scaffolded) -> MANUAL",
      verdict("A model card is scaffolded at `.compliance/model-cards/agent.md`.") == "MANUAL")
check("output-file (written) -> MANUAL",
      verdict("An entry is written to `.ai-memory/ns/k.json`.") == "MANUAL")
check("output dir (mined-patterns, no leading dot) -> MANUAL",
      verdict("The catalog is written to `mined-patterns/proj.md`.") == "MANUAL")
check("output-file (generated .accelerator-workspace.yaml) -> MANUAL",
      verdict("A `.accelerator-workspace.yaml` is generated at the root.") == "MANUAL")
# Prose "in the <word>" must not be treated as a file check.
check("prose 'present in the recommendation' -> MANUAL",
      verdict('"DATAMODEL-D-2" is present in the recommendation.') == "MANUAL")
# A real committed file with a real grep pass-condition should PASS.
check("real grep on a committed file -> PASS",
      verdict('`grep "ai-baseline" registry.json` hits.') == "PASS")
# No pass-condition -> MANUAL (honest, not a silent pass).
check("empty pass-condition -> MANUAL", verdict("") == "MANUAL")

sys.exit(1 if failures else 0)
