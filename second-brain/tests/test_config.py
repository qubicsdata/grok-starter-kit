"""The config loader: the stdlib YAML-subset parser, the `second_brain:` block of
kit.config.yaml, the file lookup order, SB_HOME, ${VAR} expansion, defaults
equal to kit.config.example.yaml, validation errors."""

import os
import tempfile
import unittest

import sbsupport
from sbsupport import DEFAULT_CHANNELS, DEFAULT_DOCTOR, SETTINGS_KEYS, SbCase


def sb():
    return sbsupport.load_sb()


class ParserTest(unittest.TestCase):
    def setUp(self):
        self.sb = sb()

    def parse(self, text):
        return self.sb.parse_config_text(text)

    def test_example_config_parses(self):
        with open(sbsupport.EXAMPLE_CONFIG, encoding="utf-8") as fh:
            data = self.parse(fh.read())
        block = data["second_brain"]
        self.assertEqual(block["home"], "${HOME}/second-brain")
        self.assertEqual(block["router_file"], "ROUTER.md")
        self.assertEqual(block["channels"], DEFAULT_CHANNELS)
        self.assertEqual(block["roots"], ["."])
        self.assertEqual(block["raw_roots"], [])
        self.assertEqual(block["path_defaults"], {
            "dance-school/": "dance-school", "other-activities/": "other-activities"})
        self.assertEqual(block["name_hashes"], {})
        self.assertEqual(block["doctor"], DEFAULT_DOCTOR)
        self.assertEqual(block["marketing_links"], {})
        # the rest of the file parses too (sb ignores it)
        self.assertEqual(data["kit"]["collision_suffix"], "-kit")
        self.assertEqual(data["kit"]["homepage"], "")
        self.assertEqual(data["routines"]["morning_brief"]["time"], "07:30")
        self.assertIs(data["routines"]["morning_brief"]["weekdays_only"], True)
        self.assertEqual(data["agents"]["dev_lead"]["sizing_interval_hours"], 4)
        self.assertEqual(data["accelerator"]["plugins"], ["ai-baseline", "content-companion"])

    def test_example_config_lists_every_key_sb_reads(self):
        with open(sbsupport.EXAMPLE_CONFIG, encoding="utf-8") as fh:
            block = self.parse(fh.read())["second_brain"]
        for key in ("home", "router_file", "channels", "roots", "raw_roots",
                    "path_defaults", "name_hashes", "boost_paths", "doctor"):
            with self.subTest(key=key):
                self.assertIn(key, block)
        self.assertEqual(block["boost_paths"], [])

    def test_scalars(self):
        data = self.parse(
            'a: "quoted # not a comment"   # a comment\n'
            "b: 'single ''quote'''\n"
            'c: "esc \\" and \\\\"\n'
            "d: plain words\n"
            "e: true\n"
            "f: false\n"
            "g: 42\n"
            "h: 07:30\n"
            'i: ""\n'
            "j: plain # trailing comment\n"
        )
        self.assertEqual(data, {
            "a": "quoted # not a comment", "b": "single 'quote'", "c": 'esc " and \\',
            "d": "plain words", "e": True, "f": False, "g": 42, "h": "07:30", "i": "",
            "j": "plain",
        })

    def test_collections(self):
        data = self.parse(
            "# full-line comment\n"
            "top:\n"
            "  flow: [a, \"b, c\", 'd']\n"
            "  empty_list: []\n"
            "  empty_map: {}\n"
            "  inline_map: {\"k/\": \"v\"}\n"
            "  block:\n"
            "    - one\n"
            "    - \"two # kept\"\n"
            "\n"
            "  nested:\n"
            "    \"x/y/\": \"z\"\n"
            "    deeper:\n"
            "      flag: true\n"
            "after: 1\n"
        )
        self.assertEqual(data, {
            "top": {
                "flow": ["a", "b, c", "d"], "empty_list": [], "empty_map": {},
                "inline_map": {"k/": "v"}, "block": ["one", "two # kept"],
                "nested": {"x/y/": "z", "deeper": {"flag": True}},
            },
            "after": 1,
        })

    def test_key_order_is_kept(self):
        data = self.parse("m:\n  \"b/\": \"1\"\n  \"a/\": \"2\"\n  \"c/\": \"3\"\n")
        self.assertEqual(list(data["m"]), ["b/", "a/", "c/"])

    def test_malformed_input_is_a_config_error(self):
        cases = {
            "tab indent": "a:\n\tb: 1\n",
            "unterminated double quote": 'a: "open\n',
            "unterminated single quote": "a: 'open\n",
            "unterminated flow list": "a: [x, y\n",
            "block scalar": "a: |\n  text\n",
            "folded scalar": "a: >-\n  text\n",
            "anchor": "a: &x 1\n",
            "alias": "a: *x\n",
            "bad dedent": "a:\n    b: 1\n  c: 2\n",
            "orphan indent": "a: 1\n  b: 2\n",
            "duplicate key": "a: 1\na: 2\n",
            "no colon": "just text\n",
            "list item at top": "- a\n",
        }
        for label, text in cases.items():
            with self.subTest(case=label):
                with self.assertRaises(self.sb.ConfigError):
                    self.parse(text)


class LoadSettingsTest(unittest.TestCase):
    def setUp(self):
        self.sb = sb()
        self.tmp = tempfile.mkdtemp(prefix="sb-cfg-")
        self.addCleanup(__import__("shutil").rmtree, self.tmp, True)
        self.home = os.path.join(self.tmp, "home")
        os.makedirs(self.home)

    def write(self, rel, text):
        path = os.path.join(self.tmp, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
        return path

    def load(self, path=None, **env):
        environ = {"HOME": self.home}
        environ.update(env)
        return self.sb.load_settings(path, environ)

    def expected_defaults(self):
        return {
            "home": os.path.join(self.home, "second-brain"),
            "router_file": "ROUTER.md",
            "channels": DEFAULT_CHANNELS,
            "roots": ["."],
            "raw_roots": [],
            "path_defaults": {"dance-school/": "dance-school", "other-activities/": "other-activities"},
            "name_hashes": {},
            "boost_paths": [],
            "doctor": DEFAULT_DOCTOR,
        }

    def strip(self, settings):
        self.assertEqual(set(settings), SETTINGS_KEYS)
        return {k: v for k, v in settings.items() if k != "config_path"}

    def test_no_config_file_gives_the_defaults(self):
        settings = self.load()
        self.assertIsNone(settings["config_path"])
        self.assertEqual(self.strip(settings), self.expected_defaults())

    def test_defaults_equal_the_example_config(self):
        with open(sbsupport.EXAMPLE_CONFIG, encoding="utf-8") as fh:
            path = self.write("cfg/kit.config.yaml", fh.read())
        settings = self.load(path)
        self.assertEqual(settings["config_path"], path)
        self.assertEqual(self.strip(settings), self.expected_defaults())

    def test_missing_second_brain_block_gives_the_defaults(self):
        path = self.write("kit.config.yaml", "kit:\n  timezone: \"UTC\"\n")
        self.assertEqual(self.strip(self.load(path)), self.expected_defaults())

    def test_partial_block_derives_path_defaults_from_channels(self):
        path = self.write("kit.config.yaml", "second_brain:\n  channels: [studio, garden]\n")
        settings = self.load(path)
        self.assertEqual(settings["channels"], ["studio", "garden"])
        self.assertEqual(settings["path_defaults"], {"studio/": "studio", "garden/": "garden"})
        self.assertEqual(settings["roots"], ["."])
        self.assertEqual(settings["name_hashes"], {})
        self.assertEqual(settings["doctor"], DEFAULT_DOCTOR)

    def test_values_from_config(self):
        hashed = sbsupport.name_hash("examplestudio")
        path = self.write("kit.config.yaml", (
            "second_brain:\n"
            "  home: \"/home/user/notes\"\n"
            "  router_file: \"INDEX.md\"\n"
            "  channels: [\"studio\", \"garden\"]\n"
            "  roots: [\"studio\", \"garden\", \"shared\"]\n"
            "  raw_roots: [\"archive\"]\n"
            "  path_defaults:\n"
            "    \"school/\": \"studio\"\n"
            "    \"garden/\": \"garden\"\n"
            "  name_hashes:\n"
            "    \"%s\": \"studio\"\n"
            "  boost_paths: [\"studio/knowledge\"]\n"
            "  doctor:\n"
            "    fail_on_folder_mismatch: false\n"
        ) % hashed)
        settings = self.load(path)
        self.assertEqual(settings["home"], "/home/user/notes")
        self.assertEqual(settings["router_file"], "INDEX.md")
        self.assertEqual(settings["channels"], ["studio", "garden"])
        self.assertEqual(settings["roots"], ["studio", "garden", "shared"])
        self.assertEqual(settings["raw_roots"], ["archive"])
        self.assertEqual(list(settings["path_defaults"].items()),
                         [("school/", "studio"), ("garden/", "garden")])
        self.assertEqual(settings["name_hashes"], {hashed: "studio"})
        self.assertEqual(settings["boost_paths"], ["studio/knowledge"])
        doctor = dict(DEFAULT_DOCTOR, fail_on_folder_mismatch=False)
        self.assertEqual(settings["doctor"], doctor)

    def test_home_expansion(self):
        path = self.write("kit.config.yaml", "second_brain:\n  home: \"${HOME}/my-notes\"\n")
        self.assertEqual(self.load(path)["home"], os.path.join(self.home, "my-notes"))
        path = self.write("kit.config.yaml", "second_brain:\n  home: \"~/tilde-notes\"\n")
        self.assertEqual(self.load(path)["home"], os.path.join(self.home, "tilde-notes"))

    def test_kit_home_expansion_falls_back_to_kit_home_key(self):
        path = self.write("kit.config.yaml", (
            "kit:\n  home: \"${HOME}/kits/k1\"\n"
            "second_brain:\n  home: \"${KIT_HOME}/notes\"\n"))
        self.assertEqual(self.load(path)["home"], os.path.join(self.home, "kits", "k1", "notes"))
        other = os.path.join(self.tmp, "elsewhere")
        self.assertEqual(self.load(path, KIT_HOME=other)["home"], os.path.join(other, "notes"))

    def test_unset_variable_is_a_config_error(self):
        path = self.write("kit.config.yaml", "second_brain:\n  home: \"${EXAMPLE_UNSET_VAR}/notes\"\n")
        with self.assertRaises(self.sb.ConfigError):
            self.load(path)

    def test_relative_home_is_relative_to_the_config_folder(self):
        path = self.write("cfg/kit.config.yaml", "second_brain:\n  home: \"notes\"\n")
        self.assertEqual(self.load(path)["home"], os.path.join(self.tmp, "cfg", "notes"))

    def test_sb_home_env_wins(self):
        path = self.write("kit.config.yaml", "second_brain:\n  home: \"/home/user/notes\"\n")
        target = os.path.join(self.tmp, "override")
        self.assertEqual(self.load(path, SB_HOME=target)["home"], target)
        self.assertEqual(self.load(SB_HOME=target)["home"], target)

    def test_lookup_order(self):
        explicit = self.write("a/kit.config.yaml", "second_brain:\n  channels: [from-explicit]\n")
        env_file = self.write("b/kit.config.yaml", "second_brain:\n  channels: [from-env]\n")
        kit_home = os.path.join(self.tmp, "kit")
        self.write("kit/kit.config.yaml", "second_brain:\n  channels: [from-kit-home]\n")
        self.write("home/grok-kit/kit.config.yaml", "second_brain:\n  channels: [from-home]\n")

        def channels(path=None, **env):
            return self.load(path, **env)["channels"]

        self.assertEqual(channels(explicit, KIT_CONFIG=env_file, KIT_HOME=kit_home), ["from-explicit"])
        self.assertEqual(channels(KIT_CONFIG=env_file, KIT_HOME=kit_home), ["from-env"])
        self.assertEqual(channels(KIT_HOME=kit_home), ["from-kit-home"])
        self.assertEqual(channels(), ["from-home"])

    def test_explicit_missing_file_is_a_config_error(self):
        missing = os.path.join(self.tmp, "nope", "kit.config.yaml")
        with self.assertRaises(self.sb.ConfigError):
            self.load(missing)
        with self.assertRaises(self.sb.ConfigError):
            self.load(KIT_CONFIG=missing)

    def test_invalid_values_are_config_errors(self):
        cases = {
            "empty channels": "  channels: []\n",
            "duplicate channel": "  channels: [a, a]\n",
            "channel with plus": "  channels: [\"a+b\"]\n",
            "channel with space": "  channels: [\"a b\"]\n",
            "channel with comma": "  channels: [\"a,b\"]\n",
            "channel with slash": "  channels: [\"a/b\"]\n",
            "channels not a list": "  channels: \"a\"\n",
            "roots not a list": "  roots: \".\"\n",
            "path default to unknown channel": "  path_defaults:\n    \"x/\": \"nowhere\"\n",
            "name hash to unknown channel": "  name_hashes:\n    \"0123456789abcdef\": \"nowhere\"\n",
            "name hash not 16 hex": "  name_hashes:\n    \"xyz\": \"dance-school\"\n",
            "doctor flag not a bool": "  doctor:\n    fail_on_untagged: \"yes\"\n",
            "unknown doctor flag": "  doctor:\n    fail_on_everything: true\n",
            "boost_paths not a list": "  boost_paths: \"x\"\n",
        }
        for label, body in cases.items():
            with self.subTest(case=label):
                path = self.write("kit.config.yaml", "second_brain:\n" + body)
                with self.assertRaises(self.sb.ConfigError):
                    self.load(path)


class ConfigCliTest(SbCase):
    def setUp(self):
        super().setUp()
        self.write_tree(sbsupport.clean_brain())

    def test_explicit_missing_config_exits_2(self):
        code, out, err = self.run_sb(["timetable"], config=os.path.join(self.tmp, "missing.yaml"))
        self.assertEqual(code, 2)
        self.assertEqual(out, "")
        self.assertTrue(err.startswith("sb: "), "one generic line on stderr")

    def test_malformed_config_exits_2_without_echoing_it(self):
        sentinel = "example-sentinel-value-7f3a"
        self.write_config(raw="second_brain:\n  home: \"%s\n\tchannels: [x]\n" % sentinel)
        for args in (["timetable"], ["--doctor"]):
            with self.subTest(args=args):
                code, out, err = self.run_sb(args)
                self.assertEqual(code, 2)
                self.assertNotIn(sentinel, out + err)
                self.assertEqual(len(err.strip().splitlines()), 1)

    def test_kit_config_env_is_used(self):
        self.write_config({"channels": ["studio", "garden"]})
        code, out, _ = self.run_sb(["--help"], config=False, KIT_CONFIG=self.config_path)
        self.assertEqual(code, 0)
        self.assertIn("studio|garden", out)

    def test_sb_home_env_overrides_config_home(self):
        other = self._mkdir("other-brain")
        self.write("other-activities/unique-sbhome-note.md",
                   sbsupport.note("other-activities", ["other-activities"], body="zebracrossing\n"),
                   root=other)
        self.write_config()
        code, out, _ = self.run_sb(["zebracrossing", "--engine", "python"], SB_HOME=other)
        self.assertEqual(code, 0)
        self.assertEqual(self.result_paths(out), ["other-activities/unique-sbhome-note.md"])


if __name__ == "__main__":
    unittest.main()
