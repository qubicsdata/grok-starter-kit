"""Run logging for run-claude.sh: runs.jsonl start/finish lines, result extraction, rate-limit capture."""
import json, os
from .common import append_jsonl, iso, log_path, now_ts

USAGE_KEYS = ("inputTokens", "outputTokens", "cacheReadInputTokens", "cacheCreationInputTokens", "thinkingTokens", "costUSD")


def log_start(cfg, run_id, label, info, cwd, output_format, pid=None):
    rec = {"ts": iso(now_ts()), "event": "start", "run_id": run_id, "label": label,
           "task_type": info.get("task_type"), "model": info.get("model"),
           "model_source": info.get("source"), "override": info.get("source", "").startswith("override"),
           "reason": info.get("reason"), "fallback_model": info.get("fallback_model"),
           "subagent_model": info.get("subagent_model"), "effort": info.get("effort"),
           "profile": info.get("profile"), "experiments": info.get("experiments") or [],
           "settings": info.get("settings"), "extra_flags": info.get("extra_flags") or [], "cwd": cwd, "output_format": output_format,
           "pid": pid}
    append_jsonl(log_path(cfg, "runs.jsonl"), rec)
    return rec


def rate_info_to_usage(info, ts, run_id, session_id=None):
    """Convert a stream-json rate_limit_event.rate_limit_info into a usage.jsonl record (seed-compatible keys)."""
    uw = info.get("unifiedWindows") or {}
    rec = {"ts": iso(ts), "source": "claude-code stream-json rate_limit_event", "kind": "rate_limit_event",
           "observed": True, "run_id": run_id, "session_id": session_id,
           "status": info.get("status"), "rate_limit_type": info.get("rateLimitType"),
           "resets_at": iso(info["resetsAt"]) if isinstance(info.get("resetsAt"), (int, float)) else None}
    fh = uw.get("five_hour")
    if fh:
        rec["session_5h"] = {"used_pct": round(fh.get("utilization", 0) * 100, 1),
                             "resets_at": iso(fh.get("resetsAt")) if fh.get("resetsAt") else None}
    sd = uw.get("seven_day")
    if sd:
        rec["weekly_all_models"] = {"used_pct": round(sd.get("utilization", 0) * 100, 1),
                                    "resets_at": iso(sd.get("resetsAt")) if sd.get("resetsAt") else None}
    for k, v in uw.items():
        if k not in ("five_hour", "seven_day") and isinstance(v, dict):
            rec.setdefault("other_windows", {})[k] = {"used_pct": round(v.get("utilization", 0) * 100, 1),
                                                      "resets_at": iso(v.get("resetsAt")) if v.get("resetsAt") else None}
    if info.get("utilization") is not None:
        rec["utilization"] = info["utilization"]
    if info.get("overageStatus"):
        rec["overage_status"] = info["overageStatus"]
    return rec


def _event_key(info):
    uw = info.get("unifiedWindows") or {}
    return (info.get("status"), info.get("rateLimitType"), info.get("resetsAt"),
            tuple(sorted((k, round((v or {}).get("utilization", 0), 2), (v or {}).get("resetsAt"))
                         for k, v in uw.items() if isinstance(v, dict))))


def parse_stream(path):
    """Return (result_line_str, result_obj, [rate_limit_info...]) from a stream-json output file."""
    result_line, result, events = None, None, []
    try:
        with open(path, errors="replace") as f:
            for line in f:
                if '"type":"result"' not in line and '"rate_limit_event"' not in line:
                    continue
                try:
                    d = json.loads(line)
                except ValueError:
                    continue
                if d.get("type") == "result":
                    result_line, result = line if line.endswith("\n") else line + "\n", d
                elif d.get("type") == "rate_limit_event" and isinstance(d.get("rate_limit_info"), dict):
                    events.append((d["rate_limit_info"], d.get("session_id")))
    except FileNotFoundError:
        pass
    return result_line, result, events


LIMIT_TEXT = ("usage limit", "hit your limit", "rate limit", "rate_limit", "limit reached")


def log_finish(cfg, run_id, rc, out_path, fmt, json_out=None):
    """Write the finish record. For stream-json, also write the result line to json_out and capture rate-limit events."""
    ts = now_ts()
    result, events = None, []
    if fmt == "stream-json":
        line, result, events = parse_stream(out_path)
        if json_out:
            with open(json_out, "w") as f:
                f.write(line or "")
    else:
        try:
            with open(out_path) as f:
                txt = f.read().strip()
            result = json.loads(txt) if txt else None
        except (FileNotFoundError, ValueError):
            result = None
    # rate-limit events -> usage.jsonl (deduplicated: only changes, plus the last one)
    seen, kept = set(), []
    for info, sid in events:
        k = _event_key(info)
        if k in seen:
            continue
        seen.add(k)
        kept.append((info, sid))
    if events and (events[-1][0], events[-1][1]) not in kept:
        kept.append(events[-1])
    for info, sid in kept:
        append_jsonl(log_path(cfg, "usage.jsonl"), rate_info_to_usage(info, ts, run_id, sid))
    rec = {"ts": iso(ts), "event": "finish", "run_id": run_id, "rc": rc, "output_format": fmt}
    if result:
        mu = result.get("modelUsage") or {}
        rec.update({
            "session_id": result.get("session_id"), "is_error": result.get("is_error"),
            "subtype": result.get("subtype"), "api_error_status": result.get("api_error_status"),
            "num_turns": result.get("num_turns"), "duration_ms": result.get("duration_ms"),
            "models_reported": sorted(mu),
            "modelUsage": {m: {k: v.get(k) for k in USAGE_KEYS if k in v} for m, v in mu.items()},
        })
        text = str(result.get("result") or "")[:500].lower()
        if result.get("is_error") and (any(t in text for t in LIMIT_TEXT) or result.get("api_error_status") == 429):
            rec["limit_hit"] = True
            append_jsonl(log_path(cfg, "usage.jsonl"), {
                "ts": iso(ts), "source": "result error text", "kind": "limit_hit", "observed": True,
                "run_id": run_id, "text": str(result.get("result"))[:200]})
    else:
        rec["result_missing"] = True
    if kept:
        last = rate_info_to_usage(kept[-1][0], ts, run_id)
        rec["rate_limit_last"] = {k: last.get(k) for k in ("status", "rate_limit_type", "session_5h", "weekly_all_models")}
    append_jsonl(log_path(cfg, "runs.jsonl"), rec)
    return rec
