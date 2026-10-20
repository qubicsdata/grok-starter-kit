"""Runner safe limits (the example config's defaults): rate_limit_event primary, claude -p /usage from the scheduler at most
every 30 min, probe_fallback none (no tmux), probe_failed -> events + estimates -> near_cap, caps 3 (Fable 2) /
total 4 / opus 3, quiet hours 01:00-07:00 in ${KIT_TZ}, pacing 70% at reset-18h / 75% at reset, Fable 75% /
park 80%, session pause 80%. The values come from runner/runner.config.example.json (see helpers.TempEnv)."""
import json, os, subprocess, sys, unittest
from helpers import TempEnv, ROOT, TEST_TZ
from crlib import backlog as B, sched as S, usage as U
from crlib.common import iso, to_epoch

RESET = "2026-10-23T18:00:00+03:00"
SAT = to_epoch("2026-10-17T18:00:00+03:00")
ZERO = {"total": 0, "opus": 0, "external": []}


def eff(w=9.0, s=10, fable=0.0, wbasis="observed", sbasis="observed"):
    e = {"session": {"pct": s, "basis": sbasis, "resets_at": "2026-10-17T23:30:00+03:00"},
         "weekly": {"pct": w, "basis": wbasis, "resets_at": RESET}, "session_elapsed_min": 30}
    e["weekly_fable"] = None if fable is None else {"pct": fable, "basis": "observed", "resets_at": RESET, "age_min": 5.0}
    return e


def qjob(i, task_type="docs"):
    return ("  - id: Q%02d\n    title: job %d\n    priority: P1\n    task_type: %s\n    channel: direct\n"
            "    worktree: {WT}\n    status: queued\n" % (i, i, task_type))


class SafeLimitsConfigTests(unittest.TestCase):
    def setUp(self):
        self.t = TempEnv().__enter__(); self.cfg = self.t.cfg

    def tearDown(self):
        self.t.__exit__()

    def test_caps(self):
        b, p = self.cfg["backlog"], self.cfg["policy"]
        self.assertEqual((b["max_concurrent"], b["fable"]["max_concurrent"], p["total_cap"], p["opus_cap"]), (3, 2, 4, 3))

    def test_session_and_weekly_guards(self):
        p, b = self.cfg["policy"], self.cfg["backlog"]
        self.assertEqual(p["session"]["pause_noncritical_pct"], 80)
        self.assertEqual(b["session_max_pct"], 80)
        self.assertEqual(b["weekly_max_pct"], 75)
        w = p["weekly"]
        self.assertEqual((w["restricted_pct"], w["critical_only_pct"], w["stop_new_pct"]), (68, 75, 80))

    def test_pacing_values(self):
        pa = self.cfg["backlog"]["weekly_pacing"]["all_models"]
        fa = self.cfg["backlog"]["weekly_pacing"]["fable"]
        self.assertEqual((pa["target_pct"], pa["target_hours_before_reset"], pa["final_pct"]), (70, 18, 75))
        self.assertEqual((fa["target_pct"], fa["final_pct"], fa["park_pct"]), (75, 75, 80))

    def test_all_models_line_70_at_friday_midnight_75_at_reset(self):
        pa = self.cfg["backlog"]["weekly_pacing"]["all_models"]
        self.assertAlmostEqual(S.pacing_line(pa, RESET, to_epoch("2026-10-23T00:00:00+03:00")), 70.0)
        self.assertAlmostEqual(S.pacing_line(pa, RESET, to_epoch(RESET)), 75.0)
        self.assertAlmostEqual(S.pacing_line(pa, RESET, SAT), 70 * 24 / 150.0, places=3)

    def test_fable_line_and_park(self):
        fa = self.cfg["backlog"]["weekly_pacing"]["fable"]
        self.assertAlmostEqual(S.pacing_line(fa, RESET, to_epoch(RESET)), 75.0)
        self.assertEqual(S.pacing_cap(fa, 80, RESET, SAT, 2)[1]["mode"], "parked")
        self.assertEqual(S.pacing_cap(fa, 79.9, RESET, to_epoch(RESET) - 60, 2)[0], 0)  # over the 75% line

    def test_usage_probe_config(self):
        u = self.cfg["usage"]
        self.assertEqual(u["probe_method"], "print")
        self.assertEqual(u["probe_fallback"], "none")
        self.assertGreaterEqual(u["poll_interval_minutes"], 30)
        self.assertGreaterEqual(u["min_probe_spacing_minutes"], 30)

    def test_quiet_hours_config(self):
        q = self.cfg["backlog"]["quiet_hours"]
        self.assertEqual((q["enabled"], q["start"], q["end"], q["tz"]), (True, "01:00", "07:00", TEST_TZ))  # ${KIT_TZ}


class NoTmuxTests(unittest.TestCase):
    """probe_fallback none: a failed claude -p /usage never falls back to a tmux screen scrape."""

    def run_probe(self, cfg):
        calls = []
        real = subprocess.run

        def fake(argv, **kw):
            calls.append(list(argv))
            return subprocess.CompletedProcess(argv, 1, stdout="not json", stderr="")
        U.subprocess.run = fake
        try:
            rec = U.poll(cfg, now=SAT)
        finally:
            U.subprocess.run = real
        return rec, calls

    def test_failed_print_probe_does_not_use_tmux(self):
        with TempEnv() as t:
            rec, calls = self.run_probe(t.cfg)
            self.assertIsNone(rec)
            self.assertEqual(len(calls), 1)
            self.assertIn("claude", calls[0]); self.assertIn("/usage", calls[0])
            self.assertNotIn("tmux", json.dumps(calls))
            failed = [r for r in t.read("usage.jsonl") if r.get("kind") == "probe_failed"]
            self.assertEqual(len(failed), 1)
            self.assertNotIn("tmux", json.dumps(failed))

    def test_tmux_path_removed_even_if_config_says_tmux(self):
        with TempEnv() as t:
            t.cfg["usage"]["probe_fallback"] = "tmux"
            rec, calls = self.run_probe(t.cfg)
            self.assertNotIn("tmux", json.dumps(calls))
            self.assertFalse(hasattr(U, "probe_tmux"))


class ProbeCadenceTests(unittest.TestCase):
    def test_probe_due_every_30_min(self):
        with TempEnv() as t:
            self.assertTrue(U.probe_due(t.cfg, SAT))
            t.write_usage([{"ts": iso(SAT - 29 * 60), "kind": "probe_failed"}])
            self.assertFalse(U.probe_due(t.cfg, SAT))
            self.assertTrue(U.probe_due(t.cfg, SAT + 61))

    def test_tick_does_not_probe_within_30_min(self):
        with TempEnv() as t:
            os.environ["CR_NOW"] = iso(SAT)
            t.write_usage([{"ts": iso(SAT - 20 * 60), "kind": "usage_screen", "observed": True,
                            "session_5h": {"used_pct": 10.0, "resets_at": "2026-10-17T23:30:00+03:00"},
                            "weekly_all_models": {"used_pct": 12.0, "resets_at": RESET}}])
            calls = []
            S.enqueue(t.cfg, "rebase", t.d, __file__)
            info = S.tick(t.cfg, prober=lambda cfg: calls.append(1) or "", procs=[], launcher=lambda c, j: 0, messages=[])
            self.assertEqual(calls, [])
            self.assertFalse(info["probed"])

    def test_usage_loop_cli_retired(self):  # bin/cr as a process, inside the sandbox
        with TempEnv():
            r = subprocess.run([sys.executable, os.path.join(ROOT, "bin", "cr"), "usage", "loop", "--interval", "20"],
                               capture_output=True, text=True, timeout=20)
        self.assertEqual(r.returncode, 2)
        self.assertIn("retired", r.stderr)


class EventsPrimaryTests(unittest.TestCase):
    def test_fresh_event_wins_over_newer_screen(self):
        with TempEnv() as t:
            t.write_usage([
                {"ts": iso(SAT - 300), "kind": "rate_limit_event", "status": "allowed",
                 "session_5h": {"used_pct": 14.0, "resets_at": "2026-10-17T23:30:00+03:00"},
                 "weekly_all_models": {"used_pct": 12.0, "resets_at": RESET}},
                {"ts": iso(SAT - 60), "kind": "usage_screen", "observed": True,
                 "session_5h": {"used_pct": 13.0, "resets_at": "2026-10-17T23:30:00+03:00"},
                 "weekly_all_models": {"used_pct": 11.0, "resets_at": RESET},
                 "weekly_fable": {"used_pct": 4.0, "resets_at": RESET}}])
            st = U.state(t.cfg, SAT, include_local=False)
            self.assertEqual((st["session"]["kind"], st["weekly"]["used_pct"]), ("rate_limit_event", 12.0))
            self.assertEqual(st["weekly_fable"]["used_pct"], 4.0)  # Fable only from /usage

    def test_stale_event_falls_back_to_newer_reading(self):
        with TempEnv() as t:
            t.write_usage([
                {"ts": iso(SAT - 3600), "kind": "rate_limit_event", "status": "allowed",
                 "weekly_all_models": {"used_pct": 12.0, "resets_at": RESET}},
                {"ts": iso(SAT - 60), "kind": "usage_screen", "observed": True,
                 "weekly_all_models": {"used_pct": 13.0, "resets_at": RESET}}])
            st = U.state(t.cfg, SAT, include_local=False)
            self.assertEqual((st["weekly"]["kind"], st["weekly"]["used_pct"]), ("usage_screen", 13.0))


class ProbeFailedFallbackTests(unittest.TestCase):
    def setUp(self):
        self.t = TempEnv().__enter__(); self.cfg = self.t.cfg
        self.wt = os.path.join(self.t.d, "wt"); os.makedirs(self.wt)
        self.pd = os.path.join(self.t.d, "prompts"); os.makedirs(self.pd)
        self.q = os.path.join(self.t.d, "queue.yaml")
        self.cfg["backlog"].update({"enabled": True, "queue": self.q, "state_file": os.path.join(self.t.d, "state.json"),
                                    "prompt_dir": self.pd, "require_soak_window": False})
        os.environ["CR_NOW"] = iso(SAT)  # backlog_tick re-checks quiet hours on the clock before each launch
        self.launched = []

    def tearDown(self):
        self.t.__exit__()

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
        return 4200000 + len(self.launched)

    def tick(self, e, now=SAT, alive=True):
        return S.backlog_tick(self.cfg, e, {"park": None, "local": None}, ZERO, 0, now, launcher=self.launcher,
                              procs_alive=lambda pid: alive)

    def test_probe_failed_uses_events(self):
        self.t.write_usage([{"ts": iso(SAT - 120), "kind": "rate_limit_event", "status": "allowed",
                             "session_5h": {"used_pct": 20.0, "resets_at": "2026-10-17T23:30:00+03:00"},
                             "weekly_all_models": {"used_pct": 9.0, "resets_at": RESET}},
                            {"ts": iso(SAT - 60), "kind": "probe_failed"}])
        e = U.effective(self.cfg, U.state(self.cfg, SAT, include_local=False), SAT)
        self.assertEqual((e["weekly"]["pct"], e["weekly"]["basis"]), (9.0, "observed"))

    def test_probe_failed_uses_estimates(self):
        self.t.write_usage([{"ts": iso(SAT - 60), "kind": "probe_failed"}])
        st = U.state(self.cfg, SAT, include_local=False)
        st["local"] = {"est_session_pct": 12.0, "est_weekly_pct": 9.0}
        e = U.effective(self.cfg, st, SAT)
        self.assertEqual((e["weekly"]["pct"], e["weekly"]["basis"]), (9.0, "estimate"))

    def test_no_reading_at_all_runs_under_near_cap(self):
        self.t.write_usage([{"ts": iso(SAT - 60), "kind": "probe_failed"}])
        e = U.effective(self.cfg, U.state(self.cfg, SAT, include_local=False), SAT)
        self.assertEqual((e["weekly"]["basis"], e["session"]["basis"]), ("none", "none"))
        e["weekly_fable"] = None
        self.write_queue([qjob(i) for i in range(6)])
        out = self.tick(e)
        near = self.cfg["backlog"]["weekly_pacing"]["all_models"]["near_cap"]
        self.assertEqual(len(self.launched), near, out)
        self.assertEqual(out["pacing"]["all_models"]["mode"], "no reading")


class QuietHoursTests(unittest.TestCase):
    def setUp(self):
        self.t = TempEnv().__enter__(); self.cfg = self.t.cfg
        self.wt = os.path.join(self.t.d, "wt"); os.makedirs(self.wt)
        self.pd = os.path.join(self.t.d, "prompts"); os.makedirs(self.pd)
        self.q = os.path.join(self.t.d, "queue.yaml")
        self.cfg["backlog"].update({"enabled": True, "queue": self.q, "state_file": os.path.join(self.t.d, "state.json"),
                                    "prompt_dir": self.pd, "require_soak_window": False})
        self.launched, self.alive = [], True
        with open(self.q, "w") as f:
            f.write("version: 1\njobs:\n" + "".join(qjob(i) for i in range(6)).replace("{WT}", self.wt))
        for i in range(6):
            with open(os.path.join(self.pd, "Q%02d.md" % i), "w") as f:
                f.write("do")

    def tearDown(self):
        self.t.__exit__()

    def launcher(self, cfg, spec):
        self.launched.append(spec)
        return 4300000 + len(self.launched)

    def tick(self, when):
        now = to_epoch(when)
        os.environ["CR_NOW"] = iso(now)  # the clock the per-launch quiet-hours check reads (TempEnv restores env)
        e = eff()
        e["weekly"]["resets_at"] = iso(now + 3 * 86400)
        e["weekly_fable"]["resets_at"] = e["weekly"]["resets_at"]
        return S.backlog_tick(self.cfg, e, {"park": None, "local": None}, ZERO, 0, now, launcher=self.launcher,
                              procs_alive=lambda pid: self.alive)

    def test_in_quiet_hours_bounds(self):
        q = lambda s: S.in_quiet_hours(self.cfg, to_epoch(s))
        self.assertFalse(q("2026-10-18T00:59:59+03:00"))
        self.assertTrue(q("2026-10-18T01:00:00+03:00"))
        self.assertTrue(q("2026-10-18T06:59:59+03:00"))
        self.assertFalse(q("2026-10-18T07:00:00+03:00"))
        self.assertTrue(q("2026-10-17T22:30:00Z"))   # 01:30 at UTC+3

    def test_quiet_hours_follow_dst(self):
        # A zone with daylight saving time (summer time ends on the first Sunday of November): the window follows local clock time.
        self.cfg["backlog"]["quiet_hours"]["tz"] = "America/New_York"
        q = lambda s: S.in_quiet_hours(self.cfg, to_epoch(s))
        self.assertTrue(q("2026-10-18T05:30:00Z"))   # 01:30 EDT (UTC-4)
        self.assertTrue(q("2026-11-10T06:30:00Z"))   # 01:30 EST (UTC-5)
        self.assertFalse(q("2026-11-10T05:59:00Z"))  # 00:59 EST (would be 01:59 EDT)
        self.assertTrue(q("2026-11-10T11:59:00Z"))   # 06:59 EST (would be 07:59 EDT)
        self.assertFalse(q("2026-11-10T12:00:00Z"))  # 07:00 EST

    def test_no_new_starts_in_quiet_hours(self):
        out = self.tick("2026-10-18T03:00:00+03:00")
        self.assertEqual(self.launched, [])
        self.assertIn("quiet hours", " ".join(out["held"]))

    def test_running_jobs_finish_and_are_reaped_in_quiet_hours(self):
        self.tick("2026-10-18T00:30:00+03:00")
        self.assertEqual(len(self.launched), 3)
        st = B.load_state(self.cfg)
        rid = st["Q00"]["run_id"]
        from crlib.common import append_jsonl, log_path
        append_jsonl(log_path(self.cfg, "runs.jsonl"), {"event": "finish", "run_id": rid, "rc": 0})
        out = self.tick("2026-10-18T02:00:00+03:00")  # Q01/Q02 alive: untouched; Q00 finished: reaped as done
        st = B.load_state(self.cfg)
        self.assertEqual(st["Q00"]["status"], "done")
        self.assertEqual((st["Q01"]["status"], st["Q02"]["status"]), ("running", "running"))
        self.assertEqual(len(self.launched), 3)  # no replacement start
        self.tick("2026-10-18T07:00:00+03:00")
        self.assertEqual(len(self.launched), 4)  # quiet hours over: the free slot fills

    def test_quiet_hours_beginning_during_a_tick_stop_launches(self):
        # The tick starts at 00:59; before each launch the clock is read again, and it already says 01:00.
        now = to_epoch("2026-10-18T00:59:00+03:00")
        e = eff()
        e["weekly"]["resets_at"] = e["weekly_fable"]["resets_at"] = iso(now + 3 * 86400)
        os.environ["CR_NOW"] = "2026-10-18T01:00:00+03:00"
        out = S.backlog_tick(self.cfg, e, {"park": None, "local": None}, ZERO, 0, now, launcher=self.launcher,
                             procs_alive=lambda pid: self.alive)
        self.assertEqual((self.launched, out.get("gate_stop")), ([], "quiet hours began"))

    def test_disabled_quiet_hours(self):
        self.cfg["backlog"]["quiet_hours"]["enabled"] = False
        self.tick("2026-10-18T03:00:00+03:00")
        self.assertEqual(len(self.launched), 3)


if __name__ == "__main__":
    unittest.main()
