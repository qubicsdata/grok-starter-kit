"""WP-13 security regression suite, part 1: the kept 1.1.2 model and the Backlog-board CSRF probe.

Kept (WP-1 `@keep`, tests/KEEP.md): the registry is intact (every KEEP-SEC id names an un-skipped test
with its `@keep` docstring, the keep_* goldens exist and refuse rewriting) and each kept behaviour is
exercised once more from this suite's own isolated fixture: unauthenticated -> 403; wrong Host or Origin
-> 403; non-JSON -> 415; no token in /api/state; the cookie attributes; CSRF on browser writes; the
discovery file 0600 with O_NOFOLLOW; workspace permissions; credentials rotate on restart; logs exclude
bodies.

Probe: the requests that wrote a task through the Backlog.md board (UPSTREAM-backlog-browser-report.md:
no auth -> 200, any Host -> 200, cross-origin text/plain POST -> 201 and a task file) are replayed
against Folio ONLY, in every spelling a browser can produce, and must all be 403 with nothing written.
The board is never started.
"""

import importlib
import io
import os
import stat
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from unittest import mock

from folio.core import AppError, Store
from folio.local_auth import browser_url, owner_credential, read_server_info
from folio.web import make_server

from wp13_support import (ATTACKER, FORBIDDEN, FORM_PROBE_BODY, HOST_REFUSED, NON_JSON, ORIGIN_REFUSED, PROBE_BODY, RELOAD,
                          REPO_ROOT, SHA256, TESTS, SecurityCase, keep_rows, mode_of)

POSIX = os.name != "nt"
GOLDENS = TESTS / "characterization" / "goldens"


class KeepRegistryTests(unittest.TestCase):
    """tests/KEEP.md is the contract WP-13 must keep green unchanged; this proves the contract is still wired."""

    def test_keep_md_lists_the_thirteen_ids_once_each(self):
        ids = [row[0] for row in keep_rows()]
        self.assertEqual(ids, ["KEEP-SEC-%02d" % number for number in range(1, 14)])

    def test_every_keep_id_names_an_unskipped_test_with_its_keep_docstring(self):
        for keep_id, locator in keep_rows():
            with self.subTest(keep_id=keep_id):
                file_part, class_name, method_name = locator.split("::")
                path = REPO_ROOT / file_part
                self.assertTrue(path.is_file(), locator)
                module_name = ".".join(path.relative_to(TESTS).with_suffix("").parts)
                module = importlib.import_module(module_name)
                case = getattr(module, class_name)
                self.assertTrue(issubclass(case, unittest.TestCase), locator)
                method = getattr(case, method_name)
                self.assertIn("test_keep_sec%s_" % keep_id[-2:], method_name, locator)
                self.assertTrue((method.__doc__ or "").startswith("@keep %s:" % keep_id), locator)
                for target in (method, case):
                    self.assertFalse(getattr(target, "__unittest_skip__", False), "%s is skipped" % locator)
                self.assertFalse(getattr(method, "__unittest_expecting_failure__", False), locator)

    def test_the_keep_module_loads_thirteen_keep_tests_under_the_default_pattern(self):
        """`discover -s tests` collects test_*.py; the module name and file sit where the default run finds them."""
        module = importlib.import_module("characterization.test_http_security_keep")
        self.assertEqual(Path(module.__file__).resolve(), (TESTS / "characterization" / "test_http_security_keep.py").resolve())
        self.assertTrue((TESTS / "characterization" / "__init__.py").is_file(), "the package marker discovery needs")
        suite = unittest.defaultTestLoader.loadTestsFromModule(module)
        ids = sorted(test.id() for test in iterate(suite))
        kept = [test_id for test_id in ids if ".test_keep_sec" in test_id]
        self.assertEqual(len(kept), 13, ids)
        self.assertFalse(any("_FailedTest" in test_id for test_id in ids), ids)

    def test_the_keep_goldens_exist_and_refuse_rewriting(self):
        from characterization.golden import assert_golden
        for name in ("keep_sec01_unauthenticated", "keep_sec06_session_refusals", "keep_sec12_headers"):
            self.assertTrue((GOLDENS / (name + ".json")).is_file(), name)
        probe = GOLDENS / "keep_sec99_probe.json"
        self.assertFalse(probe.exists())
        with mock.patch.dict(os.environ, {"FOLIO_UPDATE_GOLDENS": "1"}):
            with self.assertRaises(AssertionError):
                assert_golden(self, "keep_sec99_probe", {"never": "written"})
        self.assertFalse(probe.exists(), "a keep_* golden was written in update mode")


def iterate(suite):
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from iterate(item)
        else:
            yield item


class KeptBehaviourTests(SecurityCase):
    """The ten kept behaviours of the brief's WP-13 section, each exercised from this fixture."""

    def setUp(self):
        super().setUp()
        self.serve_default()

    def test_kept_unauthenticated_api_is_403_and_writes_nothing(self):
        attempts = (("GET", "/api/state", None), ("GET", "/api/approvals", None), ("POST", "/api/clients", {"name": "x"}),
                    ("POST", "/api/projects", {"client_id": "0" * 16, "name": "x"}),
                    ("PATCH", "/api/clients/0123456789abcdef", {"name": "x"}),
                    ("DELETE", "/api/projects/0123456789abcdef/tasks/0123456789abcdef", {}),
                    ("POST", "/api/shutdown", {}), ("GET", "/api/plugins/fake/ping", None), ("GET", "/api/nothing", None))
        for method, path, body in attempts:
            for name, headers in (("no credential", {}), ("wrong owner token", {"X-Workspace-Token": "0" * 64}),
                                  ("csrf token alone", {"X-Workspace-Token": self.server.csrf_token}),
                                  ("launch token as owner token", {"X-Workspace-Token": self.server.browser_token})):
                with self.subTest(method=method, path=path, attempt=name):
                    status, payload, _ = self.call(path, method, body, headers)
                    self.assertEqual((status, payload), FORBIDDEN)
        self.assertEqual(self.counts(), (0, 0))
        self.assertEqual(self.call("/api/state", headers=self.owner())[0], 200, "the server stopped")

    def test_kept_wrong_host_is_403_before_authentication(self):
        port = self.server.server_port
        for host in ("%s:%d" % (ATTACKER, port), "127.0.0.1:%d" % (port + 1), "localhost", "127.0.0.1", "[::1]:%d" % port,
                     "127.0.0.1.%s:%d" % (ATTACKER, port), "0.0.0.0:%d" % port, "", "127.0.0.1:%d.%s" % (port, ATTACKER)):
            for path in ("/api/state", "/", "/api/session"):
                with self.subTest(host=host, path=path):
                    method = "POST" if path == "/api/session" else "GET"
                    body = b'{"credential": "%s"}' % self.server.browser_token.encode() if method == "POST" else None
                    status, payload, _ = self.raw(method, path, {"X-Workspace-Token": self.server.token,
                                                                 "Content-Type": "application/json"}, body, host=host)
                    self.assertEqual((status, payload), HOST_REFUSED)
        for host in ("127.0.0.1:%d" % port, "localhost:%d" % port):
            with self.subTest(host=host):
                self.assertEqual(self.raw("GET", "/api/state", {"X-Workspace-Token": self.server.token}, host=host)[0], 200)

    def test_kept_foreign_origin_is_403_even_with_the_owner_token(self):
        port = self.server.server_port
        for origin in ("https://%s" % ATTACKER, "http://%s:%d" % (ATTACKER, port), "null", "http://127.0.0.1:%d" % (port + 1),
                       "https://127.0.0.1:%d" % port, "http://127.0.0.1.%s:%d" % (ATTACKER, port), "http://127.0.0.1",
                       "http://127.0.0.1:%d.%s" % (port, ATTACKER), "file://"):
            for method, path, body in (("GET", "/api/state", None), ("POST", "/api/clients", {"name": "x"}),
                                       ("POST", "/api/session", {"credential": self.server.browser_token})):
                with self.subTest(origin=origin, path=path):
                    status, payload, response = self.call(path, method, body, self.owner(Origin=origin))
                    self.assertEqual((status, payload), ORIGIN_REFUSED)
                    self.assertIsNone(response.get("Set-Cookie"))
        self.assertEqual(self.counts(), (0, 0))

    def test_kept_non_json_write_is_415_and_saves_nothing(self):
        for content_type in ("text/plain", "text/plain; charset=utf-8", "application/x-www-form-urlencoded",
                             "multipart/form-data; boundary=x", "application/jsonx", "text/json", "application/json-patch+json",
                             "APPLICATION/JSON", ""):
            with self.subTest(content_type=content_type):
                headers = {"X-Workspace-Token": self.server.token}
                if content_type:
                    headers["Content-Type"] = content_type
                status, payload, _ = self.raw("POST", "/api/clients", headers, b'{"name": "Not saved"}')
                self.assertEqual((status, payload), NON_JSON)
        self.assertEqual(self.counts(), (0, 0))
        status, _, _ = self.raw("POST", "/api/clients", {"X-Workspace-Token": self.server.token,
                                                         "Content-Type": "application/json; charset=utf-8"}, b'{"name": "Saved"}')
        self.assertEqual(status, 200)
        self.assertEqual(self.counts(), (1, 0))

    def test_kept_state_carries_no_credential(self):
        reader = self.reader()
        secrets_ = {"owner token": self.server.token, "launch token": self.server.browser_token,
                    "session cookie": reader["Cookie"].split("=", 1)[1], "session proof": reader["X-Folio-Session"]}
        for name, headers in (("owner token", self.owner()), ("session", reader)):
            status, payload, response = self.call("/api/state", headers=headers)
            self.assertEqual(status, 200)
            text = response.as_string() + repr(payload)
            for label, secret in secrets_.items():
                self.assertNotIn(secret, text, "%s leaks the %s" % (name, label))
            self.assertEqual(payload["csrf_token"], self.server.csrf_token)

    def test_kept_session_cookie_is_httponly_samesite_strict_path_api(self):
        status, payload, response = self.exchange(self.server.browser_token)
        self.assertEqual(status, 200)
        self.assertRegex(response["Set-Cookie"],
                         r"\Afolio_session_%d=[a-f0-9]{64}; HttpOnly; SameSite=Strict; Path=/api\Z" % self.server.server_port)
        self.assertRegex(payload["session_proof"], SHA256)
        for credential in (self.server.token, self.server.csrf_token, "", None, 7, "0" * 64, self.server.browser_token.upper()):
            with self.subTest(credential=credential):
                status, payload, response = self.exchange(credential)
                self.assertEqual((status, payload), FORBIDDEN)
                self.assertIsNone(response.get("Set-Cookie"))

    def test_kept_browser_writes_need_the_csrf_token(self):
        reader = self.reader()
        cookie, proof = reader["Cookie"], reader["X-Folio-Session"]
        refused = {"cookie only": {"Cookie": cookie}, "cookie and proof": {"Cookie": cookie, "X-Folio-Session": proof},
                   "csrf only": {"X-Workspace-Token": self.server.csrf_token},
                   "cookie and csrf": {"Cookie": cookie, "X-Workspace-Token": self.server.csrf_token},
                   "wrong csrf": {"Cookie": cookie, "X-Folio-Session": proof, "X-Workspace-Token": "0" * 64},
                   "launch token as csrf": {"Cookie": cookie, "X-Folio-Session": proof, "X-Workspace-Token": self.server.browser_token}}
        for name, headers in refused.items():
            with self.subTest(attempt=name):
                status, _, _ = self.call("/api/clients", "POST", {"name": "Not saved"}, {"Origin": self.base, **headers})
                self.assertEqual(status, 403)
        self.assertEqual(self.counts(), (0, 0))
        self.assertEqual(self.call("/api/state", headers={"Cookie": cookie})[0], 403)
        self.assertEqual(self.call("/api/state", headers=reader)[0], 200)
        # The same session with the CSRF token (not a second exchange: the launch credential is single-use).
        self.assertEqual(self.call("/api/clients", "POST", {"name": "Saved"}, {**reader, "X-Workspace-Token": (self.server.csrf_token)})[0], 200)
        self.assertEqual(self.counts(), (1, 0))

    @unittest.skipUnless(POSIX, "POSIX file modes and O_NOFOLLOW")
    def test_kept_discovery_file_is_0600_regular_and_read_with_o_nofollow(self):
        path = self.store.root / ".server.json"
        info = read_server_info(self.store.root)
        self.assertEqual(sorted(info), ["browser_token", "owner_token", "pid", "port", "started_at"])
        self.assertTrue(stat.S_ISREG(path.lstat().st_mode))
        self.assertEqual(mode_of(path), 0o600)
        self.assertEqual(owner_credential(self.store.root, self.base), self.server.token)
        self.assertEqual(browser_url(self.store.root, self.base), "%s/#folio-launch=%s" % (self.base, self.server.browser_token))
        flags = []
        real_open = os.open

        def recording_open(target, flag, *args, **kwargs):
            if Path(os.fsdecode(target)) == path:
                flags.append(flag)
            return real_open(target, flag, *args, **kwargs)

        with mock.patch("os.open", side_effect=recording_open):
            read_server_info(self.store.root)
        self.assertTrue(flags and all(flag & os.O_NOFOLLOW for flag in flags), "discovery read without O_NOFOLLOW: %r" % flags)
        for unsafe in (0o640, 0o644, 0o660, 0o604, 0o700, 0o400):
            path.chmod(unsafe)
            try:
                with self.subTest(mode=oct(unsafe)):
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

    def test_kept_credentials_rotate_on_restart_and_old_ones_are_refused(self):
        old = (self.server.token, self.server.browser_token, self.server.csrf_token)
        reader = self.reader()
        self.restart()
        new = (self.server.token, self.server.browser_token, self.server.csrf_token)
        self.assertEqual(len(set(old + new)), 6, "a credential survived the restart")
        self.assertEqual(self.server.sessions, {})
        self.assertEqual(self.call("/api/state", headers={"X-Workspace-Token": (old[0])})[0], 403)
        self.assertEqual(self.exchange(old[1])[0], 403)
        self.assertEqual(self.call("/api/state", headers={**reader, "Origin": self.base})[0], 403)
        self.assertEqual(self.call("/api/clients", "POST", {"name": "x"}, {**reader, "X-Workspace-Token": (old[2])})[0], 403)
        self.assertEqual(read_server_info(self.store.root)["owner_token"], new[0])
        self.assertEqual(self.call("/api/state", headers=self.owner())[0], 200)

    def test_kept_access_log_excludes_bodies_queries_headers_and_tokens(self):
        reader = self.reader()
        marker = "private-body-marker-example"
        log = io.StringIO()
        with redirect_stderr(log):
            self.call("/api/state?q=private-query-marker#frag", headers=reader)
            self.call("/api/clients", "POST", {"name": marker}, self.owner(**{"X-Private-Header": "private-header-marker"}))
            self.call("/api/clients", "POST", {"name": marker}, {"X-Workspace-Token": "0" * 64})
            self.raw("POST", "/api/clients", {"X-Workspace-Token": self.server.token, "Content-Type": "text/plain"}, marker.encode())
            self.raw("POST", "/api/clients", {"X-Workspace-Token": self.server.token, "Content-Type": "application/json"},
                     b'{"name": "' + marker.encode() + b'"')
            self.raw("GET", "/api/state", {"Cookie": "folio_session_1=private-cookie-marker"}, host="%s:1" % ATTACKER)
        text = log.getvalue()
        self.assertIn('"POST /api/clients HTTP/1.1" 200', text)
        self.assertIn('"GET /api/state HTTP/1.1" 200', text)
        self.assertIn('"GET /api/state HTTP/1.1" 403', text)
        for secret in (marker, "private-query-marker", "frag", "private-header-marker", "private-cookie-marker", ATTACKER,
                       self.server.token, self.server.browser_token, self.server.csrf_token, reader["X-Folio-Session"],
                       reader["Cookie"].split("=", 1)[1], "0" * 64):
            self.assertNotIn(secret, text)

    def test_kept_loopback_bind_and_security_headers(self):
        self.assertEqual(self.server.server_address[0], "127.0.0.1")
        for path, headers in (("/api/state", self.owner()), ("/", {}), ("/api/state", {}), ("/missing", {})):
            with self.subTest(path=path, authenticated=bool(headers)):
                _, _, response = self.call(path, headers=headers) if path.startswith("/api") else self.raw("GET", path, headers)
                self.assertEqual(response.get("Cache-Control"), "no-store")
                self.assertEqual(response.get("X-Content-Type-Options"), "nosniff")
                self.assertEqual(response.get("Referrer-Policy"), "no-referrer")
                self.assertIn("frame-ancestors 'none'", response.get("Content-Security-Policy", ""))


@unittest.skipUnless(POSIX, "POSIX workspace permissions")
class KeptWorkspacePermissionsTests(unittest.TestCase):
    def test_kept_workspace_is_0700_and_a_shared_workspace_is_refused(self):
        with tempfile.TemporaryDirectory(prefix="folio-wp13-ws-") as folder:
            previous = os.umask(0o002)
            try:
                store = Store(Path(folder) / "fresh")
            finally:
                os.umask(previous)
            try:
                self.assertEqual(mode_of(store.root), 0o700)
                server = make_server(store, 0)
                try:
                    self.assertEqual(mode_of(store.root / ".server.json"), 0o600)
                finally:
                    server.server_close()
                self.assertFalse((store.root / ".server.json").exists(), "discovery survived close")
            finally:
                store.close()
            for mode in (0o770, 0o707, 0o702, 0o722, 0o777):
                with self.subTest(mode=oct(mode)):
                    workspace = Path(folder) / ("shared-%o" % mode)
                    workspace.mkdir(mode=0o700)
                    workspace.chmod(mode)
                    store = Store(workspace)
                    try:
                        with self.assertRaises(AppError) as caught:
                            make_server(store, 0)
                        self.assertEqual(caught.exception.status, 403)
                        self.assertEqual(mode_of(workspace), mode, "the mode was changed")
                        self.assertFalse((workspace / ".server.json").exists())
                    finally:
                        store.close()


class BacklogBoardProbeTests(SecurityCase):
    """The Backlog-board CSRF probe (UPSTREAM report, reproduction steps 1-3 and the browser variants) against Folio."""

    def setUp(self):
        super().setUp()
        self.serve_default()
        self.port = self.server.server_port
        self.targets = ("/api/clients", "/api/projects", "/api/tasks", "/api/projects/0123456789abcdef/tasks")

    def assert_nothing_written(self):
        self.assertEqual(self.counts(), (0, 0))
        self.assertEqual(self.call("/api/state", headers=self.owner())[1]["projects"], [])

    def test_step_1_an_unauthenticated_read_is_403_and_reveals_nothing(self):
        for path in ("/api/state", "/api/tasks", "/api/config", "/api/projects"):
            with self.subTest(path=path):
                status, payload, _ = self.raw("GET", path)
                self.assertEqual((status, payload), FORBIDDEN)

    def test_step_2_a_rebinding_host_is_refused_also_with_a_credential(self):
        host = "%s:%d" % (ATTACKER, self.port)
        for path in ("/api/state", "/api/tasks", "/", "/app.js"):
            for headers in ({}, {"X-Workspace-Token": self.server.token}):
                with self.subTest(path=path, credential=bool(headers)):
                    status, payload, _ = self.raw("GET", path, headers, host=host)
                    self.assertEqual((status, payload), HOST_REFUSED)
        for method in ("PUT", "PATCH", "DELETE", "POST"):
            with self.subTest(method=method):
                status, payload, _ = self.raw(method, "/api/clients", {"X-Workspace-Token": self.server.token,
                                                                       "Content-Type": "application/json"}, PROBE_BODY, host=host)
                self.assertNotEqual(status, 200)
                self.assertIn(status, (403, 501))
        self.assert_nothing_written()

    def test_step_3_a_cross_origin_text_plain_post_is_403_and_writes_nothing(self):
        origin = "http://%s" % ATTACKER
        for path in self.targets:
            for name, body in (("fetch no-cors", PROBE_BODY), ("form text/plain", FORM_PROBE_BODY)):
                with self.subTest(path=path, variant=name):
                    status, payload, _ = self.raw("POST", path, {"Origin": origin, "Content-Type": "text/plain"}, body)
                    self.assertEqual((status, payload), ORIGIN_REFUSED)
        self.assert_nothing_written()

    def test_step_3_without_an_origin_header_is_403_too(self):
        """curl's spelling of the probe, and a form posted from a page that sends no Origin."""
        for path in self.targets:
            for content_type in ("text/plain", "application/x-www-form-urlencoded", "multipart/form-data; boundary=x", "application/json"):
                with self.subTest(path=path, content_type=content_type):
                    status, payload, _ = self.raw("POST", path, {"Content-Type": content_type}, PROBE_BODY)
                    self.assertEqual((status, payload), FORBIDDEN)
        self.assert_nothing_written()

    def test_an_opaque_null_origin_is_refused(self):
        for path in self.targets:
            with self.subTest(path=path):
                status, payload, _ = self.raw("POST", path, {"Origin": "null", "Content-Type": "text/plain"}, PROBE_BODY)
                self.assertEqual((status, payload), ORIGIN_REFUSED)
        self.assert_nothing_written()

    def test_bodiless_cross_origin_posts_do_nothing_and_the_server_keeps_running(self):
        origin = "http://%s" % ATTACKER
        for path in ("/api/shutdown", "/api/projects/0123456789abcdef/relocate", "/api/tasks/1/complete", "/api/init"):
            for headers in ({"Origin": origin}, {}):
                with self.subTest(path=path, origin="Origin" in headers):
                    status, payload, _ = self.raw("POST", path, headers)
                    self.assertEqual((status, payload), ORIGIN_REFUSED if headers else FORBIDDEN)
        self.assertEqual(self.call("/api/state", headers=self.owner())[0], 200, "the server stopped")

    def test_a_leaked_owner_token_still_needs_json_and_a_local_origin(self):
        token = {"X-Workspace-Token": self.server.token}
        for path in ("/api/clients", "/api/projects"):
            with self.subTest(path=path, variant="text/plain"):
                status, payload, _ = self.raw("POST", path, {**token, "Content-Type": "text/plain"}, PROBE_BODY)
                self.assertEqual((status, payload), NON_JSON)
            with self.subTest(path=path, variant="json from a foreign origin"):
                status, payload, _ = self.raw("POST", path, {**token, "Content-Type": "application/json",
                                                             "Origin": "http://%s" % ATTACKER}, PROBE_BODY)
                self.assertEqual((status, payload), ORIGIN_REFUSED)
        self.assert_nothing_written()

    def test_a_live_browser_session_does_not_make_the_probe_succeed(self):
        """Folio is open in another tab: cookie attached, proof and CSRF token unknown to the attacker page."""
        reader = self.reader()
        cookie, proof = reader["Cookie"], reader["X-Folio-Session"]
        origin = "http://%s" % ATTACKER
        for path in self.targets:
            with self.subTest(path=path, variant="cookie, cross-origin text/plain"):
                status, payload, _ = self.raw("POST", path, {"Origin": origin, "Cookie": cookie, "Content-Type": "text/plain"}, PROBE_BODY)
                self.assertEqual((status, payload), ORIGIN_REFUSED)
            with self.subTest(path=path, variant="cookie, no origin, json"):
                status, payload, _ = self.raw("POST", path, {"Cookie": cookie, "Content-Type": "application/json"}, PROBE_BODY)
                self.assertEqual((status, payload), FORBIDDEN)
            with self.subTest(path=path, variant="cookie and proof, no csrf token"):
                status, payload, _ = self.raw("POST", path, {"Cookie": cookie, "X-Folio-Session": proof,
                                                             "Content-Type": "application/json"}, PROBE_BODY)
                self.assertEqual((status, payload), RELOAD)
        self.assert_nothing_written()

    def test_the_probe_response_carries_no_data_and_no_cookie(self):
        status, payload, response = self.raw("POST", "/api/clients", {"Origin": "http://%s" % ATTACKER,
                                                                      "Content-Type": "text/plain"}, PROBE_BODY)
        self.assertEqual(status, 403)
        self.assertIsNone(response.get("Set-Cookie"))
        self.assertIsNone(response.get("Access-Control-Allow-Origin"))
        self.assertEqual(sorted(payload), ["error"])
        self.assertNotIn("csrf-probe", response.as_string() + repr(payload))


if __name__ == "__main__":
    unittest.main()
