"""run-claude.sh reads every file it uses from router.json under ${KIT_HOME} (parameterization table, script rows).

Each test first requires the old "not parameterized yet" guard to be gone; otherwise it FAILS without executing
anything. The script runs in the sandbox: a temp KIT_HOME, CR_CONFIG inside it, the fake claude (CLAUDE_BIN) and fake pgrep /
pkill first on PATH, so nothing on the machine is touched. The audit hook (helpers.py) starts
run-claude.sh only inside the sandbox. Contract:
  * runner.env_file: "" -> nothing sourced; set -> sourced; set but missing -> refuse before claude, naming the key.
  * runner.flags_file: sourced for the allow / deny / unset lists; missing -> refuse before claude, naming the key.
  * runner.bash_env_file -> CLAUDE_ENV_FILE of the claude process.
  * runner.prompts_dir: without PROMPT_FILE the prompt is <prompts_dir>/common.md + <prompts_dir>/<label>.md.
  * paths.logs: the output and runs.jsonl go there (no CLAUDE_RUN_LOG_DIR / CR_LOG_DIR needed).
  * CLAUDE_ROUTER_DIR defaults to the script's own runner dir (bin/..); the config defaults to
    ${KIT_HOME}/runner/router.json when CR_CONFIG is unset.
  * runner.mcp_cleanup_pattern: "" -> no pkill call at all; set -> `pkill -f <pattern>` only when pgrep finds no
    other `claude -p`.
  * ANTHROPIC_API_KEY set (also by the env file) -> exit 99, claude never starts."""
import json, os, stat, subprocess, unittest
import k5support as K
from k5support import TempEnv, SCRIPT
from crlib.common import read_jsonl

FLAGS = 'CLAUDE_ALLOWED=("Read" "Edit")\nCLAUDE_DISALLOWED=("Bash(git push*)" "Bash(gh *)")\nCLAUDE_UNSET_ENV=()\n'
FAKE_TOOL = "#!/bin/sh\nprintf '%%s\\n' \"$*\" >> \"%s\"\nexit %d\n"


class ScriptCase(unittest.TestCase):
    def setUp(self):
        self.t = TempEnv().__enter__()
        d = self.d = self.t.d
        self.wt = os.path.join(d, "wt"); os.makedirs(self.wt)
        self.rec = os.path.join(d, "claude-rec.jsonl")
        self.pkill_rec, self.pgrep_rec = os.path.join(d, "pkill.rec"), os.path.join(d, "pgrep.rec")
        self.sbin = os.path.join(d, "sbin"); os.makedirs(self.sbin)
        self.fake_tool("pkill", self.pkill_rec, 0)
        self.fake_tool("pgrep", self.pgrep_rec, 1)  # 1 = no other `claude -p` running
        self.prompt = os.path.join(d, "prompt.md")
        with open(self.prompt, "w") as f:
            f.write("say OK")
        rc = self.t.cfg["runner"]
        with open(rc["flags_file"], "w") as f:
            f.write(FLAGS)
        with open(rc["bash_env_file"], "w") as f:
            f.write("# example bash env for claude's Bash tool\n")

    def tearDown(self):
        self.t.__exit__()

    def fake_tool(self, name, record, rc):
        p = os.path.join(self.sbin, name)
        with open(p, "w") as f:
            f.write(FAKE_TOOL % (record, rc))
        os.chmod(p, 0o755)

    def config(self, fn):
        K.edit_config(self.t, fn)

    def env(self, drop=(), **kw):
        e = {k: v for k, v in os.environ.items()
             if k not in ("ANTHROPIC_API_KEY", "CLAUDE_ROUTER_DIR", "CLAUDE_RUN_LOG_DIR", "CLAUDE_RUNNER_SKIP_PKILL",
                          "CLAUDE_ROUTE_MODEL", "CLAUDE_RUNNER_STREAM") + tuple(drop)}
        e.update({"PATH": self.sbin + os.pathsep + os.environ["PATH"], "FAKE_CLAUDE_RECORD": self.rec,
                  "PROMPT_FILE": self.prompt, "KIT_HOME": self.d})
        e.update(kw)
        return {k: v for k, v in e.items() if v is not None}

    def run_script(self, args=(), env=None):
        self.assertFalse(K.script_guarded(), "run-claude.sh still refuses to run (the parameterization is not done)")
        try:
            return subprocess.run([SCRIPT] + list(args) + ["t1", self.wt], capture_output=True, text=True,
                                  env=env or self.env(), timeout=120)
        except PermissionError as e:
            self.fail("the sandbox refused run-claude.sh (helpers' audit hook must allow it): %s" % e)

    def records(self):
        return read_jsonl(self.rec)

    def claude_argv(self):
        recs = self.records()
        self.assertEqual(len(recs), 1, "expected exactly one (fake) claude start")
        return recs[0]["argv"]

    def assert_ran(self, r):
        self.assertEqual(r.returncode, 0, r.stderr[-2000:])
        return self.claude_argv()

    def assert_refused(self, r, name, code=None):
        self.assertNotEqual(r.returncode, 0)
        if code is not None:
            self.assertEqual(r.returncode, code)
        self.assertEqual(self.records(), [], "claude started")
        if name:
            self.assertIn(name, r.stderr)


class EnvFileTests(ScriptCase):
    def sentinel(self, path, marker):
        with open(path, "w") as f:
            f.write("echo sourced >> %s\n" % marker)

    def test_empty_env_file_sources_nothing(self):
        marker = os.path.join(self.d, "sourced.marker")
        for p in (os.path.join(self.d, "env.sh"), os.path.join(self.d, "runner", "env.sh"),
                  os.path.join(self.d, "home", "env.sh")):
            self.sentinel(p, marker)
        self.assertEqual(self.t.cfg["runner"]["env_file"], "")
        r = self.run_script()
        self.assert_ran(r)
        self.assertFalse(os.path.exists(marker), "an env file was sourced although runner.env_file is empty")
        self.assertNotIn("No such file", r.stderr)
        self.assertNotRegex(r.stderr, r"run-claude\.sh: line \d+:", "bash error while running the script")

    def test_configured_env_file_is_sourced(self):
        marker = os.path.join(self.d, "sourced.marker")
        envf = os.path.join(self.d, "example-env.sh")
        self.sentinel(envf, marker)
        self.config(lambda c: c["runner"].update(env_file=envf))
        self.assert_ran(self.run_script())
        self.assertTrue(os.path.exists(marker))

    def test_missing_env_file_refuses(self):
        self.config(lambda c: c["runner"].update(env_file=os.path.join(self.d, "missing-env.sh")))
        self.assert_refused(self.run_script(), "runner.env_file")


class FlagsAndBashEnvTests(ScriptCase):
    def test_flags_come_from_the_configured_file(self):
        argv = self.assert_ran(self.run_script())
        ia, idn = argv.index("--allowedTools"), argv.index("--disallowedTools")
        self.assertEqual(argv[ia + 1:idn], ["Read", "Edit"])
        self.assertEqual(argv[idn + 1:], ["Bash(git push*)", "Bash(gh *)"])

    def test_missing_flags_file_refuses(self):
        os.remove(self.t.cfg["runner"]["flags_file"])
        self.assert_refused(self.run_script(), "runner.flags_file")

    def test_claude_env_file_is_the_configured_bash_env_file(self):
        custom = os.path.join(self.d, "runner", "custom-bash-env.sh")
        with open(custom, "w") as f:
            f.write("# example\n")
        self.config(lambda c: c["runner"].update(bash_env_file=custom))
        self.assert_ran(self.run_script())
        self.assertEqual(self.records()[0]["claude_env_file"], custom)


class PromptsAndLogsTests(ScriptCase):
    def test_prompt_from_prompts_dir(self):
        pd = self.t.cfg["runner"]["prompts_dir"]
        with open(os.path.join(pd, "common.md"), "w") as f:
            f.write("EXAMPLE COMMON RULES")
        with open(os.path.join(pd, "t1.md"), "w") as f:
            f.write("EXAMPLE JOB T1")
        argv = self.assert_ran(self.run_script(env=self.env(PROMPT_FILE=None)))
        prompt = argv[argv.index("-p") + 1]
        self.assertIn("EXAMPLE COMMON RULES", prompt)
        self.assertIn("EXAMPLE JOB T1", prompt)
        self.assertLess(prompt.index("EXAMPLE COMMON RULES"), prompt.index("EXAMPLE JOB T1"))

    def test_outputs_go_to_the_configured_logs(self):
        alt = os.path.join(self.d, "runner", "logs-alt")
        os.makedirs(alt)
        self.config(lambda c: c["paths"].update(logs=alt))
        self.assert_ran(self.run_script(env=self.env(drop=("CR_LOG_DIR",))))
        self.assertTrue(os.path.isfile(os.path.join(alt, "claude-t1.json")))
        events = [r.get("event") for r in read_jsonl(os.path.join(alt, "runs.jsonl"))]
        self.assertEqual(events, ["start", "finish"])
        self.assertFalse(os.path.exists(os.path.join(self.t.logs, "claude-t1.json")))

    def test_router_dir_defaults_to_the_kit_runner_dir(self):
        argv = self.assert_ran(self.run_script(["--task-type", "docs", "--run-id", "k5route1"]))
        self.assertIn("--model", argv)
        self.assertTrue(os.path.isfile(os.path.join(self.t.logs, "streams", "k5route1.jsonl")))

    def test_config_found_from_kit_home(self):
        self.assert_ran(self.run_script(env=self.env(drop=("CR_CONFIG", "CR_LOG_DIR"))))
        self.assertTrue(os.path.isfile(os.path.join(self.t.logs, "claude-t1.json")))


class McpCleanupTests(ScriptCase):
    def test_empty_pattern_never_calls_pkill(self):
        self.assertEqual(self.t.cfg["runner"]["mcp_cleanup_pattern"], "")
        self.assert_ran(self.run_script())
        self.assertFalse(os.path.exists(self.pkill_rec), "pkill was called with mcp_cleanup_pattern empty")

    def test_pattern_set_calls_pkill_with_it(self):
        self.config(lambda c: c["runner"].update(mcp_cleanup_pattern="example-mcp-server --stdio"))
        self.assert_ran(self.run_script())
        self.assertEqual(K.read(self.pkill_rec).splitlines(), ["-f example-mcp-server --stdio"])

    def test_pattern_set_but_other_claude_running_leaves_it_alone(self):
        self.fake_tool("pgrep", self.pgrep_rec, 0)  # another `claude -p` is running
        self.config(lambda c: c["runner"].update(mcp_cleanup_pattern="example-mcp-server --stdio"))
        self.assert_ran(self.run_script())
        self.assertFalse(os.path.exists(self.pkill_rec))


class ApiKeyTests(ScriptCase):
    def test_api_key_in_env_refuses(self):
        for value in ("example-not-a-real-key-0000", ""):
            with self.subTest(empty=value == ""):
                self.assert_refused(self.run_script(env=self.env(ANTHROPIC_API_KEY=value)), "ANTHROPIC_API_KEY", 99)

    def test_api_key_from_env_file_refuses(self):
        envf = os.path.join(self.d, "example-env.sh")
        with open(envf, "w") as f:
            f.write("export ANTHROPIC_API_KEY=example-not-a-real-key-0000\n")
        self.config(lambda c: c["runner"].update(env_file=envf))
        self.assert_refused(self.run_script(), "ANTHROPIC_API_KEY", 99)


if __name__ == "__main__":
    unittest.main()
