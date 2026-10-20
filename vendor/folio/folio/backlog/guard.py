"""The onStatusChange guard (D-8, R13): a raw, read-only scan that refuses an edit before the binary runs.

Backlog.md 1.53.0 executes a per-task `onStatusChange` command with `sh -c` on a status change, and the
key survives edits. The scan is deliberately raw: any spelling of the key in any case, anywhere in the
config or the task file (front matter, body, nested, quoted), is a refusal. A task file that cannot be
read is refused too (fail closed). Nothing here writes.
"""

import re
from pathlib import Path

GUARD_EXIT_CODE = 4
CANONICAL_KEY = "onStatusChange"
# Any case, camel or snake or kebab. Word characters around the key are not required: this is a raw
# scan and the canonical spelling matched case-insensitively is what a YAML parser would key on.
KEY_RE = re.compile(r"onstatuschange|on_status_change|on-status-change", re.IGNORECASE)
MAX_SCAN_BYTES = 8 * 1024 * 1024


class GuardRefused(Exception):
    """The edit was refused because the key was found or the file could not be checked (exit 4)."""

    exit_code = GUARD_EXIT_CODE

    def __init__(self, message, path=None, keys=()):
        super().__init__(message)
        self.message = message
        self.path = str(path) if path is not None else None
        self.keys = list(keys)


def scan_text(text):
    """Return every spelling of the key found in `text`, in order of appearance."""
    if not text:
        return []
    return [match.group(0) for match in KEY_RE.finditer(text)]


def read_for_scan(path):
    """Read a file as text for scanning; raises GuardRefused when it cannot be read (fail closed)."""
    path = Path(path)
    try:
        with open(path, "rb") as handle:
            data = handle.read(MAX_SCAN_BYTES + 1)
    except OSError as error:
        raise GuardRefused("%s guard: cannot read %s (%s); the edit is refused" % (CANONICAL_KEY, path.name, error), path) from error
    if len(data) > MAX_SCAN_BYTES:
        raise GuardRefused("%s guard: %s is larger than %d bytes; the edit is refused" % (CANONICAL_KEY, path.name, MAX_SCAN_BYTES), path)
    return data.decode("utf-8", errors="replace")


def check_file(path, label=None):
    path = Path(path)
    keys = scan_text(read_for_scan(path))
    if keys:
        raise GuardRefused(
            "%s key found in %s (%s); the edit is refused because Backlog.md would execute it on a status change"
            % (CANONICAL_KEY, label or path.name, ", ".join(repr(key) for key in keys)),
            path,
            keys,
        )


def config_path(repo):
    return Path(repo) / "backlog" / "config.yml"


def check(repo, task_path):
    """Refuse (GuardRefused, exit 4) when backlog/config.yml or the task file carries the key."""
    check_file(config_path(repo), "backlog/config.yml")
    check_file(task_path)
