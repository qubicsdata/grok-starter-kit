"""WP-7 red tests: plugin routes sit behind the unchanged /api auth + CSRF pipeline, and the reserved
/api/plugins/switchboard/* prefix is 404 over HTTP in every configuration.

Every refusal happens before a plugin handler runs (the handler's call log stays empty). An
unauthenticated plugin route is 403 (never 200, never 404: the pipeline refuses before routing).
"""

import unittest

from folio.api import App, build_app
from folio.core import AppError

from wp7_support import FORBIDDEN, NOT_FOUND, PREFIX, RELOAD, FakePlugin, ServerCase

PING = "/api/plugins/fake/ping"
ITEMS = "/api/plugins/fake/items"
RESERVED = ("/api/plugins/switchboard", "/api/plugins/switchboard/", "/api/plugins/switchboard/ping",
            "/api/plugins/switchboard/outbox/0123456789abcdef/retry")
HARDENED = {"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff", "Referrer-Policy": "no-referrer"}


class PluginRouteAuthTests(ServerCase):
    def setUp(self):
        super().setUp()
        module = self.plugins()
        self.plugin = FakePlugin(routes=[])
        self.plugin._routes = [("GET", PREFIX + "fake/ping", self.plugin.handle), ("POST", PREFIX + "fake/items", self.plugin.handle)]
        host = module.PluginHost()
        host.mount(self.plugin)
        self.serve(App(self.store, plugins=host))

    def assert_untouched(self):
        self.assertEqual(self.plugin.calls, [], "a plugin handler ran for a refused request")

    def test_unauthenticated_plugin_routes_are_403(self):
        cookie, proof = self.session()
        attempts = {
            "nothing": {},
            "wrong_owner_token": {"X-Workspace-Token": "0" * 64},
            "browser_token_as_owner_token": {"X-Workspace-Token": self.server.browser_token},
            "csrf_token_as_owner_token": {"X-Workspace-Token": self.server.csrf_token},
            "proof_without_cookie": {"X-Folio-Session": proof},
            "cookie_without_proof": {"Cookie": cookie},
            "cookie_with_wrong_proof": {"Cookie": cookie, "X-Folio-Session": "0" * 64},
        }
        for method, path, body in (("GET", PING, None), ("POST", ITEMS, {"title": "x"})):
            for name, headers in attempts.items():
                with self.subTest(method=method, attempt=name):
                    status, payload, _ = self.call(path, method, body, {"Origin": self.base, **headers})
                    self.assertEqual((status, payload), FORBIDDEN)
        self.assert_untouched()

    def test_unauthenticated_unknown_plugin_paths_are_403_not_404(self):
        """No route enumeration without a credential: unknown plugin paths refuse the same way."""
        for path in ("/api/plugins/other/ping", "/api/plugins/fake/nope", "/api/plugins/", PING + "/"):
            with self.subTest(path=path):
                status, payload, _ = self.call(path)
                self.assertEqual((status, payload), FORBIDDEN)
        self.assert_untouched()

    def test_browser_session_without_the_csrf_token_is_403_on_post(self):
        cookie, proof = self.session()
        for name, extra in {"no_csrf": {}, "wrong_csrf": {"X-Workspace-Token": "0" * 64},
                            "browser_token_as_csrf": {"X-Workspace-Token": self.server.browser_token}}.items():
            with self.subTest(attempt=name):
                status, payload, _ = self.call(ITEMS, "POST", {"title": "x"},
                                               {"Origin": self.base, "Cookie": cookie, "X-Folio-Session": proof, **extra})
                self.assertEqual((status, payload), RELOAD)
        self.assert_untouched()

    def test_foreign_origin_is_403_even_with_the_owner_token(self):
        for method, path, body in (("GET", PING, None), ("POST", ITEMS, {"title": "x"})):
            with self.subTest(method=method):
                status, payload, _ = self.call(path, method, body, self.owner(Origin="https://example.com"))
                self.assertEqual((status, payload), (403, {"error": "Cross-origin requests are not allowed."}))
        self.assert_untouched()

    def test_wrong_host_header_is_403(self):
        status, payload, _ = self.call(PING, headers=self.owner(Host="example.com"))
        self.assertEqual((status, payload), (403, {"error": "Invalid local host."}))
        self.assert_untouched()

    def test_owner_token_reaches_the_plugin(self):
        status, payload, headers = self.call(PING, headers=self.owner())
        self.assertEqual((status, payload["pong"]), (200, True))
        status, payload, _ = self.call(ITEMS, "POST", {"title": "x"}, self.owner())
        self.assertEqual((status, payload["method_data"]), (200, {"title": "x"}))
        self.assertEqual([call["path"] for call in self.plugin.calls], [PING, ITEMS])
        self.assertEqual(self.plugin.calls[0]["actor"], {"origin": "user", "via": None})
        for key, value in HARDENED.items():
            self.assertEqual(headers.get(key), value, key)
        self.assertIn("default-src 'self'", headers.get("Content-Security-Policy", ""))

    def test_browser_session_reaches_the_plugin_and_posts_need_the_csrf_token(self):
        cookie, proof = self.session()
        status, payload, _ = self.call(PING, headers={"Origin": self.base, "Cookie": cookie, "X-Folio-Session": proof})
        self.assertEqual((status, payload["pong"]), (200, True))
        status, payload, _ = self.call(ITEMS, "POST", {"title": "x"},
                                       {"Origin": self.base, "Cookie": cookie, "X-Folio-Session": proof,
                                        "X-Workspace-Token": self.server.csrf_token})
        self.assertEqual(status, 200, payload)
        self.assertEqual(len(self.plugin.calls), 2)

    def test_cli_origin_headers_become_the_actor(self):
        status, _, _ = self.call(PING, headers=self.owner(**{"X-Folio-Origin": "cli", "X-Folio-Via": "cli:codex"}))
        self.assertEqual(status, 200)
        self.assertEqual(self.plugin.calls[0]["actor"], {"origin": "cli", "via": "cli:codex"})

    def test_unknown_plugin_paths_are_404_when_authenticated(self):
        for method, path in (("GET", "/api/plugins/other/ping"), ("GET", "/api/plugins/fake/nope"), ("GET", "/api/plugins/fake/"),
                             ("GET", "/api/plugins/fake"), ("GET", "/api/plugins/"), ("GET", "/api/plugins"),
                             ("POST", PING), ("GET", ITEMS), ("PATCH", ITEMS), ("DELETE", ITEMS)):
            with self.subTest(method=method, path=path):
                status, payload, _ = self.call(path, method, None if method == "GET" else {}, self.owner())
                self.assertEqual((status, payload), NOT_FOUND)
        self.assert_untouched()

    def test_a_plugin_app_error_is_an_error_envelope(self):
        def refuse(app, match, data, actor):
            raise AppError("Model is offline.", 503, "PLUGIN_UNAVAILABLE")
        self.plugin._routes = [("GET", PREFIX + "fake/ping", refuse)]
        module = self.plugins()
        host = module.PluginHost()
        host.mount(self.plugin)
        self.server.app = App(self.store, plugins=host)
        status, payload, _ = self.call(PING, headers=self.owner())
        self.assertEqual((status, payload), (503, {"error": "Model is offline.", "code": "PLUGIN_UNAVAILABLE"}))

    def test_post_without_a_json_body_is_refused_before_the_plugin(self):
        status, payload, _ = self.call(ITEMS, "POST", None, self.owner())
        self.assertEqual(status, 413, payload)
        self.assert_untouched()


class SwitchboardPrefixOverHttpTests(ServerCase):
    """/api/plugins/switchboard/* -> 404 in every configuration (and 403 without a credential)."""

    def check(self, app):
        self.serve(app)
        for path in RESERVED:
            with self.subTest(path=path, credential="none"):
                status, payload, _ = self.call(path)
                self.assertEqual((status, payload), FORBIDDEN)
        cookie, proof = self.session()
        session = {"Origin": self.base, "Cookie": cookie, "X-Folio-Session": proof, "X-Workspace-Token": self.server.csrf_token}
        for credential, headers in (("owner", self.owner()), ("session", session)):
            for method in ("GET", "POST", "PATCH", "DELETE"):
                for path in RESERVED:
                    with self.subTest(path=path, method=method, credential=credential):
                        status, payload, _ = self.call(path, method, None if method == "GET" else {}, headers)
                        self.assertEqual((status, payload), NOT_FOUND)

    def test_default_app(self):
        self.plugins()
        self.check(App(self.store))

    def test_app_built_for_the_server(self):
        self.plugins()
        self.check(build_app(self.store))

    def test_app_with_another_plugin_mounted(self):
        module = self.plugins()
        host = module.PluginHost()
        plugin = FakePlugin()
        host.mount(plugin)
        self.check(App(self.store, plugins=host))
        self.assertEqual(plugin.calls, [])

    def test_app_whose_plugin_tried_to_take_the_reserved_name(self):
        module = self.plugins()
        host = module.PluginHost()
        plugin = FakePlugin(name="switchboard")
        with self.assertRaises(module.PluginError):
            host.mount(plugin)
        self.check(App(self.store, plugins=host))
        self.assertEqual(plugin.calls, [])


if __name__ == "__main__":
    unittest.main()
