"""WP-13 security regression suite, part 2: the new HTTP surfaces.

- The launch credential (`#folio-launch=<token>`) is single-use: the first exchange opens a session, any
  second exchange of the same credential is 403 with no cookie, and the first session keeps working. The
  consumed credential is replaced by a fresh one in `.server.json`, so a later `folio ui` on the running
  server still opens an authenticated tab (with the live cookie it keeps the existing session).
- The actor is not taken from `X-Folio-Origin`: a browser session is the `user` actor whatever
  `X-Folio-Origin` or `X-Folio-Via` it sends, in the activity log and in plugin handlers alike.
- Plugin routes sit behind the /api auth and CSRF pipeline; `/api/plugins/switchboard/*` is 404 for every
  credential and 403 without one.
- With plugins off (no local config) nothing is mounted and no outbound socket is opened, in-process
  and behind an authenticated server.
"""

import io
import os
import threading
import unittest
from unittest import mock

from folio.api import App, build_app, route
from folio.core import AppError
from folio.local_auth import browser_url, read_server_info

from wp6_support import CORE_ROUTES
from wp7_support import FakePlugin, FORBIDDEN, NOT_FOUND, PREFIX, RELOAD, USER
from wp8_support import ConnectRecorder
from wp13_support import SHA256, SecurityCase, mode_of

PING = PREFIX + "fake/ping"
ITEMS = PREFIX + "fake/items"
RESERVED = ("/api/plugins/switchboard", "/api/plugins/switchboard/", "/api/plugins/switchboard/ping",
            "/api/plugins/switchboard/outbox/0123456789abcdef/retry", "/api/plugins/switchboard/../fake/ping")
SPOOFS = {"origin cli": {"X-Folio-Origin": "cli"},
          "origin cli with via": {"X-Folio-Origin": "cli", "X-Folio-Via": "cli:codex"},
          "via alone": {"X-Folio-Via": "cli:codex"},
          "origin upper case": {"X-Folio-Origin": "CLI", "X-Folio-Via": "cli:codex"},
          "origin agent": {"X-Folio-Origin": "agent", "X-Folio-Via": "agent:x"}}


class LaunchCredentialTests(SecurityCase):
    def setUp(self):
        super().setUp()
        self.serve_default()

    def test_a_second_exchange_of_the_launch_credential_is_403_with_no_cookie(self):
        credential = self.server.browser_token
        status, payload, response = self.exchange(credential)
        self.assertEqual(status, 200)
        self.assertIn("Set-Cookie", response)
        for attempt in range(2):
            with self.subTest(replay=attempt + 1):
                status, payload, response = self.exchange(credential)
                self.assertEqual((status, payload), FORBIDDEN)
                self.assertIsNone(response.get("Set-Cookie"))
        self.assertEqual(len(self.server.sessions), 1, "a replayed credential opened another session")

    def test_a_second_exchange_with_the_live_cookie_is_refused_and_the_first_session_survives(self):
        credential = self.server.browser_token
        status, payload, response = self.exchange(credential)
        self.assertEqual(status, 200)
        cookie, proof = response["Set-Cookie"].split(";", 1)[0], payload["session_proof"]
        status, payload, response = self.exchange(credential, {"Cookie": cookie})
        self.assertEqual((status, payload), FORBIDDEN)
        self.assertIsNone(response.get("Set-Cookie"))
        self.assertEqual(self.call("/api/state", headers={"Cookie": cookie, "X-Folio-Session": proof})[0], 200)

    def test_a_consumed_credential_is_replaced_by_a_fresh_one_in_discovery(self):
        """`folio ui` on a running server reads `.server.json`: it must advertise a live credential, never the consumed one."""
        consumed = self.server.browser_token
        self.assertEqual(self.exchange(consumed)[0], 200)
        fresh = self.server.browser_token
        self.assertNotEqual(fresh, consumed, "the launch credential was not rotated on consumption")
        self.assertRegex(fresh, SHA256)
        info = read_server_info(self.store.root)
        self.assertEqual(info["browser_token"], fresh)
        self.assertEqual(info["owner_token"], self.server.token)
        self.assertEqual((info["port"], info["pid"]), (self.server.server_port, os.getpid()))
        if os.name != "nt":
            self.assertEqual(mode_of(self.store.root / ".server.json"), 0o600)
        self.assertEqual(browser_url(self.store.root, self.base), "%s/#folio-launch=%s" % (self.base, fresh))
        self.assertEqual(self.exchange(consumed)[0], 403)
        status, payload, response = self.exchange(fresh)
        self.assertEqual(status, 200)
        self.assertNotEqual(self.server.browser_token, fresh)
        self.assertEqual(self.exchange(fresh)[0], 403, "the fresh credential was not single-use")
        self.assertEqual(len(self.server.sessions), 2)

    def test_a_second_tab_with_the_fresh_credential_and_the_live_cookie_keeps_its_session(self):
        """What a second `folio ui` does in the same browser: a new credential, the existing cookie, the same proof."""
        first = self.server.browser_token
        status, payload, response = self.exchange(first)
        self.assertEqual(status, 200)
        cookie, proof = response["Set-Cookie"].split(";", 1)[0], payload["session_proof"]
        self.assertNotEqual(self.server.browser_token, first, "the second tab would have to replay the consumed credential")
        status, second, response = self.exchange(self.server.browser_token, {"Cookie": cookie})
        self.assertEqual(status, 200, second)
        self.assertEqual(response["Set-Cookie"].split(";", 1)[0], cookie)
        self.assertEqual(second["session_proof"], proof)
        self.assertEqual(len(self.server.sessions), 1)
        self.assertEqual(self.call("/api/state", headers={"Cookie": cookie, "X-Folio-Session": proof})[0], 200)

    def test_refused_exchanges_do_not_consume_the_credential(self):
        for wrong in ("0" * 64, self.server.token, self.server.csrf_token, ""):
            self.assertEqual(self.exchange(wrong)[0], 403)
        self.assertEqual(self.exchange(self.server.browser_token)[0], 200)

    def test_a_restart_issues_a_fresh_credential_that_is_single_use_again(self):
        self.assertEqual(self.exchange(self.server.browser_token)[0], 200)
        old = self.server.browser_token  # the unconsumed replacement: a restart must retire it too
        self.restart()
        self.assertNotEqual(self.server.browser_token, old)
        self.assertEqual(self.exchange(old)[0], 403)
        credential = self.server.browser_token
        self.assertEqual(self.exchange(credential)[0], 200)
        status, payload, response = self.exchange(credential)
        self.assertEqual((status, payload), FORBIDDEN)
        self.assertIsNone(response.get("Set-Cookie"))

    def test_folio_ui_on_the_running_server_opens_a_live_credential_after_an_exchange(self):
        """The CLI reuse path (`folio ui` with a server already running) reads discovery, not the consumed fragment."""
        from folio import cli
        consumed = self.server.browser_token
        self.assertEqual(self.exchange(consumed)[0], 200)
        output = io.StringIO()
        with mock.patch("webbrowser.open") as open_browser:
            code = cli.main(["--data-dir", str(self.store.root), "ui"], env={}, stdout=output)
        self.assertEqual(code, 0, output.getvalue())
        open_browser.assert_called_once()
        url = open_browser.call_args[0][0]
        self.assertTrue(url.startswith(self.base + "/#folio-launch="), url)
        credential = url.rsplit("=", 1)[1]
        self.assertNotEqual(credential, consumed, "folio ui handed out the consumed credential")
        self.assertNotIn(credential, output.getvalue())
        self.assertEqual(self.exchange(credential)[0], 200)
        self.assertEqual(self.exchange(credential)[0], 403)

    def test_concurrent_exchanges_of_one_credential_open_exactly_one_session(self):
        """Single-use holds under the threading server: the check and the rotation are one atomic step."""
        credential = self.server.browser_token
        results = []
        barrier = threading.Barrier(8)

        def attempt():
            barrier.wait()
            results.append(self.exchange(credential)[0])
        threads = [threading.Thread(target=attempt) for _ in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(sorted(results), [200] + [403] * 7, results)
        self.assertEqual(len(self.server.sessions), 1)

    def test_a_failed_discovery_rewrite_grants_nothing_and_keeps_the_credential_live(self):
        """If the fresh credential cannot be written, nothing was handed out: the exchange is a storage error and can be retried."""
        credential = self.server.browser_token
        with mock.patch("folio.web.write_server_info", side_effect=OSError("disk full")):
            status, payload, response = self.exchange(credential)
        self.assertEqual(status, 500, payload)
        self.assertIsNone(response.get("Set-Cookie"))
        self.assertEqual(self.server.sessions, {})
        self.assertEqual(self.server.browser_token, credential)
        self.assertEqual(read_server_info(self.store.root)["browser_token"], credential)
        self.assertEqual(self.exchange(credential)[0], 200)

    def test_the_exchange_itself_needs_a_local_host_and_origin(self):
        port = self.server.server_port
        body = b'{"credential": "%s"}' % self.server.browser_token.encode()
        status, _, response = self.raw("POST", "/api/session", {"Content-Type": "application/json", "Origin": "http://attacker.example"}, body)
        self.assertEqual(status, 403)
        self.assertIsNone(response.get("Set-Cookie"))
        status, _, response = self.raw("POST", "/api/session", {"Content-Type": "application/json"}, body, host="attacker.example:%d" % port)
        self.assertEqual(status, 403)
        self.assertIsNone(response.get("Set-Cookie"))
        self.assertEqual(self.exchange(self.server.browser_token)[0], 200, "a refused exchange consumed the credential")


class ActorTests(SecurityCase):
    """`X-Folio-Origin` and `X-Folio-Via` cannot turn a browser session into the CLI actor."""

    def setUp(self):
        super().setUp()
        self.plugin = FakePlugin()
        host = self.plugins().PluginHost()
        host.mount(self.plugin)
        self.serve(App(self.store, plugins=host))

    def test_a_browser_session_is_the_user_actor_in_the_activity_log_whatever_it_sends(self):
        writer = self.writer()
        for name, spoof in SPOOFS.items():
            with self.subTest(spoof=name):
                project = self.project({**writer, **spoof})
                entry = self.activity(project["id"])
                self.assertEqual(entry["message"], "Project created")
                self.assertEqual(entry["origin"], "user", entry)
                self.assertNotIn("via", entry)

    def test_a_browser_session_is_the_user_actor_in_plugin_handlers_whatever_it_sends(self):
        reader = self.reader()
        for name, spoof in SPOOFS.items():
            with self.subTest(spoof=name):
                self.plugin.calls.clear()
                status, _, _ = self.call(PING, headers={**reader, **spoof})
                self.assertEqual(status, 200)
                self.assertEqual([call["actor"] for call in self.plugin.calls], [USER])

    def test_a_browser_session_edit_is_logged_as_the_user_whatever_it_sends(self):
        writer = self.writer()
        project = self.project()
        for name, spoof in SPOOFS.items():
            with self.subTest(spoof=name):
                revision = self.store.project(project["id"])["revision"]
                status, payload, _ = self.call("/api/projects/%s/tasks" % project["id"], "POST",
                                               {"title": "Task " + name, "revision": revision}, {**writer, **spoof})
                self.assertEqual(status, 200, payload)
                entry = self.activity(project["id"])
                self.assertEqual((entry["origin"], entry.get("via")), ("user", None), entry)

    def test_the_owner_token_actor_is_a_valid_shape_and_an_invalid_via_label_is_dropped(self):
        """The CLI holds the owner token; its actor is derived server-side, never a free-form label."""
        for name, extra in (("no headers", {}), ("cli", {"X-Folio-Origin": "cli", "X-Folio-Via": "cli:codex"}),
                            ("bad via", {"X-Folio-Origin": "cli", "X-Folio-Via": "Bad Label!"}),
                            ("long via", {"X-Folio-Origin": "cli", "X-Folio-Via": "a" * 61}),
                            ("unknown origin", {"X-Folio-Origin": "agent"})):
            with self.subTest(headers=name):
                project = self.project(self.owner(**extra))
                entry = self.activity(project["id"])
                self.assertIn(entry["origin"], ("user", "cli"))
                if name in ("bad via", "long via", "no headers", "unknown origin"):
                    self.assertNotIn("via", entry, entry)
                self.plugin.calls.clear()
                self.assertEqual(self.call(PING, headers=self.owner(**extra))[0], 200)
                actor = self.plugin.calls[0]["actor"]
                self.assertEqual(sorted(actor), ["origin", "via"])
                self.assertIn(actor["origin"], ("user", "cli"))


class PluginRouteAuthTests(SecurityCase):
    def setUp(self):
        super().setUp()
        module = self.plugins()
        self.module = module
        self.plugin = FakePlugin(routes=[])
        self.plugin._routes = [("GET", PING, self.plugin.handle), ("POST", ITEMS, self.plugin.handle)]
        host = module.PluginHost()
        host.mount(self.plugin)
        self.serve(App(self.store, plugins=host))

    def assert_untouched(self):
        self.assertEqual(self.plugin.calls, [], "a plugin handler ran for a refused request")

    def test_plugin_routes_refuse_every_credential_shape_but_a_real_one(self):
        reader = self.reader()
        attempts = {"nothing": {}, "wrong owner token": {"X-Workspace-Token": "0" * 64},
                    "launch token as owner token": {"X-Workspace-Token": self.server.browser_token},
                    "csrf token as owner token": {"X-Workspace-Token": self.server.csrf_token},
                    "proof without cookie": {"X-Folio-Session": reader["X-Folio-Session"]},
                    "cookie without proof": {"Cookie": reader["Cookie"]},
                    "cookie with wrong proof": {"Cookie": reader["Cookie"], "X-Folio-Session": "0" * 64}}
        for method, path, body in (("GET", PING, None), ("POST", ITEMS, {"title": "x"})):
            for name, headers in attempts.items():
                with self.subTest(method=method, attempt=name):
                    status, payload, _ = self.call(path, method, body, {"Origin": self.base, **headers})
                    self.assertEqual((status, payload), FORBIDDEN)
        self.assert_untouched()

    def test_browser_posts_to_plugin_routes_need_the_csrf_token(self):
        reader = self.reader()
        for name, extra in (("no csrf", {}), ("wrong csrf", {"X-Workspace-Token": "0" * 64})):
            with self.subTest(attempt=name):
                status, payload, _ = self.call(ITEMS, "POST", {"title": "x"}, {**reader, **extra})
                self.assertEqual((status, payload), RELOAD)
        self.assert_untouched()
        status, _, _ = self.call(ITEMS, "POST", {"title": "x"}, {**reader, "X-Workspace-Token": self.server.csrf_token})
        self.assertEqual(status, 200)
        self.assertEqual(len(self.plugin.calls), 1)

    def test_plugin_routes_refuse_a_wrong_host_and_a_foreign_origin(self):
        status, _, _ = self.raw("GET", PING, self.owner(), host="attacker.example:%d" % self.server.server_port)
        self.assertEqual(status, 403)
        status, _, _ = self.call(ITEMS, "POST", {"title": "x"}, self.owner(Origin="https://attacker.example"))
        self.assertEqual(status, 403)
        self.assert_untouched()

    def test_the_reserved_switchboard_prefix_is_404_authenticated_and_403_otherwise(self):
        for path in RESERVED:
            for method in ("GET", "POST", "PATCH", "DELETE"):
                body = None if method == "GET" else {}
                with self.subTest(path=path, method=method, credential="owner"):
                    status, payload, _ = self.call(path, method, body, self.owner())
                    self.assertEqual((status, payload), NOT_FOUND)
                with self.subTest(path=path, method=method, credential="none"):
                    status, payload, _ = self.call(path, method, body, {})
                    self.assertEqual((status, payload), FORBIDDEN)
        with self.subTest(credential="browser"):
            status, payload, _ = self.call("/api/plugins/switchboard/ping", headers=self.reader())
            self.assertEqual((status, payload), NOT_FOUND)
        self.assert_untouched()

    def test_nothing_can_mount_under_the_reserved_name(self):
        host = self.module.PluginHost()
        with self.assertRaises(self.module.PluginError):
            host.mount(FakePlugin(name="switchboard"))
        with self.assertRaises(self.module.PluginError):
            host.mount(FakePlugin(name="other", routes=[("GET", "/api/plugins/switchboard/ping", lambda *a: {})]))
        with self.assertRaises(self.module.PluginError):
            host.mount(FakePlugin(name="other", routes=[("GET", "/api/plugins/(other|switchboard)/ping", lambda *a: {})]))
        self.assertEqual(host.plugins, {})
        with self.assertRaises(self.module.PluginError):
            self.module.enabled_plugins({"plugins": {"switchboard": {}}})

    def test_a_plugin_cannot_answer_outside_its_own_prefix(self):
        host = self.module.PluginHost()
        for pattern in ("/api/state", "/api/plugins/fake2/ping", "/api/plugins/fak.*/ping", "/api/plugins/fake", "/api/plugins/fakes/ping",
                        "/api/plugins/(fake|other)/ping", "/static"):
            with self.subTest(pattern=pattern):
                with self.assertRaises(self.module.PluginError):
                    host.mount(FakePlugin(routes=[("GET", pattern, lambda *a: {})]))
        self.assertEqual(host.plugins, {})
        for path in ("/api/plugins/fake", "/api/plugins/fake/", "/api/plugins/", "/api/plugins", "/api/plugins/fake/ping/"):
            with self.subTest(path=path):
                status, payload, _ = self.call(path, headers=self.owner())
                self.assertEqual((status, payload), NOT_FOUND)
        self.assert_untouched()


class NoSocketsWithPluginsOffTests(SecurityCase):
    """No local config: build_app() mounts nothing, and no code path opens an outbound connection."""

    def drive_in_process(self, app):
        for method, path in CORE_ROUTES:
            body = None if method == "GET" else {"name": "x", "title": "x", "client_id": "0" * 16, "query": "", "text": "x"}
            try:
                route(app, method, path, body, USER)
            except (AppError, ValueError, KeyError, TypeError, OSError):
                pass  # unknown ids and refused bodies are expected (the handler maps these to 4xx/500); a socket is an AssertionError
        for method, path in (("GET", "/api/plugins/ollama/suggest"), ("POST", "/api/plugins/ollama/accept"), ("GET", "/api/plugins/fake/ping")):
            with self.assertRaises(AppError) as caught:
                route(app, method, path, None if method == "GET" else {}, USER)
            self.assertEqual(caught.exception.status, 404)

    def test_build_app_without_config_mounts_nothing_and_opens_no_socket(self):
        with ConnectRecorder(forbid=True, resolve={}) as recorder:
            app = build_app(self.store)
            self.addCleanup(app.close)
            self.assertEqual(app.plugins.plugins, {})
            self.assertFalse(app.approvals.configured)
            self.drive_in_process(app)
            app.plugins.on_task_change("0" * 16)
        self.assertEqual(recorder.connects, [])
        self.assertEqual(recorder.lookups, [])

    def test_an_empty_plugins_object_in_the_config_is_still_off(self):
        self.write_config({"plugins": {}})
        with ConnectRecorder(forbid=True, resolve={}) as recorder:
            app = build_app(self.store)
            self.addCleanup(app.close)
            self.assertEqual(app.plugins.plugins, {})
            self.drive_in_process(app)
        self.assertEqual(recorder.connects, [])

    def test_an_authenticated_server_with_plugins_off_connects_nowhere_but_answers_its_own_client(self):
        self.serve(build_app(self.store))
        with ConnectRecorder(forbid=False) as recorder:
            requests = 0
            project = self.project()
            requests += 2
            for method, path in CORE_ROUTES:
                real = path.replace("0123456789abcdef", project["id"], 1)
                body = None if method == "GET" else {"name": "x", "title": "x", "query": "", "text": "x"}
                self.call(real, method, body, self.owner())
                requests += 1
            for path in ("/api/plugins/ollama/suggest", "/api/plugins/switchboard/ping"):
                status, payload, _ = self.call(path, headers=self.owner())
                self.assertEqual((status, payload), NOT_FOUND)
                requests += 1
        self.assertEqual(recorder.hosts(), ["127.0.0.1"], "a connection left the loopback")
        created = [entry for entry in recorder.connects if entry[0] == "create_connection"]
        self.assertEqual(len(created), requests, "more connections than this test's own requests")
        self.assertEqual(set(recorder.lookups) - {"127.0.0.1"}, set(), "a name lookup happened")


if __name__ == "__main__":
    unittest.main()
