#!/usr/bin/env python3
"""
audit_append.py — Hook script for Stop and SubagentStop events.

Appends a single compact JSONL audit record to .ai-baseline/audit.<YYYY-MM-DD>.jsonl.
The record's model + token + plugin/agent fields are recovered from the session
transcript (deterministic, no LLM) via transcript_usage.summarize_since — previously
these were always null, which made the audit log uncosteable.

Two side effects beyond the audit line:
- Budget feed: the incremental USD cost of the appended record (per
  BENCHMARK-CONVENTIONS §1 — cache_read tokens excluded; rates from the
  pricing.json data file via _hooklib.model_pricing; without it the budget is
  left untouched and a warning names the file) is accrued into
  .ai-baseline/budget.json spent_usd. The file
  is created as {"limit_usd": null, "spent_usd": <increment>} when absent;
  limit_usd is never touched (null limit = "measure but never block" for
  cost_gate.py). Cursor semantics make each record incremental, so re-running
  over the same transcript never double-counts — and an advisory file lock
  (.ai-baseline/.lock) serializes overlapping Stop/SubagentStop processes
  (parallel subagent dispatch, dual registration) so concurrent hooks cannot
  each count the same transcript span or lose a budget increment to a
  read-modify-write race. Segments spanning more than one model tier are costed
  per turn model (transcript_usage by_model), never all at the last turn's rate.
- Attribution fallback: null app/feature fields are filled from
  .ai-baseline/context.json when present (explicit context wins), else from
  `git remote get-url origin` basename / current branch name.

Fail-open: any error writes a warning to stderr and exits 0 (never wedges the session).
Enrichment is strictly additive — if the transcript is unavailable or malformed, the
record is still written with the legacy null fields.

Usage:
    echo '<hook-json>' | python3 tools/hooks/audit_append.py --event stop
    echo '<hook-json>' | python3 tools/hooks/audit_append.py --event subagent-stop
    echo '<hook-json>' | python3 tools/hooks/audit_append.py --event stop --no-transcript
"""

import argparse
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _hooklib import (get_repo_root, read_stdin_json, cost_usd, git_output,
                      atomic_write_text, file_lock, PricingError)
from transcript_usage import summarize_since
from scoreable_agents import is_scoreable


def _repo_basename(url):
    """Repo name from a git remote URL: last path segment, .git stripped."""
    name = url.rstrip("/").rsplit("/", 1)[-1].rsplit(":", 1)[-1]
    if name.endswith(".git"):
        name = name[:-4]
    return name or None


def apply_attribution(record, repo_root):
    """Fill null app/feature on the record: explicit .ai-baseline/context.json
    wins, then git remote-basename / branch-name fallback. Only null fields are
    filled; plugin is transcript-owned and never touched. Never raises."""
    try:
        ctx_path = Path(repo_root) / ".ai-baseline" / "context.json"
        if ctx_path.exists():
            try:
                ctx = json.loads(ctx_path.read_text(encoding="utf-8")) or {}
            except Exception:
                ctx = {}
            if record.get("app") is None and ctx.get("app"):
                record["app"] = ctx["app"]
            if record.get("feature") is None and ctx.get("feature"):
                record["feature"] = ctx["feature"]
        if record.get("app") is None:
            url = git_output(["remote", "get-url", "origin"], cwd=repo_root)
            if url:
                record["app"] = _repo_basename(url)
        if record.get("feature") is None:
            branch = git_output(["branch", "--show-current"], cwd=repo_root)
            if branch:
                record["feature"] = branch
    except Exception as exc:
        sys.stderr.write(f"[audit_append] warning: attribution fallback failed: {exc}\n")
    return record


def update_budget(budget_path, increment_usd):
    """Accrue increment_usd into budget.json spent_usd. Absent file -> created as
    {"limit_usd": null, "spent_usd": <increment>}; limit_usd is NEVER touched
    (null means "measure but never block"). An unparseable existing file is left
    alone so a hand-edited limit is never clobbered. Written atomically
    (temp + rename) so cost_gate.py never reads a torn file; the caller holds
    the .ai-baseline/.lock so concurrent increments serialize instead of
    last-writer-wins. Best-effort, never raises."""
    try:
        p = Path(budget_path)
        data = {}
        if p.exists():
            try:
                data = json.loads(p.read_text(encoding="utf-8")) or {}
            except Exception:
                sys.stderr.write("[audit_append] warning: budget.json unparseable — skipping spend update\n")
                return
        if "limit_usd" not in data:
            data["limit_usd"] = None
        data["spent_usd"] = round(float(data.get("spent_usd") or 0.0) + float(increment_usd), 10)
        atomic_write_text(p, json.dumps(data, separators=(",", ":")) + "\n")
    except Exception as exc:
        sys.stderr.write(f"[audit_append] warning: budget update failed: {exc}\n")


def _read_cursor(cursor_path, session_id, key):
    try:
        data = json.loads(Path(cursor_path).read_text(encoding="utf-8"))
        return (data.get(session_id) or {}).get(key)
    except Exception:
        return None


def _write_cursor(cursor_path, session_id, key, last_uuid):
    try:
        p = Path(cursor_path)
        data = {}
        if p.exists():
            try:
                data = json.loads(p.read_text(encoding="utf-8")) or {}
            except Exception:
                data = {}
        data.setdefault(session_id, {})[key] = last_uuid
        atomic_write_text(p, json.dumps(data))
    except Exception:
        pass  # cursor is best-effort; never fail the hook over it


def _write_pending_stub(pending_path, stub) -> None:
    """Queue a tiny quality-score stub (no LLM, no output copied — just a transcript ref)."""
    try:
        p = Path(pending_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(stub, separators=(",", ":")) + "\n")
    except Exception:
        pass  # best-effort; never fail the hook over a stub


def build_record(payload: dict, event: str, no_transcript: bool = False,
                 cursor_path=None, pending_path=None, cost_out=None) -> dict:
    """Build the 15-field audit record, enriched from the transcript when available.

    Pure given (payload, event); only touches the cursor file when cursor_path is set.
    Never raises — enrichment failures degrade to the legacy null record.
    When cost_out (a dict) is given, its "usd" key receives the segment's exact
    per-model USD cost (summed over transcript_usage's by_model buckets) so a
    mixed-tier segment is never priced entirely at the last turn's rate.
    """
    session_id = payload.get("session_id") or str(uuid.uuid4())
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")

    record = {
        "schema_version": "1.0.0",
        "ts": ts,
        "session_id": session_id,
        "correlation_id": str(uuid.uuid4()),
        "parent_correlation_id": None,
        "app": None,
        "feature": None,
        "plugin": None,
        "agent": "hook",
        "command": f"hook:{event}",
        "model": None,
        "input_hash": None,
        "output_hash": None,
        "tokens_in": None,
        "tokens_out": None,
    }

    transcript_path = payload.get("transcript_path")
    if transcript_path and not no_transcript:
        try:
            sidechain = (event == "subagent-stop")
            key = "sub" if sidechain else "main"
            after = _read_cursor(cursor_path, session_id, key) if cursor_path else None
            s = summarize_since(transcript_path, after_uuid=after, sidechain_only=sidechain)
            record["model"] = s["model"]
            record["tokens_in"] = s["tokens_in"]
            record["tokens_out"] = s["tokens_out"]
            record["plugin"] = s["plugin"]
            record["agent"] = s["agent"] or "hook"
            if cost_out is not None:
                by_model = s.get("by_model") or {}
                if by_model:
                    try:
                        cost_out["usd"] = sum(
                            cost_usd(m, b.get("tokens_in"), b.get("tokens_out"))
                            for m, b in by_model.items())
                    except PricingError as exc:
                        cost_out["error"] = exc  # the record stays; main skips the budget
            if cursor_path and s["last_uuid"]:
                _write_cursor(cursor_path, session_id, key, s["last_uuid"])
            # Queue a quality-score stub for scoreable subagent dispatches (cost-aware 1b
            # path) — deterministic, no LLM; /score-pending drains it off the hot path.
            if pending_path and sidechain and s["model"] and is_scoreable(s["agent"]):
                _write_pending_stub(pending_path, {
                    "ts": ts,
                    "agent": s["agent"],
                    "plugin": s["plugin"],
                    "model": s["model"],
                    "session_id": session_id,
                    "output_ref": {"transcript_path": transcript_path, "last_uuid": s["last_uuid"]},
                    "status": "pending",
                })
        except Exception as exc:
            sys.stderr.write(f"[audit_append] warning: transcript enrichment failed: {exc}\n")
            # leave the legacy null fields in place (fail-open, additive)

    return record


def main() -> int:
    parser = argparse.ArgumentParser(description="Append audit entry on Stop/SubagentStop")
    parser.add_argument("--event", required=True, help="Event name, e.g. stop or subagent-stop")
    parser.add_argument("--no-transcript", action="store_true",
                        help="Skip transcript enrichment (legacy null record)")
    args = parser.parse_args()

    try:
        payload = read_stdin_json() or {}
        repo_root = get_repo_root()
        baseline_dir = Path(repo_root) / ".ai-baseline"
        baseline_dir.mkdir(parents=True, exist_ok=True)
        cursor_path = baseline_dir / ".audit-cursor.json"
        pending_path = Path(repo_root) / ".ai-evolution" / "feedback.jsonl.pending"

        # Serialize the cursor-read → summarize → cursor-write → budget-accrue
        # critical section across concurrent hook processes: without the lock,
        # overlapping Stop/SubagentStop events each read the pre-update cursor
        # (double-counting the same transcript span) and lose budget increments
        # to last-writer-wins. flock is released on process exit — a crashed
        # holder can never wedge the next hook — and file_lock itself fails open.
        with file_lock(baseline_dir / ".lock"):
            cost_info = {}
            record = build_record(payload, args.event, no_transcript=args.no_transcript,
                                  cursor_path=cursor_path, pending_path=pending_path,
                                  cost_out=cost_info)
            apply_attribution(record, repo_root)

            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            audit_file = baseline_dir / f"audit.{today}.jsonl"
            line = json.dumps(record, separators=(",", ":")) + "\n"
            with open(audit_file, "a", encoding="utf-8") as fh:
                fh.write(line)

            # Feed the cost gate: accrue this record's incremental USD cost into
            # .ai-baseline/budget.json (cursor semantics above keep it incremental).
            # Prefer the exact per-model segment cost; fall back to pricing the
            # record's summed tokens at its (single) model rate.
            # Without readable pricing data the budget is left as it is (never
            # accrued at a made-up rate); the audit record above is kept.
            try:
                if "error" in cost_info:
                    raise cost_info["error"]
                increment = cost_info.get("usd")
                if increment is None:
                    increment = cost_usd(record.get("model"), record.get("tokens_in"),
                                         record.get("tokens_out"))
            except PricingError as exc:
                sys.stderr.write(f"[audit_append] warning: budget not updated: {exc}\n")
            else:
                update_budget(baseline_dir / "budget.json", increment)

    except Exception as exc:
        sys.stderr.write(f"[audit_append] warning: failed to append audit entry: {exc}\n")
        return 0  # FAIL-OPEN

    return 0


if __name__ == "__main__":
    sys.exit(main())
