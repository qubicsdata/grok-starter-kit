"""Shared helpers for the WP-5a red tests (approvals interface and local log; M-20 split, no UI).

The WP-5a seam does not exist on the base; every test imports it through `seam()` so that a missing
module FAILS with a message naming the seam instead of erroring at import time. No stub module is
added by WP5-1. The contract the tests expect from WP5-2 (names are the wished-for API):

folio/approvals.py
  EMPTY_MESSAGE = "No approvals source configured"
  default_log_path(environ=None) -> Path
      $XDG_STATE_HOME/folio/approvals.jsonl when XDG_STATE_HOME is an absolute path, else
      <HOME>/.local/state/folio/approvals.jsonl (a relative XDG_STATE_HOME is ignored, XDG spec).
  ApprovalLogError(ValueError)
  ApprovalLog(path=None, environ=None)            .path; append-only JSONL, never synced (M-6)
      Every open of .path uses os.open with O_NOFOLLOW (and O_NONBLOCK); the file is created 0600 and an
      existing file must be a regular file owned by this account with mode exactly 0600
      (the local_auth.py:15-21 checks). Anything else raises ApprovalLogError and changes nothing.
      .records() -> [dict]                          (missing file -> [], never creates it)
      .record_resolution(provider, decision_id, choice, fid)
          one line {"type": "resolution", "ts", "provider", "decision_id", "choice", "fid"}; no command
          text, no note, no answer.
      .claim_notifications(provider, decision_ids) -> [ids not claimed before, in order]; persisted
      .notified(provider) -> set;  .mark_seen(provider, decision_id);  .seen(provider) -> set
  DecisionProvider: name (log key), label (human name in messages); pending() -> [decision],
      show(decision_id) -> decision or None, resolve(decision_id, choice, note, remember=False) -> dict.
      The base methods raise NotImplementedError.
  Approvals(provider=None, dialog=None, notifier=None, log=None, environ=None)
      dialog defaults to dialogs.ConfirmDialog (the dialog is reused, never re-implemented).
      .configured -> bool
      .status() -> {"configured", "message" (EMPTY_MESSAGE when no provider), "decisions"}
      .poll() -> pending decisions; notifies each decision once, de-duplicated through the log
      .resolve(decision_id, data, actor) -> the DecisionService result shape (WP-1 goldens):
          no provider -> AppError 404 "NO_APPROVALS_SOURCE", no dialog;
          anything but a dialog dict whose choice is exactly "approve"/"deny" -> AppError 409
          "HUMAN_CONFIRMATION_CANCELLED" (a timeout is Cancel); the provider is called only after the
          dialog, with the clicked choice; a resolution is then appended to the log.
          A refused log (symlink, wrong mode) refuses the resolve before the dialog opens.
folio/api.py
  App.approvals (default: Approvals() with no provider); GET /api/approvals -> status(),
  POST /api/approvals/<decision id>/resolve -> resolve(). Both sit behind the /api auth + CSRF.
"""

import copy
import importlib
import os
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
TESTS = REPO_ROOT / "tests"
APPROVALS_PY = REPO_ROOT / "folio" / "approvals.py"
GOLDENS = TESTS / "characterization" / "goldens"
FID = "0123456789abcdef"
USER = {"origin": "user", "via": None}
CODEX = {"origin": "cli", "via": "cli:codex"}


def seam(case, name="approvals"):
    """Import folio.<name> or fail the test with the missing-seam reason."""
    try:
        return importlib.import_module("folio." + name)
    except ImportError as error:
        case.fail("WP-5a seam folio/%s.py is missing: %s" % (name, error))


def decision(suffix, kind="permission", **fields):
    """A normalized decision (the shape DecisionService.normalize returns, plus an optional fid)."""
    value = {"id": "dec_00000000000000%s" % suffix, "project_id": "a1b2c3d4e5f60718", "project": "Example rollout",
             "kind": kind, "title": "%s request" % kind, "summary": "pytest -q", "command": "pytest -q" if kind == "permission" else None,
             "questions": [], "participant": "codex:worker-1", "task_id": None, "task_title": None, "sb_task_id": None,
             "created_at": 1790000000000, "request": [{"label": "Command", "value": "pytest -q"}] if kind == "permission" else [],
             "coordinator_note": None, "options": [], "rememberable": False, "hidden_characters": False}
    value.update(fields)
    return value


class FakeProvider:
    """A DecisionProvider stand-in: serves fixed decisions and records every resolve call."""

    name = "fake"
    label = "Switchboard"  # the WP-1 goldens name Switchboard in their messages

    def __init__(self, decisions=(), events=None):
        self.decisions = {item["id"]: copy.deepcopy(item) for item in decisions}
        self.order = [item["id"] for item in decisions]
        self.calls = []
        self.events = events if events is not None else []

    def add(self, item):
        self.decisions[item["id"]] = copy.deepcopy(item)
        self.order.append(item["id"])

    def pending(self):
        return [copy.deepcopy(self.decisions[key]) for key in self.order if key in self.decisions]

    def show(self, decision_id):
        item = self.decisions.get(decision_id)
        return copy.deepcopy(item) if item else None

    def resolve(self, decision_id, choice, note=None, remember=False):
        self.events.append("provider.resolve")
        self.calls.append({"decision_id": decision_id, "choice": choice, "note": note, "remember": remember})
        self.decisions.pop(decision_id, None)
        return {"remembered": bool(remember)}

    def sent(self):
        """The calls in the WP-1 approvals_resolve golden's body form."""
        bodies = []
        for call in self.calls:
            body = {"decision_id": call["decision_id"], "resolution": call["choice"]}
            if call["note"]:
                body["answer"] = call["note"]
            if call["remember"]:
                body["remember"] = True
            bodies.append(body)
        return bodies


class ScriptedDialog:
    """A confirmation dialog that answers from a script; an Exception outcome is raised."""

    def __init__(self, *outcomes, events=None):
        self.outcomes, self.asked = list(outcomes), []
        self.events = events if events is not None else []

    def ask(self, title, message, text="", allow_text=True):
        self.events.append("dialog.ask")
        self.asked.append({"title": title, "message": message, "text": text, "allow_text": allow_text})
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class RecordingNotifier:
    def __init__(self):
        self.sent = []

    def notify(self, title, message):
        self.sent.append((title, message))
        return True


class StateCase(unittest.TestCase):
    """A temp dir with a private state home; nothing outside it is ever written."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="folio-wp5-")
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)
        self.state = self.dir / "state"
        self.environ = {"XDG_STATE_HOME": str(self.state), "HOME": str(self.dir / "home")}
        self.log_path = self.state / "folio" / "approvals.jsonl"

    def approvals(self):
        return seam(self)

    def log(self, path=None):
        return self.approvals().ApprovalLog(path or self.log_path)

    def inbox(self, provider=None, *outcomes, log=None, notifier=None, events=None):
        module = self.approvals()
        self.dialog = ScriptedDialog(*outcomes, events=events)
        self.notifier = notifier or RecordingNotifier()
        return module.Approvals(provider, dialog=self.dialog, notifier=self.notifier, log=log or self.log(),
                                environ=self.environ)

    def resolution_records(self, path=None):
        target = Path(path or self.log_path)
        if not target.exists():
            return []
        return [item for item in self.log(target).records() if item.get("type") == "resolution"]


def python_child_argv(script):
    """argv for an isolated child interpreter (-I: no cwd, PYTHONPATH or user site on sys.path)."""
    return [sys.executable, "-I", "-c", "import sys; sys.path[:0] = [%r, %r]\n%s" % (str(REPO_ROOT), str(TESTS), script)]


def mode_of(path):
    return os.lstat(path).st_mode & 0o777
