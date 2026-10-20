import json, os, unittest
from helpers import TempEnv, FIX
from crlib import backlog as B, sched as S
from crlib.common import iso, to_epoch


def eff(s=10, w=30, wres="2026-10-16T18:00:00+03:00", elapsed=30):
    return {"session": {"pct": s, "basis": "observed", "resets_at": "2026-10-15T22:50:00+03:00"},
            "weekly": {"pct": w, "basis": "observed", "resets_at": wres}, "session_elapsed_min": elapsed}


NOW = to_epoch("2026-10-15T18:10:00+03:00")
ZERO = {"total": 0, "opus": 0, "external": []}


class BacklogTests(unittest.TestCase):
    def setUp(self):
        self.t = TempEnv().__enter__(); self.cfg = self.t.cfg
        self.wt = os.path.join(self.t.d, "wt"); os.makedirs(self.wt)
        pd = os.path.join(self.t.d, "prompts"); os.makedirs(pd)
        for j in ("X1", "X2", "X4", "X5", "X6", "X7"):
            with open(os.path.join(pd, j + ".md"), "w") as f:
                f.write("do %s" % j)
        q = os.path.join(self.t.d, "queue.yaml")
        with open(os.path.join(FIX, "backlog_queue.yaml")) as f, open(q, "w") as g:
            g.write(f.read().replace("{WT}", self.wt))
        self.cfg["backlog"].update({"enabled": True, "queue": q, "state_file": os.path.join(self.t.d, "state.json"), "prompt_dir": pd})
        os.environ["CR_NOW"] = iso(NOW)  # backlog_tick re-checks quiet hours on the clock before each launch
        self.launched = []
        self.alive = True

    def tearDown(self):
        self.t.__exit__()

    def launcher(self, cfg, spec):
        self.launched.append(spec)
        return 4999999

    def tick(self, e=None, counts=ZERO, queue_waiting=0, st=None):
        return S.backlog_tick(self.cfg, e or eff(), st or {"park": None, "local": None}, counts, queue_waiting, NOW,
                              launcher=self.launcher, procs_alive=lambda pid: self.alive)

    def test_parse_large_queue_read_only(self):
        # A synthetic 13-job queue in the shape of a live one (comments, quoting, lists, triggers, groups, stacking).
        p = os.path.join(FIX, "backlog_queue_large.yaml")
        before = os.stat(p).st_mtime
        with open(p) as f:
            doc = B.parse_queue_yaml(f.read())
        ids = [j["id"] for j in doc["jobs"]]
        self.assertEqual(ids[0], "B01")
        self.assertIn("B13", ids)
        b04 = [j for j in doc["jobs"] if j["id"] == "B04"][0]
        self.assertEqual((b04["depends_on"], b04["priority"], b04["model"]), (["B01"], "P1", "opus"))
        self.assertEqual(os.stat(p).st_mtime, before)

    def test_parse_fixture(self):
        with open(self.cfg["backlog"]["queue"]) as f:
            doc = B.parse_queue_yaml(f.read())
        self.assertEqual(doc["jobs"][0]["title"], "P2 docs job # not a comment")
        self.assertEqual(doc["jobs"][3]["depends_on"], ["X2"])

    def test_eligibility_and_p1_first(self):
        with open(self.cfg["backlog"]["queue"]) as f:
            doc = B.parse_queue_yaml(f.read())
        el, skipped = B.eligible(self.cfg, doc, {})
        self.assertEqual([j["id"] for j in el], ["X2", "X1"])
        why = {s["id"]: s["why"] for s in skipped}
        self.assertIn("channel script", why["X3"])
        self.assertIn("depends_on", why["X4"])
        self.assertIn("P3", why["X5"])
        self.assertIn("worktree not prepared", why["X6"])
        self.assertIn("blocked", why["X7"])

    def test_dispatch_with_guard_and_state(self):
        out = self.tick()
        self.assertEqual(out["started"], ["X2", "X1"])
        self.assertEqual([s["model"] for s in self.launched], ["opus", "sonnet"])
        self.assertEqual(self.launched[1]["task_type"], "docs")  # alias analysis/docs -> docs
        self.assertEqual(self.launched[0]["effort"], "high")
        with open(self.launched[0]["prompt_file"]) as f:
            body = f.read()
        self.assertTrue(body.startswith("BACKLOG JOB (local only): never git push"))
        self.assertTrue(body.endswith("do X2"))
        st = B.load_state(self.cfg)
        self.assertEqual(st["X2"]["status"], "running")
        with open(self.cfg["backlog"]["queue"]) as f:
            self.assertIn("status: queued", f.read())  # queue.yaml untouched
        again = self.tick()
        self.assertEqual(again.get("started", []), [])  # running jobs are not re-dispatched
        # finish X2 -> done -> X4 becomes eligible
        from crlib.common import append_jsonl, log_path
        append_jsonl(log_path(self.cfg, "runs.jsonl"), {"event": "finish", "run_id": st["X2"]["run_id"], "rc": 0})
        append_jsonl(log_path(self.cfg, "runs.jsonl"), {"event": "finish", "run_id": st["X1"]["run_id"], "rc": 0})
        self.alive = False
        out = self.tick()
        self.assertEqual(B.load_state(self.cfg)["X2"]["status"], "done")
        self.assertEqual(out["started"], ["X4"])

    def test_dead_without_finish_is_failed(self):
        self.cfg["backlog"]["max_attempts"] = 1  # no crash retry (the example retries once; see test_queue_runner)
        self.tick()
        self.alive = False
        self.tick(queue_waiting=1)
        self.assertEqual(B.load_state(self.cfg)["X2"]["status"], "failed")

    def test_holds(self):
        self.assertIn("the main queue goes first", " ".join(self.tick(queue_waiting=1)["held"]))
        self.assertIn("session", " ".join(self.tick(eff(s=80))["held"]))  # backlog.session_max_pct 80
        self.assertIn("weekly", " ".join(self.tick(eff(w=90))["held"]))
        self.cfg["backlog"]["require_soak_window"] = True  # off in the example; the gate still works
        self.assertIn("soak", " ".join(self.tick(eff(wres="2026-10-18T18:00:00+03:00"))["held"]))
        self.assertIn("park", " ".join(self.tick(st={"park": {"active": True}, "local": None})["held"]))
        self.assertEqual(self.launched, [])

    def test_projection_closes_window(self):
        self.cfg["backlog"]["require_soak_window"] = True
        st = {"park": None, "local": {"weighted_lookback": 3_000_000, "budget_weekly_weighted": 100_000_000}}
        out = self.tick(st=st)  # 1%/h x ~23.8 h + 30% = ~54% -> open
        self.assertTrue(out["soak"])
        st["local"]["weighted_lookback"] = 9_000_000  # 3%/h -> ~101% -> closed
        out = self.tick(st=st)
        self.assertFalse(out["soak"])
        self.assertEqual(self.launched[0]["model"], "opus")  # only the first tick launched

    def test_reserve_slot_and_caps(self):
        out = self.tick(counts={"total": 4, "opus": 2, "external": []})  # total cap 4 incl. external -> nothing
        self.assertEqual(out.get("started"), [])
        out = self.tick(e=eff(w=70, elapsed=120), counts=ZERO)  # weekly 68-75: non-critical only right after reset
        self.assertEqual(out.get("started"), [])
        self.assertEqual(self.launched, [])


if __name__ == "__main__":
    unittest.main()
