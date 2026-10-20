"""run-claude.sh with a fake claude: routing, logging, the default invocation, env stripping, deny rules.

Every test runs the kit's run-claude.sh inside the sandbox (helpers.TempEnv): a temp KIT_HOME whose router.json is
the example config, with the kit's flags and bash-env templates copied to its runner/ dir, and the fake claude."""
import json, os, re, stat, subprocess, unittest
from helpers import TempEnv, ROOT, BIN, FAKEBIN, RUNNER_DIR

RUNNER = os.path.join(BIN, "run-claude.sh")
FLAGS = os.path.join(RUNNER_DIR, "claude-run-flags.sh")
BASH_ENV_FILE = os.path.join(RUNNER_DIR, "claude-bash-env.sh")
# The template's env scrub list (CLAUDE_UNSET_ENV) without ANTHROPIC_API_KEY, which the runner refuses outright.
SENSITIVE = ["GH_TOKEN", "GITHUB_TOKEN", "NPM_TOKEN", "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN",
             "OPENAI_API_KEY", "ANTHROPIC_AUTH_TOKEN"]


def open_read(p, mode="r"):
    with open(p, mode) as f:
        return f.read()


def flag_arrays():
    out = subprocess.run(["bash", "-c", '. "$1"; printf "%s\\n" "${CLAUDE_ALLOWED[@]}"; echo @@; '
                          'printf "%s\\n" "${CLAUDE_DISALLOWED[@]}"; echo @@; printf "%s\\n" "${CLAUDE_UNSET_ENV[@]}"', "x", FLAGS],
                         capture_output=True, text=True, check=True).stdout
    a, d, u = out.split("@@\n")
    return a.split("\n")[:-1], d.split("\n")[:-1], u.split()


class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.t = TempEnv().__enter__()
        self.d = self.t.d
        self.logs = os.path.join(self.d, "runner", "logs-run")
        os.makedirs(self.logs)
        self.wt = os.path.join(self.d, "wt"); os.makedirs(self.wt)
        self.prompt = os.path.join(self.d, "p.md")
        with open(self.prompt, "w") as f:
            f.write("say OK")
        self.rec = os.path.join(self.d, "rec.jsonl")
        self.bash_env = self.t.cfg["runner"]["bash_env_file"]

    def tearDown(self):
        self.t.__exit__()

    def env(self, **kw):
        e = {k: v for k, v in os.environ.items() if k not in ("ANTHROPIC_API_KEY", "CLAUDE_ROUTE_MODEL", "CR_LOG_DIR",
                                                               "CLAUDE_RUNNER_STREAM", "CLAUDE_ROUTE_ALLOW_HAIKU")}
        for k in SENSITIVE:
            e[k] = "fake-test-value"
        e.update({"CLAUDE_BIN": os.path.join(FAKEBIN, "claude"), "CLAUDE_RUN_LOG_DIR": self.logs,
                  "CLAUDE_ROUTER_DIR": ROOT, "PROMPT_FILE": self.prompt, "FAKE_CLAUDE_RECORD": self.rec})
        e.update(kw)
        return e

    def run_runner(self, args, **envkw):
        return subprocess.run([RUNNER] + args + ["t1", self.wt], capture_output=True, text=True,
                              env=self.env(**envkw), timeout=60)

    def records(self):
        from crlib.common import read_jsonl
        return read_jsonl(self.rec)

    def logs_jsonl(self, name):
        from crlib.common import read_jsonl
        return read_jsonl(os.path.join(self.logs, name))

    # ---- the default invocation (no options) ----
    def test_default_invocation(self):
        r = self.run_runner([])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout, "claude rc=0\n")
        allowed, denied, _ = flag_arrays()
        self.assertEqual(self.records()[0]["argv"],
                         ["-p", "say OK", "--output-format", "json", "--permission-mode", "acceptEdits",
                          "--allowedTools"] + allowed + ["--disallowedTools"] + denied)
        res = json.loads(open_read(os.path.join(self.logs, "claude-t1.json")))
        self.assertEqual(res["type"], "result")
        self.assertEqual(self.records()[0]["cwd"], self.wt)

    def test_default_run_is_logged(self):
        self.run_runner([])
        start, fin = self.logs_jsonl("runs.jsonl")
        self.assertEqual((start["event"], start["model"], start["model_source"], start["task_type"]), ("start", None, "default", None))
        self.assertEqual(start["cwd"], self.wt)
        self.assertTrue(start["run_id"].startswith("t1-"))
        self.assertEqual(fin["run_id"], start["run_id"])
        self.assertEqual(fin["models_reported"], ["claude-opus-5-5"])
        self.assertEqual(fin["modelUsage"]["claude-opus-5-5"]["outputTokens"], 20)

    # ---- routing ----
    def test_task_type_routes_and_streams(self):
        r = self.run_runner(["--task-type", "rebase", "--run-id", "rid1"])
        self.assertEqual(r.returncode, 0, r.stderr)
        argv = self.records()[0]["argv"]
        self.assertEqual(argv[argv.index("--model") + 1], "sonnet")
        self.assertEqual(argv[argv.index("--fallback-model") + 1], "opus")
        self.assertEqual(argv[argv.index("--output-format") + 1], "stream-json")
        self.assertIn("--verbose", argv)
        self.assertEqual(argv[argv.index("--effort") + 1], "medium")
        st = json.loads(argv[argv.index("--settings") + 1])
        self.assertFalse(st["enabledPlugins"]["superpowers@claude-plugins-official"])
        self.assertEqual(st["skillListingMaxDescChars"], 80)
        self.assertIn("--strict-mcp-config", argv)
        self.assertNotIn("--autocompact", argv)
        self.assertLess(argv.index("--strict-mcp-config"), argv.index("--allowedTools"))  # not swallowed by variadic lists
        self.assertEqual(json.loads(open_read(os.path.join(self.logs, "claude-t1.json")))["type"], "result")
        self.assertTrue(os.path.exists(os.path.join(self.logs, "streams", "rid1.jsonl")))
        start, fin = self.logs_jsonl("runs.jsonl")
        self.assertEqual((start["run_id"], start["task_type"], start["model"], start["model_source"], start["override"]),
                         ("rid1", "rebase", "sonnet", "route", False))
        self.assertIn("Sonnet", start["reason"])
        self.assertEqual(fin["models_reported"], ["claude-sonnet-5-5"])
        self.assertEqual(fin["rate_limit_last"]["session_5h"]["used_pct"], 42.0)

    def test_rate_limit_event_captured_once(self):
        self.run_runner(["--task-type", "rename", "--run-id", "rid2"])
        ev = [u for u in self.logs_jsonl("usage.jsonl") if u["kind"] == "rate_limit_event"]
        self.assertEqual(len(ev), 1)  # duplicate events deduplicated
        self.assertEqual(ev[0]["session_5h"]["used_pct"], 42.0)
        self.assertEqual(ev[0]["weekly_all_models"]["used_pct"], 31.0)
        self.assertEqual(ev[0]["session_5h"]["resets_at"], "2026-10-15T17:50:00+03:00")
        self.assertEqual(ev[0]["run_id"], "rid2")

    def test_override_flag_and_env(self):
        self.run_runner(["--task-type", "rebase", "--model", "opus"])
        self.run_runner(["--task-type", "security"], CLAUDE_ROUTE_MODEL="sonnet")
        recs = self.records()
        self.assertEqual(recs[0]["argv"][recs[0]["argv"].index("--model") + 1], "opus")
        self.assertEqual(recs[1]["argv"][recs[1]["argv"].index("--model") + 1], "sonnet")
        starts = [r for r in self.logs_jsonl("runs.jsonl") if r["event"] == "start"]
        self.assertEqual([(s["model_source"], s["override"]) for s in starts], [("override-flag", True), ("override-env", True)])

    def test_default_run_has_no_new_flags(self):
        self.run_runner([])
        argv = self.records()[0]["argv"]
        for f in ("--model", "--effort", "--settings", "--strict-mcp-config", "--autocompact", "--fallback-model", "--verbose"):
            self.assertNotIn(f, argv)

    def test_experiments_flag_and_env(self):
        self.run_runner(["--task-type", "implement", "--experiment", "autocompact", "--run-id", "x1"])
        self.run_runner(["--task-type", "implement", "--run-id", "x2"], CLAUDE_ROUTE_EXPERIMENTS="prompt_cache_ttl")
        a, b = self.records()
        self.assertEqual(a["argv"][a["argv"].index("--autocompact") + 1], "200k")
        self.assertEqual(json.loads(b["argv"][b["argv"].index("--settings") + 1])["promptCacheTtl"], "5m")
        starts = [r for r in self.logs_jsonl("runs.jsonl") if r["event"] == "start"]
        self.assertEqual([s["experiments"] for s in starts], [["autocompact"], ["prompt_cache_ttl"]])
        self.assertEqual(starts[0]["profile"], "lean")

    def test_effort_override(self):
        self.run_runner(["--task-type", "security", "--effort", "max"])
        argv = self.records()[0]["argv"]
        self.assertEqual(argv[argv.index("--effort") + 1], "max")
        self.assertNotIn("superpowers@claude-plugins-official", argv[argv.index("--settings") + 1])

    def test_haiku_opt_in_flag(self):
        self.run_runner(["--task-type", "log-triage", "--allow-haiku"])
        self.run_runner(["--task-type", "log-triage"])
        a, b = self.records()
        self.assertEqual(a["argv"][a["argv"].index("--model") + 1], "haiku")
        self.assertEqual(b["argv"][b["argv"].index("--model") + 1], "sonnet")

    def test_subagent_env_only_when_configured(self):
        self.run_runner(["--task-type", "implement"])
        self.run_runner(["--task-type", "implement"], CLAUDE_ROUTE_SUBAGENT_MODEL="sonnet")
        a, b = self.records()
        self.assertIsNone(a["subagent_model"])
        self.assertEqual(b["subagent_model"], "sonnet")

    def test_unknown_task_type_does_not_start_claude(self):
        r = self.run_runner(["--task-type", "nope"])
        self.assertEqual(r.returncode, 2)
        self.assertEqual(self.records(), [])

    # ---- guard rails unchanged ----
    def test_api_key_refused(self):
        r = self.run_runner(["--task-type", "rebase"], ANTHROPIC_API_KEY="")
        self.assertEqual(r.returncode, 99)
        self.assertEqual(self.records(), [])

    def test_env_stripped_in_both_modes(self):
        self.run_runner([])
        self.run_runner(["--task-type", "rebase"])
        for rec in self.records():
            self.assertEqual({k: v for k, v in rec["env_present"].items() if k in SENSITIVE + ["ANTHROPIC_API_KEY"]},
                             {k: False for k in SENSITIVE + ["ANTHROPIC_API_KEY"]})
            self.assertEqual(rec["claude_env_file"], self.bash_env)
            self.assertFalse(rec["stdin_isatty"])
            self.assertEqual(rec["argv"][rec["argv"].index("--permission-mode") + 1], "acceptEdits")

    def test_allow_and_deny_lists_passed_verbatim(self):
        allowed, denied, unset = flag_arrays()
        self.run_runner(["--task-type", "rebase"])
        argv = self.records()[0]["argv"]
        ia, idn = argv.index("--allowedTools"), argv.index("--disallowedTools")
        self.assertEqual(argv[ia + 1:idn], allowed)
        self.assertEqual(argv[idn + 1:], denied)
        for must in ("Bash(env)", "Bash(printenv)", "Bash(set)", "Bash(export -p*)", "Bash(declare)", "Bash(typeset*)",
                     "Bash(compgen -v*)", "Read(//proc/**)", "Bash(bash -c*)", "Bash(sh -c*)", "Bash(eval *)", "Bash(exec *)",
                     "Read(~/.claude/.credentials*)", "Read(~/.ssh/**)"):
            self.assertIn(must, denied)
        self.assertEqual(unset, SENSITIVE + ["ANTHROPIC_API_KEY"])

    def test_flags_templates_match_their_doc(self):
        # The friend owns the lists: no pinned hashes, but the doc must list exactly what the template holds.
        self.assertFalse(stat.S_IMODE(os.stat(BASH_ENV_FILE).st_mode) & 0o022, "bash env template is group/other writable")
        allowed, denied, _ = flag_arrays()
        self.assertIn("Bash(pnpm check*)", allowed)
        for must in ("Bash(git push*)", "Bash(gh *)", "Bash(git commit*)"):
            self.assertIn(must, denied)
        md = open_read(os.path.join(RUNNER_DIR, "claude-run-flags.md"))
        dis = md.split("## Disallowed")[1].split("## Allowed")[0]
        alw = md.split("## Allowed")[1].split("## Changes")[0]
        bullets = lambda s: re.findall(r"^- `(.*)`$", s, re.M)
        self.assertEqual(bullets(dis), denied)
        self.assertEqual(bullets(alw), allowed)

    def test_limit_error_logged(self):
        self.run_runner(["--task-type", "rebase", "--run-id", "rl1"], FAKE_CLAUDE_MODE="ratelimit", FAKE_CLAUDE_RC="1")
        fin = self.logs_jsonl("runs.jsonl")[-1]
        self.assertTrue(fin["limit_hit"])
        self.assertEqual(fin["rc"], 1)
        kinds = [u["kind"] for u in self.logs_jsonl("usage.jsonl")]
        self.assertIn("limit_hit", kinds)
        self.assertEqual([u["status"] for u in self.logs_jsonl("usage.jsonl") if u["kind"] == "rate_limit_event"], ["rejected"])


if __name__ == "__main__":
    unittest.main()
