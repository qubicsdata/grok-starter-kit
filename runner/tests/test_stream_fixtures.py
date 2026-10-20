"""The synthetic stream-json fixtures in runner/fixtures/ against the real parsers (runlog, usage).
Checks the field set that runner/fixtures/FIXTURES.md describes: status, rateLimitType, resetsAt, utilization,
unifiedWindows (five_hour, seven_day) and overageStatus."""
import json, os, shutil, unittest
from helpers import TempEnv, RUNNER_DIR
from crlib import runlog as RL, usage as U
from crlib.common import iso

TREE_FIX = os.path.join(RUNNER_DIR, "fixtures")
RESET5, RESET7 = 1767970800, 1767981600  # 2026-01-09 15:00 / 18:00 UTC
BEFORE = RESET5 - 3600


def lines(name):
    with open(os.path.join(TREE_FIX, name)) as f:
        return [json.loads(l) for l in f if l.strip()]


class EventLineTests(unittest.TestCase):
    def test_event_lines_convert(self):
        evs = lines("rate_limit_events_synthetic.jsonl")
        self.assertEqual([e["rate_limit_info"]["status"] for e in evs], ["allowed", "allowed_warning", "rejected"])
        recs = [RL.rate_info_to_usage(e["rate_limit_info"], BEFORE, "example-run", e["session_id"]) for e in evs]
        self.assertEqual([r["session_5h"]["used_pct"] for r in recs], [42.0, 55.0, 100.0])
        self.assertEqual([r["weekly_all_models"]["used_pct"] for r in recs], [61.0, 76.0, 79.0])
        for r in recs:
            self.assertEqual((r["kind"], r["observed"], r["overage_status"]), ("rate_limit_event", True, "disabled"))
            self.assertEqual(r["session_5h"]["resets_at"], iso(RESET5))
            self.assertEqual(r["weekly_all_models"]["resets_at"], iso(RESET7))
            self.assertEqual(r["session_id"], "00000000-0000-0000-0000-000000000000")
        self.assertEqual(recs[1]["rate_limit_type"], "seven_day")
        self.assertEqual(recs[2]["utilization"], 1.0)


class StreamTests(unittest.TestCase):
    def setUp(self):
        self.t = TempEnv().__enter__(); self.cfg = self.t.cfg

    def tearDown(self):
        self.t.__exit__()

    def finish(self, name, run_id):
        out = os.path.join(self.t.logs, run_id + ".stream.jsonl")  # not under streams/: no live-stream double count
        shutil.copyfile(os.path.join(TREE_FIX, name), out)
        os.environ["CR_NOW"] = iso(BEFORE)
        return RL.log_finish(self.cfg, run_id, 0, out, "stream-json", os.path.join(self.t.logs, run_id + ".json"))

    def test_allowed_stream(self):
        line, result, events = RL.parse_stream(os.path.join(TREE_FIX, "stream_allowed_synthetic.jsonl"))
        self.assertEqual((result["type"], result["is_error"]), ("result", False))
        self.assertEqual(len(events), 2)  # a duplicate event, as real streams repeat them
        fin = self.finish("stream_allowed_synthetic.jsonl", "example-allowed")
        self.assertEqual(fin["models_reported"], ["claude-sonnet-5-5"])
        self.assertFalse(fin.get("limit_hit", False))
        ev = [r for r in self.t.read("usage.jsonl") if r["kind"] == "rate_limit_event"]
        self.assertEqual(len(ev), 1)  # deduplicated
        self.assertEqual((ev[0]["session_5h"]["used_pct"], ev[0]["weekly_all_models"]["used_pct"]), (42.0, 61.0))
        st = U.state(self.cfg, BEFORE, include_local=False)
        self.assertIsNone(st["park"])
        self.assertEqual((st["session"]["kind"], st["session"]["used_pct"]), ("rate_limit_event", 42.0))
        with open(os.path.join(self.t.logs, "example-allowed.json")) as f:
            self.assertEqual(json.load(f)["type"], "result")

    def test_rejected_stream_parks_until_reset(self):
        fin = self.finish("stream_rejected_synthetic.jsonl", "example-rejected")
        self.assertTrue(fin["limit_hit"])
        self.assertEqual(fin["rate_limit_last"]["status"], "rejected")
        statuses = [r["status"] for r in self.t.read("usage.jsonl") if r["kind"] == "rate_limit_event"]
        self.assertEqual(statuses, ["allowed_warning", "rejected"])
        st = U.state(self.cfg, BEFORE, include_local=False)
        self.assertTrue(st["park"]["active"])
        self.assertTrue(st["park"]["authoritative"])
        self.assertEqual(st["park"]["resume_at"], iso(RESET5))
        later = U.state(self.cfg, RESET5 + self.cfg["policy"]["resume_grace_seconds"] + 1, include_local=False)
        self.assertFalse(later["park"]["active"])

    def test_live_stream_is_read_before_finish(self):
        out = os.path.join(self.t.logs, "streams", "example-live.jsonl")
        os.makedirs(os.path.dirname(out))
        shutil.copyfile(os.path.join(TREE_FIX, "stream_rejected_synthetic.jsonl"), out)
        os.utime(out, (BEFORE, BEFORE))
        evs = U._stream_events(self.cfg, BEFORE - 60)
        self.assertEqual(len(evs), 1)
        self.assertEqual((evs[0]["status"], evs[0]["run_id"]), ("rejected", "example-live"))
        self.assertTrue(evs[0]["source"].endswith("(live stream)"))


class TreeUsageScreenTests(unittest.TestCase):
    def test_tree_usage_screen_parses(self):
        with open(os.path.join(TREE_FIX, "usage_screen_synthetic.txt"), encoding="utf-8") as f:
            p = U.parse_usage_screen(f.read(), BEFORE)
        self.assertEqual({k: v["used_pct"] for k, v in p.items()},
                         {"session_5h": 42.0, "weekly_all_models": 61.0, "weekly_fable": 33.0})
        self.assertTrue(all(v["resets_at"] for v in p.values()))


if __name__ == "__main__":
    unittest.main()
