"""Shared helpers for the WP-7 red tests (minimal plugin host and the Switchboard freeze).

The WP-7 seam does not exist on the base; every test imports it through `seam()` so that a missing
module FAILS with a message naming the seam instead of erroring at import time. No stub module is
added by WP7-1. The contract the tests expect from WP7-2 (names are the wished-for API):

folio/plugins/__init__.py
  GROUP = "folio.plugins"                      the importlib.metadata entry-point group (D-10)
  PREFIX = "/api/plugins/"                     every plugin route lives under PREFIX + <name> + "/"
  RESERVED = frozenset({"switchboard"})        never mounted, never imported, its routes 404 always
  NAME = re.compile(r"[a-z][a-z0-9_]{0,31}")   plugin names (fullmatch); the name is also the URL segment
  PluginError(ValueError)                      every refusal at load/mount time; nothing is half-mounted
  Plugin                                       optional base class; every method has a no-op default:
      name = ""; __init__(self, settings=None)
      routes() -> [(method, pattern, handler)]
          method is "GET"/"POST"/"PATCH"/"DELETE"; pattern is a regex string for the FULL path
          (re.fullmatch), which must start with the plugin's own literal prefix
          "/api/plugins/<name>/"; handler(app, match, data, actor) -> a JSON-able value
          (data is None for GET). A route outside the prefix refuses the whole plugin (PluginError).
      decision_provider() -> approvals.DecisionProvider | None
      on_task_change(fid)                      fid: the Folio task id
      close()
  default_config_path(environ=None) -> Path
      $XDG_CONFIG_HOME/folio/config.json when XDG_CONFIG_HOME is an absolute path, else
      <HOME>/.config/folio/config.json (a relative XDG_CONFIG_HOME is ignored, XDG spec).
  read_config(path=None, environ=None) -> dict  (missing file -> {}; not a JSON object -> PluginError)
  enabled_plugins(config) -> {name: settings}
      config["plugins"] is a JSON object {name: settings-object}; a plugin is enabled iff its name is
      a key. Missing/null -> {}. Any other shape, a malformed name or a RESERVED name -> PluginError.
  discover() -> {name: entry point}            importlib.metadata.entry_points(group=GROUP); loads nothing
  PluginHost()
      .plugins -> {name: plugin}               config order
      .mount(plugin)                           validates name (NAME, not RESERVED, not a duplicate) and
                                               every route prefix; PluginError leaves .plugins unchanged
      .route(app, method, path, data, actor)   dispatches ONLY paths under a mounted plugin's own prefix;
                                               anything else (other prefixes, method mismatch) -> AppError 404
      .decision_provider() -> the first non-None provider, else None
      .on_task_change(fid)                     every plugin; one plugin's exception is logged
                                               (logger "folio.plugins") and does not stop the others
      .close()                                 every plugin once; same exception rule
      PluginHost.load(enabled, entry_points=None) -> PluginHost
          enabled: {name: settings}; entry_points: iterable of objects with .name and .load(), default
          discover(). ONLY enabled names are loaded (ep.load() -> factory; factory(settings) -> plugin,
          whose .name must equal the entry-point name). An enabled name with no entry point ->
          PluginError (fail closed). Nothing else is imported.
  load_from_config(path=None, environ=None, entry_points=None) -> PluginHost
      read_config -> enabled_plugins -> PluginHost.load. No config file -> an empty host, nothing imported.
folio/api.py
  App(store, ..., plugins=None): .plugins (default: an empty PluginHost()); the default Approvals gets
      provider=plugins.decision_provider(). route(): "/api/plugins/switchboard" and anything below it
      -> 404 before the host is consulted; other "/api/plugins/..." paths -> app.plugins.route(...).
      after_change -> app.plugins.on_task_change(task id). App.close() -> plugins.close().
  build_app(store, ...) wires load_from_config() (the server's only way to enable a plugin).
folio/web.py: the request pipeline is unchanged (validate_host -> authenticate -> CSRF -> route),
  so every plugin route is behind the /api auth.
"""

import importlib
import json
import os
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock
from urllib.error import HTTPError
from urllib.request import Request, urlopen

REPO_ROOT = Path(__file__).resolve().parents[1]
TESTS = REPO_ROOT / "tests"
FOLIO = REPO_ROOT / "folio"
PLUGINS_INIT = FOLIO / "plugins" / "__init__.py"
PREFIX = "/api/plugins/"
FORBIDDEN = (403, {"error": "Open this workspace with folio ui to authenticate.", "code": "FORBIDDEN"})
RELOAD = (403, {"error": "Reload the page to reconnect to this workspace."})
NOT_FOUND = (404, {"error": "Not found."})
USER = {"origin": "user", "via": None}


def seam(case, name="plugins"):
    """Import folio.<name> or fail the test with the missing-seam reason."""
    try:
        return importlib.import_module("folio." + name)
    except ImportError as error:
        case.fail("WP-7 seam folio/%s/__init__.py is missing: %s" % (name, error))


def ping(app, match, data, actor):
    return {"pong": True, "method_data": data, "groups": list(match.groups())}


class FakePlugin:
    """A plugin that records every host call; routes and the provider are configurable per test."""

    def __init__(self, name="fake", routes=None, provider=None, settings=None):
        self.name = name
        self.settings = settings
        self._routes = routes if routes is not None else [("GET", PREFIX + name + "/ping", self.handle)]
        self.provider = provider
        self.calls = []
        self.task_changes = []
        self.closed = 0

    def handle(self, app, match, data, actor):
        self.calls.append({"path": match.string, "data": data, "actor": actor})
        return ping(app, match, data, actor)

    def routes(self):
        return list(self._routes)

    def decision_provider(self):
        return self.provider

    def on_task_change(self, fid):
        self.task_changes.append(fid)

    def close(self):
        self.closed += 1


class FakeEntryPoint:
    """An importlib.metadata.EntryPoint stand-in; `loads` counts every load() so a test can prove none happened."""

    def __init__(self, name, factory, group="folio.plugins"):
        self.name, self.factory, self.group = name, factory, group
        self.loads = 0

    def load(self):
        self.loads += 1
        return self.factory


def plugin_factory(**kwargs):
    """An entry-point target: called with the plugin's settings object, returns the plugin."""
    def factory(settings=None):
        return FakePlugin(settings=settings, **kwargs)
    return factory


class IsolatedCase(unittest.TestCase):
    """A temp dir with private state, config and home; nothing outside it is ever read or written."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="folio-wp7-")
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)
        self.state = self.dir / "state"
        self.config_home = self.dir / "config"
        self.home = self.dir / "home"
        self.home.mkdir()
        self.environ = {"XDG_STATE_HOME": str(self.state), "XDG_CONFIG_HOME": str(self.config_home), "HOME": str(self.home)}
        patch = mock.patch.dict(os.environ, self.environ)
        patch.start()
        self.addCleanup(patch.stop)

    def plugins(self):
        return seam(self)

    def write_config(self, value, path=None):
        target = Path(path or self.config_home / "folio" / "config.json")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(value) if not isinstance(value, str) else value, encoding="utf-8")
        return target


class ServerCase(IsolatedCase):
    """IsolatedCase plus a JSON-store workspace and a loopback server on an ephemeral port."""

    def setUp(self):
        super().setUp()
        from folio.core import Store
        self.store = Store(self.dir / "workspace")
        self.addCleanup(self.store.close)

    def serve(self, app):
        from folio.web import make_server
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
        request = Request(self.base + path, method=method, data=data,
                          headers={"Content-Type": "application/json", **(headers or {})})
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


def install_fake_distribution(root, name="fake", module="folio_fake_plugin", marker=None, body=None):
    """Write an importable module plus a *.dist-info advertising it as a folio.plugins entry point.

    Importing the module writes `marker` (when given) so a child process can prove the import happened,
    independently of sys.modules. Returns the module name.
    """
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    lines = ["import pathlib", "MARKER = %r" % (str(marker) if marker else ""),
             "if MARKER:", "    pathlib.Path(MARKER).write_text('imported', encoding='utf-8')",
             "class Plugin:",
             "    name = %r" % name,
             "    def __init__(self, settings=None):",
             "        self.settings = settings",
             "    def routes(self):",
             "        return [('GET', '/api/plugins/%s/ping', self.ping)]" % name,
             "    def ping(self, app, match, data, actor):",
             "        return {'pong': %r, 'settings': self.settings}" % name,
             "    def decision_provider(self):",
             "        return None",
             "    def on_task_change(self, fid):",
             "        pass",
             "    def close(self):",
             "        pass",
             "def make(settings=None):",
             "    return Plugin(settings)"]
    (root / (module + ".py")).write_text((body if body is not None else "\n".join(lines)) + "\n", encoding="utf-8")
    info = root / ("%s-1.0.dist-info" % module)
    info.mkdir(exist_ok=True)
    (info / "METADATA").write_text("Metadata-Version: 2.1\nName: %s\nVersion: 1.0\n" % module.replace("_", "-"), encoding="utf-8")
    (info / "entry_points.txt").write_text("[folio.plugins]\n%s = %s:make\n" % (name, module), encoding="utf-8")
    return module


def python_child_argv(script, *extra_paths):
    """argv for an isolated child interpreter (-I: no cwd, PYTHONPATH or user site on sys.path)."""
    paths = [str(REPO_ROOT), str(TESTS)] + [str(path) for path in extra_paths]
    return [sys.executable, "-I", "-c", "import sys; sys.path[:0] = %r\n%s" % (paths, script)]
