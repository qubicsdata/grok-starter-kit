"""WP-13 security regression suite, part 4: items whose seams belong to WP-9, WP-10 or WP-11.

Those WPs are not on this stack (not merged, not queued here). Each item skips with a reason naming the
owning WP, and a tripwire turns the skip into a FAILURE once that WP's seam appears in the tree, so the
skip cannot outlive the seam (the pattern of WP-1's lock cross-check skip, R-c). What can be checked
today is checked: the exact `1.53.0` version pin (R-c), no `--force`, `push` or `git` argv in the app,
no lock file created by this WP, no WP-11 migrate package.
"""

import ast
import unittest

from folio.backlog import tools

from wp2_support import FakeBacklogCase
from wp6_support import app_python_files
from wp13_support import FOLIO, FOLIO_OLLAMA, REPO_ROOT

LOCK = FOLIO / "locks" / "backlog.lock.json"
WP9_SEAMS = (FOLIO / "locks",)
WP9_MESSAGE_SITES = (FOLIO / "cli.py", FOLIO / "web.py", FOLIO / "__main__.py", FOLIO / "backlog" / "tools.py", REPO_ROOT / "bin" / "folio")
WP10_SEAMS = (FOLIO / "sync.py", FOLIO / "backlog" / "outbox.py", FOLIO / "profile.py")
WP11_SEAMS = (FOLIO / "migrate", FOLIO / "migrate.py")
FORBIDDEN_ARGV = {"--force", "--force-with-lease", "push", "git"}


def tripwire(case, seams, wp, item):
    present = [seam.relative_to(REPO_ROOT).as_posix() for seam in seams if seam.exists()]
    if present:
        case.fail("%s's seam is in the tree (%s): replace this skip with the real test for %s" % (wp, ", ".join(present), item))


class WP9PendingTests(FakeBacklogCase):
    def test_native_windows_is_refused_with_the_wsl2_message_and_no_server_starts(self):
        """M-9: Windows is WSL2 only. The refusal lives in WP-9's install seam."""
        tripwire(self, WP9_SEAMS, "WP-9", "the native-Windows refusal")
        for path in WP9_MESSAGE_SITES:
            if path.is_file() and "WSL2" in path.read_text(encoding="utf-8"):
                self.fail("%s mentions WSL2: WP-9's native-Windows refusal landed; replace this skip with the test" % path.name)
        self.skipTest("the native-Windows refusal arrives with WP-9 (M-9: WSL2 only); WP-9 removes this skip")

    def test_this_wp_creates_no_lock_file(self):
        """folio/locks/backlog.lock.json is WP-9's seam (D-2, R-c); until then the pin is the constant 1.53.0."""
        self.assertEqual(tools.BACKLOG_VERSION, "1.53.0")
        if LOCK.exists():
            self.skipTest("folio/locks/backlog.lock.json exists: WP-9 landed; the lock cross-check in tests/backlog_contract owns it")

    def test_until_wp9_every_version_check_is_the_exact_string(self):
        for version in ("1.54.0", "1.53.1", "1.52.0", "v1.53.0", "1.53.0-rc.1", "1.53", "", "1.53.0\nextra"):
            with self.subTest(version=version):
                binary = self.fake(version)
                resolver = tools.ToolResolver({"FOLIO_BACKLOG_BIN": str(binary)}, self.home)
                with self.assertRaises(tools.ToolError) as caught:
                    resolver.backlog()
                self.assertEqual(caught.exception.exit_code, 7)
        resolved = tools.ToolResolver({"FOLIO_BACKLOG_BIN": str(self.fake("1.53.0"))}, self.home).backlog()
        self.assertEqual(resolved.version, "1.53.0")


class WP10PendingTests(unittest.TestCase):
    def test_a_push_goes_only_to_a_private_remote_with_no_env_bypass(self):
        """WP-10: `tasks-example-channel` is verified private before the first push; a public remote is refused; no env override."""
        tripwire(self, WP10_SEAMS, "WP-10", "the private-remote push rule")
        self.skipTest("git sync (folio/sync.py, VisibilityChecker) arrives with WP-10; WP-10 removes this skip")

    def test_the_laptop_profile_refuses_a_non_example_channel_repo_with_exit_4(self):
        """M-5, D-16: the laptop gets example-channel only."""
        tripwire(self, WP10_SEAMS, "WP-10", "the laptop profile (example-channel only)")
        self.skipTest("the laptop profile arrives with WP-10 (M-5: example-channel only); WP-10 removes this skip")

    def test_a_pulled_onstatuschange_shows_a_banner_and_edits_nothing(self):
        tripwire(self, WP10_SEAMS, "WP-10", "the pulled-onStatusChange banner")
        self.skipTest("the sync banner arrives with WP-10; the edit refusal itself is covered by test_wp13_security_tools")

    def test_no_force_push_or_git_argv_exists_in_the_app_today(self):
        """Until WP-10 there is no git path at all: no argv word `git`, `push`, `--force` or `--force-with-lease`."""
        hits = []
        for path in app_python_files() + sorted(FOLIO_OLLAMA.rglob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value in FORBIDDEN_ARGV:
                    hits.append("%s:%d: %r" % (path.relative_to(REPO_ROOT).as_posix(), node.lineno, node.value))
        self.assertEqual(hits, [])


class WP11PendingTests(unittest.TestCase):
    def test_the_migration_fails_closed_on_the_three_client_fixture(self):
        """M-4: allowed / other-channel / unknown; only the first produces files; planted names never appear."""
        tripwire(self, WP11_SEAMS, "WP-11", "the fail-closed migration fixture")
        self.skipTest("the migration (folio/migrate/{inventory,allowlist,apply}.py) arrives with WP-11; WP-11 removes this skip")

    def test_the_legacy_workspace_move_is_not_a_migration_path(self):
        """folio/migration.py moves a 1.1.x workspace folder; it reads no client data and has no allow-list to bypass."""
        source = (FOLIO / "migration.py").read_text(encoding="utf-8")
        for word in ("allow", "client", "channel", "example-channel", "hmac"):
            self.assertNotIn(word, source.lower(), "folio/migration.py grew migration semantics; WP-11 owns those")


if __name__ == "__main__":
    unittest.main()
