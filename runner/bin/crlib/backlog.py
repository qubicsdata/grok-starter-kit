"""Backlog soak: dispatch queued jobs from backlog/queue.yaml into idle slots. queue.yaml is read-only here;
status lives in a separate state file. Backlog jobs never push, open PRs or comment (guard preamble + runner deny list)."""
import json, os, re, time
from .common import append_jsonl, iso, log_path, now_ts, read_jsonl, to_epoch


# ---- minimal YAML subset reader (stdlib only): top-level scalars + `jobs:` list of flat mappings ----
def _strip_comment(v):
    out, q = [], None
    for i, ch in enumerate(v):
        if q:
            if ch == q:
                q = None
        elif ch in "\"'":
            q = ch
        elif ch == "#" and (i == 0 or v[i - 1] in " \t"):
            break
        out.append(ch)
    return "".join(out).strip()


def _scalar(v):
    v = _strip_comment(v)
    if not v:
        return None
    if v[0] in "\"'" and v[-1] == v[0] and len(v) >= 2:
        return v[1:-1]
    if v.startswith("[") and v.endswith("]"):
        return [_scalar(x) for x in v[1:-1].split(",") if x.strip()]
    if re.fullmatch(r"-?\d+", v):
        return int(v)
    if re.fullmatch(r"-?\d+\.\d+", v):
        return float(v)
    return v


def parse_queue_yaml(text):
    doc, jobs, cur, in_jobs = {}, [], None, False
    for raw in text.splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip())
        line = raw.strip()
        if indent == 0:
            in_jobs = line.startswith("jobs:")
            cur = None
            if not in_jobs and ":" in line:
                k, v = line.split(":", 1)
                doc[k.strip()] = _scalar(v)
            continue
        if not in_jobs:
            continue
        if line.startswith("- "):
            cur = {}
            jobs.append(cur)
            line = line[2:]
        if cur is not None and ":" in line:
            k, v = line.split(":", 1)
            cur[k.strip()] = _scalar(v)
    doc["jobs"] = jobs
    return doc


def load_state(cfg):
    try:
        with open(cfg["backlog"]["state_file"]) as f:
            return json.load(f)
    except (FileNotFoundError, ValueError):
        return {}


def save_state(cfg, st):
    p = cfg["backlog"]["state_file"]
    tmp = p + ".tmp"
    with open(tmp, "w") as f:
        json.dump(st, f, indent=1, sort_keys=True)
    os.replace(tmp, p)


def weekly_burn_pct_per_h(cfg, now, st_local=None):
    """Weekly %/h from observed readings in the lookback window (OBSERVED); else local weighted tokens in the
    lookback / weekly budget (ESTIMATE). Returns (rate_or_None, basis)."""
    lbh = cfg["backlog"]["burn_lookback_hours"]
    obs = [(to_epoch(r["ts"]), r["weekly_all_models"]["used_pct"]) for r in read_jsonl(log_path(cfg, "usage.jsonl"))
           if isinstance(r.get("weekly_all_models"), dict) and r["weekly_all_models"].get("used_pct") is not None
           and to_epoch(r.get("ts")) and now - lbh * 3600 <= to_epoch(r["ts"]) <= now]
    obs.sort()
    if len(obs) >= 2 and obs[-1][0] - obs[0][0] >= 1800 and obs[-1][1] >= obs[0][1]:
        return (obs[-1][1] - obs[0][1]) / ((obs[-1][0] - obs[0][0]) / 3600.0), "observed readings"
    if st_local and st_local.get("weighted_lookback") is not None and st_local.get("budget_weekly_weighted"):
        return 100.0 * st_local["weighted_lookback"] / st_local["budget_weekly_weighted"] / lbh, "local tokens / weekly budget (estimate)"
    return None, "no data"


def soak_window(cfg, eff, now, burn):
    b = cfg["backlog"]
    ra = to_epoch(eff["weekly"].get("resets_at"))
    if not ra:
        return False, "weekly reset unknown", None
    hours = (ra - now) / 3600.0
    if hours > b["soak_reset_within_hours"]:
        return False, "weekly reset %.1f h away (> %s h)" % (hours, b["soak_reset_within_hours"]), None
    rate = burn if burn is not None else 0.0
    proj = eff["weekly"]["pct"] + rate * max(0.0, hours)
    if proj >= b["soak_projected_max_pct"]:
        return False, "projected weekly at reset %.1f%% >= %s%%" % (proj, b["soak_projected_max_pct"]), proj
    return True, "reset in %.1f h, projected %.1f%%" % (hours, proj), proj


def _dir_of(worktree):
    if not isinstance(worktree, str):
        return None
    tok = worktree.split()[0] if worktree.split() else ""
    return tok if tok.startswith("/") and os.path.isdir(tok) else None


def eligible(cfg, doc, state):
    """(eligible_jobs, skipped[{id, why}]) in priority order. Only P-levels listed in config; channel direct only."""
    b = cfg["backlog"]
    order = {p: i for i, p in enumerate(b["priorities"])}
    out, skipped = [], []
    done = {k for k, v in state.items() if v.get("status") == "done"}
    for j in doc.get("jobs", []):
        jid = j.get("id")
        why = None
        s = state.get(jid, {}).get("status")
        if j.get("status") != "queued":
            why = "status %s in queue.yaml" % j.get("status")
        elif s in ("running", "done", "failed"):  # "retry" (crashed, attempts left) stays eligible
            why = "state %s" % s
        elif j.get("priority") not in order:
            why = "priority %s not auto-dispatched" % j.get("priority")
        elif j.get("channel") != "direct":
            why = "channel %s (no Claude; run outside the runner)" % j.get("channel")
        elif j.get("model") == "none":  # no model key = the router picks it from task_type
            why = "no model"
        elif any(d not in done for d in (j.get("depends_on") or [])):
            why = "depends_on not done: %s" % [d for d in j["depends_on"] if d not in done]
        elif j.get("trigger"):
            why = "trigger-based (%s); needs a prepared prompt" % j["trigger"] if not _prompt_for(cfg, j) else None
        if not why and not _dir_of(j.get("worktree")):
            why = "worktree not prepared: %s" % j.get("worktree")
        if not why and not _prompt_for(cfg, j):
            why = "no prompt at %s/%s.md" % (b["prompt_dir"], jid)
        if why:
            skipped.append({"id": jid, "why": why})
        else:
            out.append(j)
    out.sort(key=lambda j: (order[j["priority"]], doc["jobs"].index(j)))
    return out, skipped


def _prompt_for(cfg, j):
    p = j.get("prompt_file") or os.path.join(cfg["backlog"]["prompt_dir"], "%s.md" % j.get("id"))
    return p if os.path.isfile(p) else None


def guard_preamble(cfg):
    """backlog.guard_preamble, stripped; "" when missing or blank (then the backlog is held)."""
    p = (cfg.get("backlog") or {}).get("guard_preamble")
    return p.strip() if isinstance(p, str) else ""


def build_prompt(cfg, j):
    pre = guard_preamble(cfg)
    if not pre:  # backlog_tick holds first; never write a prompt without the guard
        raise ValueError("backlog.guard_preamble is empty")
    d = os.path.join(cfg["paths"]["logs"], "backlog-prompts")
    os.makedirs(d, exist_ok=True)
    out = os.path.join(d, "%s.md" % j["id"])
    with open(_prompt_for(cfg, j)) as f:
        body = f.read()
    with open(out, "w") as f:
        f.write(pre + "\n\n" + body)
    return out


def counts(cfg):
    """Queue depth from queue.yaml + state file: pending (queued, not yet run/finished), running, done, failed, blocked."""
    try:
        with open(cfg["backlog"]["queue"]) as f:
            doc = parse_queue_yaml(f.read())
    except FileNotFoundError:
        doc = {"jobs": []}
    st = load_state(cfg)
    out = {"pending": 0, "running": 0, "done": 0, "failed": 0, "blocked": 0}
    for j in doc["jobs"]:
        s = st.get(j.get("id"), {}).get("status")
        if s in ("running", "done", "failed"):
            out[s] += 1
        elif j.get("status") == "queued":
            out["pending"] += 1
        else:
            out["blocked"] += 1
    return out


def stack_ff(worktree, branch, runner=None):
    """Fast-forward a stacked job's worktree branch onto its parent branch (`stack_on:`) right before launch.
    Local only, --ff-only: never merges, rebases, resets or pushes. Returns (ok, message)."""
    import subprocess
    run = runner or (lambda a: subprocess.run(a, capture_output=True, text=True, timeout=120))
    if not isinstance(branch, str) or not re.fullmatch(r"[A-Za-z0-9._/-]{1,120}", branch) or branch.startswith("-"):
        return False, "bad stack_on branch %r" % (branch,)
    g = ["git", "-C", worktree]
    if run(g + ["rev-parse", "--verify", "--quiet", branch + "^{commit}"]).returncode != 0:
        return False, "stack_on branch %s not found" % branch
    r = run(g + ["merge", "--ff-only", "--quiet", branch])
    if r.returncode != 0:
        return False, "cannot fast-forward onto %s: %s" % (branch, (r.stderr or r.stdout or "").strip()[:200])
    h = run(g + ["rev-parse", "HEAD"])
    return True, (h.stdout or "").strip()


IDENTITY_TEMPLATE = "<your-name>"  # runner.commit_identity as shipped: counts as unset
IDENTITY_RE = re.compile(r"\s*([^<>@\s][^<>@]*?)\s*<([^<>@\s]+@[^<>@\s]+\.[^<>@\s]+)>\s*")


def commit_identity(cfg, worktree, runner=None):
    """((name, address) or "repo", None) for a job's local commit, or (None, reason) when no commit may be made.
    runner.commit_identity "Name <address>" wins; unset ("" / missing / the <your-name> template) falls back to the
    repo's own git config (user.name and user.email, both needed); a malformed value never falls back."""
    import subprocess
    run = runner or (lambda a: subprocess.run(a, capture_output=True, text=True, timeout=120))
    v = (cfg.get("runner") or {}).get("commit_identity")
    v = v.strip() if isinstance(v, str) else ""
    if v and IDENTITY_TEMPLATE not in v:
        m = IDENTITY_RE.fullmatch(v)
        if not m:
            return None, "runner.commit_identity is not of the form 'Name <address>'; commit skipped"
        return (m.group(1), m.group(2)), None
    g = ["git", "-C", worktree]
    if all(run(g + ["config", k]).stdout.strip() for k in ("user.name", "user.email")):
        return "repo", None
    return None, "runner.commit_identity is unset and the repo has no git user.name / user.email; commit skipped"


def commit_local(worktree, message, runner=None, identity="repo"):
    """Commit everything in a job's git worktree locally (never pushes). identity: (name, address) for author and
    committer, or "repo" for the repo's own git config (see commit_identity). Returns the new sha or None."""
    import subprocess
    run = runner or (lambda a: subprocess.run(a, capture_output=True, text=True, timeout=120))
    g = ["git", "-C", worktree]
    if run(g + ["rev-parse", "--is-inside-work-tree"]).returncode != 0:
        return None
    if not run(g + ["status", "--porcelain"]).stdout.strip():
        return None
    ident = []
    if identity != "repo":
        name, address = identity
        ident = ["-c", "user.name=%s" % name, "-c", "user.email=%s" % address]
    if run(g + ["add", "-A"]).returncode != 0:
        return None
    if run(["git"] + ident + ["-C", worktree, "commit", "-q", "-m", message]).returncode != 0:
        return None
    r = run(g + ["rev-parse", "HEAD"])
    return r.stdout.strip() if r.returncode == 0 else None
