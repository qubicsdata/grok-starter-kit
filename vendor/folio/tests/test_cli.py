import io
import json
import os
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
CLEAN_ENV = {k: v for k, v in os.environ.items() if not k.startswith(("CLAUDECODE", "CODEX_", "COPILOT_", "FOLIO_"))}


def run_cli(workspace, *args, env=None, stdin=None):
    environment = {**CLEAN_ENV, **(env or {})}
    result = subprocess.run([sys.executable, str(ROOT / "bin" / "folio"), "--data-dir", str(workspace), *args],
                            capture_output=True, text=True, timeout=60, env=environment, input=stdin)
    try:
        payload = json.loads(result.stdout) if result.stdout.strip().startswith("{") else None
    except ValueError:
        payload = None
    return result.returncode, payload, result


class CliDirectTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temporary.name) / "workspace"

    def tearDown(self):
        self.temporary.cleanup()

    def cli(self, *args, **kwargs):
        return run_cli(self.workspace, *args, **kwargs)

    def seed(self):
        code, client, _ = self.cli("clients", "add", "--name", "Northstar")
        self.assertEqual(code, 0)
        code, project, _ = self.cli("projects", "add", "--client", "Northstar", "--name", "Cloud foundation")
        self.assertEqual(code, 0, project)
        return client["data"], project["data"]

    def test_envelope_and_status(self):
        client, project = self.seed()
        self.assertEqual(client["name"], "Northstar")
        code, payload, _ = self.cli("status")
        self.assertEqual(code, 0)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["data"]["totals"]["projects"], 1)
        self.assertEqual(payload["data"]["clients"][0]["client"], "Northstar")

    def test_usage_error_exit_1(self):
        code, payload, _ = self.cli("projects", "frobnicate")
        self.assertEqual(code, 1)
        self.assertEqual(payload["error"]["code"], "USAGE")
        code, payload, _ = self.cli()
        self.assertEqual(code, 1)

    def test_not_found_and_ambiguous_exit_2(self):
        self.seed()
        code, payload, _ = self.cli("projects", "show", "Nope")
        self.assertEqual((code, payload["error"]["code"]), (2, "NOT_FOUND"))
        self.cli("clients", "add", "--name", "Northstar")
        code, payload, _ = self.cli("projects", "add", "--client", "Northstar", "--name", "X")
        self.assertEqual((code, payload["error"]["code"]), (2, "AMBIGUOUS_REFERENCE"))
        self.assertEqual(len(payload["error"]["candidates"]), 2)

    def test_validation_exit_4(self):
        self.seed()
        code, payload, _ = self.cli("projects", "update", "Cloud foundation", "--target-date", "2026-02-30")
        self.assertEqual((code, payload["error"]["code"]), (4, "VALIDATION"))

    def test_projects_update_archive_requires_yes(self):
        self.seed()
        code, payload, _ = self.cli("projects", "update", "Cloud foundation", "--status", "archived")
        self.assertEqual((code, payload["error"]["code"]), (1, "USAGE"))
        code, payload, _ = self.cli("projects", "update", "Cloud foundation", "--status", "archived", "--yes")
        self.assertEqual(code, 0)
        self.assertEqual(payload["data"]["status"], "archived")
        code, payload, _ = self.cli("projects", "list")
        self.assertEqual(payload["data"], [])
        code, payload, _ = self.cli("projects", "list", "--archived")
        self.assertEqual(len(payload["data"]), 1)

    def test_workstreams_clients_update_and_table_format(self):
        self.seed()
        code, payload, _ = self.cli("workstreams", "add", "Cloud foundation", "Governance", "--color", "teal")
        self.assertEqual((code, payload["data"]["name"]), (0, "Governance"))
        code, payload, _ = self.cli("clients", "update", "Northstar", "--description", "Financial services")
        self.assertEqual(payload["data"]["description"], "Financial services")
        code, _, result = self.cli("projects", "list", "--format", "table")
        self.assertEqual(code, 0)
        self.assertIn("Cloud foundation", result.stdout)
        self.assertFalse(result.stdout.lstrip().startswith("{"))

    def test_activity_is_attributed_to_detected_harness(self):
        self.seed()
        self.cli("workstreams", "add", "Cloud foundation", "Governance", env={"CLAUDECODE": "1"})
        code, payload, _ = self.cli("projects", "show", "Cloud foundation")
        entry = payload["data"]["activity"][0]
        self.assertEqual((entry["origin"], entry["via"]), ("cli", "cli:claude-code"))


class CliHttpTests(unittest.TestCase):
    def test_cli_uses_running_server(self):
        from folio.core import Store
        from folio.web import make_server, remove_server_info, write_server_info
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary) / "workspace"
            store = Store(workspace)
            server = make_server(store, 0)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            write_server_info(store.root, server.server_address[1])
            try:
                code, payload, result = run_cli(workspace, "clients", "add", "--name", "Live")
                self.assertEqual(code, 0, result.stderr)
                self.assertEqual(store.registry()["clients"][0]["name"], "Live")
            finally:
                server.shutdown()
                server.server_close()
                thread.join()
                remove_server_info(store.root)
                store.close()


class DetectViaTests(unittest.TestCase):
    def test_labels(self):
        from folio.cli import detect_via
        self.assertEqual(detect_via({"CLAUDECODE": "1"}), "cli:claude-code")
        self.assertEqual(detect_via({"CODEX_SANDBOX": "seatbelt"}), "cli:codex")
        self.assertEqual(detect_via({"COPILOT_AGENT": "1"}), "cli:copilot")
        self.assertEqual(detect_via({"FOLIO_VIA": "cli:custom"}), "cli:custom")
        self.assertEqual(detect_via({}), "cli")
        self.assertEqual(detect_via({"FOLIO_VIA": "Bad Label!"}), "cli")


class CliInternalErrorTests(unittest.TestCase):
    def test_unexpected_exception_becomes_internal_error_envelope(self):
        from folio.cli import main

        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary) / "workspace"
            stdout = io.StringIO()
            with patch("folio.cli.cmd_status", side_effect=RuntimeError("boom")):
                code = main(["--data-dir", str(workspace), "status"], env={}, stdout=stdout)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(code, 5)
        self.assertEqual(payload["error"]["code"], "INTERNAL_ERROR")
        self.assertIn("boom", payload["error"]["message"])


class CliNotesTests(unittest.TestCase):
    """Task CRUD left the CLI in WP-6 (tests/test_wp6_routes.py checks the usage errors); notes stay."""

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temporary.name) / "workspace"
        self.cli("clients", "add", "--name", "Northstar")
        self.cli("projects", "add", "--client", "Northstar", "--name", "Cloud foundation")
        self.cli("projects", "add", "--client", "Northstar", "--name", "Data platform")

    def tearDown(self):
        self.temporary.cleanup()

    def cli(self, *args, **kwargs):
        return run_cli(self.workspace, *args, **kwargs)

    def test_notes_append_from_argument_and_stdin_then_show(self):
        code, _, _ = self.cli("notes", "append", "Cloud foundation", "--text", "Decision: managed services")
        self.assertEqual(code, 0)
        code, payload, _ = self.cli("notes", "append", "Cloud foundation", "--text", "-", stdin="From stdin\n")
        self.assertEqual(code, 0)
        code, payload, _ = self.cli("notes", "show", "Cloud foundation")
        self.assertEqual(payload["data"]["notes"], "Decision: managed services\n\nFrom stdin")


class WithRevisionTests(unittest.TestCase):
    def test_retries_once_on_conflict_then_raises(self):
        from folio.cli import CliError, Context

        class FakeTransport:
            """Each read returns the next revision, as if another window saved in between."""

            def __init__(self):
                self.revision = 0

            def request(self, method, path, data=None):
                self.revision += 1
                return {"clients": [], "storage_errors": [], "projects": [{"id": "p", "revision": self.revision}]}

        context = Context(FakeTransport())
        calls = []

        def conflict_once(revision):
            calls.append(revision)
            if len(calls) == 1:
                raise CliError("CONFLICT", "stale")
            return "saved"

        self.assertEqual(context.with_revision("p", conflict_once), "saved")
        self.assertEqual(calls, [1, 2])

        def always_conflict(revision):
            raise CliError("CONFLICT", "stale")

        with self.assertRaises(CliError):
            context.with_revision("p", always_conflict)

        def other_error(revision):
            calls.append("other")
            raise CliError("VALIDATION", "bad")

        calls.clear()
        with self.assertRaises(CliError):
            context.with_revision("p", other_error)
        self.assertEqual(calls, ["other"])


class running_server:
    """An in-thread Folio server for a workspace, advertised through .server.json."""

    def __init__(self, workspace):
        self.workspace = workspace

    def __enter__(self):
        from folio.core import Store
        from folio.web import make_server, write_server_info
        self.requests = []
        self.store = Store(self.workspace)
        self.server = make_server(self.store, 0)
        self.log = patch("folio.web.Handler.log_message", lambda handler, fmt, *args: self.requests.append(args))
        self.log.start()
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        write_server_info(self.store.root, self.server.server_address[1])
        return self

    def __exit__(self, *exc):
        from folio.web import remove_server_info
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.log.stop()
        remove_server_info(self.store.root)
        self.store.close()


class CliConcurrencyTests(unittest.TestCase):
    def test_parallel_direct_runs_wait_for_the_workspace_lock(self):
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary) / "workspace"
            command = [sys.executable, str(ROOT / "bin" / "folio"), "--data-dir", str(workspace), "status"]
            processes = [subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=CLEAN_ENV)
                         for _ in range(6)]
            outputs = [process.communicate(timeout=60) for process in processes]
            self.assertEqual([process.returncode for process in processes], [0] * 6, outputs)
            self.assertTrue(all(json.loads(stdout)["ok"] for stdout, _ in outputs))


class CliStorageParityTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temporary.name) / "workspace"

    def tearDown(self):
        if self.workspace.is_dir():
            os.chmod(self.workspace, 0o700)
        self.temporary.cleanup()

    def assertStorageError(self, outcome):
        from folio.core import STORAGE_MESSAGE
        code, payload, result = outcome
        self.assertEqual((code, payload["error"]["code"], payload["error"]["message"]), (5, "STORAGE", STORAGE_MESSAGE),
                         result.stdout + result.stderr)

    def test_corrupt_registry_is_storage_error_in_direct_mode(self):
        self.assertEqual(run_cli(self.workspace, "status")[0], 0)
        (self.workspace / "registry.json").write_text("{ not json")
        self.assertStorageError(run_cli(self.workspace, "status"))

    @unittest.skipIf(hasattr(os, "geteuid") and os.geteuid() == 0, "root ignores folder permissions")
    def test_unwritable_workspace_is_the_same_storage_error_over_http_and_direct(self):
        self.assertEqual(run_cli(self.workspace, "status")[0], 0)
        os.chmod(self.workspace, 0o500)
        try:
            self.assertStorageError(run_cli(self.workspace, "clients", "add", "--name", "Direct"))
        finally:
            os.chmod(self.workspace, 0o700)
        with running_server(self.workspace) as live:
            os.chmod(self.workspace, 0o500)
            try:
                self.assertStorageError(run_cli(self.workspace, "clients", "add", "--name", "Over HTTP"))
            finally:
                os.chmod(self.workspace, 0o700)
            self.assertIn(("POST /api/clients HTTP/1.1", "500", "-"), [args[:3] for args in live.requests if len(args) >= 3])
            self.assertEqual(live.store.registry()["clients"], [])


class CliHttpErrorParityTests(unittest.TestCase):
    def test_not_found_and_validation_match_direct_mode(self):
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary) / "workspace"
            self.assertEqual(run_cli(workspace, "clients", "add", "--name", "Northstar")[0], 0)
            self.assertEqual(run_cli(workspace, "projects", "add", "--client", "Northstar", "--name", "Cloud foundation")[0], 0)
            commands = (("projects", "show", "Nope"), ("projects", "update", "Cloud foundation", "--target-date", "2026-02-30"))
            direct = [run_cli(workspace, *command) for command in commands]
            with running_server(workspace) as live:
                over_http = [run_cli(workspace, *command) for command in commands]
                self.assertIn("400", [args[1] for args in live.requests if len(args) >= 2 and args[0].startswith("PATCH ")])
            expected = [(2, "NOT_FOUND"), (4, "VALIDATION")]
            for outcomes in (direct, over_http):
                self.assertEqual([(code, payload["error"]["code"]) for code, payload, _ in outcomes], expected)
            self.assertEqual([payload["error"]["message"] for _, payload, _ in direct],
                             [payload["error"]["message"] for _, payload, _ in over_http])


class NotesStdinTests(unittest.TestCase):
    def test_text_dash_from_a_terminal_is_usage_error_instead_of_hanging(self):
        from folio.cli import main

        class Terminal:
            def isatty(self):
                return True

            def read(self):
                raise AssertionError("must not wait for terminal input")

        with tempfile.TemporaryDirectory() as temporary:
            workspace = str(Path(temporary) / "workspace")
            for argv in (["clients", "add", "--name", "C"], ["projects", "add", "--client", "C", "--name", "P"]):
                self.assertEqual(main(["--data-dir", workspace, *argv], env={}, stdout=io.StringIO()), 0)
            stdout = io.StringIO()
            with patch("sys.stdin", Terminal()):
                code = main(["--data-dir", workspace, "notes", "append", "P", "--text", "-"], env={}, stdout=stdout)
        payload = json.loads(stdout.getvalue())
        self.assertEqual((code, payload["error"]["code"]), (1, "USAGE"))
        self.assertIn("stdin", payload["error"]["message"])


if __name__ == "__main__":
    unittest.main()
