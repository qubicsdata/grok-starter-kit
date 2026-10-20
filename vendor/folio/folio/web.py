"""HTTP server for the Folio web UI and local API."""

import argparse
import json
import os
import secrets
import shlex
import signal
import stat
import sys
import threading
from http.cookies import CookieError, SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from socketserver import TCPServer
from urllib.parse import urlparse

from .local_auth import read_server_info
from . import __version__

from .api import App, build_app, product_info, route
from .core import (DEFAULT_WORKSPACE, STORAGE_MESSAGE, VIA_LABEL, AppError, Store, now,
                   resolve_workspace, write_json)
from .plugins import PluginError

STATIC = Path(__file__).with_name("static")
TOKEN_BYTES = 32


def matches_credential(value, expected):
    return isinstance(value, str) and secrets.compare_digest(value.encode("utf-8"), expected.encode("ascii"))


class Handler(BaseHTTPRequestHandler):
    server_version = "TaskManager/1.0"

    def log_request(self, code="-", size="-"):
        # Never log query values, fragments, headers or request bodies.
        self.log_message('"%s" %s %s', f"{self.command} {urlparse(self.path).path} {self.request_version}", str(code), size)

    def send(self, status, content, content_type="application/json", headers=None):
        payload = json.dumps(content, ensure_ascii=False).encode() if content_type == "application/json" else content
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
        for key, value in (headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(payload)

    def validate_host(self):
        if self.headers.get("Host") not in self.server.allowed_hosts:
            raise AppError("Invalid local host.", 403)
        origin = self.headers.get("Origin")
        if origin and origin not in {f"http://{host}" for host in self.server.allowed_hosts}:
            raise AppError("Cross-origin requests are not allowed.", 403)

    def authenticate(self):
        if matches_credential(self.headers.get("X-Workspace-Token", ""), self.server.token):
            return "owner"
        session = self.session_cookie()
        if session:
            with self.server.sessions_lock:
                proof = self.server.sessions.get(session)
            if proof and matches_credential(self.headers.get("X-Folio-Session", ""), proof):
                return "browser"
        raise AppError("Open this workspace with folio ui to authenticate.", 403, "FORBIDDEN")

    def session_cookie(self):
        cookie = SimpleCookie()
        try:
            cookie.load(self.headers.get("Cookie", ""))
        except CookieError:
            return None
        session = cookie.get(self.server.cookie_name)
        return session.value if session else None

    def body(self):
        if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
            raise AppError("Expected application/json.", 415)
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > 1_000_000:
                raise AppError("Request body is missing or too large.", 413)
            data = json.loads(self.rfile.read(length))
        except (ValueError, UnicodeDecodeError):
            raise AppError("Invalid JSON request.")
        if not isinstance(data, dict):
            raise AppError("Expected a JSON object.")
        return data

    def handle_request(self):
        try:
            self.validate_host()
            path = urlparse(self.path).path
            if path == "/api/session" and self.command == "POST":
                data = self.body()
                credential = data.get("credential")
                session_token = self.session_cookie()
                with self.server.sessions_lock:
                    if not matches_credential(credential, self.server.browser_token):
                        raise AppError("Open this workspace with folio ui to authenticate.", 403, "FORBIDDEN")
                    # The launch credential is single-use: a fresh one replaces it in discovery before the
                    # exchange completes, so a later `folio ui` on this server still opens a live tab.
                    replacement = secrets.token_hex(32)
                    write_server_info(self.server.store.root, self.server.server_port, self.server.token, replacement)
                    self.server.browser_token = replacement
                    # Only the authorized bootstrap may recover an existing proof.
                    # Preserve it for other tabs sharing this browser's cookie.
                    proof = self.server.sessions.get(session_token)
                    if proof is None:
                        session_token, proof = secrets.token_hex(32), secrets.token_hex(32)
                        if len(self.server.sessions) >= 64:
                            self.server.sessions.pop(next(iter(self.server.sessions)))
                        self.server.sessions[session_token] = proof
                self.send(200, {"authenticated": True, "session_proof": proof}, headers={"Set-Cookie":
                    f"{self.server.cookie_name}={session_token}; HttpOnly; SameSite=Strict; Path=/api"})
                return
            auth = None
            if path.startswith("/api/"):
                auth = self.authenticate()
                if self.command != "GET" and auth == "browser" and not matches_credential(
                        self.headers.get("X-Workspace-Token", ""), self.server.csrf_token):
                    raise AppError("Reload the page to reconnect to this workspace.", 403)
            if self.command == "GET":
                if path.startswith("/api/"):
                    result = route(self.server.app, "GET", path, None, self.actor(auth))
                    if path == "/api/state":
                        # The About texts come from the local config, read once in build_app (api.product_info).
                        result = {**result, "csrf_token": self.server.csrf_token,
                                  "product": getattr(self.server.app, "product", None) or product_info()}
                    self.send(200, result)
                    return
                assets = {"/": ("index.html", "text/html; charset=utf-8"), "/app.js": ("app.js", "text/javascript; charset=utf-8"),
                          "/styles.css": ("styles.css", "text/css; charset=utf-8"), "/favicon.svg": ("favicon.svg", "image/svg+xml"),
                          "/favicon-dark.svg": ("favicon-dark.svg", "image/svg+xml"),
                          "/manifest.webmanifest": ("manifest.webmanifest", "application/manifest+json"),
                          "/LICENSE.txt": ("LICENSE.txt", "text/plain; charset=utf-8"),
                          "/NOTICE.txt": ("NOTICE.txt", "text/plain; charset=utf-8"),
                          **{f"/{name}": (name, "image/png") for name in ("icon-32.png", "icon-192.png", "icon-512.png", "apple-touch-icon.png")}}
                if path in assets:
                    filename, content_type = assets[path]
                    self.send(200, (STATIC / filename).read_bytes(), content_type)
                    return
                raise AppError("Not found.", 404)
            data = self.body()
            if path == "/api/shutdown" and self.command == "POST":
                self.send(200, {"stopping": True})
                threading.Thread(target=self.server.shutdown, daemon=True).start()
                return
            self.send(200, route(self.server.app, self.command, path, data, self.actor(auth)))
        except AppError as error:
            payload = {"error": str(error)}
            if getattr(error, "code", None):
                payload["code"] = error.code
            self.send(error.status, payload)
        except (OSError, ValueError, KeyError, TypeError):
            self.log_error("Storage or data error")
            self.send(500, {"error": STORAGE_MESSAGE})

    def actor(self, auth):
        # Only the owner credential (the CLI) may name its origin; a browser session is always the user.
        if auth != "owner" or self.headers.get("X-Folio-Origin") != "cli":
            return {"origin": "user", "via": None}
        via = self.headers.get("X-Folio-Via", "")
        return {"origin": "cli", "via": via if VIA_LABEL.fullmatch(via) else None}

    do_GET = handle_request
    do_POST = handle_request
    do_PATCH = handle_request
    do_DELETE = handle_request


class LocalHTTPServer(ThreadingHTTPServer):
    def server_close(self):
        super().server_close()
        if hasattr(self, "store"):
            remove_server_info(self.store.root, getattr(self, "token", None))

    def server_bind(self):
        # HTTPServer resolves its name through DNS; a loopback-only server needs
        # no network lookup, which can stall startup on offline or slow resolvers.
        TCPServer.server_bind(self)
        self.server_name = "localhost"
        self.server_port = self.server_address[1]


def make_server(store, port, app=None):
    app = app or App(store)
    server = LocalHTTPServer(("127.0.0.1", port), Handler)
    server.app = app
    server.store = store
    server.token = secrets.token_hex(TOKEN_BYTES)
    server.browser_token = secrets.token_hex(TOKEN_BYTES)
    server.sessions = {}
    server.sessions_lock = threading.Lock()
    server.csrf_token = secrets.token_hex(TOKEN_BYTES)
    actual_port = server.server_address[1]
    server.allowed_hosts = {f"127.0.0.1:{actual_port}", f"localhost:{actual_port}"}
    server.cookie_name = f"folio_session_{actual_port}"
    try:
        root_info = store.root.stat()
        if os.name != "nt" and (root_info.st_uid != os.getuid() or stat.S_IMODE(root_info.st_mode) & 0o022):
            raise AppError("The workspace directory must be owned by this account and not writable by other accounts.", 403)
        write_server_info(store.root, actual_port, server.token, server.browser_token)
    except Exception:
        server.server_close()
        raise
    return server


def write_server_info(root, port, owner_token=None, browser_token=None):
    path = Path(root) / ".server.json"
    # Existing callers may refresh an already-advertised server, never its secrets.
    if owner_token is None:
        try:
            current = read_server_info(root)
            if current.get("pid") == os.getpid() and current.get("port") == port:
                return path
        except (OSError, ValueError):
            pass
    write_json(path, {"port": port, "pid": os.getpid(), "started_at": now(),
                      "owner_token": owner_token, "browser_token": browser_token})
    return path


def remove_server_info(root, owner_token=None):
    path = Path(root) / ".server.json"
    try:
        info = read_server_info(root)
        if info.get("pid") == os.getpid() and (owner_token is None or info.get("owner_token") == owner_token):
            path.unlink()
    except (OSError, ValueError, AttributeError):
        pass


def _raise_keyboard_interrupt(signum, frame):
    raise KeyboardInterrupt()


def main(argv=None):
    parser = argparse.ArgumentParser(description="A local, project-folder-backed workspace for planning and coordinating work.")
    parser.add_argument("--version", action="version", version=f"folio {__version__}")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--data-dir", default=None,
                        help=f"Workspace directory (default: $FOLIO_WORKSPACE, else {DEFAULT_WORKSPACE})")
    parser.add_argument("--open", action="store_true", help="Open the workspace in your default browser")
    # Accepted and ignored since the WP-7 freeze, so existing launchers keep working (README freeze note).
    for retired in ("--no-sync", "--no-notifications"):
        parser.add_argument(retired, action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    signal.signal(signal.SIGTERM, _raise_keyboard_interrupt)
    if hasattr(signal, "SIGBREAK"):
        signal.signal(signal.SIGBREAK, _raise_keyboard_interrupt)
    store = Store(resolve_workspace(args.data_dir))
    try:
        try:
            app = build_app(store)
        except PluginError as error:
            # A bad plugin config fails closed: no socket, no traceback, one line naming the problem.
            sys.stderr.write(f"folio-server: {error}\n")
            raise SystemExit(2)
        server = make_server(store, args.port, app)
        try:
            print(f"\n  Folio {__version__} · Your account workspace\n  http://127.0.0.1:{server.server_address[1]}\n  Data: {store.root}\n  Open securely: folio ui --data-dir {shlex.quote(str(store.root))}\n  Press Ctrl+C to stop.\n", flush=True)
            if args.open:
                import webbrowser
                from .local_auth import browser_url
                webbrowser.open(browser_url(store.root, f"http://127.0.0.1:{server.server_address[1]}"))
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            app.close()
            server.server_close()
            remove_server_info(store.root)
    finally:
        store.close()
