#!/usr/bin/env python3
"""Stdlib tests for tools/hooks/cost_gate.py main(). Run: python3 tools/tests/test_cost_gate.py"""
import contextlib
import io
import json
import shutil
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO / "tools" / "hooks"))

import cost_gate  # noqa: E402

OPUS_TASK = {"tool_name": "Task", "tool_input": {"model": "opus", "subagent_type": "code-reviewer"}}
SONNET_TASK = {"tool_name": "Task", "tool_input": {"model": "sonnet", "subagent_type": "code-reviewer"}}


def _run_gate(payload, budget):
    """Run cost_gate.main() against a temp repo root whose budget.json holds
    `budget` (None = no file). Returns (exit_code, stdout)."""
    tmp = Path(tempfile.mkdtemp(prefix="cost-gate-"))
    try:
        if budget is not None:
            (tmp / ".ai-baseline").mkdir()
            (tmp / ".ai-baseline" / "budget.json").write_text(json.dumps(budget), encoding="utf-8")
        orig_root, orig_stdin = cost_gate.get_repo_root, cost_gate.read_stdin_json
        cost_gate.get_repo_root = lambda: str(tmp)
        cost_gate.read_stdin_json = lambda: payload
        out = io.StringIO()
        try:
            with contextlib.redirect_stdout(out):
                rc = cost_gate.main()
        finally:
            cost_gate.get_repo_root, cost_gate.read_stdin_json = orig_root, orig_stdin
        return rc, out.getvalue().strip()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_null_limit_allows_opus():
    # limit_usd null = "measure but never block" — an Opus dispatch passes through
    rc, out = _run_gate(OPUS_TASK, {"limit_usd": None, "spent_usd": 123.45})
    assert rc == 0 and out == "", (rc, out)


def test_absent_limit_key_allows_opus():
    rc, out = _run_gate(OPUS_TASK, {"spent_usd": 99.0})
    assert rc == 0 and out == "", (rc, out)


def test_numeric_exhausted_limit_blocks_opus():
    rc, out = _run_gate(OPUS_TASK, {"limit_usd": 1.0, "spent_usd": 1.0})
    assert rc == 0, rc
    deny = json.loads(out)
    assert deny["hookSpecificOutput"]["permissionDecision"] == "deny", deny


def test_numeric_limit_with_headroom_allows_opus():
    rc, out = _run_gate(OPUS_TASK, {"limit_usd": 5.0, "spent_usd": 1.0})
    assert rc == 0 and out == "", (rc, out)


def test_non_opus_ignores_exhausted_budget():
    rc, out = _run_gate(SONNET_TASK, {"limit_usd": 1.0, "spent_usd": 9.0})
    assert rc == 0 and out == "", (rc, out)


def test_missing_budget_file_allows_opus():
    rc, out = _run_gate(OPUS_TASK, None)
    assert rc == 0 and out == "", (rc, out)


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
