"""Queue runner (cr sched loop) gaps: concurrency with a slot and Opus reserve, per-launch usage gate, route-picked model,
crash retry, local commit on done, pidfile/stop file/SIGTERM. Never touches running claude processes."""
import json, os, signal, subprocess, sys, tempfile, time, unittest
from helpers import TempEnv, FIX, ROOT
from crlib import backlog as B, sched as S
from crlib.common import append_jsonl, iso, log_path, to_epoch

NOW = to_epoch("2026-10-16T12:30:00+03:00")  # outside quiet hours 01:00-07:00 (see test_operating_limits)
ZERO = {"total": 0, "opus": 0, "external": []}


def eff(s=10, w=33):
    return {"session": {"pct": s, "basis": "observed", "resets_at": "2026-10-16T03:50:00+03:00"},
            "weekly": {"pct": w, "basis": "observed", "resets_at": "2026-10-16T18:00:00+03:00"}, "session_elapsed_min": 30}


def qjob(i, task_type="docs", model=None, extra=""):
    m = "    model: %s\n" % model if model else ""
    return ("  - id: Q%02d\n    title: job %d\n    priority: P2\n    task_type: %s\n%s    channel: direct\n"
            "    worktree: {WT}\n    status: queued\n%s" % (i, i, task_type, m, extra))


class QueueRunnerTests(unittest.TestCase):
    def setUp(self):
        self.t = TempEnv().__enter__(); self.cfg = self.t.cfg
        self.wt = os.path.join(self.t.d, "wt"); os.makedirs(self.wt)
        self.pd = os.path.join(self.t.d, "prompts"); os.makedirs(self.pd)
        self.q = os.path.join(self.t.d, "queue.yaml")
        self.cfg["backlog"].update({"enabled": True, "queue": self.q, "state_file": os.path.join(self.t.d, "state.json"),
                                    "prompt_dir": self.pd, "max_concurrent": 3, "reserve_slots": 1,
                                    "reserve_opus": 1, "require_soak_window": False, "max_attempts": 2})
        os.environ["CR_NOW"] = iso(NOW)  # backlog_tick re-checks quiet hours on the clock before each launch
        self.launched, self.alive, self.gate_calls = [], True, 0

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
        return 4000000 + len(self.launched)

    def tick(self, e=None, counts=ZERO, gate=None):
        return S.backlog_tick(self.cfg, e or eff(), {"park": None, "local": None}, counts, 0, NOW,
                              launcher=self.launcher, procs_alive=lambda pid: self.alive, gate=gate)

    def test_fills_to_three_with_opus_reserve(self):
        # 6 opus jobs + 2 sonnet docs: own cap min(3, 4-1)=3, own opus cap 3-1=2 -> 2 opus + 1 sonnet
        self.write_queue([qjob(i, "review") for i in range(6)] + [qjob(10 + i, "docs") for i in range(2)])
        out = self.tick()
        fams = [S.job_family(self.cfg, {"task_type": s["task_type"], "model": s.get("model")}) for s in self.launched]
        self.assertEqual(len(self.launched), 3, out)
        self.assertEqual(fams.count("opus"), 2)

    def test_external_sessions_reduce_own_slots(self):
        # reserve = own sessions <= 4-1 = 3 (one slot never taken by the runner); total incl. external <= 4
        self.write_queue([qjob(i, "docs") for i in range(6)])
        self.tick(counts={"total": 2, "opus": 2, "external": [{"pid": 1}, {"pid": 2}]})
        self.assertEqual(len(self.launched), 2)  # 2 external + 2 own = 4

    def test_external_opus_counts_toward_opus_cap(self):
        self.write_queue([qjob(i, "review") for i in range(6)] + [qjob(20, "docs")])
        self.tick(counts={"total": 2, "opus": 2, "external": [{"pid": 1}, {"pid": 2}]})
        fams = [S.job_family(self.cfg, {"task_type": s["task_type"], "model": s.get("model")}) for s in self.launched]
        self.assertEqual((fams.count("opus"), len(fams)), (1, 2))  # opus 2+1 = 3, total 2+2 = 4

    def test_own_cap_three_even_with_no_external(self):
        self.write_queue([qjob(i, "docs") for i in range(8)])
        self.tick()
        self.assertEqual(len(self.launched), 3)
        self.tick(counts={"total": 3, "opus": 0, "external": []})
        self.assertEqual(len(self.launched), 3)

    def test_model_from_route_when_job_has_none(self):
        self.write_queue([qjob(1, "docs"), qjob(2, "review"), qjob(3, "docs", model="none")])
        out = self.tick()
        by = {s["label"]: s for s in self.launched}
        self.assertEqual(sorted(by), ["bl-Q01", "bl-Q02"])
        self.assertIsNone(by["bl-Q01"]["model"])  # runner routes --task-type docs -> sonnet
        self.assertEqual(S.job_family(self.cfg, {"task_type": "docs", "model": None}), "sonnet")
        self.assertIn("no model", " ".join(s["why"] for s in out["skipped"] if s["id"] == "Q03"))

    def test_usage_gate_checked_before_each_launch(self):
        self.write_queue([qjob(i, "docs") for i in range(4)])
        calls = []

        def gate():
            calls.append(1)
            return (len(calls) <= 2, "session 81% >= 80%")
        out = self.tick(gate=gate)
        self.assertEqual(len(self.launched), 2)
        self.assertEqual(len(calls), 3)
        self.assertIn("session 81%", out["gate_stop"])

    def test_session_and_weekly_thresholds_hold(self):
        self.write_queue([qjob(i, "docs") for i in range(3)])
        self.assertIn("session", " ".join(self.tick(eff(s=80))["held"]))  # backlog session_max_pct 80
        self.assertIn("weekly", " ".join(self.tick(eff(w=97))["held"]))
        self.assertIn("weekly", " ".join(self.tick(eff(w=80))["held"]))
        self.assertIn("weekly", " ".join(self.tick(eff(w=75))["held"]))  # backlog weekly_max_pct 75
        self.assertEqual(self.launched, [])
        out = self.tick(eff(w=70))  # weekly 68-75: cap 3 total, non-critical only just after a reset (elapsed 30); under the 73.5% pacing line
        self.assertEqual(len(self.launched), 3)

    def test_crash_without_finish_is_retried_then_failed(self):
        self.write_queue([qjob(1, "docs")])
        self.tick()
        self.alive = False
        self.tick()  # reaped as crashed -> retry -> relaunched
        st = B.load_state(self.cfg)["Q01"]
        self.assertEqual((st["status"], st["attempts"]), ("running", 2))
        self.assertEqual(len(self.launched), 2)
        self.tick()  # second crash: attempts exhausted
        st = B.load_state(self.cfg)["Q01"]
        self.assertEqual(st["status"], "failed")
        self.assertIn("crashed", st["why"])
        self.assertEqual(len(self.launched), 2)

    def test_limit_hit_not_retried(self):
        self.write_queue([qjob(1, "docs")])
        self.tick()
        rid = B.load_state(self.cfg)["Q01"]["run_id"]
        append_jsonl(log_path(self.cfg, "runs.jsonl"), {"event": "finish", "run_id": rid, "rc": 1, "limit_hit": True})
        self.alive = False
        self.tick()
        self.assertEqual(B.load_state(self.cfg)["Q01"]["status"], "failed")
        self.assertEqual(len(self.launched), 1)

    def test_done_job_with_commit_gets_local_commit(self):
        subprocess.run(["git", "init", "-q", "-b", "main", self.wt], check=True)
        for k, v in (("user.name", "t"), ("user.email", "t@example.invalid")):
            subprocess.run(["git", "-C", self.wt, "config", k, v], check=True)
        open(os.path.join(self.wt, "a.txt"), "w").write("a\n")
        subprocess.run(["git", "-C", self.wt, "add", "-A"], check=True)
        subprocess.run(["git", "-C", self.wt, "commit", "-qm", "base"], check=True)
        self.write_queue([qjob(1, "docs", extra="    commit: yes\n")])
        self.tick()
        open(os.path.join(self.wt, "b.txt"), "w").write("b\n")
        rid = B.load_state(self.cfg)["Q01"]["run_id"]
        append_jsonl(log_path(self.cfg, "runs.jsonl"), {"event": "finish", "run_id": rid, "rc": 0})
        self.alive = False
        self.tick()
        st = B.load_state(self.cfg)["Q01"]
        self.assertEqual(st["status"], "done")
        self.assertTrue(st.get("commit"))
        log = subprocess.run(["git", "-C", self.wt, "log", "--format=%s"], capture_output=True, text=True).stdout
        self.assertIn("backlog Q01: job 1", log)
        self.assertEqual(subprocess.run(["git", "-C", self.wt, "status", "--porcelain"], capture_output=True, text=True).stdout, "")

    def test_experiment_passed_through(self):
        self.write_queue([qjob(1, "review", extra="    experiment: autocompact\n")])
        self.tick()
        self.assertEqual(self.launched[0].get("experiment"), "autocompact")

    def test_group_limit(self):
        self.cfg["backlog"]["group_limits"] = {"sb": 2}
        self.write_queue([qjob(i, "docs", extra="    group: sb\n") for i in range(4)] + [qjob(9, "docs")])
        self.tick()
        self.assertEqual(sorted(s["label"] for s in self.launched), ["bl-Q00", "bl-Q01", "bl-Q09"])
        self.tick()
        self.assertEqual(len(self.launched), 3)  # group still full

    def test_group_slots_not_consumed_by_jobs_held_for_opus_cap(self):
        # 03:24 regression: opus jobs held by the Opus cap used up the per-group budget, starving later Sonnet jobs
        self.cfg["backlog"]["group_limits"] = {"fo": 2}
        self.write_queue([qjob(i, "review", extra="    group: fo\n") for i in range(3)] +
                         [qjob(10, "docs", extra="    group: fo\n"), qjob(11, "docs", extra="    group: fo\n")])
        self.tick(counts={"total": 3, "opus": 3, "external": []})  # 1 slot left under total 4, Opus full at 3
        self.assertEqual([s["label"] for s in self.launched], ["bl-Q10"])

    def test_counts_summary(self):
        self.write_queue([qjob(i, "docs") for i in range(7)])
        self.tick()
        c = B.counts(self.cfg)
        self.assertEqual((c["running"], c["pending"], c["done"]), (3, 4, 0))


class TickLogTests(unittest.TestCase):
    def setUp(self):
        self.t = TempEnv().__enter__(); self.cfg = self.t.cfg

    def tearDown(self):
        self.t.__exit__()

    def test_backlog_changes_are_logged(self):
        S._LAST.clear()
        base = {"mode": "normal", "reasons": [], "resume_at": None, "started": [], "reaped": [], "pending": 0}
        S._log_tick(self.cfg, dict(base, backlog={"started": ["Q01"], "reaped": []}))
        S._log_tick(self.cfg, dict(base, backlog={"started": [], "reaped": []}))
        S._log_tick(self.cfg, dict(base, backlog={"started": [], "reaped": [["Q01", "done"]]}))
        S._log_tick(self.cfg, dict(base, backlog={"started": [], "reaped": []}))
        S._log_tick(self.cfg, dict(base, backlog={"started": [], "reaped": []}))  # no change -> not logged
        self.assertEqual(len(self.t.read("scheduler.jsonl")), 4)


class LoopLifecycleTests(unittest.TestCase):
    """Real subprocess: pidfile, stop file, SIGTERM; a fake in-flight job survives the runner's exit.
    bin/cr runs inside the sandbox; the signals go to this test's own children only. runner.enabled is set to
    true in the temp config (the example's false is refused by the gate before any start)."""
    def setUp(self):
        self.t = TempEnv().__enter__()
        self.pid = os.path.join(self.t.logs, "queue-runner.pid")
        self.stop = os.path.join(self.t.logs, "queue-runner.stop")
        os.environ["CR_BACKLOG_DISABLE"] = "1"
        with open(self.t.config) as f:
            cfg = json.load(f)
        cfg["runner"]["enabled"] = True
        with open(self.t.config, "w") as f:
            json.dump(cfg, f, indent=1)

    def tearDown(self):
        self.t.__exit__()

    def start(self):
        cmd = [sys.executable, os.path.join(ROOT, "bin", "cr"), "sched", "loop", "--no-probe", "--interval", "0.2",
               "--pidfile", self.pid, "--stop-file", self.stop]
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=dict(os.environ))
        for _ in range(100):
            if os.path.exists(self.pid):
                break
            time.sleep(0.05)
        return p

    def test_pidfile_and_sigterm(self):
        p = self.start()
        self.assertEqual(int(open(self.pid).read().strip()), p.pid)
        child = subprocess.Popen(["sleep", "30"], start_new_session=True)  # stands in for an in-flight run
        p.send_signal(signal.SIGTERM)
        self.assertEqual(p.wait(10), 0)
        self.assertFalse(os.path.exists(self.pid))
        self.assertIsNone(child.poll())  # untouched
        child.kill(); child.wait()
        ev = [r.get("event") for r in self.t.read("scheduler.jsonl")]
        self.assertIn("runner_start", ev)
        self.assertIn("runner_stop", ev)

    def test_stop_file(self):
        p = self.start()
        open(self.stop, "w").close()
        self.assertEqual(p.wait(10), 0)
        self.assertFalse(os.path.exists(self.pid))

    def test_second_instance_refused(self):
        p = self.start()
        q = subprocess.run([sys.executable, os.path.join(ROOT, "bin", "cr"), "sched", "loop", "--no-probe",
                            "--pidfile", self.pid, "--stop-file", self.stop], capture_output=True, text=True, timeout=10)
        self.assertEqual(q.returncode, 3)
        self.assertIn("already running", q.stderr)
        p.send_signal(signal.SIGTERM); p.wait(10)

    def test_stale_pidfile_replaced(self):
        with open(self.pid, "w") as f:
            f.write("999999999\n")
        p = self.start()
        time.sleep(0.3)
        self.assertEqual(int(open(self.pid).read().strip()), p.pid)
        p.send_signal(signal.SIGTERM); p.wait(10)

    def test_cr_sched_stop(self):
        p = self.start()
        r = subprocess.run([sys.executable, os.path.join(ROOT, "bin", "cr"), "sched", "stop", "--pidfile", self.pid,
                            "--stop-file", self.stop], capture_output=True, text=True, timeout=10)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(p.wait(10), 0)


if __name__ == "__main__":
    unittest.main()
