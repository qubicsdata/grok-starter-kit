"""Fable reading age rule + near-park re-probe. Fake probes only: real `claude` never runs here
(helpers sets CR_TEST_NO_REAL_CLAUDE=1, and probe_print/launch refuse to start the real binary under it)."""
import json, os, unittest
from helpers import TempEnv
from crlib import backlog as B, sched as S, usage as U
from crlib.common import iso, to_epoch

RESET = "2026-10-23T18:00:00+03:00"
SAT = to_epoch("2026-10-17T18:00:00+03:00")
NEAR_RESET = to_epoch(RESET) - 60   # Fable pacing line ~75%: 75-76% is "near", not "ahead"
ZERO = {"total": 0, "opus": 0, "external": []}


def eff(fable=5.0, age=5.0, probe_failed=False):
    e = {"session": {"pct": 10, "basis": "observed", "resets_at": "2026-10-17T23:30:00+03:00"},
         "weekly": {"pct": 9.0, "basis": "observed", "resets_at": RESET}, "session_elapsed_min": 30,
         "probe_failed": probe_failed}
    e["weekly_fable"] = None if fable is None else {"pct": fable, "basis": "observed", "resets_at": RESET, "age_min": age}
    return e


def qjob(i, task_type="fable-security"):
    return ("  - id: Q%02d\n    title: job %d\n    priority: P1\n    task_type: %s\n    channel: direct\n"
            "    worktree: {WT}\n    status: queued\n" % (i, i, task_type))


def screen(fable):
    return ("Current session: 10% used · resets Oct 17, 11:30pm (Etc/GMT-3)\n"
            "Current week (all models): 9% used · resets Oct 23, 6pm (Etc/GMT-3)\n"
            "Current week (Fable only): FABLE% used · resets Oct 23, 6pm (Etc/GMT-3)\n").replace("FABLE", str(fable))


class Base(unittest.TestCase):
    def setUp(self):
        self.t = TempEnv().__enter__(); self.cfg = self.t.cfg
        self.wt = os.path.join(self.t.d, "wt"); os.makedirs(self.wt)
        self.pd = os.path.join(self.t.d, "prompts"); os.makedirs(self.pd)
        self.q = os.path.join(self.t.d, "queue.yaml")
        self.cfg["backlog"].update({"enabled": True, "queue": self.q, "state_file": os.path.join(self.t.d, "state.json"),
                                    "prompt_dir": self.pd, "require_soak_window": False})
        os.environ["CR_NOW"] = iso(SAT)  # backlog_tick re-checks quiet hours on the clock before each launch
        self.launched, self.probes = [], []

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
        return 4400000 + len(self.launched)

    def fable_launched(self):
        return sum(S.job_family(self.cfg, {"task_type": s["task_type"], "model": s.get("model")}) == "fable" for s in self.launched)

    def tick(self, e, now=SAT, prober=None):
        return S.backlog_tick(self.cfg, e, {"park": None, "local": None}, ZERO, 0, now, launcher=self.launcher,
                              procs_alive=lambda pid: True, prober=prober)


class AgeRuleConfigTests(Base):
    def test_config_keys(self):
        f = self.cfg["backlog"]["weekly_pacing"]["fable"]
        self.assertEqual((f["fresh_minutes"], f["stale_near_cap_minutes"], f["stale_block_minutes"], f["near_park_pct"],
                          f["park_pct"]), (30, 45, 90, 75, 80))
        self.assertEqual(self.cfg["usage"]["near_park_min_probe_spacing_minutes"], 5)
        self.assertEqual(self.cfg["usage"]["min_probe_spacing_minutes"], 30)


class AgeBoundaryTests(Base):
    def cap(self, **kw):
        return S.fable_age_cap(self.cfg, eff(**kw), 2)

    def test_pure_boundaries(self):
        self.assertEqual(self.cap(age=0)[0], 2)
        self.assertEqual(self.cap(age=30)[0], 2)
        self.assertEqual(self.cap(age=30.1)[0], 2)    # 30-45: normal caps (the rule names no band here)
        self.assertEqual(self.cap(age=45)[0], 2)
        self.assertEqual(self.cap(age=45.1)[0], 1)
        self.assertEqual(self.cap(age=90)[0], 1)
        self.assertEqual(self.cap(age=90.1)[0], 0)

    def test_probe_failed_and_missing(self):
        self.assertEqual(self.cap(age=1, probe_failed=True)[:2], (0, "probe failed"))
        self.assertEqual(self.cap(fable=None)[:2], (0, "no reading"))
        e = eff(); del e["weekly_fable"]["age_min"]
        self.assertEqual(S.fable_age_cap(self.cfg, e, 2)[0], 0)  # unknown age: treated as no usable reading

    def test_tick_boundaries(self):
        for age, want in ((30, 2), (45, 2), (45.1, 1), (90, 1), (90.1, 0)):
            self.launched = []
            self.cfg["backlog"]["state_file"] = os.path.join(self.t.d, "state-%s.json" % age)
            self.write_queue([qjob(i) for i in range(4)] + [qjob(10, "docs")])
            out = self.tick(eff(age=age))
            self.assertEqual(self.fable_launched(), want, (age, out.get("pacing")))
            self.assertEqual(len(self.launched) - want, 1)  # non-Fable work is unaffected

    def test_tick_probe_failed_or_missing_blocks_fable_only(self):
        for e in (eff(probe_failed=True), eff(fable=None)):
            self.launched = []
            self.cfg["backlog"]["state_file"] = os.path.join(self.t.d, "st-%d.json" % id(e))
            self.write_queue([qjob(i) for i in range(3)] + [qjob(10, "docs")])
            out = self.tick(e)
            self.assertEqual((self.fable_launched(), len(self.launched)), (0, 1))
            self.assertIn("Fable reading", json.dumps(out["decide"]["held"]))

    def test_effective_reports_probe_failed(self):
        self.t.write_usage([{"ts": iso(SAT - 600), "kind": "usage_screen", "observed": True,
                             "weekly_fable": {"used_pct": 5.0, "resets_at": RESET}},
                            {"ts": iso(SAT - 60), "kind": "probe_failed"}])
        e = U.effective(self.cfg, U.state(self.cfg, SAT, include_local=False), SAT)
        self.assertTrue(e["probe_failed"])
        self.t.write_usage([{"ts": iso(SAT - 30), "kind": "usage_screen", "observed": True,
                             "weekly_fable": {"used_pct": 5.0, "resets_at": RESET}}])
        e = U.effective(self.cfg, U.state(self.cfg, SAT, include_local=False), SAT)
        self.assertFalse(e["probe_failed"])


class NearParkReprobeTests(Base):
    def prober(self, fable):
        def p(cfg):
            self.probes.append(fable)
            return screen(fable)
        return p

    def test_reprobe_at_75_and_above(self):
        self.write_queue([qjob(0)])
        self.t.write_usage([{"ts": iso(NEAR_RESET - 10 * 60), "kind": "usage_screen", "observed": True,
                             "weekly_fable": {"used_pct": 75.0, "resets_at": RESET}}])
        out = self.tick(eff(fable=75.0, age=10), now=NEAR_RESET, prober=self.prober(75))
        self.assertEqual(self.probes, [75])
        self.assertEqual(self.fable_launched(), 1, out)

    def test_no_reprobe_below_75(self):
        self.write_queue([qjob(0)])
        self.t.write_usage([{"ts": iso(NEAR_RESET - 10 * 60), "kind": "usage_screen", "observed": True,
                             "weekly_fable": {"used_pct": 74.0, "resets_at": RESET}}])
        self.tick(eff(fable=74.9, age=10), now=NEAR_RESET, prober=self.prober(74))
        self.assertEqual(self.probes, [])
        self.assertEqual(self.fable_launched(), 1)

    def test_reprobe_reaching_park_blocks_launch(self):
        self.write_queue([qjob(0), qjob(10, "docs")])
        self.t.write_usage([{"ts": iso(NEAR_RESET - 10 * 60), "kind": "usage_screen", "observed": True,
                             "weekly_fable": {"used_pct": 76.0, "resets_at": RESET}}])
        out = self.tick(eff(fable=76.0, age=10), now=NEAR_RESET, prober=self.prober(80))
        self.assertEqual(self.probes, [80])
        self.assertEqual((self.fable_launched(), len(self.launched)), (0, 1))
        self.assertIn("park", json.dumps(out["fable_reprobe"]))

    def test_reprobe_failure_blocks_launch(self):
        self.write_queue([qjob(0)])
        self.t.write_usage([{"ts": iso(NEAR_RESET - 10 * 60), "kind": "usage_screen", "observed": True,
                             "weekly_fable": {"used_pct": 76.0, "resets_at": RESET}}])
        out = self.tick(eff(fable=76.0, age=10), now=NEAR_RESET, prober=lambda cfg: self.probes.append("x") or "")
        self.assertEqual((self.probes, self.fable_launched()), (["x"], 0))
        self.assertIn("probe failed", json.dumps(out["fable_reprobe"]))

    def test_near_park_spacing_5_min(self):
        self.write_queue([qjob(0)])
        self.t.write_usage([{"ts": iso(NEAR_RESET - 4 * 60), "kind": "usage_screen", "observed": True,
                             "weekly_fable": {"used_pct": 76.0, "resets_at": RESET}}])
        self.tick(eff(fable=76.0, age=4), now=NEAR_RESET, prober=self.prober(76))
        self.assertEqual(self.probes, [])          # last probe 4 min ago: within the 5-min near-park spacing
        self.assertEqual(self.fable_launched(), 1)  # ... so the 4-min-old reading is used
        self.assertFalse(U.probe_due(self.cfg, NEAR_RESET, spacing_minutes=5))
        self.assertTrue(U.probe_due(self.cfg, NEAR_RESET + 61, spacing_minutes=5))

    def test_reprobe_before_each_fable_launch(self):
        self.write_queue([qjob(0), qjob(1)])
        self.t.write_usage([{"ts": iso(NEAR_RESET - 10 * 60), "kind": "usage_screen", "observed": True,
                             "weekly_fable": {"used_pct": 75.0, "resets_at": RESET}}])
        self.cfg["backlog"]["weekly_pacing"]["fable"]["near_cap"] = 2
        self.tick(eff(fable=75.0, age=10), now=NEAR_RESET, prober=self.prober(75))
        self.assertEqual(self.probes, [75])  # 2nd launch: the 1st re-probe is < 5 min old, so not repeated
        self.assertEqual(self.fable_launched(), 2)

    def test_dry_run_never_probes(self):
        self.write_queue([qjob(0)])
        out = S.backlog_tick(self.cfg, eff(fable=76.0, age=10), {"park": None, "local": None}, ZERO, 0, NEAR_RESET,
                             dry_run=True, launcher=self.launcher, procs_alive=lambda pid: True, prober=self.prober(76))
        self.assertEqual(self.probes, [])


class CadenceTests(Base):
    def test_30_min_cadence_elsewhere(self):
        self.t.write_usage([{"ts": iso(SAT - 29 * 60), "kind": "usage_screen", "observed": True,
                             "weekly_fable": {"used_pct": 20.0, "resets_at": RESET}}])
        self.assertFalse(U.probe_due(self.cfg, SAT))
        self.assertTrue(U.probe_due(self.cfg, SAT + 61))
        self.assertFalse(U.probe_due(self.cfg, SAT - 20 * 60 + 1, spacing_minutes=30))
        self.write_queue([qjob(0)])
        calls = []
        self.tick(eff(fable=20.0, age=29), prober=lambda cfg: calls.append(1) or screen(20))
        self.assertEqual(calls, [])  # below 75%: no per-launch re-probe


class NoRealClaudeGuardTests(unittest.TestCase):
    def test_guard_set_and_enforced(self):
        self.assertEqual(os.environ.get("CR_TEST_NO_REAL_CLAUDE"), "1")
        with TempEnv() as t:
            with self.assertRaises(RuntimeError):
                U.probe_print(t.cfg)
            with self.assertRaises(RuntimeError):
                U.poll(t.cfg, now=SAT)  # default prober = real claude -p /usage -> refused
            with self.assertRaises(RuntimeError):
                os.environ.pop("CLAUDE_BIN", None)
                S.launch(t.cfg, {"id": "x", "task_type": "docs", "label": "x", "cwd": t.d, "prompt_file": __file__})


if __name__ == "__main__":
    unittest.main()
