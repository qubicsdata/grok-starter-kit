"""Defensive owner/session authentication checks using disposable local fixtures."""

import io
import json
import os
import tempfile
import threading
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from unittest.mock import patch

from folio import cli
from folio.core import AppError, Store
from folio.local_auth import browser_url, read_server_info
from folio.transport import connect
from folio.web import make_server


class LocalOwnerAuthTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.temp.name) / 'workspace')
        self.server = make_server(self.store, 0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f'http://127.0.0.1:{self.server.server_port}'

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.store.close()
        self.temp.cleanup()

    def call(self, path, method='GET', body=None, headers=None):
        req = Request(self.base + path, method=method,
                      data=json.dumps(body).encode() if body is not None else None,
                      headers={'Content-Type': 'application/json', **(headers or {})})
        try:
            response = urlopen(req, timeout=5)
        except HTTPError as error:
            response = error
        with response:
            return response.status, json.load(response), response.headers

    def session(self, existing_cookie=None):
        code, value, headers = self.call('/api/session', 'POST', {'credential': self.server.browser_token},
                                        {'Origin': self.base, **({'Cookie': existing_cookie} if existing_cookie else {})})
        self.assertEqual(code, 200)
        self.assertTrue(value['authenticated'])
        self.assertEqual(len(value['session_proof']), 64)
        self.assertEqual(headers['Referrer-Policy'], 'no-referrer')
        cookie = headers['Set-Cookie']
        self.assertIn('; HttpOnly;', cookie)
        self.assertIn('; SameSite=Strict;', cookie)
        self.assertIn('; Path=/api', cookie)
        return cookie.split(';', 1)[0], value['session_proof']

    def test_all_api_reads_and_writes_require_owner_or_session(self):
        for method, path, body in [('GET', '/api/state', None), ('GET', '/api/backup', None),
                                   ('GET', '/api/decisions', None), ('POST', '/api/clients', {'name': 'Local'})]:
            with self.subTest(method=method, path=path):
                status, payload, _ = self.call(path, method, body)
                self.assertEqual(status, 403)
                self.assertEqual(payload['code'], 'FORBIDDEN')
        self.assertEqual(self.store.registry()['clients'], [])
        owner = {'X-Workspace-Token': self.server.token}
        status, state, _ = self.call('/api/state', headers=owner)
        self.assertEqual(status, 200)
        self.assertNotIn('token', state)
        self.assertNotIn(self.server.token, json.dumps(state))
        self.assertNotIn(self.server.browser_token, json.dumps(state))

    def test_browser_session_reads_and_csrf_writes(self):
        cookie, proof = self.session()
        status, state, _ = self.call('/api/state', headers={'Cookie': cookie, 'X-Folio-Session': proof})
        self.assertEqual(status, 200)
        self.assertNotEqual(state['csrf_token'], self.server.token)
        for headers in ({'Cookie': cookie}, {'Cookie': cookie, 'X-Folio-Session': proof}, {'X-Workspace-Token': state['csrf_token']}):
            self.assertEqual(self.call('/api/clients', 'POST', {'name': 'Not saved'}, headers)[0], 403)
        headers = {'Cookie': cookie, 'X-Folio-Session': proof, 'X-Workspace-Token': state['csrf_token'], 'Origin': self.base}
        self.assertEqual(self.call('/api/clients', 'POST', {'name': 'Saved'}, headers)[0], 200)
        self.assertEqual(self.call('/api/state', headers={**headers, 'Origin': 'https://example.test'})[0], 403)

    def test_browser_reads_need_cookie_and_origin_scoped_proof(self):
        cookie, proof = self.session()
        for headers in ({'Cookie': cookie}, {'X-Folio-Session': proof}):
            self.assertEqual(self.call('/api/state', headers=headers)[0], 403)
        headers = {'Cookie': cookie, 'X-Folio-Session': proof}
        self.assertEqual(self.call('/api/state', headers=headers)[0], 200)
        self.assertEqual(self.call('/api/state', headers={**headers, 'Origin': 'http://127.0.0.1:1'})[0], 403)
        status, state, _ = self.call('/api/state', headers=headers)
        self.assertNotIn(proof, json.dumps(state))

    def test_second_authorized_tab_preserves_existing_browser_session(self):
        cookie, proof = self.session()
        second_cookie, second_proof = self.session(cookie)
        self.assertEqual((cookie, proof), (second_cookie, second_proof))
        headers = {'Cookie': cookie, 'X-Folio-Session': proof}
        self.assertEqual(self.call('/api/state', headers=headers)[0], 200)
        self.assertEqual(self.call('/api/state', headers={'Cookie': cookie})[0], 403)

    def test_private_discovery_and_cli_no_network_bootstrap(self):
        path = self.store.root / '.server.json'
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        info = read_server_info(self.store.root)
        self.assertEqual(info['owner_token'], self.server.token)
        self.assertEqual(browser_url(self.store.root, self.base), self.base + '/#folio-launch=' + self.server.browser_token)
        transport = connect(self.store.root, {'origin': 'cli'})
        try:
            with patch.object(transport, '_send', wraps=transport._send) as send:
                transport.request('POST', '/api/clients', {'name': 'CLI'})
                self.assertEqual(send.call_count, 1)
                self.assertEqual(send.call_args[0][0:2], ('POST', '/api/clients'))
        finally:
            transport.close()
        if os.name != 'nt':
            path.chmod(0o644)
            try:
                with self.assertRaises(ValueError):
                    read_server_info(self.store.root)
            finally:
                path.chmod(0o600)

    def test_launch_credential_is_not_printed_by_cli_ui(self):
        output = io.StringIO()
        with patch('webbrowser.open') as open_browser:
            code = cli.main(['--data-dir', str(self.store.root), 'ui'], env={}, stdout=output)
        self.assertEqual(code, 0)
        open_browser.assert_called_once_with(browser_url(self.store.root, self.base))
        self.assertNotIn(self.server.browser_token, output.getvalue())
        self.assertNotIn(self.server.token, output.getvalue())
        with patch('webbrowser.open') as open_browser:
            code = cli.main(['--data-dir', str(self.store.root), 'ui', '--no-open'], env={}, stdout=output)
        self.assertEqual(code, 0)
        open_browser.assert_not_called()
        self.assertNotIn(self.server.browser_token, output.getvalue())

    def test_session_credentials_are_rotated_and_discovery_removed_on_close(self):
        old_owner, old_browser = self.server.token, self.server.browser_token
        cookie, proof = self.session()
        old_session = cookie.split('=', 1)[1]
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.assertFalse((self.store.root / '.server.json').exists())
        self.server = make_server(self.store, 0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f'http://127.0.0.1:{self.server.server_port}'
        self.assertNotEqual(old_owner, self.server.token)
        self.assertNotEqual(old_browser, self.server.browser_token)
        self.assertEqual(self.server.sessions, {})
        cookie = f'{self.server.cookie_name}={old_session}'
        self.assertEqual(self.call('/api/state', headers={'Cookie': cookie, 'X-Folio-Session': proof})[0], 403)

    def test_discovery_symlink_is_not_read(self):
        path = self.store.root / '.server.json'
        saved = self.store.root / 'saved-discovery'
        path.rename(saved)
        path.symlink_to(saved.name)
        try:
            with self.assertRaises((OSError, ValueError)):
                read_server_info(self.store.root)
        finally:
            path.unlink()
            saved.rename(path)

    def test_invalid_session_input_returns_safe_error_and_access_log_omits_query(self):
        self.assertEqual(self.call('/api/session', 'POST', {'credential': self.server.browser_token}, {'Origin': 'https://example.test'})[0], 403)
        self.assertEqual(self.call('/api/session', 'POST', {'credential': 'not a credential'})[0], 403)
        self.assertEqual(self.call('/api/session', 'POST', {'credential': '非 ASCII'})[0], 403)
        log = io.StringIO()
        with redirect_stderr(log):
            self.call('/api/state?fixture_label=private-log-fixture')
        self.assertNotIn('private-log-fixture', log.getvalue())
        self.assertNotIn(self.server.token, log.getvalue())
        self.assertNotIn(self.server.browser_token, log.getvalue())


@unittest.skipIf(os.name == 'nt', 'POSIX workspace permissions')
class PrivateWorkspacePermissionsTests(unittest.TestCase):
    def test_new_workspace_is_private_under_collaborative_umask(self):
        with tempfile.TemporaryDirectory() as folder:
            old_umask = os.umask(0o002)
            try:
                store = Store(Path(folder) / 'workspace')
            finally:
                os.umask(old_umask)
            try:
                self.assertEqual(store.root.stat().st_mode & 0o777, 0o700)
                server = make_server(store, 0)
                try:
                    self.assertEqual((store.root / '.server.json').stat().st_mode & 0o777, 0o600)
                finally:
                    server.server_close()
            finally:
                store.close()

    def test_existing_group_writable_workspace_is_refused(self):
        with tempfile.TemporaryDirectory() as folder:
            workspace = Path(folder) / 'workspace'
            workspace.mkdir(mode=0o700)
            workspace.chmod(0o770)
            store = Store(workspace)
            try:
                with self.assertRaisesRegex(AppError, 'not writable by other accounts'):
                    make_server(store, 0)
                self.assertEqual(workspace.stat().st_mode & 0o777, 0o770)
                self.assertFalse((workspace / '.server.json').exists())
            finally:
                store.close()


if __name__ == '__main__':
    unittest.main()
