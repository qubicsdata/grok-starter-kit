"""WP-7 red tests: plugins are discovered by entry points and enabled only by name in local config.

Acceptance: with no config, nothing is imported (import-hook test). Security: an entry point that is
installed but not named in $XDG_CONFIG_HOME/folio/config.json is never imported; the reserved name
"switchboard" is never imported even when configured; a configured plugin that is not installed, an
unreadable config or an import failure fails closed (PluginError, nothing half-loaded).

The entry-point tests run in an isolated child interpreter (-I) with a synthetic *.dist-info on
sys.path. A sys.meta_path recorder sees every import ATTEMPT of the fake modules, the fake module
writes a marker file when it is actually executed, and sys.modules is reported too, so a miss cannot
hide behind a cached import. The in-process tests inject entry-point stand-ins into the host.
"""

import json
import os
import subprocess
import unittest
from pathlib import Path
from unittest import mock

from wp7_support import (REPO_ROOT, FakeEntryPoint, FakePlugin, IsolatedCase, install_fake_distribution, plugin_factory,
                         python_child_argv, seam)

CHILD = r'''
import json, sys
attempts = []
class Recorder:
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split(".")[0].startswith("folio_"):
            attempts.append(fullname)
        return None
sys.meta_path.insert(0, Recorder())
out = {"attempts": attempts, "seam": True, "error": None, "error_type": None, "plugins": None}
try:
    import folio.plugins as plugins
except ImportError as error:
    out.update(seam=False, error=str(error))
    print(json.dumps(out)); sys.exit(0)
from folio.api import build_app, route
from folio.core import AppError, Store
def finish():
    out["modules"] = sorted(name for name in sys.modules if name.startswith("folio_"))
    print(json.dumps(out))
try:
%s
except Exception as error:
    out.update(error=str(error), error_type=type(error).__name__)
finish()
'''


class ChildCase(IsolatedCase):
    def setUp(self):
        super().setUp()
        self.site = self.dir / "site"
        self.workspace = self.dir / "workspace"
        self.marker = self.dir / "fake.imported"
        self.other_marker = self.dir / "other.imported"

    def install(self, name="fake", module="folio_fake_plugin", marker=None, body=None):
        return install_fake_distribution(self.site, name, module, marker if marker is not None else self.marker, body)

    def run_child(self, body):
        script = CHILD % "\n".join("    " + line for line in body.strip("\n").splitlines())
        proc = subprocess.run(python_child_argv(script, self.site), capture_output=True, text=True, timeout=120,
                              cwd=str(self.dir), env=dict(os.environ))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        out = json.loads(proc.stdout.strip().splitlines()[-1])
        if not out["seam"]:
            self.fail("WP-7 seam folio/plugins/__init__.py is missing: %s" % out["error"])
        return out

    def assert_nothing_imported(self, out, *modules):
        modules = modules or ("folio_fake_plugin",)
        for module in modules:
            self.assertEqual([name for name in out["attempts"] if name.startswith(module)], [], "an import was attempted")
            self.assertEqual([name for name in out["modules"] if name.startswith(module)], [], "the module is in sys.modules")
        self.assertFalse(self.marker.exists(), "the fake plugin module was executed")

    LOAD = "host = plugins.load_from_config()\nout['plugins'] = list(host.plugins)"
    BUILD = ("app = build_app(Store(%r))\nout['plugins'] = list(app.plugins.plugins)\n"
             "try:\n    out['ping'] = route(app, 'GET', '/api/plugins/fake/ping', None, {'origin': 'user', 'via': None})\n"
             "except AppError as error:\n    out['ping'] = error.status\napp.close()")


class NothingImportedWithoutConfigTests(ChildCase):
    def test_with_no_config_file_the_installed_entry_point_is_not_imported(self):
        self.install()
        out = self.run_child(self.LOAD)
        self.assertEqual((out["error"], out["plugins"]), (None, []))
        self.assert_nothing_imported(out)

    def test_with_no_config_file_the_server_app_has_no_plugins(self):
        self.install()
        out = self.run_child(self.BUILD % str(self.workspace))
        self.assertEqual((out["error"], out["plugins"], out["ping"]), (None, [], 404))
        self.assert_nothing_imported(out)

    def test_an_empty_config_object_imports_nothing(self):
        self.install()
        for value in ({}, {"plugins": {}}, {"plugins": None}, {"channel": "example-channel"}):
            with self.subTest(config=value):
                self.marker.unlink(missing_ok=True)
                self.write_config(value)
                out = self.run_child(self.LOAD)
                self.assertEqual((out["error"], out["plugins"]), (None, []))
                self.assert_nothing_imported(out)

    def test_discover_lists_entry_points_without_importing_them(self):
        self.install()
        self.install("other", "folio_other_plugin", self.other_marker)
        out = self.run_child("out['discovered'] = sorted(plugins.discover())")
        self.assertEqual(out["error"], None)
        self.assertEqual(out["discovered"], ["fake", "other"])
        self.assert_nothing_imported(out, "folio_fake_plugin", "folio_other_plugin")
        self.assertFalse(self.other_marker.exists())


class UnconfiguredEntryPointTests(ChildCase):
    def test_an_entry_point_not_named_in_config_is_never_imported(self):
        self.install()
        self.install("other", "folio_other_plugin", self.other_marker)
        self.write_config({"plugins": {"fake": {}}})
        out = self.run_child(self.LOAD)
        self.assertEqual((out["error"], out["plugins"]), (None, ["fake"]))
        self.assertTrue(self.marker.exists(), "the configured plugin was not imported")
        self.assertEqual([name for name in out["attempts"] if name.startswith("folio_other")], [])
        self.assertEqual([name for name in out["modules"] if name.startswith("folio_other")], [])
        self.assertFalse(self.other_marker.exists(), "an unconfigured entry point was imported")

    def test_the_server_app_mounts_only_the_configured_plugin_with_its_settings(self):
        self.install()
        self.install("other", "folio_other_plugin", self.other_marker)
        self.write_config({"plugins": {"fake": {"url": "http://127.0.0.1:11434", "model": "example"}}})
        out = self.run_child(self.BUILD % str(self.workspace))
        self.assertEqual((out["error"], out["plugins"]), (None, ["fake"]))
        self.assertEqual(out["ping"], {"pong": "fake", "settings": {"url": "http://127.0.0.1:11434", "model": "example"}})
        self.assertFalse(self.other_marker.exists())

    def test_the_reserved_name_is_never_imported_even_when_configured(self):
        self.install("switchboard", "folio_fake_switchboard")
        self.write_config({"plugins": {"switchboard": {}}})
        out = self.run_child(self.LOAD)
        self.assertEqual(out["error_type"], "PluginError", out)
        self.assertIsNone(out["plugins"])
        self.assert_nothing_imported(out, "folio_fake_switchboard")

    def test_a_configured_name_without_an_entry_point_fails_closed(self):
        self.install()
        self.write_config({"plugins": {"missing": {}, "fake": {}}})
        out = self.run_child(self.LOAD)
        self.assertEqual(out["error_type"], "PluginError", out)
        self.assertIn("missing", out["error"])
        self.assertIsNone(out["plugins"])

    def test_invalid_config_shapes_fail_closed_without_importing(self):
        self.install()
        shapes = {"list of names": {"plugins": ["fake"]}, "string": {"plugins": "fake"}, "settings not an object": {"plugins": {"fake": "yes"}},
                  "settings null": {"plugins": {"fake": None}}, "uppercase name": {"plugins": {"Fake": {}}},
                  "path-like name": {"plugins": {"../fake": {}}}, "top level array": [], "top level string": '"fake"',
                  "not json": "{plugins: fake}", "empty file": ""}
        for name, value in shapes.items():
            with self.subTest(config=name):
                self.marker.unlink(missing_ok=True)
                self.write_config(value)
                out = self.run_child(self.LOAD)
                self.assertEqual(out["error_type"], "PluginError", out)
                self.assert_nothing_imported(out)

    def test_a_plugin_that_fails_to_import_fails_closed_naming_the_plugin(self):
        self.install(body="raise RuntimeError('broken on import')")
        self.write_config({"plugins": {"fake": {}}})
        out = self.run_child(self.LOAD)
        self.assertEqual(out["error_type"], "PluginError", out)
        self.assertIn("fake", out["error"])
        self.assertIsNone(out["plugins"])

    def test_a_relative_xdg_config_home_is_ignored(self):
        """XDG spec: a relative XDG_CONFIG_HOME is invalid; the host falls back to ~/.config and never reads a cwd-relative file."""
        self.install()
        (self.dir / "relative" / "folio").mkdir(parents=True)
        (self.dir / "relative" / "folio" / "config.json").write_text(json.dumps({"plugins": {"fake": {}}}), encoding="utf-8")
        os.environ["XDG_CONFIG_HOME"] = "relative"
        out = self.run_child(self.LOAD)
        self.assertEqual((out["error"], out["plugins"]), (None, []))
        self.assert_nothing_imported(out)


class HostLoadTests(IsolatedCase):
    def test_only_enabled_entry_points_are_loaded(self):
        module = self.plugins()
        fake, other = FakeEntryPoint("fake", plugin_factory()), FakeEntryPoint("other", plugin_factory(name="other"))
        host = module.PluginHost.load({"fake": {"model": "example"}}, entry_points=[other, fake])
        self.assertEqual((fake.loads, other.loads), (1, 0))
        self.assertEqual(list(host.plugins), ["fake"])
        self.assertEqual(host.plugins["fake"].settings, {"model": "example"})

    def test_enabled_order_is_the_config_order(self):
        module = self.plugins()
        points = [FakeEntryPoint(name, plugin_factory(name=name)) for name in ("alpha", "beta", "gamma")]
        host = module.PluginHost.load({"gamma": {}, "alpha": {}}, entry_points=points)
        self.assertEqual(list(host.plugins), ["gamma", "alpha"])
        self.assertEqual([point.loads for point in points], [1, 0, 1])

    def test_a_plugin_whose_name_differs_from_its_entry_point_is_refused(self):
        module = self.plugins()
        with self.assertRaises(module.PluginError):
            module.PluginHost.load({"fake": {}}, entry_points=[FakeEntryPoint("fake", plugin_factory(name="other"))])

    def test_the_reserved_name_is_refused_before_its_entry_point_loads(self):
        module = self.plugins()
        point = FakeEntryPoint("switchboard", plugin_factory(name="switchboard"))
        with self.assertRaises(module.PluginError):
            module.PluginHost.load({"switchboard": {}}, entry_points=[point])
        self.assertEqual(point.loads, 0)

    def test_a_factory_that_raises_is_wrapped_and_nothing_stays_mounted(self):
        module = self.plugins()

        def explode(settings=None):
            raise RuntimeError("no model configured")
        with self.assertRaises(module.PluginError) as caught:
            module.PluginHost.load({"fake": {}}, entry_points=[FakeEntryPoint("fake", explode)])
        self.assertIn("fake", str(caught.exception))

    def test_a_failed_load_closes_the_plugins_that_were_already_mounted(self):
        """Fail closed means nothing stays half-loaded: an earlier plugin's resources are released too."""
        module = self.plugins()
        made = []

        def make_alpha(settings=None):
            made.append(FakePlugin("alpha", settings=settings))
            return made[-1]

        def explode(settings=None):
            raise RuntimeError("no model configured")
        with self.assertRaises(module.PluginError):
            module.PluginHost.load({"alpha": {}, "beta": {}}, entry_points=[FakeEntryPoint("alpha", make_alpha), FakeEntryPoint("beta", explode)])
        self.assertEqual([plugin.closed for plugin in made], [1])

    def test_an_empty_enable_map_loads_nothing(self):
        module = self.plugins()
        point = FakeEntryPoint("fake", plugin_factory())
        host = module.PluginHost.load({}, entry_points=[point])
        self.assertEqual((point.loads, host.plugins), (0, {}))


class ServerStartupTests(IsolatedCase):
    """folio-server fails closed on a bad plugin config: no server socket, a one-line reason, exit code 2."""

    def test_a_bad_plugin_config_stops_the_server_before_it_listens(self):
        import io
        from folio import web
        self.plugins()
        self.write_config({"plugins": ["fake"]})
        made = []
        stderr = io.StringIO()
        with mock.patch.object(web, "make_server", lambda *args, **kwargs: made.append(args)), \
                mock.patch.object(web.signal, "signal"), mock.patch("sys.stderr", stderr):
            with self.assertRaises(SystemExit) as caught:
                web.main(["--no-sync", "--port", "0", "--data-dir", str(self.dir / "served")])
        self.assertEqual(caught.exception.code, 2)
        self.assertEqual(made, [], "the server was created despite the bad config")
        self.assertIn("plugins", stderr.getvalue())
        self.assertNotIn("Traceback", stderr.getvalue())

    def test_a_missing_plugin_stops_the_server_naming_it(self):
        import io
        from folio import web
        self.plugins()
        self.write_config({"plugins": {"missing_example": {}}})
        stderr = io.StringIO()
        with mock.patch.object(web, "make_server", lambda *args, **kwargs: self.fail("the server was created")), \
                mock.patch.object(web.signal, "signal"), mock.patch("sys.stderr", stderr):
            with self.assertRaises(SystemExit) as caught:
                web.main(["--no-sync", "--port", "0", "--data-dir", str(self.dir / "served")])
        self.assertEqual(caught.exception.code, 2)
        self.assertIn("missing_example", stderr.getvalue())


class ConfigPathTests(IsolatedCase):
    def test_default_config_path_follows_xdg(self):
        module = self.plugins()
        home = str(self.home)  # R-b: a temp-dir home, never a literal /home/<name>
        cases = {
            "absolute xdg": ({"XDG_CONFIG_HOME": "/tmp/xdg-example", "HOME": home}, Path("/tmp/xdg-example/folio/config.json")),
            "relative xdg is ignored": ({"XDG_CONFIG_HOME": "relative", "HOME": home}, Path(home, ".config/folio/config.json")),
            "empty xdg is ignored": ({"XDG_CONFIG_HOME": "", "HOME": home}, Path(home, ".config/folio/config.json")),
            "no xdg": ({"HOME": home}, Path(home, ".config/folio/config.json")),
        }
        for name, (environ, expected) in cases.items():
            with self.subTest(case=name):
                self.assertEqual(Path(module.default_config_path(environ)), expected)

    def test_read_config_missing_file_is_empty_and_never_created(self):
        module = self.plugins()
        self.assertEqual(module.read_config(environ=self.environ), {})
        self.assertFalse((self.config_home / "folio").exists())

    def test_read_config_rejects_non_objects(self):
        module = self.plugins()
        for text in ("[]", "null", "42", '"x"', "", "{"):
            with self.subTest(text=text):
                path = self.write_config(text)
                with self.assertRaises(module.PluginError):
                    module.read_config(path)

    def test_enabled_plugins_shapes(self):
        module = self.plugins()
        self.assertEqual(module.enabled_plugins({}), {})
        self.assertEqual(module.enabled_plugins({"plugins": None}), {})
        self.assertEqual(module.enabled_plugins({"plugins": {"ollama": {"model": "x"}, "fake": {}}}), {"ollama": {"model": "x"}, "fake": {}})
        for value in (["fake"], "fake", {"fake": "yes"}, {"fake": None}, {"Fake": {}}, {"switchboard": {}}, {"": {}}, {"../x": {}}):
            with self.subTest(plugins=value):
                with self.assertRaises(module.PluginError):
                    module.enabled_plugins({"plugins": value})


if __name__ == "__main__":
    unittest.main()
