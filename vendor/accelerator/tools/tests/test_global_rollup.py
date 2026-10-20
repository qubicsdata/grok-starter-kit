#!/usr/bin/env python3
"""Tests for ai-baseline/scripts/global_rollup.py.
Run: python3 tools/tests/test_global_rollup.py

Exercises the CLI end-to-end via subprocess with ACCELERATOR_HOME pointed at a
tempdir, so no test ever touches the real ~/.accelerator.
"""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
SCRIPT = REPO / "ai-baseline" / "scripts" / "global_rollup.py"

# Same golden shape as tools/tests/audit-fixtures/sample-audit.jsonl, plus ts.
# opus 1200 tok x5 = 6000 ; sonnet 600 x1 = 600 ; haiku 400 x0.25 = 100 → 6700.0
REC_OPUS = ('{"schema_version":"1.0.0","session_id":"s1","plugin":"dev-companion",'
            '"agent":"code-reviewer","model":"claude-opus-4-8","tokens_in":1000,'
            '"tokens_out":200,"ts":"2026-07-01T10:00:00.000Z"}')
REC_SONNET = ('{"schema_version":"1.0.0","session_id":"s1","plugin":"dev-companion",'
              '"agent":"security-reviewer","model":"claude-sonnet-4-6","tokens_in":500,'
              '"tokens_out":100,"ts":"2026-07-01T11:00:00.000Z"}')
REC_HAIKU = ('{"schema_version":"1.0.0","session_id":"s2","plugin":"api-designer",'
             '"agent":"intent-agent","model":"claude-haiku-4-5-20251001","tokens_in":400,'
             '"tokens_out":0,"ts":"2026-07-01T12:00:00.000Z"}')
REC_FEEDBACK = ('{"schema_version":"1.0.0","agent":"code-reviewer","score":4,'
                '"ts":"2026-07-01T13:00:00.000Z"}')


def make_repo(parent: Path, name: str, audit_lines: list, feedback_lines: list = ()) -> Path:
    root = parent / name
    (root / ".ai-baseline").mkdir(parents=True)
    (root / ".ai-baseline" / "audit.2026-07-01.jsonl").write_text(
        "\n".join(audit_lines) + "\n", encoding="utf-8")
    if feedback_lines:
        (root / ".ai-evolution").mkdir(parents=True)
        (root / ".ai-evolution" / "feedback.jsonl").write_text(
            "\n".join(feedback_lines) + "\n", encoding="utf-8")
    return root


def run(args: list, home: Path) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env["ACCELERATOR_HOME"] = str(home)
    return subprocess.run([sys.executable, str(SCRIPT)] + args,
                          capture_output=True, text=True, env=env, timeout=30)


def test_sync_twice_no_dupes():
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        home = tmp / "accel-home"
        repo = make_repo(tmp, "alpha", [REC_OPUS, REC_SONNET, REC_HAIKU])
        for _ in range(2):  # second sync must be a no-op, not a duplication
            r = run(["--sync", "--repo", str(repo)], home)
            assert r.returncode == 0, r.stderr
        target = home / "repos" / "alpha" / "audit.2026-07-01.jsonl"
        lines = [l for l in target.read_text(encoding="utf-8").splitlines() if l.strip()]
        assert len(lines) == 3, lines
        assert len(set(lines)) == 3, lines
        summary = json.loads((home / "repos" / "alpha" / "summary.json").read_text(encoding="utf-8"))
        assert summary["records"] == 3, summary
        assert summary["cost_units"] == 6700.0, summary
        assert summary["last_sync"] == "2026-07-01T12:00:00.000Z", summary


def test_report_aggregates_two_repos():
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        home = tmp / "accel-home"
        repo_a = make_repo(tmp, "alpha", [REC_OPUS, REC_SONNET, REC_HAIKU])
        repo_b = make_repo(tmp, "beta", [REC_SONNET])
        run(["--sync", "--repo", str(repo_a)], home)
        run(["--sync", "--repo", str(repo_b)], home)
        r = run(["--report", "--json"], home)
        assert r.returncode == 0, r.stderr
        rows = json.loads(r.stdout)
        by_slug = {row["repo"]: row for row in rows}
        assert set(by_slug) == {"alpha", "beta"}, rows
        assert by_slug["alpha"]["records"] == 3, rows
        assert by_slug["alpha"]["cost_units"] == 6700.0, rows
        assert by_slug["beta"]["records"] == 1, rows
        assert by_slug["beta"]["cost_units"] == 600.0, rows
        # plain-text table names both repos
        rt = run(["--report"], home)
        assert "alpha" in rt.stdout and "beta" in rt.stdout, rt.stdout


def test_dedupe_survives_interleaved_shards():
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        home = tmp / "accel-home"
        # Global copy already holds one record (e.g. synced earlier from another
        # machine) in a different order than the source shard.
        target = home / "repos" / "alpha" / "audit.2026-07-01.jsonl"
        target.parent.mkdir(parents=True)
        target.write_text(REC_SONNET + "\n", encoding="utf-8")
        repo = make_repo(tmp, "alpha", [REC_OPUS, REC_SONNET, REC_HAIKU], [REC_FEEDBACK])
        r = run(["--sync", "--repo", str(repo)], home)
        assert r.returncode == 0, r.stderr
        lines = [l for l in target.read_text(encoding="utf-8").splitlines() if l.strip()]
        assert len(lines) == 3, lines            # never delete, never duplicate
        assert set(lines) == {REC_OPUS, REC_SONNET, REC_HAIKU}, lines
        assert lines[0] == REC_SONNET, lines     # append-only: existing order kept
        fb = home / "repos" / "alpha" / "feedback.jsonl"
        assert fb.read_text(encoding="utf-8").strip() == REC_FEEDBACK, fb
        summary = json.loads((home / "repos" / "alpha" / "summary.json").read_text(encoding="utf-8"))
        assert summary["records"] == 4, summary  # 3 audit + 1 feedback
        assert summary["audit_records"] == 3, summary
        assert summary["feedback_records"] == 1, summary
        assert summary["last_sync"] == "2026-07-01T13:00:00.000Z", summary


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
