"""Tests for the `folio` step of tools/ci_local.py (runs Folio's own suite in place, only with --with-folio).

The step is pointed at a temp root holding a fake vendor/folio/tests suite, so these tests never run the
real Folio suite. Stdlib only, Python 3.9+.
"""

import importlib.util
import io
import json
import os
import shutil
import stat
import tempfile
import textwrap
import unittest
import unittest.mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CI_LOCAL = os.path.join(ROOT, "tools", "ci_local.py")
BIN_ENV = "FOLIO_BACKLOG_BIN"
OPT_OUT_ENV = "FOLIO_BACKLOG_CONTRACT"
OUT_ENV = "KIT_FOLIO_FAKE_OUT"

PASSING = '''
import json, os, unittest

class FakeTest(unittest.TestCase):
    def test_records_the_environment(self):
        out = os.environ.get("KIT_FOLIO_FAKE_OUT")
        if out:
            with open(out, "w", encoding="utf-8") as handle:
                json.dump({"cwd": os.getcwd(), "bin": os.environ.get("FOLIO_BACKLOG_BIN"),
                           "opt_out": os.environ.get("FOLIO_BACKLOG_CONTRACT"),
                           "no_bytecode": os.environ.get("PYTHONDONTWRITEBYTECODE")}, handle)
        # A Folio CLI subprocess run with -I leaves a bytecode cache; the step must remove it.
        os.makedirs(os.path.join("folio", "__pycache__"), exist_ok=True)
        with open(os.path.join("folio", "__pycache__", "cli.cpython-39.pyc"), "wb") as handle:
            handle.write(b"\\x00")

    def test_second(self):
        pass

    @unittest.skip("fake skip")
    def test_skipped(self):
        pass
'''

FAILING = '''
import unittest

class FakeTest(unittest.TestCase):
    def test_fails(self):
        self.fail("planted failure")
'''

EMPTY = '''
import unittest
'''


def _load():
    spec = importlib.util.spec_from_file_location("ci_local", CI_LOCAL)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FolioStepTest(unittest.TestCase):
    def setUp(self):
        self.ci = _load()
        self.tmp = tempfile.mkdtemp(prefix="kitci-folio-")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.root = os.path.join(self.tmp, "kit")
        self.folio = os.path.join(self.root, "vendor", "folio")
        self.out = os.path.join(self.tmp, "seen.json")
        self.fake_bin = os.path.join(self.tmp, "backlog")
        with open(self.fake_bin, "w", encoding="utf-8") as handle:
            handle.write("#!/bin/sh\nexit 0\n")
        os.chmod(self.fake_bin, stat.S_IRWXU)
        # Every test starts with no Backlog settings from the caller's environment.
        patcher = unittest.mock.patch.dict(os.environ, {OUT_ENV: self.out})
        patcher.start()
        self.addCleanup(patcher.stop)
        for key in (BIN_ENV, OPT_OUT_ENV):
            os.environ.pop(key, None)

    def suite(self, body):
        tests = os.path.join(self.folio, "tests")
        os.makedirs(tests, exist_ok=True)
        with open(os.path.join(tests, "test_fake.py"), "w", encoding="utf-8") as handle:
            handle.write(textwrap.dedent(body))

    def ctx(self, *argv):
        ctx = self.ci.build_context(self.ci.parse_args(list(argv)), io.StringIO())
        ctx.root = self.root
        return ctx

    def seen(self):
        with open(self.out, encoding="utf-8") as handle:
            return json.load(handle)

    def test_without_the_flag_is_skip_and_runs_nothing(self):
        self.suite(PASSING)
        result = self.ci.step_folio(self.ctx())
        self.assertEqual(result.status, self.ci.SKIP)
        self.assertIn("--with-folio", result.reason)
        self.assertFalse(os.path.exists(self.out), "the suite ran without --with-folio")

    def test_with_the_binary_is_pass_with_counts(self):
        self.suite(PASSING)
        os.environ[BIN_ENV] = self.fake_bin
        os.environ[OPT_OUT_ENV] = "skip"  # ignored once a binary is set
        result = self.ci.step_folio(self.ctx("--with-folio"))
        self.assertEqual(result.status, self.ci.PASS, result.reason)
        self.assertEqual(result.reason, "3 tests, 1 skipped")
        seen = self.seen()
        self.assertEqual(os.path.realpath(seen["cwd"]), os.path.realpath(self.folio))
        self.assertEqual(seen["bin"], self.fake_bin)
        self.assertIsNone(seen["opt_out"])
        self.assertEqual(seen["no_bytecode"], "1")

    def test_without_the_binary_runs_with_the_opt_out_and_is_skip(self):
        self.suite(PASSING)
        result = self.ci.step_folio(self.ctx("--with-folio"))
        self.assertEqual(result.status, self.ci.SKIP)
        self.assertIn("3 tests, 1 skipped", result.reason)
        self.assertIn(BIN_ENV, result.reason)
        seen = self.seen()
        self.assertIsNone(seen["bin"])
        self.assertEqual(seen["opt_out"], "skip")

    def test_release_without_the_binary_fails(self):
        self.suite(PASSING)
        step = self.ci.Step("folio", lambda ctx: self.ci.step_folio(self._rooted(ctx)))
        out = io.StringIO()
        code = self.ci.main(["--release", "--with-folio"], steps=[step], out=out)
        self.assertEqual(code, 1)
        self.assertIn("STEP folio: FAIL (release forbids SKIP", out.getvalue())

    def _rooted(self, ctx):
        ctx.root = self.root
        return ctx

    def test_binary_that_is_not_an_executable_file_fails_before_running(self):
        self.suite(PASSING)
        for value in (os.path.join(self.tmp, "missing"), self.tmp):
            with self.subTest(kind="missing" if value != self.tmp else "directory"):
                os.environ[BIN_ENV] = value
                result = self.ci.step_folio(self.ctx("--with-folio"))
                self.assertEqual(result.status, self.ci.FAIL)
                self.assertIn(BIN_ENV, result.reason)
                self.assertNotIn(self.tmp, result.reason)
                self.assertFalse(os.path.exists(self.out))
        plain = os.path.join(self.tmp, "plain")
        with open(plain, "w", encoding="utf-8") as handle:
            handle.write("not executable\n")
        os.chmod(plain, stat.S_IRUSR | stat.S_IWUSR)
        os.environ[BIN_ENV] = plain
        self.assertEqual(self.ci.step_folio(self.ctx("--with-folio")).status, self.ci.FAIL)

    def test_failing_suite_is_fail_with_output(self):
        self.suite(FAILING)
        os.environ[BIN_ENV] = self.fake_bin
        ctx = self.ctx("--with-folio")
        result = self.ci.step_folio(ctx)
        self.assertEqual(result.status, self.ci.FAIL)
        self.assertIn("unittest exit 1", result.reason)
        self.assertIn("FAIL: test_fails", ctx.failure_output)

    def test_failing_suite_without_the_binary_is_still_fail(self):
        self.suite(FAILING)
        self.assertEqual(self.ci.step_folio(self.ctx("--with-folio")).status, self.ci.FAIL)

    def test_empty_suite_is_fail(self):
        self.suite(EMPTY)
        os.environ[BIN_ENV] = self.fake_bin
        result = self.ci.step_folio(self.ctx("--with-folio"))
        self.assertEqual(result.status, self.ci.FAIL)
        self.assertIn("no tests ran", result.reason)

    def test_missing_folio_tests_is_fail(self):
        os.makedirs(self.folio)
        result = self.ci.step_folio(self.ctx("--with-folio"))
        self.assertEqual(result.status, self.ci.FAIL)
        self.assertIn("vendor/folio/tests", result.reason)

    def test_bytecode_caches_under_vendor_folio_are_removed(self):
        self.suite(PASSING)
        keep = os.path.join(self.folio, "folio", "keep.py")
        os.makedirs(os.path.dirname(keep), exist_ok=True)
        with open(keep, "w", encoding="utf-8") as handle:
            handle.write("x = 1\n")
        outside = os.path.join(self.root, "tools", "__pycache__")
        os.makedirs(outside)
        os.environ[BIN_ENV] = self.fake_bin
        self.assertEqual(self.ci.step_folio(self.ctx("--with-folio")).status, self.ci.PASS)
        caches = [d for d, names, _ in os.walk(self.folio) for n in names if n == "__pycache__"]
        self.assertEqual(caches, [], "bytecode cache left under vendor/folio")
        self.assertTrue(os.path.isfile(keep))
        self.assertTrue(os.path.isdir(outside), "a cache outside vendor/folio was touched")

    def test_reason_is_one_line(self):
        self.suite(PASSING)
        for env in ({}, {BIN_ENV: self.fake_bin}):
            with self.subTest(env=sorted(env)), unittest.mock.patch.dict(os.environ, env):
                line = self.ci.format_line("folio", self.ci.step_folio(self.ctx("--with-folio")))
                self.assertRegex(line, r"^STEP folio: (PASS|SKIP) \([^\n]+\)$")


class FolioRegistryTest(unittest.TestCase):
    def test_folio_is_registered_once_and_last(self):
        ci = _load()
        names = [s.name for s in ci.STEPS]
        self.assertEqual(names.count("folio"), 1)
        self.assertEqual(names[-1], "folio")

    def test_fast_mode_skips_folio_without_running_it(self):
        ci = _load()
        step = [s for s in ci.STEPS if s.name == "folio"][0]
        ctx = ci.build_context(ci.parse_args([]), io.StringIO())
        ctx.root = tempfile.mkdtemp(prefix="kitci-folio-none-")
        self.addCleanup(shutil.rmtree, ctx.root, True)
        result = step.run(ctx)
        self.assertEqual(result.status, ci.SKIP)


if __name__ == "__main__":
    unittest.main()
