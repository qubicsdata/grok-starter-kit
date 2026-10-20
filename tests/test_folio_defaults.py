"""The kit's Folio defaults (`folio.*` in kit.config.example.yaml) and the Folio behaviour behind each one.

Every default is off: Folio itself (`enabled`), external task sync (`task_sync`), the channel profile
(`machine_profile: none`), the migration allow-list (empty) and the About texts (empty). The Folio
checks run the vendored code in a subprocess with a temp HOME and XDG dirs, so they never read or
write the caller's Folio config. When a later Folio adds a setting the kit maps (sync, a channel
profile, an allow-list), the drift checks here fail and name the kit key to wire. Stdlib only.
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FOLIO = os.path.join(ROOT, "vendor", "folio")
CONFIG_EXAMPLE = os.path.join(ROOT, "kit.config.example.yaml")
PARAMETERS = os.path.join(ROOT, "PARAMETERS.md")
KIT_README = os.path.join(FOLIO, "KIT-README.md")
EXTERNAL = os.path.join(ROOT, "EXTERNAL-DEPENDENCIES.md")

EXPECTED = {
    "enabled": False,
    "source": "${KIT_HOME}/vendor/folio",
    "data_dir": "",
    "task_sync": False,
    "machine_profile": "none",
    "migration_allow_list": "",
    "backlog_version": "1.53.0",
    "about": {"attribution": "", "website": "", "help_url": ""},
}


def read(path):
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def scalar(text):
    """A YAML scalar as the example config writes them: quoted string, true/false or a bare word."""
    text = text.strip()
    if text.startswith('"'):
        end = text.index('"', 1)
        return text[1:end]
    text = text.split("#", 1)[0].strip()
    return {"true": True, "false": False}.get(text, text)


def folio_block(text):
    """The `folio:` mapping of the example config (two levels deep), parsed without a YAML library."""
    lines = text.splitlines()
    start = lines.index("folio:")
    block, current = {}, None
    for line in lines[start + 1:]:
        if line and not line.startswith(" "):
            break
        match = re.match(r"^( +)([a-z_]+):(.*)$", line)
        if not match:
            continue
        indent, key, rest = len(match.group(1)), match.group(2), match.group(3)
        value = rest.split("#", 1)[0].strip() if not rest.strip().startswith('"') else rest
        if indent == 2:
            if value == "":
                block[key] = current = {}
            else:
                block[key], current = scalar(rest), None
        elif indent == 4 and current is not None:
            current[key] = scalar(rest)
    return block


def flat_keys(block, prefix="folio."):
    keys = []
    for key, value in block.items():
        if isinstance(value, dict):
            keys += flat_keys(value, prefix + key + ".")
        else:
            keys.append(prefix + key)
    return keys


def run_folio(code):
    """Run `code` with the vendored Folio importable, in a temp HOME and XDG dirs; return its JSON output."""
    home = tempfile.mkdtemp(prefix="kit-folio-home-")
    try:
        env = {"HOME": home, "XDG_CONFIG_HOME": os.path.join(home, "config"),
               "XDG_DATA_HOME": os.path.join(home, "data"), "XDG_STATE_HOME": os.path.join(home, "state"),
               "PATH": os.environ.get("PATH", "/usr/bin:/bin"), "LANG": "C.UTF-8", "PYTHONDONTWRITEBYTECODE": "1"}
        proc = subprocess.run([sys.executable, "-B", "-c", code], cwd=FOLIO, env=env, stdin=subprocess.DEVNULL,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True, timeout=120)
        if proc.returncode != 0:
            raise AssertionError("folio probe exited %d: %s" % (proc.returncode, proc.stderr[-2000:]))
        result = json.loads(proc.stdout.strip().splitlines()[-1])
        result["_home"] = home
        result["_left"] = sorted(os.listdir(home))
        return result
    finally:
        shutil.rmtree(home, ignore_errors=True)


def package_sources():
    for top in ("folio", "folio_ollama"):
        for dirpath, dirnames, filenames in os.walk(os.path.join(FOLIO, top)):
            dirnames[:] = [d for d in dirnames if d != "__pycache__"]
            for name in sorted(filenames):
                if name.endswith((".py", ".js", ".html")):
                    path = os.path.join(dirpath, name)
                    yield os.path.relpath(path, FOLIO), read(path)


class KitConfigDefaultsTest(unittest.TestCase):
    def test_folio_block_has_exactly_the_off_defaults(self):
        self.assertEqual(folio_block(read(CONFIG_EXAMPLE)), EXPECTED)

    def test_parser_reads_planted_values(self):
        text = 'folio:\n  enabled: true   # on\n  machine_profile: "laptop"  # x\n  about:\n    website: "https://example.com/"\nrunner:\n  enabled: false\n'
        self.assertEqual(folio_block(text), {"enabled": True, "machine_profile": "laptop",
                                             "about": {"website": "https://example.com/"}})

    def covered_keys(self):
        """Keys named in the Key cell of the folio rows; `folio.a.b` / `c` also covers `folio.a.c`."""
        covered = set()
        for line in read(PARAMETERS).splitlines():
            if not line.startswith("| `folio."):
                continue
            names = re.findall(r"`([a-z_.]+)`", line.split("|")[1])
            parent = names[0].rsplit(".", 1)[0]
            covered.update(name if name.startswith("folio.") else parent + "." + name for name in names)
        return covered

    def test_every_folio_key_has_a_parameters_row(self):
        covered = self.covered_keys()
        for key in flat_keys(EXPECTED):
            with self.subTest(key=key):
                self.assertIn(key, covered, "no PARAMETERS.md row for " + key)

    def test_parameters_rows_state_the_off_defaults(self):
        rows = {line.split("|")[1].strip(): line for line in read(PARAMETERS).splitlines() if line.startswith("| `folio.")}
        self.assertIn("`false`", rows["`folio.task_sync`"])
        self.assertIn("`none`", rows["`folio.machine_profile`"])
        self.assertIn("empty (off)", rows["`folio.migration_allow_list`"])
        about = [row for key, row in rows.items() if key.startswith("`folio.about.")]
        self.assertEqual(len(about), 1, "one row for the About texts")
        self.assertIn("empty", about[0])

    def test_backlog_version_matches_folio_and_the_pin(self):
        tools = read(os.path.join(FOLIO, "folio", "backlog", "tools.py"))
        pinned = re.search(r'(?m)^BACKLOG_VERSION = "([^"]+)"$', tools).group(1)
        self.assertEqual(pinned, EXPECTED["backlog_version"])
        self.assertIn("| Backlog.md | %s |" % pinned, read(EXTERNAL))


class FolioBehindTheDefaultsTest(unittest.TestCase):
    """What Folio does when the kit writes no Folio config at all (every kit default)."""

    def test_no_local_config_enables_no_plugin_and_creates_no_file(self):
        out = run_folio(
            "import json\n"
            "from folio.plugins import default_config_path, load_from_config\n"
            "host = load_from_config()\n"
            "path = default_config_path()\n"
            "print(json.dumps({'plugins': sorted(host.plugins), 'path': str(path), 'exists': path.exists()}))\n")
        self.assertEqual(out["plugins"], [])
        self.assertEqual(out["path"], os.path.join(out["_home"], "config", "folio", "config.json"))
        self.assertFalse(out["exists"])
        self.assertEqual(out["_left"], [], "Folio wrote into HOME without being asked")

    def test_about_texts_are_empty_without_config(self):
        out = run_folio(
            "import json\nfrom folio.web import product_info\nprint(json.dumps(product_info({})))\n")
        self.assertEqual({k: out[k] for k in EXPECTED["about"]}, EXPECTED["about"])

    def test_empty_data_dir_means_the_folio_default(self):
        out = run_folio(
            "import json, os\nfrom folio.core import resolve_workspace\nfrom folio.paths import default_workspace\n"
            "print(json.dumps({'empty': resolve_workspace('', os.environ), 'default': str(default_workspace(os.environ))}))\n")
        self.assertEqual(out["empty"], out["default"])
        self.assertEqual(out["default"], os.path.join(out["_home"], "data", "folio", "workspace"))

    def commands(self):
        out = run_folio(
            "import argparse, json\nfrom folio.cli import build_parser\n"
            "parser = build_parser()\n"
            "sub = [a for a in parser._actions if isinstance(a, argparse._SubParsersAction)][0]\n"
            "def names(p):\n"
            "    subs = [a for a in p._actions if isinstance(a, argparse._SubParsersAction)]\n"
            "    return {k: names(v) for k, v in subs[0].choices.items()} if subs else {}\n"
            "print(json.dumps({'commands': names(parser)}))\n")
        return out["commands"]

    def test_task_sync_has_no_code_path(self):
        # folio.task_sync: false needs no Folio setting: the Switchboard integration is removed and
        # git sync (WP-10) is not in this tree. A Folio that adds one must be wired to folio.task_sync.
        commands = self.commands()
        self.assertTrue(commands, "no CLI commands found; the probe is broken")
        for name in ("sync", "repos", "repair-ids", "proposals", "decisions"):
            with self.subTest(command=name):
                self.assertNotIn(name, commands, "Folio gained `%s`: map it to folio.task_sync (off)" % name)
        self.assertIn("projects", commands)
        for name in ("link", "unlink"):
            with self.subTest(command="projects " + name):
                self.assertNotIn(name, commands["projects"], "project linking is back: map it to folio.task_sync (off)")
        names = [rel for rel, _ in package_sources()]
        self.assertFalse([n for n in names if re.search(r"(^|/)(sync|switchboard)[^/]*$", n)], "a sync module appeared")

    def test_frozen_integration_name_is_reserved(self):
        out = run_folio(
            "import json\nfrom folio.core import FROZEN\nfrom folio.plugins import PluginError, check_name\n"
            "try:\n    check_name(FROZEN)\n    refused = False\nexcept PluginError:\n    refused = True\n"
            "print(json.dumps({'refused': refused}))\n")
        self.assertTrue(out["refused"])

    def test_no_channel_profile_in_this_folio(self):
        # folio.machine_profile: none is Folio's behaviour today: nothing reads a profile.
        hits = [rel for rel, text in package_sources() if "machine_profile" in text]
        self.assertEqual(hits, [], "Folio reads machine_profile now: map folio.machine_profile (default none)")

    def test_no_migration_allow_list_in_this_folio(self):
        # folio.migration_allow_list: empty is Folio's behaviour today: no allow-list reader, no `migrate`.
        hits = [rel for rel, text in package_sources() if re.search(r"allow[_-]?list", text)]
        self.assertEqual(hits, [], "Folio reads an allow-list now: map folio.migration_allow_list (default empty)")
        self.assertNotIn("migrate", self.commands())


class KitReadmeTest(unittest.TestCase):
    def test_every_key_and_its_folio_side_is_documented(self):
        text = read(KIT_README)
        for key in flat_keys(EXPECTED):
            with self.subTest(key=key):
                self.assertIn("`%s`" % key, text)
        for needle in ("$XDG_CONFIG_HOME/folio/config.json", "Switchboard", "--with-folio", "FOLIO_BACKLOG_BIN",
                       "FOLIO_BACKLOG_CONTRACT=skip", "--data-dir"):
            with self.subTest(needle=needle):
                self.assertIn(needle, text)

    def test_kit_readme_has_no_fenced_commands(self):
        # Folio's docs inventory requires a doc-test row for every fenced command in its Markdown.
        self.assertNotIn("```", read(KIT_README))


if __name__ == "__main__":
    unittest.main()
