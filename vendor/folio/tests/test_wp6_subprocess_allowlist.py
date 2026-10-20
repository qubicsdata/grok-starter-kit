"""WP-6 red tests: no subprocess spawns outside the adapter allow-list (D-13).

Static: the only app modules that import a process module or call an os process primitive are the
adapter (folio/backlog/adapter.py, folio/backlog/tools.py) and the WP-5 dialog (folio/dialogs.py).
Dynamic: every route in the table, plus every cut route, is driven over HTTP with a credential while
subprocess.Popen and the os spawn primitives are replaced by a recording spy that refuses to run
anything; a spawn whose call stack does not pass through an allowed module is a failure. The spy is
proven against a planted spawn so a silent miss cannot pass.
"""

import ast
import os
import re
import subprocess
import sys
import traceback
import unittest
from pathlib import Path
from unittest import mock

from folio.api import App

from wp6_support import CORE_ROUTES, REMOVED_ROUTES, REPO_ROOT, app_python_files
from wp7_support import FakePlugin, ServerCase

ALLOWED_SPAWN_SITES = ("folio/backlog/adapter.py", "folio/backlog/tools.py", "folio/dialogs.py")
PROCESS_MODULES = ("subprocess", "pty", "multiprocessing")
OS_PROCESS = re.compile(r"(system|popen|exec\w*|spawn\w*|posix_spawn\w*|fork\w*)")
SPY_TARGETS = ("system", "popen", "posix_spawn", "posix_spawnp", "fork", "forkpty", "execv", "execve", "execvp", "execvpe",
               "spawnv", "spawnve", "spawnvp", "spawnvpe")


def dotted(node):
    if isinstance(node, ast.Attribute):
        head = dotted(node.value)
        return head + "." + node.attr if head else node.attr
    if isinstance(node, ast.Name):
        return node.id
    return ""


def process_sites(paths, root=REPO_ROOT):
    """["<file>:<line>: <reason>"] for every process import or os process call in `paths`."""
    hits = []
    for path in paths:
        tree = ast.parse(Path(path).read_text(encoding="utf-8"), filename=str(path))
        label = Path(path).relative_to(root).as_posix()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.split(".")[0] in PROCESS_MODULES:
                        hits.append("%s:%d: imports %s" % (label, node.lineno, alias.name))
            elif isinstance(node, ast.ImportFrom) and (node.module or "").split(".")[0] in PROCESS_MODULES:
                hits.append("%s:%d: imports %s" % (label, node.lineno, node.module))
            elif isinstance(node, ast.Call):
                target = dotted(node.func)
                head, _dot, tail = target.rpartition(".")
                if head == "os" and OS_PROCESS.fullmatch(tail):
                    hits.append("%s:%d: os.%s" % (label, node.lineno, tail))
    return sorted(hits)


class StaticAllowListTests(unittest.TestCase):
    def test_only_the_adapter_and_the_dialog_spawn_processes(self):
        hits = process_sites(app_python_files())
        outside = [hit for hit in hits if not hit.startswith(tuple(site + ":" for site in ALLOWED_SPAWN_SITES))]
        self.assertEqual(outside, [], "process imports or calls outside the allow-list")
        self.assertTrue(any(hit.startswith("folio/backlog/adapter.py:") for hit in hits), "the adapter is the spawn site")

    def test_no_shell_anywhere_in_the_app(self):
        """Guard: every spawn is a fixed argv list; shell=True never appears."""
        for path in app_python_files():
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    for item in node.keywords:
                        if item.arg == "shell":
                            self.assertTrue(isinstance(item.value, ast.Constant) and item.value.value is False,
                                            "%s:%d passes shell=" % (path.relative_to(REPO_ROOT), node.lineno))

    def test_adapter_allow_list_is_the_pinned_list(self):
        from folio.backlog.adapter import ALLOWED_FIRST_WORDS
        self.assertEqual(ALLOWED_FIRST_WORDS, ("init", "task", "doctor", "config", "doc", "--version"))

    def test_scanner_catches_planted_sites(self):
        import tempfile
        planted = {
            "import subprocess\n": "imports subprocess",
            "from subprocess import run\n": "imports subprocess",
            "import pty\n": "imports pty",
            "import multiprocessing.pool\n": "imports multiprocessing.pool",
            "import os\nos.system('true')\n": "os.system",
            "import os\nos.posix_spawn('/bin/true', [], {})\n": "os.posix_spawn",
            "import os\nos.execvp('true', ['true'])\n": "os.execvp",
            "import os\nos.fork()\n": "os.fork",
        }
        with tempfile.TemporaryDirectory(prefix="folio-wp6-scan-") as tmp:
            root = Path(tmp)
            for index, (text, reason) in enumerate(planted.items()):
                path = root / ("planted_%d.py" % index)
                path.write_text(text, encoding="utf-8")
                with self.subTest(planted=reason):
                    hits = process_sites([path], root)
                    self.assertTrue(hits and hits[-1].endswith(": " + reason), hits)
            clean = root / "clean.py"
            clean.write_text("import os, json\nvalue = os.path.exists('x')\nos.open('x', os.O_RDONLY)\n", encoding="utf-8")
            self.assertEqual(process_sites([clean], root), [])


class SpawnSpy:
    """Replaces subprocess.Popen and the os spawn primitives; records the caller's stack and refuses to spawn."""

    def __init__(self):
        self.calls = []

    def record(self, name):
        def refused(*args, **kwargs):
            frames = [frame.filename for frame in traceback.extract_stack()]
            self.calls.append((name, args[:1], frames))
            raise OSError("spawn refused by the WP-6 spy: %s" % name)
        return refused

    def __enter__(self):
        self.patches = [mock.patch.object(subprocess, "Popen", self.record("subprocess.Popen"))]
        self.patches += [mock.patch.object(os, name, self.record("os." + name)) for name in SPY_TARGETS if hasattr(os, name)]
        for patch in self.patches:
            patch.start()
        return self

    def __exit__(self, *exc):
        for patch in reversed(self.patches):
            patch.stop()
        return False

    def outside_allow_list(self):
        found = []
        for name, head, frames in self.calls:
            if not any(frame.replace(os.sep, "/").endswith(site) for frame in frames for site in ALLOWED_SPAWN_SITES):
                site = next((Path(frame).relative_to(REPO_ROOT).as_posix() for frame in reversed(frames)
                             if frame.startswith(str(REPO_ROOT)) and "/tests/" not in frame.replace(os.sep, "/")), "?")
                found.append("%s from %s (%r)" % (name, site, head))
        return found


class SpySelfTests(unittest.TestCase):
    def test_spy_sees_subprocess_run_and_os_spawns_and_refuses_them(self):
        with SpawnSpy() as spy:
            with self.assertRaises(OSError):
                subprocess.run(["true"], check=False)
            with self.assertRaises(OSError):
                os.system("true")
            with self.assertRaises(OSError):
                os.posix_spawn("/bin/true", ["true"], {})
        self.assertEqual([name for name, _, _ in spy.calls], ["subprocess.Popen", "os.system", "os.posix_spawn"])
        self.assertEqual(len(spy.outside_allow_list()), 3)

    def test_spy_classifies_an_adapter_spawn_as_allowed(self):
        from folio.backlog.adapter import BacklogClient
        with SpawnSpy() as spy:
            client = BacklogClient("/nonexistent/backlog", REPO_ROOT, REPO_ROOT, environ={})
            try:
                client._run(["--version"])
            except Exception:
                pass
        self.assertEqual([name for name, _, _ in spy.calls], ["subprocess.Popen"])
        self.assertEqual(spy.outside_allow_list(), [])


class NoRouteSpawnsTests(ServerCase):
    """Drive every route with a credential while the spy refuses spawns; none may come from outside the allow-list."""

    def setUp(self):
        super().setUp()
        module = self.plugins()
        host = module.PluginHost()
        host.mount(FakePlugin())
        # A Mac-style platform makes any native picker or dialog code reach for /usr/bin/osascript, so a
        # route that still spawns is caught on any box without requiring zenity or kdialog.
        with mock.patch.object(sys, "platform", "darwin"):
            self.serve(App(self.store, plugins=host))

    def drive(self):
        """Hit every route; return the (method, path, payload) of any 5xx so the spawn check can be asserted first."""
        failures = []
        status, client, _ = self.call("/api/clients", "POST", {"name": "Client A"}, self.owner())
        self.assertEqual(status, 200, client)
        status, project, _ = self.call("/api/projects", "POST", {"client_id": client["id"], "name": "Project A"}, self.owner())
        self.assertEqual(status, 200, project)
        bodies = {"brief": {"query": "plan"}, "source": {"source_id": "0123456789abcdef"}, "sections": {"title": "Note", "text": "t", "kind": "note"},
                  "relocate": {"folder": project.get("folder", "")}, "workstreams": {"name": "Stream"}, "tasks": {"title": "Task"},
                  "append": {"text": "more"}, "resolve": {"decision": "approve"}, "ping": None, "items": {"title": "x"}}
        for method, path in CORE_ROUTES + (("GET", "/api/plugins/fake/ping"),):
            if method in ("POST", "PATCH", "DELETE") and path in ("/api/clients", "/api/projects"):
                continue
            real = path.replace("0123456789abcdef", project["id"], 1)
            body = None if method == "GET" else bodies.get(path.rstrip("/").rsplit("/", 1)[-1], {})
            if path.endswith("/clients/0123456789abcdef"):
                real, body = "/api/clients/%s" % client["id"], {"name": "Client B"}
            status, payload, _ = self.call(real, method, body, self.owner())
            if status >= 500:
                failures.append((method, real, payload))
        for method, path, body in REMOVED_ROUTES:
            real = path.replace("0123456789abcdef", project["id"], 1)
            self.call(real, method, body, self.owner())
        return failures

    def test_no_route_spawns_outside_the_adapter_allow_list(self):
        with SpawnSpy() as spy:
            failures = self.drive()
        self.assertEqual(spy.outside_allow_list(), [])
        self.assertEqual(failures, [], "a kept route answered 5xx while spawns were refused")

    def test_folder_picker_route_spawns_nothing_and_is_404(self):
        with SpawnSpy() as spy:
            status, payload, _ = self.call("/api/folders/pick", "POST", {}, self.owner())
        self.assertEqual((status, payload), (404, {"error": "Not found."}))
        self.assertEqual(spy.calls, [], "the folder picker route reached a process spawn")


if __name__ == "__main__":
    unittest.main()
