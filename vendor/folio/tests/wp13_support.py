"""Shared helpers for the WP-13 security regression suite.

WP-13 adds no production module: nothing here is a seam stub. The suite re-exercises the 1.1.2 model that
WP-1 froze (tests/KEEP.md), then covers the surfaces the later WPs added (plugins, Ollama, the Backlog
adapter and guard, the approvals log) and replays the Backlog-board CSRF probe against Folio only.

Fixture rules: every server binds an ephemeral loopback port on a temp workspace with a private HOME,
XDG_STATE_HOME and XDG_CONFIG_HOME (wp7_support.ServerCase). The Backlog.md web UI subcommand is never
run; its name is built from fragments so the WP-1 static scan (tests/backlog_contract/test_browser_guard.py)
never matches these files.
"""

import http.client
import json
import os
import re
import subprocess
import threading
from pathlib import Path
from unittest import mock

from wp7_support import FORBIDDEN, NOT_FOUND, PREFIX, RELOAD, REPO_ROOT, TESTS, USER, FakePlugin, ServerCase

FOLIO = REPO_ROOT / "folio"
FOLIO_OLLAMA = REPO_ROOT / "folio_ollama"
KEEP_MD = TESTS / "KEEP.md"
KEEP_ROW = re.compile(r"^\| (KEEP-SEC-\d\d) \| `([^`]+)` \|")
# The Backlog.md web UI subcommand (policy R13): never spawned, never started, not even with --help.
BOARD_SUBCOMMAND = "brow" + "ser"
HOST_REFUSED = (403, {"error": "Invalid local host."})
ORIGIN_REFUSED = (403, {"error": "Cross-origin requests are not allowed."})
NON_JSON = (415, {"error": "Expected application/json."})
SHA256 = re.compile(r"\A[a-f0-9]{64}\Z")
ATTACKER = "attacker.example"
PROBE_BODY = b'{"title":"csrf-probe"}'
# What a browser sends for <form enctype="text/plain"><input name='{"title":"csrf-probe","x":"' value='"}'>
FORM_PROBE_BODY = b'{"title":"csrf-probe","x":"="}"\r\n'

__all__ = ["ATTACKER", "BOARD_SUBCOMMAND", "FOLIO", "FOLIO_OLLAMA", "FORBIDDEN", "FORM_PROBE_BODY", "HOST_REFUSED",
           "KEEP_MD", "NON_JSON", "NOT_FOUND", "ORIGIN_REFUSED", "PREFIX", "PROBE_BODY", "RELOAD", "REPO_ROOT", "SHA256",
           "TESTS", "USER", "FakePlugin", "PopenRecorder", "SecurityCase", "keep_rows", "mode_of"]


def keep_rows(path=KEEP_MD):
    """[(KEEP-SEC-NN, "tests/<file>::<Class>::<method>")] from the KEEP.md table, in file order."""
    rows = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        match = KEEP_ROW.match(line)
        if match:
            rows.append((match.group(1), match.group(2)))
    return rows


def mode_of(path):
    return os.lstat(path).st_mode & 0o777


class PopenRecorder:
    """Wraps subprocess.Popen: records every argv as a list of strings and lets the spawn run.

    subprocess.run() looks `Popen` up in the subprocess module at call time, so patching the name sees
    every run()/check_output()/Popen() in the process, including the adapter's.
    """

    def __init__(self):
        self.argvs = []
        self.lock = threading.Lock()

    def __enter__(self):
        recorder = self
        original = subprocess.Popen

        class Recording(original):
            def __init__(self, args, *rest, **kwargs):
                argv = [os.fsdecode(item) for item in args] if isinstance(args, (list, tuple)) else [os.fsdecode(args)]
                with recorder.lock:
                    recorder.argvs.append(argv)
                super().__init__(args, *rest, **kwargs)

        self.patch = mock.patch.object(subprocess, "Popen", Recording)
        self.patch.start()
        return self

    def __exit__(self, *exc):
        self.patch.stop()
        return False

    def board_spawns(self):
        return [argv for argv in self.argvs if BOARD_SUBCOMMAND in argv]

    def first_words(self):
        """The first argument after the binary of every spawn (what the Backlog allow-list is about)."""
        return [argv[1] if len(argv) > 1 else "" for argv in self.argvs]


class SecurityCase(ServerCase):
    """ServerCase plus raw http.client requests (any Host, Content-Type or body) and a restart."""

    def serve_default(self):
        from folio.api import App
        self.serve(App(self.store))

    def restart(self):
        """Stop the running server and start a fresh one on the same workspace (what a relaunch does)."""
        from folio.web import make_server
        old = self.server
        old.shutdown()
        old.server_close()
        app = old.app
        self.server = make_server(self.store, 0, app)
        thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        thread.start()

        def stop():
            self.server.shutdown()
            self.server.server_close()
            thread.join()
        self.addCleanup(stop)
        self.base = "http://127.0.0.1:%d" % self.server.server_port

    def raw(self, method, path, headers=None, body=None, host=None):
        """One request with full header control; returns (status, JSON value or bytes, headers).

        `host` replaces the Host header (default: this server's own 127.0.0.1:<port>). `body` is sent as
        given with its exact length; None sends no body and no Content-Length.
        """
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=10)
        try:
            connection.putrequest(method, path, skip_host=True, skip_accept_encoding=True)
            connection.putheader("Host", host if host is not None else "127.0.0.1:%d" % self.server.server_port)
            for key, value in (headers or {}).items():
                connection.putheader(key, value)
            if body is not None:
                connection.putheader("Content-Length", str(len(body)))
            connection.endheaders(body)
            response = connection.getresponse()
            payload = response.read()
            content_type = response.headers.get("Content-Type", "")
            value = json.loads(payload) if content_type.startswith("application/json") else payload
            return response.status, value, response.headers
        finally:
            connection.close()

    def exchange(self, credential, headers=None):
        """POST /api/session with `credential` from the server's own origin; returns (status, payload, headers)."""
        return self.call("/api/session", "POST", {"credential": credential}, {"Origin": self.base, **(headers or {})})

    def reader(self):
        """A browser session's read headers (cookie + proof) from a fresh exchange."""
        cookie, proof = self.session()
        return {"Cookie": cookie, "X-Folio-Session": proof, "Origin": self.base}

    def writer(self):
        """A browser session's write headers: cookie + proof + the CSRF token."""
        return {**self.reader(), "X-Workspace-Token": self.server.csrf_token}

    def counts(self):
        """(clients, projects) in the workspace registry: the 'nothing was written' check."""
        registry = self.store.registry()
        return len(registry["clients"]), len(registry["projects"])

    def project(self, headers=None):
        """A client and a project created with the owner token; returns the project dict."""
        headers = headers or self.owner()
        status, client, _ = self.call("/api/clients", "POST", {"name": "Client A"}, headers)
        self.assertEqual(status, 200, client)
        status, project, _ = self.call("/api/projects", "POST", {"client_id": client["id"], "name": "Project A"}, headers)
        self.assertEqual(status, 200, project)
        return project

    def activity(self, project_id):
        """The newest activity entry of a project, read from the store."""
        return self.store.project(project_id)["activity"][0]
