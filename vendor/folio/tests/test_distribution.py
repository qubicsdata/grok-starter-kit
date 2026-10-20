import os
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from folio.core import AppError, MIGRATED_MARKER, Store, resolve_workspace
from folio.migration import migrate_workspace
from folio.paths import default_workspace
from folio.transport import HttpTransport, pid_alive
from folio.web import make_server


class DistributionTests(unittest.TestCase):
    def test_workspace_precedence_and_platform_defaults(self):
        self.assertEqual(resolve_workspace('/explicit', {'FOLIO_WORKSPACE': '/env'}), '/explicit')
        self.assertEqual(resolve_workspace(None, {'FOLIO_WORKSPACE': '/env'}), '/env')
        self.assertEqual(default_workspace({'XDG_DATA_HOME': '/custom'}, 'linux'), Path('/custom/folio/workspace'))
        self.assertEqual(default_workspace({'LOCALAPPDATA': '/local'}, 'win32'), Path('/local/Folio/workspace'))
        self.assertEqual(default_workspace({}, 'darwin'), Path.home() / 'Library/Application Support/Folio/workspace')

    def test_workspace_lock_is_process_owned_and_released(self):
        with tempfile.TemporaryDirectory() as temporary:
            store = Store(temporary)
            code = 'from folio.core import Store; s=Store(' + repr(temporary) + '); s.close()'
            blocked = subprocess.run([sys.executable, '-c', code], capture_output=True, timeout=10)
            self.assertNotEqual(blocked.returncode, 0)
            self.assertIn(b'already open', blocked.stderr)
            store.close()
            opened = subprocess.run([sys.executable, '-c', code], capture_output=True, timeout=10)
            self.assertEqual(opened.returncode, 0, opened.stderr)

    def test_migration_preserves_project_roots_state_and_source(self):
        with tempfile.TemporaryDirectory() as temporary:
            source, target = Path(temporary) / 'old', Path(temporary) / 'new'
            store = Store(source)
            client = store.create_client({'name': 'Client'})
            project = store.create_project({'client_id': client['id'], 'name': 'Project'})
            registry = store.registry()
            contents = store.project_path(registry['projects'][0]).read_bytes()
            (source / '.sync').mkdir()
            (source / '.sync' / 'pending.json').write_text('{"attempted":true,"key":"stable"}')
            with self.assertRaisesRegex(ValueError, 'Stop Folio'):
                migrate_workspace(source, target)
            store.close()
            result = migrate_workspace(source, target)
            self.assertEqual(result['retained_project_folders'], [registry['projects'][0]['path']])
            migrated = Store(target)
            try:
                self.assertEqual(migrated.registry(), registry)
                self.assertEqual(migrated.project(project['id']), project)
                self.assertEqual(migrated.project_path(registry['projects'][0]).read_bytes(), contents)
                self.assertEqual((target / '.sync/pending.json').read_bytes(), (source / '.sync/pending.json').read_bytes())
            finally:
                migrated.close()
            self.assertTrue((source / 'registry.json').exists())
            with self.assertRaisesRegex(ValueError, 'already exists'):
                migrate_workspace(source, target)

    def test_migrated_source_refuses_to_reopen_and_names_the_projects_it_still_holds(self):
        with tempfile.TemporaryDirectory() as temporary:
            source, target, chosen = Path(temporary) / 'old', Path(temporary) / 'new', Path(temporary) / 'chosen'
            chosen.mkdir()
            store = Store(source)
            client = store.create_client({'name': 'Client'})
            nested = store.create_project({'client_id': client['id'], 'name': 'Nested'})
            store.create_project({'client_id': client['id'], 'name': 'Chosen', 'folder': str(chosen)})
            nested_path = store.registration(nested['id'])['path']
            store.close()
            result = migrate_workspace(source, target)
            # Deleting the old workspace would delete this project's only copy.
            self.assertEqual(result['projects_inside_source'], [nested_path])
            # Two workspaces must never write the same project folders.
            with self.assertRaisesRegex(AppError, 'migrated to'):
                Store(source)
            with self.assertRaisesRegex(ValueError, 'already migrated'):
                migrate_workspace(source, Path(temporary) / 'again')
            Store(target).close()

    def test_migration_concurrent_destination_is_never_replaced_or_deleted(self):
        from folio.migration import publish_directory
        with tempfile.TemporaryDirectory() as temporary:
            source, target = Path(temporary) / 'source', Path(temporary) / 'target'
            Store(source).close()
            competing = []
            def race(staged, destination):
                self.assertFalse(target.exists())
                store = Store(destination)
                store.create_client({'name': 'Concurrent workspace'})
                competing.append(store)
                publish_directory(staged, destination)
            try:
                with patch('folio.migration.publish_directory', side_effect=race):
                    with self.assertRaises(FileExistsError):
                        migrate_workspace(source, target)
                self.assertEqual(competing[0].registry()['clients'][0]['name'], 'Concurrent workspace')
                self.assertEqual(list(Path(temporary).glob('.target-migrate-*')), [])
                Store(source).close()
            finally:
                for store in competing:
                    store.close()

    def test_migration_cannot_publish_before_source_is_disabled(self):
        with tempfile.TemporaryDirectory() as temporary:
            source, target = Path(temporary) / 'source', Path(temporary) / 'target'
            Store(source).close()
            with patch('folio.migration.write_json', side_effect=OSError('Disk full')):
                with self.assertRaisesRegex(OSError, 'Disk full'):
                    migrate_workspace(source, target)
            self.assertFalse(target.exists())
            Store(source).close()

    def test_migration_interrupt_after_publication_keeps_source_disabled(self):
        from folio.migration import publish_directory
        with tempfile.TemporaryDirectory() as temporary:
            source, target = Path(temporary) / 'source', Path(temporary) / 'target'
            Store(source).close()
            def interrupted(staged, destination):
                self.assertTrue((source / MIGRATED_MARKER).exists())
                publish_directory(staged, destination)
                raise KeyboardInterrupt()
            with patch('folio.migration.publish_directory', side_effect=interrupted):
                with self.assertRaises(KeyboardInterrupt):
                    migrate_workspace(source, target)
            with self.assertRaisesRegex(AppError, 'migrated to'):
                Store(source)
            Store(target).close()

    def test_graceful_authenticated_server_shutdown(self):
        with tempfile.TemporaryDirectory() as temporary:
            store = Store(temporary)
            server = make_server(store, 0)
            thread = threading.Thread(target=server.serve_forever)
            thread.start()
            try:
                transport = HttpTransport(f'http://127.0.0.1:{server.server_address[1]}', {'origin': 'cli'}, token=server.token)
                self.assertEqual(transport.request('POST', '/api/shutdown', {}), {'stopping': True})
                thread.join(5)
                self.assertFalse(thread.is_alive())
            finally:
                if thread.is_alive():
                    server.shutdown()
                server.server_close()
                store.close()

    def test_pid_query_does_not_terminate_current_process(self):
        self.assertTrue(pid_alive(os.getpid()))
        self.assertFalse(pid_alive(-1))


if __name__ == '__main__':
    unittest.main()
