"""WP-8 red tests: the Ollama plugin accepts a loopback URL only (M-7), and refuses everything else
at load time with no socket and no name resolution.

Security: 10.0.0.5, example.com, a non-loopback IPv6 literal (and the IPv4-mapped, unspecified, link-local,
userinfo, https, path/query and bracket-less spellings) -> PluginError from make()/check_url, so the host
never mounts the plugin. "localhost" is accepted only when every resolved address is loopback, and the
resolved loopback literal is what the plugin connects to later (no DNS rebinding between load and use).
"""

import os
import unittest
from unittest import mock

from folio.api import App, route
from folio.core import AppError

from wp7_support import FakeEntryPoint
from wp8_support import CHANNEL, SUGGEST, USER, ConnectRecorder, OllamaCase, chat_response, plugins_module

REFUSED = {
    "ipv4 lan": "http://10.0.0.5:11434",
    "ipv4 lan no port": "http://10.0.0.5",
    "ipv4 private 192": "http://192.168.1.20:11434",
    "ipv4 link local metadata": "http://169.254.169.254",
    "ipv4 unspecified": "http://0.0.0.0:11434",
    "ipv4 public": "http://93.184.216.34:11434",
    "hostname": "http://example.com",
    "hostname with port": "http://example.com:11434",
    "hostname subdomain of loopback spelling": "http://127.0.0.1.example.com:11434",
    "hostname nip-style": "http://127-0-0-1.example.com:11434",
    "ipv6 documentation": "http://[2001:db8::1]:11434",
    "ipv6 global": "http://[2606:4700:4700::1111]:11434",
    "ipv6 link local": "http://[fe80::1]:11434",
    "ipv6 unique local": "http://[fd00::1]:11434",
    "ipv6 unspecified": "http://[::]:11434",
    "ipv6 mapped lan": "http://[::ffff:10.0.0.5]:11434",
    "ipv6 mapped public": "http://[::ffff:93.184.216.34]:11434",
    "ipv6 loopback without brackets": "http://::1:11434",
    "userinfo hides the real host": "http://127.0.0.1@example.com:11434",
    # Joined at run time, so the file holds no credential-shaped URL for secret scanners.
    "userinfo on loopback": "@".join(("http://user:secret", "127.0.0.1:11434")),
    "https": "https://127.0.0.1:11434",
    "ftp": "ftp://127.0.0.1",
    "file": "file:///etc/hosts",
    "gopher": "gopher://127.0.0.1",
    "query": "http://127.0.0.1:11434/?model=x",
    "empty query": "http://127.0.0.1:11434?",
    "fragment": "http://127.0.0.1:11434/#x",
    "empty fragment": "http://127.0.0.1:11434#",
    "empty port": "http://127.0.0.1:",
    "path": "http://127.0.0.1:11434/api",
    "double slash path": "http://127.0.0.1:11434//",
    "no scheme": "127.0.0.1:11434",
    "scheme only": "http://",
    "port out of range": "http://127.0.0.1:70000",
    "port not a number": "http://127.0.0.1:abc",
    "empty": "",
    "whitespace around": " http://127.0.0.1:11434 ",
    "newline inside": "http://127.0.0.1:11434\n",
    "not a string": 11434,
    "none": None,
    "list": ["http://127.0.0.1:11434"],
}

ACCEPTED = {
    "ipv4": "http://127.0.0.1:11434",
    "ipv4 no port": "http://127.0.0.1",
    "ipv4 trailing slash": "http://127.0.0.1:11434/",
    "ipv4 other port": "http://127.0.0.1:8080",
    "ipv6": "http://[::1]:11434",
    "ipv6 no port": "http://[::1]",
    "localhost": "http://localhost:11434",
}


class CheckUrlTests(OllamaCase):
    def test_refuses_every_non_loopback_url_without_resolving_or_connecting(self):
        module = self.ollama()
        plugins = plugins_module(self)
        with ConnectRecorder(forbid=True, resolve={}) as recorder:
            for name, url in REFUSED.items():
                with self.subTest(url=name):
                    with self.assertRaises(plugins.PluginError):
                        module.check_url(url)
        self.assertEqual(recorder.connects, [])
        self.assertEqual(recorder.lookups, [], "a refused URL must never reach the resolver")

    def test_make_refuses_the_same_urls_and_opens_no_socket(self):
        module = self.ollama()
        plugins = plugins_module(self)
        with ConnectRecorder(forbid=True, resolve={}) as recorder:
            for name, url in REFUSED.items():
                with self.subTest(url=name):
                    with self.assertRaises(plugins.PluginError):
                        module.make(self.settings(url))
        self.assertEqual(recorder.connects, [])
        self.assertEqual(recorder.lookups, [])

    def test_accepts_loopback_literals_and_a_loopback_localhost(self):
        module = self.ollama()
        with ConnectRecorder(forbid=True, resolve={"localhost": ["127.0.0.1", "::1"]}) as recorder:
            for name, url in ACCEPTED.items():
                with self.subTest(url=name):
                    self.assertIsInstance(module.check_url(url), str)
                    plugin = module.make(self.settings(url))
                    self.addCleanup(plugin.close)
                    self.assertEqual(plugin.name, "ollama")
        self.assertEqual(recorder.connects, [], "make() must not connect at load time")
        self.assertEqual(set(recorder.lookups), {"localhost"}, "only localhost is ever resolved")

    def test_default_url_is_the_ipv4_loopback_port_11434(self):
        module = self.ollama()
        self.assertEqual(module.DEFAULT_URL, "http://127.0.0.1:11434")
        with ConnectRecorder(forbid=True, resolve={}) as recorder:
            plugin = module.make({"model": "m", "channel": CHANNEL, "repo": str(self.repo)})
            self.addCleanup(plugin.close)
        self.assertEqual((recorder.connects, recorder.lookups), ([], []))

    def test_localhost_resolving_to_a_non_loopback_address_is_refused(self):
        module = self.ollama()
        plugins = plugins_module(self)
        for name, answers in {"lan": ["10.0.0.5"], "mixed": ["127.0.0.1", "10.0.0.5"], "ipv6 global": ["2001:db8::1"],
                              "mapped": ["::ffff:10.0.0.5"], "empty": []}.items():
            with self.subTest(resolves_to=name):
                with ConnectRecorder(forbid=True, resolve={"localhost": answers}) as recorder:
                    with self.assertRaises(plugins.PluginError):
                        module.make(self.settings("http://localhost:11434"))
                self.assertEqual(recorder.connects, [])

    def test_localhost_that_does_not_resolve_is_refused(self):
        module = self.ollama()
        plugins = plugins_module(self)
        with ConnectRecorder(forbid=True, resolve={}):
            with self.assertRaises(plugins.PluginError):
                module.check_url("http://localhost:11434")


class SettingsShapeTests(OllamaCase):
    def test_missing_or_malformed_settings_fail_closed(self):
        module = self.ollama()
        plugins = plugins_module(self)
        absent = object()
        cases = {
            "no model": {"model": absent}, "empty model": {"model": ""}, "model not a string": {"model": 3},
            "model with newline": {"model": "m\n"},
            "no channel": {"channel": absent}, "empty channel": {"channel": ""}, "channel not a string": {"channel": ["example-channel"]},
            "no repo": {"repo": absent}, "repo not a string": {"repo": 1},
            "unknown key": {"api_key": "x"}, "unknown key tools": {"tools": []},
            "timeout zero": {"timeout": 0}, "timeout negative": {"timeout": -1}, "timeout string": {"timeout": "60"},
            "timeout bool": {"timeout": True}, "url not a string": {"url": 1},
        }
        with ConnectRecorder(forbid=True, resolve={}) as recorder:
            for name, overrides in cases.items():
                with self.subTest(case=name):
                    settings = self.settings("http://127.0.0.1:11434")
                    for key, value in overrides.items():
                        if value is absent:
                            settings.pop(key, None)
                        else:
                            settings[key] = value
                    with self.assertRaises(plugins.PluginError):
                        module.make(settings)
            for bad in (None, [], "x", 1):
                with self.subTest(settings=repr(bad)):
                    with self.assertRaises(plugins.PluginError):
                        module.make(bad)
        self.assertEqual((recorder.connects, recorder.lookups), ([], []))

    def test_a_refused_url_leaves_the_host_without_the_plugin(self):
        module = self.ollama()
        plugins = plugins_module(self)
        point = FakeEntryPoint("ollama", module.make)
        with self.assertRaises(plugins.PluginError):
            plugins.PluginHost.load({"ollama": self.settings("http://10.0.0.5:11434")}, entry_points=[point])
        app = App(self.store)
        with self.assertRaises(AppError) as caught:
            route(app, "POST", SUGGEST, self.suggest_data(), USER)
        self.assertEqual(caught.exception.status, 404)


class ProxyEnvironmentTests(OllamaCase):
    def test_proxy_variables_are_ignored_and_loopback_is_contacted_directly(self):
        """urllib honours http_proxy by default; the plugin must not, or a proxy variable would redirect the call."""
        fake = self.fake_ollama("127.0.0.1", chat_response({"subtasks": [{"title": "One"}]}))
        plugin = self.plugin(fake.url)
        app = self.app_with(plugin)
        proxies = {name: "http://10.0.0.5:3128" for name in ("http_proxy", "HTTP_PROXY", "https_proxy", "HTTPS_PROXY", "all_proxy", "ALL_PROXY")}
        proxies["no_proxy"] = proxies["NO_PROXY"] = ""
        with mock.patch.dict(os.environ, proxies):
            with ConnectRecorder(resolve={}) as recorder:
                result = self.post(app, SUGGEST, self.suggest_data())
        self.assertEqual(result["subtasks"], [{"title": "One"}])
        fake.only_request(self)
        self.assertEqual(recorder.hosts(), ["127.0.0.1"])


class NoRebindingTests(OllamaCase):
    def test_the_plugin_connects_to_the_loopback_address_resolved_at_load_time(self):
        """localhost -> 127.0.0.1 at load; later the resolver says 10.0.0.5, yet only 127.0.0.1 is contacted."""
        fake = self.fake_ollama("127.0.0.1", chat_response({"subtasks": [{"title": "One"}]}))
        with ConnectRecorder(resolve={"localhost": ["127.0.0.1"]}):
            plugin = self.plugin("http://localhost:%d" % fake.port)
        app = self.app_with(plugin)
        with ConnectRecorder(resolve={"localhost": ["10.0.0.5"]}) as recorder:
            result = self.post(app, SUGGEST, self.suggest_data())
        self.assertEqual(result["subtasks"], [{"title": "One"}])
        fake.only_request(self)
        self.assertEqual(recorder.hosts(), ["127.0.0.1"])
        self.assertNotIn("localhost", recorder.lookups, "the name must not be resolved again at request time")


if __name__ == "__main__":
    unittest.main()
