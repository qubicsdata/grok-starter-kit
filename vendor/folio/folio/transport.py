"""How the CLI reaches a workspace: the running server over HTTP, or the store directly."""

import json
import os
import time
from http.client import HTTPException
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .local_auth import owner_credential, read_server_info

from .api import App, route
from .paths import path_identity
from .core import STORAGE_MESSAGE, AppError, Store


class TransportError(Exception):
    def __init__(self, status, message, code=None):
        super().__init__(message)
        self.status = status
        self.message = message
        self.code = code


class HttpTransport:
    kind = "http"

    def __init__(self, base_url, actor, timeout=150, token=None):
        self.base_url = base_url
        self.actor = actor
        self.timeout = timeout
        self.token = token

    def _send(self, method, path, data, timeout):
        headers = {"X-Folio-Origin": actor_origin(self.actor)}
        if self.actor.get("via"):
            headers["X-Folio-Via"] = self.actor["via"]
        if self.token:
            headers["X-Workspace-Token"] = self.token
        body = None
        if method != "GET":
            headers["Content-Type"] = "application/json"
            body = json.dumps(data if data is not None else {}).encode()
        request = Request(self.base_url + path, method=method, data=body, headers=headers)
        try:
            with urlopen(request, timeout=timeout) as response:
                return json.loads(response.read() or b"null")
        except HTTPError as error:
            try:
                payload = json.loads(error.read())
            except (ValueError, OSError, HTTPException):
                payload = {}
            if not isinstance(payload, dict):
                payload = {}
            raise TransportError(error.code, payload.get("error", f"HTTP {error.code}"), payload.get("code"))
        except (URLError, OSError, HTTPException) as error:
            raise TransportError(503, f"The Folio server is not responding ({error}).", "STORAGE")
        except ValueError:
            raise TransportError(503, "The Folio server returned an invalid response.", "STORAGE")

    def request(self, method, path, data=None, timeout=None):
        return self._send(method, path, data, self.timeout if timeout is None else timeout)

    def close(self):
        pass


class DirectTransport:
    kind = "direct"

    def __init__(self, app, actor):
        self.app = app
        self.actor = actor

    def request(self, method, path, data=None, timeout=None):
        try:
            return route(self.app, method, path, data if data is not None else {}, self.actor)
        except AppError as error:
            raise TransportError(error.status, str(error), getattr(error, "code", None))
        except (OSError, ValueError, KeyError, TypeError):
            raise TransportError(500, STORAGE_MESSAGE, "STORAGE")

    def close(self):
        closer = getattr(self.app, "close", None)
        if closer:
            closer()
        self.app.store.close()


def actor_origin(actor):
    return "cli" if actor.get("origin") == "cli" else "user"


def pid_alive(pid):
    try:
        pid = int(pid)
        if pid <= 0:
            return False
        if os.name == "nt":
            import ctypes
            from ctypes import wintypes
            kernel = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
            kernel.OpenProcess.restype = wintypes.HANDLE
            kernel.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
            kernel.CloseHandle.argtypes = [wintypes.HANDLE]
            handle = kernel.OpenProcess(0x1000, False, pid)  # query only; never terminate
            if not handle:
                return False
            try:
                code = wintypes.DWORD()
                return bool(kernel.GetExitCodeProcess(handle, ctypes.byref(code))) and code.value == 259
            finally:
                kernel.CloseHandle(handle)
        os.kill(pid, 0)
        return True
    except (OSError, ValueError, TypeError):
        return False


def find_server(workspace, timeout=5):
    """Return the URL of a live Folio server for exactly this workspace, or None."""
    root = Path(workspace).expanduser().resolve()
    try:
        info = read_server_info(root)
    except (OSError, ValueError):
        return None
    if not isinstance(info, dict) or not pid_alive(info.get("pid")):
        return None
    port = info.get("port")
    if type(port) is not int or not 1 <= port <= 65535:
        return None
    url = f"http://127.0.0.1:{port}"
    try:
        token = owner_credential(root, url)
        state = HttpTransport(url, {"origin": "cli", "via": None}, token=token)._send("GET", "/api/state", None, timeout)
    except (TransportError, OSError, ValueError):
        return None
    if not isinstance(state, dict) or not isinstance(state.get("workspace"), str) or path_identity(state["workspace"]) != path_identity(root):
        return None
    return url


def connect(workspace, actor, app_factory=None, lock_wait=5.0):
    root = Path(workspace).expanduser().resolve()
    deadline = time.monotonic() + lock_wait
    while True:
        url = find_server(root)
        if url:
            try:
                return HttpTransport(url, actor, token=owner_credential(root, url))
            except (OSError, ValueError):
                raise TransportError(403, "Cannot read private Folio owner discovery.", "FORBIDDEN")
        try:
            store = Store(root)
        except AppError as error:
            if error.code != "WORKSPACE_LOCKED":
                raise TransportError(error.status, str(error), error.code) from error
            if time.monotonic() >= deadline:
                raise TransportError(503, "Another Folio process is using this workspace. Try again in a moment.", "STORAGE")
            time.sleep(0.1)
            continue
        except OSError as error:
            raise TransportError(500, f"Cannot open the workspace at {root}: {error}", "STORAGE")
        return DirectTransport((app_factory or App)(store), actor)
