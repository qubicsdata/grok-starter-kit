#!/usr/bin/env python3
"""Stdlib tests for tools/hooks/audit_append.py build_record(). Run: python3 tools/tests/test_audit_append.py"""
import json
import os
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO / "tools" / "hooks"))
FIX = str(REPO / "tools" / "tests" / "transcript-fixtures" / "sample.jsonl")

from audit_append import build_record  # noqa: E402
from scoreable_agents import is_scoreable  # noqa: E402


def test_stop_enriches_from_main_segment():
    rec = build_record({"transcript_path": FIX, "session_id": "sess-1"}, event="stop")
    assert rec["model"] == "claude-opus-4-8", rec
    assert rec["tokens_in"] == 320, rec
    assert rec["tokens_out"] == 125, rec
    assert rec["plugin"] == "ai-baseline", rec
    assert rec["agent"] == "accelerate-arc", rec
    assert rec["command"] == "hook:stop", rec
    assert rec["schema_version"] == "1.0.0", rec  # 15-field shape preserved
    assert len(rec) == 15, rec


def test_subagent_stop_uses_sidechain_segment():
    rec = build_record({"transcript_path": FIX, "session_id": "sess-1"}, event="subagent-stop")
    assert rec["model"] == "claude-sonnet-4-6", rec
    assert rec["tokens_out"] == 120, rec
    assert rec["agent"] == "security-reviewer", rec
    assert rec["plugin"] == "dev-companion", rec


def test_no_transcript_flag_keeps_legacy_nulls():
    rec = build_record({"transcript_path": FIX, "session_id": "s"}, event="stop", no_transcript=True)
    assert rec["model"] is None and rec["tokens_in"] is None and rec["tokens_out"] is None, rec
    assert rec["agent"] == "hook", rec


def test_missing_transcript_fails_open():
    rec = build_record({"transcript_path": str(REPO / "nope.jsonl"), "session_id": "s"}, event="stop")
    assert rec["model"] is None, rec          # nothing recovered
    assert rec["command"] == "hook:stop", rec  # record still well-formed
    assert len(rec) == 15, rec


def _tmp_pending():
    fd, p = tempfile.mkstemp(suffix=".pending")
    os.close(fd)
    os.unlink(p)  # start absent
    return p


def test_subagent_stop_queues_pending_stub_for_scoreable():
    pend = _tmp_pending()
    rec = build_record({"transcript_path": FIX, "session_id": "sess-1"}, event="subagent-stop", pending_path=pend)
    assert rec["agent"] == "security-reviewer", rec
    lines = Path(pend).read_text().strip().splitlines()
    assert len(lines) == 1, lines
    stub = json.loads(lines[0])
    assert stub["status"] == "pending" and stub["agent"] == "security-reviewer", stub
    assert stub["output_ref"]["last_uuid"] == "s1", stub
    os.unlink(pend)


def test_main_stop_queues_no_stub():
    pend = _tmp_pending()
    build_record({"transcript_path": FIX, "session_id": "sess-1"}, event="stop", pending_path=pend)
    assert (not Path(pend).exists()) or Path(pend).read_text().strip() == "", "main Stop must not queue a stub"


def test_scoreable_blocklist():
    assert is_scoreable("code-reviewer") is True
    assert is_scoreable("router-agent") is False
    assert is_scoreable("audit-trail-agent") is False
    assert is_scoreable(None) is True


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
