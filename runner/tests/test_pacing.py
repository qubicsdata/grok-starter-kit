"""Weekly pacing (all-models + Fable-only), Fable routing/caps, Fable weekly reading, stack_on fast-forward."""
import json, os, subprocess, unittest
from helpers import TempEnv
from crlib import backlog as B, sched as S, usage as U, route as R
from crlib.common import to_epoch, iso

RESET = "2026-10-23T18:00:00+03:00"
SAT = to_epoch("2026-10-17T18:00:00+03:00")      # 24 h into the week
ZERO = {"total": 0, "opus": 0, "external": []}


def eff(w=9.0, fable=0.0, s=10, fable_basis="observed"):
    e = {"session": {"pct": s, "basis": "observed", "resets_at": "2026-10-17T18:20:00+03:00"},
         "weekly": {"pct": w, "basis": "observed", "resets_at": RESET}, "session_elapsed_min": 30}
    e["weekly_fable"] = None if fable is None else {"pct": fable, "basis": fable_basis, "resets_at": RESET, "age_min": 5.0}
    return e


def qjob(i, task_type="docs", extra=""):
    return ("  - id: Q%02d\n    title: job %d\n    priority: P1\n    task_type: %s\n    channel: direct\n"
            "    worktree: {WT}\n    status: queued\n%s" % (i, i, task_type, extra))


class PacingLineTests(unittest.TestCase):
    P = {"target_pct": 70, "target_hours_before_reset": 18, "final_pct": 75, "slack_pct": 2, "near_cap": 2}  # the example's all-models line

    def test_line_shape(self):
        ra = to_epoch(RESET)
        self.assertAlmostEqual(S.pacing_line(self.P, RESET, ra - 7 * 86400), 0.0)
        self.assertAlmostEqual(S.pacing_line(self.P, RESET, ra - 18 * 3600), 70.0)
        self.assertAlmostEqual(S.pacing_line(self.P, RESET, ra), 75.0)
        self.assertAlmostEqual(S.pacing_line(self.P, RESET, SAT), 70 * 24 / 150.0, places=3)
        self.assertEqual(S.pacing_line(self.P, RESET, ra - 9 * 3600), 72.5)
        self.assertIsNone(S.pacing_line(self.P, None, SAT))

    def test_cap_bands(self):
        line = S.pacing_line(self.P, RESET, SAT)  # 11.2
        self.assertEqual(S.pacing_cap(self.P, line - 1, RESET, SAT, 5)[0], 5)
        self.assertEqual(S.pacing_cap(self.P, line + 0.5, RESET, SAT, 5)[0], 2)
        self.assertEqual(S.pacing_cap(self.P, line + 2, RESET, SAT, 5)[0], 0)
        self.assertEqual(S.pacing_cap(self.P, None, RESET, SAT, 5)[1]["mode"], "no reading")
        self.assertEqual(S.pacing_cap(dict(self.P, park_pct=80), 80, RESET, to_epoch(RESET) - 60, 5)[0], 0)
        self.assertEqual(S.pacing_cap(dict(self.P, enabled=False), 99, RESET, SAT, 5)[0], 5)


class PacingTickTests(unittest.TestCase):
    def setUp(self):
        self.t = TempEnv().__enter__(); self.cfg = self.t.cfg
        self.wt = os.path.join(self.t.d, "wt"); os.makedirs(self.wt)
        self.pd = os.path.join(self.t.d, "prompts"); os.makedirs(self.pd)
        self.q = os.path.join(self.t.d, "queue.yaml")
        self.cfg["backlog"].update({"enabled": True, "queue": self.q, "state_file": os.path.join(self.t.d, "state.json"),
                                    "prompt_dir": self.pd, "require_soak_window": False})  # example caps: 3 own, Fable 2
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
                open(os.path.join(self.pd, jid + ".md"), "w").write("do " + jid)

    def launcher(self, cfg, spec):
        self.launched.append(spec)
        return 4100000 + len(self.launched)

    def tick(self, e, stack_runner=None):
        return S.backlog_tick(self.cfg, e, {"park": None, "local": None}, ZERO, 0, SAT, launcher=self.launcher,
                              procs_alive=lambda pid: True, stack_runner=stack_runner)

    def test_behind_line_full_caps(self):
        self.write_queue([qjob(i) for i in range(8)])
        out = self.tick(eff(w=9))
        self.assertEqual(len(self.launched), 3, out)
        self.assertEqual(out["pacing"]["all_models"]["mode"], "behind")

    def test_ahead_of_line_starts_nothing(self):
        self.write_queue([qjob(i) for i in range(8)])
        out = self.tick(eff(w=14))  # line 11.2, +2.8
        self.assertEqual(self.launched, [])
        self.assertIn("weekly pacing ahead", json.dumps(out["decide"]["held"]))

    def test_near_line_caps_at_near_cap(self):
        self.write_queue([qjob(i) for i in range(8)])
        self.tick(eff(w=12))  # line 11.2, +0.8 -> near_cap 2
        self.assertEqual(len(self.launched), 2)

    def test_fable_route_and_family(self):
        r = R.route(self.cfg, task_type="fable-pre-review")
        self.assertEqual((r["model"], r["fallback_model"]), ("fable", "opus"))
        self.assertEqual(S.job_family(self.cfg, {"task_type": "fable-implement", "model": None}), "fable")
        self.assertIn("--model", R.claude_args(r))

    def test_fable_capped_separately(self):
        self.write_queue([qjob(i, "fable-implement") for i in range(5)] + [qjob(10 + i) for i in range(2)])
        self.tick(eff(w=9, fable=0))
        fams = [S.job_family(self.cfg, {"task_type": s["task_type"], "model": s.get("model")}) for s in self.launched]
        self.assertEqual((fams.count("fable"), len(fams)), (2, 3))  # fable max_concurrent 2, own cap 3

    def test_fable_ahead_or_parked_holds_only_fable(self):
        self.write_queue([qjob(i, "fable-security") for i in range(3)] + [qjob(10)])
        out = self.tick(eff(w=9, fable=20))  # Fable line at Sat 18:00 = 75*24/168 = 10.7
        self.assertEqual([s["task_type"] for s in self.launched], ["docs"], out)
        self.assertIn("Fable pacing ahead", json.dumps(out["decide"]["held"]))

    def test_fable_without_reading_is_conservative(self):
        self.write_queue([qjob(i, "fable-security") for i in range(3)])
        self.tick(eff(w=9, fable=None))
        self.assertEqual(len(self.launched), 0)  # Fable age rule: no reading -> no new Fable starts

    def test_stack_on_ff_before_launch_and_failure_marks_failed(self):
        calls = []

        def ok_runner(a):
            calls.append(a)
            return subprocess.CompletedProcess(a, 0, stdout="abc123def4567\n", stderr="")
        self.write_queue([qjob(1, extra="    stack_on: example/parent-branch\n")])
        out = self.tick(eff(), stack_runner=ok_runner)
        self.assertEqual(len(self.launched), 1)
        self.assertIn(["git", "-C", self.wt, "merge", "--ff-only", "--quiet", "example/parent-branch"], calls)

        def bad_runner(a):
            rc = 1 if "merge" in a else 0
            return subprocess.CompletedProcess(a, rc, stdout="", stderr="fatal: Not possible to fast-forward")
        self.write_queue([qjob(2, extra="    stack_on: example/parent-branch\n")])
        out = self.tick(eff(), stack_runner=bad_runner)
        self.assertEqual(len(self.launched), 1)
        st = B.load_state(self.cfg)
        self.assertEqual(st["Q02"]["status"], "failed")
        self.assertIn("fast-forward", st["Q02"]["why"])

    def test_stack_ff_real_git(self):
        d = os.path.join(self.t.d, "repo")
        g = lambda *a: subprocess.run(["git", "-C", d] + list(a), check=True, capture_output=True, text=True)
        os.makedirs(d)
        g("init", "-q", "-b", "main"); g("config", "user.email", "t@example.com"); g("config", "user.name", "t")
        open(os.path.join(d, "a"), "w").write("1"); g("add", "a"); g("commit", "-qm", "a")
        g("branch", "child"); open(os.path.join(d, "a"), "w").write("2"); g("commit", "-qam", "b")
        wt = os.path.join(self.t.d, "childwt"); g("worktree", "add", "-q", wt, "child")
        ok, msg = B.stack_ff(wt, "main")
        self.assertTrue(ok, msg)
        self.assertEqual(open(os.path.join(wt, "a")).read(), "2")
        self.assertFalse(B.stack_ff(wt, "--upload-pack=x")[0])
        self.assertFalse(B.stack_ff(wt, "nope")[0])

    def test_priority_p0_first(self):
        self.cfg["backlog"]["max_concurrent"] = 1
        self.write_queue([qjob(1), qjob(2).replace("priority: P1", "priority: P0")])
        self.tick(eff())
        self.assertEqual(self.launched[0]["label"], "bl-Q02")


class FableUsageTests(unittest.TestCase):
    def test_weekly_fable_reading_in_state_and_effective(self):
        with TempEnv() as t:
            now = SAT
            t.write_usage([{"ts": iso(now - 300), "kind": "usage_screen", "observed": True,
                            "session_5h": {"used_pct": 33.0, "resets_at": "2026-10-17T18:20:00+03:00"},
                            "weekly_all_models": {"used_pct": 9.0, "resets_at": RESET},
                            "weekly_fable": {"used_pct": 4.0, "resets_at": RESET}}])
            st = U.state(t.cfg, now, include_local=False)
            e = U.effective(t.cfg, st, now)
            self.assertEqual((e["weekly_fable"]["pct"], e["weekly_fable"]["basis"]), (4.0, "observed"))
            self.assertEqual(U.parse_usage_screen("Current week (Fable only): 4% used · resets Oct 23, 6pm", now)
                             ["weekly_fable"]["used_pct"], 4.0)

    def test_no_fable_reading(self):
        with TempEnv() as t:
            st = U.state(t.cfg, SAT, include_local=False)
            self.assertIsNone(U.effective(t.cfg, st, SAT)["weekly_fable"])


if __name__ == "__main__":
    unittest.main()
