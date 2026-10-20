"""WP-6 red tests: the route table lists only the core and plugin-mount routes, the cut routes are 404
even when authenticated (owner token, browser session + CSRF, direct transport), and the cut CLI
commands and server flag are usage errors.

Removed routes stay 403 without a credential (no route enumeration), exactly like unknown paths.
"""

import argparse
import io
import json
import re
import tempfile
import unittest
from pathlib import Path
from unittest import mock
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from folio.api import App, route
from folio.core import AppError

from wp6_support import (CORE_ROUTES, DECISION, ID, METHODS, NOT_FOUND, PLUGIN_ROUTES, REMOVED_ROUTES, seam_attr)
from wp7_support import FORBIDDEN, FakePlugin, ServerCase

USER = {"origin": "user", "via": None}


def table_entries(case):
    table = seam_attr(case, "api", "ROUTE_TABLE")
    entries = []
    for entry in table:
        case.assertEqual(len(entry), 2, "a ROUTE_TABLE entry is (method, pattern): %r" % (entry,))
        method, pattern = entry
        case.assertIn(method, METHODS + ("*",), entry)
        entries.append((method, getattr(pattern, "pattern", pattern)))
    return entries


def matches(entries, method, path):
    return [entry for entry in entries if entry[0] in (method, "*") and re.fullmatch(entry[1], path)]


class RouteTableTests(unittest.TestCase):
    def test_api_exposes_a_route_table(self):
        entries = table_entries(self)
        self.assertTrue(entries, "ROUTE_TABLE is empty")

    def test_route_table_lists_only_core_and_plugin_mount_routes(self):
        entries = table_entries(self)
        for method, path in CORE_ROUTES:
            with self.subTest(method=method, path=path):
                self.assertEqual(len(matches(entries, method, path)), 1, "expected exactly one core entry")
        for method, path in PLUGIN_ROUTES:
            with self.subTest(method=method, path=path):
                found = matches(entries, method, path)
                self.assertEqual(len(found), 1, "expected exactly one plugin-mount entry")
                self.assertEqual(found[0][0], "*", "the plugin mount is one method-agnostic entry")
        for method, path, _ in REMOVED_ROUTES:
            with self.subTest(removed=path):
                self.assertEqual(matches(entries, method, path), [], "%s %s is still listed" % (method, path))
        examples = CORE_ROUTES + PLUGIN_ROUTES
        for entry in entries:
            with self.subTest(entry=entry):
                self.assertTrue(any(entry in matches([entry], method, path) for method, path in examples),
                                "ROUTE_TABLE entry %r is neither a core route nor the plugin mount" % (entry,))

    def test_a_listed_path_with_an_unlisted_method_is_404(self):
        """WP6-2: dispatch keys on (method, path); a known path with another method is not routed to its handler."""
        from folio.core import Store
        mismatched = (("DELETE", "/api/state"), ("GET", "/api/clients"), ("PATCH", "/api/projects/%s/brief" % ID),
                      ("POST", "/api/projects/%s/notes/sections/%s" % (ID, ID)), ("GET", "/api/approvals/%s/resolve" % DECISION))
        with tempfile.TemporaryDirectory(prefix="folio-wp6-") as tmp:
            store = Store(Path(tmp) / "workspace")
            try:
                app = App(store)
                for method, path in mismatched:
                    with self.subTest(method=method, path=path):
                        with self.assertRaises(AppError) as caught:
                            route(app, method, path, None if method == "GET" else {}, USER)
                        self.assertEqual((caught.exception.status, str(caught.exception)), (404, "Not found."))
                self.assertEqual(store.state()["clients"], [], "a mismatched method reached a handler")
            finally:
                store.close()

    def test_every_listed_route_is_dispatched(self):
        """Every table entry reaches a handler: no route is listed and then refused with the generic 404."""
        table_entries(self)
        from folio.core import Store
        with tempfile.TemporaryDirectory(prefix="folio-wp6-") as tmp:
            store = Store(Path(tmp) / "workspace")
            try:
                app = App(store)
                client = route(app, "POST", "/api/clients", {"name": "Client A"}, USER)
                project = route(app, "POST", "/api/projects", {"client_id": client["id"], "name": "Project A"}, USER)
                for method, path in CORE_ROUTES:
                    real = path.replace("0123456789abcdef", project["id"], 1)
                    with self.subTest(method=method, path=real):
                        try:
                            route(app, method, real, None if method == "GET" else {}, USER)
                        except AppError as error:
                            self.assertNotEqual((error.status, str(error)), NOT_FOUND, "listed route is not dispatched")
                        except (ValueError, KeyError, TypeError):
                            pass  # a handler ran and refused the placeholder data; that is dispatch
            finally:
                store.close()


class RemovedRoutesOverHttpTests(ServerCase):
    def setUp(self):
        super().setUp()
        module = self.plugins()
        host = module.PluginHost()
        self.plugin = FakePlugin()
        host.mount(self.plugin)
        self.serve(App(self.store, plugins=host))

    def session_headers(self):
        cookie, proof = self.session()
        return {"Origin": self.base, "Cookie": cookie, "X-Folio-Session": proof, "X-Workspace-Token": self.server.csrf_token}

    def test_removed_routes_are_404_for_the_owner_token(self):
        for method, path, body in REMOVED_ROUTES:
            with self.subTest(method=method, path=path):
                status, payload, _ = self.call(path, method, body, self.owner())
                self.assertEqual((status, payload), NOT_FOUND)

    def test_removed_routes_are_404_for_a_browser_session_with_csrf(self):
        headers = self.session_headers()
        for method, path, body in REMOVED_ROUTES:
            with self.subTest(method=method, path=path):
                status, payload, _ = self.call(path, method, body, headers)
                self.assertEqual((status, payload), NOT_FOUND)

    def test_removed_paths_are_404_for_every_method(self):
        for _, path, _ in REMOVED_ROUTES:
            for method in METHODS:
                with self.subTest(method=method, path=path):
                    status, payload, _ = self.call(path, method, None if method == "GET" else {}, self.owner())
                    self.assertEqual((status, payload), NOT_FOUND)

    def test_removed_routes_are_403_without_a_credential(self):
        """Guard: a cut route refuses like any other path before routing (no enumeration)."""
        for method, path, body in REMOVED_ROUTES:
            with self.subTest(method=method, path=path):
                status, payload, _ = self.call(path, method, body, {"Origin": self.base})
                self.assertEqual((status, payload), FORBIDDEN)

    def test_demo_route_leaves_the_workspace_empty(self):
        status, _, _ = self.call("/api/demo", "POST", {}, self.owner())
        self.assertEqual(status, 404)
        status, state, _ = self.call("/api/state", headers=self.owner())
        self.assertEqual(status, 200)
        self.assertEqual((state["clients"], state["projects"]), ([], []), "the demo seed ran")

    def test_export_of_an_existing_project_is_404(self):
        status, client, _ = self.call("/api/clients", "POST", {"name": "Client A"}, self.owner())
        self.assertEqual(status, 200, client)
        status, project, _ = self.call("/api/projects", "POST", {"client_id": client["id"], "name": "Project A"}, self.owner())
        self.assertEqual(status, 200, project)
        status, payload, headers = self.call("/api/projects/%s/export" % project["id"], headers=self.owner())
        self.assertEqual((status, payload), NOT_FOUND)
        self.assertIsNone(headers.get("Content-Disposition"))

    def test_backup_download_is_404_with_no_attachment_header(self):
        status, payload, headers = self.call("/api/backup", headers=self.owner())
        self.assertEqual((status, payload), NOT_FOUND)
        self.assertIsNone(headers.get("Content-Disposition"))

    def test_theme_script_is_not_served(self):
        try:
            response = urlopen(Request(self.base + "/theme.js"), timeout=10)
        except HTTPError as error:
            response = error
        with response:
            self.assertEqual(response.status, 404)

    def test_core_routes_still_answer(self):
        """Guard: the cuts leave the kept routes and the plugin mount in place."""
        status, state, _ = self.call("/api/state", headers=self.owner())
        self.assertEqual(status, 200)
        self.assertIn("csrf_token", state)
        status, payload, _ = self.call("/api/plugins/fake/ping", headers=self.owner())
        self.assertEqual((status, payload["pong"]), (200, True))


class RemovedRoutesOverDirectTransportTests(unittest.TestCase):
    """The CLI's in-process transport shares route(): the cut routes are 404 there too."""

    def setUp(self):
        from folio.core import Store
        tmp = tempfile.TemporaryDirectory(prefix="folio-wp6-")
        self.addCleanup(tmp.cleanup)
        self.store = Store(Path(tmp.name) / "workspace")
        self.addCleanup(self.store.close)

    def test_route_raises_not_found(self):
        app = App(self.store)
        for method, path, body in REMOVED_ROUTES:
            with self.subTest(method=method, path=path):
                # Exception, not AppError: on the base the picker route raises its own error type.
                with self.assertRaises(Exception) as caught:
                    route(app, method, path, body, USER)
                self.assertIsInstance(caught.exception, AppError, repr(caught.exception))
                self.assertEqual((caught.exception.status, str(caught.exception)), (404, "Not found."))

    def test_direct_transport_reports_404(self):
        from folio.transport import DirectTransport, TransportError
        transport = DirectTransport(App(self.store), {"origin": "cli", "via": None})
        for method, path, body in REMOVED_ROUTES:
            with self.subTest(method=method, path=path):
                with self.assertRaises(TransportError) as caught:
                    transport.request(method, path, body)
                self.assertEqual((caught.exception.status, str(caught.exception)), (404, "Not found."))


class CutCliCommandsTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="folio-wp6-cli-")
        self.addCleanup(tmp.cleanup)
        self.workspace = str(Path(tmp.name) / "workspace")
        self.home = Path(tmp.name) / "home"
        self.home.mkdir()

    def run_cli(self, *argv):
        from folio.cli import main
        stdout = io.StringIO()
        code = main(["--data-dir", self.workspace, *argv], env={"HOME": str(self.home)}, stdout=stdout)
        text = stdout.getvalue()
        try:
            return code, json.loads(text)
        except ValueError:  # the base prints the raw guide text: not an error envelope
            return code, {"ok": True, "raw": text[:80]}

    def assert_usage(self, code, payload, *argv):
        self.assertFalse(payload.get("ok"), "folio %s still runs: %r" % (" ".join(argv), payload))
        self.assertEqual((code, payload["error"]["code"]), (1, "USAGE"), payload)

    def test_task_crud_commands_are_usage_errors(self):
        for argv in (("tasks", "list"), ("tasks", "add", "p", "--title", "t"), ("tasks", "update", "t"),
                     ("tasks", "done", "t"), ("tasks", "reopen", "t"), ("tasks", "delete", "t", "--yes"), ("tasks",)):
            with self.subTest(argv=argv):
                code, payload = self.run_cli(*argv)
                self.assert_usage(code, payload, *argv)
        self.assertFalse(Path(self.workspace).exists(), "a cut command created the workspace")

    def test_agent_guide_is_a_usage_error(self):
        # Path.home() is redirected so that, on the base, the still-present installer cannot touch the real home.
        with mock.patch("pathlib.Path.home", return_value=self.home):
            for argv in (("agent-guide",), ("agent-guide", "--install", "codex")):
                with self.subTest(argv=argv):
                    code, payload = self.run_cli(*argv)
                    self.assert_usage(code, payload, *argv)
        self.assertEqual(sorted(path.name for path in self.home.rglob("*")), [], "agent-guide wrote under HOME")

    def test_parser_offers_neither_tasks_nor_agent_guide(self):
        from folio.cli import build_parser
        parser = build_parser()
        commands = [action for action in parser._actions if isinstance(action, argparse._SubParsersAction)]
        self.assertEqual(len(commands), 1)
        names = sorted(commands[0].choices)
        self.assertNotIn("tasks", names)
        self.assertNotIn("agent-guide", names)
        self.assertIn("doctor", names, "the CLI doctor stays; only the HTTP /api/doctor is cut")

    def test_guide_module_is_gone(self):
        import importlib
        with self.assertRaises(ImportError):
            importlib.import_module("folio.guide")


class ServerDemoFlagTests(unittest.TestCase):
    def test_server_refuses_demo_flag_before_opening_a_workspace(self):
        import folio.web as web

        class Opened(Exception):
            pass

        with tempfile.TemporaryDirectory(prefix="folio-wp6-web-") as tmp:
            with mock.patch.object(web, "Store", side_effect=Opened), mock.patch("sys.stderr", new=io.StringIO()):
                try:
                    with self.assertRaises(SystemExit) as caught:
                        web.main(["--demo", "--data-dir", str(Path(tmp) / "workspace"), "--port", "0"])
                except Opened:
                    self.fail("folio-server accepted --demo and opened the workspace")
        self.assertEqual(caught.exception.code, 2)

    def test_server_help_mentions_no_demo(self):
        import folio.web as web
        with mock.patch("sys.stdout", new=io.StringIO()) as out:
            with self.assertRaises(SystemExit):
                web.main(["--help"])
        self.assertNotIn("--demo", out.getvalue())


if __name__ == "__main__":
    unittest.main()
