"""scripts/export-source.py (kept after the WP-6 cuts): exclusions, and a scan whose host-specific
patterns come from the environment (R-b: no literal home or macOS temp path in the script)."""

import importlib.util
import re
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


export = load('source_export', 'scripts/export-source.py')


class SourceExportTests(unittest.TestCase):
    def test_source_export_excludes_history_workflows_and_audit_logs(self):
        for name in ('.super' + 'powers/private-report.md', '.github/workflows/test.yml', '.worktrees/test/x', 'docs/acceptance/output.json',
                     'docs/releases/1.1.0-delivery.json', 'docs/superpowers/plan.md', 'dist/release.tar.gz', 'debug.log'):
            self.assertFalse(export.included(name), name)
        for name in ('LICENSE', 'NOTICE', 'folio/static/icon.svg', 'tests/test_owner_bridge.py', 'docs/distribution.md', 'docs/releases/1.1.0.md'):
            self.assertTrue(export.included(name), name)

    def test_source_scan_reports_locations_without_disclosing_secret_or_home(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            secret = 'ghp_' + 'x' * 40
            (root / 'bad.py').write_text(secret + '\n' + str(Path.home()) + '/private/file')
            findings = export.scan(root)
            self.assertEqual({f['pattern'] for f in findings}, {'github-token', 'personal-home'})
            self.assertNotIn(secret, str(findings))
            self.assertNotIn(str(Path.home()), str(findings))
            (root / 'bad.py').unlink()
            (root / 'good.py').write_text('print("local test")')
            self.assertEqual(export.scan(root), [])

    def test_host_patterns_come_from_the_environment_not_literals(self):
        with tempfile.TemporaryDirectory() as temporary:
            private = Path(temporary) / 'account-temp'
            private.mkdir()
            patterns = export.host_patterns({'TMPDIR': str(private)}, home=Path(temporary) / 'someone')
            self.assertEqual(sorted(patterns), ['github-token', 'personal-home', 'private-key', 'provider-token', 'temporary-host-path'])
            self.assertTrue(patterns['temporary-host-path'].search('Data: %s/tmpabc' % private.resolve()))
            self.assertFalse(patterns['temporary-host-path'].search('Data: %s' % private.resolve()), 'the directory itself is not a leak')
            self.assertTrue(patterns['personal-home'].search('/' + 'Users' + '/someone/repo'))
            self.assertFalse(patterns['personal-home'].search('/' + 'Users' + '/other/repo'))
            root = Path(temporary) / 'tree'
            root.mkdir()
            (root / 'leak.txt').write_text('see %s/tmpabc\n' % private.resolve())
            self.assertEqual([f['pattern'] for f in export.scan(root, patterns)], ['temporary-host-path'])
        self.assertNotIn('temporary-host-path', export.host_patterns({}), 'no TMPDIR, no host temp pattern')

    def test_script_holds_no_literal_home_or_mac_temp_path(self):
        text = (ROOT / 'scripts' / 'export-source.py').read_text(encoding='utf-8')
        rule = re.compile(re.escape('/' + 'Users' + '/') + r'[A-Za-z0-9._-]+|' + re.escape('/' + 'home' + '/') + r'[A-Za-z0-9._-]+|'
                          + re.escape('/' + 'private/var/folders' + '/'))
        self.assertIsNone(rule.search(text))


if __name__ == '__main__':
    unittest.main()
