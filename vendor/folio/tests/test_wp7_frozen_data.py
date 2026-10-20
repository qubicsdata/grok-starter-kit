"""WP-7 (3/3) red tests: what the freeze leaves behind for data, the CLI and the server flags.

Folio 1.1.x stored link state in project files (a project key named after the frozen integration, task
keys "sb"/"sb_unlinked") and activity records whose origin is the frozen integration. After the freeze
those files must still load, their legacy keys are kept untouched but never acted on (no ownership of
status, no 503 on delete, no relocate guard), and a restore still detaches them. New writes can no
longer claim the frozen origin. The CLI loses its sync/decision commands (usage error, exit 1) and the
server keeps --no-sync/--no-notifications only as accepted no-ops.

The frozen name is never spelled in this module's file name (the freeze test globs tests/*<name>*).
"""

import inspect
import io
import json
from pathlib import Path
from unittest import mock

from folio.api import App, route
from folio.backup import restore, snapshot
from folio.core import AppError, Store, read_json, write_json

from wp7_support import USER, IsolatedCase

FROZEN = "switchboard"  # folio/ keeps exactly one declaration of this name (core.FROZEN)
PRJ, TSK = "prj_" + "1" * 16, "tsk_" + "2" * 16


def legacy_link(root):
    return {"project_id": PRJ, "root": str(root), "mode": "project", "status": "active", "linked_at": "2026-09-20",
            "workstream_ids": [], "proposals": [{"task_id": "tsk_" + "3" * 16, "title": "Agent idea", "state": "proposed"}],
            "ignored": [], "outbox": [{"id": "e" * 16, "op": "create", "idempotency_key": "k1", "state": "failed",
                                        "folio_task_id": None, "args": {}}]}


class LegacyCase(IsolatedCase):
    """A workspace whose one project file was written by Folio 1.1.x with a live link."""

    def setUp(self):
        super().setUp()
        self.workspace = self.dir / "workspace"
        self.folder = self.dir / "repo"
        self.folder.mkdir()
        store = Store(self.workspace)
        try:
            client = store.create_client({"name": "Example client"})
            project = store.create_project({"client_id": client["id"], "name": "Example rollout", "folder": str(self.folder)})
            self.project_id = project["id"]
            task = store.create_task(self.project_id, {"revision": store.project(self.project_id)["revision"],
                                                       "title": "Agent work", "status": "in_progress"})
            self.task_id = task["id"]
        finally:
            store.close()
        self.path = self.folder / ".task-manager" / "project.json"
        data = read_json(self.path)
        data[FROZEN] = legacy_link(self.folder)
        data["tasks"][0]["sb"] = {"task_id": TSK, "state": "claimed", "assignee": "codex:worker-1", "link": "active", "edits_pending": False}
        data["tasks"][0]["sb_unlinked"] = False
        data["revision"] += 1
        data["activity"].insert(0, {"id": "a" * 16, "message": "Agent claimed", "at": "2026-09-21T10:00:00+00:00",
                                    "origin": FROZEN, "revision": data["revision"]})
        write_json(self.path, data)
        self.legacy = {key: data[key] for key in (FROZEN,)}
        self.legacy_task = {key: data["tasks"][0][key] for key in ("sb", "sb_unlinked")}

    def open(self):
        store = Store(self.workspace)
        self.addCleanup(store.close)
        return store

    def saved(self):
        return read_json(self.path)


class LegacyFilesLoadTests(LegacyCase):
    def test_a_linked_project_file_still_loads_and_reaches_the_state(self):
        store = self.open()
        project = store.project(self.project_id)
        self.assertEqual(project["activity"][0]["origin"], FROZEN)
        state = App(store).state()
        self.assertEqual(state["storage_errors"], [])
        listed = state["projects"][0]
        self.assertNotIn(FROZEN + "_summary", listed)
        self.assertNotIn(FROZEN + "_detected", listed)

    def test_editing_status_and_blocker_of_a_linked_task_is_a_normal_edit(self):
        store = self.open()
        app = App(store)
        revision = store.project(self.project_id)["revision"]
        task = route(app, "PATCH", "/api/projects/%s/tasks/%s" % (self.project_id, self.task_id),
                     {"revision": revision, "status": "blocked", "blocker": "Waiting on review", "title": "Agent work v2"}, USER)
        self.assertEqual((task["status"], task["blocker"]), ("blocked", "Waiting on review"))
        saved = self.saved()
        self.assertEqual(saved[FROZEN], self.legacy[FROZEN], "the legacy link must be kept untouched")
        self.assertEqual({key: saved["tasks"][0][key] for key in ("sb", "sb_unlinked")}, self.legacy_task,
                         "the legacy task link must be kept untouched (no edits_pending bookkeeping)")

    def test_deleting_a_linked_task_is_a_normal_delete(self):
        store = self.open()
        app = App(store)
        revision = store.project(self.project_id)["revision"]
        route(app, "DELETE", "/api/projects/%s/tasks/%s" % (self.project_id, self.task_id), {"revision": revision}, USER)
        self.assertEqual(self.saved()["tasks"], [])

    def test_a_failed_legacy_create_does_not_own_a_task(self):
        data = self.saved()
        data[FROZEN]["outbox"][0]["folio_task_id"] = self.task_id
        del data["tasks"][0]["sb"]
        write_json(self.path, data)
        store = self.open()
        task = store.update_task(self.project_id, self.task_id, {"revision": data["revision"], "status": "done"}, actor=USER)
        self.assertEqual(task["status"], "done")

    def test_a_stale_revision_is_a_conflict_even_after_legacy_origin_records(self):
        store = self.open()
        current = store.project(self.project_id)["revision"]
        with self.assertRaises(AppError) as caught:
            store.update_task(self.project_id, self.task_id, {"revision": current - 1, "title": "Late edit"}, actor=USER)
        self.assertEqual(caught.exception.status, 409)

    def test_new_activity_cannot_claim_the_frozen_origin(self):
        store = self.open()
        revision = store.project(self.project_id)["revision"]
        with self.assertRaises(AppError) as caught:
            store.create_task(self.project_id, {"revision": revision, "title": "Spoofed"}, {"origin": FROZEN, "via": None})
        self.assertEqual(str(caught.exception), "Invalid activity origin.")
        self.assertEqual(len(self.saved()["tasks"]), 1)

    def test_an_unknown_stored_origin_is_still_refused(self):
        data = self.saved()
        data["activity"][0]["origin"] = "elsewhere"
        write_json(self.path, data)
        with self.assertRaises(AppError) as caught:
            self.open().project(self.project_id)
        self.assertEqual(caught.exception.status, 503)

    def test_a_linked_project_can_be_relocated(self):
        store = self.open()
        target = self.dir / "moved"
        target.mkdir()
        result = store.relocate_project(self.project_id, {"folder": str(target)})
        self.assertEqual(result["folder"], str(target.resolve()))
        self.assertEqual(read_json(target / ".task-manager" / "project.json")[FROZEN], self.legacy[FROZEN])

    def test_restore_detaches_the_legacy_links(self):
        store = self.open()
        destination = self.dir / "restored"
        result = restore(snapshot(store), destination)
        self.assertEqual(result["detached_links"], 1)
        self.assertNotIn("detached_" + FROZEN + "_projects", result)
        saved = read_json(destination / "projects" / self.project_id / ".task-manager" / "project.json")
        self.assertNotIn(FROZEN, saved)
        self.assertNotIn("sb", saved["tasks"][0])
        self.assertEqual(saved["tasks"][0]["status"], "blocked")
        self.assertNotIn(FROZEN, saved["tasks"][0]["blocker"].lower())
        self.assertNotIn(FROZEN, json.dumps(saved["activity"][0]).lower())
        self.assertIn(FROZEN, store.project(self.project_id), "the source workspace keeps its data")


class AppShapeTests(IsolatedCase):
    def test_the_app_has_no_sync_or_decision_service(self):
        parameters = set(inspect.signature(App).parameters)
        self.assertFalse(parameters & {"sync", "decisions"}, parameters)
        store = Store(self.dir / "workspace")
        self.addCleanup(store.close)
        app = App(store)
        for name in ("sync", "decisions", "runner"):
            self.assertFalse(hasattr(app, name), name)

    def test_the_store_has_no_sync_mutation_entry(self):
        self.assertFalse(hasattr(Store, "mutate"))


class CliTests(LegacyCase):
    def cli(self, *argv):
        from folio.cli import main
        out = io.StringIO()
        # A command that would start a foreground server (the old `sync --watch`) fails instead of hanging.
        with mock.patch("folio.web.main", side_effect=AssertionError("the CLI started a server")):
            code = main(["--data-dir", str(self.workspace), *argv], env={"HOME": str(self.home)}, stdout=out)
        return code, json.loads(out.getvalue())

    def test_the_sync_and_decision_commands_are_gone(self):
        for argv in (("sync",), ("sync", "--watch"), ("decisions", "list"), ("decisions", "approve", "dec_0123456789abcdef"),
                     ("proposals", "list"), ("projects", "link", "Example rollout"), ("projects", "unlink", "Example rollout"),
                     ("tasks", "dispatch", "Agent work"), ("tasks", "requeue", "Agent work"), ("tasks", "resend", "Agent work"),
                     ("tasks", "force-status", "Agent work", "done", "--yes")):
            with self.subTest(argv=argv):
                code, payload = self.cli(*argv)
                self.assertEqual((code, payload["error"]["code"]), (1, "USAGE"), payload)

    def test_listings_carry_no_sync_fields(self):
        code, status = self.cli("status")
        self.assertEqual(code, 0, status)
        self.assertNotIn("needs_you", status["data"]["totals"])
        self.assertNotIn("sync_problems", status["data"])
        code, projects = self.cli("projects", "list")
        self.assertEqual(code, 0, projects)
        self.assertNotIn(FROZEN + "_detected", projects["data"][0])
        # `folio tasks list` left with WP-6; the task rows a project shows carry no sync fields either.
        code, shown = self.cli("projects", "show", "Example rollout")
        self.assertEqual(code, 0, shown)
        self.assertFalse({FROZEN, "sending"} & set(shown["data"]["tasks"][0]), shown["data"]["tasks"][0])

    def test_reopening_a_formerly_linked_task_works(self):
        # `folio tasks reopen` left with WP-6: the same edit goes through the shared route table.
        store = self.open()
        revision = store.project(self.project_id)["revision"]
        task = route(App(store), "PATCH", "/api/projects/%s/tasks/%s" % (self.project_id, self.task_id),
                     {"status": "backlog", "revision": revision}, USER)
        self.assertEqual(task["status"], "backlog")
        self.assertEqual(self.saved()["tasks"][0]["status"], "backlog")

    def test_no_exit_code_is_reserved_for_the_frozen_integration(self):
        from folio import cli
        self.assertNotIn(6, cli.EXIT_CODES.values())
        self.assertFalse([code for code in cli.EXIT_CODES if FROZEN.upper() in code])


class ServerFlagTests(IsolatedCase):
    def run_main(self, *argv):
        from folio import web
        original = web.make_server

        def stub(*args, **kwargs):
            server = original(*args, **kwargs)
            server.serve_forever = mock.Mock(side_effect=KeyboardInterrupt())
            return server
        out, err = io.StringIO(), io.StringIO()
        with mock.patch("folio.web.make_server", side_effect=stub), mock.patch("sys.stdout", out), mock.patch("sys.stderr", err):
            try:
                web.main([*argv, "--port", "0", "--data-dir", str(self.dir / "served")])
                code = 0
            except SystemExit as exit_:
                code = exit_.code
        return code, out.getvalue(), err.getvalue()

    def test_the_old_off_switches_are_accepted_no_ops(self):
        for argv in ((), ("--no-sync",), ("--no-notifications",), ("--no-sync", "--no-notifications")):
            with self.subTest(argv=argv):
                code, out, err = self.run_main(*argv)
                self.assertEqual(code, 0, err)
                self.assertIn("http://127.0.0.1:", out)
                self.assertNotIn("sync", out.lower())
                self.assertNotIn(FROZEN, out.lower())

    def test_the_home_option_of_the_frozen_integration_is_refused(self):
        code, out, err = self.run_main("--" + FROZEN + "-home", str(self.dir))
        self.assertEqual(code, 2)
        self.assertNotIn("http://127.0.0.1:", out)

    def test_the_help_text_does_not_advertise_sync(self):
        from folio import web
        out = io.StringIO()
        with mock.patch("sys.stdout", out), self.assertRaises(SystemExit):
            web.main(["--help"])
        self.assertNotIn("sync", out.getvalue().lower())
        self.assertNotIn("notifications", out.getvalue().lower())
