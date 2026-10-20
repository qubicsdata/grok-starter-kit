"""The scan key behind second_brain.name_hashes.

A name hash is the first 16 hex chars of HMAC-SHA256(scan key, folded word),
so a word list does not reverse it without the key. `sb --init-key` creates
the key (32 random bytes) as <XDG_CONFIG_HOME or ~/.config>/grok-kit/scan.key,
file 0600 in a 0700 folder; `sb --hash-name` prints the hashes of the words on
stdin. With name_hashes configured, a missing or unusable key fails closed
(exit 2, with the command that creates it); there is no unkeyed fallback. The
key bytes never appear in any output.

Every key here is synthetic and lives in the test's temp folder: HOME and
XDG_CONFIG_HOME of every sb run point into it (sbsupport asserts that), so
the real key of the box is never read or created."""

import base64
import hashlib
import os
import stat
import unittest

import sbsupport
from sbsupport import FIXTURE_KEY, INIT_KEY_HINT, SbCase, name_hash, note, unkeyed_hash

# Synthetic channel words; a word list an attacker could try includes them.
WORD = "examplestudio"
WORD_LIST = [WORD, "quokkaclub", "walrusgate", "sampleacademy", "fictionalarts", "placeholderhall"] + [
    "word%04d" % i for i in range(2000)]
OTHER_KEY = hashlib.sha256(b"sb synthetic second scan key").digest()


def key_forms(key):
    """The ways key bytes could leak into an output."""
    return [key, key.hex().encode(), key.hex().upper().encode(), base64.b64encode(key),
            base64.urlsafe_b64encode(key), base64.b32encode(key)]


class KeyCase(SbCase):
    def setUp(self):
        super().setUp()
        self.write_tree(sbsupport.clean_brain())
        self.write("dance-school/classes/b.md", note(WORD) + "\nquokkaword\n")
        self.write_config({"name_hashes": {name_hash(WORD): "dance-school"}})

    def assert_no_key_bytes(self, key, *outputs):
        for data in outputs:
            for form in key_forms(key):
                self.assertNotIn(form, data, "key bytes in an output")

    def assert_fails_closed(self, code, out, err):
        self.assertEqual(code, 2)
        self.assertEqual(out, "", "nothing is searched or checked without the key")
        self.assertIn(INIT_KEY_HINT, err, "the error says how to create the key")
        self.assertEqual(len(err.strip().splitlines()), 1, "one error line")

    def mode(self, path):
        return stat.S_IMODE(os.lstat(path).st_mode)


class KeyedHashTest(KeyCase):
    def test_a_word_list_does_not_reverse_a_keyed_hash_without_the_key(self):
        target = name_hash(WORD)
        guesses = set()
        for word in WORD_LIST:
            guesses.add(unkeyed_hash(word))
            guesses.add(name_hash(word, OTHER_KEY))
            guesses.add(name_hash(word, b""))
            guesses.add(name_hash(word, bytes(32)))
        self.assertNotIn(target, guesses, "reversed without the key")
        # the key is what makes it reversible
        self.assertIn(target, set(name_hash(w) for w in WORD_LIST))

    def test_sb_matches_keyed_hashes(self):
        self.write_scan_key()
        self.assert_clean_doctor()
        code, out, _ = self.run_sb(["quokkaword", "--engine", "python"])
        self.assertEqual(code, 0)
        tags = {m.group("path"): m.group("tag") for m in self.results(out)}
        self.assertEqual(tags, {"dance-school/classes/b.md": "dance-school"})

    def test_old_unkeyed_entries_no_longer_match(self):
        self.write_scan_key()
        self.write_config({"name_hashes": {unkeyed_hash(WORD): "dance-school"}})
        code, out, _ = self.doctor()
        self.assertEqual(code, 3)
        self.assertEqual(self.checks(out, 9), [("FAIL", "dance-school/classes/b.md")])

    def test_another_key_gives_other_hashes(self):
        self.write_scan_key(OTHER_KEY)
        code, out, _ = self.doctor()
        self.assertEqual(code, 3, "a hash made with another key does not match")
        self.assertEqual(self.checks(out, 9), [("FAIL", "dance-school/classes/b.md")])

    def assert_clean_doctor(self):
        code, out, err = self.doctor()
        self.assertEqual((code, err), (0, ""))
        self.assertEqual([l for l in out.splitlines() if not l.startswith("sb doctor:")], [])


class FailClosedTest(KeyCase):
    COMMANDS = [["--doctor"], ["quokkaword", "--engine", "python"], ["quokkaword"]]

    def home_state(self):
        """{relative path: (mode, size, mtime)} of HOME, readable or not."""
        state = {}
        for dirpath, dirnames, filenames in os.walk(self.home):
            for name in dirnames + filenames:
                st = os.lstat(os.path.join(dirpath, name))
                state[os.path.relpath(os.path.join(dirpath, name), self.home)] = (st.st_mode, st.st_size, st.st_mtime_ns)
        return state

    def assert_all_fail_closed(self):
        before = self.home_state()
        for args in self.COMMANDS:
            with self.subTest(args=args):
                self.assert_fails_closed(*self.run_sb(args))
        self.assertEqual(self.home_state(), before, "no key created or changed by search or doctor")

    def test_missing_key(self):
        self.assert_all_fail_closed()
        self.assertFalse(os.path.lexists(os.path.join(self.home, ".config")))

    def test_missing_key_message_names_the_key_file(self):
        _, _, err = self.run_sb(["--doctor"])
        self.assertIn(self.key_path(), err)

    def test_group_or_world_accessible_key(self):
        for mode in (0o640, 0o604, 0o644, 0o620, 0o602, 0o660):
            with self.subTest(mode=oct(mode)):
                self.write_scan_key(file_mode=mode)
                self.assert_all_fail_closed()

    def test_wrong_size_key(self):
        for key in (b"", FIXTURE_KEY[:31], FIXTURE_KEY + b"x", FIXTURE_KEY.hex().encode()):
            with self.subTest(size=len(key)):
                self.write_scan_key(key)
                self.assert_all_fail_closed()

    def test_symlinked_key(self):
        real = self.write_scan_key(path=os.path.join(self.tmp, "elsewhere", "scan.key"))
        os.makedirs(os.path.dirname(self.key_path()), mode=0o700)
        os.symlink(real, self.key_path())
        self.assert_all_fail_closed()
        self.assertIn("symlink", self.run_sb(["--doctor"])[2])

    def test_key_path_is_a_folder(self):
        os.makedirs(self.key_path(), mode=0o700)
        self.assert_all_fail_closed()
        self.assertIn("not a regular file", self.run_sb(["--doctor"])[2])

    @unittest.skipUnless(hasattr(os, "mkfifo"), "no named pipes here")
    def test_key_path_is_a_named_pipe(self):
        """Never blocks on a pipe and refuses it as not a regular file."""
        os.makedirs(os.path.dirname(self.key_path()), mode=0o700)
        os.mkfifo(self.key_path(), 0o600)
        self.assert_all_fail_closed()
        self.assertIn("not a regular file", self.run_sb(["--doctor"])[2])

    @unittest.skipIf(hasattr(os, "geteuid") and os.geteuid() == 0, "root reads a 0000 file")
    def test_unreadable_key(self):
        self.write_scan_key(file_mode=0o000)
        self.assert_all_fail_closed()

    def test_key_in_xdg_config_home_only(self):
        """XDG_CONFIG_HOME wins: a key under ~/.config does not count then."""
        self.write_scan_key()
        xdg = os.path.join(self.tmp, "xdg")
        os.makedirs(xdg)
        for args in self.COMMANDS:
            with self.subTest(args=args):
                self.assert_fails_closed(*self.run_sb(args, XDG_CONFIG_HOME=xdg))
        self.write_scan_key(path=self.key_path(xdg))
        code, _, err = self.run_sb(["--doctor"], XDG_CONFIG_HOME=xdg)
        self.assertEqual((code, err), (0, ""))

    def test_no_key_needed_without_name_hashes(self):
        self.write_config()
        self.write("dance-school/classes/b.md", note("dance-school", ["dance-school"]) + "\nquokkaword\n")
        for args in self.COMMANDS:
            with self.subTest(args=args):
                code, _, err = self.run_sb(args)
                self.assertEqual((code, err), (0, ""))
        self.assertFalse(os.path.lexists(os.path.join(self.home, ".config")))

    def test_help_works_without_the_key(self):
        code, out, _ = self.run_sb(["--help"])
        self.assertEqual(code, 0)
        self.assertIn("--init-key", out)


class InitKeyTest(KeyCase):
    def init_key(self, **kwargs):
        code, out, err = self.run_sb_bytes(["--init-key"], config=False, **kwargs)
        return code, out, err

    def read_key(self, path=None):
        with open(path or self.key_path(), "rb") as fh:
            return fh.read()

    def test_creates_a_0600_key_in_a_0700_folder(self):
        code, out, err = self.init_key()
        self.assertEqual(code, 0, err)
        path = self.key_path()
        self.assertEqual(self.mode(os.path.dirname(path)), 0o700)
        self.assertEqual(self.mode(path), 0o600)
        self.assertTrue(stat.S_ISREG(os.lstat(path).st_mode))
        key = self.read_key()
        self.assertEqual(len(key), 32)
        self.assertEqual(sorted(os.listdir(os.path.dirname(path))), ["scan.key"], "no temp file left")
        self.assert_no_key_bytes(key, out, err)
        self.assertIn(path.encode(), out, "says where the key is")

    def test_modes_hold_under_a_permissive_umask(self):
        code, _, err = self.init_key(umask=0)
        self.assertEqual(code, 0, err)
        self.assertEqual(self.mode(os.path.dirname(self.key_path())), 0o700)
        self.assertEqual(self.mode(self.key_path()), 0o600)

    def test_a_missing_config_folder_is_created_0700(self):
        self.init_key(umask=0)
        self.assertEqual(self.mode(os.path.join(self.home, ".config")), 0o700)

    def test_honours_xdg_config_home(self):
        xdg = os.path.join(self.tmp, "xdg")
        code, _, err = self.init_key(XDG_CONFIG_HOME=xdg)
        self.assertEqual(code, 0, err)
        self.assertEqual(len(self.read_key(self.key_path(xdg))), 32)
        self.assertEqual(self.mode(self.key_path(xdg)), 0o600)
        self.assertFalse(os.path.lexists(os.path.join(self.home, ".config")))

    def test_relative_xdg_config_home_is_ignored(self):
        code, _, err = self.init_key(XDG_CONFIG_HOME="relative/xdg")
        self.assertEqual(code, 0, err)
        self.assertTrue(os.path.isfile(self.key_path()))
        self.assertFalse(os.path.lexists(os.path.join(self.tmp, "relative")))

    def test_keys_are_random(self):
        self.init_key()
        first = self.read_key()
        os.remove(self.key_path())
        self.init_key()
        self.assertNotEqual(self.read_key(), first)

    def test_refuses_to_replace_an_existing_key(self):
        self.write_scan_key()
        code, out, err = self.init_key()
        self.assertEqual(code, 2)
        self.assertEqual(self.read_key(), FIXTURE_KEY)
        self.assertEqual(self.mode(self.key_path()), 0o600)
        self.assertIn(b"already exists", err)
        self.assert_no_key_bytes(FIXTURE_KEY, out, err)

    def test_refuses_a_symlink_at_the_key_path(self):
        os.makedirs(os.path.dirname(self.key_path()), mode=0o700)
        target = os.path.join(self.tmp, "dangling-target")
        os.symlink(target, self.key_path())
        code, _, _ = self.init_key()
        self.assertEqual(code, 2)
        self.assertFalse(os.path.lexists(target), "never writes through a symlink")

    def test_refuses_a_key_folder_open_to_others(self):
        for mode in (0o755, 0o750, 0o705, 0o777):
            with self.subTest(mode=oct(mode)):
                folder = os.path.dirname(self.key_path())
                os.makedirs(folder, exist_ok=True)
                os.chmod(folder, mode)
                code, _, err = self.init_key()
                self.assertEqual(code, 2)
                self.assertIn(b"chmod 700", err)
                self.assertEqual(os.listdir(folder), [], "no key written")
                self.assertEqual(self.mode(folder), mode, "your folder's mode is left alone")

    def test_an_existing_private_folder_is_used(self):
        os.makedirs(os.path.dirname(self.key_path()), mode=0o700)
        with open(os.path.join(os.path.dirname(self.key_path()), "other.yaml"), "w") as fh:
            fh.write("a: 1\n")
        code, _, err = self.init_key()
        self.assertEqual(code, 0, err)
        self.assertEqual(sorted(os.listdir(os.path.dirname(self.key_path()))), ["other.yaml", "scan.key"])

    def test_takes_no_other_arguments(self):
        for args in (["--init-key", "now"], ["--init-key", "--doctor"], ["--init-key", "--hash-name"]):
            with self.subTest(args=args):
                code, _, _ = self.run_sb(args, config=False)
                self.assertEqual(code, 2)
                self.assertFalse(os.path.lexists(self.key_path()))

    def test_works_with_a_broken_config(self):
        """Creating the key does not depend on kit.config.yaml."""
        self.write_config(raw="second_brain: [\n")
        code, _, err = self.run_sb_bytes(["--init-key"])
        self.assertEqual(code, 0, err)
        self.assertTrue(os.path.isfile(self.key_path()))

    def test_end_to_end_init_hash_and_match(self):
        self.init_key()
        code, out, err = self.run_sb(["--hash-name"], config=False, stdin=WORD + "\n")
        self.assertEqual(code, 0, err)
        self.write_config({"name_hashes": {out.strip(): "dance-school"}})
        code, out, err = self.doctor()
        self.assertEqual((code, err), (0, ""), out)


class HashNameTest(KeyCase):
    def hash_names(self, text, **kwargs):
        return self.run_sb(["--hash-name"], config=False, stdin=text, **kwargs)

    def test_prints_the_keyed_hash_of_each_word(self):
        self.write_scan_key()
        code, out, err = self.hash_names("examplestudio\n\nquokkaclub\n")
        self.assertEqual((code, err), (0, ""))
        self.assertEqual(out.splitlines(), [name_hash("examplestudio"), name_hash("quokkaclub")])

    def test_words_are_folded_like_note_values(self):
        self.write_scan_key()
        code, out, _ = self.hash_names("  ÉxampleStudio  \n")
        self.assertEqual(code, 0)
        self.assertEqual(out.splitlines(), [name_hash("examplestudio")])

    def test_never_prints_the_word(self):
        self.write_scan_key()
        code, out, err = self.run_sb_bytes(["--hash-name"], config=False, stdin="examplestudio\n")
        self.assertEqual(code, 0)
        self.assertNotIn(b"examplestudio", out + err)
        self.assert_no_key_bytes(FIXTURE_KEY, out, err)

    def test_a_line_of_several_words_is_refused_without_echoing_it(self):
        self.write_scan_key()
        for line in ("quokkaalpha quokkabeta", "quokkaalpha-quokkabeta", "quokkaalpha_quokkabeta",
                     "quokkaalpha,quokkabeta", "quokkaalpha!"):
            with self.subTest(line=line):
                code, out, err = self.hash_names("examplestudio\n" + line + "\n")
                self.assertEqual(code, 2)
                self.assertEqual(out, "", "nothing printed, not even the valid first line")
                self.assertIn("line 2", err)
                self.assertNotIn("quokka", err)

    def test_needs_the_key(self):
        code, out, err = self.hash_names("examplestudio\n")
        self.assert_fails_closed(code, out, err)
        self.assertFalse(os.path.lexists(self.key_path()), "hashing never creates a key")

    def test_refuses_an_accessible_key(self):
        self.write_scan_key(file_mode=0o644)
        self.assert_fails_closed(*self.hash_names("examplestudio\n"))


class RotationTest(KeyCase):
    def test_rotation_is_re_hashing(self):
        """A new key invalidates every entry; re-hashing the plain words fixes it."""
        self.write_scan_key()
        self.assertEqual(self.doctor()[0], 0)
        os.remove(self.key_path())
        code, _, err = self.run_sb(["--init-key"], config=False)
        self.assertEqual(code, 0, err)
        code, out, _ = self.doctor()
        self.assertEqual(code, 3, "old entries are invalid under the new key")
        self.assertEqual(self.checks(out, 9), [("FAIL", "dance-school/classes/b.md")])
        code, out, _ = self.run_sb(["--hash-name"], config=False, stdin=WORD + "\n")
        self.write_config({"name_hashes": {out.strip(): "dance-school"}})
        self.assertEqual(self.doctor()[0], 0)


class NoKeyBytesTest(KeyCase):
    def test_no_command_prints_the_key(self):
        self.write_scan_key()
        commands = [
            (["--help"], None), (["--doctor"], None), (["quokkaword", "--engine", "python"], None),
            (["--hash-name"], WORD + "\n"), (["--hash-name"], "two words\n"), (["--init-key"], None),
            (["--bogus"], None),
        ]
        for args, stdin in commands:
            with self.subTest(args=args):
                _, out, err = self.run_sb_bytes(args, stdin=stdin)
                self.assert_no_key_bytes(FIXTURE_KEY, out, err)
        self.write_scan_key(file_mode=0o644)
        _, out, err = self.run_sb_bytes(["--doctor"])
        self.assert_no_key_bytes(FIXTURE_KEY, out, err)


class KeyPathTest(unittest.TestCase):
    """scan_key_path in-process: pure path logic, no file is touched."""

    def setUp(self):
        self.sb = sbsupport.load_sb()

    def test_default_under_home(self):
        self.assertEqual(self.sb.scan_key_path({"HOME": "/h"}), "/h/.config/grok-kit/scan.key")

    def test_xdg_config_home_wins(self):
        self.assertEqual(self.sb.scan_key_path({"HOME": "/h", "XDG_CONFIG_HOME": "/x"}), "/x/grok-kit/scan.key")

    def test_empty_or_relative_xdg_is_ignored(self):
        for xdg in ("", "rel/x", "./x"):
            with self.subTest(xdg=xdg):
                self.assertEqual(self.sb.scan_key_path({"HOME": "/h", "XDG_CONFIG_HOME": xdg}),
                                 "/h/.config/grok-kit/scan.key")

    def test_no_home_fails_closed(self):
        for environ in ({}, {"HOME": ""}, {"HOME": "rel"}, {"HOME": "rel", "XDG_CONFIG_HOME": "rel"}):
            with self.subTest(environ=environ):
                with self.assertRaises(self.sb.ScanKeyError) as ctx:
                    self.sb.scan_key_path(environ)
                self.assertIn(INIT_KEY_HINT, str(ctx.exception))


class InProcessGuardTest(unittest.TestCase):
    """An in-process caller (tools/kit_plan.py runs sb.doctor) that passes
    name_hashes without a key gets ScanKeyError, never unkeyed matching."""

    def test_brain_without_a_key_fails_closed(self):
        sb = sbsupport.load_sb()
        settings = sb.load_settings(None, {"HOME": "/nonexistent-home", "SB_HOME": "/nonexistent-brain"})
        sb.Brain(settings)  # no name_hashes: no key needed
        settings["name_hashes"] = {name_hash(WORD): "dance-school"}
        with self.assertRaises(sb.ScanKeyError):
            sb.Brain(settings)
        settings["name_key"] = FIXTURE_KEY
        self.assertEqual(sb.Brain(settings).chans_from_text(WORD), {"dance-school"})
        settings["name_hashes"] = {unkeyed_hash(WORD): "dance-school"}
        self.assertEqual(sb.Brain(settings).chans_from_text(WORD), set())

    def test_name_hash_matches_the_documented_formula(self):
        sb = sbsupport.load_sb()
        self.assertEqual(sb.name_hash(FIXTURE_KEY, WORD), name_hash(WORD))
        self.assertRegex(sb.name_hash(FIXTURE_KEY, WORD), r"^[0-9a-f]{16}$")


class RepoTest(unittest.TestCase):
    def test_scan_key_is_git_ignored(self):
        with open(os.path.join(sbsupport.KIT_ROOT, ".gitignore"), encoding="utf-8") as fh:
            lines = [l.strip() for l in fh]
        self.assertIn("scan.key", lines)

    def test_rotation_and_contract_change_are_documented(self):
        with open(os.path.join(sbsupport.SB_DIR, "bin", "README.md"), encoding="utf-8") as fh:
            text = fh.read()
        for phrase in ("sb --init-key", "sb --hash-name", "Rotating the key", "re-hash", "~/.config/grok-kit/scan.key",
                       "XDG_CONFIG_HOME"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)


if __name__ == "__main__":
    unittest.main()
