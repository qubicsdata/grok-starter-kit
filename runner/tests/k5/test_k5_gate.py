"""`cr sched` refuses BEFORE any start while runner.enabled is not true, and while ANTHROPIC_API_KEY is set.

bin/cr runs in-process (the sandbox refuses it as a process). Every start path is replaced by a recorder, so a
missing gate records a call instead of starting anything: sched.loop / sched.tick / sched.launch / usage.poll /
usage.probe_print. Contract:
  * `cr sched loop` and `cr sched tick` (one-shot) check the gate first: before the pidfile, before
    scheduler.jsonl, before any /usage probe or launch. Only the JSON value true enables the runner; false,
    missing, "true", 1 all refuse. A refusal returns (or exits with) a non-zero code and names `runner.enabled`.
  * ANTHROPIC_API_KEY set (even empty) refuses the same commands (subscription login only); the message names
    the variable, never its value.
  * `cr sched status` (dry run, no probe) and `cr sched stop` still work while the runner is off."""
import json, os, unittest
from unittest import mock
import k5support as K
from k5support import TempEnv
from crlib import sched as S, usage as U

START_CMDS = (["sched", "loop", "--no-probe", "--interval", "0"], ["sched", "tick", "--no-probe"], ["sched", "tick"])
FAKE_KEY_VALUE = "example-not-a-real-key-0000"


class GateCase(unittest.TestCase):
    def setUp(self):
        self.t = TempEnv().__enter__()
        os.environ.pop("ANTHROPIC_API_KEY", None)
        self.calls = []
        rec = lambda name, ret=None: (lambda *a, **k: self.calls.append(name) or ret)
        self.patches = [mock.patch.object(S, "loop", rec("loop", "max_ticks")),
                        mock.patch.object(S, "tick", rec("tick", {"started": []})),
                        mock.patch.object(S, "launch", rec("launch", 4999999)),
                        mock.patch.object(S, "stop", rec("stop", (True, "not running"))),
                        mock.patch.object(U, "poll", rec("poll", {})),
                        mock.patch.object(U, "probe_print", rec("probe_print", ""))]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in reversed(self.patches):
            p.stop()
        self.t.__exit__()

    def set_enabled(self, value, present=True):
        def fn(cfg):
            if present:
                cfg["runner"]["enabled"] = value
            else:
                cfg["runner"].pop("enabled", None)
        K.edit_config(self.t, fn)

    def assert_refused(self, argv, must_name):
        rc, out, err = K.run_cr(argv)
        self.assertNotIn(rc, (0, None), "%s was not refused" % " ".join(argv))
        starts = [c for c in self.calls if c != "stop"]
        self.assertEqual(starts, [], "%s reached %s before the gate" % (" ".join(argv), starts))
        self.assertIn(must_name, out + err)
        rc_cfg = self.t.cfg["runner"]
        self.assertFalse(os.path.exists(rc_cfg["pidfile"]), "pidfile written before the gate")
        self.assertFalse(os.path.exists(os.path.join(self.t.logs, "scheduler.jsonl")), "scheduler.jsonl before the gate")
        self.assertFalse(os.path.exists(os.path.join(self.t.logs, "usage.jsonl")), "usage.jsonl before the gate")
        return out + err


class EnabledGateTests(GateCase):
    def test_example_config_is_off(self):
        self.assertIs(K.raw_example()["runner"]["enabled"], False)

    def test_disabled_refuses_loop_and_tick(self):
        for argv in START_CMDS:
            with self.subTest(cmd=" ".join(argv)):
                self.calls.clear()
                self.assert_refused(argv, "runner.enabled")

    def test_missing_or_non_boolean_enabled_refuses(self):
        for label, value, present in (("missing", None, False), ("string true", "true", True), ("one", 1, True),
                                      ("null", None, True)):
            self.set_enabled(value, present)
            for argv in START_CMDS[:2]:
                with self.subTest(enabled=label, cmd=argv[1]):
                    self.calls.clear()
                    self.assert_refused(argv, "runner.enabled")

    def test_enabled_true_reaches_the_scheduler(self):
        # Positive control: with the gate open the same commands reach the (recorded) scheduler.
        self.set_enabled(True)
        rc, _, _ = K.run_cr(START_CMDS[0])
        self.assertEqual((rc, self.calls), (0, ["loop"]))
        self.calls.clear()
        rc, _, _ = K.run_cr(START_CMDS[1])
        self.assertEqual((rc, self.calls), (0, ["tick"]))

    def test_status_and_stop_still_work_while_off(self):
        rc, out, _ = K.run_cr(["sched", "status"])
        self.assertEqual((rc, self.calls), (0, ["tick"]))
        self.calls.clear()
        with mock.patch.object(S, "tick", lambda *a, **k: self.calls.append(("tick", k.get("dry_run"), k.get("probe")))
                               or {}):
            K.run_cr(["sched", "status"])
        self.assertEqual(self.calls, [("tick", True, False)])  # dry run, no /usage probe
        self.calls.clear()
        rc, _, _ = K.run_cr(["sched", "stop"])
        self.assertEqual((rc, self.calls), (0, ["stop"]))

    def test_refusal_does_not_touch_an_existing_runner_state(self):
        # An old pidfile / stop file stays as it is: the gate runs before loop() would rewrite or clear them.
        rc_cfg = self.t.cfg["runner"]
        with open(rc_cfg["stop_file"], "w") as f:
            f.write("stop\n")
        K.run_cr(START_CMDS[0])
        self.assertTrue(os.path.exists(rc_cfg["stop_file"]))
        self.assertEqual(self.calls, [])


class ApiKeyRefusalTests(GateCase):
    def setUp(self):
        super().setUp()
        self.set_enabled(True)

    def test_api_key_refuses_even_when_enabled(self):
        for value in (FAKE_KEY_VALUE, ""):
            os.environ["ANTHROPIC_API_KEY"] = value
            for argv in START_CMDS:
                with self.subTest(cmd=" ".join(argv), empty=value == ""):
                    self.calls.clear()
                    text = self.assert_refused(argv, "ANTHROPIC_API_KEY")
                    self.assertNotIn(FAKE_KEY_VALUE, text)

    def test_refuse_api_key_missing_still_refuses(self):
        K.edit_config(self.t, lambda cfg: cfg["runner"].pop("refuse_api_key", None))
        os.environ["ANTHROPIC_API_KEY"] = FAKE_KEY_VALUE
        self.assert_refused(START_CMDS[0], "ANTHROPIC_API_KEY")

    def test_example_keeps_the_refusal_on(self):
        self.assertIs(K.raw_example()["runner"]["refuse_api_key"], True)


if __name__ == "__main__":
    unittest.main()
