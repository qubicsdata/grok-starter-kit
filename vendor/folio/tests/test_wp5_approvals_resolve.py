"""WP-5a red tests: the DecisionProvider interface, the resolve flow through the reused native dialog,
and the no-provider empty state (interface level only; the empty-state UI is WP-5b).

Acceptance: WP-1's approvals goldens pass with a fake provider; resolving leaves the tasks repo
`git status` unchanged. Security: a dialog timeout counts as Cancel; the provider is never called
without a dialog result; with no provider, resolve is unreachable. No real dialog, notification or
provider is ever started: every process is a fake. The WP-1 goldens are read, never rewritten.
"""

import hashlib
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from folio.core import AppError
from folio.dialogs import ConfirmDialog, DialogBusy, DialogUnavailable

from wp5_support import (CODEX, FID, GOLDENS, USER, FakeProvider, RecordingNotifier, ScriptedDialog, StateCase, decision,
                         python_child_argv, seam)

CANCELLED = (409, "HUMAN_CONFIRMATION_CANCELLED")
ENVIRON = {"DISPLAY": ":0", "HOME": "/nonexistent/fixture-home", "LANG": "C.UTF-8", "PATH": "/usr/bin"}


def golden(name):
    return json.loads((GOLDENS / ("%s.json" % name)).read_text(encoding="utf-8"))


def outcome_of(call):
    try:
        return call()
    except AppError as error:
        return {"error": str(error), "status": error.status, "code": error.code}


class InterfaceTests(StateCase):
    def test_decision_provider_declares_pending_show_and_resolve(self):
        module = self.approvals()
        provider = module.DecisionProvider()
        for call in (provider.pending, lambda: provider.show("dec_00000000000000a1"),
                     lambda: provider.resolve("dec_00000000000000a1", "approve", None)):
            with self.assertRaises(NotImplementedError):
                call()

    def test_the_dialog_defaults_to_the_native_confirm_dialog(self):
        module = self.approvals()
        inbox = module.Approvals(FakeProvider(), log=self.log(), environ=self.environ)
        self.assertIsInstance(inbox.dialog, ConfirmDialog)

    def test_status_with_a_provider_lists_its_pending_decisions(self):
        provider = FakeProvider([decision("a1"), decision("a2", "review")])
        inbox = self.inbox(provider)
        self.assertTrue(inbox.configured)
        status = inbox.status()
        self.assertIs(status["configured"], True)
        self.assertEqual([item["id"] for item in status["decisions"]], ["dec_00000000000000a1", "dec_00000000000000a2"])


class GoldenWithFakeProviderTests(StateCase):
    """The WP-1 approvals goldens (tests/characterization/goldens/approvals_*.json) through the inbox."""

    def test_pending_decisions_pass_through_unchanged(self):
        normalized = golden("approvals_normalized")
        provider = FakeProvider(list(normalized.values()))
        inbox = self.inbox(provider)
        by_id = {item["id"]: name for name, item in normalized.items()}
        self.assertEqual({by_id[item["id"]]: item for item in inbox.status()["decisions"]}, normalized)
        self.assertEqual({by_id[item["id"]]: item for item in inbox.poll()}, normalized)

    def test_dialog_messages_match_the_golden(self):
        normalized = golden("approvals_normalized")
        cases = {
            "command_remember_cli": ("command", "approve", True, CODEX),
            "command_ui": ("command", "deny", False, USER),
            "write_paths_remember": ("write_paths", "approve", True, {"origin": "cli", "via": None}),
            "unknown_tool_note": ("unknown_tool", "approve", False, USER),
            "question_options": ("question_options", "answer", False, USER),
            "copilot_question": ("copilot_question", "answer", False, {"origin": "cli", "via": "cli:copilot"}),
            "review": ("review", "approve", False, USER),
            "hidden_characters": ("hidden_characters", "approve", False, USER),
        }
        shown = {}
        for name, (key, requested, remember, actor) in cases.items():
            provider = FakeProvider([normalized[key]])
            inbox = self.inbox(provider, {"choice": "cancel", "text": ""})
            data = {"requested": requested, "remember": remember}
            if requested == "answer":
                data["answer"] = ""
            outcome_of(lambda: inbox.resolve(normalized[key]["id"], data, actor))
            self.assertEqual(len(self.dialog.asked), 1, name)
            self.assertEqual(self.dialog.asked[0]["title"], "Folio · Switchboard decision", name)
            self.assertIs(self.dialog.asked[0]["allow_text"], True, name)
            shown[name] = self.dialog.asked[0]["message"].split("\n")
            self.assertEqual(provider.calls, [], name)
        self.maxDiff = None
        self.assertEqual(shown, golden("approvals_dialog_messages"))

    def test_resolve_results_and_refusals_match_the_golden(self):
        normalized = golden("approvals_normalized")
        permission, question = normalized["command"], normalized["copilot_question"]

        def run(provider, item, data, actor, *outcomes):
            inbox = self.inbox(provider, *outcomes)
            before = len(provider.calls)
            result = outcome_of(lambda: inbox.resolve(item["id"], data, actor))
            sent = provider.sent()[before:]
            return json.loads(json.dumps({"result": result, "sent": sent}).replace(item["id"], "<decision_id>"))

        def fresh(data, actor, *outcomes):
            return run(FakeProvider([permission]), permission, data, actor, *outcomes)

        result = {
            "approve_remember_cli": fresh({"requested": "approve", "remember": True, "note": "Tests only"}, CODEX,
                                          {"choice": "approve", "text": "Tests only"}),
            "clicked_deny_wins_ui": fresh({"requested": "approve", "remember": True}, USER, {"choice": "deny", "text": ""}),
            "cancel_sends_nothing": fresh({"requested": "approve"}, USER, {"choice": "cancel", "text": ""}),
            "dialog_unavailable": fresh({"requested": "approve"}, USER, DialogUnavailable("none")),
            "dialog_busy": fresh({"requested": "approve"}, USER, DialogBusy("busy")),
            "bad_request": fresh({"requested": "maybe"}, USER),
        }
        provider = FakeProvider([question])
        result["question_needs_text"] = run(provider, question, {"requested": "answer", "answer": ""}, USER, {"choice": "approve", "text": " "})
        result["question_answer"] = run(provider, question, {"requested": "answer", "answer": "eu-west-1"}, USER,
                                        {"choice": "approve", "text": "eu-west-1"})
        result["no_longer_pending"] = run(provider, question, {"requested": "answer", "answer": "x"}, USER)
        self.maxDiff = None
        self.assertEqual(result, golden("approvals_resolve"))


class TimeoutChild:
    """A dialog process that never answers: communicate() times out until it is killed."""

    def __init__(self, tool="/usr/bin/zenity"):
        self.returncode, self.tool, self.killed = None, tool, False

    def communicate(self, timeout=None):
        if not self.killed:
            raise subprocess.TimeoutExpired(self.tool, timeout)
        self.returncode = -9
        return "", ""

    def kill(self):
        self.killed = True

    def terminate(self):
        self.killed = True

    def poll(self):
        return self.returncode


class Child:
    def __init__(self, code, out, before=None):
        self.returncode, self.code, self.out, self.before = None, code, out, before

    def communicate(self, timeout=None):
        if self.before:
            self.before()
        self.returncode = self.code
        return self.out, ""

    def kill(self):
        pass

    def terminate(self):
        pass

    def poll(self):
        return self.returncode


class Spawner:
    def __init__(self, *children):
        self.children, self.calls = list(children), []

    def __call__(self, args, **kwargs):
        self.calls.append(list(args))
        return self.children.pop(0)


class DialogTimeoutIsCancelTests(StateCase):
    """README.md:152: a dialog that is not answered in time counts as Cancel, through the real ConfirmDialog."""

    def resolve_with(self, dialog, spawned):
        provider = FakeProvider([decision("a1", fid=FID)])
        module = self.approvals()
        inbox = module.Approvals(provider, dialog=dialog, notifier=RecordingNotifier(), log=self.log(), environ=self.environ)
        result = outcome_of(lambda: inbox.resolve("dec_00000000000000a1", {"requested": "approve"}, USER))
        self.assertEqual((result.get("status"), result.get("code")), CANCELLED, result)
        self.assertEqual(provider.calls, [], "a timed-out dialog reached the provider")
        self.assertEqual(self.resolution_records(), [])
        self.assertEqual(len(spawned.calls), spawned.expected, "the dialog was not really asked")

    def linux(self, *children, **kwargs):
        spawner = Spawner(*children)
        spawner.expected = len(children)
        return ConfirmDialog(popen=spawner, platform="linux", exists=lambda path: path == "/usr/bin/zenity", environ=ENVIRON,
                             clock=lambda: 500.0, **kwargs), spawner

    def test_first_box_timeout_is_cancel(self):
        self.resolve_with(*self.linux(TimeoutChild()))

    def test_zenity_timeout_exit_status_is_cancel(self):
        self.resolve_with(*self.linux(Child(5, "")))

    def test_approve_then_a_timed_out_note_box_is_cancel(self):
        self.resolve_with(*self.linux(Child(0, ""), TimeoutChild()))

    def test_macos_gave_up_is_cancel(self):
        spawner = Spawner(Child(0, "cancel\n"))
        spawner.expected = 1
        self.resolve_with(ConfirmDialog(popen=spawner, platform="darwin", environ=ENVIRON), spawner)

    def test_macos_osascript_timeout_is_cancel(self):
        spawner = Spawner(TimeoutChild("/usr/bin/osascript"))
        spawner.expected = 1
        self.resolve_with(ConfirmDialog(popen=spawner, platform="darwin", environ=ENVIRON), spawner)

    def test_a_spent_budget_is_cancel_without_a_dialog(self):
        dialog, spawner = self.linux(timeout=0)
        self.resolve_with(dialog, spawner)

    def test_shutdown_while_the_dialog_is_open_is_cancel(self):
        holder = {}
        dialog, spawner = self.linux(Child(0, "", before=lambda: holder["dialog"].close()))
        holder["dialog"] = dialog
        self.resolve_with(dialog, spawner)


class NoResolveWithoutDialogResultTests(StateCase):
    def setUp(self):
        super().setUp()
        self.events = []
        self.item = decision("a1", fid=FID)
        self.provider = FakeProvider([self.item], events=self.events)

    def attempt(self, *outcomes, data=None):
        inbox = self.inbox(self.provider, *outcomes, events=self.events)
        return outcome_of(lambda: inbox.resolve(self.item["id"], data or {"requested": "approve"}, USER))

    def assert_nothing_resolved(self):
        self.assertEqual(self.provider.calls, [])
        self.assertEqual(self.resolution_records(), [])

    def test_anything_but_an_approve_or_deny_click_is_cancel(self):
        for outcome in (None, {}, {"choice": None}, {"choice": "Approve"}, {"choice": "approve "}, {"choice": "answer"},
                        {"choice": "cancel", "text": "approve"}, {"text": "approve"}, {"choice": True}, "approve", ["approve"]):
            with self.subTest(outcome=outcome):
                result = self.attempt(outcome)
                self.assertEqual((result.get("status"), result.get("code")), CANCELLED, result)
                self.assert_nothing_resolved()

    def test_dialog_unavailable_or_busy_never_reaches_the_provider(self):
        self.assertEqual(self.attempt(DialogUnavailable("none"))["code"], "HUMAN_CONFIRMATION_UNAVAILABLE")
        self.assertEqual(self.attempt(DialogBusy("busy"))["code"], "CONFIRMATION_IN_PROGRESS")
        self.assert_nothing_resolved()

    def test_a_dialog_crash_never_reaches_the_provider(self):
        inbox = self.inbox(self.provider, RuntimeError("dialog crashed"))
        with self.assertRaises(Exception):
            inbox.resolve(self.item["id"], {"requested": "approve"}, USER)
        self.assert_nothing_resolved()

    def test_the_provider_is_called_once_after_the_dialog_with_the_clicked_choice(self):
        result = self.attempt({"choice": "deny", "text": ""})
        self.assertEqual(result["result"], "denied")
        self.assertEqual(self.events, ["dialog.ask", "provider.resolve"])
        self.assertEqual([call["choice"] for call in self.provider.calls], ["deny"])
        self.assertEqual([record["choice"] for record in self.resolution_records()], ["deny"])

    def test_an_invalid_request_or_unknown_decision_opens_no_dialog(self):
        self.assertEqual(self.attempt({"choice": "approve", "text": ""}, data={"requested": "maybe"})["status"], 400)
        inbox = self.inbox(self.provider, {"choice": "approve", "text": ""}, events=self.events)
        self.assertEqual(inbox.resolve("dec_00000000000000ff", {"requested": "approve"}, USER),
                         {"result": "no_longer_pending", "decision_id": "dec_00000000000000ff"})
        self.assertNotIn("dialog.ask", self.events)
        self.assert_nothing_resolved()

    def test_reads_never_resolve(self):
        inbox = self.inbox(self.provider, events=self.events)
        inbox.status()
        inbox.poll()
        inbox.poll()
        self.assertEqual(self.events, [])
        self.assert_nothing_resolved()

    def test_resolve_spawns_no_process_and_never_touches_backlog(self):
        spawned = []

        def refuse(*args, **kwargs):
            spawned.append(args[0] if args else kwargs.get("args"))
            raise AssertionError("approvals spawned a process")

        inbox = self.inbox(self.provider, {"choice": "approve", "text": "note"}, events=self.events)
        with mock.patch("subprocess.Popen", side_effect=refuse), mock.patch("os.system", side_effect=refuse), \
                mock.patch("os.posix_spawn", side_effect=refuse, create=True):
            inbox.poll()
            result = inbox.resolve(self.item["id"], {"requested": "approve"}, USER)
        self.assertEqual(result["result"], "approved")
        self.assertEqual(spawned, [])


class EmptyStateTests(StateCase):
    def test_no_provider_shows_the_empty_state(self):
        module = self.approvals()
        self.assertEqual(module.EMPTY_MESSAGE, "No approvals source configured")
        inbox = self.inbox(None, {"choice": "approve", "text": ""})
        self.assertIs(inbox.configured, False)
        status = inbox.status()
        self.assertEqual((status["configured"], status["message"], status["decisions"]),
                         (False, "No approvals source configured", []))
        self.assertEqual(inbox.poll(), [])
        self.assertEqual(self.notifier.sent, [])

    def test_no_provider_makes_resolve_unreachable(self):
        inbox = self.inbox(None, {"choice": "approve", "text": ""})
        result = outcome_of(lambda: inbox.resolve("dec_00000000000000a1", {"requested": "approve"}, USER))
        self.assertEqual((result.get("status"), result.get("code")), (404, "NO_APPROVALS_SOURCE"), result)
        self.assertEqual(self.dialog.asked, [], "the empty state opened a confirmation dialog")
        self.assertFalse(self.log_path.exists())
        self.assertFalse(self.state.exists(), "the empty state wrote local state")


def tree_digest(root):
    return {path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(Path(root).rglob("*")) if path.is_file()}


CHILD = """
import json
from folio.approvals import Approvals
from wp5_support import FID, USER, FakeProvider, RecordingNotifier, ScriptedDialog, decision
inbox = Approvals(FakeProvider([decision("a1", fid=FID)]), dialog=ScriptedDialog({"choice": "approve", "text": "Tests only"}),
                  notifier=RecordingNotifier())
inbox.poll()
print(json.dumps(inbox.resolve("dec_00000000000000a1", {"requested": "approve", "note": "Tests only"}, USER)))
"""


class TasksRepoStaysCleanTests(unittest.TestCase):
    """A resolve run from inside a tasks repo (cwd) writes only the local log under the state home."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="folio-wp5-repo-")
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)
        self.home = self.dir / "home"
        self.home.mkdir()
        self.repo = self.dir / "tasks-repo"
        self.git_env = {"HOME": str(self.home), "PATH": os.environ.get("PATH", "/usr/bin:/bin"), "GIT_CONFIG_NOSYSTEM": "1",
                        "GIT_CONFIG_GLOBAL": os.devnull}
        subprocess.run(["git", "init", "-q", str(self.repo)], env=self.git_env, check=True)
        tasks = self.repo / "backlog" / "tasks"
        tasks.mkdir(parents=True)
        (self.repo / "backlog" / "config.yml").write_text("project_name: Example\nauto_open_browser: false\n", encoding="utf-8")
        (tasks / "task-1 - Example-task.md").write_text("---\nid: TASK-1\ntitle: Example task\nlabels:\n  - fid:%s\n---\n" % FID,
                                                        encoding="utf-8")
        subprocess.run(["git", "add", "-A"], cwd=self.repo, env=self.git_env, check=True)

    def git_status(self):
        return subprocess.run(["git", "status", "--porcelain=v1", "--ignored", "-uall"], cwd=self.repo, env=self.git_env,
                              check=True, capture_output=True, text=True).stdout

    def test_resolve_leaves_git_status_and_the_repo_tree_unchanged(self):
        seam(self)
        variants = {"default": ({}, self.home / ".local" / "state"),
                    "relative_xdg_ignored": ({"XDG_STATE_HOME": "state"}, self.home / ".local" / "state"),
                    "absolute_xdg": ({"XDG_STATE_HOME": str(self.dir / "xdg")}, self.dir / "xdg")}
        for name, (extra, state_home) in variants.items():
            with self.subTest(variant=name):
                before, digest = self.git_status(), tree_digest(self.repo)
                self.assertTrue(before and all(line.startswith("A  ") for line in before.splitlines()), before)
                child = subprocess.run(python_child_argv(CHILD), cwd=self.repo, env={**self.git_env, **extra},
                                       capture_output=True, text=True, timeout=60)
                self.assertEqual(child.returncode, 0, child.stderr[-2000:])
                self.assertEqual(json.loads(child.stdout)["result"], "approved")
                self.assertEqual(tree_digest(self.repo), digest, "the resolve wrote inside the tasks repo")
                self.assertEqual(self.git_status(), before)
                log = state_home / "folio" / "approvals.jsonl"
                self.assertTrue(log.is_file(), "the resolution was not logged at %s" % log)
                self.assertNotIn("Tests only", log.read_text(encoding="utf-8"))
                log.unlink()


if __name__ == "__main__":
    unittest.main()
