#!/usr/bin/env python3
"""
self_check.py — deterministic runtime self-check for the accelerator hook set.

Proves the hooks actually fire OUTSIDE the dev repo: verifies each expected hook
script exists and py-compiles, then exercises each one inside a throwaway
consumer repo (git init + fake CLAUDE_PROJECT_DIR) with minimal synthetic hook
events, asserting sane behavior:

  - session_gateway emits the front-door SessionStart JSON
  - audit_append writes an audit record (model + tokens recovered from a tiny
    fixture transcript) and stays fail-open on garbage stdin
  - secret_guard denies a payload carrying a fake AWS access key and allows a
    clean write
  - cost_gate allows an Opus dispatch when budget.json is absent and denies one
    when the budget is exhausted
  - transcript_usage parses the fixture transcript to the exact token sums
  - the pricing data file the costing reads (pricing.json) is present

Fail-open-aware: a "deny" is stdout JSON with exit 0 — this checker asserts on
the JSON decision, not just exit codes. Pure stdlib, no imports from sibling
scripts (so it runs the same on an installed consumer as in the dev repo).

Prints a PASS/FAIL table; exits 0 only if every check passes.

Usage:
    python3 self_check.py                     # check the scripts beside this file
    python3 self_check.py --scripts-dir DIR   # check another hook set
"""

from __future__ import annotations

import argparse
import json
import os
import py_compile
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# The contract: every script the ai-baseline plugin ships. A missing name here
# is a broken install, not a soft degradation.
EXPECTED_SCRIPTS = (
    "_hooklib.py",
    "audit_append.py",
    "cost_gate.py",
    "scoreable_agents.py",
    "secret_guard.py",
    "self_check.py",
    "session_gateway.py",
    "transcript_usage.py",
)

# Data files the scripts read: beside them when installed, at the suite root
# (two levels up) for the canonical tools/hooks/ set — same lookup as _hooklib.
EXPECTED_DATA = ("pricing.json",)

# Built at runtime so this file never contains a literal credential pattern
# (the fleet's own secret_guard would otherwise refuse to write it).
FAKE_AWS_KEY = "AKIA" + "IOSFODNN7EXAMPLE"

FIXTURE_MODEL = "claude-opus-4-8"
FIXTURE_TOKENS_IN = 320   # (100 + 0) + (200 + 20) fresh-processed tokens
FIXTURE_TOKENS_OUT = 125  # 50 + 75


def build_fixture_transcript(path: Path, session_id: str) -> None:
    """Two main-chain assistant turns with known usage (mirrors the verified 2026-06-23 shape)."""
    lines = [
        {"type": "user", "uuid": "x0", "sessionId": session_id,
         "message": {"role": "user", "content": "hi"}},
        {"type": "assistant", "isSidechain": False, "uuid": "u1", "parentUuid": "x0",
         "sessionId": session_id,
         "message": {"model": FIXTURE_MODEL,
                     "usage": {"input_tokens": 100, "cache_creation_input_tokens": 0,
                               "cache_read_input_tokens": 0, "output_tokens": 50}}},
        {"type": "assistant", "isSidechain": False, "uuid": "u2", "parentUuid": "u1",
         "sessionId": session_id, "attributionPlugin": "ai-baseline",
         "attributionSkill": "accelerate-arc",
         "message": {"model": FIXTURE_MODEL,
                     "usage": {"input_tokens": 200, "cache_creation_input_tokens": 20,
                               "cache_read_input_tokens": 5, "output_tokens": 75}}},
    ]
    path.write_text("".join(json.dumps(o, separators=(",", ":")) + "\n" for o in lines),
                    encoding="utf-8")


def make_consumer_repo(base: Path) -> Path:
    """Throwaway consumer repo: git init (best-effort) so get_repo_root() resolves here."""
    consumer = base / "consumer"
    consumer.mkdir(parents=True)
    try:
        subprocess.run(["git", "init", "-q"], cwd=str(consumer),
                       capture_output=True, timeout=15)
    except Exception:
        pass  # no git → hooks fall back to $CLAUDE_PROJECT_DIR, which we set anyway
    return consumer


def run_hook(script: Path, consumer: Path, stdin_payload, *args: str) -> subprocess.CompletedProcess:
    """Run one hook script the way the hook system does: cwd + CLAUDE_PROJECT_DIR = consumer repo."""
    env = dict(os.environ)
    env["CLAUDE_PROJECT_DIR"] = str(consumer)
    env.pop("GIT_DIR", None)
    env.pop("GIT_WORK_TREE", None)
    stdin_text = stdin_payload if isinstance(stdin_payload, str) else json.dumps(stdin_payload)
    return subprocess.run(
        [sys.executable, str(script), *args],
        input=stdin_text, capture_output=True, text=True,
        cwd=str(consumer), env=env, timeout=30,
    )


def parse_decision(stdout: str):
    """Return the permissionDecision from a hook's stdout JSON, or None if it emitted no deny."""
    for line in stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except Exception:
            continue
        decision = (payload.get("hookSpecificOutput") or {}).get("permissionDecision")
        if decision:
            return decision
    return None


def read_audit_records(consumer: Path) -> list:
    records = []
    for shard in sorted((consumer / ".ai-baseline").glob("audit.*.jsonl")):
        for line in shard.read_text(encoding="utf-8").splitlines():
            if line.strip():
                records.append(json.loads(line))
    return records


def run_checks(scripts_dir: Path) -> list:
    """Return [(check_name, passed, detail)] — deterministic order, no early exit."""
    results = []

    def check(name: str, passed: bool, detail: str = "") -> None:
        results.append((name, bool(passed), detail))

    # 1. Existence
    for name in EXPECTED_SCRIPTS:
        check(f"exists:{name}", (scripts_dir / name).is_file(),
              "" if (scripts_dir / name).is_file() else f"not found in {scripts_dir}")
    for name in EXPECTED_DATA:
        found = any(p.is_file() for p in (scripts_dir / name, scripts_dir.parent.parent / name))
        check(f"exists:{name}", found,
              "" if found else f"not found in {scripts_dir} or two levels up")

    base = Path(tempfile.mkdtemp(prefix="hook-self-check-"))
    try:
        # 2. Compilation (byte-compile into the throwaway dir, never beside the scripts)
        pyc_dir = base / "pyc"
        pyc_dir.mkdir()
        for name in EXPECTED_SCRIPTS:
            path = scripts_dir / name
            if not path.is_file():
                check(f"compile:{name}", False, "skipped — script missing")
                continue
            try:
                py_compile.compile(str(path), cfile=str(pyc_dir / (name + "c")), doraise=True)
                check(f"compile:{name}", True)
            except Exception as exc:
                check(f"compile:{name}", False, str(exc).splitlines()[0][:120])

        # 3. Behavior in a throwaway consumer repo
        consumer = make_consumer_repo(base)
        transcript = base / "transcript.jsonl"
        session_id = "self-check-session"
        build_fixture_transcript(transcript, session_id)

        # session_gateway: emits the front-door SessionStart JSON
        try:
            r = run_hook(scripts_dir / "session_gateway.py", consumer, {})
            payload = json.loads(r.stdout.strip().splitlines()[-1])
            hso = payload.get("hookSpecificOutput") or {}
            ok = (r.returncode == 0
                  and hso.get("hookEventName") == "SessionStart"
                  and "Accelerator" in (hso.get("additionalContext") or ""))
            check("gateway:emits-front-door", ok,
                  "" if ok else f"exit={r.returncode} stdout={r.stdout[:120]!r}")
        except Exception as exc:
            check("gateway:emits-front-door", False, f"{type(exc).__name__}: {exc}")

        # transcript_usage: parses the fixture to the exact sums
        try:
            r = run_hook(scripts_dir / "transcript_usage.py", consumer, "", str(transcript))
            summary = json.loads(r.stdout)
            ok = (summary.get("model") == FIXTURE_MODEL
                  and summary.get("tokens_in") == FIXTURE_TOKENS_IN
                  and summary.get("tokens_out") == FIXTURE_TOKENS_OUT)
            check("usage:parses-fixture", ok, "" if ok else f"got {summary}")
        except Exception as exc:
            check("usage:parses-fixture", False, f"{type(exc).__name__}: {exc}")

        # audit_append: writes an enriched record on --event stop
        try:
            event = {"session_id": session_id, "transcript_path": str(transcript)}
            r = run_hook(scripts_dir / "audit_append.py", consumer, event, "--event", "stop")
            records = read_audit_records(consumer)
            rec = records[-1] if records else {}
            ok = (r.returncode == 0
                  and len(records) == 1
                  and rec.get("session_id") == session_id
                  and rec.get("model") == FIXTURE_MODEL
                  and (rec.get("tokens_out") or 0) > 0)
            check("audit:writes-record", ok,
                  "" if ok else f"exit={r.returncode} records={len(records)} rec={rec}")
        except Exception as exc:
            check("audit:writes-record", False, f"{type(exc).__name__}: {exc}")

        # audit_append: fail-open — garbage stdin must still exit 0
        try:
            r = run_hook(scripts_dir / "audit_append.py", consumer, "{not json", "--event", "stop")
            check("audit:fail-open-garbage-stdin", r.returncode == 0,
                  "" if r.returncode == 0 else f"exit={r.returncode} — fail-open broken")
        except Exception as exc:
            check("audit:fail-open-garbage-stdin", False, f"{type(exc).__name__}: {exc}")

        # secret_guard: denies a Write carrying a fake AWS access key
        try:
            event = {"tool_name": "Write",
                     "tool_input": {"file_path": "config.py",
                                    "content": f"KEY = '{FAKE_AWS_KEY}'"}}
            r = run_hook(scripts_dir / "secret_guard.py", consumer, event)
            decision = parse_decision(r.stdout)
            ok = r.returncode == 0 and decision == "deny"
            check("secret_guard:denies-aws-key", ok,
                  "" if ok else f"exit={r.returncode} decision={decision}")
        except Exception as exc:
            check("secret_guard:denies-aws-key", False, f"{type(exc).__name__}: {exc}")

        # secret_guard: allows a clean write (no false positive, exit 0)
        try:
            event = {"tool_name": "Write",
                     "tool_input": {"file_path": "notes.md", "content": "plain text"}}
            r = run_hook(scripts_dir / "secret_guard.py", consumer, event)
            ok = r.returncode == 0 and parse_decision(r.stdout) is None
            check("secret_guard:allows-clean-write", ok,
                  "" if ok else f"exit={r.returncode} stdout={r.stdout[:120]!r}")
        except Exception as exc:
            check("secret_guard:allows-clean-write", False, f"{type(exc).__name__}: {exc}")

        opus_task = {"tool_name": "Task",
                     "tool_input": {"subagent_type": "deep-reviewer", "model": "claude-opus-4-8"}}

        # cost_gate: allows when budget.json is absent (backwards-compatible fail-open).
        # audit_append may have seeded budget.json above (spend accrual) — remove it so
        # this check genuinely exercises the absent-budget path.
        try:
            seeded = consumer / ".ai-baseline" / "budget.json"
            if seeded.exists():
                seeded.unlink()
            r = run_hook(scripts_dir / "cost_gate.py", consumer, opus_task)
            ok = r.returncode == 0 and parse_decision(r.stdout) is None
            check("cost_gate:allows-no-budget", ok,
                  "" if ok else f"exit={r.returncode} decision={parse_decision(r.stdout)}")
        except Exception as exc:
            check("cost_gate:allows-no-budget", False, f"{type(exc).__name__}: {exc}")

        # cost_gate: denies an Opus dispatch when the budget is exhausted
        try:
            budget = consumer / ".ai-baseline" / "budget.json"
            budget.parent.mkdir(parents=True, exist_ok=True)
            budget.write_text(json.dumps({"limit_usd": 0.01, "spent_usd": 999.0}),
                              encoding="utf-8")
            r = run_hook(scripts_dir / "cost_gate.py", consumer, opus_task)
            decision = parse_decision(r.stdout)
            ok = r.returncode == 0 and decision == "deny"
            check("cost_gate:denies-over-budget", ok,
                  "" if ok else f"exit={r.returncode} decision={decision}")
        except Exception as exc:
            check("cost_gate:denies-over-budget", False, f"{type(exc).__name__}: {exc}")
    finally:
        shutil.rmtree(base, ignore_errors=True)

    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="Accelerator hook runtime self-check")
    parser.add_argument("--scripts-dir", default=str(Path(__file__).resolve().parent),
                        help="Directory holding the hook scripts (default: this file's dir)")
    args = parser.parse_args()

    scripts_dir = Path(args.scripts_dir).resolve()
    print(f"self_check: exercising hook set at {scripts_dir}")
    print(f"  {'CHECK':<36} {'RESULT':<6} DETAIL")

    results = run_checks(scripts_dir)
    failed = 0
    for name, passed, detail in results:
        if not passed:
            failed += 1
        print(f"  {name:<36} {'PASS' if passed else 'FAIL':<6} {detail}")

    total = len(results)
    print(f"\nself_check: {'PASS' if failed == 0 else 'FAIL'} "
          f"({total - failed}/{total} checks passed)")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
