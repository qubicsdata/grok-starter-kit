"""File-based job queue + usage-aware scheduler. Never kills or signals anything: parking = not starting.
Policy values come from the config with the safe limits of policy.DEFAULTS behind every missing key."""
import json, os, subprocess, time, uuid
from .common import append_jsonl, iso, log_path, model_family, now_ts, read_jsonl, to_epoch
from .route import route
from . import usage as U
from . import backlog as B
from . import policy as P
import copy

STATES = ("pending", "running", "done", "failed")


class RunnerDisabled(Exception):
    """runner.enabled is not the JSON value true: nothing may start."""


def require_enabled(cfg):
    if not P.enabled(cfg):
        raise RunnerDisabled("runner.enabled is not true in router.json: the runner stays off until you enable it "
                             "(see TERMS-NOTICE.md in the runner folder)")


def qdir(cfg, state):
    d = os.path.join(cfg["paths"]["queue"], state)
    os.makedirs(d, exist_ok=True)
    return d


def enqueue(cfg, task_type, cwd, prompt_file, priority=0, critical=False, heavy=False, model=None, label=None):
    route(cfg, task_type=task_type, model_flag=model)  # validate now, fail fast
    if not os.path.isdir(cwd):
        raise ValueError("cwd does not exist: %s" % cwd)
    if not os.path.isfile(prompt_file):
        raise ValueError("prompt file does not exist: %s" % prompt_file)
    jid = time.strftime("%Y%m%d-%H%M%S", time.localtime(now_ts())) + "-" + uuid.uuid4().hex[:6]
    job = {"id": jid, "task_type": task_type, "cwd": os.path.abspath(cwd), "prompt_file": os.path.abspath(prompt_file),
           "priority": int(priority), "critical": bool(critical), "heavy": bool(heavy), "model": model,
           "label": label or ("q-" + jid), "created": iso(now_ts())}
    _write(os.path.join(qdir(cfg, "pending"), jid + ".json"), job)
    return job


def _write(path, obj):
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(obj, f, indent=1)
    os.replace(tmp, path)


def list_jobs(cfg, state):
    out = []
    d = qdir(cfg, state)
    for n in sorted(os.listdir(d)):
        if n.endswith(".json"):
            try:
                with open(os.path.join(d, n)) as f:
                    out.append(json.load(f))
            except ValueError:
                pass
    return out


def _move(cfg, job, src, dst):
    _write(os.path.join(qdir(cfg, dst), job["id"] + ".json"), job)
    try:
        os.remove(os.path.join(qdir(cfg, src), job["id"] + ".json"))
    except FileNotFoundError:
        pass


def job_family(cfg, job):
    m = route(cfg, task_type=job["task_type"], model_flag=job.get("model"))["model"] or cfg.get("default_model", "opus")
    return "opus" if m == "opusplan" else model_family(m)


# ---------------- process accounting (read-only /proc scan) ----------------

def scan_claude_procs():
    """[(pid, ppid, family_or_None)] for every `claude -p` process. Reads /proc/<pid>/cmdline and stat only."""
    out = []
    for p in os.listdir("/proc"):
        if not p.isdigit():
            continue
        try:
            with open("/proc/%s/cmdline" % p, "rb") as f:
                argv = f.read().split(b"\0")
            with open("/proc/%s/stat" % p) as f:
                ppid = int(f.read().rsplit(")", 1)[1].split()[1])
        except (OSError, ValueError, IndexError):
            continue
        argv = [a.decode(errors="replace") for a in argv if a]
        if not argv or os.path.basename(argv[0]) != "claude" or not ({"-p", "--print"} & set(argv)):
            continue
        if "/usage" in argv:  # the usage probe (local command, no model)
            continue
        fam = None
        if "--model" in argv:
            i = argv.index("--model")
            if i + 1 < len(argv):
                fam = argv[i + 1]
                fam = "opus" if fam == "opusplan" else model_family(fam)
        out.append((int(p), ppid, fam))
    return out


def _ancestors(pid, parent_of):
    seen = set()
    while pid and pid not in seen:
        seen.add(pid)
        pid = parent_of.get(pid)
    return seen


def _ppid(pid):
    try:
        with open("/proc/%d/stat" % pid) as f:
            return int(f.read().rsplit(")", 1)[1].split()[1])
    except (OSError, ValueError, IndexError):
        return None


def running_counts(cfg, running_jobs, procs):
    """Total/opus counts = the runner's running jobs + every other claude -p process not descended from them."""
    ours = {j.get("pid") for j in running_jobs if j.get("pid")}
    total, opus = 0, 0
    for j in running_jobs:
        total += 1
        opus += job_family(cfg, j) == "opus"
    ext = []
    if cfg["policy"].get("count_external_claude", True):
        for pid, ppid, fam in procs:
            chain, cur = set(), ppid
            for _ in range(8):
                if cur is None or cur in chain:
                    break
                chain.add(cur)
                cur = _ppid(cur) if cur not in ours else None
            if chain & ours:
                continue
            f = fam or cfg["policy"].get("external_default_family", "opus")
            ext.append({"pid": pid, "family": f})
            total += 1
            opus += f == "opus"
    return {"total": total, "opus": opus, "external": ext}


# ---------------- policy (pure) ----------------

def decide(cfg, eff, park, pending, counts, now, accept=None):
    """Return (to_start, info). Pure function of its inputs; used by tick() and by the tests.
    accept(job) -> None to take the job (and record it) or a reason to hold it; called only after the global caps pass."""
    pol = P.section(cfg, "policy")
    s, w = eff["session"]["pct"], eff["weekly"]["pct"]
    elapsed = eff.get("session_elapsed_min", 0.0)
    cap, opus_cap = pol["total_cap"], pol["opus_cap"]
    allow_crit, allow_noncrit = True, True
    reasons, resume_at = [], None
    if park and park.get("active"):
        info = {"mode": "parked", "reasons": ["rate-limit park: %s" % park.get("source")],
                "resume_at": park.get("resume_at"), "cap": 0}
        return [], info
    ws, ss = pol["weekly"], pol["session"]
    if w >= ws["stop_new_pct"]:
        allow_crit = allow_noncrit = False
        reasons.append("weekly %.0f%% >= %s%%: start nothing" % (w, ws["stop_new_pct"]))
        resume_at = eff["weekly"].get("resets_at")
    elif w >= ws["critical_only_pct"]:
        allow_noncrit = False
        cap = min(cap, ws["critical_only_cap"])
        reasons.append("weekly %.0f%% >= %s%%: critical-path only, cap %d" % (w, ws["critical_only_pct"], cap))
    elif w >= ws["restricted_pct"]:
        cap = min(cap, ws["restricted_cap"])
        if elapsed > ws["restricted_noncritical_after_reset_minutes"]:
            allow_noncrit = False
            reasons.append("weekly %.0f%% >= %s%%: cap %d, non-critical only in the first %s min after a reset"
                           % (w, ws["restricted_pct"], cap, ws["restricted_noncritical_after_reset_minutes"]))
            resume_at = resume_at or eff["session"].get("resets_at")
        else:
            reasons.append("weekly %.0f%% >= %s%%: cap %d (just after reset, non-critical allowed)" % (w, ws["restricted_pct"], cap))
    if s >= ss["stop_new_pct"]:
        allow_crit = allow_noncrit = False
        reasons.append("session %.0f%% >= %s%%: start nothing, running jobs finish" % (s, ss["stop_new_pct"]))
        resume_at = eff["session"].get("resets_at")
    elif s >= ss["pause_noncritical_pct"]:
        allow_noncrit = False
        reasons.append("session %.0f%% >= %s%%: non-critical paused" % (s, ss["pause_noncritical_pct"]))
        resume_at = resume_at or eff["session"].get("resets_at")
    mode = "normal" if not reasons else ("stopped" if not (allow_crit or allow_noncrit) else "restricted")

    window_min = cfg["usage"]["window_hours"] * 60
    early = elapsed <= window_min * pol.get("early_block_fraction", 0.4)

    def key(j):
        fam = job_family(cfg, j)
        heavy_rank = 0 if (fam == "opus") == early else 1  # early: Opus first; late: lighter first
        return (0 if j.get("critical") else 1, -j.get("priority", 0), heavy_rank, j.get("created", ""))

    total, opus = counts["total"], counts["opus"]
    start, held = [], []
    for j in sorted(pending, key=key):
        crit = bool(j.get("critical"))
        why = None
        if crit and not allow_crit or (not crit and not allow_noncrit):
            why = "policy"
        elif j.get("heavy") and elapsed > pol["heavy_after_reset_minutes"] and not crit:
            why = "heavy: waits for the first %s min after a reset" % pol["heavy_after_reset_minutes"]
        elif total >= cap:
            why = "total cap %d" % cap
        elif job_family(cfg, j) == "opus" and opus >= opus_cap:
            why = "opus cap %d" % opus_cap
        elif accept is not None:
            why = accept(j)
        if why:
            held.append({"id": j["id"], "why": why})
            continue
        start.append(j)
        total += 1
        opus += job_family(cfg, j) == "opus"
    return start, {"mode": mode, "reasons": reasons, "resume_at": resume_at, "cap": cap,
                   "session_pct": s, "weekly_pct": w, "session_basis": eff["session"]["basis"],
                   "weekly_basis": eff["weekly"]["basis"], "elapsed_min": elapsed, "held": held,
                   "running": {"total": counts["total"], "opus": counts["opus"]}}


# ---------------- weekly pacing (pure) ----------------

def pacing_line(p, resets_at, now, weekly_days=7):
    """Target weekly % at `now`: linear from the week start (reset - 7 d) to target_pct at
    reset - target_hours_before_reset, then linear to final_pct at the reset. None if the reset is unknown."""
    ra = to_epoch(resets_at) if resets_at else None
    if not ra:
        return None
    ws = ra - weekly_days * 86400
    t_at = ra - p.get("target_hours_before_reset", P.default("backlog", "weekly_pacing", "fable", "target_hours_before_reset")) * 3600
    tgt = float(p["target_pct"])
    fin = float(p.get("final_pct", tgt))
    if now <= ws:
        return 0.0
    if now <= t_at:
        return tgt * (now - ws) / max(1.0, t_at - ws)
    return tgt + (fin - tgt) * min(1.0, (now - t_at) / max(1.0, ra - t_at))


def pacing_cap(p, pct, resets_at, now, full_cap, weekly_days=7):
    """(cap, info) for one weekly window. Ahead of the line by >= slack_pct, or at/over park_pct: 0 (start nothing new,
    running jobs finish). Ahead by < slack_pct: near_cap. Behind the line: full_cap. Unknown reading/reset: near_cap."""
    near = min(full_cap, p.get("near_cap", P.default("backlog", "weekly_pacing", "fable", "near_cap")))  # the lower one
    if not p or not p.get("enabled", P.default("backlog", "weekly_pacing", "all_models", "enabled")):
        return full_cap, {"mode": "off", "cap": full_cap}
    if pct is None:
        return near, {"mode": "no reading", "cap": near}
    if p.get("park_pct") is not None and pct >= p["park_pct"]:
        return 0, {"mode": "parked", "pct": pct, "park_pct": p["park_pct"], "cap": 0}
    line = pacing_line(p, resets_at, now, weekly_days)
    if line is None:
        return near, {"mode": "reset unknown", "pct": pct, "cap": near}
    over = pct - line
    slack = p.get("slack_pct", P.default("backlog", "weekly_pacing", "all_models", "slack_pct"))
    if over >= slack:
        cap, mode = 0, "ahead"
    elif over >= 0:
        cap, mode = near, "near"
    else:
        cap, mode = full_cap, "behind"
    return cap, {"mode": mode, "pct": pct, "line": round(line, 1), "over": round(over, 1), "cap": cap}


# ---------------- Fable reading age rule ----------------

def fable_age_cap(cfg, eff, full_cap):
    """(cap, mode, age_min) from the age of the Fable-only weekly reading (only `claude -p /usage` carries it).
    <= fresh_minutes (30): full caps. Older than stale_near_cap_minutes (45): near_cap (1). Older than
    stale_block_minutes (90), latest probe failed, no reading or unknown age: 0 (no new Fable starts).
    30-45 min: full caps (the rule names no band for 30-45)."""
    fp = P.section(cfg, "backlog", "weekly_pacing", "fable")
    near = min(full_cap, fp["near_cap"])
    if eff.get("probe_failed"):
        return 0, "probe failed", None
    fe = eff.get("weekly_fable")
    if not fe:
        return 0, "no reading", None
    age = fe.get("age_min")
    if age is None:
        return 0, "age unknown", None
    if age > fp["stale_block_minutes"]:
        return 0, "older than %s min" % fp["stale_block_minutes"], age
    if age > fp["stale_near_cap_minutes"]:
        return near, "older than %s min" % fp["stale_near_cap_minutes"], age
    return full_cap, "fresh" if age <= fp["fresh_minutes"] else "30-45 min (normal caps)", age


def _fable_reprobe(cfg, prober, now, dry_run):
    """Near-park zone (Fable >= near_park_pct, 75): fresh `claude -p /usage` before a Fable launch, spaced by
    usage.near_park_min_probe_spacing_minutes (5, never less). Returns (ok, info)."""
    fp = P.section(cfg, "backlog", "weekly_pacing", "fable")
    sp = P.near_park_spacing_minutes(cfg)
    probed = False
    if U.probe_due(cfg, now, spacing_minutes=sp):
        if dry_run:
            return True, {"would_reprobe": True}
        U.poll(cfg, now=now, prober=prober)
        probed = True
    e = U.effective(cfg, U.state(cfg, now, include_local=False), now)
    fe = e.get("weekly_fable") or {}
    info = {"probed": probed, "fable_pct": fe.get("pct"), "age_min": fe.get("age_min")}
    if probed and e.get("probe_failed"):
        return False, dict(info, why="re-probe: probe failed")
    cap, mode, _ = fable_age_cap(cfg, e, 1)
    if cap == 0:
        return False, dict(info, why="re-probe: Fable reading %s" % mode)
    if fe.get("pct") is not None and fe["pct"] >= fp["park_pct"]:
        return False, dict(info, why="re-probe: Fable %.0f%% >= park %s%%" % (fe["pct"], fp["park_pct"]))
    return True, info


# ---------------- tick / loop ----------------

def _last_probe_ts(cfg):
    return U.last_probe_ts(cfg)


# ---------------- quiet hours ----------------

def in_quiet_hours(cfg, now):
    """True inside backlog.quiet_hours (default 01:00-07:00 in backlog.quiet_hours.tz, every day; end exclusive;
    on by default). The template sets tz to ${KIT_TZ}; a missing or empty tz means UTC."""
    q = P.section(cfg, "backlog", "quiet_hours")
    if not q.get("enabled"):
        return False
    from datetime import datetime
    from zoneinfo import ZoneInfo
    t = datetime.fromtimestamp(now, tz=ZoneInfo(q.get("tz") or P.default("backlog", "quiet_hours", "tz")))
    hm = lambda x: int(x.split(":")[0]) * 60 + int(x.split(":")[1])
    m, a, b = t.hour * 60 + t.minute, hm(q["start"]), hm(q["end"])
    return a <= m < b if a <= b else (m >= a or m < b)


def reap(cfg, procs_alive=None):
    """Move finished running jobs to done/failed using runs.jsonl finish records (by run_id)."""
    finishes = {r.get("run_id"): r for r in read_jsonl(log_path(cfg, "runs.jsonl")) if r.get("event") == "finish"}
    alive = procs_alive or (lambda pid: os.path.exists("/proc/%d" % pid) and not _is_zombie(pid))
    moved = []
    for j in list_jobs(cfg, "running"):
        fin = finishes.get(j["id"])
        if fin is None and j.get("pid") and alive(j["pid"]):
            continue
        j["finished"] = iso(now_ts())
        j["finish"] = fin
        ok = fin is not None and fin.get("rc") == 0 and not fin.get("is_error") and not fin.get("limit_hit")
        _move(cfg, j, "running", "done" if ok else "failed")
        moved.append((j["id"], "done" if ok else "failed"))
    return moved


def _is_zombie(pid):
    try:
        with open("/proc/%d/stat" % pid) as f:
            return f.read().rsplit(")", 1)[1].split()[0] == "Z"
    except (OSError, IndexError):
        return False


_CHILDREN = {}


def launch(cfg, job):
    """Start one job process (run-claude.sh). Refuses while runner.enabled is not true, whatever called it."""
    if os.environ.get("CR_TEST_NO_REAL_CLAUDE") == "1" and not os.environ.get("CLAUDE_BIN"):
        raise RuntimeError("launch refused under CR_TEST_NO_REAL_CLAUDE without a fake CLAUDE_BIN")
    require_enabled(cfg)
    runner = cfg["paths"]["runner"]
    out_dir = os.path.join(cfg["paths"]["logs"], "sched")
    os.makedirs(out_dir, exist_ok=True)
    argv = [runner, "--task-type", job["task_type"], "--run-id", job["id"]]
    if job.get("model"):
        argv += ["--model", job["model"]]
    if job.get("effort"):
        argv += ["--effort", job["effort"]]
    if job.get("experiment"):
        argv += ["--experiment", job["experiment"]]
    argv += [job["label"], job["cwd"]]
    env = dict(os.environ)
    env["PROMPT_FILE"] = job["prompt_file"]
    with open(os.path.join(out_dir, job["id"] + ".out"), "w") as out:
        p = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=out, stderr=subprocess.STDOUT,
                             env=env, cwd=job["cwd"], start_new_session=True)
    _CHILDREN[p.pid] = p
    return p.pid


def tick(cfg, probe=True, dry_run=False, prober=None, procs=None, launcher=None, messages=None):
    now = now_ts()
    for p in list(_CHILDREN.values()):  # reap our own children so they do not linger as zombies
        if p.poll() is not None:
            _CHILDREN.pop(p.pid, None)
    reaped = [] if dry_run else reap(cfg)
    st = U.state(cfg, now, messages=messages)
    eff = U.effective(cfg, st, now)
    pending = list_jobs(cfg, "pending")
    stale = eff["session"]["basis"] != "observed" or eff["weekly"]["basis"] != "observed"
    probed = None
    if probe and pending and stale and U.probe_due(cfg, now):  # at most every min_probe_spacing_minutes (30)
        probed = U.poll(cfg, prober=prober)
        st = U.state(cfg, now, messages=messages)
        eff = U.effective(cfg, st, now)
    running = list_jobs(cfg, "running")
    bl_state = B.load_state(cfg) if cfg.get("backlog", {}).get("enabled") else {}
    bl_running = [{"id": v["run_id"], "task_type": v["task_type"], "model": v.get("model"), "pid": v.get("pid")}
                  for v in bl_state.values() if v.get("status") == "running"]
    procs = procs if procs is not None else scan_claude_procs()
    counts = running_counts(cfg, running + bl_running, procs)
    start, info = decide(cfg, eff, st.get("park"), pending, counts, now)
    info.update({"ts": iso(now), "event": "tick", "pending": len(pending), "reaped": reaped,
                 "probed": bool(probed), "park": st.get("park")})
    started = []
    if not dry_run:
        for j in start:
            j["pid"] = (launcher or launch)(cfg, j)
            j["started"] = iso(now_ts())
            j["route"] = route(cfg, task_type=j["task_type"], model_flag=j.get("model"))
            _move(cfg, j, "pending", "running")
            started.append(j["id"])
    info["started"] = started if not dry_run else [j["id"] for j in start]
    if cfg.get("backlog", {}).get("enabled"):
        c2 = {"total": counts["total"] + len(start), "opus": counts["opus"] + sum(job_family(cfg, j) == "opus" for j in start),
              "external": counts["external"]}
        info["backlog"] = backlog_tick(cfg, eff, st, c2, len(pending) - len(start), now, dry_run, launcher, procs_alive=None,
                                       gate=None if dry_run else (lambda: usage_gate(cfg, messages=messages)),
                                       prober=prober)
    if not dry_run:
        _log_tick(cfg, info)
    return info


def usage_gate(cfg, messages=None, now=None):
    """Fresh usage read right before one launch (usage.jsonl: /usage probes + rate_limit_events, incl. live streams).
    Returns (ok, why). Same thresholds as backlog_tick/decide: session max, weekly stop/critical-only, park."""
    now = now or now_ts()
    st = U.state(cfg, now, include_local=False, messages=messages)
    e = U.effective(cfg, st, now)
    b, ws = P.section(cfg, "backlog"), P.section(cfg, "policy", "weekly")
    if st.get("park") and st["park"].get("active"):
        return False, "rate-limit park"
    if e["session"]["pct"] >= b["session_max_pct"]:
        return False, "session %.0f%% >= %s%%" % (e["session"]["pct"], b["session_max_pct"])
    if e["weekly"]["pct"] >= min(b["weekly_max_pct"], ws["critical_only_pct"]):
        return False, "weekly %.0f%% >= %s%%" % (e["weekly"]["pct"], min(b["weekly_max_pct"], ws["critical_only_pct"]))
    return True, "session %.0f%%, weekly %.0f%%" % (e["session"]["pct"], e["weekly"]["pct"])


def _reap_backlog(cfg, doc, state, now, procs_alive=None, dry_run=False):
    """running -> done | failed | retry. Crash (pid gone, no finish record) is retried while attempts < max_attempts;
    limit hits and errors are not. Done jobs with `commit:` get a local commit in their worktree (never pushed)."""
    b = cfg["backlog"]
    finishes = {r.get("run_id"): r for r in read_jsonl(log_path(cfg, "runs.jsonl")) if r.get("event") == "finish"}
    alive = procs_alive or (lambda pid: os.path.exists("/proc/%d" % pid) and not _is_zombie(pid))
    jobs = {j.get("id"): j for j in doc.get("jobs", [])}
    changed = []
    for jid, v in state.items():
        if v.get("status") != "running":
            continue
        fin = finishes.get(v.get("run_id"))
        if fin is None and v.get("pid") and alive(v["pid"]):
            continue
        ok = fin is not None and fin.get("rc") == 0 and not fin.get("is_error") and not fin.get("limit_hit")
        v.update({"finished": iso(now), "rc": (fin or {}).get("rc")})
        if ok:
            v["status"] = "done"
            j = jobs.get(jid, {})
            if j.get("commit") and j.get("commit") not in ("no", "false") and not dry_run:
                wt = B._dir_of(j.get("worktree"))
                if wt:
                    ident, why = B.commit_identity(cfg, wt)
                    if ident is None:  # no identity: the job stays done, the commit is skipped and logged
                        v["commit"] = None
                        append_jsonl(log_path(cfg, "scheduler.jsonl"), {"ts": iso(now), "event": "commit_skipped",
                                                                        "job": jid, "reason": why})
                    else:
                        v["commit"] = B.commit_local(wt, "backlog %s: %s\n\nLocal backlog job (run %s). Not pushed." % (
                            jid, j.get("title") or jid, v.get("run_id")), identity=ident)
        elif fin is None and v.get("attempts", 1) < b.get("max_attempts", 1):
            v.update({"status": "retry", "why": "crashed (no finish record), will retry"})
        else:
            v["status"] = "failed"
            v["why"] = ("limit hit" if fin.get("limit_hit") else "rc %s%s" % (fin.get("rc"), ", is_error" if fin.get("is_error") else "")) \
                if fin else "crashed (no finish record), attempts exhausted"
        changed.append((jid, v["status"]))
    return changed


def backlog_tick(cfg, eff, st, counts, queue_waiting, now, dry_run=False, launcher=None, procs_alive=None, gate=None,
                 stack_runner=None, prober=None):
    b = P.section(cfg, "backlog")
    pol = P.section(cfg, "policy")
    if not os.path.isfile(b["queue"]):
        return {"enabled": True, "held": "queue file missing"}
    with open(b["queue"]) as f:
        doc = B.parse_queue_yaml(f.read())
    state = B.load_state(cfg)
    reaped = _reap_backlog(cfg, doc, state, now, procs_alive, dry_run)
    if reaped and not dry_run:
        B.save_state(cfg, state)
    running_n = sum(1 for v in state.values() if v.get("status") == "running")
    out = {"enabled": True, "running": running_n, "reaped": reaped}
    hold = []
    if not B.guard_preamble(cfg):
        hold.append("backlog.guard_preamble is empty: no backlog job starts without a guard preamble")
    if queue_waiting > 0:
        hold.append("%d main-queue job(s) waiting: the main queue goes first" % queue_waiting)
    if st.get("park") and st["park"].get("active"):
        hold.append("rate-limit park")
    if eff["session"]["pct"] >= b["session_max_pct"]:
        hold.append("session %.0f%% >= %s%%" % (eff["session"]["pct"], b["session_max_pct"]))
    if eff["weekly"]["pct"] >= b["weekly_max_pct"]:
        hold.append("weekly %.0f%% >= %s%%" % (eff["weekly"]["pct"], b["weekly_max_pct"]))
    burn, basis = B.weekly_burn_pct_per_h(cfg, now, st.get("local"))
    ok, why, proj = B.soak_window(cfg, eff, now, burn)
    out.update({"soak": ok, "soak_reason": why, "burn_pct_per_h": burn, "burn_basis": basis, "projected_at_reset": proj})
    if b.get("require_soak_window", True) and not ok:
        hold.append("soak window closed: " + why)
    if running_n >= b["max_concurrent"]:
        hold.append("backlog max_concurrent %d" % b["max_concurrent"])
    if in_quiet_hours(cfg, now):
        q = b["quiet_hours"]
        hold.append("quiet hours %s-%s %s: no new backlog starts (running jobs finish)"
                    % (q.get("start"), q.get("end"), q.get("tz") or P.default("backlog", "quiet_hours", "tz")))
    cands, skipped = B.eligible(cfg, doc, state)
    out["skipped"] = skipped
    out["eligible"] = [j["id"] for j in cands]
    if hold:
        out["held"] = hold
        return out
    pseudo = [{"id": j["id"], "task_type": j.get("task_type"), "model": None if j.get("model") in (None, "none") else j.get("model"),
               "critical": False, "priority": len(cands) - i, "heavy": False, "created": "%03d" % i, "_job": j}
              for i, j in enumerate(cands)]
    from .route import normalize_task_type
    for p in pseudo:
        p["task_type"] = normalize_task_type(cfg, p["task_type"])
        if p["task_type"] not in cfg["routes"]:
            p["task_type"] = "default"
    # Caps: decide() applies total_cap/opus_cap to ALL sessions (own + any other claude -p on the machine). The
    # reserve limits the runner's OWN backlog sessions: own <= total_cap - reserve_slots (and <= max_concurrent),
    # own Opus <= opus_cap - reserve_opus, so one slot (and one Opus) always stays free for your other work.
    # group_limits cap running+new jobs per `group:`. All checked inside decide() (accept), so a job held for one
    # cap never uses up another cap's budget.
    own_cap = min(b["max_concurrent"], pol["total_cap"] - b["reserve_slots"])
    own_opus_cap = pol["opus_cap"] - b["reserve_opus"]
    # Weekly pacing: the all-models line caps every backlog job; the Fable-only line caps Fable jobs.
    pac = b["weekly_pacing"]
    wd = cfg["usage"].get("weekly_days", 7)
    # No usage at all (probe failed, no rate_limit_event, no estimate): run under near_cap
    no_reading = "none" in (eff["weekly"].get("basis"), eff["session"].get("basis"))
    pace_all, pinfo_all = pacing_cap(pac["all_models"], None if no_reading else eff["weekly"]["pct"],
                                     eff["weekly"].get("resets_at"), now, own_cap, wd)
    own_cap = min(own_cap, pace_all)
    fe = eff.get("weekly_fable") or {}
    fable_full = b["fable"]["max_concurrent"]
    fable_cap, pinfo_f = pacing_cap(pac["fable"], fe.get("pct"),
                                    fe.get("resets_at") or eff["weekly"].get("resets_at"), now, fable_full, wd)
    age_cap, age_mode, age_min = fable_age_cap(cfg, eff, fable_full)
    fable_cap = min(fable_cap, age_cap)
    out["pacing"] = {"all_models": pinfo_all, "fable": dict(pinfo_f, basis=fe.get("basis"), age_min=age_min,
                                                            age_rule=age_mode, cap=fable_cap)}
    glim = b.get("group_limits") or {}
    run_v = [v for v in state.values() if v.get("status") == "running"]
    acc = {"own": running_n,
           "opus": sum(1 for v in run_v if job_family(cfg, {"task_type": v.get("task_type") or "default", "model": v.get("model")}) == "opus"),
           "fable": sum(1 for v in run_v if job_family(cfg, {"task_type": v.get("task_type") or "default", "model": v.get("model")}) == "fable"),
           "groups": {}}
    for v in run_v:
        if v.get("group"):
            acc["groups"][v["group"]] = acc["groups"].get(v["group"], 0) + 1

    def accept(p):
        fam = job_family(cfg, p)
        is_opus, is_fable = fam == "opus", fam == "fable"
        g = p["_job"].get("group")
        if acc["own"] >= own_cap:
            return "own cap %d (%s)" % (own_cap, "weekly pacing %s" % pinfo_all["mode"] if pace_all < min(
                b["max_concurrent"], pol["total_cap"] - b["reserve_slots"]) else "slot reserve")
        if is_opus and acc["opus"] >= own_opus_cap:
            return "own opus cap %d (Opus reserve)" % own_opus_cap
        if is_fable and acc["fable"] >= fable_cap:
            return "fable cap %d (Fable pacing %s; Fable reading %s)" % (fable_cap, pinfo_f["mode"], age_mode)
        if g in glim and acc["groups"].get(g, 0) >= glim[g]:
            return "group %s at limit %d" % (g, glim[g])
        acc["own"] += 1
        acc["opus"] += is_opus
        acc["fable"] += is_fable
        if g:
            acc["groups"][g] = acc["groups"].get(g, 0) + 1
        return None
    start, dinfo = decide(cfg, eff, None, pseudo, counts, now, accept=accept)
    out["decide"] = {"mode": dinfo["mode"], "reasons": dinfo["reasons"], "held": dinfo["held"]}
    started = []
    for p in start:
        j = p["_job"]
        if job_family(cfg, p) == "fable" and (fe.get("pct") or 0) >= pac["fable"]["near_park_pct"]:
            fok, finfo = _fable_reprobe(cfg, prober, now, dry_run)  # tick time; spacing still holds between launches
            out.setdefault("fable_reprobe", []).append(dict(finfo, id=j["id"]))
            if not fok:
                continue
        if not dry_run and in_quiet_hours(cfg, now_ts()):
            out["gate_stop"] = "quiet hours began"
            break
        if gate is not None and not dry_run:
            gok, gwhy = gate()
            if not gok:
                out["gate_stop"] = gwhy
                break
        run_id = "bl-%s-%s" % (j["id"], time.strftime("%Y%m%d-%H%M%S", time.localtime(now_ts())))
        if dry_run:
            started.append(j["id"])
            continue
        if j.get("stack_on"):
            sok, smsg = B.stack_ff(B._dir_of(j.get("worktree")), j["stack_on"], runner=stack_runner)
            if not sok:
                state[j["id"]] = {"status": "failed", "why": "stack_on: " + smsg, "finished": iso(now_ts()),
                                  "attempts": state.get(j["id"], {}).get("attempts", 0), "group": j.get("group")}
                B.save_state(cfg, state)
                out.setdefault("stack_failed", []).append(j["id"])
                continue
            out.setdefault("stacked", {})[j["id"]] = smsg[:12]
        spec = {"id": run_id, "task_type": p["task_type"], "model": p["model"], "effort": j.get("effort"),
                "experiment": j.get("experiment"),
                "label": "bl-" + j["id"], "cwd": B._dir_of(j.get("worktree")), "prompt_file": B.build_prompt(cfg, j)}
        attempts = state.get(j["id"], {}).get("attempts", 0) + 1
        pid = (launcher or launch)(cfg, spec)
        state[j["id"]] = {"status": "running", "run_id": run_id, "pid": pid, "started": iso(now_ts()), "attempts": attempts,
                          "task_type": p["task_type"], "model": p["model"], "effort": j.get("effort"), "group": j.get("group")}
        B.save_state(cfg, state)
        started.append(j["id"])
    out["started"] = started
    return out


_LAST = {}


def _log_tick(cfg, info):
    sig = {k: info.get(k) for k in ("mode", "reasons", "resume_at", "started", "reaped", "pending")}
    bl = info.get("backlog") or {}
    sig["backlog"] = {k: bl.get(k) for k in ("started", "reaped", "held", "gate_stop", "stack_failed")}
    sig["pacing"] = {k: (v or {}).get("mode") for k, v in (bl.get("pacing") or {}).items()}  # backlog launches/finishes too
    sig = json.dumps(sig, sort_keys=True, default=str)
    if _LAST.get("sig") == sig:
        return
    _LAST["sig"] = sig
    append_jsonl(log_path(cfg, "scheduler.jsonl"), info)


class AlreadyRunning(Exception):
    pass


def _pid_alive(pid):
    return os.path.exists("/proc/%d" % pid) and not _is_zombie(pid)


def read_pidfile(path):
    try:
        with open(path) as f:
            return int(f.read().split()[0])
    except (OSError, ValueError, IndexError):
        return None


def _is_runner(pid):
    try:
        with open("/proc/%d/cmdline" % pid, "rb") as f:
            a = f.read().split(b"\0")
    except OSError:
        return False
    return b"sched" in a and b"loop" in a


def loop(cfg, interval=60, probe=True, max_ticks=None, pidfile=None, stop_file=None, ticker=None):
    """Detached queue runner. Single instance via pidfile; exits after the current tick on SIGTERM/SIGINT or when
    stop_file exists. Never signals jobs: they run in their own sessions (launch: start_new_session) and are
    reaped by the next runner from runs.jsonl + the state file. Refuses (RunnerDisabled) before the pidfile, the
    log and any probe unless runner.enabled is true."""
    import signal
    require_enabled(cfg)
    if pidfile:
        old = read_pidfile(pidfile)
        if old and old != os.getpid() and _pid_alive(old) and _is_runner(old):
            raise AlreadyRunning("queue runner already running (pid %d, %s)" % (old, pidfile))
        _write_text(pidfile, "%d\n" % os.getpid())
    if stop_file and os.path.exists(stop_file):
        os.remove(stop_file)  # a fresh start clears an old stop request
    flag = {"stop": None}

    def on_sig(signum, _frame):
        flag["stop"] = "signal %d" % signum
    old_h = {sg: signal.signal(sg, on_sig) for sg in (signal.SIGTERM, signal.SIGINT)}
    append_jsonl(log_path(cfg, "scheduler.jsonl"), {"ts": iso(now_ts()), "event": "runner_start", "pid": os.getpid(),
                                                    "interval_s": interval, "probe": probe})
    n = 0
    try:
        while (max_ticks is None or n < max_ticks) and not flag["stop"]:
            if stop_file and os.path.exists(stop_file):
                flag["stop"] = "stop file"
                break
            try:
                if ticker:
                    ticker()
                else:
                    if probe and now_ts() - _last_probe_ts(cfg) > P.loop_probe_spacing_minutes(cfg) * 60:
                        U.poll(cfg)  # claude -p /usage from the scheduler only, at most every 30 min (Fable % + backup)
                    tick(cfg, probe=probe)
            except Exception as e:  # keep the loop alive; never touch running jobs
                append_jsonl(log_path(cfg, "scheduler.jsonl"), {"ts": iso(now_ts()), "event": "error", "error": repr(e)})
            n += 1
            end = time.time() + interval
            while time.time() < end and not flag["stop"]:
                if stop_file and os.path.exists(stop_file):
                    flag["stop"] = "stop file"
                    break
                time.sleep(min(0.2, max(0.0, end - time.time())))
    finally:
        for sg, h in old_h.items():
            signal.signal(sg, h)
        append_jsonl(log_path(cfg, "scheduler.jsonl"), {"ts": iso(now_ts()), "event": "runner_stop", "pid": os.getpid(),
                                                        "reason": flag["stop"] or "max_ticks", "ticks": n,
                                                        "note": "in-flight claude runs left running"})
        if pidfile and read_pidfile(pidfile) == os.getpid():
            os.remove(pidfile)
    return flag["stop"]


def stop(pidfile, stop_file, wait_s=30):
    """Ask the runner to exit: write the stop file, SIGTERM the pid in pidfile (only if it is a `cr sched loop`).
    In-flight claude runs are not signalled. Returns (stopped, message)."""
    import signal
    if stop_file:
        _write_text(stop_file, iso(now_ts()) + "\n")
    pid = read_pidfile(pidfile)
    if not pid or not _pid_alive(pid):
        return True, "not running"
    if not _is_runner(pid):
        return False, "pid %d in %s is not a queue runner; not signalled" % (pid, pidfile)
    os.kill(pid, signal.SIGTERM)
    end = time.time() + wait_s
    while time.time() < end:
        if not _pid_alive(pid):
            return True, "stopped pid %d (in-flight runs keep running)" % pid
        time.sleep(0.2)
    return False, "pid %d still running after %ss" % (pid, wait_s)


def _write_text(path, text):
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        f.write(text)
    os.replace(tmp, path)
