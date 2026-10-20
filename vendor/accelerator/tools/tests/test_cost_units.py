#!/usr/bin/env python3
"""Golden tests for tools/cost-units.py. Run: python3 tools/tests/test_cost_units.py"""
import importlib.util
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
FIX = str(REPO / "tools" / "tests" / "audit-fixtures" / "sample-audit.jsonl")

spec = importlib.util.spec_from_file_location("cost_units_mod", REPO / "tools" / "cost-units.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def test_golden_totals():
    # opus 1200 tok x5 = 6000 ; sonnet 600 x1 = 600 ; haiku 400 x0.25 = 100 ; null = 0
    recs = mod.load_records(FIX)
    out = mod.cost_units(recs)
    assert out["cost_units"] == 6700.0, out
    assert out["tokens"] == 2200, out
    assert out["dispatches"] == 3, out          # null-model record is not a dispatch
    assert set(out["by_model"]) == {"claude-opus-4-8", "claude-sonnet-4-6", "claude-haiku-4-5-20251001"}, out


def test_group_by_plugin():
    recs = mod.load_records(FIX)
    g = mod.group_by(recs, "plugin")
    assert g["dev-companion"]["cost_units"] == 6600.0, g       # opus 6000 + sonnet 600
    assert g["api-designer"]["cost_units"] == 100.0, g
    assert g["(none)"]["cost_units"] == 0.0, g


def test_unknown_model_weighted_zero_not_crash():
    out = mod.cost_units([{"model": "gpt-4", "tokens_in": 100, "tokens_out": 100}])
    assert out["cost_units"] == 0.0, out
    assert out["tokens"] == 200, out


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"PASS {t.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"FAIL {t.__name__}: {e}")
        except Exception as e:
            failed += 1
            print(f"ERROR {t.__name__}: {type(e).__name__}: {e}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    sys.exit(1 if failed else 0)
