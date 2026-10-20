"""One route table shared by the HTTP server and the CLI's direct transport.

ROUTE_TABLE lists every (method, pattern) the app serves: the core routes plus the one plugin mount.
A request that matches no entry is 404, over HTTP (also with a credential) and in-process alike.
"""

import re

from . import __version__
from .approvals import Approvals
from .brief import project_brief, read_source
from .core import AppError
from .notes import change_section, list_sections
from .plugins import (PREFIX as PLUGIN_PREFIX, RESERVED as RESERVED_PLUGINS, PluginError, PluginHost,
                      enabled_plugins, read_config)

ID = r"([a-f0-9]{16})"
DECISION_ID = r"([a-z]{2,8}_[a-f0-9]{16})"
SECTION = r"([a-f0-9]{16}|notes)"
# The About texts are empty unless the local config has an "about" object (see product_info).
ABOUT_KEYS = ("attribution", "website", "help_url")
ABOUT_LIMIT = 200
ABOUT_ADDRESS = re.compile(r"https?://[^\s\"'<>`\\]+")


def product_info(config=None):
    """The `product` object of /api/state: fixed facts plus the optional About texts of the local config.

    `{"about": {"attribution": str, "website": str, "help_url": str}}`; every key is optional and an
    absent one is empty (the UI then shows nothing for it). A wrong shape, an unknown key, a value
    that is not one printable line of at most ABOUT_LIMIT characters, or an address that is not
    http(s) is refused with PluginError, so folio-server fails closed as for a bad plugin config.
    """
    about = (config or {}).get("about")
    if about is None:
        about = {}
    if not isinstance(about, dict):
        raise PluginError('"about" must be a JSON object with optional attribution, website and help_url texts.')
    unknown = sorted(set(about) - set(ABOUT_KEYS))
    if unknown:
        raise PluginError("Unknown about setting(s) %s; allowed: %s." % (", ".join(map(repr, unknown)), ", ".join(ABOUT_KEYS)))
    texts = {}
    for key in ABOUT_KEYS:
        value = about.get(key, "")
        if not isinstance(value, str) or len(value) > ABOUT_LIMIT or not value.isprintable():
            raise PluginError("The about setting %r must be one line of printable text, at most %d characters." % (key, ABOUT_LIMIT))
        if key != "attribution" and value and not ABOUT_ADDRESS.fullmatch(value):
            raise PluginError("The about setting %r must be an http:// or https:// address." % key)
        texts[key] = value
    return {"name": "Folio", "version": __version__, "license": "Apache-2.0",
            "license_url": "/LICENSE.txt", "notice_url": "/NOTICE.txt", **texts}


class App:
    def __init__(self, store, approvals=None, plugins=None, product=None):
        self.store = store
        # The About texts for /api/state; build_app() takes them from the local config.
        self.product = product if product is not None else product_info()
        # WP-7: plugins are mounted only through build_app() (local config); the default is an empty host.
        self.plugins = plugins if plugins is not None else PluginHost()
        # The approvals inbox takes the first plugin-provided DecisionProvider (none -> the empty state,
        # resolve answers NO_APPROVALS_SOURCE).
        self.approvals = approvals if approvals is not None else Approvals(provider=self.plugins.decision_provider())

    def state(self):
        return self.store.state()

    def close(self):
        closer = getattr(self.approvals, "close", None)
        if closer:
            closer()
        self.plugins.close()


def build_app(store):
    # The only place that reads the local plugin config: App(store) elsewhere never imports a plugin.
    # The config is read once; its "about" object is checked before any plugin is imported.
    config = read_config()
    product = product_info(config)
    return App(store, plugins=PluginHost.load(enabled_plugins(config)), product=product)


def after_change(app, task):
    app.plugins.on_task_change(task["id"])
    return task


def plugin_route(app, method, match, data, actor):
    """/api/plugins/...: the reserved prefix is 404 before the host is consulted; the host confines the rest."""
    path = match.string
    for name in RESERVED_PLUGINS:
        reserved = PLUGIN_PREFIX + name
        if path == reserved or path.startswith(reserved + "/"):
            raise AppError("Not found.", 404)
    return app.plugins.route(app, method, path, data, actor)


def edit_task(app, method, match, data, actor):
    task = app.store.update_task(match[1], match[2], data, method == "DELETE", actor)
    return task if method == "DELETE" else after_change(app, task)


def edit_section(app, method, match, data, actor):
    return change_section(app.store, match[1], data, match[2] if method != "POST" else None, method == "DELETE", actor)


# (method, pattern, handler): handler(app, method, match, data, actor). One entry per method and path shape.
ROUTES = (
    ("GET", "/api/state", lambda app, _, m, data, actor: app.state()),
    ("GET", "/api/approvals", lambda app, _, m, data, actor: app.approvals.status()),
    ("GET", f"/api/projects/{ID}/brief", lambda app, _, m, data, actor: project_brief(app.store, m[1])),
    ("GET", f"/api/projects/{ID}/notes/sections", lambda app, _, m, data, actor: list_sections(app.store, m[1])),
    ("POST", "/api/clients", lambda app, _, m, data, actor: app.store.create_client(data)),
    ("POST", "/api/projects", lambda app, _, m, data, actor: app.store.create_project(data, actor)),
    ("POST", f"/api/projects/{ID}/brief",
     lambda app, _, m, data, actor: project_brief(app.store, m[1], data.get("query", ""), data.get("max_chars", 12000))),
    ("POST", f"/api/projects/{ID}/source",
     lambda app, _, m, data, actor: read_source(app.store, m[1], data.get("source_id"), data.get("offset", 0),
                                                data.get("max_chars", 12000), data.get("hash"))),
    ("POST", f"/api/projects/{ID}/notes/sections", edit_section),
    ("PATCH", f"/api/projects/{ID}/notes/sections/{SECTION}", edit_section),
    ("DELETE", f"/api/projects/{ID}/notes/sections/{SECTION}", edit_section),
    ("POST", f"/api/projects/{ID}/relocate", lambda app, _, m, data, actor: app.store.relocate_project(m[1], data, actor)),
    ("PATCH", f"/api/clients/{ID}", lambda app, _, m, data, actor: app.store.update_client(m[1], data)),
    ("PATCH", f"/api/projects/{ID}", lambda app, _, m, data, actor: app.store.update_project(m[1], data, actor)),
    ("POST", f"/api/projects/{ID}/workstreams", lambda app, _, m, data, actor: app.store.create_workstream(m[1], data, actor)),
    ("POST", f"/api/projects/{ID}/tasks", lambda app, _, m, data, actor: after_change(app, app.store.create_task(m[1], data, actor))),
    ("PATCH", f"/api/projects/{ID}/tasks/{ID}", edit_task),
    ("DELETE", f"/api/projects/{ID}/tasks/{ID}", edit_task),
    ("POST", f"/api/projects/{ID}/notes/append", lambda app, _, m, data, actor: app.store.append_notes(m[1], data, actor)),
    ("POST", f"/api/approvals/{DECISION_ID}/resolve", lambda app, _, m, data, actor: app.approvals.resolve(m[1], data, actor)),
    # The plugin mount: one method-agnostic entry; the host confines each plugin to its own prefix.
    ("*", re.escape(PLUGIN_PREFIX) + ".*", plugin_route),
)
ROUTE_TABLE = tuple((method, pattern) for method, pattern, _handler in ROUTES)
_DISPATCH = tuple((method, re.compile(pattern), handler) for method, pattern, handler in ROUTES)


def route(app, method, path, data, actor):
    for entry_method, pattern, handler in _DISPATCH:
        if entry_method != method and entry_method != "*":
            continue
        match = pattern.fullmatch(path)
        if match:
            return handler(app, method, match, data, actor)
    raise AppError("Not found.", 404)
