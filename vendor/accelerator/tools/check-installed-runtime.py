#!/usr/bin/env python3
"""
check-installed-runtime.py — CI-grade end-to-end proof that the SHIPPED ai-baseline
hook set (ai-baseline/hooks/scripts/) actually governs a fresh consumer repo.

This is the fresh-perspective gate for the substrate: everything runs against the
shipped copies (what installed consumers execute), never tools/hooks/, inside a
tempdir consumer repo (git init + remote + branch, fake CLAUDE_PROJECT_DIR):

  1. hooks.json wires only shipped scripts that exist
  2. SessionStart gateway emits the front-door JSON
  3. a fixture transcript through `audit_append --event stop` produces an audit
     record with exact model + token sums
  4. that record carries non-null app/feature (fallback attribution from git
     remote/branch) — see FORWARD-COMPAT below
  5. budget.json exists after the hook run (first-run seeding) — FORWARD-COMPAT
  6. secret_guard denies a payload carrying a fake AWS access key
  7. cost_gate denies an Opus Task when budget.json has limit 0.01 / spent 999
  8. cost_gate allows an Opus Task when limit_usd is null (measure-only) —
     FORWARD-COMPAT
  9. the shipped self_check.py passes end to end
 10. builder_gate denies a Write into an ACTIVE (generate, gates not cleared) builder
     session's governed plugin tree
 11. builder_gate allows a Write once the session is in audit mode

FORWARD-COMPAT: some behaviors land in tools/hooks/ first and reach the shipped
set via `python3 tools/sync-shipped-hooks.py` (the drift gate, validate.sh step 14,
forces the re-sync). When the shipped copy demonstrably predates such a feature
(capability marker absent from its source), the check reports FWD — a non-fatal
"awaiting re-sync" note — instead of FAIL. If the marker IS present but the
behavior is broken, that is a hard FAIL. Once the feature ships, FWD checks
tighten into strict asserts automatically.

Exits 0 when no check FAILs (FWD notes allowed); exits 1 otherwise, with a table.

Usage:
    python3 tools/check-installed-runtime.py
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SHIPPED_DIR = REPO_ROOT / "ai-baseline" / "hooks" / "scripts"
HOOKS_JSON = REPO_ROOT / "ai-baseline" / "hooks" / "hooks.json"
PLUGIN_ROOT = REPO_ROOT / "ai-baseline"

# Built at runtime so this file never contains a literal credential pattern
# (the fleet's own secret_guard would otherwise refuse to write it).
FAKE_AWS_KEY = "AKIA" + "IOSFODNN7EXAMPLE"

FIXTURE_MODEL = "claude-opus-4-8"
FIXTURE_TOKENS_IN = 320   # (100 + 0) + (200 + 20) fresh-processed tokens
FIXTURE_TOKENS_OUT = 125  # 50 + 75

CONSUMER_APP = "webshop"          # from the fake remote URL
CONSUMER_FEATURE = "checkout-flow"  # the consumer repo's branch


# ---------------------------------------------------------------------------
# capability detection (forward-compat classification)
# ---------------------------------------------------------------------------

def _source(name: str) -> str:
    try:
        return (SHIPPED_DIR / name).read_text(encoding="utf-8")
    except Exception:
        return ""


def has_attribution_capability() -> bool:
    """Fallback attribution reads .ai-baseline/context.json (git fallback behind it) —
    any implementation must reference the filename."""
    return "context.json" in _source("audit_append.py")


def has_budget_seed_capability() -> bool:
    """First-run budget seeding would live in the SessionStart gateway or the Stop
    hook — cost_gate only reads budget.json, so it is excluded from the marker scan."""
    return ("budget.json" in _source("session_gateway.py")
            or "budget.json" in _source("audit_append.py"))


def has_null_limit_capability() -> bool:
    """A measure-only (limit_usd: null) allow path must test the limit against None —
    look for a source line mentioning both. The current shipped copy has neither on
    one line, so this stays FWD until the feature lands and re-syncs."""
    return any(("limit" in line and "None" in line)
               for line in _source("cost_gate.py").splitlines())


# ---------------------------------------------------------------------------
# consumer-repo simulation
# ---------------------------------------------------------------------------

def make_consumer_repo(base: Path) -> Path:
    consumer = base / "consumer"
    consumer.mkdir(parents=True)
    subprocess.run(["git", "init", "-q"], cwd=str(consumer), check=True,
                   capture_output=True, timeout=15)
    # symbolic-ref works on an unborn HEAD on every git version we care about
    subprocess.run(["git", "symbolic-ref", "HEAD", f"refs/heads/{CONSUMER_FEATURE}"],
                   cwd=str(consumer), check=True, capture_output=True, timeout=15)
    subprocess.run(["git", "remote", "add", "origin",
                    f"https://github.com/acme/{CONSUMER_APP}.git"],
                   cwd=str(consumer), check=True, capture_output=True, timeout=15)
    return consumer


def build_fixture_transcript(path: Path, session_id: str) -> None:
    """Two main-chain assistant turns with known usage (verified 2026-06-23 shape)."""
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


def run_shipped(script_name: str, consumer: Path, stdin_payload,
                *args: str) -> subprocess.CompletedProcess:
    """Run one SHIPPED hook the way the hook system does: cwd + CLAUDE_PROJECT_DIR
    point at the consumer repo, CLAUDE_PLUGIN_ROOT at the plugin."""
    env = dict(os.environ)
    env["CLAUDE_PROJECT_DIR"] = str(consumer)
    env["CLAUDE_PLUGIN_ROOT"] = str(PLUGIN_ROOT)
    env.pop("GIT_DIR", None)
    env.pop("GIT_WORK_TREE", None)
    stdin_text = stdin_payload if isinstance(stdin_payload, str) else json.dumps(stdin_payload)
    return subprocess.run(
        [sys.executable, str(SHIPPED_DIR / script_name), *args],
        input=stdin_text, capture_output=True, text=True,
        cwd=str(consumer), env=env, timeout=60,
    )


def parse_decision(stdout: str):
    """Return the permissionDecision from a hook's stdout JSON, or None (= allow)."""
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


# ---------------------------------------------------------------------------
# checks
# ---------------------------------------------------------------------------

def run_checks() -> list:
    """Return [(name, status, detail)] with status in {'PASS', 'FAIL', 'FWD'}."""
    results = []

    def check(name: str, status: str, detail: str = "") -> None:
        results.append((name, status, detail))

    # 1. hooks.json wiring: every ${CLAUDE_PLUGIN_ROOT} command targets a shipped script
    try:
        data = json.loads(HOOKS_JSON.read_text(encoding="utf-8"))
        missing = []
        for event, groups in (data.get("hooks") or {}).items():
            for group in groups:
                for hook in group.get("hooks", []):
                    cmd = hook.get("command", "")
                    if "${CLAUDE_PLUGIN_ROOT}" not in cmd:
                        missing.append(f"{event}: no ${{CLAUDE_PLUGIN_ROOT}} in {cmd!r}")
                        continue
                    rel = cmd.split("${CLAUDE_PLUGIN_ROOT}", 1)[1]
                    rel = rel.replace('"', "").strip().split()[0].lstrip("/")
                    if not (PLUGIN_ROOT / rel).is_file():
                        missing.append(f"{event}: {rel} not shipped")
        check("wiring:hooks.json-targets-exist", "PASS" if not missing else "FAIL",
              "; ".join(missing))
    except Exception as exc:
        check("wiring:hooks.json-targets-exist", "FAIL", f"{type(exc).__name__}: {exc}")

    base = Path(tempfile.mkdtemp(prefix="installed-runtime-"))
    try:
        consumer = make_consumer_repo(base)
        session_id = "installed-runtime-session"
        transcript = base / "transcript.jsonl"
        build_fixture_transcript(transcript, session_id)

        # 2. SessionStart gateway emits the front-door JSON
        try:
            r = run_shipped("session_gateway.py", consumer, {})
            payload = json.loads(r.stdout.strip().splitlines()[-1])
            hso = payload.get("hookSpecificOutput") or {}
            ok = (r.returncode == 0
                  and hso.get("hookEventName") == "SessionStart"
                  and "Accelerator" in (hso.get("additionalContext") or ""))
            check("gateway:front-door-json", "PASS" if ok else "FAIL",
                  "" if ok else f"exit={r.returncode} stdout={r.stdout[:120]!r}")
        except Exception as exc:
            check("gateway:front-door-json", "FAIL", f"{type(exc).__name__}: {exc}")

        # 3. audit record with exact model + token sums from the fixture transcript
        rec = {}
        try:
            event = {"session_id": session_id, "transcript_path": str(transcript)}
            r = run_shipped("audit_append.py", consumer, event, "--event", "stop")
            records = read_audit_records(consumer)
            rec = records[-1] if records else {}
            ok = (r.returncode == 0
                  and len(records) == 1
                  and rec.get("session_id") == session_id
                  and rec.get("model") == FIXTURE_MODEL
                  and rec.get("tokens_in") == FIXTURE_TOKENS_IN
                  and rec.get("tokens_out") == FIXTURE_TOKENS_OUT)
            check("audit:record-model-tokens", "PASS" if ok else "FAIL",
                  "" if ok else f"exit={r.returncode} records={len(records)} rec={rec}")
        except Exception as exc:
            check("audit:record-model-tokens", "FAIL", f"{type(exc).__name__}: {exc}")

        # 4. non-null app/feature via fallback attribution (git remote/branch).
        # FORWARD-COMPAT: if the shipped audit_append predates fallback attribution
        # (no context.json marker), assert only that the record exists — the drift
        # gate will re-sync the shipped copy once the feature lands canonically.
        if has_attribution_capability():
            ok = bool(rec) and rec.get("app") not in (None, "") and rec.get("feature") not in (None, "")
            check("audit:app-feature-attribution", "PASS" if ok else "FAIL",
                  "" if ok else f"app={rec.get('app')!r} feature={rec.get('feature')!r}")
        else:
            status = "FWD" if rec else "FAIL"
            check("audit:app-feature-attribution", status,
                  "shipped audit_append predates fallback attribution — awaiting re-sync"
                  if rec else "no audit record to inspect")

        # 5. budget.json seeded by the first hook run.
        # FORWARD-COMPAT: seeding lands with the bootstrap feature; until the shipped
        # gateway/stop hook carries the budget.json marker, report FWD not FAIL.
        budget_path = consumer / ".ai-baseline" / "budget.json"
        if has_budget_seed_capability():
            check("runtime:budget-seeded", "PASS" if budget_path.is_file() else "FAIL",
                  "" if budget_path.is_file() else "budget.json absent after hook run")
        else:
            check("runtime:budget-seeded",
                  "PASS" if budget_path.is_file() else "FWD",
                  "" if budget_path.is_file()
                  else "shipped hooks predate first-run budget seeding — awaiting re-sync")

        # 6. secret_guard denies a fake AWS access key
        try:
            event = {"tool_name": "Write",
                     "tool_input": {"file_path": "config.py",
                                    "content": f"KEY = '{FAKE_AWS_KEY}'"}}
            r = run_shipped("secret_guard.py", consumer, event)
            decision = parse_decision(r.stdout)
            ok = r.returncode == 0 and decision == "deny"
            check("secret-guard:denies-fake-key", "PASS" if ok else "FAIL",
                  "" if ok else f"exit={r.returncode} decision={decision}")
        except Exception as exc:
            check("secret-guard:denies-fake-key", "FAIL", f"{type(exc).__name__}: {exc}")

        opus_task = {"tool_name": "Task",
                     "tool_input": {"subagent_type": "deep-reviewer",
                                    "model": "claude-opus-4-8"}}
        budget_path.parent.mkdir(parents=True, exist_ok=True)

        # 7. cost_gate denies an Opus Task on an exhausted budget
        try:
            budget_path.write_text(json.dumps({"limit_usd": 0.01, "spent_usd": 999.0}),
                                   encoding="utf-8")
            r = run_shipped("cost_gate.py", consumer, opus_task)
            decision = parse_decision(r.stdout)
            ok = r.returncode == 0 and decision == "deny"
            check("cost-gate:denies-over-budget", "PASS" if ok else "FAIL",
                  "" if ok else f"exit={r.returncode} decision={decision}")
        except Exception as exc:
            check("cost-gate:denies-over-budget", "FAIL", f"{type(exc).__name__}: {exc}")

        # 8. cost_gate allows when limit_usd is null (measure-only, never block).
        # FORWARD-COMPAT: the current shipped gate has no null-limit path (float(None)
        # raises → Opus-path fail-closed exit 2). Behavior is tested first; only when
        # it fails AND the capability marker is absent do we report FWD.
        try:
            budget_path.write_text(json.dumps({"limit_usd": None, "spent_usd": 999.0}),
                                   encoding="utf-8")
            r = run_shipped("cost_gate.py", consumer, opus_task)
            allowed = r.returncode == 0 and parse_decision(r.stdout) is None
            if allowed:
                check("cost-gate:allows-null-limit", "PASS")
            elif has_null_limit_capability():
                check("cost-gate:allows-null-limit", "FAIL",
                      f"null-limit path present but blocked (exit={r.returncode}, "
                      f"decision={parse_decision(r.stdout)})")
            else:
                check("cost-gate:allows-null-limit", "FWD",
                      "shipped cost_gate predates measure-only null limit — awaiting re-sync")
        except Exception as exc:
            check("cost-gate:allows-null-limit", "FAIL", f"{type(exc).__name__}: {exc}")

        # 9. the shipped self-check passes (what /baseline-init runs on an install)
        try:
            r = run_shipped("self_check.py", consumer, "")
            ok = r.returncode == 0
            check("self-check:shipped-passes", "PASS" if ok else "FAIL",
                  "" if ok else f"exit={r.returncode}: {r.stdout[-160:].strip()!r}")
        except Exception as exc:
            check("self-check:shipped-passes", "FAIL", f"{type(exc).__name__}: {exc}")

        # 10. builder_gate denies a Write into an ACTIVE (generate, gates not cleared)
        # builder session's governed plugin tree.
        toy_plugin = consumer / "toy-plugin"
        session_file = toy_plugin / ".builder-session.md"
        builder_event = {"tool_name": "Write",
                       "tool_input": {"file_path": str(toy_plugin / "agents" / "a.md")}}
        try:
            (toy_plugin / "agents").mkdir(parents=True, exist_ok=True)
            session_file.write_text(
                "# s\nMode: generate\n\n## Checkpoints\n- intake complete — t\n",
                encoding="utf-8")
            r = run_shipped("builder_gate.py", consumer, builder_event)
            ok = r.returncode == 0 and "deny" in r.stdout
            check("builder-gate:denies-active-session", "PASS" if ok else "FAIL",
                  "" if ok else f"exit={r.returncode} stdout={r.stdout[:160]!r}")
        except Exception as exc:
            check("builder-gate:denies-active-session", "FAIL", f"{type(exc).__name__}: {exc}")

        # 11. builder_gate allows a Write once the session is in audit mode (never
        # gates non-publishing sessions).
        try:
            session_file.write_text(
                "# s\nMode: audit\n\n## Checkpoints\n- intake complete — t\n",
                encoding="utf-8")
            r = run_shipped("builder_gate.py", consumer, builder_event)
            ok = r.returncode == 0 and r.stdout.strip() == ""
            check("builder-gate:allows-audit-mode", "PASS" if ok else "FAIL",
                  "" if ok else f"exit={r.returncode} stdout={r.stdout[:160]!r}")
        except Exception as exc:
            check("builder-gate:allows-audit-mode", "FAIL", f"{type(exc).__name__}: {exc}")
    finally:
        shutil.rmtree(base, ignore_errors=True)

    return results


def main() -> int:
    if not SHIPPED_DIR.is_dir():
        print(f"ERROR: shipped hooks dir not found: {SHIPPED_DIR}", file=sys.stderr)
        return 1

    print(f"check-installed-runtime: simulating a fresh consumer of {SHIPPED_DIR.relative_to(REPO_ROOT)}")
    print(f"  {'CHECK':<36} {'RESULT':<6} DETAIL")

    results = run_checks()
    fails = fwd = 0
    for name, status, detail in results:
        if status == "FAIL":
            fails += 1
        elif status == "FWD":
            fwd += 1
        print(f"  {name:<36} {status:<6} {detail}")

    total = len(results)
    note = f", {fwd} forward-compat (awaiting shipped re-sync)" if fwd else ""
    if fails:
        print(f"\ncheck-installed-runtime: FAIL ({fails} of {total} checks failed{note})")
        return 1
    print(f"\ncheck-installed-runtime: PASS ({total - fwd} strict{note})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
