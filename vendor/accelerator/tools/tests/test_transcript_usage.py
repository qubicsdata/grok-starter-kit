#!/usr/bin/env python3
"""Stdlib tests for tools/hooks/transcript_usage.py. Run: python3 tools/tests/test_transcript_usage.py"""
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO / "tools" / "hooks"))
FIX = REPO / "tools" / "tests" / "transcript-fixtures" / "sample.jsonl"

from transcript_usage import summarize_since, extract_output  # noqa: E402


def test_main_segment_sums_and_picks_last_model():
    s = summarize_since(str(FIX), after_uuid=None, sidechain_only=False)
    # main turns u1 (input100,cc0 / out50) + u2 (input200,cc20 / out75); cache_read 5 excluded from tokens_in
    assert s["tokens_in"] == 320, s
    assert s["tokens_out"] == 125, s
    assert s["cache_read"] == 5, s
    assert s["model"] == "claude-opus-4-8", s
    assert s["plugin"] == "ai-baseline", s     # last main turn's attribution
    assert s["agent"] == "accelerate-arc", s
    assert s["last_uuid"] == "u2", s


def test_after_uuid_cursor_excludes_prior():
    s = summarize_since(str(FIX), after_uuid="u1", sidechain_only=False)
    # only u2 counted (input200 + cc20 = 220)
    assert s["tokens_in"] == 220, s
    assert s["tokens_out"] == 75, s
    assert s["last_uuid"] == "u2", s


def test_sidechain_only_isolates_subagent():
    s = summarize_since(str(FIX), after_uuid=None, sidechain_only=True)
    assert s["tokens_in"] == 300, s
    assert s["tokens_out"] == 120, s
    assert s["model"] == "claude-sonnet-4-6", s
    assert s["plugin"] == "dev-companion", s
    assert s["agent"] == "security-reviewer", s


def test_missing_file_returns_zeroed_summary():
    s = summarize_since(str(REPO / "nope.jsonl"))
    assert s["tokens_in"] == 0 and s["tokens_out"] == 0 and s["model"] is None, s


def test_malformed_line_is_skipped(tmp_path=None):
    import tempfile, os
    fd, p = tempfile.mkstemp(suffix=".jsonl")
    with os.fdopen(fd, "w") as fh:
        fh.write('{"type":"assistant","isSidechain":false,"uuid":"a","message":{"model":"claude-opus-4-8","usage":{"input_tokens":10,"output_tokens":5}}}\n')
        fh.write('this is not json\n')
    try:
        s = summarize_since(p, sidechain_only=False)
        assert s["tokens_in"] == 10 and s["tokens_out"] == 5, s
    finally:
        os.unlink(p)


def test_by_model_buckets_track_each_tier():
    import tempfile, os, json
    fd, p = tempfile.mkstemp(suffix=".jsonl")
    with os.fdopen(fd, "w") as fh:
        fh.write(json.dumps({"type": "assistant", "isSidechain": False, "uuid": "a",
                             "message": {"model": "claude-opus-4-8",
                                         "usage": {"input_tokens": 100, "cache_creation_input_tokens": 50,
                                                   "output_tokens": 10}}}) + "\n")
        fh.write(json.dumps({"type": "assistant", "isSidechain": False, "uuid": "b",
                             "message": {"model": "claude-haiku-4-5-20251001",
                                         "usage": {"input_tokens": 200, "output_tokens": 20}}}) + "\n")
    try:
        s = summarize_since(p, sidechain_only=False)
        assert s["model"] == "claude-haiku-4-5-20251001", s  # last turn's model (unchanged)
        assert s["tokens_in"] == 350 and s["tokens_out"] == 30, s
        assert s["by_model"]["claude-opus-4-8"] == {"tokens_in": 150, "tokens_out": 10}, s
        assert s["by_model"]["claude-haiku-4-5-20251001"] == {"tokens_in": 200, "tokens_out": 20}, s
    finally:
        os.unlink(p)


def test_extract_output_by_uuid():
    assert extract_output(str(FIX), "s1") == "Security review: found 1 important issue.", extract_output(str(FIX), "s1")
    assert extract_output(str(FIX), "missing") == ""


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
        except Exception as e:  # import/other errors
            failed += 1
            print(f"ERROR {t.__name__}: {type(e).__name__}: {e}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    sys.exit(1 if failed else 0)
