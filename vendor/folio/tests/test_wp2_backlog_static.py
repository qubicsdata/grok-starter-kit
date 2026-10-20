"""WP-2 red tests (static): the seams exist, no `shell=True`, no write to backlog/** outside subprocess.

The scanner parses the AST of every module under folio/ and flags:
  - any subprocess call with a `shell` keyword that is not the constant False, and any os.system /
    os.popen / os.exec* / os.spawn* / pty call (whole package);
  - in folio/backlog/adapter.py and folio/backlog/guard.py, any file-writing call: open() with a
    mode other than read, Path.write_text/write_bytes/unlink/rename/replace/mkdir/touch/rmdir,
    os.remove/rename/replace/unlink/mkdir/makedirs/rmdir/truncate/utime, shutil.* and tempfile.*;
    the only way those modules may change backlog/** is through the Backlog.md binary.
  - every subprocess call under folio/backlog/ must pass a list/tuple argv (never a str) and an
    explicit env= (the temporary HOME).
folio/backlog/tools.py is exempt from the write ban only because WP-9 extracts the binary under
$XDG_DATA_HOME; it is still covered by the shell and argv rules, and WP-9 adds its own no-backlog-
path test. The scanner is checked against planted violations so a silent miss cannot pass.
"""

import ast
import tempfile
import unittest
from pathlib import Path

from wp2_support import FOLIO_BACKLOG, REPO_ROOT, SEAMS

SUBPROCESS_CALLS = ("run", "Popen", "call", "check_call", "check_output")
OS_SHELL_CALLS = ("system", "popen", "execl", "execle", "execlp", "execv", "execve", "execvp", "execvpe",
                  "spawnl", "spawnle", "spawnlp", "spawnv", "spawnve", "spawnvp", "spawnvpe", "startfile")
# Path.replace is not listed because str.replace shares the name; Path.rename and os.replace still catch moves.
WRITE_METHODS = ("write_text", "write_bytes", "unlink", "rename", "mkdir", "touch", "rmdir", "write")
OS_WRITE_CALLS = ("remove", "rename", "replace", "unlink", "mkdir", "makedirs", "rmdir", "truncate", "utime",
                  "removedirs", "renames", "link", "symlink", "chmod")
WRITE_MODULES = ("shutil", "tempfile")
WRITE_BANNED = ("adapter.py", "guard.py")


def dotted(node):
    if isinstance(node, ast.Attribute):
        head = dotted(node.value)
        return head + "." + node.attr if head else node.attr
    if isinstance(node, ast.Name):
        return node.id
    return ""


def keyword(call, name):
    for item in call.keywords:
        if item.arg == name:
            return item
    return None


def is_false(node):
    return isinstance(node, ast.Constant) and node.value is False


def open_mode(call):
    mode = keyword(call, "mode")
    node = mode.value if mode else (call.args[1] if len(call.args) > 1 else None)
    if node is None:
        return "r"
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return "?"


def scan_module(path, write_banned):
    """Return ["<file>:<line>: <reason>"] for every violation in one module."""
    found = []  # (line, reason); ast.walk is breadth-first, so sort by line before reporting
    tree = ast.parse(Path(path).read_text(encoding="utf-8"), filename=str(path))
    name = Path(path).name
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        target = dotted(node.func)
        line = node.lineno
        shell = keyword(node, "shell")
        if shell is not None and not is_false(shell.value):
            found.append((line, "shell=%s" % ast.unparse(shell.value)))
        head, _dot, tail = target.rpartition(".")
        if head == "os" and tail in OS_SHELL_CALLS:
            found.append((line, "os.%s" % tail))
        if head == "pty" or head.startswith("pty."):
            found.append((line, "pty call"))
        if head == "subprocess" and tail in SUBPROCESS_CALLS:
            argv = keyword(node, "args")
            argv = argv.value if argv else (node.args[0] if node.args else None)
            if argv is None or isinstance(argv, ast.Constant) or isinstance(argv, ast.JoinedStr):
                found.append((line, "subprocess.%s without a list argv" % tail))
            if keyword(node, "env") is None:
                found.append((line, "subprocess.%s without env=" % tail))
        if not write_banned:
            continue
        if target in ("open", "io.open") or target.endswith(".open"):
            mode = open_mode(node)
            if mode not in ("r", "rb", "rt"):
                found.append((line, "open(mode=%r)" % mode))
        if isinstance(node.func, ast.Attribute) and tail in WRITE_METHODS:
            found.append((line, target))
        if head == "os" and tail in OS_WRITE_CALLS:
            found.append((line, target))
        if head.split(".")[0] in WRITE_MODULES:
            found.append((line, target))
    return ["%s:%d: %s" % (name, line, reason) for line, reason in sorted(found, key=lambda item: item[0])]


def reasons(hits):
    return [hit.split(": ", 1)[1] for hit in hits]


def scan_package(root, write_banned=WRITE_BANNED):
    hits = []
    for path in sorted(Path(root).rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        hits.extend(scan_module(path, path.name in write_banned))
    return hits


class SeamTests(unittest.TestCase):
    def test_folio_backlog_package_and_seams_exist(self):
        self.assertTrue((FOLIO_BACKLOG / "__init__.py").is_file(), "folio/backlog/__init__.py is missing")
        for name in SEAMS:
            with self.subTest(seam=name):
                self.assertTrue((FOLIO_BACKLOG / (name + ".py")).is_file(), "folio/backlog/%s.py is missing" % name)

    def test_seams_import_without_side_effects_and_expose_the_contract(self):
        import importlib

        expected = {
            "adapter": ("BacklogClient", "BacklogError"),
            "tools": ("ToolResolver", "ToolError", "BACKLOG_VERSION", "BIN_ENV"),
            "guard": ("GuardRefused", "scan_text", "check"),
        }
        for name, attributes in expected.items():
            with self.subTest(seam=name):
                try:
                    module = importlib.import_module("folio.backlog." + name)
                except ImportError as error:
                    self.fail("WP-2 seam folio/backlog/%s.py is missing: %s" % (name, error))
                for attribute in attributes:
                    self.assertTrue(hasattr(module, attribute), "%s lacks %s" % (name, attribute))


class StaticScanTests(unittest.TestCase):
    def test_no_shell_true_anywhere_in_folio(self):
        self.assertTrue(FOLIO_BACKLOG.is_dir(), "folio/backlog/ is missing")
        hits = scan_package(REPO_ROOT / "folio", write_banned=())
        self.assertEqual([hit for hit in hits if not reasons([hit])[0].startswith("subprocess.")], [])

    def test_backlog_adapter_and_guard_never_write_files(self):
        self.assertTrue(FOLIO_BACKLOG.is_dir(), "folio/backlog/ is missing")
        self.assertEqual(scan_package(FOLIO_BACKLOG), [])

    def test_every_backlog_subprocess_has_a_list_argv_and_an_env(self):
        self.assertTrue(FOLIO_BACKLOG.is_dir(), "folio/backlog/ is missing")
        sources = "".join((FOLIO_BACKLOG / (name + ".py")).read_text(encoding="utf-8") for name in SEAMS)
        self.assertIn("subprocess", sources, "folio/backlog never spawns the binary")
        self.assertEqual([hit for hit in scan_package(FOLIO_BACKLOG, write_banned=()) if "subprocess" in hit], [])

    def test_scanner_catches_planted_violations(self):
        planted = (
            "import os, shutil, subprocess, tempfile\n"
            "from pathlib import Path\n"
            "def bad(argv, path):\n"
            "    subprocess.run('backlog task list', shell=True)\n"            # shell=True, str argv
            "    subprocess.Popen(argv, env={})\n"                            # fine
            "    subprocess.run(argv)\n"                                      # no env
            "    os.system('true')\n"
            "    Path(path).write_text('x')\n"
            "    open(path, 'w').close()\n"
            "    open(path, mode='a').close()\n"
            "    open(path).close()\n"                                        # fine
            "    os.remove(path)\n"
            "    shutil.copy(path, path)\n"
            "    tempfile.mkdtemp()\n"
            "    Path(path).read_text()\n"                                    # fine
        )
        with tempfile.TemporaryDirectory(prefix="folio-wp2-static-") as tmp:
            (Path(tmp) / "adapter.py").write_text(planted, encoding="utf-8")
            hits = scan_package(tmp)
        self.assertEqual(
            reasons(hits),
            [
                "shell=True",
                "subprocess.run without a list argv",
                "subprocess.run without env=",
                "subprocess.run without env=",
                "os.system",
                "write_text",
                "open(mode='w')",
                "open(mode='a')",
                "os.remove",
                "shutil.copy",
                "tempfile.mkdtemp",
            ],
        )

    def test_scanner_ignores_read_only_and_subprocess_only_code(self):
        clean = (
            "import json, subprocess\n"
            "from pathlib import Path\n"
            "def good(binary, repo, env):\n"
            "    with open(repo / 'backlog' / 'config.yml', encoding='utf-8') as handle:\n"
            "        handle.read()\n"
            "    Path(repo).read_text(encoding='utf-8')\n"
            "    return subprocess.run([binary, 'task', 'list', '--json'], cwd=str(repo), env=env,\n"
            "                          stdin=subprocess.DEVNULL, capture_output=True, text=True, shell=False)\n"
        )
        with tempfile.TemporaryDirectory(prefix="folio-wp2-static-") as tmp:
            (Path(tmp) / "guard.py").write_text(clean, encoding="utf-8")
            self.assertEqual(scan_package(tmp), [])


if __name__ == "__main__":
    unittest.main()
