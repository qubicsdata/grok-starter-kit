"""WP-2 red tests: ToolResolver.backlog() checks the version and the recorded sha256 (exit 7).

Until WP-9 lands folio/locks/backlog.lock.json, the version check compares against exactly 1.53.0
(R-c) and the sha256 is injected by the caller (the install record arrives with WP-9). The lock
cross-check is skipped with a reason that names WP-9.
"""

import hashlib
import json
import os
import unittest
from pathlib import Path
from unittest import mock

from wp2_support import FakeBacklogCase, REPO_ROOT, argvs, seam, write_fake_backlog

LOCK_PATH = REPO_ROOT / "folio" / "locks" / "backlog.lock.json"
LOCK_SKIP_REASON = "folio/locks/backlog.lock.json arrives in WP-9; WP-9 removes this skip"


def sha256_of(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class ToolResolverTests(FakeBacklogCase):
    def resolver(self, binary=None, expected_sha256=None, environ=None):
        tools = seam(self, "tools")
        env = {"HOME": str(self.home)}
        if binary is not None:
            env[tools.BIN_ENV] = str(binary)
        if environ:
            env.update(environ)
        return tools, tools.ToolResolver(env, home=self.home, expected_sha256=expected_sha256)

    def test_pin_constant_and_env_name(self):
        tools = seam(self, "tools")
        self.assertEqual(tools.BACKLOG_VERSION, "1.53.0")
        self.assertEqual(tools.BIN_ENV, "FOLIO_BACKLOG_BIN")

    def test_matching_version_and_hash_resolves(self):
        binary = self.fake("1.53.0")
        tools, resolver = self.resolver(binary, expected_sha256=sha256_of(binary))
        resolved = resolver.backlog()
        self.assertEqual(Path(resolved.path), binary)
        self.assertEqual(resolved.version, "1.53.0")
        self.assertEqual(resolved.sha256, sha256_of(binary))
        self.assertEqual(argvs(self.log), [["--version"]])
        self.assert_temp_home_everywhere()

    def test_version_mismatch_exits_7_for_every_near_miss(self):
        for index, version in enumerate(("1.54.0", "1.53.1", "1.52.0", "1.53.0-rc.1", "v1.53.0", "1.53", "")):
            with self.subTest(version=version):
                directory = self.dir / ("bin%d" % index)
                directory.mkdir()
                binary, _log = write_fake_backlog(directory, version)
                tools, resolver = self.resolver(binary, expected_sha256=sha256_of(binary))
                with self.assertRaises(tools.ToolError) as raised:
                    resolver.backlog()
                self.assertEqual(raised.exception.exit_code, 7)
                self.assertIn("1.53.0", str(raised.exception))

    def test_hash_mismatch_exits_7_even_when_the_version_matches(self):
        binary = self.fake("1.53.0")
        tools, resolver = self.resolver(binary, expected_sha256="0" * 64)
        with self.assertRaises(tools.ToolError) as raised:
            resolver.backlog()
        self.assertEqual(raised.exception.exit_code, 7)
        self.assertIn("sha256", str(raised.exception).lower())

    def test_hash_check_is_byte_exact(self):
        binary = self.fake("1.53.0")
        expected = sha256_of(binary)
        tools, resolver = self.resolver(binary, expected_sha256=expected)
        resolver.backlog()
        with binary.open("a", encoding="utf-8") as handle:
            handle.write("\n# one more byte\n")
        self.assertNotEqual(sha256_of(binary), expected)
        tools, resolver = self.resolver(binary, expected_sha256=expected)
        with self.assertRaises(tools.ToolError) as raised:
            resolver.backlog()
        self.assertEqual(raised.exception.exit_code, 7)

    def test_hash_mismatch_is_detected_before_the_binary_is_executed(self):
        binary = self.fake("1.53.0")
        tools, resolver = self.resolver(binary, expected_sha256="f" * 64)
        with self.assertRaises(tools.ToolError):
            resolver.backlog()
        self.assertEqual(argvs(self.log), [], "a binary with the wrong sha256 must never be run")

    def test_missing_binary_exits_7(self):
        tools, resolver = self.resolver(self.dir / "nowhere" / "backlog")
        with self.assertRaises(tools.ToolError) as raised:
            resolver.backlog()
        self.assertEqual(raised.exception.exit_code, 7)

    def test_without_env_the_default_is_the_xdg_tools_path(self):
        data_home = self.dir / "xdg-data"
        location = data_home / "folio" / "tools" / "backlog-1.53.0"
        location.mkdir(parents=True)
        binary, log = write_fake_backlog(location, "1.53.0")
        tools, resolver = self.resolver(environ={"XDG_DATA_HOME": str(data_home)})
        resolved = resolver.backlog()
        self.assertEqual(Path(resolved.path), binary)
        self.assertEqual(argvs(log), [["--version"]])

    def test_xdg_data_home_defaults_to_dot_local_share_under_home(self):
        location = self.home / ".local" / "share" / "folio" / "tools" / "backlog-1.53.0"
        location.mkdir(parents=True)
        binary, _log = write_fake_backlog(location, "1.53.0")
        tools, resolver = self.resolver()
        self.assertEqual(Path(resolver.backlog().path), binary)

    def test_env_binary_wins_over_the_xdg_path(self):
        location = self.home / ".local" / "share" / "folio" / "tools" / "backlog-1.53.0"
        location.mkdir(parents=True)
        _other, other_log = write_fake_backlog(location, "1.53.0")
        binary = self.fake("1.53.0")
        tools, resolver = self.resolver(binary)
        self.assertEqual(Path(resolver.backlog().path), binary)
        self.assertEqual(argvs(other_log), [])

    def test_no_expected_hash_means_version_check_only_until_wp9(self):
        binary = self.fake("1.53.0")
        tools, resolver = self.resolver(binary)
        resolved = resolver.backlog()
        self.assertEqual(resolved.sha256, sha256_of(binary))
        self.assertEqual(argvs(self.log), [["--version"]])

    def test_resolver_does_not_read_the_process_environment(self):
        binary = self.fake("1.53.0")
        tools = seam(self, "tools")
        with mock.patch.dict(os.environ, {tools.BIN_ENV: str(binary), "HOME": str(self.home)}):
            resolver = tools.ToolResolver({"HOME": str(self.home)}, home=self.home)
            with self.assertRaises(tools.ToolError):
                resolver.backlog()
        self.assertEqual(argvs(self.log), [])

    @unittest.skip(LOCK_SKIP_REASON)
    def test_resolver_pin_matches_the_lock(self):
        tools = seam(self, "tools")
        lock = json.loads(LOCK_PATH.read_text(encoding="utf-8"))
        self.assertEqual(lock["backlog_version"], tools.BACKLOG_VERSION)
        self.assertEqual(lock["backlog_version"], "1.53.0")

    def test_lock_skip_reason_names_wp9(self):
        self.assertIn("WP-9", LOCK_SKIP_REASON)
        self.assertFalse(LOCK_PATH.exists(), "the lock arrived: WP-9 must remove the skip on test_resolver_pin_matches_the_lock")


if __name__ == "__main__":
    unittest.main()
