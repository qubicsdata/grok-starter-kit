"""Static checks on the runner code (bin/cr, bin/crlib/, bin/run-claude.sh), the flags / bash-env templates
and the example config: no built-in paths or identities, no owner strings left from the source, doc references that
resolve inside the kit, and generic templates under ${KIT_HOME}/runner/. Messages name files, lines and rule names;
matched text is shown only for the synthetic placeholders these rules look for."""
import glob, json, os, re, subprocess, unittest
import k5support as K
from k5support import BIN, RUNNER_DIR, SCRIPT, FLAGS_TEMPLATE, BASH_ENV_TEMPLATE

KIT_ROOT = os.path.dirname(RUNNER_DIR)
CODE = [os.path.join(BIN, "cr"), SCRIPT] + sorted(glob.glob(os.path.join(BIN, "crlib", "*.py")))
TEMPLATES = [FLAGS_TEMPLATE, BASH_ENV_TEMPLATE]
SHEBANGS = ("#!/usr/bin/env python3", "#!/bin/bash", "#!/usr/bin/env bash", "#!/bin/sh")
# Leftovers of the source: the placeholders that stood in for its folder and its built-in backlog identity. The
# source's own names (folder, MCP process, process doc) are checked by digest in test_k5_generic.
LEFTOVERS = ("example-ops", "example-backlog")
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
CITY_TZ_RE = re.compile(r"\b(?:Africa|America|Antarctica|Asia|Atlantic|Australia|Europe|Indian|Pacific)/[A-Z]")


def rel(p):
    return os.path.relpath(p, KIT_ROOT)


def existing(paths):
    return [p for p in paths if os.path.isfile(p)]


def allowed_abs(path, line, lineno, is_comment):
    if lineno == 1 and line.strip() in SHEBANGS:
        return True
    if path == "/dev/null" or path == "/proc" or path.startswith("/proc/"):
        return True
    if path == "/usage":  # the Claude Code slash command, not a file
        return True
    return is_comment and (path == "/home/user" or path.startswith("/home/user/"))


class NoBuiltInPathsTests(unittest.TestCase):
    def test_no_absolute_path_in_runner_code(self):
        bad = []
        for p in CODE + existing(TEMPLATES) + [K.EXAMPLE_CONFIG]:
            lines = K.read(p).splitlines()
            for lineno, path, is_comment in K.absolute_paths("\n".join(lines)):
                if not allowed_abs(path, lines[lineno - 1], lineno, is_comment):
                    bad.append("%s:%d" % (rel(p), lineno))
        self.assertEqual(bad, [], "absolute paths (only /home/user examples in comments, /dev/null, /proc allowed)")

    def test_the_path_rule_has_teeth(self):
        text = "x=1\n. /home/user/example/env.sh\n# see /home/user/kit/runner\nopen('/srv/data')\ny=$(a)/bin\n"
        found = [(n, p) for n, p, c in K.absolute_paths(text) if not allowed_abs(p, text.splitlines()[n - 1], n, c)]
        self.assertEqual(found, [(2, "/home/user/example/env.sh"), (4, "/srv/data")])

    def test_script_sources_only_configured_files(self):
        bad = [n for n, line in K.code_lines(K.read(SCRIPT))
               for m in re.finditer(r"(?:^|[;&|]\s*|\bthen\s+|&&\s*|\|\|\s*)(?:\.|source)\s+(\S+)", line.strip())
               if not m.group(1).startswith(('"$', "$"))]
        self.assertEqual(bad, [], "run-claude.sh sources a literal path at lines %s" % bad)

    def test_claude_env_file_comes_from_config(self):
        vals = re.findall(r"CLAUDE_ENV_FILE=(\S+)", K.read(SCRIPT))
        self.assertTrue(vals, "run-claude.sh no longer sets CLAUDE_ENV_FILE for claude")
        self.assertTrue(all(v.startswith(('"$', "$")) for v in vals), "CLAUDE_ENV_FILE is a literal path")

    def test_mcp_cleanup_has_no_built_in_pattern(self):
        bad = []
        for n, line in K.code_lines(K.read(SCRIPT)):
            for opts, arg in re.findall(r"\bpkill((?:\s+-[A-Za-z]+)*)\s+(\S+)", line):
                if not arg.startswith(('"$', "$")):
                    bad.append(n)
        self.assertEqual(bad, [], "pkill with a built-in pattern at lines %s (use runner.mcp_cleanup_pattern)" % bad)
        self.assertEqual(K.raw_example()["runner"]["mcp_cleanup_pattern"], "")

    def test_k5_2_guard_is_gone(self):
        self.assertFalse(K.script_guarded(), "run-claude.sh still refuses to run (the parameterization is not done)")


class NoOwnerStringsTests(unittest.TestCase):
    def test_no_leftovers_from_the_source(self):
        bad = []
        for p in CODE + existing(TEMPLATES) + [K.EXAMPLE_CONFIG]:
            text = K.read(p)
            bad += ["%s: %s" % (rel(p), s) for s in LEFTOVERS if s.lower() in text.lower()]
        self.assertEqual(bad, [])

    def test_no_email_address_in_code(self):
        bad = []
        for p in CODE + existing(TEMPLATES):
            for n, line in enumerate(K.read(p).splitlines(), 1):
                if EMAIL_RE.search(line):
                    bad.append("%s:%d" % (rel(p), n))
        self.assertEqual(bad, [], "built-in addresses (identity comes from runner.commit_identity)")

    def test_no_built_in_git_identity(self):
        text = K.read(os.path.join(BIN, "crlib", "backlog.py"))
        self.assertFalse(re.search(r"user\.(?:name|email)=[\w<]", text), "a literal git identity in backlog.py")

    def test_example_identity_is_the_template(self):
        self.assertEqual(K.raw_example()["runner"]["commit_identity"], "<your-name> <you@example.com>")

    def test_no_city_time_zone(self):
        bad = ["%s:%d" % (rel(p), n) for p in CODE + existing(TEMPLATES) + [K.EXAMPLE_CONFIG]
               for n, line in enumerate(K.read(p).splitlines(), 1) if CITY_TZ_RE.search(line)]
        self.assertEqual(bad, [], "time zone defaults are ${KIT_TZ} (template) and UTC (code)")


class DocReferenceTests(unittest.TestCase):
    RUNTIME = {"router.json"}  # the user's own config, written at setup (never shipped)

    def refs(self, path):
        out = []
        for n, line in enumerate(K.read(path).splitlines(), 1):
            if not line.strip().startswith(("#", '"""')) and n > 3:
                continue
            for m in re.finditer(r"[\w./-]+\.(?:md|sh|json)\b", line):
                tok = m.group(0)
                if tok in self.RUNTIME or "$" in tok or tok.startswith(("logs/", "http")):
                    continue
                out.append((n, tok))
        return out

    def resolves(self, tok):
        tok = tok.lstrip("./") if not tok.startswith("../") else tok
        return any(os.path.exists(os.path.normpath(os.path.join(base, tok))) for base in (BIN, RUNNER_DIR))

    def test_script_and_cli_doc_references_resolve_in_the_kit(self):
        bad = ["%s:%d %s" % (rel(p), n, tok) for p in (SCRIPT, os.path.join(BIN, "cr"))
               for n, tok in self.refs(p) if not self.resolves(tok)]
        self.assertEqual(bad, [], "doc references that do not exist in the kit layout")


class TemplateTests(unittest.TestCase):
    def test_templates_exist_under_runner(self):
        for p in TEMPLATES:
            self.assertTrue(os.path.isfile(p), "missing template %s" % rel(p))

    def test_example_points_at_the_templates(self):
        ex = K.raw_example()["runner"]
        sub = lambda v: v.replace("${KIT_HOME}", KIT_ROOT)
        self.assertEqual((sub(ex["flags_file"]), sub(ex["bash_env_file"])), (FLAGS_TEMPLATE, BASH_ENV_TEMPLATE))
        self.assertEqual(sub(ex["script"]), SCRIPT)

    def test_flags_template_is_valid_bash_with_the_three_lists(self):
        self.assertTrue(os.path.isfile(FLAGS_TEMPLATE), "missing template %s" % rel(FLAGS_TEMPLATE))
        r = subprocess.run(["bash", "-n", FLAGS_TEMPLATE], capture_output=True, text=True, timeout=30)
        self.assertEqual(r.returncode, 0, "bash -n failed")
        text = K.read(FLAGS_TEMPLATE)
        for arr in ("CLAUDE_ALLOWED=(", "CLAUDE_DISALLOWED=(", "CLAUDE_UNSET_ENV=("):
            self.assertIn(arr, text)
        for must in ("Bash(git push*)", "Bash(gh *)", "ANTHROPIC_API_KEY"):
            self.assertIn(must, text)

    def test_bash_env_template_holds_no_secret_values(self):
        self.assertTrue(os.path.isfile(BASH_ENV_TEMPLATE), "missing template %s" % rel(BASH_ENV_TEMPLATE))
        r = subprocess.run(["bash", "-n", BASH_ENV_TEMPLATE], capture_output=True, text=True, timeout=30)
        self.assertEqual(r.returncode, 0, "bash -n failed")
        bad = [n for n, line in K.code_lines(K.read(BASH_ENV_TEMPLATE))
               if re.search(r"\b\w*(?:TOKEN|SECRET|PASSWORD|API_KEY|AUTH)\w*=[^\s;]", line, re.I)]
        self.assertEqual(bad, [], "the bash env template assigns secret-looking values at lines %s" % bad)


class ExampleConfigTests(unittest.TestCase):
    def test_example_is_valid_json_with_comment_naming_kit_home(self):
        with open(K.EXAMPLE_CONFIG) as f:
            ex = json.load(f)
        self.assertNotRegex(ex["_comment"], r"(?<![}\w])/(?:home|workspace|Users|root)\b")


if __name__ == "__main__":
    unittest.main()
