"""ADR-0001 Backlog.md facts 1-6, executed against the pinned 1.53.0 binary.

Each test builds its own temporary repo with `init --defaults`, a temporary HOME and
`auto_open_browser: false`. Run with:
FOLIO_BACKLOG_BIN=<binary> python3 -m unittest discover -s tests -p "test_backlog_*.py" -v
"""

import json

from .support import BacklogContractCase

PINS = ("remote_operations", "check_active_branches", "auto_commit")


class StorageAndReadsTests(BacklogContractCase):
    """Fact 1: one Markdown file per task; reads emit schemaVersion 1 JSON."""

    def test_list_json_has_no_description_or_path_and_view_json_adds_them(self):
        repo = self.init_repo()
        self.backlog.run(["task", "create", "First task", "-d", "Body text"], cwd=repo)

        self.assertEqual(self.task_files(repo), ["task-1 - First-task.md"])
        listed = json.loads(self.backlog.run(["task", "list", "--json"], cwd=repo).stdout)
        self.assertEqual((listed["schemaVersion"], listed["kind"]), (1, "task-list"))
        self.assertEqual([task["id"] for task in listed["tasks"]], ["TASK-1"])
        self.assertNotIn("description", listed["tasks"][0])
        self.assertNotIn("path", listed["tasks"][0])

        viewed = json.loads(self.backlog.run(["task", "view", "TASK-1", "--json"], cwd=repo).stdout)
        self.assertEqual((viewed["schemaVersion"], viewed["kind"]), (1, "task-view"))
        task = viewed["task"]
        self.assertEqual(task["path"], "backlog/tasks/task-1 - First-task.md")
        self.assertEqual(task["description"], "Body text")
        for key in ("implementationPlan", "implementationNotes", "comments"):
            self.assertIn(key, task)

    def test_create_has_no_json_and_no_explicit_id_option(self):
        repo = self.init_repo()
        for option in (["--json"], ["--id", "TASK-9"]):
            with self.subTest(option=option):
                result = self.backlog.run(["task", "create", "Refused", *option], cwd=repo, check=False)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("unknown option '%s'" % option[0], result.stderr)
        self.assertEqual(self.task_files(repo), [])
        self.assertIn("Created task TASK-1", self.backlog.run(["task", "create", "Plain"], cwd=repo).stdout)


class ProjectListsTests(BacklogContractCase):
    """Fact 2: `--project` accepts only values from the `projects:` list in config.yml."""

    def test_project_needs_a_configured_projects_list(self):
        repo = self.init_repo()
        result = self.backlog.run(["task", "create", "Orphan", "--project", "Alpha"], cwd=repo, check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("No projects are configured", result.stderr)
        self.assertEqual(self.task_files(repo), [])

        refused = self.backlog.run(["config", "set", "projects", "Alpha"], cwd=repo, check=False)
        self.assertNotEqual(refused.returncode, 0)
        self.assertIn("projects cannot be set directly", refused.stderr)

    def test_configured_projects_are_matched_case_insensitively_and_enforced(self):
        repo = self.init_repo()
        self.set_projects(repo, "Alpha", "Beta")
        self.assertEqual(self.backlog.run(["config", "get", "projects"], cwd=repo).stdout.strip(), "Alpha, Beta")

        self.backlog.run(["task", "create", "Planned", "--project", "alpha"], cwd=repo)
        self.assertIn("project: Alpha", self.front_matter(self.task_file(repo, "task-1")))
        invalid = self.backlog.run(["task", "create", "Elsewhere", "--project", "Gamma"], cwd=repo, check=False)
        self.assertNotEqual(invalid.returncode, 0)
        self.assertIn("Invalid project: Gamma. Valid projects are: Alpha, Beta", invalid.stderr)

        listed = json.loads(self.backlog.run(["task", "list", "--json"], cwd=repo).stdout)
        self.assertEqual([(task["id"], task["project"]) for task in listed["tasks"]], [("TASK-1", "Alpha")])


class EditPreservationTests(BacklogContractCase):
    """Fact 3: unknown front-matter keys are dropped on edit; labels survive."""

    def test_unknown_key_dropped_and_fid_label_survives_status_edit(self):
        repo = self.init_repo()
        self.backlog.run(["task", "create", "Labelled", "-l", "fid:abc123,other"], cwd=repo)
        path = self.task_file(repo, "task-1")
        text = path.read_text(encoding="utf-8")
        self.assertIn("status: To Do\n", text)
        path.write_text(text.replace("status: To Do\n", "status: To Do\nchannel: example-channel\n", 1), encoding="utf-8")
        self.assertIn("channel: example-channel", self.front_matter(path))

        self.backlog.run(["task", "edit", "TASK-1", "-s", "In Progress"], cwd=repo)

        front = self.front_matter(path)
        self.assertIn("status: In Progress", front)
        self.assertFalse([line for line in front if line.startswith("channel:")], front)
        labels = front.index("labels:")
        self.assertEqual(front[labels + 1:labels + 3], ["  - 'fid:abc123'", "  - other"])
        viewed = json.loads(self.backlog.run(["task", "view", "TASK-1", "--json"], cwd=repo).stdout)
        self.assertEqual(viewed["task"]["labels"], ["fid:abc123", "other"])


class TitleFoldTests(BacklogContractCase):
    """Fact 4: long titles fold to `title: >-`; the filename slug comes from the title."""

    def test_title_fold_boundary(self):
        repo = self.init_repo()
        plain = "x" * 78
        long_word = "x" * 79
        spaced = "Box offline task " + "y" * 63
        self.assertEqual(len(spaced), 80)
        for title in (plain, long_word, spaced):
            self.backlog.run(["task", "create", title], cwd=repo)

        self.assertIn("title: " + plain, self.front_matter(self.task_file(repo, "task-1")))
        front = self.front_matter(self.task_file(repo, "task-2"))
        self.assertEqual(front[1:3], ["title: >-", "  " + long_word])
        front = self.front_matter(self.task_file(repo, "task-3"))
        self.assertEqual(front[1:4], ["title: >-", "  Box offline task", "  " + "y" * 63])
        self.assertEqual(self.task_file(repo, "task-3").name, "task-3 - Box-offline-task-" + "y" * 63 + ".md")

        viewed = json.loads(self.backlog.run(["task", "view", "TASK-3", "--json"], cwd=repo).stdout)
        self.assertEqual(viewed["task"]["title"], spaced)


class DuplicateIdTests(BacklogContractCase):
    """Fact 5: IDs collide across clones; `doctor --fix --yes` renumbers and verifies."""

    def make_collision(self):
        bare = self.root / "origin.git"
        self.git(self.root, "init", "-q", "--bare", "-b", "main", str(bare))
        seed = self.init_repo("seed")
        self.backlog.run(["task", "create", "Seed task"], cwd=seed)
        self.git(seed, "add", "-A")
        self.git(seed, "commit", "-q", "-m", "seed")
        self.git(seed, "remote", "add", "origin", str(bare))
        self.git(seed, "push", "-q", "origin", "main")
        clones = {}
        for name, title in (("a", "Laptop offline task"), ("b", "Box offline task")):
            clone = self.root / name
            self.git(self.root, "clone", "-q", str(bare), str(clone))
            created = self.backlog.run(["task", "create", title], cwd=clone)
            self.assertIn("Created task TASK-2", created.stdout)
            self.git(clone, "add", "-A")
            self.git(clone, "commit", "-q", "-m", name)
            clones[name] = clone
        self.git(clones["a"], "push", "-q", "origin", "main")
        self.git(clones["b"], "pull", "--rebase", "-q", "origin", "main")
        return clones["b"]

    def test_two_offline_clones_both_create_task_2_without_git_conflict(self):
        repo = self.make_collision()
        self.assertEqual(self.git(repo, "status", "--porcelain").stdout, "")
        self.assertEqual(
            self.task_files(repo),
            ["task-1 - Seed-task.md", "task-2 - Box-offline-task.md", "task-2 - Laptop-offline-task.md"],
        )
        doctor = self.backlog.run(["doctor"], cwd=repo, check=False)
        self.assertEqual(doctor.returncode, 1)
        self.assertIn("ID-based commands are blocked until the collision is repaired", doctor.stdout)
        blocked = self.backlog.run(["task", "view", "TASK-2", "--json"], cwd=repo, check=False)
        self.assertNotEqual(blocked.returncode, 0)
        self.assertIn("Task ID TASK-2 is ambiguous; 2 files match", blocked.stderr)

    def test_doctor_fix_renumbers_the_later_file_and_verifies(self):
        repo = self.make_collision()
        fixed = self.backlog.run(["doctor", "--fix", "--yes"], cwd=repo)
        self.assertIn("No textual references to the duplicate IDs", fixed.stdout)
        self.assertIn(
            "backlog/tasks/task-2 - Laptop-offline-task.md -> backlog/tasks/task-3 - Laptop-offline-task.md (TASK-2 -> TASK-3)",
            fixed.stdout,
        )
        self.assertIn("Verification passed: no duplicate active/completed task IDs remain.", fixed.stdout)
        self.assertEqual(
            self.task_files(repo),
            ["task-1 - Seed-task.md", "task-2 - Box-offline-task.md", "task-3 - Laptop-offline-task.md"],
        )
        self.assertIn("id: TASK-3", self.front_matter(self.task_file(repo, "task-3")))
        self.assertEqual(self.backlog.run(["doctor"], cwd=repo).returncode, 0)
        listed = json.loads(self.backlog.run(["task", "list", "--json"], cwd=repo).stdout)
        self.assertEqual(
            [(task["id"], task["title"]) for task in listed["tasks"]],
            [("TASK-1", "Seed task"), ("TASK-2", "Box offline task"), ("TASK-3", "Laptop offline task")],
        )

    def test_task_prefix_is_read_only_in_config_list(self):
        repo = self.init_repo()
        self.assertIn("taskPrefix: task (read-only)", self.backlog.run(["config", "list"], cwd=repo).stdout)


class ConfigPinTests(BacklogContractCase):
    """Fact 6: the safety pins and the absence of `onStatusChange` in a fresh config."""

    def pin_values(self, repo):
        lines = self.config_text(repo).splitlines()
        return {key: [line for line in lines if line.startswith(key + ":")] for key in PINS}

    def test_git_init_with_branch_and_remote_checks_off_has_all_pins_false(self):
        repo = self.init_repo()
        self.assertEqual(self.pin_values(repo), {key: [key + ": false"] for key in PINS})
        self.assertNotIn("onStatusChange", self.config_text(repo))

    def test_no_git_init_defaults_has_all_pins_false(self):
        repo = self.init_repo(git_repo=False, extra=("--no-git",))
        self.assertEqual(self.pin_values(repo), {key: [key + ": false"] for key in PINS})
        self.assertIn("filesystem_only: true\n", self.config_text(repo))
        self.assertNotIn("onStatusChange", self.config_text(repo))

    def test_plain_git_init_defaults_turns_remote_and_branch_checks_on(self):
        # Measured at 1.53.0: in a git repo, bare `init --defaults` does NOT set these pins to false,
        # so the adapter must pass --check-branches false --include-remote false (or --no-git).
        repo = self.init_repo(extra=())
        self.assertEqual(
            self.pin_values(repo),
            {
                "remote_operations": ["remote_operations: true"],
                "check_active_branches": ["check_active_branches: true"],
                "auto_commit": ["auto_commit: false"],
            },
        )
        self.assertNotIn("onStatusChange", self.config_text(repo))
