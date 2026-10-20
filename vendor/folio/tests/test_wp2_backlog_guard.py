"""WP-2 red tests: the onStatusChange guard (D-8, R13).

Probed on Backlog.md 1.53.0 (2026-10-17): a per-task `onStatusChange: 'touch <file>'` line IS executed
by `task edit -s`, and the key survives the edit. So the sentinel assertions below are a real canary:
if the guard lets the edit through, the sentinel appears. The sentinel lives inside the test's temp
dir, never under /tmp/x.

Contract: guard.scan_text(text) returns the matched key spellings (any case, `onStatusChange` or
`on_status_change`); guard.check(repo, task_path) raises GuardRefused (exit 4) when the key is found in
backlog/config.yml or in the task file; BacklogClient.edit runs the guard before spawning the binary.
"""

import unittest
from pathlib import Path

from backlog_contract.support import BacklogContractCase
from wp2_support import FID_HEX, FakeBacklogCase, argvs, seam

KEY_SPELLINGS = ("onStatusChange", "onstatuschange", "ONSTATUSCHANGE", "OnStatusChange", "on_status_change",
                 "On_Status_Change", "ON_STATUS_CHANGE")


def sentinel_line(key, sentinel):
    return "%s: 'touch %s'\n" % (key, sentinel)


class GuardScanTests(unittest.TestCase):
    def test_every_case_variant_is_found_in_front_matter(self):
        guard = seam(self, "guard")
        for key in KEY_SPELLINGS:
            with self.subTest(key=key):
                text = "---\nid: TASK-1\nstatus: To Do\n%s: 'touch x'\n---\n" % key
                self.assertEqual(guard.scan_text(text), [key])

    def test_clean_task_and_config_text_yield_no_findings(self):
        guard = seam(self, "guard")
        clean = (
            "---\nid: TASK-1\ntitle: Status change policy\nstatus: To Do\nlabels:\n  - 'fid:%s'\n---\nBody\n" % FID_HEX,
            "project_name: Clean\nremote_operations: false\ncheck_active_branches: false\nauto_commit: false\n",
            "",
        )
        for text in clean:
            with self.subTest(text=text[:30]):
                self.assertEqual(guard.scan_text(text), [])

    def test_key_hidden_in_the_body_or_nested_is_still_found(self):
        guard = seam(self, "guard")
        samples = (
            "---\nid: TASK-1\n---\nnotes\nonStatusChange: 'touch x'\n",
            "---\nid: TASK-1\nhooks:\n  onStatusChange: touch x\n---\n",
            '---\nid: TASK-1\n"onStatusChange": touch x\n---\n',
            "---\r\nid: TASK-1\r\nonStatusChange: touch x\r\n---\r\n",
        )
        for text in samples:
            with self.subTest(text=text):
                self.assertEqual([key.lower() for key in guard.scan_text(text)], ["onstatuschange"])

    def test_check_raises_exit_4_naming_the_file(self):
        guard = seam(self, "guard")
        import tempfile

        with tempfile.TemporaryDirectory(prefix="folio-wp2-guard-") as tmp:
            repo = Path(tmp)
            (repo / "backlog" / "tasks").mkdir(parents=True)
            (repo / "backlog" / "config.yml").write_text("remote_operations: false\n", encoding="utf-8")
            task = repo / "backlog" / "tasks" / "task-1 - One.md"
            task.write_text("---\nid: TASK-1\nON_STATUS_CHANGE: touch x\n---\n", encoding="utf-8")
            with self.assertRaises(guard.GuardRefused) as raised:
                guard.check(repo, task)
            self.assertEqual(raised.exception.exit_code, 4)
            self.assertIn("onStatusChange", str(raised.exception))
            self.assertIn(task.name, str(raised.exception))

            task.write_text("---\nid: TASK-1\n---\n", encoding="utf-8")
            guard.check(repo, task)
            (repo / "backlog" / "config.yml").write_text("remote_operations: false\nonstatuschange: touch x\n", encoding="utf-8")
            with self.assertRaises(guard.GuardRefused) as raised:
                guard.check(repo, task)
            self.assertEqual(raised.exception.exit_code, 4)
            self.assertIn("config.yml", str(raised.exception))

    def test_a_missing_task_file_fails_closed(self):
        guard = seam(self, "guard")
        import tempfile

        with tempfile.TemporaryDirectory(prefix="folio-wp2-guard-") as tmp:
            repo = Path(tmp)
            (repo / "backlog").mkdir()
            (repo / "backlog" / "config.yml").write_text("remote_operations: false\n", encoding="utf-8")
            with self.assertRaises(guard.GuardRefused) as raised:
                guard.check(repo, repo / "backlog" / "tasks" / "task-9 - Gone.md")
            self.assertEqual(raised.exception.exit_code, 4)


class GuardedEditTests(BacklogContractCase):
    """Against the real binary: the refused edit leaves the task file and the sentinel untouched."""

    def client(self, repo):
        adapter = seam(self, "adapter")
        return adapter, adapter.BacklogClient(self.backlog.binary, repo, self.home)

    def poisoned_task(self, repo, key, sentinel):
        self.backlog.run(["task", "create", "Synced task", "-l", "fid:" + FID_HEX], cwd=repo)
        path = self.task_file(repo, "task-1")
        text = path.read_text(encoding="utf-8")
        self.assertIn("status: To Do\n", text)
        path.write_text(text.replace("status: To Do\n", "status: To Do\n" + sentinel_line(key, sentinel), 1), encoding="utf-8")
        return path

    def test_status_edit_on_a_task_with_the_key_is_refused_and_sentinel_absent(self):
        for index, key in enumerate(KEY_SPELLINGS):
            with self.subTest(key=key):
                repo = self.init_repo("repo-%d" % index)
                sentinel = self.root / ("sentinel-%d" % index)
                path = self.poisoned_task(repo, key, sentinel)
                before = path.read_bytes()
                adapter, client = self.client(repo)

                with self.assertRaises(adapter.BacklogError) as raised:
                    client.edit("TASK-1", status="In Progress")

                self.assertEqual(raised.exception.exit_code, 4)
                self.assertIn("onStatusChange", str(raised.exception))
                self.assertFalse(sentinel.exists(), "the hook ran: %s exists" % sentinel)
                self.assertEqual(path.read_bytes(), before, "the task file changed")
                self.assertIn("status: To Do", self.front_matter(path))

    def test_key_in_config_refuses_the_edit_of_a_clean_task(self):
        repo = self.init_repo()
        self.backlog.run(["task", "create", "Clean task"], cwd=repo)
        sentinel = self.root / "sentinel-config"
        with self.config_path(repo).open("a", encoding="utf-8") as handle:
            handle.write(sentinel_line("OnStatusChange", sentinel))
        path = self.task_file(repo, "task-1")
        before = path.read_bytes()
        adapter, client = self.client(repo)

        with self.assertRaises(adapter.BacklogError) as raised:
            client.edit("TASK-1", status="Done")

        self.assertEqual(raised.exception.exit_code, 4)
        self.assertFalse(sentinel.exists())
        self.assertEqual(path.read_bytes(), before)

    def test_any_edit_of_a_poisoned_task_is_refused_not_only_status(self):
        repo = self.init_repo()
        sentinel = self.root / "sentinel-title"
        path = self.poisoned_task(repo, "onStatusChange", sentinel)
        before = path.read_bytes()
        adapter, client = self.client(repo)
        for kwargs in ({"title": "Renamed"}, {"labels": ("fid:" + FID_HEX, "extra")}, {"description": "text"}):
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(adapter.BacklogError) as raised:
                    client.edit("TASK-1", **kwargs)
                self.assertEqual(raised.exception.exit_code, 4)
        self.assertFalse(sentinel.exists())
        self.assertEqual(path.read_bytes(), before)

    def test_edit_of_a_clean_task_in_a_clean_repo_goes_through(self):
        repo = self.init_repo()
        self.backlog.run(["task", "create", "Clean task"], cwd=repo)
        adapter, client = self.client(repo)
        client.edit("TASK-1", status="In Progress")
        self.assertIn("status: In Progress", self.front_matter(self.task_file(repo, "task-1")))

    def test_view_and_list_still_work_on_a_poisoned_task_reads_are_not_guarded(self):
        repo = self.init_repo()
        self.poisoned_task(repo, "onStatusChange", self.root / "sentinel-read")
        adapter, client = self.client(repo)
        self.assertEqual(client.view("TASK-1")["id"], "TASK-1")
        self.assertEqual([task["id"] for task in client.list()], ["TASK-1"])
        self.assertFalse((self.root / "sentinel-read").exists())


class GuardOrderingTests(FakeBacklogCase):
    """The guard runs before the binary is spawned for the edit."""

    def test_refused_edit_spawns_no_edit_subprocess(self):
        adapter = seam(self, "adapter")
        task = self.repo / "backlog" / "tasks" / "task-1 - One.md"
        task.write_text("---\nid: TASK-1\ntitle: One\nstatus: To Do\nonStatusChange: touch x\n---\n", encoding="utf-8")
        binary = self.fake("1.53.0", ((
            ["task", "view"],
            '{"schemaVersion": 1, "kind": "task-view", "task": {"id": "TASK-1", "title": "One", "status": "To Do", '
            '"labels": [], "path": "backlog/tasks/task-1 - One.md"}}',
            0,
        ),))
        client = adapter.BacklogClient(str(binary), self.repo, self.home)
        with self.assertRaises(adapter.BacklogError) as raised:
            client.edit("TASK-1", status="Done")
        self.assertEqual(raised.exception.exit_code, 4)
        self.assertEqual([argv[:2] for argv in argvs(self.log) if argv[:2] == ["task", "edit"]], [])


if __name__ == "__main__":
    unittest.main()
