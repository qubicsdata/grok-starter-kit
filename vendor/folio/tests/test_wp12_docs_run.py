"""WP-12 doc-test harness, part 2 (runs): every row of tests/wp12_support.py ROWS is exercised here.

doc-test, gate and external rows run offline in a temporary HOME with the documented argv (placeholders
filled; server commands get `--port 0` so no fixed port is taken). Backlog.md rows use the pinned 1.53.0
binary from FOLIO_BACKLOG_BIN through BacklogRunner, and fail without it like the contract suite (the
explicit opt-out is FOLIO_BACKLOG_CONTRACT=skip). Pending rows first prove the command is missing from
this tree, then skip with a reason naming the WP and its branch; a tripwire fails once that WP's seam
lands. Smoke and manual rows are never run; their argv is checked against this tree.
"""

import json
import os
import re
import shutil
import stat
import subprocess
import sys
import unittest
from datetime import date
from pathlib import Path

from backlog_contract.support import BacklogContractCase

import wp12_support as support
from wp12_support import (DOCS, PUBLIC_INSTALL_URL, REPO_ROOT, WP9, WP10, WP11, WP14, DocCase, doc_text, exercises, fences, fill,
                          key, pending_skip, project_name, row, sha256_of, tripwire)

FOLIO = REPO_ROOT / "folio"
SERVER_PORT = ("--port", "0")
LAUNCH_URL = re.compile(r"^http://127\.0\.0\.1:(\d+)/#folio-launch=[a-f0-9]{64}$")


def last_json(text):
    """The last top-level JSON object of a CLI's stdout (the server banner may come first)."""
    starts = [match.start() for match in re.finditer(r"(?m)^\{", text)]
    return json.loads(text[starts[-1]:]) if starts else None


def envelope(test, result):
    try:
        payload = last_json(result.stdout)
    except ValueError:
        payload = None
    if not isinstance(payload, dict):
        test.fail("no JSON envelope on stdout: %r" % result.stdout[-500:])
    return payload


class FolioCliDocTests(DocCase):
    @exercises("folio --version")
    def test_folio_version_prints_this_trees_version(self):
        from folio import __version__
        self.assertEqual(self.run_doc("folio --version").stdout, "folio %s\n" % __version__)

    @exercises("folio doctor")
    def test_folio_doctor_runs_read_only_in_a_fresh_home(self):
        report = envelope(self, self.run_doc("folio doctor"))
        self.assertTrue(report["ok"])
        self.assertTrue(report["data"]["ok"], report)
        self.assertEqual(report["data"]["workspace"], str(self.workspace.resolve()))
        self.assertFalse(self.workspace.exists(), "folio doctor must not create the workspace")

    def server_info(self):
        path = self.workspace / ".server.json"
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None

    @exercises("folio ui --no-open", "folio server-stop")
    def test_ui_no_open_starts_a_server_without_printing_a_credential_and_server_stop_ends_it(self):
        process = self.start_doc("folio ui --no-open", extra=SERVER_PORT)
        self.wait_for(lambda: self.server_info() is not None, process, "the discovery file")
        info = self.server_info()
        self.assertTrue(info.get("owner_token") and info.get("browser_token"), "discovery lists both credentials")
        self.assertEqual(stat.S_IMODE((self.workspace / ".server.json").stat().st_mode), 0o600)
        stopped = envelope(self, self.run_doc("folio server-stop"))
        self.assertTrue(stopped["ok"], stopped)
        output, errors = process.communicate(timeout=30)
        self.assertEqual(process.returncode, 0, errors)
        for credential in (info["owner_token"], info["browser_token"]):
            self.assertNotIn(credential, output + errors)
        self.assertEqual(last_json(output), {"ok": True, "data": {"stopped": True}})
        self.assertFalse((self.workspace / ".server.json").exists(), "the server removes its discovery file on close")
        again = self.run_doc("folio server-stop", check=False)
        self.assertEqual((again.returncode, envelope(self, again)["error"]["code"]), (2, "NOT_FOUND"))

    @exercises("folio ui")
    def test_ui_opens_the_browser_on_an_authenticated_launch_url(self):
        opened = self.root / "opened.txt"
        recorder = self.root / "record-browser"
        recorder.write_text("#!%s\nimport sys\nopen(%r, 'w').write(sys.argv[1])\n" % (sys.executable, str(opened)), encoding="utf-8")
        recorder.chmod(0o700)
        env = dict(self.env, BROWSER=str(recorder))
        process = self.start_doc("folio ui", extra=SERVER_PORT, env=env)
        self.wait_for(opened.exists, process, "the browser launch")
        self.wait_for(lambda: LAUNCH_URL.match(opened.read_text(encoding="utf-8")), process, "the launch URL")
        url = opened.read_text(encoding="utf-8")
        self.assertEqual(int(LAUNCH_URL.match(url).group(1)), self.server_info()["port"])
        self.run_doc("folio server-stop", env=env)
        output, errors = process.communicate(timeout=30)
        self.assertEqual(process.returncode, 0, errors)
        self.assertNotIn(url.split("#", 1)[1], output + errors, "the launch fragment never reaches the terminal")

    @exercises('folio brief <list> --query "release plan"', "folio source <source-id> --project <list>")
    def test_brief_and_source_on_a_synthetic_list(self):
        self.folio("clients", "add", "--name", "client-alpha")
        self.folio("projects", "add", "--client", "client-alpha", "--name", "release-plan",
                   "--description", "Release plan for the example.com beta, in two steps.")
        brief = envelope(self, self.run_doc('folio brief <list> --query "release plan"', list="release-plan"))
        records = brief["data"]["records"]
        self.assertEqual(brief["data"]["query"], "release plan")
        project = next(record for record in records if record["kind"] == "project")
        self.assertIn("Release plan for the example.com beta", project["text"])
        source = envelope(self, self.run_doc("folio source <source-id> --project <list>", list="release-plan",
                                             **{"source-id": project["source"]}))
        self.assertEqual((source["data"]["text"], source["data"]["hash"]), (project["text"], project["hash"]))


def iterate(suite):
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from iterate(item)
        else:
            yield item


class GateDocTests(DocCase):
    @exercises("python3 -m unittest discover -s tests -v")
    def test_the_gate_command_discovers_this_suite_without_import_errors(self):
        """Not run inside itself: the documented discover call is replayed in-process and must load cleanly."""
        argv = key(row("python3 -m unittest discover -s tests -v").command)
        self.assertEqual(argv[:4], ("python3", "-m", "unittest", "discover"))
        self.assertIn("-v", argv)
        loader = unittest.TestLoader()
        suite = loader.discover(str(REPO_ROOT / argv[argv.index("-s") + 1]))
        self.assertEqual(loader.errors, [])
        ids = {test.id().split(".", 1)[-1] for test in iterate(suite)}
        self.assertIn(self.id().split(".", 1)[-1], ids)
        self.assertGreater(len(ids), 600)

    @exercises("node --check folio/static/app.js")
    def test_node_check_passes_on_the_app_script(self):
        self.run_doc("node --check folio/static/app.js", cwd=REPO_ROOT)

    @exercises("scripts/ci-local.sh")
    def test_ci_local_names_the_documented_gate_stages(self):
        """The full run would run this suite inside itself; --help is the documented stage list."""
        self.assertTrue(os.access(REPO_ROOT / "scripts" / "ci-local.sh", os.X_OK))
        text = self.run_doc("scripts/ci-local.sh", cwd=REPO_ROOT, extra=("--help",)).stdout
        for stage in ("python3 -m unittest discover -s tests -v", "node --check folio/static/app.js"):
            self.assertIn(stage, text)


class ExternalDocTests(DocCase):
    @exercises("sha256sum example-channel-allow-list.json", "sha256sum folio-final-backup.json", "sha256sum dry-run-report.json")
    def test_sha256sum_prints_the_hash_the_reviewer_compares(self):
        for name in ("example-channel-allow-list.json", "folio-final-backup.json", "dry-run-report.json"):
            with self.subTest(name=name):
                path = self.root / name
                path.write_text('{"schema_version": 1, "entries": [{"id": "client-alpha", "channel": "example-channel"}]}\n', encoding="utf-8")
                self.assertEqual(self.run_doc("sha256sum %s" % name).stdout, "%s  %s\n" % (sha256_of(path), name))

    def synthetic_workspace(self):
        workspace = self.root / "workspace"
        project = workspace / "clients" / "client-alpha" / "projects" / "release-plan" / ".task-manager"
        project.mkdir(parents=True)
        (workspace / "registry.json").write_text('{"schema_version": 1, "clients": [], "projects": []}\n', encoding="utf-8")
        (project / "project.json").write_text('{"schema_version": 1, "name": "release-plan"}\n', encoding="utf-8")

        def thaw():
            for path in [workspace, *workspace.rglob("*")]:
                path.chmod(stat.S_IMODE(path.stat().st_mode) | 0o700 if path.is_dir() else 0o600)
        self.addCleanup(thaw)
        return workspace

    @exercises("chmod -R a-w <workspace>", "chmod -R u+w <workspace>")
    def test_freeze_makes_the_source_read_only_and_thaw_restores_the_owner(self):
        workspace = self.synthetic_workspace()
        entries = [workspace, *sorted(workspace.rglob("*"))]
        hashes = {path: sha256_of(path) for path in entries if path.is_file()}
        self.run_doc("chmod -R a-w <workspace>", workspace=workspace)
        self.assertEqual([path for path in entries if path.stat().st_mode & 0o222], [])
        self.assertEqual({path: sha256_of(path) for path in hashes}, hashes)
        self.run_doc("chmod -R u+w <workspace>", workspace=workspace)
        self.assertEqual([path for path in entries if not path.stat().st_mode & 0o200], [])

    def repo_with_main(self):
        repo = self.root / "tasks-example-channel"
        (repo / "backlog" / "tasks").mkdir(parents=True)
        self.git(repo, "init", "-q", "-b", "main")
        (repo / "backlog" / "config.yml").write_text("project_name: \"tasks-example-channel\"\nauto_open_browser: false\n", encoding="utf-8")
        self.git(repo, "add", "-A")
        self.git(repo, "commit", "-q", "-m", "chore: bootstrap")
        return repo

    def migration_commit(self, repo, number, list_name):
        (repo / "backlog" / "tasks" / ("task-%d - Migrated-task.md" % number)).write_text(
            "---\nid: TASK-%d\ntitle: Migrated task\nproject: %s\nlabels:\n  - fid:%016x\n---\n" % (number, list_name, number), encoding="utf-8")
        self.git(repo, "add", "-A")
        self.git(repo, "commit", "-q", "-m", "migrate: %s\n\nFolio-Op: task.migrate" % list_name)
        return self.git(repo, "rev-parse", "HEAD").strip()

    @exercises("git checkout main", "git branch -D folio-migration/<date>")
    def test_rollback_of_an_unmerged_migration_branch_drops_the_local_branch(self):
        repo = self.repo_with_main()
        main = self.git(repo, "rev-parse", "HEAD").strip()
        today = date.today().isoformat()
        self.git(repo, "checkout", "-q", "-b", "folio-migration/" + today)
        self.migration_commit(repo, 1, "release-plan")
        self.run_doc("git checkout main", cwd=repo)
        self.run_doc("git branch -D folio-migration/<date>", cwd=repo, date=today)
        self.assertEqual(self.git(repo, "branch", "--list", "folio-migration/*"), "")
        self.assertEqual(self.git(repo, "rev-parse", "HEAD").strip(), main)
        self.assertEqual(sorted(repo.rglob("task-*.md")), [])

    @exercises("git revert --no-edit <first-migration-commit>^..<last-migration-commit>")
    def test_rollback_of_a_merged_migration_reverts_its_commits(self):
        repo = self.repo_with_main()
        base = self.git(repo, "rev-parse", "HEAD").strip()
        first = self.migration_commit(repo, 1, "release-plan")
        last = self.migration_commit(repo, 2, "ops-notes")
        self.run_doc("git revert --no-edit <first-migration-commit>^..<last-migration-commit>", cwd=repo,
                     **{"first-migration-commit": first, "last-migration-commit": last})
        self.assertEqual(self.git(repo, "diff", "--stat", base, "HEAD"), "")
        self.assertEqual(self.git(repo, "rev-list", "--count", base + "..HEAD").strip(), "4")

    @exercises("uv tool upgrade folio-workspace", "uv tool uninstall folio-workspace")
    def test_uv_upgrade_and_uninstall_name_this_distribution(self):
        name = project_name()
        for command in ("uv tool upgrade folio-workspace", "uv tool uninstall folio-workspace"):
            argv = key(row(command).command)
            with self.subTest(command=command):
                self.assertEqual(argv[-1], name, "uv tools are named by the distribution in pyproject.toml")
                uv = shutil.which("uv")
                if uv:
                    env = dict(self.env, UV_CACHE_DIR=str(self.root / "uv-cache"), UV_NO_CONFIG="1")
                    result = subprocess.run([uv, *argv[1:3], "--help"], env=env, cwd=str(self.root), stdin=subprocess.DEVNULL,
                                            capture_output=True, text=True, timeout=self.TIMEOUT)
                    self.assertEqual(result.returncode, 0, result.stderr)


class BacklogDocTests(BacklogContractCase):
    @exercises("cd <clone>", "backlog task list --plain", "backlog task list --json --project <list>", "backlog doctor")
    def test_the_count_check_and_the_terminal_view_on_a_synthetic_clone(self):
        clone = self.init_repo("tasks-example-channel")
        self.set_projects(clone, "release-plan", "ops-notes")
        for title, project, fid in (("Draft the release plan", "release-plan", "0123456789abcdef"),
                                    ("Rotate the example.com certificate", "ops-notes", "fedcba9876543210")):
            self.backlog.run(["task", "create", title, "--project", project, "--labels", "fid:" + fid], cwd=clone)
        argv = fill(key(row("cd <clone>").command), {"clone": clone})
        self.assertEqual(argv[0], "cd")
        cwd = Path(argv[1])
        self.assertTrue(cwd.is_dir())

        def backlog(command, **values):
            argv = fill(key(row(command).command), values)
            self.assertEqual(argv[0], "backlog")
            return self.backlog.run(argv[1:], cwd=cwd)

        plain = backlog("backlog task list --plain").stdout
        self.assertIn("Draft the release plan", plain)
        self.assertIn("Rotate the example.com certificate", plain)
        listed = json.loads(backlog("backlog task list --json --project <list>", list="release-plan").stdout)
        self.assertEqual([(task["title"], task["project"], task["labels"]) for task in listed["tasks"]],
                         [("Draft the release plan", "release-plan", ["fid:0123456789abcdef"])])
        self.assertIn("No duplicate IDs", backlog("backlog doctor").stdout)


class SmokeAndManualDocTests(DocCase):
    @exercises('uv tool install "%s"' % PUBLIC_INSTALL_URL, 'pipx install "%s"' % PUBLIC_INSTALL_URL)
    def test_the_one_command_install_pins_the_public_git_url(self):
        for command in ('uv tool install "%s"' % PUBLIC_INSTALL_URL, 'pipx install "%s"' % PUBLIC_INSTALL_URL):
            argv = key(row(command).command)
            self.assertEqual(argv[-1], PUBLIC_INSTALL_URL)
        self.assertTrue(PUBLIC_INSTALL_URL.startswith("git+https://github.com/example-org/folio-oss@"))
        scripts = support.PYPROJECT.read_text(encoding="utf-8")
        for entry in ('folio = "folio.cli:main"', 'folio-server = "folio.web:main"'):
            self.assertIn(entry, scripts, "the install puts the documented commands on PATH")
        self.skipTest("smoke only: the one-command install needs the network and the published repository (WP-0b flip); "
                      "the clean-machine install check of WP-9 (wp/9-install) runs it")

    @exercises('ssh-keygen -t ed25519 -f ~/.ssh/folio_tasks_example_channel -C "folio tasks-example-channel"', "cat ~/.ssh/folio_tasks_example_channel.pub",
               "git clone git@tasks-example-channel:example-org/tasks-example-channel.git")
    def test_the_deploy_key_rows_agree_with_each_other_and_with_the_host_alias(self):
        """Manual (a credential and the network): never run; the key path, alias and repository must agree."""
        keygen = key(row('ssh-keygen -t ed25519 -f ~/.ssh/folio_tasks_example_channel -C "folio tasks-example-channel"').command)
        self.assertEqual(keygen[keygen.index("-t") + 1], "ed25519")
        key_path = keygen[keygen.index("-f") + 1]
        self.assertEqual(key(row("cat ~/.ssh/folio_tasks_example_channel.pub").command)[1], key_path + ".pub")
        clone = key(row("git clone git@tasks-example-channel:example-org/tasks-example-channel.git").command)
        self.assertEqual(clone[2].partition(":")[::2], ("git@tasks-example-channel", "example-org/tasks-example-channel.git"))
        wanted = {"Host tasks-example-channel", "HostName github.com", "User git", "IdentityFile " + key_path, "IdentitiesOnly yes"}
        for doc in DOCS:
            text = doc_text(doc) or ""
            if "ssh-keygen" not in text:
                continue
            with self.subTest(doc=doc):
                blocks, _problems = fences(text)
                configs = [{line.strip() for _number, line in body} for _start, info, body in blocks if info == "text"]
                self.assertTrue(any(wanted <= lines for lines in configs), "%s needs the ssh host alias block %s" % (doc, sorted(wanted)))

    @exercises("folio-1.1.2 server-stop", "folio-1.1.2 backup --output folio-final-backup.json", "folio-1.1.2 ui")
    def test_the_old_launcher_rows_are_manual_and_backup_is_not_a_command_of_this_tree(self):
        """The final backup needs the 1.1.2 launcher: WP-6 cut `folio backup` from this tree."""
        for command in ("folio-1.1.2 server-stop", "folio-1.1.2 backup --output folio-final-backup.json", "folio-1.1.2 ui"):
            self.assertEqual(row(command).kind, "manual")
        _owner, problem = support.check_folio_argv(("folio", "backup", "--output", "folio-final-backup.json"))
        self.assertIsNotNone(problem)
        result = self.folio("backup", "--output", str(self.root / "backup.json"), check=False)
        self.assertEqual(result.returncode, 1)
        self.assertFalse((self.root / "backup.json").exists())

    @exercises('rm -r "${XDG_STATE_HOME:-$HOME/.local/state}/folio"')
    def test_the_state_removal_row_names_folios_state_folder(self):
        """Manual (it deletes): the shell default must be the folder Folio's local state uses."""
        from folio.approvals import default_log_path
        target = key(row('rm -r "${XDG_STATE_HOME:-$HOME/.local/state}/folio"').command)[-1]
        match = re.fullmatch(r"\$\{XDG_STATE_HOME:-\$HOME(/[^}]*)\}(/.*)", target)
        self.assertIsNotNone(match, target)
        for environ, base in (({"HOME": str(self.home)}, str(self.home) + match.group(1)),
                              ({"HOME": str(self.home), "XDG_STATE_HOME": str(self.root / "state")}, str(self.root / "state"))):
            with self.subTest(environ=sorted(environ)):
                self.assertEqual(Path(base + match.group(2)), default_log_path(environ).parent)


class PendingDocTests(DocCase):
    """Rows whose code is on a landed branch that is not on this stack (M-20/r2)."""

    def assert_missing_here(self, command, **values):
        result = self.run_doc(command, check=False, **values)
        payload = envelope(self, result)
        self.assertEqual((result.returncode, payload["error"]["code"]), (1, "USAGE"), "%r is in this tree" % command)

    @exercises("folio tools ensure", "folio tools verify")
    def test_wp9_tools_commands_and_the_doctor_pin_line(self):
        tripwire(self, (FOLIO / "locks", FOLIO / "backlog" / "lock.py"), "WP-9", "folio tools ensure|verify and the doctor pin")
        self.assert_missing_here("folio tools ensure")
        self.assert_missing_here("folio tools verify")
        checks = envelope(self, self.run_doc("folio doctor"))["data"]["checks"]
        self.assertNotIn("backlog", [check["name"] for check in checks], "WP-9's doctor pin line landed: assert it here")
        pending_skip(self, WP9, "`folio tools ensure|verify` and the pinned version and lock sha256 in `folio doctor`")

    @exercises("folio repos add <path> --channel example-channel", "folio sync --repo <path>", "folio repair-ids --repo <path>",
               "folio repair-ids --repo <path> --yes")
    def test_wp10_repository_registration_sync_and_repair_ids(self):
        tripwire(self, (FOLIO / "sync.py", FOLIO / "backlog" / "outbox.py"), "WP-10", "repos add, sync --repo and repair-ids")
        clone = self.root / "tasks-example-channel"
        clone.mkdir()
        for command in ("folio repos add <path> --channel example-channel", "folio sync --repo <path>", "folio repair-ids --repo <path>",
                        "folio repair-ids --repo <path> --yes"):
            with self.subTest(command=command):
                self.assert_missing_here(command, path=clone)
        self.assertEqual(sorted(path.name for path in clone.iterdir()), [])
        pending_skip(self, WP10, "`folio repos add`, `folio sync --repo` and `folio repair-ids --repo`")

    @exercises("folio migrate --from <workspace> --inventory",
               "folio migrate --from <workspace> --dry-run --allow-list example-channel-allow-list.json --report dry-run-report.json",
               "folio migrate --from <workspace> --apply --allow-list example-channel-allow-list.json --reviewed <allow-list-sha256> --to <clone>")
    def test_wp11_migrate_inventory_dry_run_and_apply(self):
        tripwire(self, (FOLIO / "migrate", FOLIO / "migrate.py"), "WP-11", "folio migrate")
        values = {"workspace": self.root / "workspace", "clone": self.root / "tasks-example-channel", "allow-list-sha256": "0" * 64}
        for command in [r.command for r in support.ROWS if r.owner == WP11 and r.kind == "pending"]:
            with self.subTest(command=command):
                self.assert_missing_here(command, **values)
        self.assertFalse((self.root / "dry-run-report.json").exists())
        pending_skip(self, WP11, "`folio migrate --inventory|--dry-run|--apply`")

    @exercises("folio usage report")
    def test_wp14_usage_report(self):
        tripwire(self, (FOLIO / "usage.py",), "WP-14", "folio usage report")
        self.assert_missing_here("folio usage report")
        pending_skip(self, WP14, "`folio usage report`")


if __name__ == "__main__":
    unittest.main()
