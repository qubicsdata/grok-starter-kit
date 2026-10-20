"""ConfirmDialog and Notifier tests. Every test injects fake popen/run/exists/platform/environ:
no test ever starts osascript, zenity, or notify-send, and no real dialog or notification opens."""

import os
import subprocess
import tempfile
import threading
import unittest

from folio.dialogs import (APPROVAL_SCRIPT, HIDDEN_NOTICE, MARGIN, ConfirmDialog, DialogBusy, DialogUnavailable, Notifier,
                           clean_text, clean_text_report)

DESKTOP = {"DISPLAY": ":0"}
# A fixture home under the temp dir (R-b: no literal home path in the tree); never created or read.
HOME = os.path.join(tempfile.gettempdir(), "folio-dialog-fixture-home")


class FakeChild:
    def __init__(self, code=0, out="", expire=False, block=None, on_communicate=None):
        self.code, self.out, self.expire, self.block, self.on_communicate = code, out, expire, block, on_communicate
        self.returncode = None
        self.timeouts = []
        self.started = threading.Event()
        self.terminated = self.killed = False

    def communicate(self, timeout=None):
        self.timeouts.append(timeout)
        if self.on_communicate:
            self.on_communicate()
        if self.killed:
            return self.out, ""
        if self.expire:
            raise subprocess.TimeoutExpired("dialog", timeout)
        if self.block is not None:
            self.started.set()
            self.block.wait(5)
        if self.returncode is None:
            self.returncode = self.code
        return self.out, ""

    def poll(self):
        return self.returncode

    def terminate(self):
        self.terminated = True
        self.returncode = -15
        if self.block is not None:
            self.block.set()

    def kill(self):
        self.killed = True
        self.returncode = -9


class Spawner:
    def __init__(self, *children):
        self.children = list(children)
        self.calls = []

    def __call__(self, args, **kwargs):
        self.calls.append((args, kwargs))
        child = self.children.pop(0)
        if isinstance(child, Exception):
            raise child
        return child


class Clock:
    def __init__(self):
        self.value = 500.0

    def __call__(self):
        return self.value


def only(*paths):
    return lambda path: path in paths


class ConfirmDialogTests(unittest.TestCase):
    def test_macos_passes_text_as_arguments_and_parses_choices(self):
        popen = Spawner(FakeChild(0, "Approve\nLooks good\n"), FakeChild(0, "Deny\n"), FakeChild(0, "cancel\n"))
        dialog = ConfirmDialog(popen=popen, platform="darwin", environ={})
        hostile = 'x" & do shell script "rm -rf ~" & "'
        self.assertEqual(dialog.ask("Title", hostile, "note"), {"choice": "approve", "text": "Looks good"})
        args, kwargs = popen.calls[0]
        self.assertEqual(args[:3], ["/usr/bin/osascript", "-e", APPROVAL_SCRIPT])
        self.assertEqual(args[3], "Title")
        self.assertTrue(args[4].startswith(hostile + "\n\n"))
        self.assertEqual(args[5:], ["note", "1", "120"])
        self.assertNotIn("rm -rf", APPROVAL_SCRIPT)
        self.assertEqual(kwargs["stdin"], subprocess.DEVNULL)
        self.assertIn('default button "Cancel"', APPROVAL_SCRIPT)
        self.assertIn("giving up after theSeconds", APPROVAL_SCRIPT)
        self.assertNotIn("giving up after 120", APPROVAL_SCRIPT)
        self.assertEqual(dialog.ask("T", "M", allow_text=False)["choice"], "deny")
        self.assertEqual(dialog.ask("T", "M")["choice"], "cancel")

    def test_macos_hint_says_to_edit_in_the_dialog(self):
        popen = Spawner(FakeChild(0, "cancel\n"), FakeChild(0, "cancel\n"))
        dialog = ConfirmDialog(popen=popen, platform="darwin", environ={})
        dialog.ask("T", "M", "note")
        self.assertIn("edit it in this dialog before you click", popen.calls[0][0][4])
        dialog.ask("T", "M", allow_text=False)
        self.assertEqual(popen.calls[1][0][4], "M")

    def test_macos_give_up_and_process_timeout_follow_the_dialog_timeout(self):
        child = FakeChild(0, "cancel\n")
        popen = Spawner(child)
        ConfirmDialog(popen=popen, platform="darwin", environ={}, timeout=45).ask("T", "M")
        self.assertEqual(popen.calls[0][0][-1], "45")
        self.assertEqual(child.timeouts[0], 45 + MARGIN)
        self.assertLessEqual(MARGIN, 10)

    def test_macos_failure_is_unavailable_and_timeout_is_cancel(self):
        dialog = ConfirmDialog(popen=Spawner(FakeChild(1, "")), platform="darwin", environ={})
        with self.assertRaises(DialogUnavailable):
            dialog.ask("T", "M")
        expired = FakeChild(expire=True)
        dialog = ConfirmDialog(popen=Spawner(expired), platform="darwin", environ={})
        self.assertEqual(dialog.ask("T", "M")["choice"], "cancel")
        self.assertTrue(expired.killed)
        dialog = ConfirmDialog(popen=Spawner(FileNotFoundError()), platform="darwin", environ={})
        with self.assertRaises(DialogUnavailable):
            dialog.ask("T", "M")

    def test_one_dialog_at_a_time(self):
        release = threading.Event()
        child = FakeChild(0, "cancel\n", block=release)
        dialog = ConfirmDialog(popen=Spawner(child), platform="darwin", environ={})
        thread = threading.Thread(target=dialog.ask, args=("T", "M"))
        thread.start()
        self.assertTrue(child.started.wait(5))
        try:
            with self.assertRaises(DialogBusy):
                dialog.ask("T", "M")
        finally:
            release.set()
            thread.join(5)

    def test_close_terminates_the_open_dialog_and_counts_as_cancel(self):
        release = threading.Event()
        child = FakeChild(0, "Approve\n", block=release)
        dialog = ConfirmDialog(popen=Spawner(child), platform="darwin", environ={})
        outcome = {}
        thread = threading.Thread(target=lambda: outcome.update(dialog.ask("T", "M")))
        thread.start()
        self.assertTrue(child.started.wait(5))
        dialog.close()
        thread.join(5)
        self.assertFalse(thread.is_alive())
        self.assertTrue(child.terminated)
        self.assertEqual(outcome["choice"], "cancel")
        # A closed dialog never starts another child process.
        self.assertEqual(dialog.ask("T", "M")["choice"], "cancel")
        ConfirmDialog(popen=Spawner(), platform="darwin", environ={}).close()

    def test_child_environment_is_an_allowlist_with_a_fixed_path(self):
        environ = {"DISPLAY": ":1", "WAYLAND_DISPLAY": "wayland-0", "XAUTHORITY": HOME + "/.Xauthority",
                   "DBUS_SESSION_BUS_ADDRESS": "unix:path=/run/user/1/bus", "XDG_RUNTIME_DIR": "/run/user/1", "HOME": HOME,
                   "LANG": "en_US.UTF-8", "LC_ALL": "C.UTF-8", "LC_CTYPE": "UTF-8", "__CF_USER_TEXT_ENCODING": "0x1F5:0x0:0x0",
                   "PATH": "/tmp/x:/usr/bin", "LD_PRELOAD": "/tmp/x/evil.so", "PYTHONPATH": "/tmp/x", "ZENITY_OVERRIDE": "1",
                   "DYLD_INSERT_LIBRARIES": "/tmp/x.dylib", "TMPDIR": "/tmp/x"}
        expected = {key: value for key, value in environ.items()
                    if key not in ("PATH", "LD_PRELOAD", "PYTHONPATH", "ZENITY_OVERRIDE", "DYLD_INSERT_LIBRARIES", "TMPDIR")}
        expected["PATH"] = "/usr/bin:/bin"
        popen = Spawner(FakeChild(1, ""))
        ConfirmDialog(popen=popen, platform="linux", exists=only("/usr/bin/zenity"), environ=environ).ask("T", "M", allow_text=False)
        self.assertEqual(popen.calls[0][1]["env"], expected)
        popen = Spawner(FakeChild(0, "cancel\n"))
        ConfirmDialog(popen=popen, platform="darwin", environ=environ).ask("T", "M")
        self.assertEqual(popen.calls[0][1]["env"], expected)

    def test_linux_resolves_zenity_only_from_fixed_system_paths(self):
        for path in ("/usr/bin/zenity", "/bin/zenity"):
            popen = Spawner(FakeChild(1, ""))
            ConfirmDialog(popen=popen, platform="linux", exists=only(path), environ=DESKTOP).ask("T", "M", allow_text=False)
            self.assertEqual(popen.calls[0][0][0], path)
        popen = Spawner(FakeChild(1, ""))
        ConfirmDialog(popen=popen, platform="linux", exists=only("/usr/bin/zenity", "/bin/zenity"), environ=DESKTOP).ask("T", "M", allow_text=False)
        self.assertEqual(popen.calls[0][0][0], "/usr/bin/zenity")

    def test_a_fake_zenity_on_path_is_ignored(self):
        popen = Spawner()
        environ = {"DISPLAY": ":0", "PATH": "/tmp/x:/usr/local/bin"}
        dialog = ConfirmDialog(popen=popen, platform="linux", exists=only("/tmp/x/zenity", "/usr/local/bin/zenity"), environ=environ)
        with self.assertRaises(DialogUnavailable) as error:
            dialog.ask("T", "M")
        self.assertEqual(popen.calls, [])
        self.assertIn("Decide it in the tool that asked for it.", str(error.exception))

    def test_kdialog_is_never_used(self):
        popen = Spawner()
        dialog = ConfirmDialog(popen=popen, platform="linux", exists=only("/usr/bin/kdialog", "/bin/kdialog"), environ=DESKTOP)
        with self.assertRaises(DialogUnavailable) as error:
            dialog.ask("T", "M")
        self.assertEqual(popen.calls, [])
        self.assertIn("zenity", str(error.exception).lower())
        self.assertIn("Decide it in the tool that asked for it.", str(error.exception))

    def test_linux_zenity_choices_default_cancel_and_timeouts(self):
        popen = Spawner(FakeChild(0), FakeChild(0, "edited\n"), FakeChild(1, "Deny\n"), FakeChild(0, "reason\n"),
                        FakeChild(1, ""), FakeChild(5, ""), FakeChild(0), FakeChild(5, ""))
        dialog = ConfirmDialog(popen=popen, platform="linux", exists=only("/usr/bin/zenity"), environ=DESKTOP)
        self.assertEqual(dialog.ask("T", "M", "pre"), {"choice": "approve", "text": "edited"})
        question, entry = popen.calls[0][0], popen.calls[1][0]
        self.assertIn("--default-cancel", question)
        self.assertEqual(question[question.index("--timeout") + 1], "120")
        self.assertIn("After you click", question[question.index("--text") + 1])
        self.assertEqual(entry[:2], ["/usr/bin/zenity", "--entry"])
        self.assertIn("pre", entry)
        self.assertEqual(entry[entry.index("--timeout") + 1], "120")
        self.assertEqual(dialog.ask("T", "M"), {"choice": "deny", "text": "reason"})
        self.assertEqual(dialog.ask("T", "M")["choice"], "cancel")  # Cancel button
        self.assertEqual(dialog.ask("T", "M")["choice"], "cancel")  # zenity --timeout (exit 5)
        self.assertEqual(dialog.ask("T", "M")["choice"], "cancel")  # approve, then the entry box timed out
        self.assertEqual(popen.children, [])

    def test_linux_shares_one_deadline_across_both_steps(self):
        clock = Clock()

        def spend(seconds):
            return lambda: setattr(clock, "value", clock.value + seconds)

        question, entry = FakeChild(0, on_communicate=spend(100.4)), FakeChild(0, "note\n")
        popen = Spawner(question, entry)
        dialog = ConfirmDialog(popen=popen, platform="linux", exists=only("/usr/bin/zenity"), environ=DESKTOP, clock=clock)
        self.assertEqual(dialog.ask("T", "M"), {"choice": "approve", "text": "note"})
        args = popen.calls[1][0]
        self.assertEqual(args[args.index("--timeout") + 1], "19")
        self.assertEqual(question.timeouts[0], 120 + MARGIN)
        self.assertEqual(entry.timeouts[0], 19 + MARGIN)

        exhausted = FakeChild(0, on_communicate=spend(120.2))
        popen = Spawner(exhausted)
        dialog = ConfirmDialog(popen=popen, platform="linux", exists=only("/usr/bin/zenity"), environ=DESKTOP, clock=clock)
        self.assertEqual(dialog.ask("T", "M"), {"choice": "cancel", "text": ""})
        self.assertEqual(len(popen.calls), 1)

    def test_unavailable_without_display_or_tools(self):
        # win32: native Windows is not supported since WP-6 (windows_desktop.py is gone); WSL2 reads as linux.
        for kwargs in ({"platform": "linux", "exists": lambda path: True, "environ": {}},
                       {"platform": "linux", "exists": lambda path: False, "environ": DESKTOP},
                       {"platform": "unsupported", "exists": lambda path: True, "environ": DESKTOP},
                       {"platform": "win32", "exists": lambda path: True, "environ": DESKTOP}):
            with self.subTest(platform=kwargs["platform"], environ=kwargs["environ"]), self.assertRaises(DialogUnavailable):
                ConfirmDialog(popen=Spawner(), **kwargs).ask("T", "M")

    def test_hidden_characters_in_the_prefill_add_the_notice(self):
        popen = Spawner(FakeChild(0, "cancel\n"), FakeChild(0, "cancel\n"))
        dialog = ConfirmDialog(popen=popen, platform="darwin", environ={})
        dialog.ask("T", "M", "ok\u202etxt")
        args = popen.calls[0][0]
        self.assertIn(HIDDEN_NOTICE, args[4])
        self.assertEqual(args[5], "ok⟦U+202E⟧txt")
        dialog.ask("T", f"M\n{HIDDEN_NOTICE}", "ok\u200b")
        self.assertEqual(popen.calls[1][0][4].count(HIDDEN_NOTICE), 1)


class CleanTextTests(unittest.TestCase):
    def test_strips_controls_and_truncates(self):
        self.assertEqual(clean_text("a\x00b\x1bc\nd\te\r\x7f", 100), "abc\nd\te")
        self.assertEqual(clean_text("x" * 20, 10), "x" * 10 + "… (truncated)")
        self.assertEqual(clean_text(None, 10), "")

    def test_format_characters_become_visible_markers(self):
        cases = {"\u202e": "⟦U+202E⟧", "\u200b": "⟦U+200B⟧", "\u2066": "⟦U+2066⟧", "\ufeff": "⟦U+FEFF⟧", "\U000e0001": "⟦U+E0001⟧"}
        for raw, marker in cases.items():
            with self.subTest(character=marker):
                self.assertEqual(clean_text_report(f"echo safe{raw}x", 100), (f"echo safe{marker}x", True))

    def test_c1_controls_are_removed(self):
        self.assertEqual(clean_text_report("a\x85b\x9bc", 100), ("abc", False))

    def test_ordinary_text_is_unchanged(self):
        text = "Déjà vu: naïve Ångström café 🚀 日本語 — ok"
        self.assertEqual(clean_text_report(text, 1000), (text, False))
        self.assertEqual(clean_text("echo safe \u202e hs|lruc \u200b\x85\x9b", 100), "echo safe ⟦U+202E⟧ hs|lruc ⟦U+200B⟧")


class NotifierTests(unittest.TestCase):
    def test_notify_platforms_and_failures(self):
        run = Spawner(subprocess.CompletedProcess([], 0, "", ""))
        self.assertTrue(Notifier(run=run, platform="darwin", environ={"HOME": HOME, "PATH": "/tmp/x"}).notify("Folio", 'He said "hi"'))
        self.assertEqual(run.calls[0][0][:1], ["/usr/bin/osascript"])
        self.assertEqual(run.calls[0][0][-2:], ["Folio", 'He said "hi"'])
        self.assertEqual(run.calls[0][1]["env"], {"HOME": HOME, "PATH": "/usr/bin:/bin"})
        run = Spawner(subprocess.CompletedProcess([], 0, "", ""))
        environ = {"DISPLAY": ":0", "DBUS_SESSION_BUS_ADDRESS": "unix:path=/run/user/1/bus", "PATH": "/tmp/x", "LD_PRELOAD": "x"}
        self.assertTrue(Notifier(run=run, platform="linux", exists=only("/bin/notify-send"), environ=environ).notify("Folio", "msg\u202e"))
        self.assertEqual(run.calls[0][0], ["/bin/notify-send", "Folio", "msg⟦U+202E⟧"])
        self.assertEqual(run.calls[0][1]["env"], {"DISPLAY": ":0", "DBUS_SESSION_BUS_ADDRESS": "unix:path=/run/user/1/bus", "PATH": "/usr/bin:/bin"})
        self.assertFalse(Notifier(run=Spawner(), platform="linux", exists=only("/tmp/x/notify-send"), environ={"PATH": "/tmp/x"}).notify("Folio", "msg"))
        self.assertFalse(Notifier(run=Spawner(OSError()), platform="darwin", environ={}).notify("Folio", "msg"))
        win = Spawner()
        self.assertFalse(Notifier(run=win, platform="win32", environ={}).notify("Folio", "msg"))
        self.assertEqual(win.calls, [], "win32 spawns nothing: native Windows is not supported")


if __name__ == "__main__":
    unittest.main()
