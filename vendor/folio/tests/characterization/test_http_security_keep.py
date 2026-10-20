"""@keep goldens: the Folio 1.1.2 local HTTP security behaviour (folio/web.py, folio/local_auth.py).

Every test name carries a stable KEEP-SEC-NN identifier listed in tests/KEEP.md. Later work packages
may refactor the server, but these tests must stay green unchanged.
"""

import io
import json
import os
import re
import stat
import tempfile
import threading
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from folio.core import AppError, Store
from folio.local_auth import browser_url, owner_credential, read_server_info
from folio.web import make_server

from .golden import assert_golden

POSIX = os.name != "nt"


class ServerCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.temp.name) / "workspace")
        self.start()

    def start(self):
        self.server = make_server(self.store, 0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_port}"

    def stop(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def tearDown(self):
        self.stop()
        self.store.close()
        self.temp.cleanup()

    def call(self, path, method="GET", body=None, headers=None, raw=None):
        data = raw if raw is not None else json.dumps(body).encode() if body is not None else None
        request = Request(self.base + path, method=method, data=data,
                          headers={"Content-Type": "application/json", **(headers or {})})
        try:
            response = urlopen(request, timeout=5)
        except HTTPError as error:
            response = error
        with response:
            payload = response.read()
            content_type = response.headers.get("Content-Type", "")
            return response.status, json.loads(payload) if content_type.startswith("application/json") else payload, response.headers

    def owner(self, **extra):
        return {"X-Workspace-Token": self.server.token, **extra}

    def session(self):
        status, value, headers = self.call("/api/session", "POST", {"credential": self.server.browser_token}, {"Origin": self.base})
        self.assertEqual(status, 200)
        return headers["Set-Cookie"], headers["Set-Cookie"].split(";", 1)[0], value["session_proof"]

    def client_count(self):
        return len(self.store.registry()["clients"])


class HttpSecurityKeepTests(ServerCase):
    def test_keep_sec01_unauthenticated_api_is_403(self):
        """@keep KEEP-SEC-01: every /api/* read and write without owner token or session is 403 FORBIDDEN, and nothing is saved."""
        project = "/api/projects/a1b2c3d4e5f60718"
        attempts = [("GET", "/api/state", None), ("GET", "/api/backup", None), ("GET", "/api/decisions", None),
                    ("GET", "/api/session", None), ("GET", project + "/export", None), ("POST", "/api/clients", {"name": "Not saved"}),
                    ("POST", project + "/brief", {"query": ""}), ("POST", "/api/shutdown", {}),
                    ("PATCH", project, {"revision": 1}), ("DELETE", project, {"revision": 1})]
        results = {}
        for method, path, body in attempts:
            with self.subTest(method=method, path=path):
                status, payload, _ = self.call(path, method, body, {"X-Workspace-Token": "0" * 64})
                results[f"{method} {path.replace('a1b2c3d4e5f60718', '<id>')}"] = [status, payload]
        self.assertEqual(self.client_count(), 0)
        self.assertTrue(self.thread.is_alive())
        assert_golden(self, "keep_sec01_unauthenticated", results)

    def test_keep_sec02_wrong_host_is_403(self):
        """@keep KEEP-SEC-02: a Host other than 127.0.0.1:<port>/localhost:<port> is 403 before auth, on API and static paths."""
        port = self.server.server_port
        for host in ("example.com", f"example.com:{port}", f"127.0.0.1:{port + 1}", "127.0.0.1", f"0.0.0.0:{port}", f"[::1]:{port}"):
            for method, path, body in (("GET", "/api/state", None), ("GET", "/", None), ("POST", "/api/clients", {"name": "Forged"})):
                with self.subTest(host=host, path=path):
                    status, payload, _ = self.call(path, method, body, self.owner(Host=host))
                    self.assertEqual((status, payload), (403, {"error": "Invalid local host."}))
        for host in (f"127.0.0.1:{port}", f"localhost:{port}"):
            self.assertEqual(self.call("/api/state", headers=self.owner(Host=host))[0], 200)
        self.assertEqual(self.client_count(), 0)

    def test_keep_sec03_foreign_origin_is_403(self):
        """@keep KEEP-SEC-03: an Origin other than http://127.0.0.1:<port> or http://localhost:<port> is 403, even with the owner token."""
        port = self.server.server_port
        for origin in ("https://example.com", "null", f"https://127.0.0.1:{port}", f"http://127.0.0.1:{port + 1}",
                       f"http://example.com:{port}", f"http://localhost:{port}/"):
            for method, path, body in (("GET", "/api/state", None), ("POST", "/api/clients", {"name": "Forged"}),
                                       ("POST", "/api/session", {"credential": self.server.browser_token})):
                with self.subTest(origin=origin, path=path):
                    status, payload, _ = self.call(path, method, body, self.owner(Origin=origin))
                    self.assertEqual((status, payload), (403, {"error": "Cross-origin requests are not allowed."}))
        for origin in (f"http://127.0.0.1:{port}", f"http://localhost:{port}"):
            self.assertEqual(self.call("/api/state", headers=self.owner(Origin=origin))[0], 200)
        self.assertEqual(self.client_count(), 0)

    def test_keep_sec04_non_json_write_is_415(self):
        """@keep KEEP-SEC-04: an authenticated write whose Content-Type is not application/json is 415 and saves nothing."""
        for content_type in ("text/plain", "application/x-www-form-urlencoded", "multipart/form-data; boundary=x",
                             "application/json-patch+json", "text/json"):
            with self.subTest(content_type=content_type):
                status, payload, _ = self.call("/api/clients", "POST", {"name": "Not saved"}, self.owner(**{"Content-Type": content_type}))
                self.assertEqual((status, payload), (415, {"error": "Expected application/json."}))
        self.assertEqual(self.client_count(), 0)
        status, _, _ = self.call("/api/clients", "POST", {"name": "Saved"}, self.owner(**{"Content-Type": "application/json; charset=utf-8"}))
        self.assertEqual(status, 200)

    def test_keep_sec05_state_carries_no_credentials(self):
        """@keep KEEP-SEC-05: /api/state never contains the owner token, the browser launch token or a session secret; only csrf_token."""
        cookie_header, cookie, proof = self.session()
        session_value = cookie.split("=", 1)[1]
        for headers in (self.owner(), {"Cookie": cookie, "X-Folio-Session": proof}):
            status, state, _ = self.call("/api/state", headers=headers)
            self.assertEqual(status, 200)
            text = json.dumps(state)
            for secret in (self.server.token, self.server.browser_token, proof, session_value):
                self.assertNotIn(secret, text)
            self.assertNotIn("token", state)
            self.assertNotIn("owner_token", text)
            self.assertNotIn("browser_token", text)
            self.assertEqual(state["csrf_token"], self.server.csrf_token)
            self.assertNotEqual(state["csrf_token"], self.server.token)

    def test_keep_sec06_session_cookie_attributes(self):
        """@keep KEEP-SEC-06: the session cookie is per-port, HttpOnly; SameSite=Strict; Path=/api, and the bootstrap needs the launch token."""
        cookie_header, _, proof = self.session()
        self.assertRegex(cookie_header, rf"\Afolio_session_{self.server.server_port}=[a-f0-9]{{64}}; HttpOnly; SameSite=Strict; Path=/api\Z")
        self.assertRegex(proof, r"\A[a-f0-9]{64}\Z")
        refusals = {}
        for name, body, headers in (("wrong_credential", {"credential": "0" * 64}, {}),
                                    ("owner_token_is_not_launch_token", {"credential": self.server.token}, {}),
                                    ("non_ascii", {"credential": "非 ASCII"}, {}),
                                    ("not_a_string", {"credential": 7}, {})):
            status, payload, response = self.call("/api/session", "POST", body, headers)
            self.assertIsNone(response.get("Set-Cookie"))
            refusals[name] = [status, payload]
        assert_golden(self, "keep_sec06_session_refusals", refusals)

    def test_keep_sec07_csrf_on_browser_writes(self):
        """@keep KEEP-SEC-07: browser-session writes need cookie + X-Folio-Session proof + X-Workspace-Token csrf; reads need cookie + proof."""
        _, cookie, proof = self.session()
        csrf = self.server.csrf_token
        refused = [{"Cookie": cookie}, {"Cookie": cookie, "X-Folio-Session": proof}, {"X-Workspace-Token": csrf},
                   {"Cookie": cookie, "X-Workspace-Token": csrf}, {"X-Folio-Session": proof, "X-Workspace-Token": csrf},
                   {"Cookie": cookie, "X-Folio-Session": proof, "X-Workspace-Token": "0" * 64}]
        for headers in refused:
            with self.subTest(headers=sorted(headers)):
                self.assertEqual(self.call("/api/clients", "POST", {"name": "Not saved"}, headers)[0], 403)
        self.assertEqual(self.client_count(), 0)
        for headers in ({"Cookie": cookie}, {"X-Folio-Session": proof}):
            self.assertEqual(self.call("/api/state", headers=headers)[0], 403)
        self.assertEqual(self.call("/api/state", headers={"Cookie": cookie, "X-Folio-Session": proof})[0], 200)
        allowed = {"Cookie": cookie, "X-Folio-Session": proof, "X-Workspace-Token": csrf, "Origin": self.base}
        self.assertEqual(self.call("/api/clients", "POST", {"name": "Saved"}, allowed)[0], 200)
        self.assertEqual(self.call("/api/clients", "POST", {"name": "Owner"}, self.owner())[0], 200)
        self.assertEqual(self.client_count(), 2)

    def test_keep_sec08_discovery_file_private_and_nofollow(self):
        """@keep KEEP-SEC-08: .server.json is a 0600 regular file with exactly these keys; reads refuse symlinks, other modes and bad URLs."""
        path = self.store.root / ".server.json"
        info = read_server_info(self.store.root)
        self.assertEqual(sorted(info), ["browser_token", "owner_token", "pid", "port", "started_at"])
        self.assertEqual((info["port"], info["pid"], info["owner_token"], info["browser_token"]),
                         (self.server.server_port, os.getpid(), self.server.token, self.server.browser_token))
        self.assertEqual(owner_credential(self.store.root, self.base), self.server.token)
        self.assertEqual(browser_url(self.store.root, self.base), f"{self.base}/#folio-launch={self.server.browser_token}")
        for wrong in (f"http://localhost:{self.server.server_port}", f"http://127.0.0.1:{self.server.server_port + 1}"):
            with self.assertRaises(ValueError):
                owner_credential(self.store.root, wrong)
            with self.assertRaises(ValueError):
                browser_url(self.store.root, wrong)
        if not POSIX:
            return
        mode = path.lstat().st_mode
        self.assertTrue(stat.S_ISREG(mode))
        self.assertEqual(stat.S_IMODE(mode), 0o600)
        for unsafe in (0o640, 0o644, 0o660, 0o604, 0o700):
            path.chmod(unsafe)
            try:
                with self.assertRaises(ValueError):
                    read_server_info(self.store.root)
            finally:
                path.chmod(0o600)
        saved = self.store.root / "saved-discovery"
        path.rename(saved)
        path.symlink_to(saved.name)
        try:
            with self.assertRaises((OSError, ValueError)):
                read_server_info(self.store.root)
        finally:
            path.unlink()
            saved.rename(path)
        self.assertEqual(read_server_info(self.store.root)["owner_token"], self.server.token)

    def test_keep_sec10_credentials_rotate_on_restart(self):
        """@keep KEEP-SEC-10: a restart issues new owner, launch and csrf tokens, forgets every session and removes discovery on close."""
        old = (self.server.token, self.server.browser_token, self.server.csrf_token)
        _, cookie, proof = self.session()
        old_session = cookie.split("=", 1)[1]
        self.stop()
        self.assertFalse((self.store.root / ".server.json").exists())
        self.start()
        new = (self.server.token, self.server.browser_token, self.server.csrf_token)
        for before, after in zip(old, new):
            self.assertNotEqual(before, after)
        self.assertEqual(len(set(new)), 3)
        self.assertEqual(self.server.sessions, {})
        replay = {"Cookie": f"{self.server.cookie_name}={old_session}", "X-Folio-Session": proof}
        self.assertEqual(self.call("/api/state", headers=replay)[0], 403)
        self.assertEqual(self.call("/api/state", headers={"X-Workspace-Token": (old[0])})[0], 403)
        self.assertEqual(self.call("/api/session", "POST", {"credential": old[1]})[0], 403)

    def test_keep_sec11_logs_exclude_bodies_queries_and_secrets(self):
        """@keep KEEP-SEC-11: the access log records method, path and status only: no body, query, header, cookie or token."""
        _, cookie, proof = self.session()
        marker = "private-body-marker-example"
        log = io.StringIO()
        with redirect_stderr(log):
            self.call("/api/state?q=private-query-marker", headers={"Cookie": cookie, "X-Folio-Session": proof})
            self.call("/api/clients", "POST", {"name": marker}, self.owner())
            self.call("/api/clients", "POST", {"name": marker}, {"X-Workspace-Token": "0" * 64})
            self.call("/api/clients", "POST", raw=b'{"name": "' + marker.encode() + b'"', headers=self.owner())
            self.call("/api/session", "POST", {"credential": self.server.browser_token}, {"Origin": self.base})
        text = log.getvalue()
        self.assertIn('"POST /api/clients HTTP/1.1" 200', text)
        self.assertIn('"GET /api/state HTTP/1.1" 200', text)
        for secret in (marker, "private-query-marker", self.server.token, self.server.browser_token, self.server.csrf_token,
                       proof, cookie.split("=", 1)[1], "0" * 64):
            self.assertNotIn(secret, text)

    def test_keep_sec12_security_response_headers(self):
        """@keep KEEP-SEC-12: API, static and error responses carry CSP, nosniff, no-referrer and no-store."""
        results = {}
        for name, (path, headers) in {"api": ("/api/state", self.owner()), "static": ("/", {}),
                                      "forbidden": ("/api/state", {}), "not_found": ("/missing", {})}.items():
            status, _, response = self.call(path, headers=headers)
            results[name] = {"status": status, **{key: response[key] for key in
                             ("Content-Security-Policy", "X-Content-Type-Options", "Referrer-Policy", "Cache-Control")}}
        assert_golden(self, "keep_sec12_headers", results)

    def test_keep_sec13_loopback_only_bind(self):
        """@keep KEEP-SEC-13: the server listens on 127.0.0.1 only and accepts only its own port's Host names."""
        port = self.server.server_port
        self.assertEqual(self.server.server_address[0], "127.0.0.1")
        self.assertEqual(self.server.allowed_hosts, {f"127.0.0.1:{port}", f"localhost:{port}"})
        self.assertEqual(self.server.cookie_name, f"folio_session_{port}")


@unittest.skipUnless(POSIX, "POSIX workspace permissions")
class WorkspacePermissionsKeepTests(unittest.TestCase):
    def test_keep_sec09_workspace_permissions(self):
        """@keep KEEP-SEC-09: a new workspace is 0700 under umask 002; a group- or other-writable one is refused with no discovery written."""
        with tempfile.TemporaryDirectory() as folder:
            old_umask = os.umask(0o002)
            try:
                store = Store(Path(folder) / "fresh")
            finally:
                os.umask(old_umask)
            try:
                self.assertEqual(stat.S_IMODE(store.root.stat().st_mode), 0o700)
                server = make_server(store, 0)
                try:
                    self.assertEqual(stat.S_IMODE((store.root / ".server.json").stat().st_mode), 0o600)
                finally:
                    server.server_close()
                self.assertFalse((store.root / ".server.json").exists())
            finally:
                store.close()
            for mode in (0o770, 0o702, 0o722, 0o777):
                with self.subTest(mode=oct(mode)):
                    workspace = Path(folder) / f"shared-{mode:o}"
                    workspace.mkdir(mode=0o700)
                    workspace.chmod(mode)
                    store = Store(workspace)
                    try:
                        with self.assertRaises(AppError) as error:
                            make_server(store, 0)
                        self.assertEqual((error.exception.status, str(error.exception)), (403,
                            "The workspace directory must be owned by this account and not writable by other accounts."))
                        self.assertEqual(stat.S_IMODE(workspace.stat().st_mode), mode)
                        self.assertFalse((workspace / ".server.json").exists())
                    finally:
                        store.close()


if __name__ == "__main__":
    unittest.main()
