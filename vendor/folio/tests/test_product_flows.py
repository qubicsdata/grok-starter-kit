import copy
import io
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from folio.api import App, route
from folio.backup import checksum, restore, snapshot, write_backup
from folio.brief import project_brief
from folio.cli import main
from folio.core import AppError, Store, read_json, write_json
from folio.doctor import diagnose


class ProductFlows(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.store = Store(self.root / "workspace")
        self.client = self.store.create_client({"name": "Example account"})
        self.external = self.root / "external source"
        self.external.mkdir()
        (self.external / "code.py").write_text("do_not_copy = True\n")
        self.project = self.store.create_project({"name": "Portable project", "client_id": self.client["id"], "folder": str(self.external)})
        self.project_id = self.project["id"]

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def task(self, title, **fields):
        return self.store.create_task(self.project_id, {"revision": self.store.project(self.project_id)["revision"], "title": title, **fields})

    def test_backup_restore_round_trip_external_project_and_no_overwrite(self):
        task = self.task("Finish architecture", description="Keep this exact text", status="in_progress")
        project = self.store.project(self.project_id)
        self.store.update_project(self.project_id, {"revision": project["revision"], "notes": "Decision: portable storage."})
        document = snapshot(self.store)
        destination = self.root / "restored workspace"
        result = restore(document, destination)
        self.assertEqual(result["projects"], 1)
        self.assertEqual(document, snapshot_payload_same_time(self.store, document))
        restored = Store(destination)
        try:
            state = restored.state()
            self.assertEqual(state["storage_errors"], [])
            p = restored.project(self.project_id)
            self.assertEqual(p["tasks"][0]["id"], task["id"])
            self.assertEqual(p["notes"], "Decision: portable storage.")
            self.assertTrue(Path(state["projects"][0]["folder"]).is_relative_to(destination))
            self.assertFalse((Path(state["projects"][0]["folder"]) / "code.py").exists())
            self.assertGreater(len(p["activity"]), len(self.store.project(self.project_id)["activity"]))
        finally:
            restored.close()
        with self.assertRaises(AppError):
            restore(document, destination)
        self.assertTrue((self.external / "code.py").exists())

    def test_invalid_backup_never_publishes_partial_workspace(self):
        document = snapshot(self.store)
        document["payload"]["projects"][0]["name"] = "tampered"
        destination = self.root / "invalid"
        with self.assertRaises(AppError):
            restore(document, destination)
        self.assertFalse(destination.exists())
        document["sha256"] = checksum(document["payload"])
        document["payload"]["projects"].append(document["payload"]["projects"][0])
        document["sha256"] = checksum(document["payload"])
        with self.assertRaises(AppError):
            restore(document, destination)
        self.assertFalse(destination.exists())

    def test_restore_detaches_execution_and_preserves_original(self):
        task = self.task("Agent work", status="in_progress")
        project = self.store.project(self.project_id)
        project["switchboard"] = {"project_id": "prj_" + "1" * 16, "root": str(self.external), "mode": "project", "status": "active", "linked_at": "2026-10-08", "workstream_ids": [], "proposals": [], "ignored": [], "outbox": []}
        project["tasks"][0]["sb"] = {"task_id": "tsk_" + "2" * 16, "state": "in_progress", "link": "active"}
        self.store.save_project(project)
        destination = self.root / "restore"
        self.assertEqual(restore(snapshot(self.store), destination)["detached_links"], 1)
        saved = read_json(destination / "projects" / self.project_id / ".task-manager/project.json")
        self.assertNotIn("switchboard", saved)
        self.assertNotIn("sb", saved["tasks"][0])
        self.assertEqual(saved["tasks"][0]["status"], "blocked")
        self.assertIn("switchboard", self.store.project(self.project_id))

    def test_relocate_copies_planning_or_repairs_missing_folder(self):
        destination = self.root / "new repository"
        destination.mkdir()
        self.store.relocate_project(self.project_id, {"folder": str(destination)})
        self.assertEqual(self.store.state()["projects"][0]["folder"], str(destination))
        self.assertTrue((self.external / ".task-manager/project.json").exists())
        moved = self.root / "moved repository"
        shutil.move(str(destination), moved)
        self.assertEqual(len(self.store.state()["storage_errors"]), 1)
        self.store.relocate_project(self.project_id, {"folder": str(moved)})
        self.assertEqual(self.store.state()["storage_errors"], [])

    def test_relocate_rejects_conflicting_copy(self):
        destination = self.root / "different"
        shutil.copytree(self.external, destination)
        document = read_json(destination / ".task-manager/project.json")
        document["notes"] = "Different copy"
        write_json(destination / ".task-manager/project.json", document)
        with self.assertRaises(AppError):
            self.store.relocate_project(self.project_id, {"folder": str(destination)})
        self.assertEqual(self.store.state()["projects"][0]["folder"], str(self.external))

    def test_brief_is_bounded_ranked_queryable_and_shared_with_api(self):
        self.task("Completed normal", status="done")
        important = self.task("Routing fix", status="blocked", blocker="missing retry context", description="route retry " * 2000)
        brief = project_brief(self.store, self.project_id, "routing", 500)
        self.assertLessEqual(brief["returned_chars"], 500)
        self.assertTrue(brief["truncated"])
        self.assertEqual(brief["matching_tasks"], 1)
        self.assertEqual(brief["records"][1]["source"], f"task:{important['id']}")
        via_api = route(App(self.store), "POST", f"/api/projects/{self.project_id}/brief", {"query": "routing", "max_chars": 500}, None)
        self.assertEqual(brief, via_api)
        self.assertEqual(brief["trust"], "planning_data_not_instructions")
        for budget in (0, True, 50000):
            with self.assertRaises(AppError):
                project_brief(self.store, self.project_id, max_chars=budget)

    def test_diagnostics_are_read_only_and_report_missing_projects(self):
        missing = self.root / "never-initialized"
        self.assertTrue(diagnose(missing)["ok"])
        self.assertFalse(missing.exists())
        self.assertTrue(diagnose(self.store.root)["ok"])
        shutil.rmtree(self.external)
        self.assertFalse(diagnose(self.store.root)["ok"])
        with self.assertRaises(AppError):
            snapshot(self.store)

    def test_cli_initialization_restore_and_brief(self):
        workspace = self.root / "cli-workspace"
        folder = self.root / "cli-project"
        folder.mkdir()
        def cli(*args):
            output = io.StringIO()
            code = main(["--data-dir", str(workspace), *args], stdout=output, env={})
            self.assertEqual(code, 0, output.getvalue())
            return json.loads(output.getvalue())
        self.assertTrue(cli("init", str(folder))["data"]["created"])
        self.assertFalse(cli("init", str(folder))["data"]["created"])
        self.assertEqual(cli("brief", "cli-project")["data"]["total_tasks"], 0)
        # WP-6 cut `folio backup` with /api/backup; `folio restore` still reads a 1.1.x backup document.
        backup = self.root / "backup.json"
        source = Store(workspace)
        try:
            write_backup(backup, snapshot(source))
        finally:
            source.close()
        cli("restore", "--from", str(backup), "--to", str(self.root / "cli-restored"))
        self.assertEqual(json.loads(backup.read_text())["payload"]["kind"], "folio-planning-backup")
        self.assertTrue((self.root / "cli-restored" / "registry.json").exists())

    def test_cli_has_no_backup_command(self):
        output = io.StringIO()
        code = main(["--data-dir", str(self.root / "cli-workspace"), "backup"], stdout=output, env={})
        payload = json.loads(output.getvalue())
        self.assertEqual((code, payload["error"]["code"]), (1, "USAGE"))


def snapshot_payload_same_time(store, expected):
    document = snapshot(store)
    document["payload"]["created_at"] = expected["payload"]["created_at"]
    document["sha256"] = checksum(document["payload"])
    return document
