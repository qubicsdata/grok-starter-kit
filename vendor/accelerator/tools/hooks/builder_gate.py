#!/usr/bin/env python3
"""
builder_gate.py — PreToolUse hook for Write and Edit tool calls.

If the write target sits inside a directory tree governed by an ACTIVE
agent-builder generate/workshop session (.builder-session.md present, neither
'gate-2 cleared' nor 'publish complete' checkpointed), deny the write:
plugin files may only reach disk through the gated publisher. Audit-mode
sessions and the session file itself are always exempt.

Fail-open on any error: stderr note + exit 0. Never wedge a session.

Usage:
    echo '<hook-json>' | python3 tools/hooks/builder_gate.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _hooklib import read_stdin_json, deny_response

# Substrings WITHOUT the list-dash: two plugins carry stale COMPLETED session
# files in the pre-D1 comment grammar (`<!-- checkpoint: gate-2 cleared,
# publish complete -->`); substring matching treats both grammars as cleared,
# so completed sessions never lock a plugin. An in-flight pre-gate session
# contains neither substring, so the deny path is unaffected.
CLEAR_TOKENS = ("gate-2 cleared", "publish complete")


def check_write(file_path: str):
    """Return a deny reason, or None to allow."""
    target = Path(file_path)
    if target.name == ".builder-session.md":
        return None
    for d in [target.parent, *target.parent.parents]:
        session = d / ".builder-session.md"
        if session.is_file():
            break
    else:
        return None
    text = session.read_text(encoding="utf-8", errors="replace")
    mode = ""
    for line in text.splitlines():
        if line.lower().startswith("mode:"):
            mode = line.split(":", 1)[1].strip().lower()
            break
    if mode not in ("generate", "workshop"):
        return None  # audit sessions never clear gate-2; exempt (spec WS2-D)
    if any(tok in text for tok in CLEAR_TOKENS):
        return None
    return (f"Blocked write to {file_path}: {session} shows no 'gate-2 cleared' or "
            "'publish complete' checkpoint. Plugin files reach disk only through the "
            "gated publisher — finish the builder lifecycle or remove .builder-session.md.")


def main() -> int:
    try:
        data = read_stdin_json() or {}
        file_path = (data.get("tool_input") or {}).get("file_path") or ""
        if not file_path:
            return 0
        reason = check_write(file_path)
        if reason:
            print(deny_response("PreToolUse", "builder session gates not cleared", reason))
        return 0
    except Exception as e:
        print(f"builder_gate: fail-open: {e}", file=sys.stderr)
        return 0


if __name__ == "__main__":
    sys.exit(main())
