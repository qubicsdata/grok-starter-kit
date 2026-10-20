"""Safe policy: the runner's defaults, quiet hours in any time zone, no tmux, the enabled gate, the probe spacing.

SAFE below is the safe-limits table of the runner design. Both the example config (runner.config.example.json)
and the code defaults (crlib/policy.py, filled into a config at load time, add-only) must equal it; the pure policy
functions fall back to the same values when a key is missing. Every test runs in the runner test sandbox (helpers):
a temp KIT_HOME, the fake claude only; nothing here starts a real claude, a tmux or a job process."""
import glob, io, json, os, re, subprocess, sys, tokenize, unittest
from unittest import mock
from helpers import TempEnv, RUNNER_DIR, BIN, EXAMPLE_CONFIG, TEST_TZ
from crlib import backlog as B, common, sched as S, usage as U
from crlib.common import append_jsonl, iso, log_path, to_epoch

KIT_ROOT = os.path.dirname(RUNNER_DIR)
ZERO = {"total": 0, "opus": 0, "external": []}
CODE = [os.path.join(BIN, "cr")] + sorted(glob.glob(os.path.join(BIN, "crlib", "*.py")))
SHELL = [os.path.join(BIN, "run-claude.sh"), os.path.join(RUNNER_DIR, "claude-run-flags.sh"),
         os.path.join(RUNNER_DIR, "claude-bash-env.sh")]

# The safe limits, as they must appear in the example config. The code default for quiet_hours.tz is UTC.
SAFE = {
    "policy": {
        "total_cap": 4, "opus_cap": 3,
        "session": {"pause_noncritical_pct": 80, "stop_new_pct": 90},
        "weekly": {"restricted_pct": 68, "critical_only_pct": 75, "stop_new_pct": 80},
        "rate_limit_park_statuses": ["rejected"], "overage": "disabled",
    },
    "usage": {
        "primary_source": "rate_limit_event", "probe_method": "print", "probe_fallback": "none",
        "poll_interval_minutes": 30, "min_probe_spacing_minutes": 30, "near_park_min_probe_spacing_minutes": 5,
    },
    "backlog": {
        "max_concurrent": 3, "reserve_slots": 1, "reserve_opus": 1, "session_max_pct": 80, "weekly_max_pct": 75,
        "fable": {"max_concurrent": 2},
        "quiet_hours": {"enabled": True, "start": "01:00", "end": "07:00", "tz": "${KIT_TZ}"},
        "weekly_pacing": {
            "all_models": {"enabled": True, "target_pct": 70, "target_hours_before_reset": 18, "final_pct": 75,
                           "slack_pct": 2, "near_cap": 2},
            "fable": {"enabled": True, "target_pct": 75, "target_hours_before_reset": 0, "final_pct": 75,
                      "slack_pct": 2, "near_cap": 1, "park_pct": 80, "near_park_pct": 75,
                      "fresh_minutes": 30, "stale_near_cap_minutes": 45, "stale_block_minutes": 90},
        },
    },
}
TZ_PATH = ("backlog", "quiet_hours", "tz")


def leaves(o, pre=()):
    if isinstance(o, dict):
        for k, v in o.items():
            for x in leaves(v, pre + (k,)):
                yield x
    else:
        yield pre, o


def get(o, path):
    for k in path:
        if not isinstance(o, dict) or k not in o:
            return KeyError
        o = o[k]
    return o


def drop(o, path):
    for k in path[:-1]:
        o = o.get(k) or {}
    o.pop(path[-1], None)


def code_defaults():
    """SAFE with the code's own time zone default (UTC: the template's ${KIT_TZ} is filled in at setup)."""
    want = dict(leaves(SAFE))
    want[TZ_PATH] = "UTC"
    return want


def read(p):
    with open(p) as f:
        return f.read()


def raw_example():
    with open(EXAMPLE_CONFIG) as f:
        return json.load(f)


def write_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(obj, f, indent=1)


def policy_module(tc):
    try:
        from crlib import policy
    except ImportError:
        tc.fail("crlib/policy.py (the safe defaults) is missing")
    return policy


def python_code(text):
    """Source tokens minus comments and docstrings, joined by spaces."""
    out, prev = [], None
    for tok in tokenize.generate_tokens(io.StringIO(text).readline):
        if tok.type == tokenize.COMMENT:
            continue
        if tok.type == tokenize.STRING and prev in (None, tokenize.NEWLINE, tokenize.INDENT, tokenize.DEDENT,
                                                    tokenize.NL):
            prev = tok.type
            continue
        if tok.type not in (tokenize.NL,):
            prev = tok.type
        out.append(tok.string)
    return " ".join(out)


def shell_code(text):
    return "\n".join(re.sub(r"(^|\s)#.*$", "", line) for line in text.splitlines())


def qjob(i, task_type="docs"):
    return ("  - id: Q%02d\n    title: job %d\n    priority: P1\n    task_type: %s\n    channel: direct\n"
            "    worktree: {WT}\n    status: queued\n" % (i, i, task_type))


def eff(now, w=9.0, s=10, fable=0.0, age=5.0, probe_failed=False):
    reset = iso(now + 3 * 86400)
    e = {"session": {"pct": s, "basis": "observed", "resets_at": iso(now + 3600)},
         "weekly": {"pct": w, "basis": "observed", "resets_at": reset}, "session_elapsed_min": 30,
         "probe_failed": probe_failed}
    e["weekly_fable"] = None if fable is None else {"pct": fable, "basis": "observed", "resets_at": reset, "age_min": age}
    return e


class BacklogCase(unittest.TestCase):
    """A TempEnv with a backlog queue; `cfg` may be replaced by a config loaded from a raw example copy."""
    def setUp(self):
        self.t = TempEnv().__enter__()
        self.cfg = self.t.cfg
        self.wt = os.path.join(self.t.d, "wt"); os.makedirs(self.wt)
        self.pd = os.path.join(self.t.d, "prompts"); os.makedirs(self.pd)
        self.q = os.path.join(self.t.d, "queue.yaml")
        self.launched = []
        self.enable_backlog(self.cfg)

    def tearDown(self):
        self.t.__exit__()

    def enable_backlog(self, cfg):
        cfg["backlog"].update({"enabled": True, "queue": self.q, "state_file": os.path.join(self.t.d, "state.json"),
                               "prompt_dir": self.pd, "require_soak_window": False})

    def write_queue(self, jobs):
        with open(self.q, "w") as f:
            f.write("version: 1\njobs:\n" + "".join(jobs).replace("{WT}", self.wt))
        for line in "".join(jobs).splitlines():
            if line.strip().startswith("- id:"):
                jid = line.split(":", 1)[1].strip()
                with open(os.path.join(self.pd, jid + ".md"), "w") as f:
                    f.write("do " + jid)

    def launcher(self, cfg, spec):
        self.launched.append(spec)
        return 4500000 + len(self.launched)

    def families(self):
        return [S.job_family(self.cfg, {"task_type": s["task_type"], "model": s.get("model")}) for s in self.launched]

    def tick(self, now, e=None, prober=None, alive=True, clock=None):
        os.environ["CR_NOW"] = iso(clock if clock is not None else now)  # the per-launch quiet-hours re-check
        return S.backlog_tick(self.cfg, e or eff(now), {"park": None, "local": None}, ZERO, 0, now,
                              launcher=self.launcher, procs_alive=lambda pid: alive, prober=prober)

    def finish(self, jid, now):
        rid = B.load_state(self.cfg)[jid]["run_id"]
        append_jsonl(log_path(self.cfg, "runs.jsonl"), {"event": "finish", "run_id": rid, "rc": 0, "ts": iso(now)})

    def load_raw(self, name, edit=None, tz=None):
        """A config loaded from the RAW example (placeholders in place) with KIT_HOME = the sandbox and KIT_TZ = tz."""
        ex = raw_example()
        if edit:
            edit(ex)
        path = os.path.join(self.t.d, "runner", name)
        write_json(path, ex)
        os.environ["KIT_HOME"] = self.t.d
        if tz is None:
            os.environ.pop("KIT_TZ", None)
        else:
            os.environ["KIT_TZ"] = tz
        try:
            cfg = common.load_config(path)
        except Exception as e:  # noqa: BLE001
            self.fail("load_config raised %s: %s" % (type(e).__name__, e))
        self.enable_backlog(cfg)
        self.cfg = cfg
        return cfg


# ---------------- (a) the defaults ----------------

class SafeDefaultsTests(unittest.TestCase):
    def test_example_config_equals_the_safe_limits(self):
        ex = raw_example()
        for path, want in leaves(SAFE):
            with self.subTest(key=".".join(path)):
                self.assertEqual(get(ex, path), want)

    def test_code_defaults_equal_the_safe_limits(self):
        P = policy_module(self)
        self.assertEqual(sorted(leaves(P.DEFAULTS)), sorted(code_defaults().items()))

    def test_probe_floors(self):
        P = policy_module(self)
        self.assertEqual((P.PROBE_FLOOR_MINUTES, P.NEAR_PARK_PROBE_FLOOR_MINUTES), (30, 5))

    def test_fill_defaults_is_add_only(self):
        P = policy_module(self)
        cfg = {"_comment": "keep", "policy": {"total_cap": 9, "_comment_x": 1}, "backlog": {"quiet_hours": {"start": "02:00"}}}
        out = P.fill_defaults(cfg)
        self.assertIs(out, cfg)
        self.assertEqual((cfg["_comment"], cfg["policy"]["_comment_x"]), ("keep", 1))
        self.assertEqual((cfg["policy"]["total_cap"], cfg["policy"]["opus_cap"]), (9, 3))
        q = cfg["backlog"]["quiet_hours"]
        self.assertEqual((q["start"], q["end"], q["enabled"], q["tz"]), ("02:00", "07:00", True, "UTC"))
        self.assertEqual(cfg["backlog"]["weekly_pacing"]["fable"]["stale_block_minutes"], 90)
        P.DEFAULTS["policy"]["session"]["x"] = 1  # a filled config never shares a dict with DEFAULTS
        try:
            self.assertNotIn("x", cfg["policy"]["session"])
        finally:
            del P.DEFAULTS["policy"]["session"]["x"]

    def test_no_literal_default_for_a_safe_limit_outside_the_policy_module(self):
        names = sorted({path[-1] for path, _ in leaves(SAFE)})
        bad = []
        for p in CODE:
            if os.path.basename(p) == "policy.py":
                continue
            for n, line in enumerate(read(p).splitlines(), 1):
                for name in names:
                    if re.search(r'\.get\(\s*"%s"\s*,\s*(?:\d|"|\[|True|False)' % re.escape(name), line):
                        bad.append("%s:%d %s" % (os.path.relpath(p, RUNNER_DIR), n, name))
        self.assertEqual(bad, [], "literal defaults drift from crlib/policy.py")


class LoadedDefaultsTests(BacklogCase):
    def strip(self, ex):
        for path, _ in leaves(SAFE):
            drop(ex, path)
        for sect in (("backlog", "quiet_hours"), ("backlog", "fable"), ("backlog", "weekly_pacing")):
            drop(ex, sect)

    def test_loader_fills_every_missing_safe_limit(self):
        cfg = self.load_raw("router-stripped.json", self.strip)
        for path, want in code_defaults().items():
            with self.subTest(key=".".join(path)):
                self.assertEqual(get(cfg, path), want)

    def test_loader_keeps_your_own_values(self):
        def edit(ex):
            ex["backlog"]["max_concurrent"] = 5
            ex["policy"]["total_cap"] = 6
            ex["backlog"]["quiet_hours"]["start"] = "02:00"
            ex["usage"]["min_probe_spacing_minutes"] = 10
        cfg = self.load_raw("router-own.json", edit)
        self.assertEqual((cfg["backlog"]["max_concurrent"], cfg["policy"]["total_cap"],
                          cfg["backlog"]["quiet_hours"]["start"], cfg["usage"]["min_probe_spacing_minutes"]),
                         (5, 6, "02:00", 10))

    def test_stripped_config_runs_under_the_safe_limits(self):
        cfg = self.load_raw("router-stripped.json", self.strip)
        now = to_epoch("2026-10-18T12:00:00Z")
        pending = [{"id": "j%d" % i, "task_type": "implement", "priority": 0, "created": "%02d" % i} for i in range(8)]
        pending.append({"id": "r1", "task_type": "rebase", "priority": 0, "created": "99"})
        try:
            start, info = S.decide(cfg, eff(now), None, pending, ZERO, now)
        except KeyError as e:  # a safe limit the loader did not fill in
            self.fail("decide needs a key the loader did not fill: %s" % e)
        fams = [S.job_family(cfg, j) for j in start]
        self.assertEqual((fams.count("opus"), len(start)), (3, 4))
        self.assertEqual(S.decide(cfg, eff(now, s=80), None, pending, ZERO, now)[1]["mode"], "restricted")
        self.assertEqual(S.decide(cfg, eff(now, s=90), None, pending, ZERO, now)[1]["mode"], "stopped")
        self.assertEqual(S.decide(cfg, eff(now, w=80), None, pending, ZERO, now)[1]["mode"], "stopped")
        self.assertTrue(S.in_quiet_hours(cfg, to_epoch("2026-10-18T02:00:00Z")))
        self.assertFalse(S.in_quiet_hours(cfg, to_epoch("2026-10-18T07:00:00Z")))
        self.write_queue([qjob(i, "fable-implement") for i in range(5)] + [qjob(10 + i) for i in range(5)])
        out = self.tick(now)
        self.assertEqual((self.families().count("fable"), len(self.launched)), (2, 3), out)
        self.assertEqual(out["pacing"]["all_models"]["mode"], "behind")


class PureFallbackTests(unittest.TestCase):
    """The pure policy functions with a config that lacks the keys: the safe limits apply."""
    NOW = to_epoch("2026-10-18T12:00:00Z")

    def test_fable_age_rule(self):
        for age, want in ((30, 2), (45, 2), (45.1, 1), (90, 1), (90.1, 0)):
            self.assertEqual(S.fable_age_cap({}, eff(self.NOW, age=age), 2)[0], want, age)

    def test_pacing_slack_and_near_cap(self):
        p = {"target_pct": 70, "target_hours_before_reset": 18, "final_pct": 75}
        reset = iso(self.NOW + 3 * 86400)
        line = S.pacing_line(p, reset, self.NOW)
        self.assertEqual(S.pacing_cap(p, line - 1, reset, self.NOW, 3)[0], 3)
        self.assertEqual(S.pacing_cap(p, line + 1.9, reset, self.NOW, 3)[0], 1)   # near: the conservative near_cap
        self.assertEqual(S.pacing_cap(p, line + 2, reset, self.NOW, 3)[0], 0)     # slack 2: ahead

    def test_quiet_hours_without_a_section(self):
        q = lambda s: S.in_quiet_hours({}, to_epoch(s))
        self.assertFalse(q("2026-10-18T00:59:59Z"))
        self.assertTrue(q("2026-10-18T01:00:00Z"))
        self.assertTrue(q("2026-10-18T06:59:59Z"))
        self.assertFalse(q("2026-10-18T07:00:00Z"))

    def test_probe_spacing_without_usage_keys(self):
        with TempEnv() as t:
            cfg = dict(t.cfg, usage={})
            cfg["paths"] = t.cfg["paths"]
            t.write_usage([{"ts": iso(self.NOW - 29 * 60), "kind": "probe_failed"}])
            self.assertFalse(U.probe_due(cfg, self.NOW))
            self.assertTrue(U.probe_due(cfg, self.NOW + 61))

    def test_park_on_rejected_without_the_key(self):
        with TempEnv() as t:
            t.cfg["policy"].pop("rate_limit_park_statuses", None)
            reset = iso(self.NOW + 3600)
            t.write_usage([{"ts": iso(self.NOW - 60), "kind": "rate_limit_event", "status": "allowed_warning",
                            "resets_at": reset, "session_5h": {"used_pct": 90.0, "resets_at": reset}}])
            self.assertIsNone(U.state(t.cfg, self.NOW, include_local=False)["park"])
            t.write_usage([{"ts": iso(self.NOW - 30), "kind": "rate_limit_event", "status": "rejected",
                            "resets_at": reset, "session_5h": {"used_pct": 100.0, "resets_at": reset}}])
            park = U.state(t.cfg, self.NOW, include_local=False)["park"]
            self.assertTrue(park and park["active"])


# ---------------- (b) quiet hours in any time zone ----------------

class QuietHoursZoneTests(BacklogCase):
    def quiet(self, when):
        return S.in_quiet_hours(self.cfg, to_epoch(when))

    def test_auckland_bounds(self):
        cfg = self.load_raw("router-nz.json", tz="Pacific/Auckland")
        self.assertEqual(cfg["backlog"]["quiet_hours"]["tz"], "Pacific/Auckland")
        self.assertFalse(self.quiet("2026-10-18T11:59:59Z"))  # 00:59:59 NZDT
        self.assertTrue(self.quiet("2026-10-18T12:00:00Z"))   # 01:00 NZDT
        self.assertTrue(self.quiet("2026-10-18T17:59:59Z"))   # 06:59:59 NZDT
        self.assertFalse(self.quiet("2026-10-18T18:00:00Z"))  # 07:00 NZDT
        self.assertFalse(self.quiet("2026-10-18T02:00:00Z"))  # 15:00 NZDT, although 02:00 in UTC

    def test_auckland_when_summer_time_ends(self):
        # The first Sunday of April: 03:00 NZDT becomes 02:00 NZST, so that night the window lasts seven hours.
        self.load_raw("router-nz.json", tz="Pacific/Auckland")
        self.assertFalse(self.quiet("2026-04-04T11:59:59Z"))
        self.assertTrue(self.quiet("2026-04-04T12:00:00Z"))   # 01:00 NZDT
        self.assertTrue(self.quiet("2026-04-04T18:59:59Z"))   # 06:59:59 NZST
        self.assertFalse(self.quiet("2026-04-04T19:00:00Z"))  # 07:00 NZST

    def test_los_angeles_fall_back_night(self):
        # The first Sunday of November: 02:00 PDT becomes 01:00 PST; both 01:00 hours are quiet.
        self.load_raw("router-la.json", tz="America/Los_Angeles")
        self.assertFalse(self.quiet("2026-11-01T07:59:59Z"))  # 00:59:59 PDT
        self.assertTrue(self.quiet("2026-11-01T08:00:00Z"))   # 01:00 PDT
        self.assertTrue(self.quiet("2026-11-01T09:00:00Z"))   # 01:00 PST, the repeated hour
        self.assertTrue(self.quiet("2026-11-01T14:59:59Z"))   # 06:59:59 PST
        self.assertFalse(self.quiet("2026-11-01T15:00:00Z"))  # 07:00 PST

    def test_los_angeles_spring_forward_night(self):
        # The second Sunday of March: 02:00 PST becomes 03:00 PDT; the window lasts six hours.
        self.load_raw("router-la.json", tz="America/Los_Angeles")
        self.assertFalse(self.quiet("2026-03-08T08:59:59Z"))  # 00:59:59 PST
        self.assertTrue(self.quiet("2026-03-08T09:00:00Z"))   # 01:00 PST
        self.assertTrue(self.quiet("2026-03-08T13:59:59Z"))   # 06:59:59 PDT
        self.assertFalse(self.quiet("2026-03-08T14:00:00Z"))  # 07:00 PDT

    def test_kit_config_timezone_without_env(self):
        with open(os.path.join(self.t.d, "kit.config.yaml"), "w") as f:
            f.write('kit:\n  home: "%s"\n  timezone: "Pacific/Auckland"\n' % self.t.d)
        self.load_raw("router-nz.json", tz=None)
        self.assertTrue(self.quiet("2026-10-18T12:00:00Z"))
        self.assertFalse(self.quiet("2026-10-18T18:00:00Z"))

    def test_auckland_no_new_starts_running_jobs_finish_and_are_reaped(self):
        self.load_raw("router-nz.json", tz="Pacific/Auckland")
        self.write_queue([qjob(i) for i in range(6)])
        self.tick(to_epoch("2026-10-18T10:30:00Z"))            # 23:30 NZDT
        self.assertEqual(len(self.launched), 3)
        self.finish("Q00", to_epoch("2026-10-18T12:30:00Z"))
        out = self.tick(to_epoch("2026-10-18T13:00:00Z"))      # 02:00 NZDT
        st = B.load_state(self.cfg)
        self.assertEqual(st["Q00"]["status"], "done")
        self.assertEqual((st["Q01"]["status"], st["Q02"]["status"]), ("running", "running"))
        self.assertEqual(len(self.launched), 3)
        held = " ".join(out["held"])
        self.assertIn("quiet hours", held)
        self.assertIn("Pacific/Auckland", held)
        self.tick(to_epoch("2026-10-18T17:59:00Z"))            # 06:59 NZDT: still quiet
        self.assertEqual(len(self.launched), 3)
        self.tick(to_epoch("2026-10-18T18:00:00Z"))            # 07:00 NZDT: the free slot fills
        self.assertEqual(len(self.launched), 4)

    def test_los_angeles_both_one_oclocks_block_starts(self):
        self.load_raw("router-la.json", tz="America/Los_Angeles")
        self.write_queue([qjob(i) for i in range(6)])
        self.tick(to_epoch("2026-11-01T07:30:00Z"))            # 00:30 PDT
        self.assertEqual(len(self.launched), 3)
        self.finish("Q01", to_epoch("2026-11-01T08:00:00Z"))
        for when in ("2026-11-01T08:30:00Z", "2026-11-01T09:30:00Z", "2026-11-01T14:59:00Z"):  # 01:30 PDT, 01:30 PST, 06:59 PST
            out = self.tick(to_epoch(when))
            self.assertEqual(len(self.launched), 3, (when, out.get("held")))
        self.assertEqual(B.load_state(self.cfg)["Q01"]["status"], "done")
        self.tick(to_epoch("2026-11-01T15:00:00Z"))            # 07:00 PST
        self.assertEqual(len(self.launched), 4)

    def test_launch_time_recheck_uses_the_configured_zone(self):
        # The tick starts at 00:59 NZDT; the clock read before the launch says 01:00 NZDT (15:00 in the sandbox zone).
        self.load_raw("router-nz.json", tz="Pacific/Auckland")
        self.write_queue([qjob(i) for i in range(3)])
        out = self.tick(to_epoch("2026-10-18T11:59:00Z"), clock=to_epoch("2026-10-18T12:00:00Z"))
        self.assertEqual((self.launched, out.get("gate_stop")), ([], "quiet hours began"))
        self.assertNotEqual(TEST_TZ, "Pacific/Auckland")


# ---------------- (c) no tmux ----------------

class NoTmuxTests(unittest.TestCase):
    def test_no_tmux_in_runner_code(self):
        bad = []
        for p in CODE:
            if re.search(r"\btmux\b", python_code(read(p))):
                bad.append(os.path.relpath(p, RUNNER_DIR))
        for p in SHELL:
            if re.search(r"\btmux\b", shell_code(read(p))):
                bad.append(os.path.relpath(p, RUNNER_DIR))
        self.assertEqual(bad, [], "tmux in runner code (comments and docstrings aside)")
        self.assertTrue(re.search(r"\btmux\b", python_code('x = {"tmux": 1}')))  # the scan has teeth
        self.assertFalse(re.search(r"\btmux\b", python_code('"""no tmux"""\nx = 1  # tmux\n')))

    def test_only_the_print_probe_exists(self):
        self.assertEqual(sorted(U.PROBES), ["print"])
        self.assertFalse(hasattr(U, "probe_tmux"))

    def run_probe(self, cfg, now):
        calls = []
        with mock.patch.object(U.subprocess, "run", lambda argv, **kw: calls.append(list(argv)) or None):
            rec = U.poll(cfg, now=now)
        return rec, calls

    def test_config_saying_tmux_starts_no_process(self):
        now = to_epoch("2026-10-18T12:00:00Z")
        with TempEnv() as t:
            t.cfg["usage"]["probe_method"] = "tmux"
            t.cfg["usage"]["probe_fallback"] = "tmux"
            rec, calls = self.run_probe(t.cfg, now)
            self.assertEqual((rec, calls), (None, []))
            kinds = [r.get("kind") for r in t.read("usage.jsonl")]
            self.assertEqual(kinds, ["probe_failed"])
            self.assertNotIn("tmux", json.dumps(t.read("usage.jsonl")))

    def test_loop_with_tmux_config_starts_no_process(self):
        with TempEnv() as t:
            cfg = t.cfg
            cfg["runner"]["enabled"] = True
            cfg["usage"]["probe_method"] = "tmux"
            cfg["usage"]["probe_fallback"] = "tmux"
            calls = []
            pid = os.path.join(t.logs, "p.pid")
            with mock.patch.object(S, "tick", lambda *a, **k: {"started": []}), \
                    mock.patch.object(U.subprocess, "run", lambda argv, **kw: calls.append(list(argv)) or None):
                S.loop(cfg, interval=0, probe=True, max_ticks=1, pidfile=pid, stop_file=os.path.join(t.logs, "p.stop"))
            self.assertEqual(calls, [])
            self.assertEqual([r.get("kind") for r in t.read("usage.jsonl")], ["probe_failed"])
            self.assertEqual([r for r in t.read("scheduler.jsonl") if r.get("event") == "error"], [])


# ---------------- (d) the enabled gate ----------------

class EnabledGateTests(unittest.TestCase):
    def setUp(self):
        self.t = TempEnv().__enter__()
        self.cfg = self.t.cfg
        self.pid = os.path.join(self.t.logs, "queue-runner.pid")
        self.stop = os.path.join(self.t.logs, "queue-runner.stop")
        self.ticks = []

    def tearDown(self):
        self.t.__exit__()

    def disabled_error(self):
        exc = getattr(S, "RunnerDisabled", None)
        if exc is None:
            self.fail("crlib/sched.py has no RunnerDisabled error")
        return exc

    def run_loop(self):
        with mock.patch.object(S, "tick", lambda *a, **k: self.ticks.append(1) or {"started": []}):
            return S.loop(self.cfg, interval=0, probe=False, max_ticks=1, pidfile=self.pid, stop_file=self.stop)

    def test_example_ships_off(self):
        self.assertIs(raw_example()["runner"]["enabled"], False)
        self.assertIn("Off by default", read(os.path.join(RUNNER_DIR, "DESIGN.md")))

    def test_loop_refuses_before_any_start(self):
        exc = self.disabled_error()
        for label, value, present in (("false", False, True), ("missing", None, False), ("string true", "true", True),
                                      ("one", 1, True), ("null", None, True)):
            with self.subTest(enabled=label):
                if present:
                    self.cfg["runner"]["enabled"] = value
                else:
                    self.cfg["runner"].pop("enabled", None)
                with self.assertRaises(exc) as cm:
                    self.run_loop()
                self.assertIn("runner.enabled", str(cm.exception))
                self.assertEqual(self.ticks, [])
                self.assertFalse(os.path.exists(self.pid))
                self.assertFalse(os.path.exists(os.path.join(self.t.logs, "scheduler.jsonl")))

    def test_loop_runs_when_enabled(self):
        self.cfg["runner"]["enabled"] = True
        self.run_loop()
        self.assertEqual(self.ticks, [1])
        self.assertFalse(os.path.exists(self.pid))
        ev = [r.get("event") for r in self.t.read("scheduler.jsonl")]
        self.assertEqual(ev, ["runner_start", "runner_stop"])

    def test_launch_refuses_while_off(self):
        exc = self.disabled_error()
        spec = {"id": "x1", "task_type": "docs", "label": "x1", "cwd": self.t.d, "prompt_file": __file__}
        with self.assertRaises(exc):
            S.launch(self.cfg, spec)
        self.assertFalse(os.path.exists(os.path.join(self.t.logs, "sched", "x1.out")))
        self.assertEqual(S._CHILDREN, {})

    def test_cr_sched_loop_refuses_as_a_process(self):
        r = subprocess.run([sys.executable, os.path.join(BIN, "cr"), "sched", "loop", "--no-probe", "--interval", "0.2",
                            "--pidfile", self.pid, "--stop-file", self.stop], capture_output=True, text=True, timeout=30)
        self.assertEqual(r.returncode, 4, r.stderr)
        self.assertIn("runner.enabled", r.stderr)
        self.assertIn("TERMS-NOTICE.md", r.stderr)
        self.assertFalse(os.path.exists(self.pid))
        self.assertFalse(os.path.exists(os.path.join(self.t.logs, "scheduler.jsonl")))

    def test_cr_sched_tick_refuses_as_a_process(self):
        # A pending job and no usage reading: an ungated tick would probe and launch. The CLI refuses first.
        S.enqueue(self.cfg, "rebase", self.t.d, __file__)
        r = subprocess.run([sys.executable, os.path.join(BIN, "cr"), "sched", "tick"], capture_output=True, text=True,
                           timeout=30)
        self.assertEqual(r.returncode, 4, r.stderr)
        self.assertIn("runner.enabled", r.stderr)
        self.assertNotIn("Traceback", r.stderr)
        self.assertEqual(len(S.list_jobs(self.cfg, "pending")), 1)
        for name in ("scheduler.jsonl", "usage.jsonl"):
            self.assertFalse(os.path.exists(os.path.join(self.t.logs, name)), name)


# ---------------- (e) probe spacing ----------------

class ProbeSpacingTests(BacklogCase):
    NOW = to_epoch("2026-10-18T12:00:00Z")

    def lower(self):
        self.cfg["usage"]["poll_interval_minutes"] = 1
        self.cfg["usage"]["min_probe_spacing_minutes"] = 1
        self.cfg["usage"]["near_park_min_probe_spacing_minutes"] = 1

    def test_probe_due_never_closer_than_30_min(self):
        self.lower()
        self.t.write_usage([{"ts": iso(self.NOW - 29 * 60), "kind": "probe_failed"}])
        self.assertFalse(U.probe_due(self.cfg, self.NOW))
        self.assertTrue(U.probe_due(self.cfg, self.NOW + 61))

    def test_a_wider_spacing_is_honored(self):
        self.cfg["usage"]["min_probe_spacing_minutes"] = 45
        self.t.write_usage([{"ts": iso(self.NOW - 40 * 60), "kind": "usage_screen", "observed": True}])
        self.assertFalse(U.probe_due(self.cfg, self.NOW))
        self.assertTrue(U.probe_due(self.cfg, self.NOW + 6 * 60))

    def test_tick_probe_respects_the_floor(self):
        self.lower()
        reset = iso(self.NOW + 3600)
        self.t.write_usage([{"ts": iso(self.NOW - 25 * 60), "kind": "usage_screen", "observed": True,
                             "session_5h": {"used_pct": 10.0, "resets_at": reset},
                             "weekly_all_models": {"used_pct": 12.0, "resets_at": iso(self.NOW + 3 * 86400)}}])
        self.cfg["backlog"]["enabled"] = False
        S.enqueue(self.cfg, "rebase", self.t.d, __file__)
        calls = []
        screen = ("Current session: 10% used · resets Oct 18, 4pm (Etc/GMT-3)\n"
                  "Current week (all models): 12% used · resets Oct 21, 3pm (Etc/GMT-3)\n")
        prober = lambda cfg: calls.append(1) or screen
        os.environ["CR_NOW"] = iso(self.NOW)
        info = S.tick(self.cfg, prober=prober, procs=[], launcher=lambda c, j: 0, messages=[])
        self.assertEqual((calls, info["probed"]), ([], False))
        os.environ["CR_NOW"] = iso(self.NOW + 6 * 60)  # 31 min after the reading
        S.enqueue(self.cfg, "rebase", self.t.d, __file__)
        info = S.tick(self.cfg, prober=prober, procs=[], launcher=lambda c, j: 0, messages=[])
        self.assertEqual((calls, info["probed"]), ([1], True))

    def test_loop_probes_at_most_every_30_min(self):
        self.lower()
        self.cfg["runner"]["enabled"] = True
        polls = []

        def fake_poll(cfg, *a, **k):
            polls.append(common.now_ts())
            self.t.write_usage([{"ts": iso(common.now_ts()), "kind": "usage_screen", "observed": True}])
            return {}
        pid, stop = os.path.join(self.t.logs, "p.pid"), os.path.join(self.t.logs, "p.stop")
        with mock.patch.object(S, "tick", lambda *a, **k: {"started": []}), mock.patch.object(U, "poll", fake_poll):
            os.environ["CR_NOW"] = iso(self.NOW)
            S.loop(self.cfg, interval=0, probe=True, max_ticks=3, pidfile=pid, stop_file=stop)
            self.assertEqual(len(polls), 1)
            os.environ["CR_NOW"] = iso(self.NOW + 29 * 60)
            S.loop(self.cfg, interval=0, probe=True, max_ticks=2, pidfile=pid, stop_file=stop)
            self.assertEqual(len(polls), 1)
            os.environ["CR_NOW"] = iso(self.NOW + 31 * 60)
            S.loop(self.cfg, interval=0, probe=True, max_ticks=2, pidfile=pid, stop_file=stop)
            self.assertEqual(len(polls), 2)

    def test_near_park_reprobe_never_closer_than_5_min(self):
        self.lower()
        now = to_epoch(eff(self.NOW)["weekly"]["resets_at"]) - 60  # the Fable line is ~75% just before the reset
        reset = iso(now + 60)
        self.write_queue([qjob(0, "fable-security")])
        self.t.write_usage([{"ts": iso(now - 4 * 60), "kind": "usage_screen", "observed": True,
                             "weekly_fable": {"used_pct": 76.0, "resets_at": reset}}])
        probes = []
        e = eff(now, fable=76.0, age=4)
        e["weekly"]["resets_at"] = e["weekly_fable"]["resets_at"] = reset
        out = self.tick(now, e=e, prober=lambda cfg: probes.append(1) or "")
        self.assertEqual(probes, [])  # 4 min since the last probe: the reading is reused, no re-probe
        self.assertEqual(self.families(), ["fable"], out)
        self.assertFalse(U.probe_due(self.cfg, now, spacing_minutes=5))
        self.assertTrue(U.probe_due(self.cfg, now + 61, spacing_minutes=5))


# ---------------- (f) the terms notice ----------------

class TermsNoticeTests(unittest.TestCase):
    NOTICE = os.path.join(RUNNER_DIR, "TERMS-NOTICE.md")

    def test_notice_present(self):
        text = read(self.NOTICE)
        self.assertIn("your own", text)
        self.assertIn("anthropic.com/legal", text)
        self.assertIn("requires legal confirmation", text)

    def test_design_links_the_notice(self):
        head = "\n".join(read(os.path.join(RUNNER_DIR, "DESIGN.md")).splitlines()[:5])
        self.assertIn("TERMS-NOTICE.md", head)

    def test_setup_phase_9_links_the_notice(self):
        text = read(os.path.join(KIT_ROOT, "AGENTS.md"))
        m = re.search(r"^## Phase 9\b.*?(?=^## )", text, re.S | re.M)
        self.assertTrue(m, "AGENTS.md has no Phase 9 section")
        self.assertIn("runner/TERMS-NOTICE.md", m.group(0))
        self.assertIn("runner.enabled: false", m.group(0))

    def test_refusal_names_the_notice(self):
        self.assertIn("TERMS-NOTICE.md", read(os.path.join(BIN, "cr")))


# ---------------- (g) synthetic data only ----------------

class SyntheticDataTests(unittest.TestCase):
    def test_policy_module_and_tests_hold_synthetic_data_only(self):
        from test_fixture_privacy import scan_text
        for p in (__file__, os.path.join(BIN, "crlib", "policy.py"), EXAMPLE_CONFIG):
            with self.subTest(file=os.path.basename(p)):
                self.assertTrue(os.path.isfile(p), "missing")
                self.assertEqual(scan_text(read(p)), set())

    def test_fixture_files_match_the_generator(self):
        r = subprocess.run([sys.executable, "-B", os.path.join(RUNNER_DIR, "tests", "make_synthetic_fixtures.py"), "--check"],
                           capture_output=True, text=True, timeout=120)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


if __name__ == "__main__":
    unittest.main()
