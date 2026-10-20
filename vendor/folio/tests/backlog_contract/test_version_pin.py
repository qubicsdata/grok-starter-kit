"""The contract suite is bound to exactly Backlog.md 1.53.0 and fails (never skips) on any other version."""

import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from . import support, test_backlog_facts
from .support import BACKLOG_VERSION, BIN_ENV, BacklogContractCase, BacklogRunner

REPO_ROOT = Path(__file__).resolve().parents[2]
LOCK_PATH = REPO_ROOT / "folio" / "locks" / "backlog.lock.json"
LOCK_SKIP_REASON = "folio/locks/backlog.lock.json arrives in WP-9; WP-9 removes this skip"


def write_fake_backlog(directory, version):
    """A stand-in binary that records its argv and prints `version` for --version."""
    log = Path(directory) / "argv.log"
    fake = Path(directory) / "backlog"
    fake.write_text(
        "#!%s\n"
        "import json, sys\n"
        "with open(%r, 'a', encoding='utf-8') as handle:\n"
        "    handle.write(json.dumps(sys.argv[1:]) + '\\n')\n"
        "print(%r)\n" % (sys.executable, str(log), version),
        encoding="utf-8",
    )
    fake.chmod(0o700)
    return fake, log


def probe_case():
    # Defined here, not at module level, so discovery does not collect it.
    class Probe(BacklogContractCase):
        def runTest(self):
            pass

    return Probe()


def logged_argvs(log):
    if not log.exists():
        return []
    return [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]


class VersionPinTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="folio-backlog-fake-")
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)

    def run_contract_suite(self, binary):
        suite = unittest.defaultTestLoader.loadTestsFromModule(test_backlog_facts)
        stream = io.StringIO()
        with mock.patch.dict(os.environ, {BIN_ENV: str(binary)}):
            result = unittest.TextTestRunner(stream=stream, verbosity=0).run(suite)
        return suite, result

    def test_contract_suite_fails_not_skips_on_backlog_1_54_0(self):
        fake, log = write_fake_backlog(self.dir, "1.54.0")
        suite, result = self.run_contract_suite(fake)

        self.assertGreaterEqual(suite.countTestCases(), 10)
        self.assertEqual(result.testsRun, suite.countTestCases())
        self.assertFalse(result.wasSuccessful())
        self.assertEqual(result.skipped, [])
        self.assertEqual(result.errors, [])
        self.assertEqual(len(result.failures), suite.countTestCases())
        for _test, trace in result.failures:
            self.assertIn("reports Backlog.md '1.54.0'; the contract suite is pinned to exactly 1.53.0", trace)
        # The version check runs before any repo is built: the fake only ever saw --version.
        self.assertEqual(logged_argvs(log), [["--version"]])

    def test_version_must_match_exactly(self):
        for index, version in enumerate(("1.54.0", "1.53.1", "1.52.0", "1.53.0-rc.1", "v1.53.0", "1.53", "")):
            with self.subTest(version=version):
                directory = self.dir / str(index)
                directory.mkdir()
                fake, _log = write_fake_backlog(directory, version)
                with mock.patch.dict(os.environ, {BIN_ENV: str(fake)}):
                    case = probe_case()
                    with self.assertRaises(AssertionError) as raised:
                        case.setUp()
                    case.doCleanups()
                self.assertIn("pinned to exactly 1.53.0", str(raised.exception))

    def test_matching_fake_version_passes_the_pin(self):
        fake, log = write_fake_backlog(self.dir, BACKLOG_VERSION)
        with mock.patch.dict(os.environ, {BIN_ENV: str(fake)}):
            case = probe_case()
            case.setUp()
            case.doCleanups()
        self.assertEqual(logged_argvs(log), [["--version"]])

    def without_bin(self, **extra):
        environ = {key: value for key, value in os.environ.items() if key not in (BIN_ENV, support.OPT_OUT_ENV)}
        environ.update(extra)
        return mock.patch.dict(os.environ, environ, clear=True)

    def test_unset_binary_fails_with_explicit_message(self):
        """review r1 H-1 (R-c): no FOLIO_BACKLOG_BIN is a FAILURE, not a silent skip."""
        with self.without_bin():
            case = probe_case()
            with self.assertRaises(AssertionError) as raised:
                case.setUp()
            case.doCleanups()
        self.assertNotIsInstance(raised.exception, unittest.SkipTest)
        self.assertIn(support.UNSET_MESSAGE, str(raised.exception))
        self.assertIn(BIN_ENV, support.UNSET_MESSAGE)
        self.assertIn("%s=%s" % (support.OPT_OUT_ENV, support.OPT_OUT_VALUE), support.UNSET_MESSAGE)

    def test_contract_suite_fails_not_skips_without_the_binary(self):
        suite = unittest.defaultTestLoader.loadTestsFromModule(test_backlog_facts)
        with self.without_bin():
            result = unittest.TextTestRunner(stream=io.StringIO(), verbosity=0).run(suite)
        self.assertGreaterEqual(suite.countTestCases(), 10)
        self.assertEqual(result.skipped, [])
        self.assertEqual(len(result.failures), suite.countTestCases())

    def test_explicit_opt_out_skips_and_prints_that_it_did(self):
        stderr = io.StringIO()
        with self.without_bin(**{support.OPT_OUT_ENV: support.OPT_OUT_VALUE}), mock.patch("sys.stderr", stderr):
            support._ANNOUNCED.clear()
            case = probe_case()
            with self.assertRaises(unittest.SkipTest) as raised:
                case.setUp()
        self.assertEqual(str(raised.exception), support.OPT_OUT_REASON)
        self.assertIn("%s=%s" % (support.OPT_OUT_ENV, support.OPT_OUT_VALUE), support.OPT_OUT_REASON)
        self.assertIn(support.OPT_OUT_REASON, stderr.getvalue())

    def test_any_other_opt_out_value_still_fails(self):
        for value in ("1", "true", "yes", "SKIP", " skip", ""):
            with self.subTest(value=value), self.without_bin(**{support.OPT_OUT_ENV: value}):
                case = probe_case()
                with self.assertRaises(AssertionError) as raised:
                    case.setUp()
                case.doCleanups()
                self.assertNotIsInstance(raised.exception, unittest.SkipTest)

    def test_pin_constant(self):
        self.assertEqual(BACKLOG_VERSION, "1.53.0")

    @unittest.skip(LOCK_SKIP_REASON)
    def test_lock_backlog_version_matches_pin(self):
        lock = json.loads(LOCK_PATH.read_text(encoding="utf-8"))
        self.assertEqual(lock["backlog_version"], "1.53.0")
        self.assertEqual(lock["backlog_version"], BACKLOG_VERSION)

    def test_lock_skip_reason_names_wp9(self):
        self.assertEqual(LOCK_SKIP_REASON, "folio/locks/backlog.lock.json arrives in WP-9; WP-9 removes this skip")
        self.assertFalse(LOCK_PATH.exists(), "the lock arrived: WP-9 must remove the skip on test_lock_backlog_version_matches_pin")


class RealBinaryVersionTests(BacklogContractCase):
    def test_real_binary_reports_exactly_1_53_0(self):
        self.assertEqual(BacklogRunner(support.backlog_bin(), self.home).version(), "1.53.0")
