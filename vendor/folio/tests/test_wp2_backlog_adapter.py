"""WP-2 red tests: BacklogClient list/view/create/edit/doctor (+ doc), fid resolution, cache, refusals.

Round trips run against the pinned 1.53.0 binary (FOLIO_BACKLOG_BIN, fail-not-skip as in the WP-1
contract suite). Behaviour that needs a controllable binary (re-list resolution, cache keys, HOME,
no-write) runs against the recording fake from wp2_support.
"""

import os
import re
import subprocess
import time
import unittest
from pathlib import Path

from backlog_contract.support import BacklogContractCase
from wp2_support import FID_HEX, FakeBacklogCase, argvs, seam, task_list_json, tree_digest

FID_RE = re.compile(r"^[0-9a-f]{16}$")
REFUSED_TITLES = ("--help", "-rf", "-", "--", "-s", "-h", "--json")
BULK_TASKS = 200


class AdapterCase(BacklogContractCase):
    def client(self, repo):
        adapter = seam(self, "adapter")
        return adapter, adapter.BacklogClient(self.backlog.binary, repo, self.home)


class RoundTripTests(AdapterCase):
    def test_create_edit_view_round_trip(self):
        repo = self.init_repo()
        adapter, client = self.client(repo)

        created = client.create("Round trip", description="Body text", labels=("other",))
        self.assertRegex(created.fid, FID_RE)
        self.assertEqual(created.id, "TASK-1")
        self.assertEqual(self.task_files(repo), ["task-1 - Round-trip.md"])

        viewed = client.view(created.id)
        self.assertEqual((viewed["id"], viewed["title"], viewed["status"]), ("TASK-1", "Round trip", "To Do"))
        self.assertEqual(viewed["description"], "Body text")
        self.assertEqual(viewed["labels"], ["fid:" + created.fid, "other"])

        client.edit(created.id, status="In Progress", title="Round trip edited")
        viewed = client.view(created.id)
        self.assertEqual((viewed["title"], viewed["status"]), ("Round trip edited", "In Progress"))
        self.assertEqual(viewed["labels"], ["fid:" + created.fid, "other"], "the fid label survives an edit")
        self.assertEqual([task["id"] for task in client.list()], ["TASK-1"])

    def test_create_assigns_a_fresh_fid_and_honours_a_preassigned_one(self):
        repo = self.init_repo()
        adapter, client = self.client(repo)
        first = client.create("One")
        second = client.create("Two")
        self.assertNotEqual(first.fid, second.fid)
        third = client.create("Three", fid=FID_HEX)
        self.assertEqual((third.fid, third.id), (FID_HEX, "TASK-3"))
        self.assertEqual(client.view("TASK-3")["labels"], ["fid:" + FID_HEX])

    def test_resolve_finds_a_task_created_outside_folio_by_its_fid_label(self):
        repo = self.init_repo()
        adapter, client = self.client(repo)
        self.backlog.run(["task", "create", "Raw CLI task", "-l", "fid:" + FID_HEX], cwd=repo)
        self.assertEqual(client.resolve(FID_HEX), "TASK-1")
        with self.assertRaises(adapter.BacklogError):
            client.resolve("f" * 16)

    def test_doc_create_view_update_round_trip(self):
        repo = self.init_repo()
        adapter, client = self.client(repo)
        doc_id = client.doc_create("List notes", content="First body")
        self.assertEqual(doc_id, "doc-1")
        doc = client.doc_view(doc_id)
        self.assertEqual((doc["id"], doc["title"]), ("doc-1", "List notes"))
        self.assertEqual(doc["content"].strip(), "First body")
        client.doc_update(doc_id, content="Second body\nwith two lines")
        self.assertEqual(client.doc_view(doc_id)["content"].strip(), "Second body\nwith two lines")

    def test_view_of_an_unknown_task_is_a_backlog_error_not_a_crash(self):
        repo = self.init_repo()
        adapter, client = self.client(repo)
        with self.assertRaises(adapter.BacklogError) as raised:
            client.view("TASK-404")
        self.assertNotEqual(raised.exception.exit_code, 0)


class DoctorTests(AdapterCase):
    def test_doctor_passes_on_a_fresh_pinned_repo(self):
        repo = self.init_repo()
        adapter, client = self.client(repo)
        client.doctor()

    def test_doctor_fails_when_remote_operations_is_true(self):
        repo = self.init_repo()
        config = self.config_path(repo)
        text = self.config_text(repo)
        self.assertIn("remote_operations: false\n", text)
        config.write_text(text.replace("remote_operations: false\n", "remote_operations: true\n", 1), encoding="utf-8")
        adapter, client = self.client(repo)
        with self.assertRaises(adapter.BacklogError) as raised:
            client.doctor()
        self.assertIn("remote_operations", str(raised.exception))

    def test_doctor_fails_when_the_binary_reports_a_duplicate_id(self):
        repo = self.init_repo()
        self.backlog.run(["task", "create", "Original"], cwd=repo)
        original = self.task_file(repo, "task-1")
        duplicate = original.with_name("task-1 - Duplicate.md")
        duplicate.write_text(original.read_text(encoding="utf-8").replace("title: Original", "title: Duplicate"), encoding="utf-8")
        adapter, client = self.client(repo)
        with self.assertRaises(adapter.BacklogError):
            client.doctor()


class TitleAndArgvRefusalTests(AdapterCase):
    def test_option_like_titles_are_refused_before_any_file_exists(self):
        repo = self.init_repo()
        adapter, client = self.client(repo)
        for title in REFUSED_TITLES:
            with self.subTest(title=title):
                with self.assertRaises(adapter.BacklogError) as raised:
                    client.create(title)
                self.assertEqual(raised.exception.exit_code, 4)
        self.assertEqual(self.task_files(repo), [])

    def test_title_over_79_characters_is_refused_and_79_is_accepted(self):
        repo = self.init_repo()
        adapter, client = self.client(repo)
        with self.assertRaises(adapter.BacklogError) as raised:
            client.create("x" * 80)
        self.assertEqual(raised.exception.exit_code, 4)
        self.assertEqual(self.task_files(repo), [])
        created = client.create("y" * 79)
        self.assertEqual(client.view(created.id)["title"], "y" * 79)

    def test_edit_title_has_the_same_cap_and_dash_refusal(self):
        repo = self.init_repo()
        adapter, client = self.client(repo)
        created = client.create("Short")
        for title in ("z" * 80, "--help", "-rf"):
            with self.subTest(title=title):
                with self.assertRaises(adapter.BacklogError) as raised:
                    client.edit(created.id, title=title)
                self.assertEqual(raised.exception.exit_code, 4)
        self.assertEqual(client.view(created.id)["title"], "Short")


class FakeBinaryTests(FakeBacklogCase):
    """Contract points that need a scripted binary."""

    def client(self, responses=()):
        adapter = seam(self, "adapter")
        binary = self.fake("1.53.0", responses)
        return adapter, adapter.BacklogClient(str(binary), self.repo, self.home)

    def test_create_resolves_task_id_by_relisting_not_from_create_stdout(self):
        # The create banner says TASK-1; the authoritative list puts the fid on TASK-7.
        adapter, client = self.client((
            (["task", "create"], "Created task TASK-1\nFile: x\n", 0),
            (["task", "list"], task_list_json(("TASK-7", "Fake", ["fid:" + FID_HEX]), ("TASK-1", "Other", [])), 0),
        ))
        created = client.create("Fake", fid=FID_HEX)
        self.assertEqual((created.fid, created.id), (FID_HEX, "TASK-7"))
        recorded = argvs(self.log)
        self.assertEqual(recorded[0][:2], ["task", "create"])
        self.assertIn("fid:" + FID_HEX, " ".join(recorded[0]))
        self.assertIn(["task", "list", "--json"], recorded[1:])

    def test_create_whose_fid_is_not_listed_afterwards_is_an_error(self):
        adapter, client = self.client((
            (["task", "create"], "Created task TASK-1\n", 0),
            (["task", "list"], task_list_json(("TASK-1", "Fake", ["other"])), 0),
        ))
        with self.assertRaises(adapter.BacklogError):
            client.create("Fake", fid=FID_HEX)

    def test_every_subprocess_runs_with_the_temp_home(self):
        adapter, client = self.client((
            (["task", "list"], task_list_json(("TASK-1", "Fake", [])), 0),
        ))
        client.list()
        self.assert_temp_home_everywhere()

    def test_option_like_values_in_any_field_never_reach_the_binary(self):
        adapter, client = self.client()
        attempts = (
            lambda: client.create("Fine", description="--desc"),
            lambda: client.create("Fine", labels=("-l",)),
            lambda: client.create("Fine", labels=("ok", "--remove-label")),
            lambda: client.create("Fine", status="-s"),
            lambda: client.create("Fine", priority="--priority"),
            lambda: client.create("Fine", project="-p"),
            lambda: client.view("--help"),
            lambda: client.view("-rf"),
            lambda: client.edit("--help", status="Done"),
            lambda: client.edit("TASK-1", status="-s"),
            lambda: client.edit("TASK-1", labels=("-x",)),
            lambda: client.doc_create("--help"),
            lambda: client.doc_view("-rf"),
            lambda: client.doc_update("doc-1", content="--content"),
            lambda: client.resolve("--help"),
        )
        for index, attempt in enumerate(attempts):
            with self.subTest(attempt=index):
                with self.assertRaises(adapter.BacklogError) as raised:
                    attempt()
                self.assertEqual(raised.exception.exit_code, 4)
        self.assertEqual(argvs(self.log), [], "a refused value must not spawn the binary")

    def test_nonzero_exit_from_the_binary_is_a_backlog_error_with_stderr(self):
        adapter, client = self.client(((["task", "view"], "", 1),))
        with self.assertRaises(adapter.BacklogError):
            client.view("TASK-1")

    def test_adapter_writes_nothing_under_backlog_itself(self):
        (self.repo / "backlog" / "tasks" / "task-1 - Fake.md").write_text(
            "---\nid: TASK-1\ntitle: Fake\nstatus: To Do\nlabels:\n  - 'fid:%s'\n---\n" % FID_HEX, encoding="utf-8")
        before = tree_digest(self.repo / "backlog")
        adapter, client = self.client((
            (["task", "create"], "Created task TASK-1\n", 0),
            (["task", "list"], task_list_json(("TASK-1", "Fake", ["fid:" + FID_HEX])), 0),
            (["task", "view"], '{"schemaVersion": 1, "kind": "task-view", "task": {"id": "TASK-1", "title": "Fake", '
                               '"status": "To Do", "labels": ["fid:%s"], "path": "backlog/tasks/task-1 - Fake.md"}}' % FID_HEX, 0),
            (["doc", "create"], "Created document doc-1\nPath: backlog/docs/doc-1 - Notes.md\n", 0),
            (["doctor"], "No duplicate IDs, self-referential dependencies, or dependency cycles found.\n", 0),
        ))
        client.create("Fake", fid=FID_HEX)
        client.list()
        client.view("TASK-1")
        client.edit("TASK-1", status="Done")
        client.doc_create("Notes", content="body")
        client.doctor()
        self.assertEqual(tree_digest(self.repo / "backlog"), before)
        self.assertGreaterEqual(len(argvs(self.log)), 5)


class CacheTests(AdapterCase):
    def bulk_tasks(self, repo, count=BULK_TASKS):
        self.backlog.run(["task", "create", "Bulk 1"], cwd=repo)
        template = self.task_file(repo, "task-1").read_text(encoding="utf-8")
        self.assertIn("id: TASK-1\n", template)
        self.assertIn("title: Bulk 1\n", template)
        tasks = Path(repo) / "backlog" / "tasks"
        for number in range(2, count + 1):
            text = template.replace("id: TASK-1\n", "id: TASK-%d\n" % number, 1).replace("title: Bulk 1\n", "title: Bulk %d\n" % number, 1)
            (tasks / ("task-%d - Bulk-%d.md" % (number, number))).write_text(text, encoding="utf-8")
        self.assertEqual(len(self.task_files(repo)), count)

    def test_second_list_of_200_tasks_is_served_from_cache_in_under_50ms(self):
        repo = self.init_repo()
        self.bulk_tasks(repo)
        adapter, client = self.client(repo)
        cold = client.list()
        self.assertEqual(len(cold), BULK_TASKS)
        started = time.perf_counter()
        warm = client.list()
        elapsed = time.perf_counter() - started
        self.assertEqual([task["id"] for task in warm], [task["id"] for task in cold])
        self.assertLess(elapsed, 0.050, "second list took %.1f ms" % (elapsed * 1000))

    def test_cache_is_invalidated_by_a_task_file_edit_in_place(self):
        repo = self.init_repo()
        self.backlog.run(["task", "create", "Before"], cwd=repo)
        adapter, client = self.client(repo)
        self.assertEqual([task["title"] for task in client.list()], ["Before"])
        path = self.task_file(repo, "task-1")
        path.write_text(path.read_text(encoding="utf-8").replace("title: Before", "title: After", 1), encoding="utf-8")
        stat = path.stat()
        os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns + 2_000_000_000))
        self.assertEqual([task["title"] for task in client.list()], ["After"])

    def test_cache_is_invalidated_by_a_task_created_outside_the_client(self):
        repo = self.init_repo()
        self.backlog.run(["task", "create", "One"], cwd=repo)
        adapter, client = self.client(repo)
        self.assertEqual(len(client.list()), 1)
        self.backlog.run(["task", "create", "Two"], cwd=repo)
        self.assertEqual([task["id"] for task in client.list()], ["TASK-1", "TASK-2"])

    def test_client_writes_through_the_binary_refresh_the_list(self):
        repo = self.init_repo()
        adapter, client = self.client(repo)
        self.assertEqual(client.list(), [])
        created = client.create("Fresh")
        self.assertEqual([task["id"] for task in client.list()], [created.id])
        client.edit(created.id, status="Done")
        self.assertEqual([task["status"] for task in client.list()], ["Done"])


class CacheKeyTests(FakeBacklogCase):
    def setUp(self):
        super().setUp()
        # subprocess here builds the git fixture only; backlog is never spawned by the tests themselves.
        self.git = lambda *args: subprocess.run(
            ["git", *args], cwd=str(self.repo), check=True, stdin=subprocess.DEVNULL, capture_output=True,
            env={"HOME": str(self.home), "PATH": os.environ.get("PATH", "/usr/bin:/bin"), "GIT_CONFIG_NOSYSTEM": "1",
                 "GIT_AUTHOR_NAME": "WP2", "GIT_AUTHOR_EMAIL": "wp2@example.com",
                 "GIT_COMMITTER_NAME": "WP2", "GIT_COMMITTER_EMAIL": "wp2@example.com"},
        )
        self.git("init", "-q", "-b", "main")
        (self.repo / "backlog" / "tasks" / "task-1 - One.md").write_text("---\nid: TASK-1\ntitle: One\nstatus: To Do\n---\n", encoding="utf-8")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "one")

    def client(self):
        adapter = seam(self, "adapter")
        binary = self.fake("1.53.0", ((["task", "list"], task_list_json(("TASK-1", "One", [])), 0),))
        return adapter.BacklogClient(str(binary), self.repo, self.home)

    def list_calls(self):
        return [argv for argv in argvs(self.log) if argv[:2] == ["task", "list"]]

    def test_unchanged_tasks_and_head_spawn_the_binary_once(self):
        client = self.client()
        client.list()
        client.list()
        client.list()
        self.assertEqual(len(self.list_calls()), 1)

    def test_a_new_head_invalidates_the_cache_without_any_task_change(self):
        client = self.client()
        client.list()
        (self.repo / "README.md").write_text("unrelated\n", encoding="utf-8")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "two")
        client.list()
        self.assertEqual(len(self.list_calls()), 2)

    def test_a_task_file_mtime_bump_invalidates_the_cache(self):
        client = self.client()
        client.list()
        path = self.repo / "backlog" / "tasks" / "task-1 - One.md"
        stat = path.stat()
        os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns + 2_000_000_000))
        client.list()
        self.assertEqual(len(self.list_calls()), 2)

    def test_a_new_task_file_invalidates_the_cache(self):
        client = self.client()
        client.list()
        (self.repo / "backlog" / "tasks" / "task-2 - Two.md").write_text("---\nid: TASK-2\ntitle: Two\nstatus: To Do\n---\n", encoding="utf-8")
        client.list()
        self.assertEqual(len(self.list_calls()), 2)


if __name__ == "__main__":
    unittest.main()
