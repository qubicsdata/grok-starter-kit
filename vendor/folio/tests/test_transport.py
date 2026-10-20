import http.client
import json
import os
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from unittest.mock import patch

from folio.core import STORAGE_MESSAGE, Store, read_json
from folio.migration import migrate_workspace
from folio.transport import HttpTransport, TransportError, connect, find_server
from folio.web import make_server, remove_server_info, write_server_info

CLI = {"origin": "cli", "via": "cli:test"}


class TransportTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name) / "workspace"

    def tearDown(self):
        self.temporary.cleanup()

    def test_direct_transport_when_no_server(self):
        transport = connect(self.root, CLI)
        try:
            self.assertEqual(transport.kind, "direct")
            client = transport.request("POST", "/api/clients", {"name": "Direct"})
            self.assertEqual(transport.request("GET", "/api/state")["clients"][0]["id"], client["id"])
        finally:
            transport.close()
        with self.assertRaises(TransportError) as error:
            direct = connect(self.root, CLI)
            try:
                direct.request("POST", "/api/nowhere", {})
            finally:
                direct.close()
        self.assertEqual(error.exception.status, 404)

    def test_http_transport_when_server_running(self):
        store = Store(self.root)
        server = make_server(store, 0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        info = write_server_info(store.root, server.server_address[1])
        try:
            self.assertEqual(info.stat().st_mode & 0o777, 0o600)
            self.assertEqual(read_json(info)["pid"], os.getpid())
            transport = connect(self.root, CLI)
            self.assertEqual(transport.kind, "http")
            client = transport.request("POST", "/api/clients", {"name": "Over HTTP"})
            project = transport.request("POST", "/api/projects", {"client_id": client["id"], "name": "P"})
            transport.request("POST", f"/api/projects/{project['id']}/notes/append", {"text": "hi"})
            activity = store.project(project["id"])["activity"][0]
            self.assertEqual((activity["origin"], activity["via"]), ("cli", "cli:test"))
            with self.assertRaises(TransportError) as error:
                transport.request("PATCH", f"/api/projects/{project['id']}", {"revision": 999, "name": "Stale"})
            self.assertEqual(error.exception.status, 409)
        finally:
            server.shutdown()
            server.server_close()
            thread.join()
            remove_server_info(store.root)
            store.close()
        self.assertFalse((self.root / ".server.json").exists())

    def test_stale_server_info_falls_back_to_direct(self):
        self.root.mkdir(parents=True)
        (self.root / ".server.json").write_text('{"port": 9, "pid": 999999, "started_at": "x"}')
        transport = connect(self.root, CLI)
        try:
            self.assertEqual(transport.kind, "direct")
        finally:
            transport.close()

    def test_locked_workspace_without_answering_server_is_storage_error(self):
        store = Store(self.root)
        try:
            write_server_info(store.root, 9)
            with self.assertRaises(TransportError) as error:
                connect(self.root, CLI, lock_wait=0.2)
            self.assertEqual((error.exception.status, error.exception.code), (503, "STORAGE"))
        finally:
            remove_server_info(store.root)
            store.close()

    def test_migrated_workspace_reports_destination_without_retrying_a_lock(self):
        Store(self.root).close()
        target = Path(self.temporary.name) / 'migrated'
        migrate_workspace(self.root, target)
        with patch('folio.transport.time.sleep') as sleep:
            with self.assertRaises(TransportError) as error:
                connect(self.root, CLI, lock_wait=0)
        self.assertEqual(error.exception.status, 409)
        self.assertIn(str(target), error.exception.message)
        self.assertIn('migrated', error.exception.message)
        sleep.assert_not_called()

    def test_find_server_rejects_a_server_for_another_workspace(self):
        other = Path(self.temporary.name) / "other"
        store = Store(self.root)
        server = make_server(store, 0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        port = server.server_address[1]
        write_server_info(store.root, port)
        try:
            self.assertEqual(find_server(self.root), f"http://127.0.0.1:{port}")
            other.mkdir(parents=True)
            (other / ".server.json").write_text(json.dumps({"port": port, "pid": os.getpid(), "started_at": "x"}))
            self.assertIsNone(find_server(other))
            before = store.registry()
            transport = connect(other, CLI)
            try:
                self.assertEqual(transport.kind, "direct")
                transport.request("POST", "/api/clients", {"name": "Belongs to other"})
            finally:
                transport.close()
            self.assertEqual(store.registry(), before)
            self.assertEqual([c["name"] for c in read_json(other / "registry.json")["clients"]], ["Belongs to other"])
        finally:
            server.shutdown()
            server.server_close()
            thread.join()
            remove_server_info(store.root)
            store.close()

    def test_find_server_rejects_bad_server_files(self):
        self.root.mkdir(parents=True)
        for content in ("not json", "[]", '{"port": 8765}', f'{{"port": true, "pid": {os.getpid()}}}',
                        f'{{"port": 70000, "pid": {os.getpid()}}}', '{"port": 8765, "pid": 0}'):
            (self.root / ".server.json").write_text(content)
            self.assertIsNone(find_server(self.root), content)

    def test_connect_waits_briefly_for_the_workspace_lock(self):
        holder = Store(self.root)
        releaser = threading.Timer(0.4, holder.close)
        started = time.monotonic()
        releaser.start()
        try:
            transport = connect(self.root, CLI, lock_wait=3)
            try:
                self.assertEqual(transport.kind, "direct")
                self.assertGreaterEqual(time.monotonic() - started, 0.3)
            finally:
                transport.close()
        finally:
            releaser.join()

    def test_connect_gives_up_when_the_lock_stays_held(self):
        holder = Store(self.root)
        try:
            started = time.monotonic()
            with self.assertRaises(TransportError) as error:
                connect(self.root, CLI, lock_wait=0.2)
            self.assertLess(time.monotonic() - started, 2)
            self.assertEqual((error.exception.status, error.exception.code), (503, "STORAGE"))
            self.assertIn("Another Folio process is using this workspace", error.exception.message)
        finally:
            holder.close()

    def test_unopenable_workspace_is_storage_error(self):
        self.root.parent.mkdir(parents=True, exist_ok=True)
        self.root.write_text("a file, not a folder")
        with self.assertRaises(TransportError) as error:
            connect(self.root, CLI, lock_wait=0.2)
        self.assertEqual((error.exception.status, error.exception.code), (500, "STORAGE"))
        self.assertIn("Cannot open the workspace at", error.exception.message)

    def test_direct_transport_maps_data_errors_to_storage(self):
        transport = connect(self.root, CLI)
        try:
            self.assertEqual(transport.kind, "direct")
            for failure in (ValueError("bad json"), OSError("denied"), KeyError("clients"), TypeError("nope")):
                with patch.object(transport.app.store, "state", side_effect=failure):
                    with self.assertRaises(TransportError) as error:
                        transport.request("GET", "/api/state")
                self.assertEqual((error.exception.status, error.exception.code, error.exception.message),
                                 (500, "STORAGE", STORAGE_MESSAGE))
        finally:
            transport.close()

    def test_http_error_body_that_is_not_an_object_is_ignored(self):
        class ListErrorHandler(BaseHTTPRequestHandler):
            def do_GET(self):
                body = b"[1, 2]"
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args):
                pass

        server = HTTPServer(("127.0.0.1", 0), ListErrorHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            transport = HttpTransport(f"http://127.0.0.1:{server.server_address[1]}", CLI)
            with self.assertRaises(TransportError) as error:
                transport.request("GET", "/api/state")
            self.assertEqual((error.exception.status, error.exception.message, error.exception.code), (500, "HTTP 500", None))
        finally:
            server.shutdown()
            server.server_close()
            thread.join()

    def test_http_protocol_errors_are_storage_errors(self):
        transport = HttpTransport("http://127.0.0.1:9", CLI)
        with patch("folio.transport.urlopen", side_effect=http.client.RemoteDisconnected("closed")):
            with self.assertRaises(TransportError) as error:
                transport.request("GET", "/api/state")
        self.assertEqual((error.exception.status, error.exception.code), (503, "STORAGE"))
        with patch("folio.transport.urlopen", side_effect=http.client.IncompleteRead(b"")):
            with self.assertRaises(TransportError) as error:
                transport.request("GET", "/api/state")
        self.assertEqual((error.exception.status, error.exception.code), (503, "STORAGE"))

    def test_malformed_port_falls_back_to_direct(self):
        self.root.mkdir(parents=True)
        (self.root / ".server.json").write_text(
            f'{{"port": "abc", "pid": {os.getpid()}, "started_at": "x"}}'
        )
        transport = connect(self.root, CLI)
        try:
            self.assertEqual(transport.kind, "direct")
        finally:
            transport.close()

    def test_invalid_json_response_falls_back_to_direct(self):
        class PlainTextHandler(BaseHTTPRequestHandler):
            def do_GET(self):
                body = b"hello"
                self.send_response(200)
                self.send_header("Content-Type", "text/plain")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args):
                pass

        server = HTTPServer(("127.0.0.1", 0), PlainTextHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            self.root.mkdir(parents=True)
            (self.root / ".server.json").write_text(
                f'{{"port": {server.server_address[1]}, "pid": {os.getpid()}, "started_at": "x"}}'
            )
            transport = connect(self.root, CLI)
            try:
                self.assertEqual(transport.kind, "direct")
            finally:
                transport.close()
        finally:
            server.shutdown()
            server.server_close()
            thread.join()


if __name__ == "__main__":
    unittest.main()
