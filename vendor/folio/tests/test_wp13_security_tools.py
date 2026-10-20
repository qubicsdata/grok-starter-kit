"""WP-13 security regression suite, part 3: the Backlog adapter, the Ollama plugin and the approvals log.

- The onStatusChange guard (D-8, R2): any spelling of the key in the task file or backlog/config.yml
  refuses every edit with exit 4 before `task edit` is spawned; doctor refuses a poisoned config.
- No `backlog <board>` spawn (D-13, R13): a recording fake binary sits on PATH and behind
  FOLIO_BACKLOG_BIN while every adapter operation and every HTTP route (core, Ollama suggest and
  accept) runs; every spawn's first word is on the allow-list, none is the board subcommand, and the
  adapter refuses the subcommand without spawning. A static scan covers the app, the plugin, the
  launchers and the tests.
- Ollama non-loopback refusal (M-7): LAN, public, hostname, non-loopback IPv6 and mapped URLs are
  refused by check_url, make and the config loader with no lookup and no socket; a redirect off the
  loopback is not followed.
- The approvals log (M-6): created 0600 under every umask inside 0700 folders, opened with O_NOFOLLOW,
  and a symlink, another mode, a directory or a FIFO is refused without touching anything.
"""

import ast
import json
import os
import stat
import unittest
from pathlib import Path
from unittest import mock

from folio.backlog import tools
from folio.backlog.adapter import ALLOWED_FIRST_WORDS, BacklogClient, BacklogError, DoctorFailed, RefusedValue

from backlog_contract import support as contract_support
from backlog_contract.test_browser_guard import subcommand_invocations
from test_wp6_subprocess_allowlist import ALLOWED_SPAWN_SITES, process_sites
from wp2_support import FID_HEX, FakeBacklogCase, argvs
from wp5_support import FID, USER, FakeProvider, StateCase, decision
from wp6_support import CORE_ROUTES, REMOVED_ROUTES, app_python_files
from wp7_support import FakeEntryPoint
from wp8_support import ACCEPT, SUGGEST, ConnectRecorder, OllamaCase, calls, chat_response, plugins_module, redirect
from wp13_support import BOARD_SUBCOMMAND, FOLIO, FOLIO_OLLAMA, REPO_ROOT, PopenRecorder, mode_of

POSIX = os.name != "nt"
KEY_SPELLINGS = ("onStatusChange", "onstatuschange", "ONSTATUSCHANGE", "OnStatusChange", "on_status_change",
                 "On_Status_Change", "ON_STATUS_CHANGE", "on-status-change")
TASK_PATH = "backlog/tasks/task-1 - One.md"
VIEW = (["task", "view"], json.dumps({"schemaVersion": 1, "kind": "task-view",
                                      "task": {"id": "TASK-1", "title": "One", "status": "To Do", "labels": [], "path": TASK_PATH}}), 0)
REFUSED_URLS = {
    "ipv4 lan": "http://10.0.0.5:11434",
    "ipv4 private": "http://192.168.1.20:11434",
    "ipv4 public": "http://93.184.216.34:11434",
    "ipv4 unspecified": "http://0.0.0.0:11434",
    "hostname": "http://example.com:11434",
    "loopback look-alike hostname": "http://127.0.0.1.example.com:11434",
    "ipv6 global": "http://[2001:db8::1]:11434",
    "ipv6 link local": "http://[fe80::1]:11434",
    "ipv6 mapped lan": "http://[::ffff:10.0.0.5]:11434",
    "ipv6 unspecified": "http://[::]:11434",
    "https on loopback": "https://127.0.0.1:11434",
    "userinfo hides the host": "http://127.0.0.1@example.com:11434",
}


# -- the onStatusChange guard ---------------------------------------------------------------------------


class OnStatusChangeGuardTests(FakeBacklogCase):
    def client(self):
        return BacklogClient(str(self.fake("1.53.0", (VIEW,))), self.repo, self.home)

    def task(self, extra_line=""):
        path = self.repo / TASK_PATH
        path.write_text("---\nid: TASK-1\ntitle: One\nstatus: To Do\n%s---\nBody\n" % extra_line, encoding="utf-8")
        return path

    def edit_spawns(self):
        return [argv for argv in argvs(self.log) if argv[:2] == ["task", "edit"]]

    def test_a_status_edit_of_a_poisoned_task_is_refused_with_exit_4_before_any_edit_spawn(self):
        sentinel = self.dir / "sentinel"
        for key in KEY_SPELLINGS:
            with self.subTest(key=key):
                path = self.task("%s: 'touch %s'\n" % (key, sentinel))
                before = path.read_bytes()
                with self.assertRaises(BacklogError) as caught:
                    self.client().edit("TASK-1", status="Done")
                self.assertEqual(caught.exception.exit_code, 4)
                self.assertIn("onStatusChange", str(caught.exception))
                self.assertEqual(self.edit_spawns(), [])
                self.assertFalse(sentinel.exists(), "the hook ran")
                self.assertEqual(path.read_bytes(), before)

    def test_a_poisoned_config_refuses_every_kind_of_edit_of_a_clean_task(self):
        self.task()
        with (self.repo / "backlog" / "config.yml").open("a", encoding="utf-8") as handle:
            handle.write("OnStatusChange: 'touch %s'\n" % (self.dir / "sentinel"))
        client = self.client()
        for kwargs in ({"status": "Done"}, {"title": "Renamed"}, {"description": "text"}, {"labels": ("fid:" + FID_HEX,)},
                       {"priority": "high"}, {"project": "alpha"}):
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(BacklogError) as caught:
                    client.edit("TASK-1", **kwargs)
                self.assertEqual(caught.exception.exit_code, 4)
        self.assertEqual(self.edit_spawns(), [])
        self.assertFalse((self.dir / "sentinel").exists())

    def test_the_key_in_the_body_or_nested_or_quoted_still_refuses(self):
        for text in ("---\nid: TASK-1\nstatus: To Do\n---\nnotes\nonStatusChange: touch x\n",
                     "---\nid: TASK-1\nstatus: To Do\nhooks:\n  onStatusChange: touch x\n---\n",
                     '---\nid: TASK-1\nstatus: To Do\n"onStatusChange": touch x\n---\n',
                     "---\r\nid: TASK-1\r\nstatus: To Do\r\nonStatusChange: touch x\r\n---\r\n"):
            with self.subTest(text=text[:40]):
                (self.repo / TASK_PATH).write_text(text, encoding="utf-8")
                with self.assertRaises(BacklogError) as caught:
                    self.client().edit("TASK-1", status="Done")
                self.assertEqual(caught.exception.exit_code, 4)
        self.assertEqual(self.edit_spawns(), [])

    def test_a_clean_edit_reaches_the_binary_exactly_once_as_task_edit(self):
        self.task()
        self.client().edit("TASK-1", status="In Progress")
        spawned = argvs(self.log)
        self.assertEqual([argv[:2] for argv in spawned], [["task", "view"], ["task", "edit"]])
        self.assertEqual(spawned[1][:5], ["task", "edit", "TASK-1", "-s", "In Progress"])

    def test_an_unreadable_or_missing_task_file_fails_closed(self):
        with self.assertRaises(BacklogError) as caught:
            self.client().edit("TASK-1", status="Done")
        self.assertEqual(caught.exception.exit_code, 4)
        if POSIX and os.getuid() != 0:
            path = self.task()
            path.chmod(0)
            try:
                with self.assertRaises(BacklogError) as caught:
                    self.client().edit("TASK-1", status="Done")
                self.assertEqual(caught.exception.exit_code, 4)
            finally:
                path.chmod(0o600)
        self.assertEqual(self.edit_spawns(), [])

    def test_doctor_refuses_a_poisoned_or_remote_config_before_spawning(self):
        config = self.repo / "backlog" / "config.yml"
        clean = config.read_text(encoding="utf-8")
        for line in ("onStatusChange: touch x\n", "remote_operations: true\n"):
            with self.subTest(line=line.strip()):
                config.write_text(clean.replace("remote_operations: false\n", "") + line, encoding="utf-8")
                with self.assertRaises(DoctorFailed):
                    self.client().doctor()
        self.assertEqual(argvs(self.log), [], "doctor spawned the binary although the config was refused")


# -- no board spawn ------------------------------------------------------------------------------------


class BoardOnPathCase(OllamaCase):
    """OllamaCase (stateful recording fake behind FOLIO_BACKLOG_BIN) with the fake's folder first on PATH."""

    def setUp(self):
        super().setUp()
        os.environ["PATH"] = str(self.binary.parent) + os.pathsep + "/usr/bin:/bin"  # inside IsolatedCase's patch.dict

    def assert_only_allowed_spawns(self, recorder):
        self.assertEqual(recorder.board_spawns(), [], "the board subcommand was spawned")
        self.assertTrue(recorder.argvs, "nothing was spawned, so the check proved nothing")
        for argv in recorder.argvs:
            with self.subTest(argv=argv[:3]):
                self.assertEqual(Path(argv[0]), self.binary, "a binary other than the pinned one was run")
                self.assertIn(argv[1], ALLOWED_FIRST_WORDS)
                self.assertNotIn(BOARD_SUBCOMMAND, argv)
        recorded = calls(self.log)
        self.assertEqual([call["argv"][:1] for call in recorded], [argv[1:2] for argv in recorder.argvs],
                         "the on-disk record of the fake disagrees with the in-process record")
        for call in recorded:
            self.assertNotIn(BOARD_SUBCOMMAND, call["argv"])


class AdapterNeverSpawnsTheBoardTests(BoardOnPathCase):
    def client(self):
        return BacklogClient(str(self.binary), self.repo, self.home)

    def test_the_board_subcommand_and_every_other_first_word_is_refused_before_a_spawn(self):
        client = self.client()
        refused = ([BOARD_SUBCOMMAND], [BOARD_SUBCOMMAND, "--help"], [BOARD_SUBCOMMAND, "--port", "0", "--no-open"],
                   ["--help"], ["mcp", "start"], ["board"], ["Task", "list"], [" task"], [""], [], ["--project", "x", "task"], ["-v"])
        with PopenRecorder() as recorder:
            for argv in refused:
                with self.subTest(argv=argv):
                    with self.assertRaises(RefusedValue):
                        client._run(argv)
        self.assertEqual(recorder.argvs, [])
        self.assertEqual(calls(self.log), [])

    def test_every_adapter_operation_and_the_resolver_spawn_allowed_words_with_a_private_home(self):
        client = self.client()
        with PopenRecorder() as recorder:
            resolved = tools.ToolResolver(os.environ, self.home).backlog()
            self.assertEqual(Path(resolved.path), self.binary)
            self.assertEqual(client.list(), [])
            created = client.create("A task", description="text", labels=("ws:alpha",))
            self.assertEqual(client.view(created.id)["id"], created.id)
            client.edit(created.id, status="Done")
            self.assertTrue(client.doctor()["ok"])
            client.config_pins()
            for operation in (lambda: client.doc_create("Note"), lambda: client.doc_view("doc-1"),
                              lambda: client.doc_update("doc-1", content="x")):
                try:
                    operation()
                except BacklogError:
                    pass  # the fake answers nothing for `doc`; the spawn is what this test records
        self.assert_only_allowed_spawns(recorder)
        self.assertEqual(sorted(set(recorder.first_words())), ["--version", "doc", "doctor", "task"])
        for call in calls(self.log):
            self.assertEqual(call["home"], str(self.home), call)
            self.assertTrue(call["home"].startswith(str(self.dir)), "the subprocess HOME is not inside the test's temp dir")


class RoutesNeverSpawnTheBoardTests(BoardOnPathCase):
    def setUp(self):
        super().setUp()
        self.fake = self.fake_ollama(reply=chat_response({"subtasks": [{"title": "From the model"}]}))
        self.serve(self.app_with(self.plugin(self.fake.url)))

    def test_every_route_including_ollama_accept_spawns_only_allowed_words(self):
        with PopenRecorder() as recorder:
            status, client, _ = self.call("/api/clients", "POST", {"name": "Client A"}, self.owner())
            self.assertEqual(status, 200, client)
            status, project, _ = self.call("/api/projects", "POST", {"client_id": client["id"], "name": "Project A"}, self.owner())
            self.assertEqual(status, 200, project)
            bodies = {"brief": {"query": "plan"}, "source": {"source_id": "0" * 16}, "sections": {"title": "Note", "text": "t", "kind": "note"},
                      "relocate": {"folder": project.get("folder", "")}, "workstreams": {"name": "Stream"}, "tasks": {"title": "Task"},
                      "append": {"text": "more"}, "resolve": {"requested": "approve"}}
            for method, path in CORE_ROUTES:
                if method == "POST" and path in ("/api/clients", "/api/projects"):
                    continue
                real = path.replace("0123456789abcdef", project["id"], 1)
                body = None if method == "GET" else bodies.get(path.rstrip("/").rsplit("/", 1)[-1], {})
                status, payload, _ = self.call(real, method, body, self.owner())
                self.assertLess(status, 500, (method, real, payload))
            for method, path, body in REMOVED_ROUTES:
                self.assertEqual(self.call(path, method, body, self.owner())[0], 404)
            status, proposal, _ = self.call(SUGGEST, "POST", self.suggest_data(), self.owner())
            self.assertEqual(status, 200, proposal)
            status, result, _ = self.call(ACCEPT, "POST", self.accept_data(["One", "Two"]), self.owner())
            self.assertEqual(status, 200, result)
            self.assertEqual(len(result["created"]), 2)
            self.assertEqual(self.call("/api/plugins/switchboard/ping", headers=self.owner())[0], 404)
        self.assert_only_allowed_spawns(recorder)
        self.assertLessEqual(set(recorder.first_words()), {"--version", "task", "doctor"})
        self.assertIn("task", recorder.first_words(), "accept did not reach the adapter")


class StaticBoardScanTests(unittest.TestCase):
    def test_no_board_invocation_in_the_app_the_plugin_the_launchers_or_the_tests(self):
        self.assertEqual(subcommand_invocations(REPO_ROOT, ("folio", "folio_ollama", "scripts", "tests", "bin")), [])

    def test_the_allow_lists_agree_and_exclude_the_board(self):
        self.assertEqual(ALLOWED_FIRST_WORDS, ("init", "task", "doctor", "config", "doc", "--version"))
        self.assertEqual(contract_support.ALLOWED_FIRST_WORDS, ALLOWED_FIRST_WORDS)
        self.assertNotIn(BOARD_SUBCOMMAND, ALLOWED_FIRST_WORDS)

    def test_no_spawn_site_names_the_board_subcommand_as_a_string(self):
        """The adapter, the resolver and the plugin are the only modules that build a backlog argv."""
        hits = []
        for path in sorted((FOLIO / "backlog").glob("*.py")) + sorted(FOLIO_OLLAMA.glob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Constant) and isinstance(node.value, str) and BOARD_SUBCOMMAND in node.value.lower():
                    hits.append("%s:%d: %r" % (path.relative_to(REPO_ROOT), node.lineno, node.value))
        self.assertEqual(hits, [])

    def test_the_plugin_spawns_nothing_itself_and_the_app_spawns_only_from_the_allow_list(self):
        """folio_ollama writes through the adapter; it imports no process module and calls no os spawn primitive."""
        self.assertEqual(process_sites(sorted(FOLIO_OLLAMA.rglob("*.py"))), [])
        outside = [hit for hit in process_sites(app_python_files()) if not hit.startswith(tuple(site + ":" for site in ALLOWED_SPAWN_SITES))]
        self.assertEqual(outside, [])


# -- Ollama non-loopback refusal -------------------------------------------------------------------------


class OllamaRefusalTests(OllamaCase):
    def test_check_url_and_make_refuse_non_loopback_urls_with_no_lookup_and_no_socket(self):
        module = self.ollama()
        plugins = plugins_module(self)
        with ConnectRecorder(forbid=True, resolve={}) as recorder:
            for name, url in REFUSED_URLS.items():
                with self.subTest(url=name):
                    with self.assertRaises(plugins.PluginError):
                        module.check_url(url)
                    with self.assertRaises(plugins.PluginError):
                        module.make(self.settings(url))
        self.assertEqual(recorder.connects, [])
        self.assertEqual(recorder.lookups, [], "a refused URL reached the resolver")
        self.assert_no_write()

    def test_a_non_loopback_url_in_the_local_config_mounts_nothing(self):
        module = self.ollama()
        plugins = plugins_module(self)
        point = FakeEntryPoint("ollama", module.make)
        with ConnectRecorder(forbid=True, resolve={}) as recorder:
            for name, url in REFUSED_URLS.items():
                with self.subTest(url=name):
                    self.write_config({"plugins": {"ollama": self.settings(url)}})
                    with self.assertRaises(plugins.PluginError):
                        plugins.load_from_config(entry_points=[point])
        self.assertEqual(recorder.connects, [])
        self.assertEqual(recorder.lookups, [])
        self.assertEqual(point.loads, len(REFUSED_URLS), "the entry point was loaded once per attempt and refused each time")

    def test_localhost_that_resolves_off_the_loopback_is_refused(self):
        module = self.ollama()
        plugins = plugins_module(self)
        for answers in (["10.0.0.5"], ["127.0.0.1", "10.0.0.5"], ["::ffff:10.0.0.5"], []):
            with self.subTest(answers=answers):
                with ConnectRecorder(forbid=True, resolve={"localhost": answers}) as recorder:
                    with self.assertRaises(plugins.PluginError):
                        module.make(self.settings("http://localhost:11434"))
                self.assertEqual(recorder.connects, [])

    def test_a_redirect_off_the_loopback_is_not_followed(self):
        for location in ("http://10.0.0.5:11434/api/chat", "http://example.com/api/chat", "http://[2001:db8::1]/api/chat",
                         "https://127.0.0.1:11434/api/chat"):
            with self.subTest(location=location):
                fake = self.fake_ollama(reply=redirect(location))
                app = self.app_with(self.plugin(fake.url))
                with ConnectRecorder(forbid=False, resolve={}) as recorder:
                    self.assert_refused(lambda: self.post(app, SUGGEST, self.suggest_data()), 502, "OLLAMA_RESPONSE")
                self.assertEqual(recorder.hosts(), ["127.0.0.1"])
                self.assertEqual(set(recorder.lookups) - {"127.0.0.1"}, set(), "a name lookup happened")
                fake.only_request(self)
        self.assert_no_write()


# -- approvals file mode ---------------------------------------------------------------------------------


@unittest.skipUnless(POSIX, "POSIX file modes and O_NOFOLLOW")
class ApprovalsFileModeTests(StateCase):
    def record(self, log):
        log.record_resolution("fake", "dec_00000000000000a1", "approve", FID)

    def test_the_log_is_created_0600_inside_0700_folders_under_every_umask(self):
        for umask in (0, 0o022, 0o077, 0o277):
            with self.subTest(umask=oct(umask)):
                previous = os.umask(umask)
                try:
                    self.record(self.log())
                finally:
                    os.umask(previous)
                self.assertTrue(stat.S_ISREG(os.lstat(self.log_path).st_mode))
                self.assertEqual(mode_of(self.log_path), 0o600)
                for directory in (self.state, self.state / "folio"):
                    self.assertEqual(mode_of(directory), 0o700, directory)
                self.record(self.log())
                self.assertEqual(len(self.log().records()), 2)
                self.log_path.unlink()
                for directory in (self.state / "folio", self.state):
                    directory.rmdir()

    def test_every_open_of_the_log_uses_o_nofollow(self):
        log = self.log()
        real_open = os.open
        flags = []

        def recording_open(path, flag, *args, **kwargs):
            if Path(os.fsdecode(path)) == self.log_path:
                flags.append(flag)
            return real_open(path, flag, *args, **kwargs)

        with mock.patch("os.open", side_effect=recording_open):
            self.record(log)
            log.records()
            log.claim_notifications("fake", ["dec_00000000000000a2"])
            log.mark_seen("fake", "dec_00000000000000a2")
        self.assertGreaterEqual(len(flags), 4)
        for flag in flags:
            self.assertTrue(flag & os.O_NOFOLLOW, "an open of approvals.jsonl lacks O_NOFOLLOW: %#o" % flag)

    def test_a_symlinked_approvals_log_is_rejected_for_each_operation_and_the_link_target_stays_unchanged(self):
        module = self.approvals()
        target = self.dir / "elsewhere.jsonl"
        target.write_text('{"type": "resolution"}\n', encoding="utf-8")
        target.chmod(0o600)
        self.log_path.parent.mkdir(parents=True)
        self.log_path.symlink_to(target)
        log = self.log()
        for operation in (lambda: self.record(log), log.records, lambda: log.claim_notifications("fake", ["dec_00000000000000a2"]),
                          lambda: log.mark_seen("fake", "dec_00000000000000a2"), log.check):
            with self.assertRaises(module.ApprovalLogError):
                operation()
        self.assertEqual(target.read_text(encoding="utf-8"), '{"type": "resolution"}\n')
        self.assertTrue(self.log_path.is_symlink())
        self.log_path.unlink()
        self.log_path.symlink_to(self.dir / "planted.jsonl")
        with self.assertRaises(module.ApprovalLogError):
            self.record(self.log())
        self.assertFalse((self.dir / "planted.jsonl").exists(), "O_CREAT followed a dangling symlink")

    def test_another_mode_a_directory_or_a_fifo_in_place_of_the_log_is_refused_unchanged(self):
        module = self.approvals()
        self.log_path.parent.mkdir(parents=True)
        for mode in (0o644, 0o640, 0o660, 0o604, 0o700, 0o400, 0o666):
            with self.subTest(mode=oct(mode)):
                self.log_path.write_text("", encoding="utf-8")
                self.log_path.chmod(mode)
                log = self.log()
                with self.assertRaises(module.ApprovalLogError):
                    self.record(log)
                with self.assertRaises(module.ApprovalLogError):
                    log.records()
                self.assertEqual(mode_of(self.log_path), mode, "the mode was changed")
                self.assertEqual(self.log_path.read_bytes(), b"")
                self.log_path.chmod(0o600)
                self.log_path.unlink()
        self.log_path.mkdir()
        with self.assertRaises(module.ApprovalLogError):
            self.record(self.log())
        self.log_path.rmdir()
        os.mkfifo(self.log_path, 0o600)
        with self.assertRaises(module.ApprovalLogError):
            self.record(self.log())
        with self.assertRaises(module.ApprovalLogError):
            self.log().records()
        self.assertTrue(stat.S_ISFIFO(os.lstat(self.log_path).st_mode))

    def test_a_refused_log_stops_a_resolve_before_the_dialog_and_the_provider(self):
        target = self.dir / "elsewhere.jsonl"
        target.write_text("", encoding="utf-8")
        target.chmod(0o600)
        self.log_path.parent.mkdir(parents=True)
        self.log_path.symlink_to(target)
        provider = FakeProvider([decision("a1")])
        inbox = self.inbox(provider, {"choice": "approve", "text": ""})
        from folio.core import AppError
        with self.assertRaises(AppError) as caught:
            inbox.resolve("dec_00000000000000a1", {"requested": "approve"}, USER)
        self.assertEqual((caught.exception.status, caught.exception.code), (500, "APPROVALS_LOG_REFUSED"))
        self.assertEqual(self.dialog.asked, [], "the dialog opened although the trace is unsafe")
        self.assertEqual(provider.calls, [])
        self.assertEqual(target.read_bytes(), b"")


if __name__ == "__main__":
    unittest.main()
