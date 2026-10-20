import os, unittest
from helpers import TempEnv, FIX
from make_synthetic_fixtures import ANSI
from crlib import usage as U
from crlib.common import to_epoch, iso

NOW = to_epoch("2026-10-11T03:00:00Z")


def rd(p):
    with open(os.path.join(FIX, p)) as f:
        return f.read()


class ScreenTests(unittest.TestCase):
    def test_parse_synthetic_screen(self):
        p = U.parse_usage_screen(rd("usage_screen_synthetic_1744.txt"), to_epoch("2026-10-15T17:44:00+03:00"))
        self.assertEqual(p["session_5h"], {"used_pct": 26.0, "resets_at": "2026-10-15T17:49:00+03:00"})
        self.assertEqual(p["weekly_all_models"], {"used_pct": 29.0, "resets_at": "2026-10-16T17:59:00+03:00"})
        self.assertEqual(p["weekly_fable"], {"used_pct": 0.0, "resets_at": "2026-10-16T18:00:00+03:00"})
        self.assertEqual(set(p), {"session_5h", "weekly_all_models", "weekly_fable"})  # nothing else parsed

    def test_email_redacted_and_never_stored(self):
        txt = rd("usage_screen_with_example_email.txt")
        self.assertIn("user@example.invalid", txt)
        self.assertNotIn("user@example.invalid", U.redact(txt))
        with TempEnv() as t:
            U.poll(t.cfg, screen_text=txt, now=to_epoch("2026-10-15T17:44:00+03:00"))
            with open(os.path.join(t.logs, "usage.jsonl")) as f:
                raw = f.read()
            self.assertNotIn("@", raw)
            self.assertIn('"kind":"usage_screen"', raw)

    def test_email_line_does_not_change_parse(self):
        now = to_epoch("2026-10-15T17:44:00+03:00")
        self.assertEqual(U.parse_usage_screen(rd("usage_screen_with_example_email.txt"), now),
                         U.parse_usage_screen(rd("usage_screen_synthetic_1744.txt"), now))

    def test_ansi_boxdraw_crlf_full_bar(self):
        # Built in memory: ESC and CR bytes are control characters, which no file under runner/ may hold.
        txt = ANSI
        self.assertIn("\x1b[", txt)
        self.assertIn("\r\n", txt)
        self.assertIn("\u2500", txt)
        p = U.parse_usage_screen(txt, to_epoch("2026-10-15T18:01:00+03:00"))
        self.assertEqual(p["session_5h"], {"used_pct": 12.5, "resets_at": "2026-10-15T23:00:00+03:00"})
        self.assertEqual(p["weekly_all_models"], {"used_pct": 66.0, "resets_at": "2026-10-16T17:59:00+03:00"})
        self.assertEqual(p["weekly_fable"], {"used_pct": 100.0, "resets_at": "2026-10-16T18:00:00+03:00"})
        self.assertEqual(set(p), {"session_5h", "weekly_all_models", "weekly_fable"})
        red = U.redact(txt)
        self.assertNotIn("@", red)
        with TempEnv() as t:
            U.poll(t.cfg, screen_text=txt, now=to_epoch("2026-10-15T18:01:00+03:00"))
            with open(os.path.join(t.logs, "usage.jsonl")) as f:
                raw = f.read()
            self.assertNotIn("@", raw)
            self.assertNotIn("Example Org", raw)
            self.assertIn('"kind":"usage_screen"', raw)

    def test_print_mode_fable_line(self):
        p = U.parse_usage_screen(rd("usage_print_synthetic_1801.txt"), to_epoch("2026-10-15T18:01:00+03:00"))
        self.assertEqual(p["weekly_fable"], {"used_pct": 0.0, "resets_at": "2026-10-16T18:00:00+03:00"})

    def test_fresh_window_without_reset_line(self):
        p = U.parse_usage_screen(rd("usage_screen_fresh_window.txt"), to_epoch("2026-10-15T19:00:00+03:00"))
        self.assertEqual(p["session_5h"], {"used_pct": 0.0, "resets_at": None})
        self.assertEqual(p["weekly_all_models"]["used_pct"], 81.0)

    def test_time_only_reset_rolls_to_next_day(self):
        p = U.parse_usage_screen("Current session\n 3% used\n Resets 1:10am (Etc/GMT-3)\n", to_epoch("2026-10-15T23:30:00+03:00"))
        self.assertEqual(p["session_5h"]["resets_at"], "2026-10-16T01:10:00+03:00")

    def test_parse_print_mode(self):
        p = U.parse_usage_screen(rd("usage_print_synthetic_1801.txt"), to_epoch("2026-10-15T18:01:00+03:00"))
        self.assertEqual(p["session_5h"], {"used_pct": 5.0, "resets_at": "2026-10-15T22:50:00+03:00"})
        self.assertEqual(p["weekly_all_models"], {"used_pct": 30.0, "resets_at": "2026-10-16T18:00:00+03:00"})

    def test_probe_print_with_fake_claude(self):
        import json as _j
        calls = []

        class R:
            def __init__(self, out):
                self.stdout = out

        def runner(argv, **kw):
            calls.append(argv)
            return R(_j.dumps({"type": "result", "num_turns": 0, "modelUsage": {}, "result": rd("usage_print_synthetic_1801.txt")}))
        with TempEnv() as t:
            txt = U.probe_print(t.cfg, runner=runner)
            self.assertIn("Current session: 5% used", txt)
            self.assertEqual(calls[0][calls[0].index("-p") + 1], "/usage")
            self.assertIn("ANTHROPIC_API_KEY", calls[0])  # as an -u target
            bad = lambda argv, **kw: R(_j.dumps({"result": "Current session: 1% used", "modelUsage": {"claude-x": {}}}))
            self.assertEqual(U.probe_print(t.cfg, runner=bad), "")  # a model reply is never a reading

    def test_no_tmux_probe(self):
        # Safe limits: probe_fallback none, the tmux screen scrape is removed
        # (full coverage in test_operating_limits.NoTmuxTests).
        self.assertFalse(hasattr(U, "probe_tmux"))
        with TempEnv() as t:
            self.assertEqual(t.cfg["usage"]["probe_fallback"], "none")


class LocalTests(unittest.TestCase):
    def setUp(self):
        self.t = TempEnv().__enter__()
        self.msgs = U.iter_messages(os.path.join(FIX, "projects"), NOW - 9 * 86400)

    def tearDown(self):
        self.t.__exit__()

    def test_dedupe_and_synthetic_skipped(self):
        self.assertEqual(len(self.msgs), 7)  # 9 assistant lines - 1 duplicate - 1 synthetic

    def test_block_detection_across_gaps(self):
        bl = U.blocks(self.msgs, 5)
        self.assertEqual([iso(b["start"]) for b in bl],
                         [iso(to_epoch("2026-10-02T10:00:00Z")), iso(to_epoch("2026-10-10T08:00:00Z")),
                          iso(to_epoch("2026-10-10T13:05:00Z")), iso(to_epoch("2026-10-11T02:00:00Z"))])
        self.assertEqual(len(bl[1]["messages"]), 3)  # 08:00, 08:30, 12:59 share a block
        cur = U.summarize_block(self.t.cfg, bl[-1], NOW)
        self.assertTrue(cur["active"])
        self.assertEqual(cur["expected_reset"], iso(to_epoch("2026-10-11T07:00:00Z")))
        self.assertEqual(cur["tokens_by_model"]["claude-opus-5-5"]["output"], 300)
        self.assertEqual(cur["tokens_by_model"]["claude-haiku-5-5"]["output"], 7)
        self.assertEqual(cur["burn_output_per_min"], round(307 / 60))

    def test_anchor_splits_block(self):
        anchor = to_epoch("2026-10-10T10:00:00Z")  # server says the window reset at 10:00
        bl = U.blocks(self.msgs, 5, anchors=[anchor])
        starts = [iso(b["start"]) for b in bl]
        self.assertIn(iso(to_epoch("2026-10-10T12:59:00Z")), starts)
        self.assertEqual(bl[1]["end"], anchor)

    def test_weekly_rollup(self):
        w = U.rollup(self.t.cfg, self.msgs, NOW - 7 * 86400, NOW + 1)
        self.assertNotIn(999, [v["output"] for v in w["tokens_by_model"].values()])
        self.assertEqual(w["tokens_by_model"]["claude-opus-5-5"]["output"], 100 * 3 + 300)
        self.assertEqual(w["tokens_by_model"]["claude-sonnet-5-5"]["output"], 50)
        self.assertEqual(w["tokens_by_model"]["claude-haiku-5-5"]["messages"], 1)

    def test_state_observed_vs_estimate(self):
        os.environ["CR_NOW"] = "2026-10-11T03:00:00Z"
        self.t.write_usage([{"ts": "2026-10-11T02:50:00Z", "kind": "usage_screen",
                             "session_5h": {"used_pct": 40, "resets_at": "2026-10-11T07:00:00Z"},
                             "weekly_all_models": {"used_pct": 50, "resets_at": "2026-10-14T00:00:00Z"}}])
        st = U.state(self.t.cfg, NOW)
        eff = U.effective(self.t.cfg, st, NOW)
        self.assertEqual((eff["session"]["pct"], eff["session"]["basis"]), (40, "observed"))
        self.assertEqual(eff["session_elapsed_min"], 60.0)
        self.assertTrue(st["local"]["inferred"])
        later = NOW + 3600  # 70 min old -> stale -> max(observed, estimate)
        st2 = U.state(self.t.cfg, later)
        self.assertTrue(st2["session"]["stale"])
        self.assertEqual(U.effective(self.t.cfg, st2, later)["session"]["basis"], "stale-observed+estimate")
        after = to_epoch("2026-10-11T07:30:00Z")  # past the observed reset
        st3 = U.state(self.t.cfg, after)
        self.assertTrue(st3["session"]["reset_passed"])
        self.assertEqual(st3["session"]["used_pct"], 0.0)

    def test_seed_record_compatible(self):
        self.t.write_usage([{"ts": "2026-10-11T02:43:00+03:00", "source": "claude-code /usage", "kind": "seed",
                             "session_5h": {"used_pct": 25, "resets_at": "2026-10-11T07:49:00+03:00"},
                             "weekly_all_models": {"used_pct": 29, "resets_at": "2026-10-16T17:59:00+03:00"}}])
        st = U.state(self.t.cfg, to_epoch("2026-10-11T02:45:00+03:00"), messages=[])
        self.assertEqual((st["session"]["used_pct"], st["weekly"]["used_pct"], st["session"]["kind"]), (25, 29, "seed"))

    def test_calibration_from_observation(self):
        self.t.write_usage([{"ts": "2026-10-11T02:59:00Z", "kind": "usage_screen",
                             "session_5h": {"used_pct": 10, "resets_at": "2026-10-11T07:00:00Z"}}])
        cal = U.calibrate(self.t.cfg, NOW, messages=self.msgs)
        st = U.state(self.t.cfg, NOW, messages=self.msgs)
        self.assertEqual(cal["five_hour_weighted"], st["local"]["block"]["weighted_tokens"] * 10)
        self.assertEqual(st["local"]["budget_source"], "calibration")
        self.assertAlmostEqual(st["local"]["est_session_pct"], 10.0, delta=0.2)


if __name__ == "__main__":
    unittest.main()
