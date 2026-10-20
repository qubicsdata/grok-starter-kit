#!/usr/bin/env python3
"""Exercise real Zenity cancellation on an isolated Linux display (requires xdotool)."""
import json
from pathlib import Path
import re
import subprocess
import sys
import threading
import time

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from folio.dialogs import ConfirmDialog


def check(callback, title, key=None):
    result, errors = [], []
    def worker():
        try:
            result.append(callback())
        except Exception as error:
            errors.append(error)
    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    deadline = time.monotonic() + 8
    window = None
    while time.monotonic() < deadline and thread.is_alive():
        found = subprocess.run(['xdotool', 'search', '--onlyvisible', '--name', '^' + re.escape(title) + '$'],
                               capture_output=True, text=True, timeout=2)
        if found.returncode == 0 and found.stdout.strip():
            window = found.stdout.splitlines()[0]
            break
        time.sleep(0.05)
    assert window, f'No real dialog appeared: {title}; {errors}'
    if key:
        subprocess.run(['xdotool', 'windowfocus', '--sync', window], check=True, timeout=3)
        time.sleep(0.2)
        subprocess.run(['xdotool', 'key', '--clearmodifiers', key], check=True, timeout=3)
    thread.join(3 if key else 10)
    assert not thread.is_alive(), 'The dialog did not close'
    if errors:
        raise errors[0]
    return result[0]


if __name__ == '__main__':
    if not sys.platform.startswith('linux'):
        raise SystemExit('Run on Linux with an isolated DISPLAY, e.g. xvfb-run -a python3 scripts/smoke-linux-desktop.py')
    for title, timeout, key in [('Folio default cancel check', 8, 'Return'), ('Folio timeout check', 2, None)]:
        dialog = ConfirmDialog(timeout=timeout)
        try:
            result = check(lambda: dialog.ask(title, 'Test fixture only. No permission will be sent.', allow_text=False), title, key)
            assert result['choice'] == 'cancel', result
        finally:
            dialog.close()
    # The native folder picker left with WP-6 (/api/folders/pick is 404); only the confirmation dialog remains.
    print(json.dumps({'ok': True, 'platform': sys.platform, 'tool': 'real Zenity on isolated X11 display',
                      'checks': ['confirmation-default-cancel', 'confirmation-timeout']}))
