"""WP-5a red tests: the approvals routes behind the /api auth + CSRF, and the no-provider empty state.

POST /api/approvals/<decision id>/resolve needs the owner token, or a browser session (cookie plus
X-Folio-Session proof) plus the CSRF token; every refusal happens before the dialog opens or the
provider is called. With no provider, GET /api/approvals reports the empty state and no route
accepts a resolve. The empty-state UI (app.js) is WP-5b and is not touched here.
"""

import json
import os
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from folio.api import App, build_app
from folio.core import Store
from folio.web import make_server

from wp5_support import FID, FakeProvider, RecordingNotifier, ScriptedDialog, decision, seam

DECISION = "dec_00000000000000a1"
RESOLVE = "/api/approvals/%s/resolve" % DECISION
FORBIDDEN = (403, {"error": "Open this workspace with folio ui to authenticate.", "code": "FORBIDDEN"})
RELOAD = (403, {"error": "Reload the page to reconnect to this workspace."})


class ApprovalsServerCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="folio-wp5-http-")
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)
        self.state = self.dir / "state"
        # XDG_CONFIG_HOME too: build_app() reads the local plugin config (WP-7), never the developer's own.
        environ = mock.patch.dict(os.environ, {"XDG_STATE_HOME": str(self.state), "XDG_CONFIG_HOME": str(self.dir / "config")})
        environ.start()
        self.addCleanup(environ.stop)
        self.store = Store(self.dir / "workspace")
        self.addCleanup(self.store.close)

    def serve(self, app):
        self.server = make_server(self.store, 0, app)
        thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        thread.start()

        def stop():
            self.server.shutdown()
            self.server.server_close()
            thread.join()
        self.addCleanup(stop)
        self.base = "http://127.0.0.1:%d" % self.server.server_port

    def call(self, path, method="GET", body=None, headers=None):
        data = json.dumps(body).encode() if body is not None else None
        request = Request(self.base + path, method=method, data=data, headers={"Content-Type": "application/json", **(headers or {})})
        try:
            response = urlopen(request, timeout=10)
        except HTTPError as error:
            response = error
        with response:
            return response.status, json.loads(response.read()), response.headers

    def owner(self, **extra):
        return {"X-Workspace-Token": self.server.token, **extra}

    def session(self):
        status, value, headers = self.call("/api/session", "POST", {"credential": self.server.browser_token}, {"Origin": self.base})
        self.assertEqual(status, 200)
        return headers["Set-Cookie"].split(";", 1)[0], value["session_proof"]

    def log_path(self):
        return self.state / "folio" / "approvals.jsonl"


class ResolveNeedsAuthAndCsrfTests(ApprovalsServerCase):
    def setUp(self):
        super().setUp()
        module = seam(self)
        self.provider = FakeProvider([decision("a1", fid=FID)])
        self.dialog = ScriptedDialog(*[{"choice": "approve", "text": ""} for _ in range(4)])
        self.inbox = module.Approvals(self.provider, dialog=self.dialog, notifier=RecordingNotifier(),
                                      log=module.ApprovalLog(self.log_path()))
        app = App(self.store)
        app.approvals = self.inbox
        self.serve(app)

    def assert_untouched(self):
        self.assertEqual(self.dialog.asked, [], "the dialog opened for a refused request")
        self.assertEqual(self.provider.calls, [])
        self.assertFalse(self.log_path().exists())

    def test_resolve_without_credentials_is_403(self):
        cookie, proof = self.session()
        attempts = {
            "nothing": {},
            "wrong_owner_token": {"X-Workspace-Token": "0" * 64},
            "proof_without_cookie": {"X-Folio-Session": proof},
            "cookie_without_proof": {"Cookie": cookie},
            "cookie_with_wrong_proof": {"Cookie": cookie, "X-Folio-Session": "0" * 64},
        }
        for name, headers in attempts.items():
            with self.subTest(attempt=name):
                status, payload, _ = self.call(RESOLVE, "POST", {"requested": "approve"}, {"Origin": self.base, **headers})
                self.assertEqual((status, payload), FORBIDDEN)
        self.assert_untouched()

    def test_browser_session_without_the_csrf_token_is_403(self):
        cookie, proof = self.session()
        for name, extra in {"no_csrf": {}, "wrong_csrf": {"X-Workspace-Token": "0" * 64},
                            "browser_token_as_csrf": {"X-Workspace-Token": self.server.browser_token}}.items():
            with self.subTest(attempt=name):
                status, payload, _ = self.call(RESOLVE, "POST", {"requested": "approve"},
                                               {"Origin": self.base, "Cookie": cookie, "X-Folio-Session": proof, **extra})
                self.assertEqual((status, payload), RELOAD)
        self.assert_untouched()

    def test_foreign_origin_is_403_even_with_the_owner_token(self):
        status, payload, _ = self.call(RESOLVE, "POST", {"requested": "approve"}, self.owner(Origin="https://example.com"))
        self.assertEqual((status, payload), (403, {"error": "Cross-origin requests are not allowed."}))
        self.assert_untouched()

    def test_unauthenticated_listing_is_403(self):
        status, payload, _ = self.call("/api/approvals")
        self.assertEqual((status, payload), FORBIDDEN)

    def test_browser_session_with_csrf_reaches_the_dialog_and_resolves(self):
        cookie, proof = self.session()
        status, payload, _ = self.call(RESOLVE, "POST", {"requested": "approve"},
                                       {"Origin": self.base, "Cookie": cookie, "X-Folio-Session": proof,
                                        "X-Workspace-Token": self.server.csrf_token})
        self.assertEqual(status, 200, payload)
        self.assertEqual(payload["result"], "approved")
        self.assertEqual(len(self.dialog.asked), 1)
        self.assertEqual([call["choice"] for call in self.provider.calls], ["approve"])

    def test_owner_token_reaches_the_dialog_and_resolves(self):
        status, payload, _ = self.call(RESOLVE, "POST", {"requested": "approve"}, self.owner())
        self.assertEqual(status, 200, payload)
        self.assertEqual(payload, {"result": "approved", "decision_id": DECISION, "kind": "permission", "remembered": False})
        status, listing, _ = self.call("/api/approvals", headers=self.owner())
        self.assertEqual((status, listing["configured"], listing["decisions"]), (200, True, []))

    def test_get_on_the_resolve_route_never_resolves(self):
        status, _, _ = self.call(RESOLVE, headers=self.owner())
        self.assertEqual(status, 404)
        self.assert_untouched()


class EmptyStateRouteTests(ApprovalsServerCase):
    def check_empty_state(self, app):
        seam(self)
        self.serve(app)
        status, payload, _ = self.call("/api/approvals", headers=self.owner())
        self.assertEqual(status, 200, payload)
        self.assertEqual((payload["configured"], payload["message"], payload["decisions"]),
                         (False, "No approvals source configured", []))
        for path in (RESOLVE, "/api/decisions/%s/resolve" % DECISION):
            with self.subTest(path=path):
                status, payload, _ = self.call(path, "POST", {"requested": "approve"}, self.owner())
                self.assertGreaterEqual(status, 400, "a route accepted a resolve with no provider: %r" % payload)
                if path == RESOLVE:
                    self.assertEqual((status, payload.get("code")), (404, "NO_APPROVALS_SOURCE"))
        self.assertFalse(self.state.exists(), "the empty state wrote local state")

    def test_default_app_has_no_provider_and_refuses_resolve(self):
        self.check_empty_state(App(self.store))

    def test_the_built_app_has_no_provider_and_refuses_resolve(self):
        # WP-7 (3/3): build_app() has no sync switch any more; with no plugin config it has no provider.
        self.check_empty_state(build_app(self.store))


if __name__ == "__main__":
    unittest.main()
