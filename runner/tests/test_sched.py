import json, os, time, unittest
from helpers import TempEnv, FIX, FAKEBIN, ROOT, BIN
from crlib import sched as S
from crlib.common import to_epoch, iso


def eff(s=10, w=10, elapsed=30, sres="2026-10-15T22:00:00+03:00", wres="2026-10-20T18:00:00+03:00"):
    return {"session": {"pct": s, "basis": "observed", "resets_at": sres},
            "weekly": {"pct": w, "basis": "observed", "resets_at": wres}, "session_elapsed_min": elapsed}


def job(i, tt="implement", crit=False, prio=0, heavy=False):
    return {"id": "j%02d" % i, "task_type": tt, "critical": crit, "priority": prio, "heavy": heavy,
            "created": "2026-10-15T10:%02d:00" % i}


ZERO = {"total": 0, "opus": 0, "external": []}


class DecideTests(unittest.TestCase):
    def setUp(self):
        self.t = TempEnv().__enter__(); self.cfg = self.t.cfg

    def tearDown(self):
        self.t.__exit__()

    def d(self, e, pending, counts=ZERO):
        return S.decide(self.cfg, e, None, pending, counts, 0)

    def test_opus_cap_3_total_cap_4(self):  # safe limits: total 4, Opus 3
        start, info = self.d(eff(), [job(i) for i in range(8)] + [job(20, "rebase")])
        fams = [S.job_family(self.cfg, j) for j in start]
        self.assertEqual((fams.count("opus"), len(start)), (3, 4))
        self.assertEqual(info["mode"], "normal")

    def test_external_claude_counted(self):
        counts = {"total": 2, "opus": 2, "external": []}
        start, _ = self.d(eff(), [job(i) for i in range(5)] + [job(20, "rename")], counts)
        self.assertEqual(len(start), 2)  # 1 more opus (cap 3) + 1 sonnet (total 4)
        self.assertEqual(self.d(eff(), [job(1)], {"total": 4, "opus": 1, "external": []})[0], [])
        procs = [(999991, 1, None), (999992, 1, "sonnet")]
        c = S.running_counts(self.cfg, [], procs)
        self.assertEqual((c["total"], c["opus"]), (2, 1))

    def test_session_80_pauses_noncritical(self):  # session pause at 80%
        start, info = self.d(eff(s=80), [job(1), job(2, crit=True), job(3, "rebase")])
        self.assertEqual([j["id"] for j in start], ["j02"])
        self.assertEqual(info["mode"], "restricted")
        self.assertEqual(self.d(eff(s=79), [job(1)])[1]["mode"], "normal")

    def test_session_90_stops_all_until_reset(self):
        start, info = self.d(eff(s=90), [job(1, crit=True)])
        self.assertEqual((start, info["mode"], info["resume_at"]), ([], "stopped", "2026-10-15T22:00:00+03:00"))

    def test_weekly_68_cap3_noncritical_only_after_reset(self):  # restricted at 68%
        pend = [job(i) for i in range(5)] + [job(9, crit=True)]
        late, info = self.d(eff(w=70, elapsed=120), pend)
        self.assertEqual([j["id"] for j in late], ["j09"])
        early, info = self.d(eff(w=70, elapsed=20), pend)
        self.assertEqual(len(early), 3)
        self.assertEqual(early[0]["id"], "j09")

    def test_weekly_75_critical_only_cap1(self):
        start, _ = self.d(eff(w=76), [job(1, crit=True), job(2, crit=True), job(3)])  # 75-80: critical only
        self.assertEqual([j["id"] for j in start], ["j01"])

    def test_weekly_80_nothing(self):
        start, info = self.d(eff(w=80), [job(1, crit=True)])  # stop_new_pct 80
        self.assertEqual((start, info["mode"]), ([], "stopped"))

    def test_thresholds_come_from_config(self):
        self.cfg["policy"]["session"]["stop_new_pct"] = 50
        start, _ = self.d(eff(s=55), [job(1, crit=True)])
        self.assertEqual(start, [])

    def test_heavy_waits_for_reset(self):
        pend = [job(1, heavy=True), job(2)]
        self.assertEqual([j["id"] for j in self.d(eff(elapsed=200), pend)[0]], ["j02"])
        self.assertEqual(len(self.d(eff(elapsed=5), pend)[0]), 2)
        self.assertEqual(len(self.d(eff(elapsed=0), pend)[0]), 2)  # no active window

    def test_order_critical_then_priority_then_window_position(self):
        pend = [job(1, "rebase"), job(2, "implement"), job(3, "rebase", prio=5), job(4, "security", crit=True)]
        early = [j["id"] for j in self.d(eff(elapsed=10), pend, {"total": 1, "opus": 0, "external": []})[0]]  # 3 slots left (cap 4)
        self.assertEqual(early, ["j04", "j03", "j02"])
        late = [j["id"] for j in self.d(eff(elapsed=250), pend, {"total": 1, "opus": 0, "external": []})[0]]
        self.assertEqual(late, ["j04", "j03", "j01"])

    def test_park_overrides_everything(self):
        park = {"active": True, "resume_at": "2026-10-15T17:50:00+03:00", "source": "rate_limit_event status=rejected"}
        start, info = S.decide(self.cfg, eff(s=1, w=1), park, [job(1, crit=True)], ZERO, 0)
        self.assertEqual((start, info["mode"], info["resume_at"]), ([], "parked", "2026-10-15T17:50:00+03:00"))


class TickTests(unittest.TestCase):
    """Queue + tick: park on a simulated rate-limit event, resume after the reset."""
    def setUp(self):
        self.t = TempEnv().__enter__(); self.cfg = self.t.cfg
        self.cwd = self.t.d
        self.prompt = os.path.join(self.t.d, "p.md")
        with open(self.prompt, "w") as f:
            f.write("x")
        self.launched = []

    def tearDown(self):
        self.t.__exit__()

    def launcher(self, cfg, j):
        self.launched.append(j["id"])
        return 0  # pid 0 = not a real process

    def screen(self, cfg):
        with open(os.path.join(FIX, "usage_screen_synthetic_1744.txt")) as f:
            return f.read()

    def test_park_then_resume(self):
        os.environ["CR_NOW"] = "2026-10-15T17:30:00+03:00"
        a = S.enqueue(self.cfg, "rebase", self.cwd, self.prompt, critical=True)
        b = S.enqueue(self.cfg, "implement", self.cwd, self.prompt)
        self.t.write_usage([{"ts": "2026-10-15T17:29:00+03:00", "kind": "rate_limit_event", "status": "rejected",
                             "rate_limit_type": "five_hour", "resets_at": "2026-10-15T17:50:00+03:00",
                             "session_5h": {"used_pct": 100, "resets_at": "2026-10-15T17:50:00+03:00"},
                             "weekly_all_models": {"used_pct": 30, "resets_at": "2026-10-16T18:00:00+03:00"}}])
        info = S.tick(self.cfg, prober=self.screen, procs=[], launcher=self.launcher, messages=[])
        self.assertEqual((info["mode"], info["resume_at"], self.launched), ("parked", "2026-10-15T17:50:00+03:00", []))
        self.assertEqual(len(S.list_jobs(self.cfg, "pending")), 2)
        os.environ["CR_NOW"] = "2026-10-15T17:50:30+03:00"  # inside the grace period: still parked
        self.assertEqual(S.tick(self.cfg, probe=False, procs=[], launcher=self.launcher, messages=[])["mode"], "parked")
        os.environ["CR_NOW"] = "2026-10-15T17:52:00+03:00"
        fresh = lambda cfg: "Current session\n 1% used\n Resets 10:52pm\nCurrent week (all models)\n 30% used\n Resets Oct 16, 6pm\n"
        info = S.tick(self.cfg, prober=fresh, procs=[], launcher=self.launcher, messages=[])
        self.assertTrue(info["probed"])
        self.assertEqual(info["mode"], "normal")
        self.assertEqual(self.launched, [a["id"], b["id"]])  # critical first
        self.assertEqual(len(S.list_jobs(self.cfg, "running")), 2)
        sched_log = self.t.read("scheduler.jsonl")
        self.assertEqual([r["mode"] for r in sched_log], ["parked", "normal"])  # unchanged tick not re-logged

    def test_running_jobs_not_touched_when_parked(self):
        os.environ["CR_NOW"] = "2026-10-15T17:30:00+03:00"
        j = S.enqueue(self.cfg, "rebase", self.cwd, self.prompt)
        S.tick(self.cfg, probe=False, procs=[], launcher=self.launcher, messages=[])
        self.t.write_usage([{"ts": "2026-10-15T17:31:00+03:00", "kind": "rate_limit_event", "status": "rejected",
                             "resets_at": "2026-10-15T17:50:00+03:00"}])
        running = S.list_jobs(self.cfg, "running")
        running[0]["pid"] = os.getpid()  # a live pid: must be left alone
        S._write(os.path.join(S.qdir(self.cfg, "running"), j["id"] + ".json"), running[0])
        info = S.tick(self.cfg, probe=False, procs=[], launcher=self.launcher, messages=[])
        self.assertEqual(info["mode"], "parked")
        self.assertEqual(len(S.list_jobs(self.cfg, "running")), 1)

    def test_end_to_end_with_runner_and_fake_claude(self):  # run-claude.sh as a process, inside the sandbox
        os.environ.update({"CR_RUNNER": os.path.join(BIN, "run-claude.sh"), "CLAUDE_BIN": os.path.join(FAKEBIN, "claude"),
                           "CLAUDE_RUN_LOG_DIR": self.t.logs, "CLAUDE_ROUTER_DIR": ROOT})
        os.environ.pop("ANTHROPIC_API_KEY", None)
        from crlib import common
        cfg = common.load_config()
        cfg["runner"]["enabled"] = True  # launch() refuses while the runner is off (the example ships it off)
        j = S.enqueue(cfg, "pr-body", self.cwd, self.prompt, label="e2e")
        info = S.tick(cfg, probe=False, procs=[], messages=[])
        self.assertEqual(info["started"], [j["id"]])
        for _ in range(100):
            S.tick(cfg, probe=False, procs=[], messages=[])
            if S.list_jobs(cfg, "done") or S.list_jobs(cfg, "failed"):
                break
            time.sleep(0.2)
        done = S.list_jobs(cfg, "done")
        self.assertEqual([d["id"] for d in done], [j["id"]])
        self.assertEqual(done[0]["finish"]["models_reported"], ["claude-sonnet-5-5"])
        starts = [r for r in self.t.read("runs.jsonl") if r["event"] == "start"]
        self.assertEqual((starts[0]["run_id"], starts[0]["model"], starts[0]["task_type"]), (j["id"], "sonnet", "pr-body"))


if __name__ == "__main__":
    unittest.main()
