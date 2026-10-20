#!/usr/bin/env python3
"""
transcript_usage.py — recover per-dispatch model + token usage + plugin/agent
attribution from a Claude Code session transcript (JSONL).

Pure stdlib, tolerant (skips malformed lines, returns a zeroed summary on a missing
file). Used by audit_append.py to populate the audit record that was previously hollow,
and to capture quality-score stubs — all deterministic, no LLM.

Transcript shape (verified 2026-06-23): each assistant turn carries
`message.model`, `message.usage.{input_tokens,cache_creation_input_tokens,
cache_read_input_tokens,output_tokens}`, plus top-level `uuid`, `isSidechain`,
`attributionPlugin`, `attributionSkill`.

CLI (debug):  python3 tools/hooks/transcript_usage.py <transcript.jsonl> [--sidechain]
"""

from __future__ import annotations

import json
from typing import Optional


def _empty() -> dict:
    return {"model": None, "tokens_in": 0, "tokens_out": 0, "cache_read": 0,
            "by_model": {}, "plugin": None, "agent": None, "last_uuid": None}


def summarize_since(transcript_path: str, after_uuid: Optional[str] = None,
                    sidechain_only: bool = False) -> dict:
    """Aggregate assistant-turn usage for one dispatch.

    - Counts only turns AFTER the line whose `uuid == after_uuid` (cursor); if
      `after_uuid` is None, counts from the start.
    - `sidechain_only=False` → main-agent turns (isSidechain falsy); True → subagent
      turns (isSidechain truthy).
    - tokens_in = input_tokens + cache_creation (fresh-processed tokens, billed >=1x).
      cache_read is tracked SEPARATELY (cheap ~0.1x and dominated by session length,
      not work done — folding it into tokens_in overstates cost; verified on a real
      30M-cache-read transcript). cost-units applies one blended per-tier weight to
      tokens_in+tokens_out per BENCHMARK-CONVENTIONS §1.
    - model is the last matching turn's model; plugin/agent are the last turn's
      attributionPlugin/attributionSkill.
    - by_model buckets tokens_in/tokens_out per turn model, so a segment spanning
      more than one tier (mid-session /model switch) can be costed at each turn's
      real rate — never all at the last turn's rate (audit_append budget feed).
    """
    summary = _empty()
    seen_cursor = after_uuid is None
    try:
        with open(transcript_path, encoding="utf-8") as fh:
            for raw in fh:
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    o = json.loads(raw)
                except Exception:
                    continue  # tolerant: skip malformed line
                uuid = o.get("uuid")
                if not seen_cursor:
                    if uuid == after_uuid:
                        seen_cursor = True
                    continue  # skip everything up to and including the cursor line
                if o.get("type") != "assistant":
                    continue
                if bool(o.get("isSidechain")) != bool(sidechain_only):
                    continue
                msg = o.get("message") or {}
                usage = msg.get("usage") or {}
                turn_in = ((usage.get("input_tokens") or 0)
                           + (usage.get("cache_creation_input_tokens") or 0))
                turn_out = usage.get("output_tokens") or 0
                summary["tokens_in"] += turn_in
                summary["cache_read"] += (usage.get("cache_read_input_tokens") or 0)
                summary["tokens_out"] += turn_out
                if turn_in or turn_out:
                    bucket = summary["by_model"].setdefault(
                        msg.get("model"), {"tokens_in": 0, "tokens_out": 0})
                    bucket["tokens_in"] += turn_in
                    bucket["tokens_out"] += turn_out
                if msg.get("model"):
                    summary["model"] = msg["model"]
                if o.get("attributionPlugin"):
                    summary["plugin"] = o["attributionPlugin"]
                if o.get("attributionSkill"):
                    summary["agent"] = o["attributionSkill"]
                if uuid:
                    summary["last_uuid"] = uuid
    except FileNotFoundError:
        return _empty()
    except Exception:
        return summary  # tolerant: return what we have so far
    return summary


def extract_output(transcript_path: str, turn_uuid: str) -> str:
    """Return the concatenated text of the assistant turn with the given uuid — the
    subagent's final output, referenced by a pending stub's output_ref. '' if not found."""
    try:
        with open(transcript_path, encoding="utf-8") as fh:
            for raw in fh:
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    o = json.loads(raw)
                except Exception:
                    continue
                if o.get("uuid") == turn_uuid and o.get("type") == "assistant":
                    content = (o.get("message") or {}).get("content")
                    if isinstance(content, str):
                        return content
                    if isinstance(content, list):
                        return "".join(b.get("text", "") for b in content
                                       if isinstance(b, dict) and b.get("type") == "text")
    except Exception:
        return ""
    return ""


if __name__ == "__main__":
    import sys
    if len(sys.argv) >= 4 and sys.argv[1] == "--extract":
        # python3 transcript_usage.py --extract <transcript> <uuid>
        print(extract_output(sys.argv[2], sys.argv[3]))
        sys.exit(0)
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    side = "--sidechain" in sys.argv[2:]
    print(json.dumps(summarize_since(sys.argv[1], sidechain_only=side), indent=2))
