"""The config loader fills ${KIT_HOME} / ${KIT_TZ} (env first, then kit.config.yaml) in every path key of
the parameterization table, keeps the CR_* overrides, and fails closed: an unresolvable or unknown placeholder is an error, never
a built-in path. Contract (crlib/common.load_config):
  * KIT_HOME: env KIT_HOME, else `kit.home` of <KIT_HOME>/kit.config.yaml found next to the config
    (${KIT_HOME}/runner/router.json -> ${KIT_HOME}/kit.config.yaml; `${HOME}` and `~` expanded there); must be
    absolute; trailing slashes normalized; the value is used literally (no shell or $VAR expansion inside it).
  * KIT_TZ: env KIT_TZ (empty = unset), else `kit.timezone`, else "UTC".
  * Any other ${...} in a config value, or ${KIT_HOME} with no KIT_HOME, raises a ValueError naming the key.
  * With CR_CONFIG unset, the config is ${KIT_HOME}/runner/router.json."""
import os, unittest
import k5support as K
from k5support import TempEnv, KIT_HOME_KEYS, CR_OVERRIDES
from crlib import common, sched as S
from crlib.common import to_epoch


def kit_config_yaml(home=None, tz=None, decoy=True):
    lines = ["# Starter-kit config (test copy). Every value is synthetic."]
    if decoy:  # another section with the same key names, before `kit:`
        lines += ["second_brain:", '  home: "/home/user/example-notes"   # not KIT_HOME', '  timezone: "Etc/GMT-9"']
    lines.append("kit:")
    if home is not None:
        lines.append('  home: "%s"            # KIT_HOME: where this kit lives on your box' % home)
    if tz is not None:
        lines.append('  timezone: "%s"                     # KIT_TZ: set your own' % tz)
    lines += ['  author_name: "<your-name>"', "", "runner:", "  enabled: false"]
    return "\n".join(lines) + "\n"


class LoaderCase(unittest.TestCase):
    """A temp KIT_HOME whose runner/router.json is the RAW example (placeholders not filled in)."""
    def setUp(self):
        self.t = TempEnv().__enter__()
        self.d = self.t.d
        for k in CR_OVERRIDES + ("KIT_HOME", "KIT_TZ", "CR_NOW"):
            os.environ.pop(k, None)
        self.example = K.raw_example()
        self.raw = os.path.join(self.d, "runner", "router.json")
        K.write_json(self.raw, self.example)

    def tearDown(self):
        self.t.__exit__()

    def load(self, path=None):
        """load_config(path); any exception is a test failure (red = FAIL, never ERROR)."""
        try:
            return common.load_config(path or self.raw)
        except Exception as e:  # noqa: BLE001
            self.fail("load_config raised %s: %s" % (type(e).__name__, e))

    def load_refused(self, *must_name):
        try:
            common.load_config(self.raw)
        except ValueError as e:
            for n in must_name:
                self.assertIn(n, str(e))
            return
        except Exception as e:  # noqa: BLE001
            self.fail("expected a ValueError naming %s, got %s" % (must_name, type(e).__name__))
        self.fail("load_config accepted the config; expected a ValueError naming %s" % (must_name,))

    def want(self, sect, key, home):
        return self.example[sect][key].replace("${KIT_HOME}", home)

    def write_kit_config(self, text, where=None):
        with open(os.path.join(where or self.d, "kit.config.yaml"), "w") as f:
            f.write(text)


class ExampleTemplateTests(unittest.TestCase):
    def test_every_path_key_of_the_example_uses_kit_home(self):
        ex = K.raw_example()
        found = {(s, k) for s, sec in ex.items() if isinstance(sec, dict) and not s.startswith("_")
                 for k, v in sec.items() if isinstance(v, str) and "${KIT_HOME}" in v}
        self.assertEqual(found, set(KIT_HOME_KEYS))
        for s, k in KIT_HOME_KEYS:
            self.assertTrue(ex[s][k].startswith("${KIT_HOME}/runner/"), "%s.%s" % (s, k))
        self.assertEqual(ex["runner"]["env_file"], "")
        self.assertEqual(ex["backlog"]["quiet_hours"]["tz"], "${KIT_TZ}")
        self.assertIn("${KIT_HOME}/runner/router.json", ex["_comment"])


class KitHomeFromEnvTests(LoaderCase):
    def setUp(self):
        super().setUp()
        os.environ["KIT_HOME"] = self.d
        os.environ["KIT_TZ"] = "Etc/GMT-5"

    def test_every_kit_home_key_is_expanded(self):
        cfg = self.load()
        for sect, key in KIT_HOME_KEYS:
            with self.subTest(key="%s.%s" % (sect, key)):
                self.assertEqual(cfg[sect][key], self.want(sect, key, self.d))

    def test_kit_tz_is_expanded(self):
        self.assertEqual(self.load()["backlog"]["quiet_hours"]["tz"], "Etc/GMT-5")

    def test_nothing_left_unresolved_or_outside_kit_home(self):
        self.assertEqual(K.helpers.check_sandbox(self.load(), self.d), [])

    def test_env_file_stays_empty(self):
        self.assertEqual(self.load()["runner"]["env_file"], "")

    def test_quiet_hours_run_in_the_expanded_tz(self):
        cfg = self.load()
        try:  # Etc/GMT-5 = UTC+5: 22:30Z is 03:30 local (quiet), 03:30Z is 08:30 local (not quiet)
            self.assertTrue(S.in_quiet_hours(cfg, to_epoch("2026-10-18T22:30:00Z")))
            self.assertFalse(S.in_quiet_hours(cfg, to_epoch("2026-10-18T03:30:00Z")))
        except Exception as e:  # noqa: BLE001
            self.fail("in_quiet_hours raised %s" % type(e).__name__)

    def test_trailing_slash_is_normalized(self):
        os.environ["KIT_HOME"] = self.d + "//"
        self.assertEqual(self.load()["paths"]["logs"], os.path.join(self.d, "runner", "logs"))

    def test_kit_home_is_used_literally(self):
        odd = os.path.join(self.d, "kit $HOME dir")
        os.makedirs(odd)
        os.environ["KIT_HOME"] = odd
        self.assertEqual(self.load()["runner"]["pidfile"], self.want("runner", "pidfile", odd))

    def test_cr_overrides_still_win(self):
        os.environ["CR_LOG_DIR"] = os.path.join(self.d, "override-logs")
        os.environ["CR_BACKLOG_STATE"] = os.path.join(self.d, "override-state.json")
        cfg = self.load()
        self.assertEqual(cfg["paths"]["logs"], os.environ["CR_LOG_DIR"])
        self.assertEqual(cfg["backlog"]["state_file"], os.environ["CR_BACKLOG_STATE"])
        self.assertEqual(cfg["paths"]["queue"], self.want("paths", "queue", self.d))

    def test_relative_kit_home_is_refused(self):
        os.environ["KIT_HOME"] = "relative/kit"
        self.load_refused("KIT_HOME")

    def test_unknown_placeholder_is_refused(self):
        self.example["paths"]["logs"] = "${KIT_OTHER}/runner/logs"
        K.write_json(self.raw, self.example)
        self.load_refused("paths.logs")

    def test_default_config_is_kit_home_runner_router_json(self):
        os.environ.pop("CR_CONFIG", None)
        try:
            cfg = common.load_config()
        except Exception as e:  # noqa: BLE001
            self.fail("load_config() without CR_CONFIG raised %s (expected ${KIT_HOME}/runner/router.json)"
                      % type(e).__name__)
        self.assertEqual(cfg["paths"]["logs"], os.path.join(self.d, "runner", "logs"))


class KitHomeFromKitConfigTests(LoaderCase):
    def test_kit_home_and_tz_from_kit_config(self):
        self.write_kit_config(kit_config_yaml(home=self.d, tz="Etc/GMT-7"))
        cfg = self.load()
        self.assertEqual(cfg["runner"]["stop_file"], self.want("runner", "stop_file", self.d))
        self.assertEqual(cfg["backlog"]["quiet_hours"]["tz"], "Etc/GMT-7")

    def test_home_variable_in_kit_home(self):
        # The shipped kit.config.example.yaml writes kit.home as "${HOME}/grok-kit".
        self.write_kit_config(kit_config_yaml(home="${HOME}/grok-kit", tz="UTC"))
        want = os.path.join(os.environ["HOME"], "grok-kit")
        self.assertEqual(self.load()["paths"]["queue"], self.want("paths", "queue", want))

    def test_env_wins_over_kit_config(self):
        other = os.path.join(self.d, "other-kit")
        os.makedirs(other)
        self.write_kit_config(kit_config_yaml(home=other, tz="Etc/GMT-7"))
        os.environ["KIT_HOME"], os.environ["KIT_TZ"] = self.d, "Etc/GMT-2"
        cfg = self.load()
        self.assertEqual(cfg["paths"]["runner"], self.want("paths", "runner", self.d))
        self.assertEqual(cfg["backlog"]["quiet_hours"]["tz"], "Etc/GMT-2")

    def test_tz_defaults_to_utc(self):
        os.environ["KIT_HOME"] = self.d  # no kit.config.yaml, no KIT_TZ
        self.assertEqual(self.load()["backlog"]["quiet_hours"]["tz"], "UTC")

    def test_kit_config_without_timezone_defaults_to_utc(self):
        self.write_kit_config(kit_config_yaml(home=self.d, tz=None))
        self.assertEqual(self.load()["backlog"]["quiet_hours"]["tz"], "UTC")

    def test_empty_kit_tz_env_counts_as_unset(self):
        self.write_kit_config(kit_config_yaml(home=self.d, tz="Etc/GMT-7"))
        os.environ["KIT_TZ"] = ""
        self.assertEqual(self.load()["backlog"]["quiet_hours"]["tz"], "Etc/GMT-7")

    def test_no_kit_home_anywhere_is_refused(self):
        self.load_refused("KIT_HOME")  # no env, no kit.config.yaml: never a built-in path

    def test_kit_config_without_kit_home_is_refused(self):
        self.write_kit_config(kit_config_yaml(home=None, tz="UTC"))
        self.load_refused("KIT_HOME")

    def test_config_without_placeholders_needs_no_kit_home(self):
        K.write_json(self.raw, K.helpers._subst(self.example, self.d))
        cfg = self.load()
        self.assertEqual(cfg["paths"]["logs"], os.path.join(self.d, "runner", "logs"))
        self.assertEqual(cfg["backlog"]["quiet_hours"]["tz"], K.helpers.TEST_TZ)


if __name__ == "__main__":
    unittest.main()
