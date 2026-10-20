"""The fail-closed test sandbox (helpers.py): temp KIT_HOME from the example config, path guard, process guard."""
import json, os, shutil, subprocess, sys, tempfile, time, unittest
import helpers
from helpers import TempEnv, PATH_KEYS, OPTIONAL_EMPTY, FAKE_CLAUDE, FAKEBIN, BIN, RUNNER_DIR, TEST_TZ, ABORT_EXIT


def leaf_paths(o, pre=()):
    if isinstance(o, dict) and o:
        for k, v in o.items():
            yield from leaf_paths(v, pre + (k,))
    else:
        yield pre


def get(o, path):
    for k in path:
        o = o[k]
    return o


class ConfigFromExampleTests(unittest.TestCase):
    def setUp(self):
        with open(helpers.EXAMPLE_CONFIG) as f:
            self.example = json.load(f)
        with open(helpers.TEST_OVERLAY) as f:
            self.overlay = json.load(f)

    def test_every_path_key_resolves_inside_the_temp_kit_home(self):
        with TempEnv() as t:
            self.assertEqual(helpers.check_sandbox(t.cfg, t.d), [])
            for sect, key in PATH_KEYS:
                v = t.cfg[sect][key]
                if (sect, key) in OPTIONAL_EMPTY and v == "":
                    continue
                self.assertTrue(os.path.realpath(os.path.expanduser(v)).startswith(t.d + os.sep), (sect, key))
            self.assertTrue(os.environ["CR_CONFIG"].startswith(t.d + os.sep))

    def test_overlay_only_adds_keys(self):
        ex = {p for p in leaf_paths(self.example)}
        for p in leaf_paths(self.overlay):
            if p and not str(p[0]).startswith("_"):
                self.assertNotIn(p, ex, "overlay overrides example key %s" % ".".join(p))
        with self.assertRaises(ValueError):
            helpers._add_only({"policy": {"total_cap": 4}}, {"policy": {"total_cap": 9}})
        with self.assertRaises(ValueError):
            helpers._add_only({"usage": {"probe_fallback": "none"}}, {"usage": {"probe_fallback": "tmux"}})

    def test_example_values_reach_the_tests(self):
        # The operating-limit tests read the example config's own values, never an overlay copy.
        env_set = {("paths", "logs"), ("paths", "queue"), ("backlog", "state_file"), ("usage", "projects_dir")}
        with TempEnv() as t:
            for p in leaf_paths(self.example):
                if p[0].startswith("_") or p in env_set or get(self.example, p) == {}:
                    continue
                want = helpers._subst(get(self.example, p), t.d)
                self.assertEqual(get(t.cfg, p), want, ".".join(p))
            self.assertEqual(t.cfg["backlog"]["quiet_hours"]["tz"], TEST_TZ)
            self.assertFalse(t.cfg["runner"]["enabled"])
            self.assertFalse(t.cfg["backlog"]["enabled"])

    def test_no_placeholder_left(self):
        with TempEnv() as t:
            with open(t.config) as f:
                self.assertNotIn("${", f.read())


class PathGuardTests(unittest.TestCase):
    def setUp(self):
        self.t = TempEnv().__enter__()
        self.outside = tempfile.mkdtemp(prefix="crtest-outside-")

    def tearDown(self):
        shutil.rmtree(self.outside, ignore_errors=True)
        self.t.__exit__()

    def bad_after(self, sect, key, value):
        cfg = json.loads(json.dumps(self.t.cfg))
        cfg[sect][key] = value
        return helpers.check_sandbox(cfg, self.t.d)

    def test_each_path_key_outside_is_caught(self):
        for sect, key in PATH_KEYS:
            with self.subTest(key="%s.%s" % (sect, key)):
                self.assertEqual(self.bad_after(sect, key, os.path.join(self.outside, "x")), ["%s.%s" % (sect, key)])

    def test_missing_relative_unresolved_dotdot_and_tilde_are_caught(self):
        self.assertEqual(self.bad_after("paths", "logs", ""), ["paths.logs (missing)"])
        self.assertEqual(self.bad_after("paths", "logs", "relative/logs"), ["paths.logs"])
        self.assertEqual(self.bad_after("paths", "logs", "${KIT_HOME}/runner/logs"), ["paths.logs"])
        self.assertEqual(self.bad_after("paths", "logs", os.path.join(self.t.d, "..", "x")), ["paths.logs"])
        self.assertEqual(self.bad_after("usage", "probe_dir", "~/../../x"), ["usage.probe_dir"])
        cfg = json.loads(json.dumps(self.t.cfg)); del cfg["runner"]["pidfile"]
        self.assertEqual(helpers.check_sandbox(cfg, self.t.d), ["runner.pidfile (missing)"])
        self.assertEqual(self.bad_after("runner", "env_file", ""), [])  # empty = no env file

    def test_symlink_escape_is_caught(self):
        link = os.path.join(self.t.d, "escape")
        os.symlink(self.outside, link)
        self.assertEqual(self.bad_after("runner", "stop_file", os.path.join(link, "stop")), ["runner.stop_file"])

    def test_unknown_path_like_values_are_caught(self):
        cfg = json.loads(json.dumps(self.t.cfg))
        cfg["usage"]["extra_dir"] = os.path.join(self.outside, "y")
        cfg["routes"]["docs"]["note"] = "~/../../outside"  # HOME is <KIT_HOME>/home
        self.assertEqual(helpers.check_sandbox(cfg, self.t.d), ["usage.extra_dir", "routes.docs.note"])

    def test_env_overrides_are_checked(self):
        cfg = self.t.cfg
        for k in helpers.PATH_ENV:
            with self.subTest(env=k):
                env = dict(os.environ, **{k: os.path.join(self.outside, "z")})
                self.assertEqual(helpers.check_sandbox(cfg, self.t.d, env), ["env " + k])
        env = dict(os.environ, CLAUDE_BIN="/usr/bin/claude")
        self.assertEqual(helpers.check_sandbox(cfg, self.t.d, env), ["env CLAUDE_BIN"])
        env = dict(os.environ); env.pop("CR_TEST_NO_REAL_CLAUDE")
        self.assertEqual(helpers.check_sandbox(cfg, self.t.d, env), ["env CR_TEST_NO_REAL_CLAUDE"])

    def test_escape_aborts_the_whole_run(self):
        # In a child interpreter: enforce_sandbox on an escaping config ends the process with ABORT_EXIT and
        # names the key only (never the value).
        script = os.path.join(self.t.d, "child.py")
        with open(script, "w") as f:
            f.write("import sys, os\nsys.path.insert(0, %r)\nimport helpers\n"
                    "helpers.enforce_sandbox({'paths': {'logs': %r}}, %r)\nprint('not reached')\n"
                    % (os.path.dirname(helpers.__file__), os.path.join(self.outside, "secret-dir"), self.t.d))
        r = subprocess.run([sys.executable, "-B", script], capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, ABORT_EXIT, r.stderr)
        self.assertNotIn("not reached", r.stdout)
        self.assertIn("paths.logs", r.stderr)
        self.assertNotIn("secret-dir", r.stderr)

    def test_tempenv_entry_checks_before_the_test_body(self):
        # An escaping override already in the environment (CR_RUNNER -> paths.runner) aborts at TempEnv entry.
        script = os.path.join(self.t.d, "child3.py")
        with open(script, "w") as f:
            f.write("import os, sys\nsys.path.insert(0, %r)\nimport helpers\nos.environ['CR_RUNNER'] = %r\n"
                    "helpers.TempEnv().__enter__()\nprint('not reached')\n"
                    % (os.path.dirname(helpers.__file__), os.path.join(self.outside, "run-claude.sh")))
        r = subprocess.run([sys.executable, "-B", script], capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, ABORT_EXIT, r.stderr)
        self.assertNotIn("not reached", r.stdout)
        self.assertIn("paths.runner", r.stderr)

    def test_tempenv_exit_rechecks(self):
        script = os.path.join(self.t.d, "child2.py")
        with open(script, "w") as f:
            f.write("import sys\nsys.path.insert(0, %r)\nimport helpers\nt = helpers.TempEnv().__enter__()\n"
                    "t.cfg['backlog']['queue'] = %r\nt.__exit__()\nprint('not reached')\n"
                    % (os.path.dirname(helpers.__file__), os.path.join(self.outside, "queue.yaml")))
        r = subprocess.run([sys.executable, "-B", script], capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, ABORT_EXIT, r.stderr)
        self.assertIn("backlog.queue", r.stderr)


class ProcessGuardTests(unittest.TestCase):
    def test_refused_programs(self):
        with TempEnv() as t:
            for argv in (["claude", "-p", "/usage"], ["/usr/local/bin/claude"], ["env", "-u", "X", "claude", "-p", "x"],
                         [os.path.join(BIN, "run-claude.sh"), "t1", t.d], [sys.executable, os.path.join(BIN, "cr")],
                         ["tmux", "capture-pane"], ["pkill", "-f", "x"], ["kill", "1"],
                         ["git", "-C", RUNNER_DIR, "status"], ["git", "status"]):
                with self.subTest(argv=argv[0]):
                    self.assertIsNotNone(helpers.refused(argv, cwd=RUNNER_DIR))

    def test_allowed_programs(self):
        with TempEnv() as t:
            wt = os.path.join(t.d, "wt")
            for argv, cwd in (([FAKE_CLAUDE, "-p", "x"], None), (["git", "-C", wt, "status"], None),
                              (["git", "init", "-q", "-b", "main", wt], RUNNER_DIR), (["git", "status"], wt),
                              ([sys.executable, "-B", "x.py"], None), (["sleep", "0"], None)):
                with self.subTest(argv=argv[0]):
                    self.assertIsNone(helpers.refused(argv, cwd=cwd))

    def test_kit_programs_need_a_sandbox_env(self):
        with TempEnv() as t:
            script, cr = os.path.join(BIN, "run-claude.sh"), os.path.join(BIN, "cr")
            good = dict(os.environ)
            for argv in ([script, "t1", t.d], [sys.executable, "-I", cr, "sched", "status"]):
                with self.subTest(argv=os.path.basename(argv[1] if argv[0] == sys.executable else argv[0])):
                    self.assertIsNone(helpers.refused(argv, env=good))
                    kit_home_only = {k: v for k, v in good.items() if k != "CR_CONFIG"}
                    kit_home_only["KIT_HOME"] = t.d
                    self.assertIsNone(helpers.refused(argv, env=kit_home_only))
                    outside = tempfile.mkdtemp(prefix="crtest-outside-")
                    try:
                        for bad in (dict(good, CR_CONFIG=os.path.join(outside, "router.json")),
                                    dict(good, CR_LOG_DIR=outside), dict(good, CLAUDE_RUN_LOG_DIR=outside),
                                    dict(good, CLAUDE_BIN="/usr/bin/claude"),
                                    {k: v for k, v in good.items() if k != "CR_TEST_NO_REAL_CLAUDE"},
                                    {k: v for k, v in good.items() if k != "CLAUDE_BIN"},
                                    dict({k: v for k, v in good.items() if k != "CR_CONFIG"},
                                         KIT_HOME=outside), None):
                            self.assertIsNotNone(helpers.refused(argv, env=bad))
                    finally:
                        shutil.rmtree(outside, ignore_errors=True)
            # A copy of the script outside bin/ is never the kit's own program.
            copy = os.path.join(t.d, "run-claude.sh")
            shutil.copyfile(script, copy)
            self.assertIsNotNone(helpers.refused([copy, "t1", t.d], env=good))

    def test_signals_only_to_own_children(self):
        with TempEnv():
            child = subprocess.Popen(["sleep", "30"])
            try:
                helpers._audit("os.kill", (child.pid, 15))  # our own child: allowed
            finally:
                child.kill(); child.wait()
            for args in ((os.getpid(), 15), (os.getppid(), 15), (1, 9), (-1, 9), (0, 15)):
                with self.subTest(args=args):
                    with self.assertRaises(PermissionError):
                        helpers._audit("os.kill", args)

    def test_hook_blocks_real_starts_and_signals(self):
        # The hook is checked directly for anything that must never run even once (the runner script without the
        # sandbox env, git on the kit repo, a real signal); the one live call below would only reach the fake
        # claude if the hook failed.
        with TempEnv() as t:
            with self.assertRaises(PermissionError):
                subprocess.run(["claude", "--version"], capture_output=True)  # PATH -> fake; still refused by name
            plain = {"PATH": os.environ["PATH"], "HOME": os.environ["HOME"]}
            for event, args in (("subprocess.Popen", (None, [os.path.join(BIN, "run-claude.sh")], None, plain)),
                                ("subprocess.Popen", (None, ["git", "status"], RUNNER_DIR, None)),
                                ("os.exec", (os.path.join(BIN, "cr"), [os.path.join(BIN, "cr")], plain)),
                                ("os.system", (b"tmux ls",)),
                                ("os.kill", (os.getpid(), 15)), ("os.killpg", (1, 9))):
                with self.subTest(event=event, args=str(args)[:40]):
                    with self.assertRaises(PermissionError):
                        helpers._audit(event, args)
            helpers._audit("os.kill", (os.getpid(), 0))  # signal 0 (a liveness probe) is allowed
            helpers._audit("subprocess.Popen", (None, ["git", "-C", t.d, "status"], None, None))
            r = subprocess.run([FAKE_CLAUDE, "-p", "x", "--output-format", "json"], capture_output=True, text=True,
                               timeout=60)
            self.assertEqual(json.loads(r.stdout)["type"], "result")

    def test_process_pins(self):
        self.assertEqual(os.environ["CR_TEST_NO_REAL_CLAUDE"], "1")
        self.assertEqual(os.environ["CLAUDE_BIN"], FAKE_CLAUDE)
        self.assertEqual(shutil.which("claude"), FAKE_CLAUDE)
        self.assertTrue(os.access(FAKE_CLAUDE, os.X_OK))
        self.assertEqual((os.environ["GIT_CONFIG_GLOBAL"], os.environ["GIT_CONFIG_NOSYSTEM"]), (os.devnull, "1"))
        self.assertFalse([k for k in os.environ if k.startswith("GIT_") and k not in
                          ("GIT_CONFIG_GLOBAL", "GIT_CONFIG_NOSYSTEM", "GIT_TERMINAL_PROMPT")])
        self.assertNotIn("ANTHROPIC_API_KEY", os.environ)
        self.assertEqual(time.strftime("%z"), "+0300")
        self.assertTrue(os.environ["HOME"].startswith(helpers.SESSION_HOME + os.sep))
        self.assertTrue(os.environ["CR_CONFIG"].startswith(helpers.SESSION_HOME + os.sep))

    def test_tz_pinned_on_any_host(self):
        # A host in another zone (here: a child started with TZ=UTC) still sees UTC+3 once helpers is imported.
        code = os.path.join(helpers.SESSION_HOME, "tzchild.py")
        with open(code, "w") as f:
            f.write("import sys, time\nsys.path.insert(0, %r)\nimport helpers\nprint(time.strftime('%%z'))\n"
                    % os.path.dirname(helpers.__file__))
        r = subprocess.run([sys.executable, "-B", code], capture_output=True, text=True, timeout=60,
                           env=dict(os.environ, TZ="UTC"))
        self.assertEqual((r.returncode, r.stdout.strip()), (0, "+0300"), r.stderr)

    def test_default_config_is_never_used(self):
        from crlib import common
        self.assertFalse(os.path.exists(common.DEFAULT_CONFIG))  # no router.json next to the code
        self.assertNotEqual(os.path.realpath(os.environ["CR_CONFIG"]), os.path.realpath(common.DEFAULT_CONFIG))

    def test_tempenv_restores_env_and_removes_dir(self):
        before = dict(os.environ)
        with TempEnv() as t:
            d = t.d
            os.environ["CR_NOW"] = "2026-10-15T17:30:00+03:00"
        self.assertEqual(dict(os.environ), before)
        self.assertFalse(os.path.exists(d))


class RunnerScriptTests(unittest.TestCase):
    """Static checks on the parameterized run-claude.sh and on the suite that runs it."""
    def test_api_key_refused_before_anything_is_read(self):
        with open(os.path.join(BIN, "run-claude.sh")) as f:
            lines = [l.strip() for l in f]
        code = [l for l in lines if l and not l.startswith("#")]
        self.assertEqual(code[0], "set -u")
        self.assertNotIn("not parameterized yet", "\n".join(lines))
        first_check = min(i for i, l in enumerate(code) if l == "refuse_api_key")
        first_config = min(i for i, l in enumerate(code) if "config --tsv" in l)
        first_source = min(i for i, l in enumerate(code) if l.startswith(". "))
        self.assertLess(first_check, first_config)
        self.assertLess(first_config, first_source)
        self.assertEqual(code[first_source + 1], "refuse_api_key")  # again after the env file

    def test_tests_that_start_the_runner_are_not_skipped(self):
        import unittest as u
        suite = u.TestLoader().discover(os.path.dirname(helpers.__file__), pattern="test_*.py")
        skipped = {}

        def walk(s):
            for x in s:
                if isinstance(x, u.TestSuite):
                    walk(x)
                else:
                    m = getattr(x, x._testMethodName, None)
                    why = getattr(m, "__unittest_skip_why__", None) or getattr(type(x), "__unittest_skip_why__", None)
                    if why is None and type(x).__name__ == "ModuleImportFailure":
                        why = str(getattr(x, "_exception", ""))
                    skipped[x.id()] = why
        walk(suite)
        want = ("test_sched.TickTests.test_end_to_end_with_runner_and_fake_claude",
                "test_operating_limits.ProbeCadenceTests.test_usage_loop_cli_retired",
                "test_queue_runner.LoopLifecycleTests.test_pidfile_and_sigterm",
                "test_queue_runner.LoopLifecycleTests.test_cr_sched_stop")
        for tid in want:
            self.assertIn(tid, skipped)
            self.assertIsNone(skipped[tid], tid)
        runner_ids = [k for k in skipped if k.startswith("test_runner.")]
        self.assertGreaterEqual(len(runner_ids), 10)
        self.assertEqual([k for k in runner_ids if skipped[k] is not None], [])
        self.assertEqual([k for k, why in skipped.items() if why is not None], [], "skipped runner tests")


if __name__ == "__main__":
    unittest.main()
