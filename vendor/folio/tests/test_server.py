import json
import shutil
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from server import AppError, Store, make_server


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.store = Store(self.root / "workspace")
        self.client = self.store.create_client({"name": "Client A"})
        self.project = self.store.create_project({"client_id": self.client["id"], "name": "Project A"})

    def tearDown(self):
        self.store.close()
        self.temporary.cleanup()

    def task(self, **fields):
        project = self.store.project(self.project["id"])
        return self.store.create_task(project["id"], {"title": "Design review", "revision": project["revision"], **fields})

    def test_project_data_lives_in_its_own_folder_and_survives_restart(self):
        task = self.task(owner="Architect", status="blocked", blocker="Waiting for approval")
        project = self.store.project(self.project["id"])
        self.store.update_project(project["id"], {"revision": project["revision"], "notes": "Decision: use managed services."})
        registry_text = self.store.registry_path.read_text()
        self.assertNotIn("Design review", registry_text)
        self.assertNotIn("managed services", registry_text)
        path = Path(self.store.registration(project["id"])["path"]) / ".task-manager" / "project.json"
        self.assertEqual(json.loads(path.read_text())["tasks"][0]["id"], task["id"])
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        self.store.close()
        self.store = Store(self.root / "workspace")
        loaded = self.store.project(project["id"])
        self.assertEqual(loaded["notes"], "Decision: use managed services.")
        self.assertEqual(loaded["tasks"][0]["blocker"], "Waiting for approval")

    def test_task_cannot_cross_project_boundary(self):
        task = self.task()
        other = self.store.create_project({"client_id": self.client["id"], "name": "Other"})
        with self.assertRaises(AppError) as error:
            self.store.update_task(other["id"], task["id"], {"revision": other["revision"], "status": "done"})
        self.assertEqual(error.exception.status, 404)
        with self.assertRaises(AppError):
            self.task(workstream_id=other["workstreams"][0]["id"])
        self.assertEqual(self.store.project(self.project["id"])["tasks"][0]["status"], "backlog")

    def test_concurrent_edits_detect_conflicts(self):
        task = self.task()
        project = self.store.project(self.project["id"])

        def change(status):
            try:
                self.store.update_task(project["id"], task["id"], {"revision": project["revision"], "status": status})
                return 200
            except AppError as error:
                return error.status

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(change, ["done", "blocked"]))
        self.assertEqual(sorted(results), [200, 409])

    def test_update_delete_and_activity(self):
        task = self.task()
        project = self.store.project(self.project["id"])
        self.store.update_task(project["id"], task["id"], {"revision": project["revision"], "status": "done"})
        project = self.store.project(project["id"])
        self.assertEqual(project["tasks"][0]["status"], "done")
        self.assertIn("Moved to done", project["activity"][0]["message"])
        self.store.update_task(project["id"], task["id"], {"revision": project["revision"]}, delete=True)
        self.assertEqual(self.store.project(project["id"])["tasks"], [])

    def test_validation_does_not_write_partial_data(self):
        before = self.store.project(self.project["id"])
        for fields in [{"title": " "}, {"status": "unknown"}, {"priority": "critical"}, {"due_date": "2026-02-30"}, {"owner": []}, {"workstream_id": "missing"}]:
            with self.subTest(fields=fields), self.assertRaises(AppError):
                self.task(**fields)
        self.assertEqual(before, self.store.project(self.project["id"]))

    def test_missing_or_corrupt_folder_does_not_reset_data(self):
        path = Path(self.store.registration(self.project["id"])["path"]) / ".task-manager" / "project.json"
        path.write_text("invalid json")
        snapshot = self.store.state()
        self.assertEqual(len(snapshot["storage_errors"]), 1)
        self.assertEqual(snapshot["projects"], [])
        with self.assertRaises(AppError):
            self.store.update_project(self.project["id"], {"revision": 1, "name": "Overwrite"})
        self.assertEqual(path.read_text(), "invalid json")
        path.unlink()
        self.assertEqual(len(self.store.state()["storage_errors"]), 1)
        self.assertFalse(path.exists())

    def test_reopen_portable_project_and_preserve_switchboard(self):
        self.task(description="Portable context")
        source = Path(self.store.registration(self.project["id"])["path"])
        portable = self.root / "portable-project"
        shutil.copytree(source, portable)
        (portable / ".switchboard").mkdir()
        sentinel = portable / ".switchboard" / "state.db"
        sentinel.write_bytes(b"untouched switchboard database")
        other = Store(self.root / "other-workspace")
        try:
            client = other.create_client({"name": "New account"})
            project = other.create_project({"client_id": client["id"], "name": "Ignored new name", "folder": str(portable)})
            loaded = other.project(project["id"])
            self.assertEqual(loaded["name"], "Project A")
            self.assertEqual(loaded["tasks"][0]["description"], "Portable context")
            self.assertEqual(loaded["client_id"], client["id"])
            # Since the WP-7 freeze Folio no longer looks for the other app's folder; it still never touches it.
            self.assertNotIn("switchboard_detected", other.state()["projects"][0])
            self.assertEqual(sentinel.read_bytes(), b"untouched switchboard database")
        finally:
            other.close()

    def test_duplicate_project_registration_and_symlink_storage_rejected(self):
        registration = self.store.registration(self.project["id"])
        with self.assertRaises(AppError):
            self.store.create_project({"client_id": self.client["id"], "name": "Duplicate", "folder": registration["path"]})
        folder = self.root / "linked"
        folder.mkdir()
        (folder / ".task-manager").symlink_to(Path(registration["path"]) / ".task-manager", target_is_directory=True)
        with self.assertRaises(AppError):
            self.store.create_project({"client_id": self.client["id"], "name": "Symlink", "folder": str(folder)})

    def test_invalid_portable_project_is_rejected_without_modification(self):
        self.task()
        source = Path(self.store.registration(self.project["id"])["path"])
        portable = self.root / "invalid-import"
        shutil.copytree(source, portable)
        path = portable / ".task-manager" / "project.json"
        project = json.loads(path.read_text())
        project["tasks"][0]["priority"] = '\" onclick=\"alert(1)'
        payload = json.dumps(project)
        path.write_text(payload)
        with self.assertRaises(AppError):
            self.store.create_project({"client_id": self.client["id"], "name": "Invalid", "folder": str(portable)})
        self.assertEqual(path.read_text(), payload)

    def test_workspace_has_one_writer(self):
        with self.assertRaises(AppError):
            Store(self.root / "workspace")

    def test_clients_workstreams_and_archive(self):
        client = self.store.update_client(self.client["id"], {"name": "Renamed", "color": "teal"})
        self.assertEqual(client["name"], "Renamed")
        stream = self.store.create_workstream(self.project["id"], {"revision": 1, "name": "Governance"})
        task = self.task(workstream_id=stream["id"])
        self.assertEqual(task["workstream_id"], stream["id"])
        project = self.store.project(self.project["id"])
        self.store.update_project(project["id"], {"revision": project["revision"], "status": "archived"})
        self.assertEqual(self.store.state()["projects"][0]["status"], "archived")
        self.assertEqual(len(self.store.project(project["id"])["tasks"]), 1)


class HttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory()
        cls.store = Store(cls.temporary.name)
        cls.server = make_server(cls.store, 0)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.server.server_address[1]}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()
        cls.store.close()
        cls.temporary.cleanup()

    def request(self, path, method="GET", data=None, headers=None):
        request_headers = {"Content-Type": "application/json", "X-Workspace-Token": self.server.token, **(headers or {})}
        request = Request(self.base + path, method=method, data=json.dumps(data).encode() if data is not None else None, headers=request_headers)
        try:
            response = urlopen(request, timeout=5)
        except HTTPError as error:
            response = error
        with response:
            body = response.read()
            return response.status, json.loads(body) if response.headers.get_content_type() == "application/json" else body, response.headers

    def test_static_assets_and_state(self):
        for path, content_type in [("/", "text/html"), ("/app.js", "text/javascript"), ("/styles.css", "text/css"), ("/favicon.svg", "image/svg+xml"),
                                   ("/favicon-dark.svg", "image/svg+xml"), ("/manifest.webmanifest", "application/manifest+json"),
                                   *[(f"/{name}", "image/png") for name in ("icon-32.png", "icon-192.png", "icon-512.png", "apple-touch-icon.png")]]:
            with self.subTest(path=path):
                status, body, headers = self.request(path)
                self.assertEqual(status, 200)
                self.assertTrue(body)
                self.assertIn(content_type, headers["Content-Type"])
        status, body, headers = self.request("/api/state")
        self.assertEqual(status, 200)
        self.assertNotIn("token", body)
        self.assertEqual(body["csrf_token"], self.server.csrf_token)
        self.assertNotIn(self.server.token, json.dumps(body))
        self.assertNotIn(self.server.browser_token, json.dumps(body))
        from folio import __version__
        self.assertEqual(body["product"], {"name": "Folio", "version": __version__,
                                         "license": "Apache-2.0",
                                         "license_url": "/LICENSE.txt", "notice_url": "/NOTICE.txt",
                                         "attribution": "", "website": "", "help_url": ""})
        self.assertEqual(headers["Cache-Control"], "no-store")

    def test_packaged_legal_links_serve_the_exact_first_party_texts(self):
        root = Path(__file__).resolve().parents[1]
        for name in ("LICENSE", "NOTICE"):
            with self.subTest(name=name):
                status, body, headers = self.request(f"/{name}.txt")
                self.assertEqual(status, 200)
                self.assertEqual(body, (root / name).read_bytes())
                self.assertEqual(headers.get_content_type(), "text/plain")
                self.assertEqual(headers.get_content_charset(), "utf-8")

    def test_brand_manifest_and_local_icon_dimensions(self):
        _, html, _ = self.request("/")
        self.assertIn(b'<link rel="stylesheet" href="/styles.css">', html)
        self.assertLess(html.index(b'/styles.css'), html.index(b'/app.js'))
        status, body, _ = self.request("/manifest.webmanifest")
        self.assertEqual(status, 200)
        manifest = json.loads(body)
        self.assertEqual(manifest["name"], "Folio")
        self.assertEqual(manifest["start_url"], "/")
        for icon in manifest["icons"]:
            status, data, headers = self.request(icon["src"])
            self.assertEqual(status, 200)
            self.assertEqual(headers.get_content_type(), icon["type"])
            self.assertEqual(data[:8], b"\x89PNG\r\n\x1a\n")
            self.assertEqual(f"{int.from_bytes(data[16:20], 'big')}x{int.from_bytes(data[20:24], 'big')}", icon["sizes"])
        for path in ("/favicon.svg", "/favicon-dark.svg"):
            _, svg, _ = self.request(path)
            self.assertIn(b"M16 3 28 10v12l-12 7-12-7V10z", svg)
            self.assertIn(b"M4 10l12 7 12-7M16 17v12", svg)

    def test_http_project_task_notes_lifecycle(self):
        status, client, _ = self.request("/api/clients", "POST", {"name": "HTTP Client"})
        self.assertEqual(status, 200)
        status, project, _ = self.request("/api/projects", "POST", {"client_id": client["id"], "name": "HTTP project"})
        self.assertEqual(status, 200)
        base = f"/api/projects/{project['id']}"
        status, task, _ = self.request(base + "/tasks", "POST", {"title": "HTTP task", "revision": 1})
        self.assertEqual(status, 200)
        status, body, _ = self.request(base + "/tasks/" + task["id"], "PATCH", {"status": "done", "revision": 2})
        self.assertEqual(status, 200)
        self.assertEqual(body["status"], "done")
        status, body, _ = self.request(base, "PATCH", {"notes": "API decision", "revision": 3})
        self.assertEqual(status, 200)
        self.assertEqual(body["notes"], "API decision")
        self.assertEqual(body["tasks"][0]["status"], "done")

    def test_rejects_cross_origin_and_forged_requests(self):
        for headers in [{"X-Workspace-Token": "wrong"}, {"Origin": "https://untrusted.example"}, {"Host": "untrusted.example"}]:
            with self.subTest(headers=headers):
                status, _, _ = self.request("/api/clients", "POST", {"name": "Forged"}, headers)
                self.assertEqual(status, 403)
        status, _, _ = self.request("/api/state", headers={"Host": "untrusted.example"})
        self.assertEqual(status, 403)
        status, _, _ = self.request("/../server.py")
        self.assertEqual(status, 404)

    def test_bad_request_returns_json_error(self):
        status, body, _ = self.request("/api/clients", "POST", ["not an object"])
        self.assertEqual(status, 400)
        self.assertIn("error", body)
        status, _, _ = self.request("/api/clients", "POST", {"name": "Test"}, {"Content-Type": "text/plain"})
        self.assertEqual(status, 415)
        status, _, _ = self.request("/api/clients", "POST", {"name": ""})
        self.assertEqual(status, 400)


if __name__ == "__main__":
    unittest.main()
