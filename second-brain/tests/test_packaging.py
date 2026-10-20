"""bin/sb as shipped: an executable python3 script, stdlib only, a generic
docstring with no built-in channels, roots or name hashes, a clean-data scan
at zero, and the local CI step `sb` that runs this suite."""

import ast
import os
import re
import subprocess
import sys
import unittest

import sbsupport

STDLIB_OK = {
    "argparse", "errno", "fnmatch", "hashlib", "hmac", "io", "json", "os", "re", "secrets", "shutil", "stat",
    "subprocess", "sys", "time", "unicodedata", "collections", "itertools", "functools",
}


def sb_source():
    with open(sbsupport.SB, encoding="utf-8") as fh:
        return fh.read()


class ScriptTest(unittest.TestCase):
    def test_executable_python3_script(self):
        self.assertTrue(os.access(sbsupport.SB, os.X_OK), "bin/sb is executable")
        self.assertTrue(sb_source().startswith("#!/usr/bin/env python3\n"))

    def test_stdlib_imports_only(self):
        tree = ast.parse(sb_source())
        names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom):
                names.add((node.module or "").split(".")[0])
        self.assertEqual(names - STDLIB_OK, set(), "only stdlib imports")

    def test_not_a_stub(self):
        self.assertNotIn("STUB.", sb_source())
        sb = sbsupport.load_sb()
        self.assertIsInstance(sb.parse_config_text("a: 1\n"), dict)

    def test_no_built_in_channel_values(self):
        """Name hashes come from config only (no 16-hex literal in the script),
        and the docstring is the generic one."""
        source = sb_source()
        self.assertEqual(re.findall(r"['\"][0-9a-f]{16}['\"]", source), [])
        doc = ast.get_docstring(ast.parse(source)) or ""
        self.assertTrue(doc.startswith("sb: fast, channel-aware search over your second brain"))

    def test_rg_only_through_a_fixed_argv(self):
        source = sb_source()
        self.assertNotIn("shell=True", source)
        self.assertNotIn("os.system", source)

    def test_clean_scan_of_the_second_brain_folder_is_zero(self):
        proc = subprocess.run([sys.executable, sbsupport.CLEAN_SCAN, sbsupport.SB_DIR],
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True,
                              env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
        self.assertIn("TOTAL 0", proc.stdout.splitlines())


class CiStepTest(unittest.TestCase):
    """tools/ci_local.py runs this suite as step `sb`, right after the scans."""

    def load_ci(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("ci_local_under_test", sbsupport.CI_LOCAL)
        module = importlib.util.module_from_spec(spec)
        saved = sys.dont_write_bytecode
        sys.dont_write_bytecode = True
        try:
            spec.loader.exec_module(module)
        finally:
            sys.dont_write_bytecode = saved
        return module

    def test_sb_step_is_registered_after_the_scans(self):
        ci = self.load_ci()
        names = [s.name for s in ci.STEPS]
        self.assertEqual(names[:5], ["structure", "kit-tests", "clean-scan", "history-scan", "sb"])

    def test_sb_step_runs_this_suite(self):
        ci = self.load_ci()
        calls = []

        def fake_unittest_step(ctx, argv):
            calls.append(argv)
            return ci.StepResult(ci.PASS, "1 tests")

        ci.unittest_step = fake_unittest_step
        step = dict((s.name, s) for s in ci.STEPS)["sb"]
        result = step.run(ci.build_context(ci.parse_args([]), sys.stdout))
        self.assertEqual(result.status, ci.PASS)
        self.assertEqual(len(calls), 1)
        joined = " ".join(calls[0]).replace(os.sep, "/")
        self.assertIn("discover", calls[0])
        self.assertIn("second-brain/tests", joined)


if __name__ == "__main__":
    unittest.main()
