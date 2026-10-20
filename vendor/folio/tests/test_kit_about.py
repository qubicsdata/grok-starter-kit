"""The About texts (attribution, website, help link) come from the local config, never from the code.

With no local config, or one without an "about" object, `/api/state` carries empty texts and the UI
shows no attribution, website or help link. An "about" object in `$XDG_CONFIG_HOME/folio/config.json`
sets them:

    {"about": {"attribution": "...", "website": "https://...", "help_url": "https://..."}}

Anything else (an unknown key, a non-string, more than one line, an address that is not http(s))
is refused at startup like a bad plugin config: `folio-server` prints one line and exits 2.
"""

import json
import os
import re
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.request import Request, urlopen

from folio import __version__, web
from folio.api import App
from folio.core import Store
from folio.plugins import PluginError

REPO_ROOT = Path(__file__).resolve().parents[1]
STATIC = REPO_ROOT / "folio" / "static"
EMPTY = {"attribution": "", "website": "", "help_url": ""}
VALID = {"attribution": "Maintained by Example Person", "website": "https://example.com/",
         "help_url": "https://example.org/folio/help"}


def fixed(**texts):
    return {"name": "Folio", "version": __version__, "license": "Apache-2.0",
            "license_url": "/LICENSE.txt", "notice_url": "/NOTICE.txt", **texts}


class ProductInfoTests(unittest.TestCase):
    def test_default_texts_are_empty(self):
        for config in (None, {}, {"plugins": {}}, {"about": None}, {"about": {}}):
            with self.subTest(config=config):
                self.assertEqual(web.product_info(config), fixed(**EMPTY))

    def test_about_object_sets_the_texts(self):
        self.assertEqual(web.product_info({"about": VALID}), fixed(**VALID))
        partial = web.product_info({"about": {"website": "http://127.0.0.1:9000/"}})
        self.assertEqual(partial, fixed(attribution="", website="http://127.0.0.1:9000/", help_url=""))

    def test_fixed_facts_cannot_be_overridden(self):
        for key in ("name", "version", "license", "license_url", "notice_url"):
            with self.subTest(key=key), self.assertRaises(PluginError):
                web.product_info({"about": {key: "x"}})

    def test_invalid_about_is_refused(self):
        cases = {
            "not an object": ["x"],
            "unknown key": {"homepage": "https://example.com/"},
            "number": {"attribution": 7},
            "too long": {"attribution": "x" * 201},
            "two lines": {"attribution": "one\ntwo"},
            "bidi override": {"attribution": "abc\u202edef"},
            "script address": {"website": "javascript:alert(1)"},
            "no scheme": {"website": "example.com"},
            "ftp": {"help_url": "ftp://example.com/"},
            "space in address": {"help_url": "https://example.com/a b"},
            "quote in address": {"website": "https://example.com/\"onmouseover=x"},
        }
        for name, about in cases.items():
            with self.subTest(case=name), self.assertRaises(PluginError):
                web.product_info({"about": about})

    def test_limit_is_inclusive(self):
        self.assertEqual(web.product_info({"about": {"attribution": "x" * 200}})["attribution"], "x" * 200)


class StatePayloadTests(unittest.TestCase):
    def serve(self, app=None):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        store = Store(temporary.name)
        self.addCleanup(store.close)
        server = web.make_server(store, 0, app(store) if app else None)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(thread.join)
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        request = Request(f"http://127.0.0.1:{server.server_address[1]}/api/state",
                          headers={"X-Workspace-Token": server.token})
        with urlopen(request, timeout=5) as response:
            return json.loads(response.read())

    def test_state_without_config_has_empty_texts(self):
        self.assertEqual(self.serve()["product"], fixed(**EMPTY))

    def test_state_carries_the_app_texts(self):
        app = lambda store: App(store, product=web.product_info({"about": VALID}))
        self.assertEqual(self.serve(app)["product"], fixed(**VALID))

    def test_an_app_without_texts_serves_the_empty_defaults(self):
        class Bare(App):
            def __init__(self, store):
                super().__init__(store)
                del self.product
        self.assertEqual(self.serve(Bare)["product"], fixed(**EMPTY))


class ServerStartupTests(unittest.TestCase):
    def start(self, config_text, code="import sys; from folio.web import main; main(sys.argv[1:])"):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        (root / "config" / "folio").mkdir(parents=True)
        (root / "config" / "folio" / "config.json").write_text(config_text, encoding="utf-8")
        workspace = root / "workspace"
        env = {"HOME": str(root), "XDG_CONFIG_HOME": str(root / "config"), "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
               "PYTHONDONTWRITEBYTECODE": "1", "LANG": "C.UTF-8"}
        return subprocess.run([sys.executable, "-B", "-c", code, "--port", "0", "--data-dir", str(workspace)],
                              cwd=str(REPO_ROOT), env=env, stdin=subprocess.DEVNULL, capture_output=True,
                              text=True, timeout=30)

    def build(self, config_text):
        """build_app() in a subprocess with this local config; prints the app's About texts."""
        code = ("import json, sys; from folio.api import build_app; from folio.core import Store; "
                "app = build_app(Store(sys.argv[-1])); print(json.dumps(app.product)); app.close()")
        return self.start(config_text, code)

    def test_build_app_takes_the_texts_from_the_local_config(self):
        result = self.build(json.dumps({"about": VALID, "plugins": {}}))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), fixed(**VALID))

    def test_build_app_without_about_has_empty_texts(self):
        result = self.build("{}")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), fixed(**EMPTY))

    def test_bad_about_config_exits_2_with_one_line(self):
        for text in ('{"about": {"website": "javascript:alert(1)"}}', '{"about": ["x"]}', '{"about": {"colour": "red"}}'):
            with self.subTest(config=text):
                result = self.start(text)
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertEqual(result.stdout, "")
                lines = result.stderr.splitlines()
                self.assertEqual(len(lines), 1, result.stderr)
                self.assertTrue(lines[0].startswith("folio-server: "), lines[0])
                self.assertNotIn("Traceback", result.stderr)


class StaticBrandTests(unittest.TestCase):
    def test_about_panel_shows_each_text_only_when_set(self):
        app = (STATIC / "app.js").read_text(encoding="utf-8")
        for key, css in (("attribution", "about-attribution"), ("website", "about-website"), ("help_url", "about-help")):
            with self.subTest(key=key):
                self.assertRegex(app, r"product\.%s \?[^:]*%s" % (key, css))
        self.assertNotRegex(app, r"[a-z-]+\.com</a>", "no fixed website name as link text")

    def test_brand_title_and_manifest_are_generic(self):
        app = (STATIC / "app.js").read_text(encoding="utf-8")
        self.assertIn('class="brand" href="#/portfolio//overview" aria-label="Folio home" title="Folio">', app)
        manifest = json.loads((STATIC / "manifest.webmanifest").read_text(encoding="utf-8"))
        self.assertEqual((manifest["name"], manifest["short_name"]), ("Folio", "Folio"))
        self.assertEqual(manifest["description"], "Folio, a local planning workspace")

    def test_no_organisation_placeholder_in_product_surfaces(self):
        for rel in ("folio/web.py", "folio/api.py", "folio/static/app.js", "folio/static/manifest.webmanifest",
                    "folio/static/styles.css", "folio/static/index.html", "pyproject.toml"):
            with self.subTest(file=rel):
                text = (REPO_ROOT / rel).read_text(encoding="utf-8").lower()
                for word in ("example org", "example-org", "originally developed"):
                    self.assertNotIn(word, text)

    def test_pyproject_metadata_is_generic(self):
        text = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
        self.assertNotIn("[project.urls]", text)
        self.assertIsNone(re.search(r"(?im)^\s*(authors|maintainers)\s*=", text))
        description = re.search(r'(?m)^description = "([^"]*)"$', text).group(1)
        self.assertEqual(description, "A local, project-folder-backed planning workspace")


if __name__ == "__main__":
    unittest.main()
