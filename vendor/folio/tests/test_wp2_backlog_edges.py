"""WP-2 edge cases added with the implementation (WP2-2): behaviours the adapter chose beyond the WP2-1
red tests. Each is pinned by a mutant in the job's mutation run.

- `doc view` on 1.53.0 exits 0 for a missing document (the message is on stderr): the adapter must
  still raise. A 79-character doc title folds to `>-` in the plain output and must round-trip.
- An edit or doc update that changes nothing is refused (exit 4) before any subprocess.
- `doctor` fails on every D-8 pin (remote_operations, check_active_branches, auto_commit) and on an
  `onStatusChange` key in config, before the binary is asked.
- The resolver treats a failing or unrunnable `--version` as exit 7.
"""

import os
import unittest

from backlog_contract.support import BacklogContractCase
from wp2_support import FID_HEX, FakeBacklogCase, argvs, seam, task_list_json


class DocEdgeTests(BacklogContractCase):
    def client(self, repo):
        adapter = seam(self, "adapter")
        return adapter, adapter.BacklogClient(self.backlog.binary, repo, self.home)

    def test_doc_view_of_a_missing_doc_is_an_error_despite_exit_0(self):
        repo = self.init_repo()
        adapter, client = self.client(repo)
        with self.assertRaises(adapter.BacklogError) as raised:
            client.doc_view("doc-9")
        self.assertNotEqual(raised.exception.exit_code, 0)
        self.assertIn("doc-9", str(raised.exception))

    def test_doc_title_at_the_cap_folds_in_plain_output_and_round_trips(self):
        repo = self.init_repo()
        adapter, client = self.client(repo)
        title = "Notes " + "n" * 73
        self.assertEqual(len(title), 79)
        doc_id = client.doc_create(title)
        self.assertEqual(client.doc_view(doc_id)["title"], title)
        with self.assertRaises(adapter.BacklogError) as raised:
            client.doc_create(title + "x")
        self.assertEqual(raised.exception.exit_code, 4)

    def test_doc_update_with_nothing_to_change_is_refused(self):
        repo = self.init_repo()
        adapter, client = self.client(repo)
        doc_id = client.doc_create("Notes")
        with self.assertRaises(adapter.BacklogError) as raised:
            client.doc_update(doc_id)
        self.assertEqual(raised.exception.exit_code, 4)


class DoctorPinTests(BacklogContractCase):
    def client(self, repo):
        adapter = seam(self, "adapter")
        return adapter, adapter.BacklogClient(self.backlog.binary, repo, self.home)

    def flip(self, repo, key):
        config = self.config_path(repo)
        text = self.config_text(repo)
        self.assertIn("%s: false\n" % key, text)
        config.write_text(text.replace("%s: false\n" % key, "%s: true\n" % key, 1), encoding="utf-8")

    def test_every_d8_pin_turned_on_fails_doctor(self):
        for index, key in enumerate(("remote_operations", "check_active_branches", "auto_commit")):
            with self.subTest(pin=key):
                repo = self.init_repo("repo-%d" % index)
                self.flip(repo, key)
                adapter, client = self.client(repo)
                with self.assertRaises(adapter.BacklogError) as raised:
                    client.doctor()
                self.assertIn(key, str(raised.exception))

    def test_on_status_change_in_config_fails_doctor(self):
        repo = self.init_repo()
        with self.config_path(repo).open("a", encoding="utf-8") as handle:
            handle.write("onStatusChange: 'touch %s'\n" % (self.root / "sentinel-doctor"))
        adapter, client = self.client(repo)
        with self.assertRaises(adapter.BacklogError) as raised:
            client.doctor()
        self.assertIn("onStatusChange", str(raised.exception))
        self.assertFalse((self.root / "sentinel-doctor").exists())


class FakeEdgeTests(FakeBacklogCase):
    def client(self, responses=()):
        adapter = seam(self, "adapter")
        binary = self.fake("1.53.0", responses)
        return adapter, adapter.BacklogClient(str(binary), self.repo, self.home)

    def test_edit_with_nothing_to_change_is_refused_without_a_subprocess(self):
        adapter, client = self.client()
        with self.assertRaises(adapter.BacklogError) as raised:
            client.edit("TASK-1")
        self.assertEqual(raised.exception.exit_code, 4)
        self.assertEqual(argvs(self.log), [])

    def test_create_labels_may_not_smuggle_a_second_fid_or_a_comma_list(self):
        adapter, client = self.client()
        for labels in (("fid:" + FID_HEX,), ("FID:" + FID_HEX,), ("a,b",), ("two words",), "notalist"):
            with self.subTest(labels=labels):
                with self.assertRaises(adapter.BacklogError) as raised:
                    client.create("Fine", labels=labels)
                self.assertEqual(raised.exception.exit_code, 4)
        self.assertEqual(argvs(self.log), [])

    def test_edit_labels_may_carry_at_most_one_fid_and_never_be_empty(self):
        adapter, client = self.client()
        for labels in (("fid:" + FID_HEX, "fid:" + "f" * 16), (), "fid:" + FID_HEX):
            with self.subTest(labels=labels):
                with self.assertRaises(adapter.BacklogError) as raised:
                    client.edit("TASK-1", labels=labels)
                self.assertEqual(raised.exception.exit_code, 4)
        self.assertEqual(argvs(self.log), [])

    def test_doctor_pin_failure_spawns_nothing(self):
        adapter, client = self.client()
        config = self.repo / "backlog" / "config.yml"
        config.write_text(config.read_text(encoding="utf-8").replace("auto_commit: false", "auto_commit: true"), encoding="utf-8")
        with self.assertRaises(adapter.DoctorFailed):
            client.doctor()
        self.assertEqual(argvs(self.log), [])

    def test_doctor_nonzero_exit_is_doctor_failed_with_the_output(self):
        adapter, client = self.client(((["doctor"], "Duplicate task IDs found\n", 1),))
        with self.assertRaises(adapter.DoctorFailed) as raised:
            client.doctor()
        self.assertIn("Duplicate task IDs found", str(raised.exception))

    def test_list_results_are_copies_the_cache_is_not_shared(self):
        adapter, client = self.client(((["task", "list"], task_list_json(("TASK-1", "One", ["a"])),  0),))
        for attempt in range(3):  # the cold result, then two cache hits: none may leak into the next
            with self.subTest(attempt=attempt):
                tasks = client.list()
                self.assertEqual((tasks[0]["title"], tasks[0]["labels"]), ("One", ["a"]))
                tasks[0]["labels"].append("mutated")
                tasks[0]["title"] = "mutated"
        self.assertEqual(len([argv for argv in argvs(self.log) if argv[:2] == ["task", "list"]]), 1)

    def test_a_task_view_without_a_path_refuses_the_edit(self):
        adapter, client = self.client(((
            ["task", "view"], '{"schemaVersion": 1, "kind": "task-view", "task": {"id": "TASK-1", "title": "One", "status": "To Do", "labels": []}}', 0),))
        with self.assertRaises(adapter.BacklogError) as raised:
            client.edit("TASK-1", status="Done")
        self.assertIn("no file path", str(raised.exception))
        self.assertEqual([argv[:2] for argv in argvs(self.log)], [["task", "view"]])

    def test_unexpected_json_kind_is_an_error(self):
        adapter, client = self.client(((["task", "list"], '{"schemaVersion": 1, "kind": "task-view", "tasks": []}', 0),))
        with self.assertRaises(adapter.BacklogError):
            client.list()


class ResolverEdgeTests(FakeBacklogCase):
    def test_a_failing_version_command_exits_7_even_when_it_prints_the_pin(self):
        tools = seam(self, "tools")
        binary = self.fake("1.53.0")
        binary.write_text("#!/bin/sh\necho 1.53.0\nexit 3\n", encoding="utf-8")
        resolver = tools.ToolResolver({"HOME": str(self.home), tools.BIN_ENV: str(binary)}, home=self.home)
        with self.assertRaises(tools.ToolError) as raised:
            resolver.backlog()
        self.assertEqual(raised.exception.exit_code, 7)

    def test_a_non_executable_binary_exits_7(self):
        tools = seam(self, "tools")
        binary = self.fake("1.53.0")
        os.chmod(binary, 0o600)
        resolver = tools.ToolResolver({"HOME": str(self.home), tools.BIN_ENV: str(binary)}, home=self.home)
        with self.assertRaises(tools.ToolError) as raised:
            resolver.backlog()
        self.assertEqual(raised.exception.exit_code, 7)


if __name__ == "__main__":
    unittest.main()
