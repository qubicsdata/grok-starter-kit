import json as _json
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent.parent


class PackageSplitTests(unittest.TestCase):
    def test_server_shim_reexports_package_objects(self):
        import server
        from folio import core, web
        self.assertIs(server.Store, core.Store)
        self.assertIs(server.AppError, core.AppError)
        self.assertIs(server.make_server, web.make_server)

    def test_server_help_still_works(self):
        result = subprocess.run([sys.executable, str(ROOT / "server.py"), "--help"], capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
        for flag in ("--port", "--data-dir"):
            self.assertIn(flag, result.stdout)

    def test_route_table_serves_state_and_mutations_without_http(self):
        from folio.api import App, route
        from folio.core import AppError, Store
        with tempfile.TemporaryDirectory() as temporary:
            store = Store(temporary)
            try:
                app = App(store)
                actor = {"origin": "user", "via": None}
                client = route(app, "POST", "/api/clients", {"name": "Route client"}, actor)
                project = route(app, "POST", "/api/projects", {"client_id": client["id"], "name": "Routed"}, actor)
                task = route(app, "POST", f"/api/projects/{project['id']}/tasks", {"title": "T", "revision": 1}, actor)
                self.assertEqual(task["title"], "T")
                state = route(app, "GET", "/api/state", None, actor)
                self.assertEqual(state["projects"][0]["tasks"][0]["id"], task["id"])
                with self.assertRaises(AppError) as error:
                    route(app, "POST", "/api/unknown", {}, actor)
                self.assertEqual(error.exception.status, 404)
            finally:
                store.close()


class ActivityMetadataTests(unittest.TestCase):
    def setUp(self):
        from folio.core import Store
        self.temporary = tempfile.TemporaryDirectory()
        self.store = Store(self.temporary.name)
        self.client = self.store.create_client({"name": "C"})
        self.project = self.store.create_project({"client_id": self.client["id"], "name": "P"})

    def tearDown(self):
        self.store.close()
        self.temporary.cleanup()

    def test_activity_records_origin_via_and_resulting_revision(self):
        cli = {"origin": "cli", "via": "cli:codex"}
        self.store.create_task(self.project["id"], {"title": "A", "revision": 1}, actor=cli)
        project = self.store.project(self.project["id"])
        entry = project["activity"][0]
        self.assertEqual(entry["origin"], "cli")
        self.assertEqual(entry["via"], "cli:codex")
        self.assertEqual(entry["revision"], project["revision"])
        self.store.update_project(project["id"], {"revision": project["revision"], "name": "P2"})
        project = self.store.project(self.project["id"])
        self.assertEqual(project["activity"][0]["origin"], "user")
        self.assertNotIn("via", project["activity"][0])
        self.assertEqual(project["activity"][0]["revision"], project["revision"])

    def test_append_notes_needs_no_revision_and_never_overwrites(self):
        project = self.store.project(self.project["id"])
        self.store.update_project(project["id"], {"revision": project["revision"], "notes": "Saved by user"})
        self.store.append_notes(project["id"], {"text": "Agent summary"}, actor={"origin": "cli", "via": "cli"})
        project = self.store.project(self.project["id"])
        self.assertEqual(project["notes"], "Saved by user\n\nAgent summary")
        self.assertEqual(project["activity"][0]["message"], "Notes appended")
        from folio.core import AppError
        with self.assertRaises(AppError):
            self.store.append_notes(project["id"], {"text": "   "})
        with self.assertRaises(AppError):
            self.store.append_notes(project["id"], {"text": "x" * 100000})

    def test_invalid_activity_origin_is_rejected(self):
        from folio.core import AppError, validate_project
        project = self.store.project(self.project["id"])
        project["activity"][0]["origin"] = "robot"
        with self.assertRaises(AppError):
            validate_project(project)

    def test_invalid_actor_is_rejected_before_writing(self):
        from folio.core import AppError
        project = self.store.project(self.project["id"])
        revision, task_count = project["revision"], len(project["tasks"])
        for bad in ({"origin": "robot", "via": None}, {"origin": "cli", "via": "Bad Label!"}, "not a dict"):
            with self.assertRaises(AppError):
                self.store.create_task(self.project["id"], {"title": "A", "revision": revision}, actor=bad)
            project = self.store.project(self.project["id"])
            self.assertEqual(project["revision"], revision)
            self.assertEqual(len(project["tasks"]), task_count)

    def test_http_actor_headers_and_error_codes(self):
        from folio.core import AppError
        from folio.web import make_server
        server = make_server(self.store, 0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            base = f"http://127.0.0.1:{server.server_address[1]}"

            def post(path, data, headers):
                request = Request(base + path, method="POST", data=_json.dumps(data).encode(),
                                  headers={"Content-Type": "application/json", "X-Workspace-Token": server.token, **headers})
                with urlopen(request, timeout=5) as response:
                    return _json.loads(response.read())

            post(f"/api/projects/{self.project['id']}/notes/append", {"text": "From CLI"},
                 {"X-Folio-Origin": "cli", "X-Folio-Via": "cli:claude-code"})
            post(f"/api/projects/{self.project['id']}/notes/append", {"text": "Bad label"},
                 {"X-Folio-Origin": "cli", "X-Folio-Via": "Robert'); DROP"})
            activity = self.store.project(self.project["id"])["activity"]
            self.assertEqual((activity[1]["origin"], activity[1]["via"]), ("cli", "cli:claude-code"))
            self.assertEqual(activity[0]["origin"], "cli")
            self.assertNotIn("via", activity[0])
            # An AppError code travels as the JSON envelope's "code".
            with patch.object(server.app.store, "append_notes", side_effect=AppError("Nope", 409, "EXAMPLE_CODE")):
                request = Request(base + f"/api/projects/{self.project['id']}/notes/append", method="POST", data=b'{"text": "x"}',
                                  headers={"Content-Type": "application/json", "X-Workspace-Token": server.token})
                with self.assertRaises(Exception) as caught:
                    urlopen(request, timeout=5)
                body = _json.loads(caught.exception.read())
                self.assertEqual(body, {"error": "Nope", "code": "EXAMPLE_CODE"})
        finally:
            server.shutdown()
            server.server_close()
            thread.join()


if __name__ == "__main__":
    unittest.main()
