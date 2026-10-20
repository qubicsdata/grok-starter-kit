"""The minimal plugin host (WP-7, D-10).

Plugins are discovered through the ``folio.plugins`` entry-point group and enabled only by name in the
local config file (``$XDG_CONFIG_HOME/folio/config.json``, else ``~/.config/folio/config.json``)::

    {"plugins": {"<name>": {<settings for that plugin>}}}

Nothing is imported for a plugin that is not named there, and every refusal (a malformed config, an
unknown or reserved name, a route outside the plugin's own prefix, a factory that fails) raises
``PluginError`` before anything is mounted. A mounted plugin answers only ``/api/plugins/<name>/...``,
behind the unchanged ``/api`` authentication of the server. The name of the integration frozen in WP-7
(``folio.core.FROZEN``) is reserved: never mounted, never imported, its prefix is 404 in every
configuration.
"""

import json
import logging
import os
import re
from pathlib import Path

from ..core import FROZEN, AppError

GROUP = "folio.plugins"
PREFIX = "/api/plugins/"
RESERVED = frozenset({FROZEN})
NAME = re.compile(r"[a-z][a-z0-9_]{0,31}")
METHODS = frozenset({"GET", "POST", "PATCH", "DELETE"})
LOG = logging.getLogger("folio.plugins")


class PluginError(ValueError):
    """A plugin or its configuration was refused; nothing was mounted or imported for it."""


class Plugin:
    """Optional base class: every hook has a no-op default."""

    name = ""

    def __init__(self, settings=None):
        self.settings = settings

    def routes(self):
        """[(method, pattern, handler)]: pattern is a full-path regex starting with /api/plugins/<name>/."""
        return []

    def decision_provider(self):
        return None

    def on_task_change(self, fid):
        pass

    def close(self):
        pass


def default_config_path(environ=None):
    """$XDG_CONFIG_HOME/folio/config.json; a relative or empty XDG_CONFIG_HOME is ignored (XDG spec)."""
    environ = os.environ if environ is None else environ
    config = environ.get("XDG_CONFIG_HOME") or ""
    if not os.path.isabs(config):
        home = environ.get("HOME") or os.path.expanduser("~")
        config = os.path.join(home, ".config")
    return Path(config) / "folio" / "config.json"


def read_config(path=None, environ=None):
    """The local config object; a missing file is {}. Anything but a readable JSON object is refused."""
    path = Path(path) if path is not None else default_config_path(environ)
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return {}
    except (OSError, UnicodeDecodeError) as error:
        raise PluginError("Cannot read the plugin config %s: %s" % (path, error)) from error
    try:
        value = json.loads(text)
    except ValueError as error:
        raise PluginError("The plugin config %s is not valid JSON: %s" % (path, error)) from error
    if not isinstance(value, dict):
        raise PluginError("The plugin config %s must be a JSON object." % path)
    return value


def check_name(name):
    """A plugin name is the URL segment: [a-z][a-z0-9_]{0,31}, never a reserved name."""
    if not isinstance(name, str) or not NAME.fullmatch(name):
        raise PluginError("Invalid plugin name %r: use a-z, 0-9 and _, starting with a letter, at most 32 characters." % (name,))
    if name in RESERVED:
        raise PluginError("The plugin name %r is reserved." % name)
    return name


def enabled_plugins(config):
    """{name: settings} from config["plugins"]; only a JSON object of valid names to settings objects is accepted."""
    plugins = config.get("plugins") if isinstance(config, dict) else None
    if plugins is None:
        return {}
    if not isinstance(plugins, dict):
        raise PluginError('"plugins" must be a JSON object mapping each plugin name to its settings object.')
    enabled = {}
    for name, settings in plugins.items():
        check_name(name)
        if not isinstance(settings, dict):
            raise PluginError("The settings for plugin %r must be a JSON object." % name)
        enabled[name] = settings
    return enabled


def _entry_points():
    """Every folio.plugins entry point (metadata only, nothing imported); Python 3.9 compatible."""
    import importlib.metadata
    points = importlib.metadata.entry_points()
    if hasattr(points, "select"):
        return list(points.select(group=GROUP))
    return list(points.get(GROUP, ()))


def discover():
    """{name: entry point} for every installed folio.plugins entry point; loads nothing."""
    found = {}
    for point in _entry_points():
        found.setdefault(point.name, point)
    return found


class PluginHost:
    def __init__(self):
        self.plugins = {}
        self._routes = {}

    def mount(self, plugin):
        """Validate the plugin's name and every route, then mount it; a PluginError changes nothing."""
        name = check_name(getattr(plugin, "name", None))
        if name in self.plugins:
            raise PluginError("A plugin named %r is already mounted." % name)
        compiled = self._compile_routes(name, plugin)
        self.plugins[name] = plugin
        self._routes[name] = compiled

    @staticmethod
    def _compile_routes(name, plugin):
        prefix = PREFIX + name + "/"
        routes = plugin.routes()
        if not isinstance(routes, (list, tuple)):
            raise PluginError("Plugin %r: routes() must return a list of (method, pattern, handler)." % name)
        compiled = []
        for item in routes:
            if not isinstance(item, (list, tuple)) or len(item) != 3:
                raise PluginError("Plugin %r: each route must be (method, pattern, handler)." % name)
            method, pattern, handler = item
            if method not in METHODS:
                raise PluginError("Plugin %r: route method %r is not one of GET, POST, PATCH, DELETE." % (name, method))
            if not isinstance(pattern, str) or not pattern.startswith(prefix):
                raise PluginError("Plugin %r: route %r must be a path pattern starting with %r." % (name, pattern, prefix))
            if not callable(handler):
                raise PluginError("Plugin %r: the handler for %r is not callable." % (name, pattern))
            try:
                regex = re.compile(pattern)
            except re.error as error:
                raise PluginError("Plugin %r: route %r is not a valid pattern: %s" % (name, pattern, error)) from error
            compiled.append((method, regex, handler))
        return compiled

    def route(self, app, method, path, data, actor):
        """Dispatch a path under a mounted plugin's own prefix; anything else is 404."""
        if path.startswith(PREFIX):
            name = path[len(PREFIX):].split("/", 1)[0]
            prefix = PREFIX + name + "/"
            if name in self.plugins and path.startswith(prefix):
                for route_method, regex, handler in self._routes[name]:
                    match = regex.fullmatch(path)
                    if match and route_method == method:
                        return handler(app, match, data, actor)
        raise AppError("Not found.", 404)

    def decision_provider(self):
        """The first plugin's provider that is not None, in mount order."""
        for name, plugin in self.plugins.items():
            provider = self._call(name, plugin, "decision_provider")
            if provider is not None:
                return provider
        return None

    def on_task_change(self, fid):
        for name, plugin in self.plugins.items():
            self._call(name, plugin, "on_task_change", fid)

    def close(self):
        for name, plugin in self.plugins.items():
            self._call(name, plugin, "close")

    @staticmethod
    def _call(name, plugin, hook, *args):
        """One plugin's failure is logged and never stops the others."""
        try:
            return getattr(plugin, hook)(*args)
        except Exception:
            LOG.exception("Plugin %r failed in %s()", name, hook)
            return None

    @classmethod
    def load(cls, enabled, entry_points=None):
        """Load ONLY the enabled names from the entry points (default: every installed one); fail closed."""
        if not isinstance(enabled, dict):
            raise PluginError("The enabled plugins must be a mapping of name to settings.")
        host = cls()
        if not enabled:
            return host
        points = {}
        for point in (_entry_points() if entry_points is None else entry_points):
            points.setdefault(point.name, []).append(point)
        try:
            for name, settings in enabled.items():
                check_name(name)
                candidates = points.get(name, [])
                if not candidates:
                    raise PluginError("Plugin %r is enabled in the config but no %s entry point provides it." % (name, GROUP))
                if len(candidates) > 1:
                    raise PluginError("Plugin %r is provided by more than one installed distribution." % name)
                try:
                    plugin = candidates[0].load()(settings)
                except PluginError:
                    raise
                except Exception as error:
                    raise PluginError("Plugin %r failed to load: %s: %s" % (name, type(error).__name__, error)) from error
                if getattr(plugin, "name", None) != name:
                    raise PluginError("Plugin %r reports the name %r; it must match its entry point." % (name, getattr(plugin, "name", None)))
                host.mount(plugin)
        except PluginError:
            host.close()
            raise
        return host


def load_from_config(path=None, environ=None, entry_points=None):
    """read_config -> enabled_plugins -> PluginHost.load; no config file means an empty host."""
    return PluginHost.load(enabled_plugins(read_config(path, environ)), entry_points)
