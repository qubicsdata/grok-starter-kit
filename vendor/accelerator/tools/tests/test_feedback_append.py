#!/usr/bin/env python3
"""Tests for tools/feedback-append.py. Run: python3 tools/tests/test_feedback_append.py"""
import importlib.util
import json
import os
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
spec = importlib.util.spec_from_file_location("feedback_append_mod", REPO / "tools" / "feedback-append.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def _tmp():
    fd, p = tempfile.mkstemp(suffix=".jsonl")
    os.close(fd)
    os.unlink(p)  # start absent so we test dir/file creation
    return p


def test_efficacy_8_fields_paid_true():
    p = _tmp()
    e = mod.append_efficacy("full", found_critical=True, found_important=False, score_delta=0, session_id="s1", path=p)
    assert set(e) == {"ts", "kind", "tier", "found_critical", "found_important", "score_delta", "paid", "session_id"}, e
    assert e["kind"] == "review-efficacy" and e["paid"] is True, e
    lines = Path(p).read_text().strip().splitlines()
    assert len(lines) == 1 and json.loads(lines[0])["tier"] == "full"


def test_efficacy_paid_false_when_nothing_found():
    p = _tmp()
    e = mod.append_efficacy("light", found_critical=False, found_important=False, score_delta=0.0, session_id="s", path=p)
    assert e["paid"] is False, e


def test_quality_9_fields_overall_computed():
    p = _tmp()
    e = mod.append_quality("memory-writer", completeness=8, safety=10, accuracy=9, reasoning="ok", session_id="s", path=p)
    assert set(e) == {"ts", "agent", "completeness", "safety", "accuracy", "overall", "reasoning", "session_id", "scorer"}, e
    assert e["overall"] == 9.0 and e["scorer"] == "quality-scorer", e


def test_invalid_tier_rejected():
    try:
        mod.append_efficacy("bogus", False, False, 0, path=_tmp())
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_quality_out_of_range_rejected():
    try:
        mod.append_quality("a", completeness=11, safety=5, accuracy=5, reasoning="x", path=_tmp())
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_append_only_preserves_prior():
    p = _tmp()
    mod.append_efficacy("standard", True, False, 1.0, path=p)
    mod.append_quality("a", 5, 5, 5, "r", path=p)
    lines = Path(p).read_text().strip().splitlines()
    assert len(lines) == 2, lines
    assert json.loads(lines[0])["kind"] == "review-efficacy"
    assert "completeness" in json.loads(lines[1])


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
