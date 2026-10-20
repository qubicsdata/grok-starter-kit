import os
import signal
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from folio import web
from folio.core import DEFAULT_WORKSPACE, resolve_workspace

ROOT = Path(__file__).resolve().parent.parent
CLEAN_ENV = {k: v for k, v in os.environ.items() if not k.startswith(("CLAUDECODE", "CODEX_", "COPILOT_", "FOLIO_"))}


class ResolveWorkspaceTests(unittest.TestCase):
    def test_data_dir_then_environment_then_default(self):
        self.assertEqual(resolve_workspace("/explicit", {"FOLIO_WORKSPACE": "/env"}), "/explicit")
        self.assertEqual(resolve_workspace(None, {"FOLIO_WORKSPACE": "/env"}), "/env")
        self.assertEqual(resolve_workspace(None, {}), str(DEFAULT_WORKSPACE))
        self.assertEqual(resolve_workspace("", {"FOLIO_WORKSPACE": ""}), str(DEFAULT_WORKSPACE))


class ServerLifecycleTests(unittest.TestCase):
    def test_local_server_starts_without_dns_resolution(self):
        with tempfile.TemporaryDirectory() as temporary:
            store = web.Store(temporary)
            try:
                with patch("socket.getfqdn", side_effect=AssertionError("Local startup must not resolve DNS")) as lookup:
                    server = web.make_server(store, 0)
                try:
                    self.assertEqual(server.server_name, "localhost")
                    self.assertEqual(server.server_port, server.server_address[1])
                    self.assertGreater(server.server_port, 0)
                    self.assertEqual(server.server_address[0], "127.0.0.1")
                    lookup.assert_not_called()
                finally:
                    server.server_close()
            finally:
                store.close()

    def test_sigterm_removes_server_info_and_server_honors_folio_workspace(self):
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary) / "ws"
            env = {**CLEAN_ENV, "FOLIO_WORKSPACE": str(workspace)}
            process = subprocess.Popen([sys.executable, str(ROOT / "server.py"), "--port", "0"], cwd=str(ROOT), env=env,
                                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            watchdog = threading.Timer(30, process.kill)
            watchdog.start()
            try:
                url = None
                for raw in iter(process.stdout.readline, b""):
                    line = raw.decode("utf-8", "replace").strip()
                    if line.startswith("http://127.0.0.1:"):
                        url = line
                        break
                self.assertIsNotNone(url, process.stderr.read().decode("utf-8", "replace") if process.poll() is not None else "no URL printed")
                info = workspace / ".server.json"
                self.assertTrue(info.exists())
                self.assertTrue((workspace / "registry.json").exists())
                self.assertIn(f'"port": {url.rsplit(":", 1)[1]}', info.read_text())
                process.send_signal(signal.SIGTERM)
                self.assertEqual(process.wait(timeout=15), 0, process.stderr.read().decode("utf-8", "replace"))
                self.assertFalse(info.exists())
            finally:
                watchdog.cancel()
                if process.poll() is None:
                    process.kill()
                    process.wait()
                process.stdout.close()
                process.stderr.close()


# The old --no-sync/--no-notifications flags are accepted no-ops since the WP-7 freeze:
# tests/test_wp7_frozen_data.py::ServerFlagTests.


if __name__ == "__main__":
    unittest.main()
