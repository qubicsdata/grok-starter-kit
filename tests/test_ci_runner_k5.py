"""The `runner-k5` step of tools/ci_local.py runs the runner/tests/k5 suite;
a red suite is a FAIL, never a SKIP."""

import argparse
import os
import shutil
import tempfile
import unittest

from tests.test_ci_local import _load

K5_ARGV = ["discover", "-s", "runner/tests/k5", "-t", "runner/tests/k5"]


class RunnerK5StepTest(unittest.TestCase):
    def setUp(self):
        self.ci = _load()
        self.root = tempfile.mkdtemp(prefix="k5-ci-")
        self.ran = []

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def record_only(self):
        self.ci.unittest_step = lambda ctx, argv: self.ran.append(argv) or self.ci.StepResult(self.ci.PASS, "1 tests")

    def run_step(self, root=None):
        ctx = argparse.Namespace(root=root or self.root, failure_output="")
        return self.ci.step_runner_k5(ctx), ctx

    def write_suite(self, body):
        suite = os.path.join(self.root, "runner", "tests", "k5")
        os.makedirs(suite)
        with open(os.path.join(suite, "test_example.py"), "w") as handle:
            handle.write("import unittest\n\n\nclass ExampleTest(unittest.TestCase):\n    def test_example(self):\n")
            handle.write("        %s\n" % body)

    def test_registered_after_runner_tests(self):
        names = [s.name for s in self.ci.STEPS]
        self.assertEqual(names[names.index("runner-tests") + 1], "runner-k5")

    def test_runs_the_suite_without_looking_at_run_claude(self):
        # No runner/bin/run-claude.sh in the temp root: the step still just runs the suite.
        self.record_only()
        result, _ = self.run_step()
        self.assertEqual(result.status, self.ci.PASS)
        self.assertEqual(self.ran, [K5_ARGV])

    def test_red_suite_fails(self):
        self.write_suite("self.fail('example red test')")
        result, ctx = self.run_step()
        self.assertEqual((result.status, result.reason), (self.ci.FAIL, "unittest exit 1"))
        self.assertIn("example red test", ctx.failure_output)

    def test_green_suite_passes(self):
        self.write_suite("self.assertTrue(True)")
        result, _ = self.run_step()
        self.assertEqual((result.status, result.reason), (self.ci.PASS, "1 tests"))

    def test_missing_suite_fails(self):
        result, _ = self.run_step()
        self.assertEqual(result.status, self.ci.FAIL)

    def test_the_real_tree_runs_the_suite(self):
        # Recorded here, not executed: the gate runs the real suite.
        self.record_only()
        result, _ = self.run_step(self.ci.ROOT)
        self.assertEqual(result.status, self.ci.PASS)
        self.assertEqual(self.ran, [K5_ARGV])


class RunnerScanStepTest(unittest.TestCase):
    """The `runner` step runs the clean-data scan on runner/ only (plus the term list when given)."""

    def setUp(self):
        self.ci = _load()
        self.root = tempfile.mkdtemp(prefix="k5-ci-scan-")
        self.outside = tempfile.mkdtemp(prefix="k5-ci-terms-")
        os.makedirs(os.path.join(self.root, "runner", "bin"))
        self.write("runner/bin/cr", "print('example')\n")

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)
        shutil.rmtree(self.outside, ignore_errors=True)

    def write(self, rel, text):
        with open(os.path.join(self.root, rel), "w") as handle:
            handle.write(text)

    def run_step(self, terms=None):
        ctx = argparse.Namespace(root=self.root, failure_output="", terms_file=terms)
        return self.ci.step_runner(ctx), ctx

    def terms(self, *lines):
        path = os.path.join(self.outside, "terms.tsv")
        with open(path, "w") as handle:
            handle.write("".join(line + "\n" for line in lines))
        return path

    def test_registered_after_runner_k5(self):
        names = [s.name for s in self.ci.STEPS]
        self.assertEqual(names[names.index("runner-k5") + 1], "runner")

    def test_clean_runner_without_terms_skips(self):
        result, _ = self.run_step()
        self.assertEqual((result.status, result.reason), (self.ci.SKIP, "TOTAL 0, not run: terms"))

    def test_clean_runner_with_terms_passes(self):
        result, _ = self.run_step(self.terms("example-forbidden-word"))
        self.assertEqual((result.status, result.reason), (self.ci.PASS, "TOTAL 0"))

    def test_term_in_runner_fails_without_echoing_it(self):
        self.write("runner/bin/cr", "# example-forbidden-word\n")
        result, ctx = self.run_step(self.terms("example-forbidden-word"))
        self.assertEqual(result.status, self.ci.FAIL)
        self.assertIn("TERMS 1", result.reason)
        self.assertNotIn("forbidden", result.reason + ctx.failure_output)

    def test_only_runner_is_scanned(self):
        address = "user" + "@" + "real-domain-example.test\n"  # built at run time: no address in this file
        self.write("outside-runner.md", address)
        result, _ = self.run_step()
        self.assertEqual(result.status, self.ci.SKIP)
        self.write("runner/bin/cr", address)
        result, _ = self.run_step()
        self.assertEqual(result.status, self.ci.FAIL)

    def test_missing_runner_dir_fails(self):
        shutil.rmtree(os.path.join(self.root, "runner"))
        result, _ = self.run_step()
        self.assertEqual(result.status, self.ci.FAIL)


if __name__ == "__main__":
    unittest.main()
