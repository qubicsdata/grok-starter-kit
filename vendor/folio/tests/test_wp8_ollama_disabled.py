"""WP-8 red tests: the Ollama plugin is off by default, with no outbound socket and nothing imported.

Acceptance: with no local config, build_app() mounts nothing, /api/plugins/ollama/* is 404 (403 without a
credential) and no socket is created (socket monkeypatch); folio_ollama is never imported (a child
interpreter with an import recorder). Security: the plugin is enabled only by the "ollama" entry in
$XDG_CONFIG_HOME/folio/config.json, through the folio.plugins entry point; a config with a non-loopback URL
fails closed at startup (PluginError, nothing mounted).
"""

import json
import subprocess
import unittest

from folio.api import build_app, route
from folio.core import AppError

from wp7_support import REPO_ROOT, IsolatedCase, python_child_argv
from wp8_support import ACCEPT, CHANNEL, FOLIO_OLLAMA, MODEL, SUGGEST, USER, ConnectRecorder, OllamaCase, seam

CHILD = r'''
import json, socket, sys
attempts, connects = [], []
class Recorder:
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split(".")[0] == "folio_ollama":
            attempts.append(fullname)
        return None
sys.meta_path.insert(0, Recorder())
def forbidden(*args, **kwargs):
    connects.append(repr(args[:1]))
    raise AssertionError("outbound socket")
socket.create_connection = forbidden
socket.socket.connect = forbidden
out = {"attempts": attempts, "connects": connects, "error": None, "error_type": None, "plugins": None, "status": None, "code": None}
from folio.api import build_app, route
from folio.core import AppError, Store
def finish():
    out["modules"] = sorted(name for name in sys.modules if name.split(".")[0] == "folio_ollama")
    print(json.dumps(out))
try:
%s
except AppError as error:
    out.update(error=str(error), error_type="AppError", status=error.status, code=error.code)
except Exception as error:
    out.update(error=str(error), error_type=type(error).__name__)
finish()
'''

USER_ACTOR = '{"origin": "user", "via": None}'


def install_entry_point(root):
    """A *.dist-info advertising the REAL folio_ollama package as the `ollama` folio.plugins entry point."""
    info = root / "folio_ollama_dist-1.0.dist-info"
    info.mkdir(parents=True, exist_ok=True)
    (info / "METADATA").write_text("Metadata-Version: 2.1\nName: folio-ollama-dist\nVersion: 1.0\n", encoding="utf-8")
    (info / "entry_points.txt").write_text("[folio.plugins]\nollama = folio_ollama:make\n", encoding="utf-8")


class ChildCase(IsolatedCase):
    def setUp(self):
        super().setUp()
        self.site = self.dir / "site"
        self.workspace = self.dir / "workspace"
        self.site.mkdir()

    def run_child(self, body):
        script = CHILD % "\n".join("    " + line for line in body.strip("\n").splitlines())
        result = subprocess.run(python_child_argv(script, self.site), capture_output=True, text=True, timeout=120,
                                env=dict(self.environ, PATH="/usr/bin:/bin"), cwd=str(REPO_ROOT))
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout.strip().splitlines()[-1])


class DisabledByDefaultTests(ChildCase):
    def test_no_config_imports_nothing_and_answers_404_without_a_socket(self):
        seam(self)
        install_entry_point(self.site)
        out = self.run_child('''
store = Store(%r)
app = build_app(store)
out["plugins"] = sorted(app.plugins.plugins)
try:
    route(app, "POST", %r, {"channel": %r, "task": {"title": "x"}}, %s)
except AppError as error:
    out["status"], out["code"] = error.status, error.code
store.close()
''' % (str(self.workspace), SUGGEST, CHANNEL, USER_ACTOR))
        self.assertIsNone(out["error"], out)
        self.assertEqual(out["plugins"], [])
        self.assertEqual(out["status"], 404)
        self.assertEqual(out["attempts"], [], "folio_ollama was looked up without being enabled")
        self.assertEqual(out["modules"], [])
        self.assertEqual(out["connects"], [])

    def test_a_config_without_the_ollama_entry_imports_nothing(self):
        seam(self)
        install_entry_point(self.site)
        self.write_config({"plugins": {}})
        out = self.run_child('''
store = Store(%r)
app = build_app(store)
out["plugins"] = sorted(app.plugins.plugins)
store.close()
''' % str(self.workspace))
        self.assertEqual((out["error"], out["plugins"], out["attempts"], out["modules"], out["connects"]), (None, [], [], [], []))

    def test_the_config_entry_mounts_the_plugin_through_the_entry_point(self):
        seam(self)
        install_entry_point(self.site)
        self.write_config({"plugins": {"ollama": {"url": "http://127.0.0.1:11434", "model": MODEL, "channel": CHANNEL,
                                                  "repo": str(self.dir / "repo")}}})
        out = self.run_child('''
store = Store(%r)
app = build_app(store)
out["plugins"] = sorted(app.plugins.plugins)
try:
    route(app, "POST", %r, {"channel": "ch-other", "task": {"title": "x"}}, %s)
except AppError as error:
    out["status"], out["code"] = error.status, error.code
app.close()
store.close()
''' % (str(self.workspace), SUGGEST, USER_ACTOR))
        self.assertIsNone(out["error"], out)
        self.assertEqual(out["plugins"], ["ollama"])
        self.assertEqual((out["status"], out["code"]), (409, "SINGLE_CHANNEL"))
        self.assertIn("folio_ollama", out["modules"])
        self.assertEqual(out["connects"], [], "mounting and a refused request must not connect")

    def test_a_non_loopback_url_in_the_config_fails_closed_at_startup(self):
        seam(self)
        install_entry_point(self.site)
        for url in ("http://10.0.0.5:11434", "http://example.com", "http://[2001:db8::1]:11434"):
            with self.subTest(url=url):
                self.write_config({"plugins": {"ollama": {"url": url, "model": MODEL, "channel": CHANNEL, "repo": str(self.dir / "repo")}}})
                out = self.run_child('''
store = Store(%r)
try:
    app = build_app(store)
    out["plugins"] = sorted(app.plugins.plugins)
finally:
    store.close()
''' % str(self.workspace))
                self.assertEqual(out["error_type"], "PluginError", out)
                self.assertIsNone(out["plugins"])
                self.assertEqual(out["connects"], [])

    def test_the_package_is_importable_in_isolation_without_side_effects(self):
        """Importing folio_ollama alone (no config, no app) connects nowhere and spawns nothing."""
        seam(self)
        out = self.run_child('''
import threading
import folio_ollama
out["plugins"] = [folio_ollama.NAME, threading.active_count()]
''')
        self.assertIsNone(out["error"], out)
        self.assertEqual(out["plugins"], ["ollama", 1])
        self.assertEqual(out["connects"], [])


class DisabledInProcessTests(OllamaCase):
    def test_build_app_without_config_has_no_ollama_routes_and_opens_no_socket(self):
        seam(self)
        with ConnectRecorder(forbid=True) as recorder:
            app = build_app(self.store)
            self.assertEqual(app.plugins.plugins, {})
            for method, path, data in (("POST", SUGGEST, self.suggest_data()), ("POST", ACCEPT, self.accept_data(["x"])),
                                       ("GET", SUGGEST, None), ("GET", "/api/plugins/ollama/", None)):
                with self.subTest(method=method, path=path):
                    with self.assertRaises(AppError) as caught:
                        route(app, method, path, data, USER)
                    self.assertEqual(caught.exception.status, 404)
        self.assertEqual(recorder.connects, [])
        self.assert_no_write()

    def test_the_seam_is_a_package_beside_folio(self):
        self.assertTrue((FOLIO_OLLAMA / "__init__.py").is_file(), "WP-8 seam folio_ollama/__init__.py is missing")
        self.assertFalse((REPO_ROOT / "folio" / "ollama").exists(), "the plugin lives outside the folio package")
        self.assertFalse((REPO_ROOT / "folio" / "plugins" / "ollama").exists(), "the plugin lives outside the folio package")


if __name__ == "__main__":
    unittest.main()
