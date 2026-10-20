"""Native, harness-independent human confirmation and notifications (spec §13.3–§13.5)."""

import os
import subprocess
import sys
import threading
import time
import unicodedata

DIALOG_SECONDS = 120
# Extra seconds a dialog process may run past its own give-up time before Folio kills it.
MARGIN = 5
NOTE_LABEL = "Note (from the requester, editable)"
MAC_HINT = "The text field comes from the requester; edit it in this dialog before you click."
LINUX_HINT = "After you click Approve or Deny, a second box asks for the note (it comes from the requester; edit it there)."
HIDDEN_NOTICE = "Hidden formatting characters were replaced with ⟦U+…⟧ markers."
UNAVAILABLE_MESSAGE = ("A person must confirm this at the computer, but no confirmation dialog can open here. "
                       "Decide it in the tool that asked for it.")
# Dialog and notification tools are run only from these fixed system directories, never through
# PATH, and with only these variables from Folio's environment (I-4): a caller that controls PATH
# or the environment must not be able to stand in for the human.
TOOL_DIRS = ("/usr/bin", "/bin")
SAFE_PATH = "/usr/bin:/bin"
# __CF_USER_TEXT_ENCODING: macOS needs this to decode non-ASCII dialog text, such as the
# ⟦U+…⟧ markers clean_text_report inserts, correctly in the AppleScript/osascript dialog.
ENV_ALLOWLIST = ("DISPLAY", "WAYLAND_DISPLAY", "XAUTHORITY", "DBUS_SESSION_BUS_ADDRESS", "XDG_RUNTIME_DIR", "HOME", "LANG", "LC_ALL",
                  "LC_CTYPE", "__CF_USER_TEXT_ENCODING")

APPROVAL_SCRIPT = """on run argv
  set theTitle to item 1 of argv
  set theMessage to item 2 of argv
  set theText to item 3 of argv
  set wantsText to item 4 of argv
  set theSeconds to (item 5 of argv) as integer
  try
    if wantsText is "1" then
      set outcome to display dialog theMessage with title theTitle default answer theText buttons {"Deny", "Cancel", "Approve"} default button "Cancel" cancel button "Cancel" giving up after theSeconds with icon caution
    else
      set outcome to display dialog theMessage with title theTitle buttons {"Deny", "Cancel", "Approve"} default button "Cancel" cancel button "Cancel" giving up after theSeconds with icon caution
    end if
    if gave up of outcome then return "cancel"
    if wantsText is "1" then return (button returned of outcome) & linefeed & (text returned of outcome)
    return button returned of outcome
  on error number -128
    return "cancel"
  end try
end run"""

NOTIFY_SCRIPT = """on run argv
  display notification (item 2 of argv) with title (item 1 of argv)
end run"""


class DialogUnavailable(Exception):
    pass


class DialogBusy(Exception):
    pass


def clean_text_report(value, limit):
    """Return (text, hidden): control characters removed, format characters made visible, clipped.

    Category Cc (C0 and C1 controls) is removed except newline and tab. Category Cf (bidi
    overrides and isolates, zero-width characters, BOM, tags) is replaced with a visible
    ⟦U+XXXX⟧ marker so agent-authored text cannot reorder or hide what a person reads (I-2).
    `hidden` is True when any marker was inserted.
    """
    parts = []
    hidden = False
    for character in str(value or ""):
        category = unicodedata.category(character)
        if category == "Cc" and character not in "\n\t":
            continue
        if category == "Cf":
            parts.append(f"⟦U+{ord(character):04X}⟧")
            hidden = True
            continue
        parts.append(character)
    text = "".join(parts)
    return (text if len(text) <= limit else text[:limit] + "… (truncated)"), hidden


def clean_text(value, limit):
    return clean_text_report(value, limit)[0]


def child_environment(environ):
    env = {key: environ[key] for key in ENV_ALLOWLIST if key in environ}
    env["PATH"] = SAFE_PATH
    return env


def system_tool(name, exists):
    for directory in TOOL_DIRS:
        path = f"{directory}/{name}"
        if exists(path):
            return path
    return None


CHOICES = {"approve": "approve", "deny": "deny"}


class ConfirmDialog:
    def __init__(self, popen=subprocess.Popen, platform=None, exists=os.path.exists, environ=None, timeout=DIALOG_SECONDS,
                 clock=time.monotonic):
        self.popen = popen
        self.platform = platform or sys.platform
        self.exists = exists
        self.environ = os.environ if environ is None else environ
        self.timeout = timeout
        self.clock = clock
        self.lock = threading.Lock()
        self.child_lock = threading.Lock()
        self.child = None
        self.closed = False

    def close(self):
        """Stop an open dialog (Folio is shutting down). The pending ask counts as Cancel."""
        with self.child_lock:
            self.closed = True
            child = self.child
        if child is not None and child.poll() is None:
            try:
                child.terminate()
            except OSError:
                pass

    def _exec(self, args, seconds, env=None):
        with self.child_lock:
            if self.closed:
                return None
            try:
                child = self.popen(args, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8",
                                   env=child_environment(self.environ) if env is None else env)
            except OSError as error:
                raise DialogUnavailable(f"Could not open a confirmation dialog ({error.__class__.__name__}).")
            self.child = child
        try:
            try:
                stdout, _ = child.communicate(timeout=seconds)
            except subprocess.TimeoutExpired:
                child.kill()
                try:
                    child.communicate(timeout=MARGIN)
                except subprocess.TimeoutExpired:
                    pass
                return None
        finally:
            with self.child_lock:
                self.child = None
                closed = self.closed
        if closed:
            return None
        return subprocess.CompletedProcess(args, child.returncode, stdout, "")

    def ask(self, title, message, text="", allow_text=True):
        if not self.lock.acquire(blocking=False):
            raise DialogBusy("Another confirmation dialog is already open. Finish that one first.")
        try:
            deadline = self.clock() + self.timeout
            title, hidden_title = clean_text_report(title, 120)
            message, hidden_message = clean_text_report(message, 3000)
            text, hidden_text = clean_text_report(text, 2000)
            # Native Windows is not supported (WSL2 only, D-15): win32 falls through to "unavailable".
            if self.platform == "darwin":
                return self._macos(title, self._compose(message, hidden_title or hidden_message or hidden_text, allow_text, MAC_HINT), text, allow_text)
            if self.platform.startswith("linux") and (self.environ.get("DISPLAY") or self.environ.get("WAYLAND_DISPLAY")):
                zenity = system_tool("zenity", self.exists)
                if zenity is None:
                    raise DialogUnavailable("Folio needs Zenity (/usr/bin/zenity or /bin/zenity) for confirmation dialogs on Linux. "
                                            + UNAVAILABLE_MESSAGE)
                message = self._compose(message, hidden_title or hidden_message or hidden_text, allow_text, LINUX_HINT)
                return self._zenity(zenity, title, message, text, allow_text, deadline)
            raise DialogUnavailable(UNAVAILABLE_MESSAGE)
        finally:
            self.lock.release()

    @staticmethod
    def _compose(message, hidden, allow_text, hint):
        parts = [message]
        if hidden and HIDDEN_NOTICE not in message:
            parts.append(HIDDEN_NOTICE)
        if allow_text:
            parts.append(hint)
        return "\n\n".join(parts)

    def _remaining(self, deadline):
        # Whole seconds left, rounded down; the small tolerance keeps a full budget from reading
        # as one second less just because microseconds passed since the deadline was set.
        return int(deadline - self.clock() + 0.05)

    def _macos(self, title, message, text, allow_text):
        seconds = int(self.timeout)
        result = self._exec(["/usr/bin/osascript", "-e", APPROVAL_SCRIPT, title, message, text, "1" if allow_text else "0", str(seconds)],
                            seconds + MARGIN)
        if result is None:
            return {"choice": "cancel", "text": ""}
        if result.returncode != 0:
            raise DialogUnavailable("The macOS confirmation dialog could not be shown (no desktop session or permission).")
        first, _, rest = result.stdout.rstrip("\n").partition("\n")
        return {"choice": CHOICES.get(first.strip().lower(), "cancel"), "text": rest}

    def _zenity(self, zenity, title, message, text, allow_text, deadline):
        cancel = {"choice": "cancel", "text": ""}
        remaining = self._remaining(deadline)
        if remaining <= 0:
            return cancel
        result = self._exec([zenity, "--question", "--title", title, "--text", message, "--ok-label", "Approve", "--cancel-label", "Cancel",
                             "--extra-button", "Deny", "--default-cancel", "--timeout", str(remaining)], remaining + MARGIN)
        if result is None:
            return cancel
        if result.returncode == 0:
            choice = "approve"
        elif result.returncode == 1 and result.stdout.strip() == "Deny":
            choice = "deny"
        else:
            return cancel
        if not allow_text:
            return {"choice": choice, "text": ""}
        # The note box shares the one overall deadline: a person who spent the budget on the first
        # box gets Cancel, so the whole confirmation never outlasts `timeout` (I-3).
        remaining = self._remaining(deadline)
        if remaining <= 0:
            return cancel
        result = self._exec([zenity, "--entry", "--title", title, "--text", NOTE_LABEL, "--entry-text", text, "--timeout", str(remaining)],
                            remaining + MARGIN)
        if result is None or result.returncode != 0:
            return cancel
        return {"choice": choice, "text": result.stdout.rstrip("\n")}


class Notifier:
    def __init__(self, run=subprocess.run, platform=None, exists=os.path.exists, environ=None):
        self.run = run
        self.platform = platform or sys.platform
        self.exists = exists
        self.environ = os.environ if environ is None else environ

    def notify(self, title, message):
        title, message = clean_text(title, 80), clean_text(message, 300)
        options = {"capture_output": True, "text": True, "timeout": 10, "env": child_environment(self.environ)}
        try:
            if self.platform == "darwin":
                self.run(["/usr/bin/osascript", "-e", NOTIFY_SCRIPT, title, message], **options)
                return True
            if self.platform.startswith("linux"):
                tool = system_tool("notify-send", self.exists)
                if tool:
                    self.run([tool, title, message], **options)
                    return True
        except (OSError, subprocess.SubprocessError):
            return False
        return False
