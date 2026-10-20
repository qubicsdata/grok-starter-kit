import io
import json
import tempfile
import unittest
from pathlib import Path

from folio.api import App, route
from folio.backup import restore, snapshot
from folio.brief import project_brief, read_source
from folio.cli import main
from folio.core import AppError, Store
from folio.notes import change_section, digest, list_sections, sections


class NoteSourceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.store = Store(self.root / "workspace")
        client = self.store.create_client({"name": "Example"})
        self.project_id = self.store.create_project({"client_id": client["id"], "name": "Planning"})["id"]

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def project(self):
        return self.store.project(self.project_id)

    def set_notes(self, notes):
        return self.store.update_project(self.project_id, {"revision": self.project()["revision"], "notes": notes})

    def test_late_decision_is_found_and_full_source_pages_are_verifiable(self):
        self.set_notes("# Background\n" + "Earlier context. " * 3500 + "\n\n## Decision: storage\nUse SQLite WAL for the routing ledger.\n" + "🧭 " * 2000)
        brief = project_brief(self.store, self.project_id, "routing ledger", 500)
        record = next(r for r in brief["records"] if r["kind"] == "decision")
        self.assertIn("SQLite WAL", record["text"])
        self.assertTrue(record["truncated"])
        self.assertLessEqual(brief["returned_chars"], 500)
        parts, offset = [], 0
        while offset is not None:
            result = read_source(self.store, self.project_id, record["source"], offset, 333, record["hash"])
            parts.append(result["text"])
            offset = result["next_offset"]
        self.assertEqual(digest("".join(parts)), record["hash"])
        self.assertEqual(len("".join(parts)), record["total_chars"])
        manifest = self.project()["planning_sources"]
        self.assertEqual(manifest["notes_hash"], digest(self.project()["notes"]))
        source = next(r for r in manifest["records"] if r["source_id"] == record["source"])
        self.assertEqual(source["text"], "".join(parts))

    def test_query_window_reads_end_of_legacy_unheaded_notes(self):
        self.set_notes("Old discussion. " * 4000 + "ZEBRACONFIG uses three retries; this is the latest decision.")
        brief = project_brief(self.store, self.project_id, "zebraconfig", 500)
        record = next(r for r in brief["records"] if r["kind"] == "note")
        self.assertIn("ZEBRACONFIG", record["text"])
        self.assertGreater(record["offset"], 50000)
        self.assertGreater(record["total_chars"], len(record["text"]))

    def test_query_window_keeps_source_offsets_when_casefold_expands_unicode(self):
        self.set_notes("ß" * 30000 + "IMPORTANTNEEDLE decision" + " ordinary" * 3000)
        brief = project_brief(self.store, self.project_id, "importantneedle", 500)
        record = next(r for r in brief["records"] if r["kind"] == "note")
        self.assertIn("IMPORTANTNEEDLE", record["text"])
        source = read_source(self.store, self.project_id, record["source"], record["offset"], len(record["text"]), record["hash"])
        self.assertEqual(source["text"], record["text"])

    def test_section_crud_preserves_neighbors_identity_and_checks_concurrency(self):
        self.set_notes("# Untouched\nKeep this section exact.\n\n## Decision\nUse Redis.\n")
        original = next(s for s in sections(self.project()) if s["kind"] == "decision")
        changed = change_section(self.store, self.project_id, {"revision": self.project()["revision"], "hash": original["hash"], "title": "Storage decision", "text": "Use SQLite."}, original["id"])
        self.assertEqual(changed["source"], original["source"])
        self.assertIn("# Untouched\nKeep this section exact.", self.project()["notes"])
        self.assertNotIn("Use Redis", self.project()["notes"])
        with self.assertRaises(AppError) as stale:
            read_source(self.store, self.project_id, original["source"], expected_hash=original["hash"])
        self.assertEqual(stale.exception.code, "SOURCE_CHANGED")
        with self.assertRaises(AppError):
            change_section(self.store, self.project_id, {"revision": self.project()["revision"], "hash": original["hash"], "text": "Wrong edit"}, original["id"])
        forgotten = change_section(self.store, self.project_id, {"revision": self.project()["revision"], "hash": changed["hash"]}, changed["id"], delete=True)
        self.assertTrue(forgotten["deleted"])
        self.assertNotIn("SQLite", json.dumps(self.project()))
        self.assertIn("Keep this section exact", self.project()["notes"])
        with self.assertRaises(AppError):
            read_source(self.store, self.project_id, changed["source"])

    def test_fenced_markdown_is_not_mistaken_for_a_section(self):
        self.set_notes("## Architecture\n```markdown\n# Example, not a section\n```\n\n## Decision\nKeep it simple.")
        self.assertEqual([s["title"] for s in sections(self.project())], ["Architecture", "Decision"])

    def test_backup_restore_keeps_ids_and_rebuilds_manifest(self):
        saved = change_section(self.store, self.project_id, {"revision": self.project()["revision"], "title": "Storage", "text": "SQLite WAL", "kind": "decision"})
        destination = self.root / "restored"
        restore(snapshot(self.store), destination)
        restored = Store(destination)
        try:
            record = read_source(restored, self.project_id, saved["source"], expected_hash=saved["hash"])
            self.assertEqual(record["text"], saved["text"])
            self.assertEqual(record["revision"], restored.project(self.project_id)["revision"])
        finally:
            restored.close()

    def test_api_and_cli_source_and_note_lifecycle(self):
        app = App(self.store)
        result = route(app, "POST", f"/api/projects/{self.project_id}/notes/sections", {"revision": self.project()["revision"], "title": "Decision", "text": "Prefer SQLite", "kind": "decision"}, None)
        source = route(app, "POST", f"/api/projects/{self.project_id}/source", {"source_id": result["source"], "hash": result["hash"], "max_chars": 9}, None)
        self.assertEqual(source["next_offset"], 9)
        self.store.close()
        def cli(*args):
            output = io.StringIO()
            code = main(["--data-dir", str(self.root / "workspace"), *args], stdout=output, env={})
            self.assertEqual(code, 0, output.getvalue())
            return json.loads(output.getvalue())["data"]
        try:
            added = cli("notes", "add", "Planning", "--title", "Delivery", "--text", "Ship on Friday", "--kind", "decision")
            changed = cli("notes", "update", "Planning", added["source"], "--text", "Ship on Monday")
            self.assertEqual(changed["source"], added["source"])
            self.assertIn("Monday", cli("source", changed["source"], "--project", "Planning", "--hash", changed["hash"])["text"])
            cli("notes", "delete", "Planning", changed["source"], "--yes")
            self.assertEqual(len(cli("notes", "list", "Planning")["sections"]), 1)
        finally:
            self.store = Store(self.root / "workspace")
