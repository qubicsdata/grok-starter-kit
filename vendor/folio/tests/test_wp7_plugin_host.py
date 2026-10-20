"""WP-7 red tests: the minimal plugin host (folio/plugins) and its wiring into the App.

Acceptance: a fake plugin mounts a route and a fake decision provider. Security: a plugin cannot
mount (or be reached) outside /api/plugins/<its name>/, and the name "switchboard" is reserved so
/api/plugins/switchboard/* is 404 in every configuration. The host is exercised through the shared
route table (folio.api.route), the same entry the HTTP server and the CLI's direct transport use.
"""

import json
import logging
import re
import threading
import time
import unittest
from unittest import mock
from urllib.request import Request, urlopen

from folio.api import App, route
from folio.core import AppError

from wp5_support import FID, FakeProvider, RecordingNotifier, ScriptedDialog, decision
from wp7_support import PREFIX, USER, FakePlugin, ServerCase, seam

RESERVED_PATHS = ("/api/plugins/switchboard", "/api/plugins/switchboard/", "/api/plugins/switchboard/ping",
                  "/api/plugins/switchboard/outbox/0123456789abcdef/retry", "/api/plugins/switchboard/../fake/ping")


class HostCase(ServerCase):
    def host(self, *plugins):
        module = self.plugins()
        host = module.PluginHost()
        for plugin in plugins:
            host.mount(plugin)
        return host

    def app(self, *plugins):
        return App(self.store, plugins=self.host(*plugins))

    def get(self, app, path, actor=USER):
        return route(app, "GET", path, None, actor)

    def assert_404(self, app, method, path, data=None):
        with self.assertRaises(AppError) as caught:
            route(app, method, path, data, USER)
        self.assertEqual((caught.exception.status, str(caught.exception)), (404, "Not found."), path)


class FakePluginMountsARouteTests(HostCase):
    def test_a_mounted_route_is_dispatched_with_the_match_data_and_actor(self):
        plugin = FakePlugin(routes=[])
        plugin._routes = [("GET", PREFIX + r"fake/items/([a-f0-9]{16})", plugin.handle), ("POST", PREFIX + "fake/items", plugin.handle)]
        app = self.app(plugin)
        result = self.get(app, "/api/plugins/fake/items/" + FID)
        self.assertEqual(result["groups"], [FID])
        self.assertEqual(plugin.calls[-1], {"path": "/api/plugins/fake/items/" + FID, "data": None, "actor": USER})
        created = route(app, "POST", "/api/plugins/fake/items", {"title": "x"}, {"origin": "cli", "via": "cli:codex"})
        self.assertEqual(created["method_data"], {"title": "x"})
        self.assertEqual(plugin.calls[-1]["actor"], {"origin": "cli", "via": "cli:codex"})

    def test_the_host_lists_the_mounted_plugin_by_name(self):
        plugin = FakePlugin()
        host = self.host(plugin)
        self.assertEqual(list(host.plugins), ["fake"])
        self.assertIs(host.plugins["fake"], plugin)

    def test_default_app_has_an_empty_host_and_no_plugin_routes(self):
        module = self.plugins()
        app = App(self.store)
        self.assertIsInstance(app.plugins, module.PluginHost)
        self.assertEqual(app.plugins.plugins, {})
        self.assert_404(app, "GET", "/api/plugins/fake/ping")

    def test_method_and_path_must_both_match(self):
        plugin = FakePlugin()  # GET /api/plugins/fake/ping only
        app = self.app(plugin)
        self.assertEqual(self.get(app, "/api/plugins/fake/ping")["pong"], True)
        self.assert_404(app, "POST", "/api/plugins/fake/ping", {})
        self.assert_404(app, "GET", "/api/plugins/fake/ping/")
        self.assert_404(app, "GET", "/api/plugins/fake/pings")
        self.assert_404(app, "GET", "/api/plugins/fake")
        self.assert_404(app, "GET", "/api/plugins/fake/")
        self.assert_404(app, "GET", "/api/plugins/")
        self.assert_404(app, "GET", "/api/plugins")
        self.assertEqual(len(plugin.calls), 1)

    def test_two_plugins_each_answer_only_their_own_prefix(self):
        alpha = FakePlugin("alpha")
        beta = FakePlugin("beta")
        app = self.app(alpha, beta)
        self.assertEqual(self.get(app, "/api/plugins/alpha/ping")["pong"], True)
        self.assertEqual(self.get(app, "/api/plugins/beta/ping")["pong"], True)
        self.assertEqual((len(alpha.calls), len(beta.calls)), (1, 1))
        self.assertEqual(alpha.calls[0]["path"], "/api/plugins/alpha/ping")
        self.assertEqual(beta.calls[0]["path"], "/api/plugins/beta/ping")

    def test_a_plugin_app_error_reaches_the_caller_unchanged(self):
        def refuse(app, match, data, actor):
            raise AppError("Model is offline.", 503, "PLUGIN_UNAVAILABLE")
        app = self.app(FakePlugin(routes=[("GET", PREFIX + "fake/ping", refuse)]))
        with self.assertRaises(AppError) as caught:
            self.get(app, "/api/plugins/fake/ping")
        self.assertEqual((caught.exception.status, caught.exception.code), (503, "PLUGIN_UNAVAILABLE"))


class PrefixConfinementTests(HostCase):
    """Security: a plugin cannot mount outside /api/plugins/<its name>/."""

    OUTSIDE = {
        "core route": "/api/state",
        "core approvals": "/api/approvals",
        "another plugin": PREFIX + "other/ping",
        "the bare prefix": PREFIX + "fake",
        "prefix without slash": PREFIX + "fakeping",
        "sibling by prefix": PREFIX + "fake_two/ping",
        "relative": "ping",
        "static asset": "/app.js",
        "session bootstrap": "/api/session",
        "shutdown": "/api/shutdown",
        "optional prefix": r"(?:/api/plugins/fake/)?ping",
        "anything": r".*",
        "case variant": "/API/plugins/fake/ping",
        "leading whitespace": " " + PREFIX + "fake/ping",
    }
    # Regexes that start under the prefix but can match elsewhere: the host may refuse them at mount
    # time or confine them at dispatch; either way nothing outside the prefix ever reaches the handler.
    SNEAKY = {
        "alternation": r"/api/plugins/fake/ping|/api/state",
        "alternation to another plugin": r"/api/plugins/fake/ping|/api/plugins/other/ping",
        "dot-dot": r"/api/plugins/fake/\.\./\.\./state",
        "wildcard tail": r"/api/plugins/fake/.*",
    }

    def test_a_regex_under_the_prefix_never_matches_outside_it(self):
        module = self.plugins()
        for name, pattern in self.SNEAKY.items():
            with self.subTest(route=name):
                host = module.PluginHost()
                plugin = FakePlugin(routes=[("GET", pattern, FakePlugin().handle)])
                try:
                    host.mount(plugin)
                except module.PluginError:
                    self.assertEqual(host.plugins, {})
                app = App(self.store, plugins=host)
                self.assertIn("projects", self.get(app, "/api/state"))
                self.assert_404(app, "GET", "/api/plugins/other/ping")
                self.assertEqual(plugin.calls, [], "a plugin handler saw a request outside its prefix")

    def test_a_route_outside_the_prefix_refuses_the_whole_plugin(self):
        module = self.plugins()
        for name, pattern in self.OUTSIDE.items():
            with self.subTest(route=name):
                host = module.PluginHost()
                plugin = FakePlugin(routes=[("GET", PREFIX + "fake/ping", FakePlugin().handle), ("GET", pattern, FakePlugin().handle)])
                with self.assertRaises(module.PluginError):
                    host.mount(plugin)
                self.assertEqual(host.plugins, {}, "a refused plugin was (partly) mounted")
                app = App(self.store, plugins=host)
                self.assert_404(app, "GET", "/api/plugins/fake/ping")

    def test_a_core_route_is_never_shadowed_even_if_a_plugin_slips_a_regex_past_mount(self):
        """Defence in depth: dispatch consults a plugin only for paths under its own prefix."""
        module = self.plugins()
        host = module.PluginHost()
        plugin = FakePlugin()
        host.mount(plugin)
        # Rewrite the mounted routes after mount, as a buggy or hostile plugin could if the host kept
        # a live reference instead of validating what it dispatches.
        plugin._routes = [("GET", r"/api/state|/api/plugins/fake/ping|/api/plugins/other/ping|.*", plugin.handle)]
        app = App(self.store, plugins=host)
        self.assertIn("projects", self.get(app, "/api/state"))
        self.assert_404(app, "GET", "/api/plugins/other/ping")
        self.assert_404(app, "GET", "/api/approvals/x")
        self.assertEqual(plugin.calls, [], "a plugin handler saw a request outside its prefix")

    def test_plugin_names_are_validated_before_anything_is_mounted(self):
        module = self.plugins()
        for name in ("", "Fake", "fake plugin", "fake/ping", "fake.py", "..", "../fake", "9fake", "fake-two", "a" * 33,
                     "fäke", "switchboard", "SWITCHBOARD", None, 7):
            with self.subTest(name=repr(name)):
                host = module.PluginHost()
                with self.assertRaises(module.PluginError):
                    host.mount(FakePlugin(name=name, routes=[]))
                self.assertEqual(host.plugins, {})

    def test_a_duplicate_name_is_refused_and_the_first_plugin_keeps_its_routes(self):
        module = self.plugins()
        first, second = FakePlugin(), FakePlugin()
        host = self.host(first)
        with self.assertRaises(module.PluginError):
            host.mount(second)
        self.assertIs(host.plugins["fake"], first)
        app = App(self.store, plugins=host)
        self.get(app, "/api/plugins/fake/ping")
        self.assertEqual((len(first.calls), len(second.calls)), (1, 0))

    def test_malformed_route_tuples_are_refused(self):
        module = self.plugins()
        good = PREFIX + "fake/ping"
        for name, routes in {"not a list": "GET " + good, "two-tuple": [("GET", good)], "lowercase method": [("get", good, FakePlugin().handle)],
                             "unknown method": [("TRACE", good, FakePlugin().handle)], "non-callable handler": [("GET", good, "ping")],
                             "bytes pattern": [("GET", good.encode(), FakePlugin().handle)],
                             "bad regex": [("GET", good + "(", FakePlugin().handle)]}.items():
            with self.subTest(route=name):
                host = module.PluginHost()
                with self.assertRaises(module.PluginError):
                    host.mount(FakePlugin(routes=routes))
                self.assertEqual(host.plugins, {})


class ReservedSwitchboardPrefixTests(HostCase):
    """Security: /api/plugins/switchboard/* -> 404 in every configuration."""

    def test_404_with_no_plugins(self):
        app = self.app()
        for method in ("GET", "POST", "PATCH", "DELETE"):
            for path in RESERVED_PATHS:
                with self.subTest(method=method, path=path):
                    self.assert_404(app, method, path, None if method == "GET" else {})

    def test_404_with_another_plugin_mounted(self):
        plugin = FakePlugin()
        app = self.app(plugin)
        for path in RESERVED_PATHS:
            with self.subTest(path=path):
                self.assert_404(app, "GET", path)
        self.assertEqual(plugin.calls, [])

    def test_a_plugin_named_switchboard_is_refused_and_its_routes_stay_404(self):
        module = self.plugins()
        host = module.PluginHost()
        plugin = FakePlugin(name="switchboard")
        with self.assertRaises(module.PluginError):
            host.mount(plugin)
        self.assertEqual(host.plugins, {})
        self.assertIn("switchboard", module.RESERVED)
        app = App(self.store, plugins=host)
        self.assert_404(app, "GET", "/api/plugins/switchboard/ping")
        self.assertEqual(plugin.calls, [])

    def test_a_plugin_cannot_claim_the_reserved_prefix_through_its_routes(self):
        module = self.plugins()
        host = module.PluginHost()
        plugin = FakePlugin(routes=[("GET", PREFIX + "switchboard/ping", FakePlugin().handle)])
        with self.assertRaises(module.PluginError):
            host.mount(plugin)
        self.assertEqual(host.plugins, {})

    def test_the_route_table_refuses_the_reserved_prefix_before_consulting_the_host(self):
        """Defence in depth: even a host that (buggily) holds a plugin under the reserved name is never asked."""
        module = self.plugins()
        host = module.PluginHost()
        plugin = FakePlugin(name="switchboard")
        host.plugins["switchboard"] = plugin  # bypass mount(), as a broken host implementation might
        host._routes["switchboard"] = [("GET", re.compile(PREFIX + "switchboard/ping"), plugin.handle)]
        app = App(self.store, plugins=host)
        self.assertEqual(host.route(app, "GET", "/api/plugins/switchboard/ping", None, USER)["pong"], True, "the test setup did not reach the host")
        plugin.calls.clear()
        for path in RESERVED_PATHS:
            with self.subTest(path=path):
                self.assert_404(app, "GET", path)
        self.assertEqual(plugin.calls, [])

    def test_the_legacy_switchboard_routes_are_gone_from_the_route_table(self):
        """The freeze removes the Switchboard routes, badges and sync thread: 404 even when authenticated."""
        self.plugins()
        app = App(self.store)
        for method, path in (("GET", "/api/decisions"), ("GET", "/api/decisions/dec_0123456789abcdef"),
                             ("POST", "/api/decisions/dec_0123456789abcdef/resolve"), ("POST", "/api/sync"),
                             ("POST", "/api/projects/%s/switchboard" % FID), ("PATCH", "/api/projects/%s/switchboard" % FID),
                             ("DELETE", "/api/projects/%s/switchboard" % FID),
                             ("POST", "/api/projects/%s/tasks/%s/dispatch" % (FID, FID)),
                             ("POST", "/api/projects/%s/tasks/%s/requeue" % (FID, FID)),
                             ("POST", "/api/projects/%s/proposals/sb_%s/accept" % (FID, FID)),
                             ("POST", "/api/projects/%s/switchboard/outbox/%s/retry" % (FID, FID))):
            with self.subTest(method=method, path=path):
                self.assert_404(app, method, path, None if method == "GET" else {})
        state = app.state()
        self.assertNotIn("switchboard_summary", str(state))


class DecisionProviderTests(HostCase):
    def inbox(self, app, *outcomes):
        app.approvals.dialog = ScriptedDialog(*outcomes)
        app.approvals.notifier = RecordingNotifier()
        return app.approvals

    def test_a_fake_plugin_provider_lights_up_the_approvals_inbox(self):
        provider = FakeProvider([decision("a1", fid=FID)])
        plugin = FakePlugin(provider=provider)
        app = self.app(plugin)
        self.assertIs(app.plugins.decision_provider(), provider)
        self.assertIs(app.approvals.provider, provider)
        status = self.get(app, "/api/approvals")
        self.assertEqual((status["configured"], [item["id"] for item in status["decisions"]]), (True, ["dec_00000000000000a1"]))

    def test_the_plugin_provider_resolves_through_the_approvals_route_and_dialog(self):
        provider = FakeProvider([decision("a1", fid=FID)])
        app = self.app(FakePlugin(provider=provider))
        self.inbox(app, {"choice": "approve", "text": ""})
        result = route(app, "POST", "/api/approvals/dec_00000000000000a1/resolve", {"requested": "approve"}, USER)
        self.assertEqual(result["result"], "approved")
        self.assertEqual([call["choice"] for call in provider.calls], ["approve"])

    def test_no_provider_keeps_the_empty_state(self):
        app = self.app(FakePlugin())  # decision_provider() -> None
        self.assertIsNone(app.plugins.decision_provider())
        status = self.get(app, "/api/approvals")
        self.assertEqual((status["configured"], status["message"]), (False, "No approvals source configured"))

    def test_the_first_provider_wins_and_the_choice_is_deterministic(self):
        first, second = FakeProvider(), FakeProvider()
        app = self.app(FakePlugin("alpha"), FakePlugin("beta", provider=first), FakePlugin("gamma", provider=second))
        self.assertIs(app.plugins.decision_provider(), first)

    def test_an_explicit_approvals_object_is_not_overridden_by_a_plugin_provider(self):
        module = seam(self, "approvals")
        explicit = module.Approvals(dialog=ScriptedDialog())
        app = App(self.store, approvals=explicit, plugins=self.host(FakePlugin(provider=FakeProvider())))
        self.assertIs(app.approvals, explicit)
        self.assertIsNone(app.approvals.provider)


class TaskChangeHookTests(HostCase):
    def project(self):
        client = self.store.create_client({"name": "Example client"})
        return self.store.create_project({"client_id": client["id"], "name": "Example rollout"})

    def test_create_and_update_notify_every_plugin_with_the_task_id(self):
        alpha, beta = FakePlugin("alpha"), FakePlugin("beta")
        app = self.app(alpha, beta)
        project = self.project()
        task = route(app, "POST", "/api/projects/%s/tasks" % project["id"],
                     {"title": "Design review", "revision": self.store.project(project["id"])["revision"]}, USER)
        self.assertEqual((alpha.task_changes, beta.task_changes), ([task["id"]], [task["id"]]))
        revision = self.store.project(project["id"])["revision"]
        route(app, "PATCH", "/api/projects/%s/tasks/%s" % (project["id"], task["id"]), {"title": "Design review 2", "revision": revision}, USER)
        self.assertEqual(alpha.task_changes, [task["id"], task["id"]])

    def test_a_failing_plugin_is_logged_and_does_not_stop_the_others_or_the_change(self):
        class Broken(FakePlugin):
            def on_task_change(self, fid):
                raise RuntimeError("plugin exploded")
        broken, other = Broken("broken"), FakePlugin("other")
        app = self.app(broken, other)
        project = self.project()
        with self.assertLogs("folio.plugins", level=logging.ERROR) as logs:
            task = route(app, "POST", "/api/projects/%s/tasks" % project["id"],
                         {"title": "Design review", "revision": self.store.project(project["id"])["revision"]}, USER)
        self.assertEqual(other.task_changes, [task["id"]])
        self.assertTrue(any("broken" in line for line in logs.output), logs.output)
        self.assertEqual([item["id"] for item in self.store.project(project["id"])["tasks"]], [task["id"]])

    def test_the_host_hook_fans_out_directly(self):
        alpha, beta = FakePlugin("alpha"), FakePlugin("beta")
        host = self.host(alpha, beta)
        host.on_task_change(FID)
        self.assertEqual((alpha.task_changes, beta.task_changes), ([FID], [FID]))


class CloseTests(HostCase):
    def test_app_close_closes_every_plugin_once(self):
        alpha, beta = FakePlugin("alpha"), FakePlugin("beta")
        app = self.app(alpha, beta)
        app.close()
        self.assertEqual((alpha.closed, beta.closed), (1, 1))

    def test_a_failing_close_is_logged_and_the_others_still_close(self):
        class Broken(FakePlugin):
            def close(self):
                raise RuntimeError("close exploded")
        other = FakePlugin("other")
        host = self.host(Broken("broken"), other)
        with self.assertLogs("folio.plugins", level=logging.ERROR):
            host.close()
        self.assertEqual(other.closed, 1)

    def test_the_server_closes_plugins_on_shutdown(self):
        """folio-server's main() closes the app (and so every plugin) when /api/shutdown stops it."""
        from folio import web
        plugin = FakePlugin()
        app = self.app(plugin)
        servers = []
        original = web.make_server

        def capture(store, port, app_):
            servers.append(original(store, port, app_))
            return servers[-1]
        with mock.patch.object(web, "build_app", lambda store, **kwargs: app), mock.patch.object(web, "make_server", capture), \
                mock.patch.object(web.signal, "signal"), mock.patch("builtins.print"):
            thread = threading.Thread(target=web.main, args=(["--port", "0", "--data-dir", str(self.dir / "served")],), daemon=True)
            thread.start()
            deadline = time.monotonic() + 10
            while not servers and time.monotonic() < deadline:
                time.sleep(0.02)
            self.assertTrue(servers, "the server did not start")
            server = servers[0]
            request = Request("http://127.0.0.1:%d/api/shutdown" % server.server_port, method="POST", data=b"{}",
                              headers={"Content-Type": "application/json", "X-Workspace-Token": server.token})
            with urlopen(request, timeout=10) as response:
                self.assertEqual(json.loads(response.read()), {"stopping": True})
            thread.join(10)
        self.assertFalse(thread.is_alive(), "the server did not stop")
        self.assertEqual(plugin.closed, 1)


if __name__ == "__main__":
    unittest.main()
