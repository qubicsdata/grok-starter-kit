"""WP-8 red tests: Accept is the only write, and it goes through the Backlog adapter.

Acceptance: Accept creates the proposed tasks with `fid` labels (against the stateful fake binary and
against the pinned 1.53.0 binary). Security: every title is validated before the first write (an
option-like, over-long, hidden-character or eleventh title -> 400 and nothing created), Accept never calls
the model and opens no socket, the Backlog subprocess gets a private temporary HOME, and the plugin
routes sit behind the /api credential checks.
"""

import json
import os
import re
import tempfile
import unittest
from pathlib import Path

from folio.api import App, route
from folio.core import Store

from backlog_contract.support import BacklogContractCase
from wp7_support import FORBIDDEN
from wp8_support import (ACCEPT, CHANNEL, MODEL, SUGGEST, ConnectRecorder, OllamaCase, argvs, calls, chat_response, creates,
                         fid_labels, plugins_module, seam, tree_digest)

FID_RE = re.compile(r"^[0-9a-f]{16}$")
TITLES = ["Write the spec", "Review it with the client", "Ship the widget"]


class AcceptCase(OllamaCase):
    def accept(self, titles, **overrides):
        plugin = self.plugin("http://127.0.0.1:11434", **overrides)
        app = self.app_with(plugin)
        return self.post(app, ACCEPT, self.accept_data(titles))


class AcceptCreatesTasksTests(AcceptCase):
    def test_accept_creates_tasks_with_fid_labels_through_the_adapter(self):
        with ConnectRecorder(forbid=True) as recorder:
            result = self.accept(TITLES)
        created = result["created"]
        self.assertEqual([item["title"] for item in created], TITLES)
        self.assertEqual([item["id"] for item in created], ["TASK-1", "TASK-2", "TASK-3"])
        fids = [item["fid"] for item in created]
        for fid in fids:
            self.assertRegex(fid, FID_RE)
        self.assertEqual(len(set(fids)), 3, "every task gets its own fid")
        spawned = creates(self.log)
        self.assertEqual(len(spawned), 3)
        for argv, item in zip(spawned, created):
            self.assertEqual(argv[:3], ["task", "create", item["title"]])
            self.assertEqual(fid_labels(argv), ["fid:" + item["fid"]])
        self.assertEqual(recorder.connects, [], "Accept must not open a socket")
        self.assertNotEqual(tree_digest(self.repo), self.before, "the tasks repo gained the tasks")

    def test_created_tasks_are_listed_with_their_fid_labels(self):
        adapter = __import__("folio.backlog.adapter", fromlist=["BacklogClient"])
        result = self.accept(TITLES[:2])
        client = adapter.BacklogClient(self.binary, self.repo, self.home)
        listed = {task["id"]: task for task in client.list()}
        for item in result["created"]:
            self.assertIn("fid:" + item["fid"], listed[item["id"]]["labels"])
            self.assertEqual(listed[item["id"]]["title"], item["title"])
            self.assertEqual(client.resolve(item["fid"]), item["id"])

    def test_accept_never_calls_the_model(self):
        fake = self.fake_ollama(reply=chat_response({"subtasks": [{"title": "x"}]}))
        plugin = self.plugin(fake.url)
        app = self.app_with(plugin)
        result = self.post(app, ACCEPT, self.accept_data(["One"]))
        self.assertEqual(len(result["created"]), 1)
        self.assertEqual(fake.requests, [])

    def test_the_backlog_subprocess_gets_a_private_temporary_home(self):
        self.accept(TITLES[:1])
        recorded = calls(self.log)
        self.assertTrue(recorded)
        homes = {call["home"] for call in recorded}
        self.assertEqual(len(homes), 1, homes)
        home = homes.pop()
        self.assertTrue(home and os.path.isabs(home), home)
        self.assertNotEqual(home, str(self.home), "the account HOME must not be handed to the binary")
        self.assertNotEqual(home, os.path.expanduser("~"))
        task_calls = [call for call in recorded if call["argv"][:1] == ["task"]]
        self.assertTrue(task_calls)
        for call in task_calls:
            self.assertEqual(call["cwd"], str(self.repo), "task commands run inside the configured tasks repo")

    def test_accept_runs_backlog_with_allowed_first_words_only(self):
        self.accept(TITLES)
        for argv in argvs(self.log):
            self.assertIn(argv[0], ("init", "task", "doctor", "config", "doc", "--version"), argv)
            self.assertNotEqual(argv[:2], ["task", "edit"], "Accept only creates")

    def test_close_releases_the_temporary_home(self):
        module = self.ollama()
        plugin = module.make(self.settings("http://127.0.0.1:11434"))
        app = self.app_with(plugin)
        self.post(app, ACCEPT, self.accept_data(["One"]))
        home = calls(self.log)[-1]["home"]
        self.assertTrue(os.path.isdir(home))
        plugin.close()
        self.assertFalse(os.path.exists(home), "close() must remove the temporary HOME")
        plugin.close()  # idempotent


class AcceptValidationTests(AcceptCase):
    def test_every_title_is_validated_before_the_first_write(self):
        cases = {
            "option-like second": ["Fine", "-rf"], "option-like first": ["--help", "Fine"],
            "eighty characters": ["Fine", "x" * 80], "empty": ["Fine", ""], "whitespace": ["Fine", "  "],
            "leading space": ["Fine", " x"], "newline": ["Fine", "a\nb"], "tab": ["Fine", "a\tb"],
            "nul": ["Fine", "a\x00b"], "zero width": ["Fine", "a\u200bb"], "bidi": ["Fine", "a\u202eb"],
            "nbsp": ["Fine", "a\u00a0b"],
            "eleven": ["Step %d" % index for index in range(11)],
            "not a string": ["Fine", 5], "null": ["Fine", None],
            "extra key": ["Fine", {"title": "x", "description": "y"}],
            "labels smuggled": ["Fine", {"title": "x", "labels": ["fid:0123456789abcdef"]}],
            "no title": ["Fine", {}],
            "empty list": [],
        }
        for name, titles in cases.items():
            with self.subTest(case=name):
                self.assert_refused(lambda: self.accept(titles), 400, "VALIDATION")
                self.assert_no_write()

    def test_malformed_accept_bodies_are_400(self):
        plugin = self.plugin("http://127.0.0.1:11434")
        app = self.app_with(plugin)
        for name, body in {"no subtasks": {"channel": CHANNEL}, "subtasks not a list": {"channel": CHANNEL, "subtasks": {"title": "x"}},
                           "subtasks string": {"channel": CHANNEL, "subtasks": "x"},
                           "unknown key": {"channel": CHANNEL, "subtasks": [{"title": "x"}], "labels": ["a"]},
                           "task instead": {"channel": CHANNEL, "task": {"title": "x"}}}.items():
            with self.subTest(body=name):
                self.assert_refused(lambda: self.post(app, ACCEPT, body), 400, None)
        self.assert_no_write()

    def test_a_valid_list_after_a_refused_one_still_works(self):
        plugin = self.plugin("http://127.0.0.1:11434")
        app = self.app_with(plugin)
        self.assert_refused(lambda: self.post(app, ACCEPT, self.accept_data(["Fine", "-rf"])), 400, "VALIDATION")
        self.assert_no_write()
        result = self.post(app, ACCEPT, self.accept_data(["Fine"]))
        self.assertEqual([item["title"] for item in result["created"]], ["Fine"])
        self.assertEqual(len(creates(self.log)), 1)


class AcceptOverHttpTests(OllamaCase):
    def setUp(self):
        super().setUp()
        self.fake = self.fake_ollama(reply=chat_response({"subtasks": [{"title": "From the model"}]}))
        self.serve(self.app_with(self.plugin(self.fake.url)))

    def test_unauthenticated_accept_and_suggest_are_403_and_do_nothing(self):
        for path, body in ((ACCEPT, self.accept_data(["One"])), (SUGGEST, self.suggest_data())):
            for name, headers in {"nothing": {}, "wrong owner token": {"X-Workspace-Token": "0" * 64},
                                  "foreign origin with owner token": {**self.owner(), "Origin": "https://example.com"}}.items():
                with self.subTest(path=path, attempt=name):
                    status, payload, _ = self.call(path, "POST", body, {"Origin": self.base, **headers})
                    self.assertEqual(status, 403, payload)
        self.assertEqual(self.fake.requests, [])
        self.assert_no_write()

    def test_unauthenticated_requests_do_not_reveal_the_plugin(self):
        status, payload, _ = self.call(SUGGEST, "POST", self.suggest_data())
        self.assertEqual((status, payload), FORBIDDEN)

    def test_owner_token_suggests_then_accepts(self):
        status, proposal, _ = self.call(SUGGEST, "POST", self.suggest_data(), self.owner())
        self.assertEqual((status, proposal["kind"]), (200, "proposal"))
        self.assertEqual(proposal["subtasks"], [{"title": "From the model"}])
        self.assert_no_write()
        status, result, _ = self.call(ACCEPT, "POST", {"channel": CHANNEL, "subtasks": proposal["subtasks"]}, self.owner())
        self.assertEqual(status, 200, result)
        self.assertEqual([item["title"] for item in result["created"]], ["From the model"])
        self.assertEqual(len(creates(self.log)), 1)

    def test_browser_session_needs_the_csrf_token_to_accept(self):
        cookie, proof = self.session()
        session = {"Origin": self.base, "Cookie": cookie, "X-Folio-Session": proof}
        status, payload, _ = self.call(ACCEPT, "POST", self.accept_data(["One"]), session)
        self.assertEqual(status, 403, payload)
        self.assert_no_write()
        status, payload, _ = self.call(ACCEPT, "POST", self.accept_data(["One"]), {**session, "X-Workspace-Token": self.server.csrf_token})
        self.assertEqual(status, 200, payload)
        self.assertEqual(len(creates(self.log)), 1)

    def test_get_patch_and_delete_on_the_plugin_routes_are_404(self):
        for method, path in (("GET", SUGGEST), ("GET", ACCEPT), ("PATCH", ACCEPT), ("DELETE", ACCEPT), ("PATCH", SUGGEST),
                             ("GET", "/api/plugins/ollama/"), ("POST", "/api/plugins/ollama/propose")):
            with self.subTest(method=method, path=path):
                status, payload, _ = self.call(path, method, None if method == "GET" else {"channel": CHANNEL}, self.owner())
                self.assertEqual(status, 404, payload)
        self.assertEqual(self.fake.requests, [])
        self.assert_no_write()

    def test_errors_from_the_model_are_error_envelopes_with_the_code(self):
        self.fake.reply = chat_response({"subtasks": [{"title": "-rf"}]})
        status, payload, _ = self.call(SUGGEST, "POST", self.suggest_data(), self.owner())
        self.assertEqual((status, payload.get("code")), (502, "OLLAMA_RESPONSE"), payload)
        self.assert_no_write()


class RealBinaryAcceptTests(BacklogContractCase):
    """Accept against the pinned Backlog.md 1.53.0 binary (FOLIO_BACKLOG_BIN; fail-not-skip as in WP-1)."""

    def test_accept_creates_tasks_the_real_binary_lists_with_fid_labels(self):
        module = seam(self)
        plugins = plugins_module(self)
        repo = self.init_repo()
        workspace = tempfile.TemporaryDirectory(prefix="folio-wp8-store-")
        self.addCleanup(workspace.cleanup)
        store = Store(Path(workspace.name))
        self.addCleanup(store.close)
        plugin = module.make({"url": "http://127.0.0.1:11434", "model": MODEL, "channel": CHANNEL, "repo": str(repo)})
        self.addCleanup(plugin.close)
        host = plugins.PluginHost()
        host.mount(plugin)
        app = App(store, plugins=host)
        with ConnectRecorder(forbid=True):
            result = route(app, "POST", ACCEPT, {"channel": CHANNEL, "subtasks": [{"title": "Write the spec"}, {"title": "Ship it"}]},
                           {"origin": "user", "via": None})
        created = result["created"]
        self.assertEqual([item["id"] for item in created], ["TASK-1", "TASK-2"])
        self.assertEqual(self.task_files(repo), ["task-1 - Write-the-spec.md", "task-2 - Ship-it.md"])
        for item in created:
            viewed = json.loads(self.backlog.run(["task", "view", item["id"], "--json"], cwd=repo).stdout)["task"]
            self.assertEqual(viewed["title"], item["title"])
            self.assertIn("fid:" + item["fid"], viewed["labels"])


if __name__ == "__main__":
    unittest.main()
