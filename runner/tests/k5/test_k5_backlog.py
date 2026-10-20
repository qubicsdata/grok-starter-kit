"""Backlog rows of the parameterization table - group_limits {} (no built-in groups), a generic guard preamble naming
<your-name> (from config only; a job never starts without one), and the quiet-hours time zone (${KIT_TZ} in the
template, code default UTC, never a city).
Contract: an empty or missing backlog.guard_preamble holds the backlog (backlog_tick returns normally,
launches nothing, and its `held` list names backlog.guard_preamble); a quiet_hours.tz that is missing or empty
means UTC."""
import os, unittest
import k5support as K
from k5support import TempEnv
from crlib import backlog as B, sched as S
from crlib.common import iso, to_epoch

NOON = "2026-10-18T12:00:00+03:00"
ZERO = {"total": 0, "opus": 0, "external": []}


def eff(now):
    reset = iso(now + 3 * 86400)
    return {"session": {"pct": 10, "basis": "observed", "resets_at": iso(now + 3600)},
            "weekly": {"pct": 9.0, "basis": "observed", "resets_at": reset}, "session_elapsed_min": 30,
            "weekly_fable": {"pct": 0.0, "basis": "observed", "resets_at": reset, "age_min": 5.0}}


def qjob(i, group=None):
    return ("  - id: G%02d\n    title: job %d\n    priority: P1\n    task_type: docs\n    channel: direct\n"
            "    worktree: {WT}\n    status: queued\n" % (i, i)) + ("    group: %s\n" % group if group else "")


class BacklogCase(unittest.TestCase):
    def setUp(self):
        self.t = TempEnv().__enter__(); self.cfg = self.t.cfg
        os.environ["CR_NOW"] = NOON  # the launch-time quiet-hours re-check reads now_ts()
        self.wt = os.path.join(self.t.d, "wt"); os.makedirs(self.wt)
        self.pd = os.path.join(self.t.d, "prompts"); os.makedirs(self.pd)
        self.q = os.path.join(self.t.d, "queue.yaml")
        self.cfg["backlog"].update({"enabled": True, "queue": self.q, "state_file": os.path.join(self.t.d, "state.json"),
                                    "prompt_dir": self.pd, "require_soak_window": False})
        self.launched = []

    def tearDown(self):
        self.t.__exit__()

    def queue(self, groups):
        with open(self.q, "w") as f:
            f.write("version: 1\njobs:\n" + "".join(qjob(i, g) for i, g in enumerate(groups)).replace("{WT}", self.wt))
        for i in range(len(groups)):
            with open(os.path.join(self.pd, "G%02d.md" % i), "w") as f:
                f.write("do %d" % i)

    def launcher(self, cfg, spec):
        self.launched.append(spec)
        return 4300000 + len(self.launched)

    def tick(self):
        now = to_epoch(NOON)
        try:
            return S.backlog_tick(self.cfg, eff(now), {"park": None, "local": None}, ZERO, 0, now,
                                  launcher=self.launcher, procs_alive=lambda pid: True)
        except Exception as e:  # noqa: BLE001
            self.fail("backlog_tick raised %s: %s" % (type(e).__name__, e))


class GroupLimitsTests(BacklogCase):
    def test_example_has_no_groups(self):
        self.assertEqual(K.raw_example()["backlog"]["group_limits"], {})

    def test_empty_group_limits_cap_nothing(self):
        self.queue(["example-group"] * 3)
        self.tick()
        self.assertEqual(len(self.launched), 3)  # only max_concurrent (3) applies

    def test_missing_group_limits_cap_nothing(self):
        self.cfg["backlog"].pop("group_limits")
        self.queue(["example-group"] * 3)
        self.tick()
        self.assertEqual(len(self.launched), 3)

    def test_configured_group_limit_applies(self):
        # Control: the same queue with a limit of 1 for its group starts one job.
        self.cfg["backlog"]["group_limits"] = {"example-group": 1}
        self.queue(["example-group"] * 3)
        self.tick()
        self.assertEqual(len(self.launched), 1)


class GuardPreambleTests(BacklogCase):
    def test_example_preamble_is_generic(self):
        p = K.raw_example()["backlog"]["guard_preamble"]
        self.assertIn("<your-name>", p)
        for must in ("never git push", "PR"):
            self.assertIn(must, p)
        import re
        self.assertEqual(set(re.findall(r"<[^<>]+>", p)), {"<your-name>"})

    def test_prompt_uses_the_configured_preamble(self):
        self.cfg["backlog"]["guard_preamble"] = "EXAMPLE GUARD: local only. Ask <your-name>."
        self.queue([None])
        self.tick()
        with open(self.launched[0]["prompt_file"]) as f:
            self.assertEqual(f.read(), "EXAMPLE GUARD: local only. Ask <your-name>.\n\ndo 0")

    def test_no_preamble_text_built_into_the_code(self):
        for rel in ("crlib/backlog.py", "crlib/sched.py", "cr"):
            self.assertNotIn("BACKLOG JOB", K.read(os.path.join(K.BIN, rel)), rel)

    def test_empty_or_missing_preamble_holds_the_backlog(self):
        for label in ("empty", "blank", "missing"):
            with self.subTest(preamble=label):
                self.launched.clear()
                if os.path.exists(self.cfg["backlog"]["state_file"]):
                    os.remove(self.cfg["backlog"]["state_file"])
                if label == "missing":
                    self.cfg["backlog"].pop("guard_preamble", None)
                else:
                    self.cfg["backlog"]["guard_preamble"] = "" if label == "empty" else "  \n "
                self.queue([None])
                out = self.tick()
                self.assertEqual(self.launched, [], "a job started without a guard preamble")
                self.assertNotIn("running", [v.get("status") for v in B.load_state(self.cfg).values()])
                self.assertIn("backlog.guard_preamble", " ".join(out.get("held") or []))


class QuietHoursTzTests(unittest.TestCase):
    def setUp(self):
        self.t = TempEnv().__enter__(); self.cfg = self.t.cfg

    def tearDown(self):
        self.t.__exit__()

    def quiet(self, when):
        try:
            return S.in_quiet_hours(self.cfg, to_epoch(when))
        except Exception as e:  # noqa: BLE001
            self.fail("in_quiet_hours raised %s" % type(e).__name__)

    def test_template_tz_is_kit_tz(self):
        self.assertEqual(K.raw_example()["backlog"]["quiet_hours"]["tz"], "${KIT_TZ}")

    def test_missing_tz_means_utc(self):
        self.cfg["backlog"]["quiet_hours"].pop("tz")
        self.assertTrue(self.quiet("2026-10-18T02:00:00Z"))
        self.assertFalse(self.quiet("2026-10-18T02:00:00+03:00"))  # 23:00 UTC

    def test_empty_tz_means_utc(self):
        self.cfg["backlog"]["quiet_hours"]["tz"] = ""
        self.assertTrue(self.quiet("2026-10-18T02:00:00Z"))
        self.assertFalse(self.quiet("2026-10-18T02:00:00+03:00"))


if __name__ == "__main__":
    unittest.main()
