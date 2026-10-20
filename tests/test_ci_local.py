"""Tests for tools/ci_local.py: step results, exit codes and flags.

Steps are injected in-process so these tests never run the real registry
(which itself runs this test suite).
"""

import importlib.util
import io
import json
import os
import re
import subprocess
import sys
import unittest
import unittest.mock

from tests.scan import support as scan_support
from tests.scan import test_history as scan_history

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CI_LOCAL = os.path.join(ROOT, "tools", "ci_local.py")

LINE_RE = re.compile(r"^STEP [a-z0-9-]+: (PASS|FAIL|SKIP)( \(.+\))?$")


def _load():
    spec = importlib.util.spec_from_file_location("ci_local", CI_LOCAL)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class CiLocalTestBase(unittest.TestCase):
    def setUp(self):
        self.ci = _load()
        self.calls = []

    def step(self, name, status, reason=""):
        def run(ctx):
            self.calls.append((name, ctx))
            return self.ci.StepResult(status, reason)

        return self.ci.Step(name, run)

    def run_main(self, argv, steps):
        out = io.StringIO()
        code = self.ci.main(argv, steps=steps, out=out)
        return code, out.getvalue().splitlines()

    def step_lines(self, lines):
        return [line for line in lines if line.startswith("STEP ")]


class ExitCodeTest(CiLocalTestBase):
    def test_all_pass_exits_0(self):
        steps = [self.step("one", self.ci.PASS), self.step("two", self.ci.PASS)]
        code, lines = self.run_main([], steps)
        self.assertEqual(code, 0)
        self.assertEqual(self.step_lines(lines), ["STEP one: PASS", "STEP two: PASS"])

    def test_failing_step_exits_1(self):
        steps = [
            self.step("one", self.ci.PASS),
            self.step("two", self.ci.FAIL, "boom"),
            self.step("three", self.ci.PASS),
        ]
        code, lines = self.run_main([], steps)
        self.assertEqual(code, 1)
        self.assertIn("STEP two: FAIL (boom)", lines)

    def test_steps_after_a_failure_still_run(self):
        steps = [self.step("one", self.ci.FAIL, "x"), self.step("two", self.ci.PASS)]
        self.run_main([], steps)
        self.assertEqual([c[0] for c in self.calls], ["one", "two"])

    def test_steps_run_in_registry_order(self):
        names = ["c", "a", "b"]
        self.run_main([], [self.step(n, self.ci.PASS) for n in names])
        self.assertEqual([c[0] for c in self.calls], names)

    def test_raising_step_is_a_failure(self):
        def broken(ctx):
            raise RuntimeError("bad")

        code, lines = self.run_main([], [self.ci.Step("broken", broken)])
        self.assertEqual(code, 1)
        self.assertTrue(
            any(line.startswith("STEP broken: FAIL (") for line in lines), lines
        )

    def test_invalid_result_is_a_failure(self):
        code, lines = self.run_main([], [self.ci.Step("odd", lambda ctx: None)])
        self.assertEqual(code, 1)
        self.assertTrue(any(line.startswith("STEP odd: FAIL (") for line in lines))

    def test_unknown_status_is_a_failure(self):
        code, _ = self.run_main([], [self.step("odd", "MAYBE")])
        self.assertEqual(code, 1)

    def test_no_steps_exits_1(self):
        code, _ = self.run_main([], [])
        self.assertEqual(code, 1)


class SkipTest(CiLocalTestBase):
    def test_skip_is_reported_as_skip(self):
        steps = [
            self.step("one", self.ci.PASS),
            self.step("two", self.ci.SKIP, "tool not installed"),
        ]
        code, lines = self.run_main([], steps)
        self.assertEqual(code, 0)
        self.assertIn("STEP two: SKIP (tool not installed)", lines)

    def test_release_turns_skip_into_failure(self):
        steps = [
            self.step("one", self.ci.PASS),
            self.step("two", self.ci.SKIP, "tool not installed"),
        ]
        code, lines = self.run_main(["--release"], steps)
        self.assertEqual(code, 1)
        two = [line for line in lines if line.startswith("STEP two:")]
        self.assertEqual(len(two), 1)
        self.assertTrue(two[0].startswith("STEP two: FAIL ("), two[0])
        self.assertIn("tool not installed", two[0])

    def test_release_all_pass_exits_0(self):
        code, _ = self.run_main(["--release"], [self.step("one", self.ci.PASS)])
        self.assertEqual(code, 0)


class OutputFormatTest(CiLocalTestBase):
    def test_step_lines_match_format(self):
        steps = [
            self.step("a-1", self.ci.PASS),
            self.step("b", self.ci.PASS, "3 tests"),
            self.step("c", self.ci.FAIL, "bad"),
            self.step("d", self.ci.SKIP, "off"),
        ]
        _, lines = self.run_main([], steps)
        step_lines = self.step_lines(lines)
        self.assertEqual(len(step_lines), 4)
        for line in step_lines:
            self.assertRegex(line, LINE_RE)

    def test_summary_counts(self):
        steps = [
            self.step("a", self.ci.PASS),
            self.step("b", self.ci.FAIL, "bad"),
            self.step("c", self.ci.SKIP, "off"),
        ]
        _, lines = self.run_main([], steps)
        summary = [line for line in lines if line.startswith("SUMMARY")]
        self.assertEqual(len(summary), 1)
        self.assertIn("1 passed", summary[0])
        self.assertIn("1 failed", summary[0])
        self.assertIn("1 skipped", summary[0])
        self.assertIn("FAIL", summary[0])

    def test_summary_ok(self):
        _, lines = self.run_main([], [self.step("a", self.ci.PASS)])
        self.assertTrue(lines[-1].startswith("SUMMARY"))
        self.assertTrue(lines[-1].endswith("OK"), lines[-1])


class FlagsTest(CiLocalTestBase):
    def test_flags_reach_steps(self):
        argv = [
            "--with-folio",
            "--gitleaks", "/home/user/bin/gitleaks",
            "--trufflehog", "/home/user/bin/trufflehog",
            "--terms-file", "/home/user/terms.tsv",
        ]
        self.run_main(argv, [self.step("a", self.ci.PASS)])
        ctx = self.calls[0][1]
        self.assertTrue(ctx.with_folio)
        self.assertFalse(ctx.release)
        self.assertEqual(ctx.gitleaks, "/home/user/bin/gitleaks")
        self.assertEqual(ctx.trufflehog, "/home/user/bin/trufflehog")
        self.assertEqual(ctx.terms_file, "/home/user/terms.tsv")
        self.assertEqual(os.path.realpath(ctx.root), os.path.realpath(ROOT))

    def test_flag_defaults(self):
        self.run_main([], [self.step("a", self.ci.PASS)])
        ctx = self.calls[0][1]
        self.assertFalse(ctx.with_folio)
        self.assertFalse(ctx.release)
        self.assertIsNone(ctx.gitleaks)
        self.assertIsNone(ctx.trufflehog)
        self.assertIsNone(ctx.terms_file)


class RegistryTest(CiLocalTestBase):
    def test_registry_order(self):
        names = [s.name for s in self.ci.STEPS]
        self.assertEqual(names[:4], ["structure", "kit-tests", "clean-scan", "history-scan"])

    def test_registry_names_unique_and_well_formed(self):
        names = [s.name for s in self.ci.STEPS]
        self.assertEqual(len(names), len(set(names)))
        for name in names:
            self.assertRegex(name, r"^[a-z0-9-]+$")

    def test_readme_step_table_matches_registry(self):
        with open(os.path.join(ROOT, "tools", "README.md")) as handle:
            readme = handle.read()
        table = readme.split("### Steps (in run order)", 1)[1].split("\n\n", 2)[1]
        documented = re.findall(r"^\| `([a-z0-9-]+)` \|", table, re.MULTILINE)
        self.assertEqual(documented, [s.name for s in self.ci.STEPS])
        self.assertNotIn("Planned steps", readme)


needs_git = unittest.skipUnless(scan_support.git_available(), "git not installed")


class ScanStepTest(CiLocalTestBase):
    """The clean-scan and history-scan steps, run against temp trees.

    Planted values come from tests.scan.support, assembled at run time, so this
    file stays clean under the scanner.
    """

    def setUp(self):
        super().setUp()
        self.tree = scan_support.Tree(prefix="kitci-")
        self.addCleanup(self.tree.cleanup)
        self.outside = scan_support.Tree(prefix="kitci-outside-")
        self.addCleanup(self.outside.cleanup)
        self.planted = scan_support.planted()

    def ctx_for(self, argv=()):
        ctx = self.ci.build_context(self.ci.parse_args(list(argv)), io.StringIO())
        ctx.root = self.tree.root
        return ctx

    def terms(self, *lines):
        return self.outside.write("terms.tsv", "\n".join(lines) + "\n")

    def test_clean_scan_finding_is_fail_with_counts_only(self):
        self.tree.write("a.md", self.planted["email"] + "\n")
        ctx = self.ctx_for()
        result = self.ci.step_clean_scan(ctx)
        self.assertEqual(result.status, self.ci.FAIL)
        self.assertIn("TOTAL 1", result.reason)
        self.assertIn("EMAIL 1", result.reason)
        self.assertNotIn(self.planted["email"], result.reason + ctx.failure_output)
        self.assertNotIn(self.tree.root, result.reason + ctx.failure_output)

    def test_clean_scan_without_terms_is_skip(self):
        self.tree.write("a.md", "clean\n")
        result = self.ci.step_clean_scan(self.ctx_for())
        self.assertEqual(result.status, self.ci.SKIP)
        self.assertIn("TOTAL 0", result.reason)
        self.assertIn("terms", result.reason)

    def test_clean_scan_with_terms_is_pass(self):
        self.tree.write("a.md", "clean\n")
        result = self.ci.step_clean_scan(self.ctx_for(["--terms-file", self.terms("Quor" + "vane")]))
        self.assertEqual(result.status, self.ci.PASS)
        self.assertIn("TOTAL 0", result.reason)

    def test_clean_scan_term_hit_is_fail(self):
        self.tree.write("a.md", "quor" + "vane\n")
        result = self.ci.step_clean_scan(self.ctx_for(["--terms-file", self.terms("Quor" + "vane")]))
        self.assertEqual(result.status, self.ci.FAIL)
        self.assertIn("TERMS 1", result.reason)

    def test_clean_scan_usage_error_is_fail(self):
        terms = self.tree.write("terms.tsv", "x\n")
        result = self.ci.step_clean_scan(self.ctx_for(["--terms-file", terms]))
        self.assertEqual(result.status, self.ci.FAIL)
        self.assertIn("exit 2", result.reason)

    def test_clean_scan_step_line_is_single_line(self):
        self.tree.write("a.md", self.planted["email"] + "\n")
        result = self.ci.step_clean_scan(self.ctx_for())
        self.assertRegex(self.ci.format_line("clean-scan", result), LINE_RE)

    def test_history_scan_outside_a_repo_is_skip(self):
        self.tree.write("a.md", "clean\n")
        result = self.ci.step_history_scan(self.ctx_for())
        self.assertEqual(result.status, self.ci.SKIP)

    def _repo(self):
        scan_support.init_repo(self.tree)
        scan_support.git(self.tree.root, "config", "user.name", scan_support.ALLOWED_NAME)
        scan_support.git(self.tree.root, "config", "user.email", scan_support.ALLOWED_EMAIL)
        self.tree.write("README.md", "Example kit\n")
        scan_support.commit_all(self.tree, "seed")

    @needs_git
    def test_history_scan_other_author_is_fail(self):
        self._repo()
        self.tree.write("a.md", "more\n")
        scan_support.commit_all(self.tree, "second", author="Other Person <other@example.org>")
        ctx = self.ctx_for()
        result = self.ci.step_history_scan(ctx)
        self.assertEqual(result.status, self.ci.FAIL)
        self.assertIn("HDR 1", result.reason)
        for value in (scan_support.ALLOWED_NAME, scan_support.ALLOWED_EMAIL, "Other Person"):
            self.assertNotIn(value, result.reason + ctx.failure_output)

    @needs_git
    def test_history_scan_identity_comes_from_git_config(self):
        self._repo()
        scan_support.git(self.tree.root, "config", "user.name", "Someone Else")
        result = self.ci.step_history_scan(self.ctx_for())
        self.assertEqual(result.status, self.ci.FAIL)
        self.assertIn("HDR 2", result.reason)

    @needs_git
    def test_history_scan_without_identity_is_skip(self):
        self._repo()
        scan_support.git(self.tree.root, "config", "--unset", "user.email")
        env = {"GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}
        with unittest.mock.patch.dict(os.environ, env):
            result = self.ci.step_history_scan(self.ctx_for())
        self.assertEqual(result.status, self.ci.SKIP)

    @needs_git
    def test_history_scan_clean_repo_without_tools_is_skip(self):
        self._repo()
        result = self.ci.step_history_scan(self.ctx_for())
        self.assertEqual(result.status, self.ci.SKIP)
        self.assertIn("TOTAL 0", result.reason)
        for what in ("gitleaks", "trufflehog", "terms"):
            self.assertIn(what, result.reason)

    @needs_git
    def test_history_scan_with_every_tool_is_pass(self):
        self._repo()
        bin_dir = scan_support.Tree(prefix="kitci-bin-")
        self.addCleanup(bin_dir.cleanup)
        tools = {}
        for name, body in (("gitleaks", scan_history.FAKE_GITLEAKS), ("trufflehog", scan_history.FAKE_TRUFFLEHOG)):
            path = scan_support.write_executable(bin_dir.path(name), body)
            with open(path + ".cfg.json", "w", encoding="utf-8") as handle:
                json.dump({"log": bin_dir.path(name + ".log"), "findings": []}, handle)
            tools[name] = path
        argv = ["--gitleaks", tools["gitleaks"], "--trufflehog", tools["trufflehog"],
                "--terms-file", self.terms("Quor" + "vane")]
        result = self.ci.step_history_scan(self.ctx_for(argv))
        self.assertEqual(result.status, self.ci.PASS)
        self.assertIn("TOTAL 0", result.reason)
        self.assertTrue(os.path.exists(bin_dir.path("gitleaks.log")), "gitleaks was not run")
        self.assertTrue(os.path.exists(bin_dir.path("trufflehog.log")), "trufflehog was not run")


# --- accelerator step ---------------------------------------------------------------

class AcceleratorStepTest(CiLocalTestBase):
    """The `accelerator` step runs the kit-level suite in tests/accelerator."""

    def ctx_at(self, root):
        ctx = self.ci.build_context(self.ci.parse_args([]), io.StringIO())
        ctx.root = root
        return ctx

    def fake_run(self, code, output):
        seen = []

        def run(ctx, argv):
            seen.append(argv)
            return code, output

        return seen, run

    def test_registered_after_the_base_steps(self):
        names = [s.name for s in self.ci.STEPS]
        self.assertIn("accelerator", names)
        self.assertGreater(names.index("accelerator"), names.index("history-scan"))

    def test_runs_the_accelerator_suite(self):
        seen, run = self.fake_run(0, "Ran 7 tests in 0.1s\n\nOK\n")
        with unittest.mock.patch.object(self.ci, "run_command", run):
            result = self.ci.step_accelerator(self.ctx_at(ROOT))
        self.assertEqual(result, self.ci.StepResult(self.ci.PASS, "7 tests"))
        self.assertEqual(len(seen), 1)
        argv = seen[0]
        self.assertEqual(argv[1:4], ["-m", "unittest", "discover"])
        self.assertEqual(argv[argv.index("-s") + 1], os.path.join("tests", "accelerator"))
        self.assertEqual(argv[argv.index("-t") + 1], os.path.join("tests", "accelerator"))

    def test_failing_suite_is_fail(self):
        seen, run = self.fake_run(1, "Ran 7 tests in 0.1s\n\nFAILED (failures=1)\n")
        with unittest.mock.patch.object(self.ci, "run_command", run):
            result = self.ci.step_accelerator(self.ctx_at(ROOT))
        self.assertEqual(result.status, self.ci.FAIL)

    def test_without_the_vendored_suite_is_skip(self):
        tree = scan_support.Tree(prefix="kitci-accel-")
        self.addCleanup(tree.cleanup)
        tree.write("README.md", "Example kit\n")
        seen, run = self.fake_run(0, "Ran 1 test\n\nOK\n")
        with unittest.mock.patch.object(self.ci, "run_command", run):
            result = self.ci.step_accelerator(self.ctx_at(tree.root))
        self.assertEqual(result.status, self.ci.SKIP)
        self.assertEqual(seen, [])


class CliTest(unittest.TestCase):
    def _run(self, *args):
        return subprocess.run(
            [sys.executable, CI_LOCAL, *args],
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            timeout=60,
        )

    def test_unknown_flag_exits_2(self):
        proc = self._run("--no-such-flag")
        self.assertEqual(proc.returncode, 2)
        self.assertNotIn("STEP ", proc.stdout)

    def test_unexpected_positional_exits_2(self):
        proc = self._run("extra")
        self.assertEqual(proc.returncode, 2)

    def test_missing_flag_value_exits_2(self):
        proc = self._run("--gitleaks")
        self.assertEqual(proc.returncode, 2)

    def test_help_exits_0(self):
        proc = self._run("--help")
        self.assertEqual(proc.returncode, 0)
        for flag in ("--release", "--with-folio", "--gitleaks", "--trufflehog", "--terms-file"):
            self.assertIn(flag, proc.stdout)


# --- the `pins` step ---------------------------------------------------------


class PinsStepTest(CiLocalTestBase):
    """The pins step runs tools/verify_pins.py on <root>/tools/pins.json."""

    HEX = "0" * 63 + "1"

    def setUp(self):
        super().setUp()
        self.tree = scan_support.Tree(prefix="kitci-pins-")
        self.addCleanup(self.tree.cleanup)

    def ctx_for(self, argv=(), root=None):
        ctx = self.ci.build_context(self.ci.parse_args(list(argv)), io.StringIO())
        ctx.root = self.tree.root if root is None else root
        return ctx

    def write_pins(self, digest, required=True):
        entry = {
            "name": "example-tool",
            "version": "1.2.3",
            "platform": "linux-x64",
            "url": "https://example.com/example-tool-1.2.3.tar.gz",
            "algo": "sha256",
            "digest": digest,
            "required": required,
        }
        self.tree.write("tools/pins.json", json.dumps({"schema": 1, "pins": [entry]}))

    def test_pins_is_registered(self):
        self.assertIn("pins", [s.name for s in self.ci.STEPS])

    def test_good_pins_pass_in_both_modes(self):
        self.write_pins(self.HEX)
        for argv in ([], ["--release"]):
            with self.subTest(argv=argv):
                result = self.ci.step_pins(self.ctx_for(argv))
                self.assertEqual(result.status, self.ci.PASS, result)
                self.assertTrue(result.reason.startswith("1 pin, 1 required"), result.reason)

    def test_placeholder_warns_in_dev_mode(self):
        self.write_pins("<pinned-at-build>")
        result = self.ci.step_pins(self.ctx_for())
        self.assertEqual(result.status, self.ci.PASS, result)
        self.assertIn("1 warning", result.reason)

    def test_placeholder_fails_release(self):
        self.write_pins("<pinned-at-build>")
        ctx = self.ctx_for(["--release"])
        result = self.ci.step_pins(ctx)
        self.assertEqual(result.status, self.ci.FAIL)
        self.assertIn("1 error", result.reason)
        self.assertIn("example-tool", ctx.failure_output)

    def test_malformed_digest_fails_in_dev_mode(self):
        self.write_pins("abc")
        result = self.ci.step_pins(self.ctx_for())
        self.assertEqual(result.status, self.ci.FAIL)

    def test_missing_pins_file_fails(self):
        result = self.ci.step_pins(self.ctx_for())
        self.assertEqual(result.status, self.ci.FAIL)

    def test_shipped_pins_pass_release(self):
        result = self.ci.step_pins(self.ctx_for(["--release"], root=ROOT))
        self.assertEqual(result.status, self.ci.PASS, result)
        self.assertIn("0 warnings, 0 errors", result.reason)

    def test_step_line_is_single_line(self):
        self.write_pins("<pinned-at-build>")
        result = self.ci.step_pins(self.ctx_for(["--release"]))
        self.assertRegex(self.ci.format_line("pins", result), LINE_RE)


# --- the `placeholders` step (no build-time sha left in a release tree) ---

# Joined at run time, so this file never holds the placeholder itself.
SHA_PLACEHOLDER = "-".join(("<sha", "filled", "at", "build>"))


class PlaceholdersStepTest(CiLocalTestBase):
    """The placeholders step lists every path:line under the root that still
    holds the build-time sha placeholder: PASS in fast mode, FAIL with --release."""

    def setUp(self):
        super().setUp()
        self.tree = scan_support.Tree(prefix="kitci-placeholders-")
        self.addCleanup(self.tree.cleanup)
        self.outside = scan_support.Tree(prefix="kitci-placeholders-outside-")
        self.addCleanup(self.outside.cleanup)

    def ctx_for(self, argv=(), root=None):
        ctx = self.ci.build_context(self.ci.parse_args(list(argv)), io.StringIO())
        ctx.root = self.tree.root if root is None else root
        return ctx

    def run_step(self, ctx):
        step = getattr(self.ci, "step_placeholders", None)
        self.assertIsNotNone(step, "tools/ci_local.py has no step_placeholders")
        return step(ctx)

    def vendored(self, *shas):
        rows = ["| Component | Path | Source sha |", "|---|---|---|"]
        rows += ["| part %d | `part%d/` | `%s` |" % (i, i, sha) for i, sha in enumerate(shas)]
        return self.tree.write("VENDORED.md", "# Vendored\n\n" + "\n".join(rows) + "\n")

    def test_placeholder_literal(self):
        self.assertEqual(getattr(self.ci, "SHA_PLACEHOLDER", None), SHA_PLACEHOLDER)

    def test_registered_after_every_build_and_tree_step_before_folio(self):
        names = [s.name for s in self.ci.STEPS]
        self.assertEqual(names.count("placeholders"), 1)
        self.assertEqual(names.index("placeholders"), len(names) - 2, names)
        self.assertEqual(names[-1], "folio")
        self.assertGreater(names.index("placeholders"), names.index("pins"))

    def test_leftover_fails_release_naming_file_and_line(self):
        self.vendored("abc1234", SHA_PLACEHOLDER)
        ctx = self.ctx_for(["--release"])
        result = self.run_step(ctx)
        self.assertEqual(result.status, self.ci.FAIL, result)
        self.assertIn("1 left", result.reason)
        self.assertIn("VENDORED.md:6", result.reason)
        self.assertEqual(ctx.failure_output.splitlines(), ["VENDORED.md:6"])

    def test_filled_tree_passes_release(self):
        self.vendored("abc1234", "def5678")
        self.tree.write("docs/notes.md", "sha-filled-at-build without brackets is prose\n")
        result = self.run_step(self.ctx_for(["--release"]))
        self.assertEqual(result.status, self.ci.PASS, result)
        self.assertEqual(result.reason, "0 left")

    def test_fast_mode_passes_with_leftovers(self):
        self.vendored(SHA_PLACEHOLDER, SHA_PLACEHOLDER)
        ctx = self.ctx_for()
        result = self.run_step(ctx)
        self.assertEqual(result.status, self.ci.PASS, result)
        self.assertIn("2 left", result.reason)
        self.assertIn("--release fails", result.reason)

    def test_every_leftover_is_named_in_path_order(self):
        self.tree.write("b/deep/file.txt", "x\n%s\ny %s\n" % (SHA_PLACEHOLDER, SHA_PLACEHOLDER))
        self.tree.write("a.md", "one\ntwo\nthree %s\n" % SHA_PLACEHOLDER)
        self.tree.write("c.bin", b"\x00\x01\n\x02" + SHA_PLACEHOLDER.encode() + b"\x00")
        ctx = self.ctx_for(["--release"])
        result = self.run_step(ctx)
        self.assertEqual(result.status, self.ci.FAIL, result)
        self.assertIn("4 left", result.reason)
        deep = os.path.join("b", "deep", "file.txt")
        expected = ["a.md:3", deep + ":2", deep + ":3", "c.bin:2"]
        self.assertEqual(ctx.failure_output.splitlines(), expected)
        self.assertIn("first at a.md:3", result.reason)

    def test_two_on_one_line_name_the_line_once(self):
        self.tree.write("a.md", "%s %s\n" % (SHA_PLACEHOLDER, SHA_PLACEHOLDER))
        ctx = self.ctx_for(["--release"])
        self.run_step(ctx)
        self.assertEqual(ctx.failure_output.splitlines(), ["a.md:1"])

    def test_git_folder_is_not_part_of_the_release_tree(self):
        self.vendored("abc1234")
        self.tree.write(".git/COMMIT_EDITMSG", SHA_PLACEHOLDER + "\n")
        self.tree.write("sub/.git", "gitdir: " + SHA_PLACEHOLDER + "\n")
        result = self.run_step(self.ctx_for(["--release"]))
        self.assertEqual(result.status, self.ci.PASS, result)

    def test_git_named_lookalikes_are_still_read(self):
        self.tree.write(".github-notes/a.md", SHA_PLACEHOLDER + "\n")
        self.tree.write("x.git", SHA_PLACEHOLDER + "\n")
        ctx = self.ctx_for(["--release"])
        result = self.run_step(ctx)
        self.assertEqual(result.status, self.ci.FAIL, result)
        self.assertEqual(len(ctx.failure_output.splitlines()), 2)

    def test_symlink_out_of_the_tree_is_not_followed(self):
        target = self.outside.write("elsewhere.md", SHA_PLACEHOLDER + "\n")
        os.symlink(target, self.tree.path("link.md"))
        os.symlink(self.outside.root, self.tree.path("linkdir"))
        self.vendored("abc1234")
        result = self.run_step(self.ctx_for(["--release"]))
        self.assertEqual(result.status, self.ci.PASS, result)

    def test_release_run_prints_the_location_under_the_step_line(self):
        self.vendored(SHA_PLACEHOLDER)
        self.ci.ROOT = self.tree.root
        steps = [s for s in self.ci.STEPS if s.name == "placeholders"]
        self.assertEqual(len(steps), 1)
        code, lines = self.run_main(["--release"], steps)
        self.assertEqual(code, 1)
        self.assertRegex(lines[0], r"^STEP placeholders: FAIL \(.*VENDORED\.md:5.*\)$")
        self.assertIn("  | VENDORED.md:5", lines)
        code, lines = self.run_main([], steps)
        self.assertEqual(code, 0, lines)

    def test_shipped_tree_passes_fast_mode_and_only_vendored_rows_are_left(self):
        ctx = self.ctx_for(root=ROOT)
        result = self.run_step(ctx)
        self.assertEqual(result.status, self.ci.PASS, result)
        ctx = self.ctx_for(["--release"], root=ROOT)
        self.run_step(ctx)
        for location in ctx.failure_output.splitlines():
            self.assertTrue(location.startswith("VENDORED.md:"), location)

    def test_step_line_is_single_line(self):
        self.vendored(SHA_PLACEHOLDER, SHA_PLACEHOLDER)
        for argv in ([], ["--release"]):
            with self.subTest(argv=argv):
                result = self.run_step(self.ctx_for(argv))
                self.assertRegex(self.ci.format_line("placeholders", result), LINE_RE)


if __name__ == "__main__":
    unittest.main()
