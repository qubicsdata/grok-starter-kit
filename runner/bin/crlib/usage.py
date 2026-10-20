"""Usage-window awareness.

Signals, best first:
  1. PRIMARY: stream-json rate_limit_event (every headless run emits one): exact utilization + resetsAt for the
     five_hour and seven_day windows. OBSERVED (server-provided). A fresh event wins over any other reading.
  2. `claude -p "/usage"` (local slash command, $0), run by the scheduler itself at most every
     min_probe_spacing_minutes (30). Minute precision. The only source of the Fable-only weekly %. OBSERVED.
     probe_fallback is "none": there is no tmux / interactive screen scrape anywhere.
  3. local session JSONL token counts (this machine only) -> inferred 5h blocks and rolling weekly totals. INFERRED.
  4. budgets (config / calibration) turn local tokens into estimated percentages. ESTIMATE.
  probe_failed -> 1 + 3/4; with neither, effective() reports basis "none" and the backlog runs under near_cap.
"""
import fcntl, glob, json, os, re, subprocess, time, uuid
from datetime import datetime, timedelta
from .common import (append_jsonl, iso, local_tz, log_path, model_family, now_ts, parse_ts,
                     read_jsonl, to_epoch)
from . import policy as P

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PCT_RE = re.compile(r"(\d{1,3}(?:\.\d+)?)%\s*used")
RESET_RE = re.compile(r"Resets\s+(?:(?P<mon>[A-Z][a-z]{2})\s+(?P<day>\d{1,2}),\s*)?(?P<h>\d{1,2})(?::(?P<m>\d{2}))?\s*(?P<ap>am|pm)", re.I)
MONTHS = {m: i + 1 for i, m in enumerate("Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split())}


def redact(text):
    return EMAIL_RE.sub("<redacted-email>", text or "")


def _parse_reset(line, now):
    m = RESET_RE.search(line)
    if not m:
        return None
    h = int(m.group("h")) % 12 + (12 if m.group("ap").lower() == "pm" else 0)
    mi = int(m.group("m") or 0)
    nd = datetime.fromtimestamp(now, tz=local_tz())
    if m.group("mon"):
        d = nd.replace(month=MONTHS[m.group("mon").title()], day=int(m.group("day")), hour=h, minute=mi,
                       second=0, microsecond=0)
        if d.timestamp() < now - 200 * 86400:
            d = d.replace(year=d.year + 1)
    else:
        d = nd.replace(hour=h, minute=mi, second=0, microsecond=0)
        if d.timestamp() < now - 120:  # time-only means the next occurrence
            d += timedelta(days=1)
    return d.timestamp()


def parse_usage_screen(text, now=None):
    """Parse only the usage lines of the /usage screen. Returns dict with session_5h / weekly_* or {}."""
    now = now if now is not None else now_ts()
    lines = redact(text).splitlines()
    out, cur = {}, None
    for line in lines:
        s = line.strip()
        head = None
        if s.startswith("Current session"):
            head = "session_5h"
        elif s.startswith("Current week"):
            m = re.search(r"\(([^)]*)\)", s)
            name = (m.group(1) if m else "all models").strip().lower()
            if name.endswith(" only"):  # "(Fable only)" and "(Fable)" both -> weekly_fable
                name = name[:-5].strip()
            head = "weekly_all_models" if name == "all models" else "weekly_" + re.sub(r"[^a-z0-9]+", "_", name).strip("_")
        if head:
            cur = head
            # one-line form from `claude -p /usage`: "Current session: 5% used · resets Oct 15, 10:50pm (...)"
            if PCT_RE.search(s):
                out.setdefault(cur, {})["used_pct"] = float(PCT_RE.search(s).group(1))
                r = _parse_reset(s, now)
                if r:
                    out[cur]["resets_at"] = iso(r)
                cur = None
            continue
        if cur and PCT_RE.search(s):
            out.setdefault(cur, {})["used_pct"] = float(PCT_RE.search(s).group(1))
        elif cur and s.startswith("Resets"):
            r = _parse_reset(s, now)
            if r:
                out.setdefault(cur, {})["resets_at"] = iso(r)
            cur = None
        elif s.startswith("What's contributing") or s.startswith("Last 24h"):
            cur = None
    for v in out.values():
        if isinstance(v, dict):
            v.setdefault("resets_at", None)
    return out


# Always removed from the probe's environment: the probe must use your subscription login, never an API key.
PROBE_UNSET_ENV = ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN")
ENV_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def probe_unset_env(cfg):
    """usage.probe_unset_env: extra variable names to remove for the probe (e.g. tokens your shell sets for other
    tools). Names that are not valid variable names are ignored."""
    names = (cfg.get("usage") or {}).get("probe_unset_env") or []
    return [n for n in names if isinstance(n, str) and ENV_NAME_RE.match(n) and n not in PROBE_UNSET_ENV]


def probe_print(cfg, runner=None):
    """`claude -p /usage`: a local slash command (num_turns 0, no modelUsage, total_cost_usd 0). Returns redacted text."""
    if runner is None and os.environ.get("CR_TEST_NO_REAL_CLAUDE") == "1" and subprocess.run is _REAL_RUN:
        raise RuntimeError("real `claude -p /usage` refused under CR_TEST_NO_REAL_CLAUDE (tests use fake probers)")
    runner = runner or subprocess.run  # looked up at call time (tests patch usage.subprocess.run)
    unset = []
    for v in PROBE_UNSET_ENV + tuple(probe_unset_env(cfg)):
        unset += ["-u", v]
    os.makedirs(cfg["usage"]["probe_dir"], exist_ok=True)
    p = runner(["env"] + unset + ["DISABLE_TELEMETRY=1", "DISABLE_ERROR_REPORTING=1", "claude", "-p", "/usage",
                                  "--output-format", "json", "--strict-mcp-config"],
               capture_output=True, text=True, timeout=90, stdin=subprocess.DEVNULL, cwd=cfg["usage"]["probe_dir"])
    try:
        d = json.loads(p.stdout or "")
    except ValueError:
        return ""
    if d.get("modelUsage"):  # it must stay a local command; never treat a model reply as a reading
        return ""
    return redact(str(d.get("result") or ""))


_REAL_RUN = subprocess.run
PROBES = {"print": probe_print}  # the only probe; there is no tmux screen scrape


def probe_auto(cfg):
    """`claude -p /usage` only. probe_fallback must be "none"; any other value (e.g. the old "tmux") is ignored."""
    m = P.value(cfg, "usage", "probe_method")
    fn = PROBES.get(m)
    if fn is None:
        return ""
    txt = fn(cfg)
    p = parse_usage_screen(txt)
    return txt if ("session_5h" in p or "weekly_all_models" in p) else ""


def last_probe_ts(cfg):
    for r in reversed(read_jsonl(log_path(cfg, "usage.jsonl"))):
        if r.get("kind") in ("usage_screen", "probe_failed"):
            return to_epoch(r["ts"]) or 0
    return 0


def probe_due(cfg, now=None, spacing_minutes=None):
    """True when the last /usage probe (ok or failed) is older than spacing_minutes (default
    min_probe_spacing_minutes, 30, never less; the Fable near-park re-probe passes its own spacing, 5 at least)."""
    now = now if now is not None else now_ts()
    sp = P.probe_spacing_minutes(cfg) if spacing_minutes is None else spacing_minutes
    return now - last_probe_ts(cfg) > sp * 60


def last_probe_failed(recs):
    """True when the newest /usage probe record (usage_screen | probe_failed) is a failure."""
    for r in reversed(recs):
        if r.get("kind") == "probe_failed":
            return True
        if r.get("kind") == "usage_screen":
            return False
    return False


def poll(cfg, screen_text=None, now=None, prober=None):
    """Take one /usage reading and append it to usage.jsonl (kind usage_screen). Returns the record or None."""
    now = now if now is not None else now_ts()
    lock = log_path(cfg, ".usage-probe.lock")
    os.makedirs(os.path.dirname(lock), exist_ok=True)
    with open(lock, "w") as lf:
        try:
            fcntl.flock(lf, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            return None  # another probe is running
        if screen_text is None:
            screen_text = (prober or probe_auto)(cfg)
        parsed = parse_usage_screen(screen_text, now)
        if "session_5h" not in parsed and "weekly_all_models" not in parsed:
            append_jsonl(log_path(cfg, "usage.jsonl"), {"ts": iso(now), "kind": "probe_failed",
                                                        "source": "claude -p /usage", "observed": False,
                                                        "fallback": "rate_limit_event + estimates; none -> near_cap"})
            return None
        src = "claude-code /usage v2.1.300 (%s)" % ("claude -p /usage" if ": " in screen_text and "% used ·" in screen_text
                                                     else "saved capture")
        rec = {"ts": iso(now), "source": src, "kind": "usage_screen", "observed": True}
        rec.update(parsed)
        if rec.get("session_5h", {}).get("resets_at"):
            rec["session_5h"]["start_at_inferred"] = iso(to_epoch(rec["session_5h"]["resets_at"]) - cfg["usage"]["window_hours"] * 3600)
            rec["session_5h"]["start_observed"] = False
        append_jsonl(log_path(cfg, "usage.jsonl"), rec)
        return rec


# ---------------- local JSONL (inferred) ----------------

def iter_messages(projects_dir, since_ts):
    """Deduplicated assistant messages with usage from Claude Code session JSONLs: (ts, model, usage)."""
    root = os.path.expanduser(projects_dir)
    seen, out = set(), []
    for path in glob.glob(os.path.join(root, "**", "*.jsonl"), recursive=True):
        try:
            if os.path.getmtime(path) < since_ts:
                continue
            f = open(path, errors="replace")
        except OSError:
            continue
        with f:
            for line in f:
                if '"assistant"' not in line or '"usage"' not in line:
                    continue
                try:
                    d = json.loads(line)
                except ValueError:
                    continue
                if d.get("type") != "assistant":
                    continue
                msg = d.get("message") or {}
                u = msg.get("usage")
                ts = d.get("timestamp")
                if not u or not ts:
                    continue
                key = (msg.get("id"), d.get("requestId"))
                if key != (None, None):
                    if key in seen:
                        continue
                    seen.add(key)
                t = to_epoch(ts)
                if t is None or t < since_ts:
                    continue
                model = msg.get("model") or "unknown"
                if model == "<synthetic>":
                    continue
                out.append((t, model, u))
    out.sort(key=lambda x: x[0])
    return out


def weighted(cfg, model, u):
    tw, mw = cfg["usage"]["token_weights"], cfg["usage"]["model_weights"]
    base = (u.get("input_tokens", 0) * tw["input"] + u.get("output_tokens", 0) * tw["output"]
            + u.get("cache_read_input_tokens", 0) * tw["cache_read"]
            + u.get("cache_creation_input_tokens", 0) * tw["cache_creation"])
    return base * mw.get(model_family(model), mw.get("other", 1.0))


def _acc(tot, model, u):
    m = tot.setdefault(model, {"input": 0, "output": 0, "cache_read": 0, "cache_creation": 0, "messages": 0})
    m["input"] += u.get("input_tokens", 0)
    m["output"] += u.get("output_tokens", 0)
    m["cache_read"] += u.get("cache_read_input_tokens", 0)
    m["cache_creation"] += u.get("cache_creation_input_tokens", 0)
    m["messages"] += 1


def blocks(messages, window_hours=5, anchors=()):
    """Chain 5h blocks: a block starts at the first message at/after the previous block's end
    (i.e. after a gap or after the block expired). Start = that message's timestamp (not floored).
    anchors: observed server reset times; a block never spans one (the next block starts at the
    first message at/after the anchor)."""
    W = window_hours * 3600
    anchors = sorted(a for a in anchors if a)
    out = []
    for t, model, u in messages:
        cross = out and any(out[-1]["start"] < a <= t for a in anchors)
        if not out or t >= out[-1]["start"] + W or cross:
            if cross and out:
                out[-1]["end"] = min(out[-1]["end"], max(a for a in anchors if out[-1]["start"] < a <= t))
            out.append({"start": t, "end": t + W, "last": t, "messages": []})
        b = out[-1]
        b["last"] = t
        b["messages"].append((t, model, u))
    return out


def summarize_block(cfg, b, now):
    tot, w = {}, 0.0
    for t, model, u in b["messages"]:
        _acc(tot, model, u)
        w += weighted(cfg, model, u)
    elapsed_min = max(1.0, (min(now, b["end"]) - b["start"]) / 60.0)
    out_tokens = sum(v["output"] for v in tot.values())
    return {"start": iso(b["start"]), "expected_reset": iso(b["end"]), "last_message": iso(b["last"]),
            "active": b["start"] <= now < b["end"], "tokens_by_model": tot, "weighted_tokens": round(w),
            "burn_weighted_per_min": round(w / elapsed_min), "burn_output_per_min": round(out_tokens / elapsed_min)}


def rollup(cfg, messages, start, end):
    tot, w = {}, 0.0
    for t, model, u in messages:
        if start <= t < end:
            _acc(tot, model, u)
            w += weighted(cfg, model, u)
    return {"from": iso(start), "to": iso(end), "tokens_by_model": tot, "weighted_tokens": round(w)}


# ---------------- combined state ----------------

def _stream_events(cfg, since):
    """Live rate_limit_events from runner stream files of runs still writing (not yet in usage.jsonl)."""
    out = []
    for p in glob.glob(os.path.join(cfg["paths"]["logs"], "streams", "*.jsonl")):
        try:
            mt = os.path.getmtime(p)
        except OSError:
            continue
        if mt < since:
            continue
        last = None
        try:
            with open(p, errors="replace") as f:
                for line in f:
                    if '"rate_limit_event"' in line:
                        last = line
        except OSError:
            continue
        if last:
            try:
                d = json.loads(last)
                from .runlog import rate_info_to_usage
                rec = rate_info_to_usage(d["rate_limit_info"], mt, os.path.basename(p)[:-6], d.get("session_id"))
                rec["source"] += " (live stream)"
                out.append(rec)
            except (ValueError, KeyError, TypeError):
                pass
    return out


def session_anchors(obs):
    """Observed 5h reset times. rate_limit_event values are exact; screen/seed values (minute precision,
    seen ~1 min early) are used only when no event value lies within 3 minutes."""
    ev = sorted({to_epoch(o["session_5h"]["resets_at"]) for o in obs if o.get("kind") == "rate_limit_event"
                 and (o.get("session_5h") or {}).get("resets_at")})
    other = sorted({to_epoch(o["session_5h"]["resets_at"]) for o in obs if o.get("kind") != "rate_limit_event"
                    and (o.get("session_5h") or {}).get("resets_at")})
    return ev + [a for a in other if all(abs(a - e) > 180 for e in ev)]


def load_calibration(cfg):
    try:
        with open(log_path(cfg, "usage-calibration.json")) as f:
            return json.load(f)
    except (FileNotFoundError, ValueError):
        return {}


def _window(obs_list, key, now, stale_s):
    cands = [o for o in obs_list if isinstance(o.get(key), dict) and o[key].get("used_pct") is not None]
    if not cands:
        return None
    # rate_limit_event is the primary source: the newest event wins while it is fresh; otherwise the newest reading
    ev = [o for o in cands if o.get("kind") == "rate_limit_event" and now - (to_epoch(o["ts"]) or 0) <= stale_s]
    o = max(ev or cands, key=lambda r: to_epoch(r["ts"]) or 0)
    w = o[key]
    ts = to_epoch(o["ts"])
    reset = to_epoch(w.get("resets_at"))
    res = {"used_pct": w["used_pct"], "resets_at": w.get("resets_at"), "observed_at": o["ts"],
           "source": o.get("source"), "kind": o.get("kind"), "age_min": round((now - ts) / 60, 1),
           "stale": (now - ts) > stale_s, "reset_passed": bool(reset and reset <= now)}
    if res["reset_passed"]:
        res["observed_used_pct"] = w["used_pct"]
        res["used_pct"] = 0.0
        res["note"] = "reset time passed after the last reading; assumed 0% until a new reading (inferred)"
        res["stale"] = True
    return res


def state(cfg, now=None, include_local=True, messages=None):
    now = now if now is not None else now_ts()
    u = cfg["usage"]
    stale_s = u["stale_minutes"] * 60
    recs = read_jsonl(log_path(cfg, "usage.jsonl"))
    obs = [r for r in recs if r.get("kind") in ("seed", "usage_screen", "rate_limit_event")]
    obs += _stream_events(cfg, now - 6 * 3600)
    st = {"now": iso(now), "session": _window(obs, "session_5h", now, stale_s),
          "weekly": _window(obs, "weekly_all_models", now, stale_s),
          "weekly_fable": _window(obs, "weekly_fable", now, stale_s),
          "last_probe_failed": last_probe_failed(recs)}  # /usage "Current week (Fable only)"; no stream event carries it
    # limit / park
    park_statuses = set(P.value(cfg, "policy", "rate_limit_park_statuses"))
    park = None
    for r in sorted(recs + obs, key=lambda r: to_epoch(r.get("ts")) or 0):
        k = r.get("kind")
        if k == "rate_limit_event" and r.get("status") in park_statuses:
            ra = to_epoch(r.get("resets_at"))
            park = {"since": r["ts"], "resume_at": r.get("resets_at"), "source": "rate_limit_event status=%s type=%s"
                    % (r.get("status"), r.get("rate_limit_type")), "authoritative": True, "_ra": ra}
        elif k == "rate_limit_event" and r.get("status") not in park_statuses and park and \
                (to_epoch(r["ts"]) or 0) > (to_epoch(park["since"]) or 0):
            park = None  # a later "allowed" event clears it
        elif k == "limit_hit":
            ra = to_epoch((st["session"] or {}).get("resets_at"))
            park = {"since": r["ts"], "resume_at": iso(ra) if ra else None,
                    "source": "limit_hit (result error text); resume = session resets_at", "authoritative": False, "_ra": ra}
    if park:
        ra = park.pop("_ra")
        if ra is None:
            ra = to_epoch(park["since"]) + u["window_hours"] * 3600
            park["resume_at"] = iso(ra)
            park["source"] += "; no reset known -> since+window (inferred)"
        park["active"] = now < ra + cfg["policy"].get("resume_grace_seconds", 60)
        st["park"] = park
    else:
        st["park"] = None
    if include_local:
        week_s = u["weekly_days"] * 86400
        msgs = messages if messages is not None else iter_messages(u["projects_dir"], now - week_s - 6 * 3600)
        bl = blocks(msgs, u["window_hours"], anchors=session_anchors(obs))
        cur = [b for b in bl if b["start"] <= now < b["end"]]
        cal = load_calibration(cfg)
        b5 = cal.get("five_hour_weighted") or u["budgets_estimate"]["five_hour_weighted"]
        bw = cal.get("weekly_weighted") or u["budgets_estimate"]["weekly_weighted"]
        loc = {"inferred": True, "block": summarize_block(cfg, cur[0], now) if cur else None,
               "recent_blocks": [summarize_block(cfg, b, now)["start"] for b in bl[-4:]],
               "weekly_rolling": rollup(cfg, msgs, now - week_s, now + 1),
               "budget_five_hour_weighted": b5, "budget_weekly_weighted": bw,
               "weighted_lookback": rollup(cfg, msgs, now - cfg.get("backlog", {}).get("burn_lookback_hours", 3) * 3600, now + 1)["weighted_tokens"],
               "budget_source": "calibration" if cal else "config estimate"}
        wk_reset = to_epoch((st["weekly"] or {}).get("resets_at"))
        if wk_reset and not (st["weekly"] or {}).get("reset_passed"):
            loc["weekly_server_window"] = rollup(cfg, msgs, wk_reset - week_s, now + 1)
        if loc["block"]:
            loc["est_session_pct"] = round(100.0 * loc["block"]["weighted_tokens"] / b5, 1)
        else:
            loc["est_session_pct"] = 0.0
        loc["est_weekly_pct"] = round(100.0 * loc["weekly_rolling"]["weighted_tokens"] / bw, 1)
        st["local"] = loc
    return st


def effective(cfg, st, now=None):
    """Numbers the scheduler uses: observed when fresh, else max(observed-but-stale, local estimate)."""
    now = now if now is not None else now_ts()
    loc = st.get("local") or {}
    out = {}
    for key, est_key, win_s in (("session", "est_session_pct", cfg["usage"]["window_hours"] * 3600),
                                ("weekly", "est_weekly_pct", cfg["usage"]["weekly_days"] * 86400)):
        o = st.get(key)
        est = loc.get(est_key)
        if o and not o["stale"]:
            out[key] = {"pct": o["used_pct"], "basis": "observed", "resets_at": o["resets_at"]}
        elif o:
            pct = max(o["used_pct"], est or 0) if not o["reset_passed"] else (est if key == "session" and loc.get("block")
                                                                              and to_epoch(loc["block"]["start"]) >= to_epoch(o["resets_at"]) else 0.0)
            out[key] = {"pct": pct or 0.0, "basis": "stale-observed+estimate", "resets_at": None if o["reset_passed"] else o["resets_at"]}
        elif est is not None:
            out[key] = {"pct": est, "basis": "estimate", "resets_at": None}
        else:  # no event, no /usage reading, no estimate (e.g. probe_failed): callers run under near_cap
            out[key] = {"pct": 0.0, "basis": "none", "resets_at": None}
        if out[key]["resets_at"] is None and key == "session" and loc.get("block"):
            out[key]["resets_at"] = loc["block"]["expected_reset"]
            out[key]["resets_basis"] = "inferred from local block"
    # Fable-only weekly window: observed from the /usage probe only (rate_limit_event has no Fable window).
    # Stale readings are still used (a lower bound); no reading at all -> None (callers treat Fable conservatively).
    fo = st.get("weekly_fable")
    if fo:
        out["weekly_fable"] = {"pct": 0.0 if fo["reset_passed"] else fo["used_pct"],
                               "basis": "observed" if not fo["stale"] else ("reset passed" if fo["reset_passed"] else "stale-observed"),
                               "resets_at": None if fo["reset_passed"] else fo["resets_at"], "age_min": fo["age_min"]}
    else:
        out["weekly_fable"] = None
    out["probe_failed"] = bool(st.get("last_probe_failed"))
    # minutes since the current session window began (observed reset - 5h, else local block start)
    s = out["session"]
    ra = to_epoch(s.get("resets_at"))
    if ra and ra > now:
        out["session_elapsed_min"] = round((now - (ra - cfg["usage"]["window_hours"] * 3600)) / 60, 1)
    else:
        out["session_elapsed_min"] = 0.0  # no active window: a new one would start with the next request
    return out


def calibrate(cfg, now=None, messages=None):
    """Derive budgets from the latest fresh observation (or a limit hit = 100%) and local tokens."""
    now = now if now is not None else now_ts()
    st = state(cfg, now, messages=messages)
    loc = st["local"]
    cal = load_calibration(cfg)
    notes = []
    s = st.get("session")
    pct = s["used_pct"] if s and not s["reset_passed"] else None
    if st.get("park") and st["park"].get("active"):
        pct = 100.0
    if pct and pct >= 5 and loc.get("block"):
        cal["five_hour_weighted"] = round(loc["block"]["weighted_tokens"] / (pct / 100.0))
        notes.append("five_hour from %.0f%% vs %d local weighted tokens" % (pct, loc["block"]["weighted_tokens"]))
    w = st.get("weekly")
    if w and not w["reset_passed"] and w["used_pct"] >= 5:
        base = loc.get("weekly_server_window") or loc["weekly_rolling"]
        cal["weekly_weighted"] = round(base["weighted_tokens"] / (w["used_pct"] / 100.0))
        notes.append("weekly from %.0f%% vs %d local weighted tokens" % (w["used_pct"], base["weighted_tokens"]))
    cal["ts"] = iso(now)
    cal["notes"] = notes + ["local tokens cover this machine only; if other devices/claude.ai also used quota, these budgets come out smaller than the real cap (conservative)"]
    with open(log_path(cfg, "usage-calibration.json"), "w") as f:
        json.dump(cal, f, indent=1)
    return cal
