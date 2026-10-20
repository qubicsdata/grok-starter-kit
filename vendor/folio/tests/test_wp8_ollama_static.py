"""WP-8 red tests (static): the seam exists with its contract, is packaged through the folio.plugins
entry point, adds no dependency, imports only the stdlib and folio, and contains no shell, no process
spawn, no bare urlopen (it follows redirects) and no file write outside a temporary HOME.
"""

import ast
import importlib.util
import re
import sys
import sysconfig
import unittest
from pathlib import Path

from backlog_contract.test_browser_guard import subcommand_invocations
from test_wp2_backlog_static import scan_package
from wp8_support import FOLIO_OLLAMA, PYPROJECT, REPO_ROOT, seam

CONTRACT = ("NAME", "DEFAULT_URL", "CHAT_PATH", "MAX_BYTES", "MAX_ITEMS", "TITLE_MAX", "DEFAULT_TIMEOUT", "TRUST_LABEL",
            "DATA_BEGIN", "DATA_END", "OllamaError", "check_url", "parse_subtasks", "make", "OllamaPlugin")
PROCESS_MODULES = ("subprocess", "pty", "multiprocessing", "asyncio", "ctypes", "socketserver", "http.server", "webbrowser")
BANNED_NAMES = ("exec", "eval", "compile", "__import__", "urlopen", "install_opener")  # bare calls
BANNED_ATTRS = ("urlopen", "install_opener", "system", "popen", "spawn", "fork", "execv", "execvp")  # x.<attr>( calls


def sources():
    return sorted(path for path in FOLIO_OLLAMA.rglob("*.py") if "__pycache__" not in path.parts)


def toml():
    text = PYPROJECT.read_text(encoding="utf-8")
    try:
        import tomllib  # Python 3.11+
    except ImportError:
        tomllib = None
    if tomllib is not None:
        return tomllib.loads(text), text
    return None, text


def is_stdlib(name):
    top = name.split(".")[0]
    names = getattr(sys, "stdlib_module_names", None)
    if names is not None:
        return top in names
    spec = importlib.util.find_spec(top)
    if spec is None:
        return False
    if spec.origin in ("built-in", "frozen"):
        return True
    stdlib = Path(sysconfig.get_paths()["stdlib"]).resolve()
    return spec.origin is not None and Path(spec.origin).resolve().is_relative_to(stdlib)


def imports(tree):
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name, node.lineno
        elif isinstance(node, ast.ImportFrom) and node.level == 0:
            yield node.module or "", node.lineno


class SeamTests(unittest.TestCase):
    def test_package_exists_and_exposes_the_contract(self):
        self.assertTrue((FOLIO_OLLAMA / "__init__.py").is_file(), "WP-8 seam folio_ollama/__init__.py is missing")
        module = seam(self)
        for name in CONTRACT:
            with self.subTest(attribute=name):
                self.assertTrue(hasattr(module, name), "folio_ollama lacks %s" % name)
        self.assertEqual(module.NAME, "ollama")
        self.assertEqual(module.CHAT_PATH, "/api/chat")
        self.assertEqual(module.TRUST_LABEL, "planning_data_not_instructions")
        self.assertEqual((module.DATA_BEGIN, module.DATA_END), ("<<<" + module.TRUST_LABEL, ">>>" + module.TRUST_LABEL))
        self.assertTrue(callable(module.make))
        self.assertEqual(module.OllamaPlugin.name, "ollama")
        from folio.core import AppError
        from folio.plugins import Plugin
        self.assertTrue(issubclass(module.OllamaError, AppError))
        self.assertTrue(issubclass(module.OllamaPlugin, Plugin))


class PackagingTests(unittest.TestCase):
    def test_pyproject_declares_the_entry_point_and_ships_the_package(self):
        data, text = toml()
        if data is not None:
            points = data["project"].get("entry-points", {}).get("folio.plugins", {})
            self.assertEqual(points.get("ollama"), "folio_ollama:make", points)
            include = data["tool"]["setuptools"]["packages"]["find"]["include"]
            self.assertIn("folio_ollama", include)
        else:  # Python 3.9/3.10: no tomllib
            self.assertRegex(text, r'\[project\.entry-points\."folio\.plugins"\]\s*\n(?:.*\n)*?ollama\s*=\s*"folio_ollama:make"')
            self.assertRegex(text, r'include\s*=\s*\[[^\]]*"folio_ollama"')

    def test_no_new_dependencies(self):
        data, text = toml()
        if data is not None:
            self.assertEqual(data["project"].get("dependencies", []), [])
            self.assertEqual(data["project"].get("optional-dependencies", {}), {})
        else:
            self.assertNotRegex(text, r"^\s*dependencies\s*=\s*\[\s*[^\]\s]", re.MULTILINE)
        for path in (REPO_ROOT / "requirements.txt", REPO_ROOT / "setup.py", REPO_ROOT / "setup.cfg"):
            self.assertFalse(path.exists(), "%s must not appear" % path.name)

    def test_only_stdlib_and_folio_imports(self):
        files = sources()
        self.assertTrue(files, "folio_ollama/ has no modules")
        for path in files:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for name, line in imports(tree):
                with self.subTest(file=path.name, line=line, module=name):
                    top = name.split(".")[0]
                    self.assertTrue(top == "folio" or is_stdlib(name), "%s:%d imports %s (not stdlib, not folio)" % (path.name, line, name))
                    self.assertNotIn(top, PROCESS_MODULES, "%s:%d imports %s" % (path.name, line, name))


class NoShellNoProcessTests(unittest.TestCase):
    def test_no_shell_process_or_dangerous_call(self):
        files = sources()
        self.assertTrue(files, "folio_ollama/ has no modules")
        hits = scan_package(FOLIO_OLLAMA, write_banned=())
        self.assertEqual(hits, [])
        for path in files:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    func = node.func
                    if isinstance(func, ast.Name):
                        self.assertNotIn(func.id, BANNED_NAMES, "%s:%d calls %s()" % (path.name, node.lineno, func.id))
                    elif isinstance(func, ast.Attribute):
                        self.assertNotIn(func.attr, BANNED_ATTRS, "%s:%d calls .%s()" % (path.name, node.lineno, func.attr))

    def test_no_file_write_outside_the_temporary_home(self):
        """The adapter is the only writer: nothing else under folio_ollama writes, moves, deletes or chmods."""
        files = sources()
        self.assertTrue(files, "folio_ollama/ has no modules")
        hits = [hit for hit in scan_package(FOLIO_OLLAMA, write_banned=tuple(path.name for path in files))
                if not hit.split(": ", 1)[1].startswith("tempfile.")]
        self.assertEqual(hits, [])

    def test_no_backlog_web_ui_invocation_in_the_plugin(self):
        self.assertTrue(FOLIO_OLLAMA.is_dir(), "WP-8 seam folio_ollama/ is missing")
        self.assertEqual(subcommand_invocations(REPO_ROOT, ("folio_ollama",)), [])

    def test_no_redirect_following_opener(self):
        """urlopen() and install_opener() use the global opener, which follows redirects; neither may appear."""
        files = sources()
        self.assertTrue(files, "folio_ollama/ has no modules")
        text = "\n".join(path.read_text(encoding="utf-8") for path in files)
        self.assertNotRegex(text, r"\burlopen\s*\(")
        self.assertNotRegex(text, r"\binstall_opener\s*\(")
        self.assertIn("urllib", text, "stdlib urllib is the HTTP client")

    def test_no_tool_calling_vocabulary_in_the_request_builder(self):
        files = sources()
        self.assertTrue(files, "folio_ollama/ has no modules")
        for path in files:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Constant) and isinstance(node.value, str):
                    self.assertNotIn(node.value, ("tools", "tool_calls", "function_call"), "%s:%d" % (path.name, node.lineno))


if __name__ == "__main__":
    unittest.main()
