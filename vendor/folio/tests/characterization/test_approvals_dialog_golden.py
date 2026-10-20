"""Golden: the confirmation dialog argv, environment and choices, the unavailable messages and the
desktop notification (folio/dialogs.py).

No real dialog or notification is ever started: every process is a fake.

WP-7 (3/3) removed the frozen sync integration's decision service, so the goldens it produced
(approvals_normalized, approvals_dialog_messages, approvals_resolve) are no longer written here; they stay
as the fixtures tests/test_wp5_approvals_resolve.py replays through folio/approvals.py.
"""

import subprocess
import unittest

from folio.dialogs import ConfirmDialog, DialogUnavailable, Notifier

from .golden import assert_golden


class Child:
    def __init__(self, code, out):
        self.returncode, self.code, self.out = None, code, out

    def communicate(self, timeout=None):
        self.returncode = self.code
        return self.out, ""

    def poll(self):
        return self.returncode


class Spawner:
    def __init__(self, *children):
        self.children, self.calls = list(children), []

    def __call__(self, args, **kwargs):
        self.calls.append({"argv": list(args), **{key: kwargs[key] for key in sorted(kwargs) if key in ("env", "text", "encoding")},
                           "stdin_devnull": kwargs.get("stdin") == subprocess.DEVNULL})
        return self.children.pop(0)


class ConfirmDialogGoldenTests(unittest.TestCase):
    ENVIRON = {"DISPLAY": ":0", "HOME": "/nonexistent/fixture-home", "LANG": "C.UTF-8", "PATH": "/tmp/x:/usr/bin", "LD_PRELOAD": "x.so"}

    def test_platform_argv_env_and_choices(self):
        mac = Spawner(Child(0, "Approve\nLooks good\n"), Child(0, "Deny\n"), Child(0, "cancel\n"))
        dialog = ConfirmDialog(popen=mac, platform="darwin", environ=self.ENVIRON)
        mac_outcomes = [dialog.ask("Folio · Switchboard decision", "Project: Example rollout", "note"),
                        dialog.ask("T", "M", allow_text=False), dialog.ask("T", "M")]
        linux = Spawner(Child(0, ""), Child(0, "edited\n"), Child(1, "Deny\n"), Child(0, "reason\n"), Child(1, ""), Child(5, ""))
        dialog = ConfirmDialog(popen=linux, platform="linux", exists=lambda path: path == "/usr/bin/zenity", environ=self.ENVIRON,
                               clock=lambda: 500.0)
        linux_outcomes = [dialog.ask("Folio · Switchboard decision", "Project: Example rollout", "pre"),
                          dialog.ask("T", "M"), dialog.ask("T", "M"), dialog.ask("T", "M")]
        assert_golden(self, "dialog_platforms", {"darwin": {"calls": mac.calls, "outcomes": mac_outcomes},
                                                 "linux": {"calls": linux.calls, "outcomes": linux_outcomes}})

    def test_unavailable_and_notifier(self):
        unavailable = {}
        for name, kwargs in {"linux_no_display": {"platform": "linux", "exists": lambda path: True, "environ": {}},
                             "linux_no_zenity": {"platform": "linux", "exists": lambda path: False, "environ": self.ENVIRON},
                             "unsupported": {"platform": "plan9", "exists": lambda path: True, "environ": self.ENVIRON}}.items():
            try:
                ConfirmDialog(popen=Spawner(), **kwargs).ask("T", "M")
            except DialogUnavailable as error:
                unavailable[name] = str(error)
        runs = []

        def run(args, **kwargs):
            runs.append({"argv": list(args), "env": kwargs.get("env")})

            class Done:
                returncode = 0
            return Done()
        Notifier(run=run, platform="linux", exists=lambda path: path == "/usr/bin/notify-send", environ=self.ENVIRON).notify("Folio", "Example rollout: codex:worker-1 wants to run pytest -q")
        assert_golden(self, "dialog_unavailable_and_notify", {"unavailable": unavailable, "notify": runs})


if __name__ == "__main__":
    unittest.main()
