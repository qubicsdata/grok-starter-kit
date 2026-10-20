#!/usr/bin/env python3
"""Stdlib tests for the maintenance-debt detector in tools/hooks/session_gateway.py.
Run: python3 tools/tests/test_session_gateway_debt.py"""
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO / "tools" / "hooks"))

# Deterministic run() output: never let a locally installed superpowers toolkit leak in.
os.environ["ACCELERATOR_SUPERPOWERS"] = "0"

import session_gateway  # noqa: E402


# ---------------------------------------------------------------- fixtures

def _write_pending(root: Path, n: int, blanks: int = 0) -> None:
    d = root / ".ai-evolution"
    d.mkdir(parents=True, exist_ok=True)
    lines = ['{"agent":"router-agent"}'] * n + [""] * blanks
    (d / "feedback.jsonl.pending").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_budget(root: Path, limit, spent) -> None:
    d = root / ".ai-baseline"
    d.mkdir(parents=True, exist_ok=True)
    (d / "budget.json").write_text(
        json.dumps({"limit_usd": limit, "spent_usd": spent}), encoding="utf-8"
    )


def _write_memory(root: Path, entries: int = 1) -> None:
    ns = root / ".ai-memory" / "project"
    ns.mkdir(parents=True, exist_ok=True)
    for i in range(entries):
        (ns / f"key{i}.json").write_text("{}", encoding="utf-8")


def _debt(build):
    """Build a synthetic repo root, run detect_debt against it, clean up."""
    tmp = Path(tempfile.mkdtemp(prefix="gateway-debt-"))
    try:
        build(tmp)
        return session_gateway.detect_debt(str(tmp))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _run_with_root(build) -> str:
    """Run the full gateway run() with get_repo_root patched to a synthetic root."""
    tmp = Path(tempfile.mkdtemp(prefix="gateway-run-"))
    original = session_gateway.get_repo_root
    try:
        build(tmp)
        session_gateway.get_repo_root = lambda: str(tmp)
        return session_gateway.run()
    finally:
        session_gateway.get_repo_root = original
        shutil.rmtree(tmp, ignore_errors=True)


# ---------------------------------------------------------------- zero-noise rule

def test_no_debt_returns_no_lines():
    assert _debt(lambda root: None) == []


def test_compose_maintenance_none_when_no_lines():
    assert session_gateway.compose_maintenance([]) is None


def test_run_emits_nothing_extra_when_no_debt():
    # CRITICAL: no debt → the context is byte-identical to the plain front door.
    out = _run_with_root(lambda root: None)
    assert out == session_gateway.build_message(0, False), out
    assert "Maintenance" not in out, out


# ---------------------------------------------------------------- (a) pending scores

def test_pending_at_threshold_fires_exact_line():
    lines = _debt(lambda root: _write_pending(root, 5))
    assert lines == ["5 unscored outputs pending — /score-pending"], lines


def test_pending_below_threshold_is_silent():
    assert _debt(lambda root: _write_pending(root, 4)) == []


def test_pending_blank_lines_not_counted():
    assert _debt(lambda root: _write_pending(root, 4, blanks=3)) == []


# ---------------------------------------------------------------- (b) budget pressure

def test_budget_at_80_pct_fires_exact_line():
    lines = _debt(lambda root: _write_budget(root, 10.0, 8.0))
    assert lines == ["budget 80% — /budget-status"], lines


def test_budget_over_limit_fires():
    lines = _debt(lambda root: _write_budget(root, 10.0, 9.5))
    assert lines == ["budget 95% — /budget-status"], lines


def test_budget_below_threshold_is_silent():
    assert _debt(lambda root: _write_budget(root, 10.0, 7.9)) == []


def test_budget_non_numeric_limit_is_silent():
    assert _debt(lambda root: _write_budget(root, "high", 8.0)) == []


def test_budget_zero_limit_is_silent():
    assert _debt(lambda root: _write_budget(root, 0, 5.0)) == []


def test_budget_malformed_json_is_silent():
    def build(root):
        d = root / ".ai-baseline"
        d.mkdir(parents=True)
        (d / "budget.json").write_text("{not json", encoding="utf-8")
    assert _debt(build) == []


# ---------------------------------------------------------------- (c) memory present

def test_memory_entry_fires_exact_line():
    lines = _debt(lambda root: _write_memory(root, 1))
    assert lines == ["memory present: /recall"], lines


def test_memory_bare_dir_is_silent():
    assert _debt(lambda root: (root / ".ai-memory").mkdir()) == []


def test_memory_empty_namespace_is_silent():
    assert _debt(lambda root: (root / ".ai-memory" / "project").mkdir(parents=True)) == []


# ---------------------------------------------------------------- collapse rule

def test_single_signal_composes_maintenance_prefix():
    line = session_gateway.compose_maintenance(["memory present: /recall"])
    assert line == "Maintenance: memory present: /recall", line


def test_two_signals_collapse_to_steward():
    def build(root):
        _write_pending(root, 6)
        _write_memory(root, 2)
    lines = _debt(build)
    assert len(lines) == 2, lines
    collapsed = session_gateway.compose_maintenance(lines)
    assert collapsed == "Maintenance: 2 upkeep signals — run /steward", collapsed


def test_three_signals_collapse_to_steward():
    def build(root):
        _write_pending(root, 7)
        _write_budget(root, 10.0, 9.0)
        _write_memory(root, 1)
    lines = _debt(build)
    assert len(lines) == 3, lines
    collapsed = session_gateway.compose_maintenance(lines)
    assert collapsed == "Maintenance: 3 upkeep signals — run /steward", collapsed


# ---------------------------------------------------------------- end-to-end wiring

def test_run_appends_maintenance_after_front_door():
    out = _run_with_root(lambda root: _write_memory(root, 1))
    front = session_gateway.build_message(0, False)
    assert out == front + "\nMaintenance: memory present: /recall", out


def test_run_collapses_in_full_context():
    def build(root):
        _write_pending(root, 5)
        _write_budget(root, 10.0, 8.5)
    out = _run_with_root(build)
    assert out.endswith("\nMaintenance: 2 upkeep signals — run /steward"), out


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
