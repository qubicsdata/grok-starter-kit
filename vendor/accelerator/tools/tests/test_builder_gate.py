#!/usr/bin/env python3
"""Stdlib tests for tools/hooks/builder_gate.py check_write(). Run directly."""
import importlib.util
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
_spec = importlib.util.spec_from_file_location("builder_gate", REPO / "tools" / "hooks" / "builder_gate.py")
fg = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fg)

failures = []

def check(name, cond):
    print(("PASS " if cond else "FAIL ") + name)
    if not cond:
        failures.append(name)

with tempfile.TemporaryDirectory() as tmp:
    plug = Path(tmp) / "toy-plugin"
    (plug / "agents").mkdir(parents=True)

    check("no session file → allow", fg.check_write(str(plug / "agents" / "a.md")) is None)

    (plug / ".builder-session.md").write_text(
        "# s\nMode: generate\n\n## Checkpoints\n- intake complete — t\n", encoding="utf-8")
    check("generate session, gates not cleared → deny",
          fg.check_write(str(plug / "agents" / "a.md")) is not None)
    check("session file itself exempt", fg.check_write(str(plug / ".builder-session.md")) is None)

    (plug / ".builder-session.md").write_text(
        "# s\nMode: generate\n\n## Checkpoints\n- gate-2 cleared — t\n", encoding="utf-8")
    check("gate-2 cleared → allow", fg.check_write(str(plug / "agents" / "a.md")) is None)

    (plug / ".builder-session.md").write_text(
        "# s\nMode: generate\n\n<!-- checkpoint: gate-2 cleared, publish complete -->\n", encoding="utf-8")
    check("old-grammar completed session exempt",
          fg.check_write(str(plug / "agents" / "a.md")) is None)

    (plug / ".builder-session.md").write_text(
        "# s\nMode: audit\n\n## Checkpoints\n- intake complete — t\n", encoding="utf-8")
    check("audit mode always exempt", fg.check_write(str(plug / "agents" / "a.md")) is None)

sys.exit(1 if failures else 0)
