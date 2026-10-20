"""Approvals: decisions from a DecisionProvider, resolved only after the native dialog, traced in a local log (WP-5a).

The trace is $XDG_STATE_HOME/folio/approvals.jsonl: append-only JSON lines, owner-only (0600), never
opened through a symlink, never synced and never written into a tasks repo. It holds ids and the
clicked choice only, never command text, notes or answers (M-6). With no provider configured the
inbox is an empty state and resolve is unreachable.
"""

import json
import os
import re
import stat
import threading
from pathlib import Path

from .core import AppError, VIA_LABEL, now
from .dialogs import HIDDEN_NOTICE, UNAVAILABLE_MESSAGE, ConfirmDialog, DialogBusy, DialogUnavailable, Notifier, clean_text

EMPTY_MESSAGE = "No approvals source configured"
FILE_MODE = 0o600
DIR_MODE = 0o700
# Every open of the log: never through a symlink, never blocking on a FIFO (the local_auth.py checks).
OPEN_FLAGS = getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_BINARY", 0)
FID = re.compile(r"[0-9a-f]{16}")
REQUESTS = ("approve", "deny", "answer")
CHOICES = ("approve", "deny")
# packages/protocol/src/supervisor.ts:76: decision.resolve `answer` is z.string().max(20000), which counts UTF-16 code units.
ANSWER_UNITS = 20000
NOTE_TITLE = "Coordinator's note (agent-written)"
TRUNCATED = "… (truncated)"
LABELS = {"permission": "Request", "review": "Review summary", "question": "Question"}


def origin_label(actor):
    actor = actor or {}
    if actor.get("origin", "user") == "user":
        return "ui"
    via = actor.get("via")
    if isinstance(via, str) and VIA_LABEL.fullmatch(via):
        return via
    return "cli"


def utf16_units(text):
    return len(text.encode("utf-16-le", "surrogatepass")) // 2


def clip_utf16(text, units):
    """Clip text to at most `units` UTF-16 code units, labelling a cut (m8)."""
    if utf16_units(text) <= units:
        return text
    budget, used, kept = units - utf16_units(TRUNCATED), 0, []
    for character in text:
        size = 2 if ord(character) > 0xFFFF else 1
        if used + size > budget:
            break
        kept.append(character)
        used += size
    return "".join(kept) + TRUNCATED


def dialog_message(decision, requested, remember, origin):
    """The confirmation text, built only from the provider's normalized decision."""
    lines = [f"Project: {decision['project']}"]
    if decision.get("task_title") or decision.get("sb_task_id"):
        lines.append(f"Task: {decision.get('task_title') or decision.get('sb_task_id')}")
    lines += [f"Agent: {decision.get('participant') or 'unknown'}", f"Kind: {decision['kind']}"]
    if decision.get("hidden_characters"):
        lines += ["", HIDDEN_NOTICE]
    lines.append("")
    request = decision.get("request") or []
    if request:
        lines += [f"{item['label']}: {item['value']}" for item in request]
    else:
        lines.append(f"{LABELS.get(decision['kind'], 'Request')}: {decision.get('summary') or decision.get('title')}")
    if decision.get("options"):
        lines += ["", "Offered options (the answer is free text):"] + [f"{number}. {option}" for number, option in enumerate(decision["options"], 1)]
    if decision.get("coordinator_note"):
        lines += ["", f"{NOTE_TITLE}: {decision['coordinator_note']}"]
    if remember:
        lines += ["", f"And remember this exact {'command' if decision.get('command') else 'permission'} for the rest of the task."]
    # The platform-accurate hint about editing the note is added by the dialog itself.
    lines += ["", f"Requested: {requested} (via {origin})"]
    return "\n".join(lines)


def compose_answer(kind, resolution, text, origin):
    """The answer sent with a resolution: a question's typed answer, else the note plus the attribution."""
    if kind == "question":
        if resolution == "approve" and not text:
            raise AppError("Type an answer to answer the question.", 400, "ANSWER_REQUIRED")
        return clip_utf16(text, ANSWER_UNITS) or None
    attribution = f"Confirmed by a person in Folio (via {origin})."
    return f"{clip_utf16(text, ANSWER_UNITS - utf16_units(attribution) - 2)}\n\n{attribution}" if text else attribution


def notification_text(decision):
    who = decision.get("participant") or "An agent"
    what = {"permission": f"wants to run {decision['command']}" if decision.get("command") else "needs permission",
            "question": "has a question", "review": "needs your review"}.get(decision.get("kind"), "needs you")
    return f"{decision.get('project')}: {who} {what}"


def default_log_path(environ=None):
    """$XDG_STATE_HOME/folio/approvals.jsonl; a relative XDG_STATE_HOME is ignored (XDG spec)."""
    environ = os.environ if environ is None else environ
    state = environ.get("XDG_STATE_HOME") or ""
    if not os.path.isabs(state):
        home = environ.get("HOME") or os.path.expanduser("~")
        if not os.path.isabs(home):
            raise ApprovalLogError("No home folder for the approvals log (set HOME or XDG_STATE_HOME).")
        state = os.path.join(home, ".local", "state")
    return Path(state) / "folio" / "approvals.jsonl"


class ApprovalLogError(ValueError):
    pass


class ApprovalLog:
    """The append-only local trace of resolutions, notification claims and seen markers (M-6)."""

    def __init__(self, path=None, environ=None):
        self.path = Path(path) if path is not None else default_log_path(environ)
        self.lock = threading.Lock()

    def _refuse(self, reason):
        return ApprovalLogError(f"Refusing the approvals log {self.path}: {reason}.")

    def _make_parent(self):
        missing = []
        for directory in self.path.parents:
            if os.path.lexists(directory):
                break
            missing.append(directory)
        for directory in reversed(missing):
            try:
                os.mkdir(directory, DIR_MODE)
            except FileExistsError:
                continue
            except OSError as error:
                raise self._refuse(f"cannot create {directory} ({error.__class__.__name__})")
            # A restrictive umask must not leave a folder this account cannot write into.
            os.chmod(directory, DIR_MODE)

    def _open(self, write):
        """A checked descriptor, or None when reading a log that does not exist yet."""
        if write:
            self._make_parent()
            try:
                descriptor = os.open(self.path, os.O_RDWR | os.O_APPEND | os.O_CREAT | os.O_EXCL | OPEN_FLAGS, FILE_MODE)
            except FileExistsError:
                descriptor = None
            except OSError as error:
                raise self._refuse(error.strerror or error.__class__.__name__)
            if descriptor is not None and os.name != "nt":
                # The umask may have narrowed the creation mode; the log is always exactly 0600.
                try:
                    os.fchmod(descriptor, FILE_MODE)
                except OSError as error:
                    os.close(descriptor)
                    raise self._refuse(error.strerror or error.__class__.__name__)
        else:
            descriptor = None
        if descriptor is None:
            try:
                descriptor = os.open(self.path, (os.O_RDWR | os.O_APPEND if write else os.O_RDONLY) | OPEN_FLAGS)
            except FileNotFoundError:
                if write:
                    raise self._refuse("it disappeared while being opened")
                return None
            except OSError as error:
                raise self._refuse(error.strerror or error.__class__.__name__)
        try:
            info = os.fstat(descriptor)
            if not stat.S_ISREG(info.st_mode):
                raise self._refuse("it is not a regular file")
            if os.name != "nt" and (info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != FILE_MODE):
                raise self._refuse("it must be owned by this account with mode 0600")
        except BaseException:
            os.close(descriptor)
            raise
        return descriptor

    @staticmethod
    def _flock(descriptor, exclusive):
        if os.name != "nt":
            import fcntl
            fcntl.flock(descriptor, fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH)

    @staticmethod
    def _read(descriptor):
        os.lseek(descriptor, 0, os.SEEK_SET)
        chunks = []
        while True:
            chunk = os.read(descriptor, 1 << 16)
            if not chunk:
                break
            chunks.append(chunk)
        return b"".join(chunks)

    @staticmethod
    def _parse(data):
        records = []
        for line in data.decode("utf-8", "replace").splitlines():
            try:
                record = json.loads(line)
            except ValueError:
                continue  # a torn last line after a crash; the rest of the trace still counts
            if isinstance(record, dict):
                records.append(record)
        return records

    @staticmethod
    def _append(descriptor, records, torn=False):
        data = "".join(json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n" for record in records).encode("ascii")
        if torn:
            # End a line left half-written by a crash, so the next record is not glued onto it and lost.
            data = b"\n" + data
        while data:
            data = data[os.write(descriptor, data):]

    def _transaction(self, change):
        """Run change(records) -> new records under the exclusive lock, appending what it returns."""
        with self.lock:
            descriptor = self._open(write=True)
            try:
                self._flock(descriptor, True)
                data = self._read(descriptor)
                added, result = change(self._parse(data))
                if added:
                    self._append(descriptor, added, torn=bool(data) and not data.endswith(b"\n"))
                return result
            except OSError as error:
                raise self._refuse(error.strerror or error.__class__.__name__)
            finally:
                os.close(descriptor)

    def check(self):
        """Create (if needed) and verify the log without writing a record: a refused log raises here."""
        self._transaction(lambda records: (None, None))

    def records(self):
        with self.lock:
            descriptor = self._open(write=False)
            if descriptor is None:
                return []
            try:
                self._flock(descriptor, False)
                return self._parse(self._read(descriptor))
            except OSError as error:
                raise self._refuse(error.strerror or error.__class__.__name__)
            finally:
                os.close(descriptor)

    def record_resolution(self, provider, decision_id, choice, fid):
        if choice not in CHOICES or not (fid is None or (isinstance(fid, str) and FID.fullmatch(fid))):
            raise ValueError("A resolution records only approve/deny and a Folio task id.")
        record = {"type": "resolution", "ts": now(), "provider": str(provider), "decision_id": str(decision_id), "choice": choice, "fid": fid}
        self._transaction(lambda records: ([record], None))

    def _ids(self, records, kind, provider):
        return {item.get("decision_id") for item in records if item.get("type") == kind and item.get("provider") == provider}

    def claim_notifications(self, provider, decision_ids):
        """Persist and return the ids not notified before, in order; a restart sees the same claims."""
        def change(records):
            known, claimed = self._ids(records, "notified", provider), []
            for decision_id in decision_ids:
                if decision_id not in known:
                    known.add(decision_id)
                    claimed.append(decision_id)
            stamp = now()
            return [{"type": "notified", "ts": stamp, "provider": provider, "decision_id": item} for item in claimed], claimed
        return self._transaction(change)

    def notified(self, provider):
        return self._ids(self.records(), "notified", provider)

    def mark_seen(self, provider, decision_id):
        record = {"type": "seen", "ts": now(), "provider": provider, "decision_id": decision_id}
        self._transaction(lambda records: ([record], None))

    def seen(self, provider):
        return self._ids(self.records(), "seen", provider)


class DecisionProvider:
    """Where pending human decisions come from (a provider plugin; none ships in v1). Decisions are normalized dicts."""

    name = "provider"  # the key in the local log
    label = "Provider"  # the human name used in dialog titles and messages

    def pending(self):
        raise NotImplementedError

    def show(self, decision_id):
        """The pending decision, or None when it is unknown or no longer pending."""
        raise NotImplementedError

    def resolve(self, decision_id, choice, note, remember=False):
        """Send the human's choice ("approve"/"deny"); return a dict ({"remembered": bool} at least)."""
        raise NotImplementedError


class Approvals:
    def __init__(self, provider=None, dialog=None, notifier=None, log=None, environ=None):
        self.provider = provider
        self.dialog = dialog if dialog is not None else ConfirmDialog()
        self.notifier = notifier if notifier is not None else Notifier()
        self.environ = environ
        self._log = log

    @property
    def configured(self):
        return self.provider is not None

    @property
    def log(self):
        # Built on first use, so the empty state never resolves a state path or writes local state.
        if self._log is None:
            self._log = ApprovalLog(environ=self.environ)
        return self._log

    @property
    def label(self):
        return getattr(self.provider, "label", None) or getattr(self.provider, "name", None) or "Provider"

    def close(self):
        """Shutdown: stop a confirmation dialog that is still open (it counts as Cancel)."""
        closer = getattr(self.dialog, "close", None)
        if closer:
            closer()

    def status(self):
        if not self.configured:
            return {"configured": False, "message": EMPTY_MESSAGE, "decisions": []}
        return {"configured": True, "message": None, "decisions": self.provider.pending()}

    def poll(self):
        """Pending decisions; each one is notified once, de-duplicated through the log across restarts."""
        if not self.configured:
            return []
        decisions = self.provider.pending()
        ids = [item["id"] for item in decisions if isinstance(item.get("id"), str)]
        claimed = set(self.log.claim_notifications(self.provider.name, ids)) if ids else set()
        for item in decisions:
            if item.get("id") in claimed:
                self.notifier.notify("Folio", notification_text(item))
        return decisions

    def resolve(self, decision_id, data, actor):
        if not self.configured:
            raise AppError(EMPTY_MESSAGE + ".", 404, "NO_APPROVALS_SOURCE")
        data = data if isinstance(data, dict) else {}
        requested = data.get("requested")
        if requested not in REQUESTS:
            raise AppError("Choose approve, deny, or answer.")
        decision = self.provider.show(decision_id)
        if decision is None:
            return {"result": "no_longer_pending", "decision_id": decision_id}
        # Fail closed: a refused trace (symlink, wrong mode) stops the resolve before anyone is asked.
        try:
            self.log.check()
        except ApprovalLogError as error:
            raise AppError(str(error), 500, "APPROVALS_LOG_REFUSED")
        origin = origin_label(actor)
        # Remembering is offered, mentioned and sent only when the provider would honour it (m1).
        remember = bool(data.get("remember")) and decision["kind"] == "permission" and bool(decision.get("rememberable"))
        prefill = data.get("answer") if requested == "answer" else (data.get("note") or data.get("reason") or "")
        try:
            outcome = self.dialog.ask(f"Folio · {self.label} decision", dialog_message(decision, requested, remember, origin),
                                      text=str(prefill or ""), allow_text=True)
        except DialogBusy as error:
            raise AppError(str(error), 409, "CONFIRMATION_IN_PROGRESS")
        except DialogUnavailable:
            raise AppError(UNAVAILABLE_MESSAGE, 503, "HUMAN_CONFIRMATION_UNAVAILABLE")
        # Only an exact approve/deny click resolves; a timeout, a close or anything malformed is Cancel.
        choice = outcome.get("choice") if isinstance(outcome, dict) else None
        if type(choice) is not str or choice not in CHOICES:
            raise AppError(f"The confirmation was cancelled or timed out. Nothing was sent to {self.label}.", 409,
                           "HUMAN_CONFIRMATION_CANCELLED")
        text = outcome.get("text")
        text = clean_text(text.strip() if isinstance(text, str) else "", 1_000_000)
        answer = compose_answer(decision["kind"], choice, text, origin)
        response = self.provider.resolve(decision_id, choice, answer, remember and choice == "approve")
        result = {"result": "approved" if choice == "approve" else "denied", "decision_id": decision_id, "kind": decision["kind"],
                  "remembered": bool(isinstance(response, dict) and response.get("remembered"))}
        fid = decision.get("fid")
        fid = fid if isinstance(fid, str) and FID.fullmatch(fid) else None
        try:
            self.log.record_resolution(self.provider.name, decision_id, choice, fid)
        except ApprovalLogError as error:
            # The provider already acted, so report that outcome instead of an error (m9).
            result["warning"] = f"Resolved in {self.label}, but Folio could not record it locally: {error}"
        return result
