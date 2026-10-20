#!/usr/bin/env python3
"""
secret_guard.py — PreToolUse hook for Write, Edit, and Bash tool calls.

Scans tool input text for HIGH-CONFIDENCE secret patterns only (to avoid
false positives). If a match is found, prints a deny JSON response and exits 0.
If no match, exits 0 silently (allow).

Fail-open on parse/script errors: exit 0 with a stderr note. Never wedge
normal work due to script failure.

Usage:
    echo '<hook-json>' | python3 tools/hooks/secret_guard.py
"""

from __future__ import annotations  # PEP 585 annotations must not break Python 3.8

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _hooklib import read_stdin_json, deny_response


# HIGH-CONFIDENCE secret patterns only.
# Each entry: (pattern_name, compiled_regex)
SECRET_PATTERNS = [
    ("AWS access key",     re.compile(r"AKIA[0-9A-Z]{16}")),
    ("private key block",  re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("Stripe live key",    re.compile(r"sk_live_[0-9a-zA-Z]{16,}")),
    ("GitHub PAT",         re.compile(r"ghp_[0-9A-Za-z]{36}")),
    ("Slack token",        re.compile(r"xox[baprs]-[0-9A-Za-z-]{10,}")),
    ("Google API key",     re.compile(r"AIza[0-9A-Za-z_\-]{35}")),
]


def extract_candidate_text(payload: dict) -> tuple[str, str]:
    """
    Return (text_to_scan, tool_name) from the hook payload.
    Extracts based on tool_name:
      Write  → tool_input.content
      Edit   → tool_input.new_string
      Bash   → tool_input.command
    """
    tool_name = payload.get("tool_name", "")
    tool_input = payload.get("tool_input", {})

    if tool_name == "Write":
        text = tool_input.get("content", "") or ""
    elif tool_name == "Edit":
        text = tool_input.get("new_string", "") or ""
    elif tool_name == "Bash":
        text = tool_input.get("command", "") or ""
    else:
        # Unknown tool — scan content/command/new_string best-effort
        text = (
            tool_input.get("content", "")
            or tool_input.get("new_string", "")
            or tool_input.get("command", "")
            or ""
        )

    return str(text), tool_name


def main() -> int:
    payload = read_stdin_json()
    if payload is None:
        # FAIL-OPEN: could not parse stdin
        sys.stderr.write("[secret_guard] warning: could not parse stdin JSON — allowing\n")
        return 0

    try:
        text, tool_name = extract_candidate_text(payload)

        for pattern_name, regex in SECRET_PATTERNS:
            if regex.search(text):
                reason = (
                    f"secret-guard: a credential pattern ({pattern_name}) was detected "
                    f"in this {tool_name} input. Use an env var or secret store."
                )
                system_msg = "baseline secret-guard blocked a write containing a credential pattern"
                print(deny_response("PreToolUse", reason, system_msg))
                return 0

    except Exception as exc:
        sys.stderr.write(f"[secret_guard] warning: scan error — allowing: {exc}\n")
        return 0

    # No match — allow silently
    return 0


if __name__ == "__main__":
    sys.exit(main())
