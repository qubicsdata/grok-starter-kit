#!/usr/bin/env python3
"""Stdlib tests for hook-side costing (_hooklib model_pricing/cost_usd, rates
from the pricing.json data file) and the audit_append.py budget feed
(.ai-baseline/budget.json spent_usd accrual).
Run: python3 tools/tests/test_hook_costing.py"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO / "tools" / "hooks"))
FIX = str(REPO / "tools" / "tests" / "transcript-fixtures" / "sample.jsonl")
HOOK = str(REPO / "tools" / "hooks" / "audit_append.py")
PRICING_FILE = REPO / "pricing.json"

from _hooklib import PricingError, cost_usd, model_pricing  # noqa: E402

PRICING_DATA = json.loads(PRICING_FILE.read_text(encoding="utf-8"))


def _rates(model):
    entry = PRICING_DATA["models"][model]
    return (entry["input"], entry["output"])


# Fixture (sample.jsonl): main segment 320 in / 125 out on opus (cache_read=5
# EXCLUDED per BENCHMARK-CONVENTIONS §1); sidechain 300 in / 120 out on sonnet.
OPUS_IN, OPUS_OUT = _rates("claude-opus-4-8")
SONNET_IN, SONNET_OUT = _rates("claude-sonnet-4-6")
STOP_COST = 320 * OPUS_IN + 125 * OPUS_OUT
SUB_COST = 300 * SONNET_IN + 120 * SONNET_OUT


def test_rates_come_from_the_data_file():
    for model in PRICING_DATA["models"]:
        assert model_pricing(model) == _rates(model), model
    assert OPUS_IN > 0 and SONNET_OUT > 0


def _hooks_without_pricing():
    """A copy of tools/hooks/*.py in a temp dir with no pricing.json beside it
    or two levels up."""
    base = Path(tempfile.mkdtemp(prefix="nopricing-"))
    hooks = base / "a" / "b"
    hooks.mkdir(parents=True)
    for script in (REPO / "tools" / "hooks").glob("*.py"):
        shutil.copyfile(script, hooks / script.name)
    return base, hooks


def test_missing_pricing_file_raises_pricing_error():
    base, hooks = _hooks_without_pricing()
    try:
        code = ("import sys; sys.path.insert(0, sys.argv[1]); import _hooklib\n"
                "try:\n    _hooklib.model_pricing('claude-opus-4-8')\n"
                "except _hooklib.PricingError as e:\n    print('PricingError', e)\n")
        r = subprocess.run([sys.executable, "-c", code, str(hooks)],
                           capture_output=True, text=True, timeout=30)
        assert r.returncode == 0, r.stderr
        assert r.stdout.startswith("PricingError") and "pricing.json" in r.stdout, r.stdout
    finally:
        shutil.rmtree(base, ignore_errors=True)


def test_audit_record_kept_and_budget_untouched_without_pricing():
    base, hooks = _hooks_without_pricing()
    try:
        project = base / "project"
        project.mkdir()
        payload = json.dumps({"session_id": "sess-np", "transcript_path": FIX})
        env = dict(os.environ, CLAUDE_PROJECT_DIR=str(project))
        r = subprocess.run([sys.executable, str(hooks / "audit_append.py"), "--event", "stop"],
                           input=payload, capture_output=True, text=True,
                           cwd=str(project), env=env, timeout=30)
        assert r.returncode == 0, r.stderr
        assert "budget not updated" in r.stderr, r.stderr
        recs = [json.loads(l)
                for shard in (project / ".ai-baseline").glob("audit.*.jsonl")
                for l in shard.read_text(encoding="utf-8").splitlines() if l.strip()]
        assert len(recs) == 1 and recs[0]["tokens_in"] == 320, recs
        assert not (project / ".ai-baseline" / "budget.json").exists()
    finally:
        shutil.rmtree(base, ignore_errors=True)


def test_pricing_error_is_a_runtime_error():
    assert issubclass(PricingError, RuntimeError)


def test_cost_usd_exact_math():
    assert abs(cost_usd("claude-opus-4-8", 320, 125) - STOP_COST) < 1e-12
    assert abs(cost_usd("claude-sonnet-4-6", 300, 120) - SUB_COST) < 1e-12


def test_cost_usd_null_or_zero_tokens_cost_zero():
    assert cost_usd(None, None, None) == 0.0
    assert cost_usd("claude-opus-4-8", 0, 0) == 0.0


def test_unknown_model_falls_back_to_sonnet_rates():
    # conservative estimate per cost-monitor pricing-table convention
    assert model_pricing("gpt-9") == _rates(PRICING_DATA["default"])
    assert model_pricing(None) == _rates(PRICING_DATA["default"])


def test_tier_substring_matches_unlisted_snapshot():
    assert model_pricing("claude-opus-5-20270101") == _rates(PRICING_DATA["tiers"]["opus"])
    assert model_pricing("claude-haiku-4-5") == _rates(PRICING_DATA["tiers"]["haiku"])


def _run_hook(root, event, session="sess-1"):
    payload = json.dumps({"session_id": session, "transcript_path": FIX})
    env = dict(os.environ, CLAUDE_PROJECT_DIR=str(root))
    r = subprocess.run([sys.executable, HOOK, "--event", event],
                       input=payload, capture_output=True, text=True,
                       cwd=str(root), env=env, timeout=30)
    assert r.returncode == 0, r.stderr
    return r


def _budget(root):
    return json.loads((Path(root) / ".ai-baseline" / "budget.json").read_text(encoding="utf-8"))


def test_budget_created_on_first_run_with_null_limit():
    tmp = Path(tempfile.mkdtemp(prefix="budget-"))
    try:
        _run_hook(tmp, "stop")
        b = _budget(tmp)
        assert b["limit_usd"] is None, b
        assert abs(b["spent_usd"] - STOP_COST) < 1e-9, (b, STOP_COST)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_spend_accrues_across_events():
    tmp = Path(tempfile.mkdtemp(prefix="budget-"))
    try:
        _run_hook(tmp, "stop")
        _run_hook(tmp, "subagent-stop")
        b = _budget(tmp)
        assert abs(b["spent_usd"] - (STOP_COST + SUB_COST)) < 1e-9, b
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_second_run_same_transcript_does_not_double_count():
    tmp = Path(tempfile.mkdtemp(prefix="budget-"))
    try:
        _run_hook(tmp, "stop")
        first = _budget(tmp)["spent_usd"]
        _run_hook(tmp, "stop")  # cursor semantics: no new main-agent turns
        second = _budget(tmp)["spent_usd"]
        assert abs(second - first) < 1e-12, (first, second)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_mixed_model_segment_costs_each_tier():
    # A single Stop segment spanning two model tiers must be costed per-turn-model,
    # not at the last turn's (cheapest) rate — the budget feeds the Opus cost gate.
    tmp = Path(tempfile.mkdtemp(prefix="budget-"))
    try:
        t = tmp / "mixed.jsonl"
        lines = [
            {"type": "assistant", "isSidechain": False, "uuid": "u1",
             "message": {"model": "claude-opus-4-8",
                         "usage": {"input_tokens": 1000, "cache_creation_input_tokens": 500,
                                   "cache_read_input_tokens": 0, "output_tokens": 2000}}},
            {"type": "assistant", "isSidechain": False, "uuid": "u2",
             "message": {"model": "claude-haiku-4-5-20251001",
                         "usage": {"input_tokens": 4000, "cache_creation_input_tokens": 0,
                                   "cache_read_input_tokens": 0, "output_tokens": 1000}}},
        ]
        t.write_text("".join(json.dumps(o) + "\n" for o in lines), encoding="utf-8")
        payload = json.dumps({"session_id": "sess-mixed", "transcript_path": str(t)})
        env = dict(os.environ, CLAUDE_PROJECT_DIR=str(tmp))
        r = subprocess.run([sys.executable, HOOK, "--event", "stop"],
                           input=payload, capture_output=True, text=True,
                           cwd=str(tmp), env=env, timeout=30)
        assert r.returncode == 0, r.stderr
        haiku_in, haiku_out = _rates("claude-haiku-4-5-20251001")
        expected = (1500 * OPUS_IN + 2000 * OPUS_OUT) + (4000 * haiku_in + 1000 * haiku_out)
        b = _budget(tmp)
        assert abs(b["spent_usd"] - expected) < 1e-9, (b, expected)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_parallel_hooks_never_double_count():
    # Overlapping Stop/SubagentStop hook processes (parallel subagent dispatch,
    # dual registration) must not each count the same transcript span, and no
    # budget increment may be lost to a read-modify-write race.
    tmp = Path(tempfile.mkdtemp(prefix="budget-"))
    try:
        n = 30000
        t = tmp / "big.jsonl"
        with open(t, "w", encoding="utf-8") as fh:
            for i in range(n):
                fh.write(json.dumps({"type": "assistant", "isSidechain": False, "uuid": f"u{i}",
                                     "message": {"model": "claude-opus-4-8",
                                                 "usage": {"input_tokens": 1000,
                                                           "cache_creation_input_tokens": 0,
                                                           "cache_read_input_tokens": 0,
                                                           "output_tokens": 100}}}) + "\n")
        expected = n * (1000 * OPUS_IN + 100 * OPUS_OUT)
        payload = json.dumps({"session_id": "sess-race", "transcript_path": str(t)})
        env = dict(os.environ, CLAUDE_PROJECT_DIR=str(tmp))
        procs = [subprocess.Popen([sys.executable, HOOK, "--event", "stop"],
                                  stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE, cwd=str(tmp), env=env, text=True)
                 for _ in range(4)]
        for p in procs:
            p.stdin.write(payload)
            p.stdin.close()
        for p in procs:
            assert p.wait(timeout=120) == 0
        b = _budget(tmp)
        assert abs(b["spent_usd"] - expected) < 1e-6, (b["spent_usd"], expected)
        recs = [json.loads(l)
                for shard in (tmp / ".ai-baseline").glob("audit.*.jsonl")
                for l in shard.read_text(encoding="utf-8").splitlines() if l.strip()]
        with_tokens = [r for r in recs if r.get("tokens_in")]
        assert len(recs) == 4, recs
        assert len(with_tokens) == 1, [r.get("tokens_in") for r in recs]
        assert with_tokens[0]["tokens_in"] == n * 1000, with_tokens[0]
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_existing_limit_usd_never_touched():
    tmp = Path(tempfile.mkdtemp(prefix="budget-"))
    try:
        (tmp / ".ai-baseline").mkdir()
        (tmp / ".ai-baseline" / "budget.json").write_text(
            json.dumps({"limit_usd": 2.5, "spent_usd": 0.1}), encoding="utf-8")
        _run_hook(tmp, "stop")
        b = _budget(tmp)
        assert b["limit_usd"] == 2.5, b
        assert abs(b["spent_usd"] - (0.1 + STOP_COST)) < 1e-9, b
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


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
