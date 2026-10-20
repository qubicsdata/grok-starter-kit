"""WP-5a red tests: the local ApprovalLog at $XDG_STATE_HOME/folio/approvals.jsonl.

Security: the file is created 0600, every open uses O_NOFOLLOW, and a symlink (live or dangling), a
FIFO, a directory or a file with any other mode is refused without changing anything (the
local_auth.py:15-21 checks). Acceptance: notifications are de-duplicated across a restart, and the
trace is local only and holds no command text or note (M-6).
"""

import json
import os
import stat
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

from wp5_support import FID, USER, FakeProvider, RecordingNotifier, StateCase, decision, mode_of

POSIX = os.name != "nt"


class LogPathTests(StateCase):
    def test_default_path_is_under_xdg_state_home(self):
        module = self.approvals()
        self.assertEqual(module.default_log_path({"XDG_STATE_HOME": str(self.state), "HOME": "/nonexistent/fixture-home"}),
                         self.state / "folio" / "approvals.jsonl")

    def test_default_path_falls_back_to_home_local_state(self):
        module = self.approvals()
        home = self.dir / "home"
        self.assertEqual(module.default_log_path({"HOME": str(home)}), home / ".local" / "state" / "folio" / "approvals.jsonl")
        for value in ("", "relative/state", "./state"):
            with self.subTest(XDG_STATE_HOME=value):
                self.assertEqual(module.default_log_path({"HOME": str(home), "XDG_STATE_HOME": value}),
                                 home / ".local" / "state" / "folio" / "approvals.jsonl")

    def test_log_without_a_path_uses_the_environment(self):
        module = self.approvals()
        self.assertEqual(module.ApprovalLog(environ=self.environ).path, self.log_path)


@unittest.skipUnless(POSIX, "POSIX file modes and O_NOFOLLOW")
class LogFileSecurityTests(StateCase):
    def record(self, log):
        log.record_resolution("fake", "dec_00000000000000a1", "approve", FID)

    def test_created_file_is_0600_whatever_the_umask(self):
        for umask in (0, 0o022, 0o277):
            with self.subTest(umask=oct(umask)):
                previous = os.umask(umask)
                try:
                    self.record(self.log())
                finally:
                    os.umask(previous)
                self.assertTrue(stat.S_ISREG(os.lstat(self.log_path).st_mode))
                self.assertEqual(mode_of(self.log_path), 0o600)
                # A restrictive umask must not leave a log that every later open refuses.
                self.record(self.log())
                self.assertEqual(len(self.log().records()), 2)
                self.log_path.unlink()

    def test_first_creation_under_a_restrictive_umask_leaves_usable_private_folders(self):
        previous = os.umask(0o277)
        try:
            self.record(self.log())
        finally:
            os.umask(previous)
        self.assertEqual(mode_of(self.log_path), 0o600)
        for directory in (self.state, self.state / "folio"):
            self.assertEqual(mode_of(directory), 0o700, directory)
        self.record(self.log())
        self.assertEqual(len(self.log().records()), 2)

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
        self.assertTrue(flags, "the log was never opened through os.open (builtin open() cannot pass O_NOFOLLOW)")
        for flag in flags:
            self.assertTrue(flag & os.O_NOFOLLOW, "an open of approvals.jsonl lacks O_NOFOLLOW: flags=%#o" % flag)

    def test_symlink_to_a_private_file_is_refused_on_write_and_read(self):
        module = self.approvals()
        target = self.dir / "elsewhere.jsonl"
        target.write_text('{"type": "resolution"}\n', encoding="utf-8")
        target.chmod(0o600)
        self.log_path.parent.mkdir(parents=True)
        self.log_path.symlink_to(target)
        log = self.log()
        with self.assertRaises(module.ApprovalLogError):
            self.record(log)
        with self.assertRaises(module.ApprovalLogError):
            log.records()
        with self.assertRaises(module.ApprovalLogError):
            log.claim_notifications("fake", ["dec_00000000000000a2"])
        self.assertEqual(target.read_text(encoding="utf-8"), '{"type": "resolution"}\n')
        self.assertTrue(self.log_path.is_symlink())

    def test_dangling_symlink_is_refused_and_its_target_is_not_created(self):
        module = self.approvals()
        target = self.dir / "planted.jsonl"
        self.log_path.parent.mkdir(parents=True)
        self.log_path.symlink_to(target)
        with self.assertRaises(module.ApprovalLogError):
            self.record(self.log())
        self.assertFalse(target.exists(), "O_CREAT followed a dangling symlink")

    def test_existing_file_with_another_mode_is_refused_and_left_unchanged(self):
        module = self.approvals()
        self.log_path.parent.mkdir(parents=True)
        for mode in (0o644, 0o640, 0o660, 0o700, 0o400):
            with self.subTest(mode=oct(mode)):
                self.log_path.write_text("", encoding="utf-8")
                self.log_path.chmod(mode)
                log = self.log()
                with self.assertRaises(module.ApprovalLogError):
                    self.record(log)
                with self.assertRaises(module.ApprovalLogError):
                    log.records()
                self.assertEqual(mode_of(self.log_path), mode, "the mode was silently changed")
                self.assertEqual(self.log_path.read_bytes(), b"")
                self.log_path.chmod(0o600)
                self.log_path.unlink()

    def test_directory_in_place_of_the_log_is_refused(self):
        module = self.approvals()
        self.log_path.mkdir(parents=True)
        with self.assertRaises(module.ApprovalLogError):
            self.record(self.log())
        with self.assertRaises(module.ApprovalLogError):
            self.log().records()

    def test_fifo_in_place_of_the_log_is_refused_without_blocking(self):
        module = self.approvals()
        self.log_path.parent.mkdir(parents=True)
        os.mkfifo(self.log_path, 0o600)
        outcomes = []

        def attempt(operation):
            try:
                operation()
                outcomes.append("accepted")
            except module.ApprovalLogError:
                outcomes.append("refused")
            except Exception as error:  # reported below with its type
                outcomes.append(error.__class__.__name__)

        log = self.log()
        for name, operation in (("write", lambda: self.record(log)), ("read", log.records)):
            outcomes.clear()
            worker = threading.Thread(target=attempt, args=(operation,), daemon=True)
            worker.start()
            worker.join(3)
            blocked = worker.is_alive()
            deadline = time.monotonic() + 5
            while worker.is_alive() and time.monotonic() < deadline:
                # Release a blocked open() by opening the other end, so the suite never hangs.
                try:
                    descriptor = os.open(self.log_path, os.O_RDWR | os.O_NONBLOCK)
                    os.close(descriptor)
                except OSError:
                    pass
                worker.join(0.1)
            with self.subTest(operation=name):
                self.assertFalse(blocked, "%s blocked on a FIFO (open without O_NONBLOCK)" % name)
                self.assertEqual(outcomes, ["refused"])

    def test_a_fifo_is_refused_as_not_a_regular_file_before_any_read(self):
        # The refusal must come from the file-type check, not from a later seek or read failing by accident.
        module = self.approvals()
        self.log_path.parent.mkdir(parents=True)
        os.mkfifo(self.log_path, 0o600)
        # Hold both ends open, so even an open without O_NONBLOCK returns (that case is the test above).
        keeper = os.open(self.log_path, os.O_RDWR | os.O_NONBLOCK)
        self.addCleanup(os.close, keeper)
        log = self.log()
        for operation in (log.records, lambda: self.record(log)):
            with self.assertRaises(module.ApprovalLogError) as caught:
                operation()
            self.assertIn("not a regular file", str(caught.exception))

    def test_a_log_owned_by_another_account_is_refused(self):
        module = self.approvals()
        self.record(self.log())
        before = self.log_path.read_bytes()
        with mock.patch("os.getuid", return_value=os.getuid() + 1):
            log = self.log()
            for operation in (log.records, lambda: self.record(log), lambda: log.claim_notifications("fake", ["dec_00000000000000a2"])):
                with self.assertRaises(module.ApprovalLogError):
                    operation()
        self.assertEqual(self.log_path.read_bytes(), before)

    def test_a_refused_log_refuses_the_resolve_before_the_dialog_opens(self):
        target = self.dir / "elsewhere.jsonl"
        target.write_text("", encoding="utf-8")
        target.chmod(0o600)
        self.log_path.parent.mkdir(parents=True)
        self.log_path.symlink_to(target)
        provider = FakeProvider([decision("a1")])
        inbox = self.inbox(provider, {"choice": "approve", "text": ""})
        with self.assertRaises(Exception):
            inbox.resolve("dec_00000000000000a1", {"requested": "approve"}, USER)
        self.assertEqual(self.dialog.asked, [], "the dialog opened although the trace could not be written")
        self.assertEqual(provider.calls, [])
        self.assertEqual(target.read_bytes(), b"")


class ResolutionRecordTests(StateCase):
    def test_resolution_line_has_exactly_the_m6_fields(self):
        log = self.log()
        log.record_resolution("fake", "dec_00000000000000a1", "approve", FID)
        lines = self.log_path.read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(lines), 1)
        record = json.loads(lines[0])
        self.assertEqual(set(record), {"type", "ts", "provider", "decision_id", "choice", "fid"})
        self.assertEqual({key: record[key] for key in ("type", "provider", "decision_id", "choice", "fid")},
                         {"type": "resolution", "provider": "fake", "decision_id": "dec_00000000000000a1", "choice": "approve", "fid": FID})
        self.assertTrue(record["ts"])

    def test_log_is_append_only(self):
        log = self.log()
        log.record_resolution("fake", "dec_00000000000000a1", "approve", FID)
        first = self.log_path.read_bytes()
        log.record_resolution("fake", "dec_00000000000000a2", "deny", None)
        self.assertTrue(self.log_path.read_bytes().startswith(first))
        self.assertEqual([item["decision_id"] for item in self.log().records() if item["type"] == "resolution"],
                         ["dec_00000000000000a1", "dec_00000000000000a2"])

    def test_a_resolution_records_only_a_choice_and_a_folio_task_id(self):
        log = self.log()
        for choice, fid in (("cancel", FID), ("answer", FID), ("approve", "pytest -q"), ("deny", "TASK-1"), ("approve", FID.upper())):
            with self.subTest(choice=choice, fid=fid):
                with self.assertRaises(ValueError):
                    log.record_resolution("fake", "dec_00000000000000a1", choice, fid)
        self.assertEqual(log.records(), [])

    def test_a_trace_that_fails_after_the_provider_acted_is_reported_not_raised(self):
        module = self.approvals()
        provider = FakeProvider([decision("a1", fid=FID)])
        inbox = self.inbox(provider, {"choice": "approve", "text": ""})
        with mock.patch.object(inbox.log, "record_resolution", side_effect=module.ApprovalLogError("disk full")):
            result = inbox.resolve("dec_00000000000000a1", {"requested": "approve"}, USER)
        self.assertEqual(result["result"], "approved")
        self.assertIn("could not record it locally", result["warning"])
        self.assertEqual([call["choice"] for call in provider.calls], ["approve"])

    def test_a_torn_last_line_does_not_swallow_the_next_record(self):
        log = self.log()
        log.record_resolution("fake", "dec_00000000000000a1", "approve", FID)
        with open(self.log_path, "ab") as handle:  # a crash part-way through an append
            handle.write(b'{"type":"notif')
        log.record_resolution("fake", "dec_00000000000000a2", "deny", None)
        self.assertEqual(log.claim_notifications("fake", ["dec_00000000000000a3"]), ["dec_00000000000000a3"])
        self.assertEqual([item["decision_id"] for item in self.resolution_records()], ["dec_00000000000000a1", "dec_00000000000000a2"])
        self.assertEqual(self.log().notified("fake"), {"dec_00000000000000a3"})

    def test_records_on_a_missing_file_is_empty_and_creates_nothing(self):
        self.assertEqual(self.log().records(), [])
        self.assertFalse(self.log_path.exists())
        self.assertFalse(self.log_path.parent.exists())

    def test_resolve_writes_no_command_text_note_or_answer_to_the_log(self):
        item = decision("a1", fid=FID, rememberable=True, task_id=FID, task_title="Run the suite",
                        coordinator_note="Escalated by the coordinator")
        # No fid: nothing else (task id, command, title) may stand in for it.
        loose = decision("a2", task_id="0000000000000002", title="Loose request")
        provider = FakeProvider([item, loose])
        inbox = self.inbox(provider, {"choice": "approve", "text": "Tests only, private note"}, {"choice": "deny", "text": "No thanks"})
        inbox.poll()
        result = inbox.resolve(item["id"], {"requested": "approve", "note": "Tests only, private note"}, USER)
        self.assertEqual(result["result"], "approved")
        self.assertEqual(inbox.resolve(loose["id"], {"requested": "deny"}, USER)["result"], "denied")
        text = self.log_path.read_text(encoding="utf-8")
        for secret in ("pytest -q", "Tests only", "private note", "No thanks", "Escalated", "Run the suite", "Loose request",
                       "0000000000000002", "Confirmed by a person"):
            self.assertNotIn(secret, text)
        self.assertEqual([{key: record[key] for key in ("provider", "decision_id", "choice", "fid")} for record in self.resolution_records()],
                         [{"provider": "fake", "decision_id": item["id"], "choice": "approve", "fid": FID},
                          {"provider": "fake", "decision_id": loose["id"], "choice": "deny", "fid": None}])


class NotificationDedupTests(StateCase):
    def test_notifications_are_deduplicated_across_a_restart(self):
        provider = FakeProvider([decision("a1"), decision("a2")])
        first = RecordingNotifier()
        self.inbox(provider, notifier=first).poll()
        self.assertEqual(len(first.sent), 2)
        self.inbox(provider, notifier=first).poll()
        self.assertEqual(len(first.sent), 2, "the same process notified twice")
        # A restart: a new inbox and a new log object on the same file.
        second = RecordingNotifier()
        self.inbox(provider, log=self.approvals().ApprovalLog(self.log_path), notifier=second).poll()
        self.assertEqual(second.sent, [], "a restart re-notified decisions already announced")
        provider.add(decision("a3"))
        self.inbox(provider, log=self.approvals().ApprovalLog(self.log_path), notifier=second).poll()
        self.assertEqual(len(second.sent), 1)

    def test_claims_persist_and_are_keyed_by_provider(self):
        log = self.log()
        self.assertEqual(log.claim_notifications("fake", ["dec_00000000000000a1", "dec_00000000000000a2"]),
                         ["dec_00000000000000a1", "dec_00000000000000a2"])
        reopened = self.log()
        self.assertEqual(reopened.claim_notifications("fake", ["dec_00000000000000a2", "dec_00000000000000a3"]),
                         ["dec_00000000000000a3"])
        self.assertEqual(reopened.notified("fake"), {"dec_00000000000000a1", "dec_00000000000000a2", "dec_00000000000000a3"})
        self.assertEqual(reopened.claim_notifications("other", ["dec_00000000000000a1"]), ["dec_00000000000000a1"])

    @unittest.skipUnless(POSIX, "flock")
    def test_a_claim_waits_for_a_concurrent_claim_from_another_log_object(self):
        # Two log objects stand for two processes (a server and a CLI): only the file lock orders them.
        first, second = self.log(), self.log()
        appending, results = threading.Event(), []
        real_append = first._append

        def slow_append(descriptor, records, **options):
            appending.set()
            time.sleep(0.3)
            real_append(descriptor, records, **options)

        first._append = slow_append
        worker = threading.Thread(target=lambda: results.append(first.claim_notifications("fake", ["dec_00000000000000a1"])))
        worker.start()
        self.assertTrue(appending.wait(5))
        self.assertEqual(second.claim_notifications("fake", ["dec_00000000000000a1"]), [], "both claims notified the same decision")
        worker.join(5)
        self.assertEqual(results, [["dec_00000000000000a1"]])

    def test_seen_markers_survive_a_restart(self):
        self.log().mark_seen("fake", "dec_00000000000000a1")
        self.assertEqual(self.log().seen("fake"), {"dec_00000000000000a1"})
        self.assertEqual(self.log().seen("other"), set())

    def test_notification_records_hold_no_command_text(self):
        provider = FakeProvider([decision("a1", title="codex:worker-1 requests permission")])
        self.inbox(provider).poll()
        text = self.log_path.read_text(encoding="utf-8")
        self.assertNotIn("pytest -q", text)
        self.assertNotIn("requests permission", text)

    def test_a_refused_log_sends_no_notification(self):
        target = self.dir / "elsewhere.jsonl"
        target.write_text("", encoding="utf-8")
        target.chmod(0o600)
        self.log_path.parent.mkdir(parents=True)
        self.log_path.symlink_to(target)
        notifier = RecordingNotifier()
        inbox = self.inbox(FakeProvider([decision("a1")]), notifier=notifier)
        try:
            inbox.poll()
        except Exception:
            pass
        self.assertEqual(notifier.sent, [], "without a writable claim, every poll would notify again")
        self.assertEqual(target.read_bytes(), b"")


if __name__ == "__main__":
    unittest.main()
