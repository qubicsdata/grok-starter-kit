"""Resolve the pinned Backlog.md binary and verify its version and sha256 before anything runs it.

Resolution order: `FOLIO_BACKLOG_BIN` from the environment mapping handed to the resolver (never the
process environment), else `$XDG_DATA_HOME/folio/tools/backlog-<version>/backlog` where
`XDG_DATA_HOME` defaults to `<HOME>/.local/share`. The sha256 is checked before `--version` is run,
so a binary with the wrong hash is never executed. Every mismatch is a ToolError with exit code 7.

Until WP-9 lands `folio/locks/backlog.lock.json`, the expected version is the constant below and the
expected sha256 is supplied by the caller (WP-9 reads both from the lock).
"""

import hashlib
import subprocess
from pathlib import Path

# TODO(WP-9): read backlog_version and the sha256 from folio/locks/backlog.lock.json.
BACKLOG_VERSION = "1.53.0"
BIN_ENV = "FOLIO_BACKLOG_BIN"
TOOL_EXIT_CODE = 7
VERSION_TIMEOUT = 30


class ToolError(Exception):
    """The pinned tool is missing, has the wrong version or the wrong sha256 (exit 7)."""

    exit_code = TOOL_EXIT_CODE

    def __init__(self, message, path=None):
        super().__init__(message)
        self.message = message
        self.path = str(path) if path is not None else None


class ResolvedTool:
    def __init__(self, path, version, sha256):
        self.path = str(path)
        self.version = version
        self.sha256 = sha256


def default_binary(environ, version=BACKLOG_VERSION):
    data_home = environ.get("XDG_DATA_HOME") or ""
    if not data_home:
        data_home = str(Path(environ.get("HOME") or "~").expanduser() / ".local" / "share")
    return Path(data_home) / "folio" / "tools" / ("backlog-" + version) / "backlog"


def sha256_of(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def tool_env(environ, home):
    """The minimal environment for a tool subprocess: a temporary HOME, no colour, no inherited extras."""
    return {
        "HOME": str(home),
        "PATH": environ.get("PATH") or "/usr/bin:/bin",
        "LANG": "C.UTF-8",
        "NO_COLOR": "1",
        "TERM": "dumb",
    }


class ToolResolver:
    def __init__(self, environ, home, expected_sha256=None):
        self.environ = dict(environ)
        self.home = Path(home)
        self.expected_sha256 = expected_sha256.lower() if expected_sha256 else None

    def backlog(self):
        configured = self.environ.get(BIN_ENV)
        path = Path(configured) if configured else default_binary(self.environ)
        if not path.is_file():
            raise ToolError("Backlog.md %s binary not found at %s (set %s or install it under $XDG_DATA_HOME/folio/tools)"
                            % (BACKLOG_VERSION, path, BIN_ENV), path)
        try:
            digest = sha256_of(path)
        except OSError as error:
            raise ToolError("Backlog.md binary at %s is unreadable: %s" % (path, error), path) from error
        if self.expected_sha256 is not None and digest != self.expected_sha256:
            raise ToolError("Backlog.md binary at %s has sha256 %s; the recorded sha256 is %s (not run)"
                            % (path, digest, self.expected_sha256), path)
        version = self._version(path)
        if version != BACKLOG_VERSION:
            raise ToolError("Backlog.md binary at %s reports version %r; Folio is pinned to exactly %s"
                            % (path, version, BACKLOG_VERSION), path)
        return ResolvedTool(path, version, digest)

    def _version(self, path):
        try:
            result = subprocess.run(
                [str(path), "--version"],
                cwd=str(self.home),
                env=tool_env(self.environ, self.home),
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                timeout=VERSION_TIMEOUT,
            )
        except (OSError, subprocess.SubprocessError) as error:
            raise ToolError("could not run %s --version: %s" % (path, error), path) from error
        if result.returncode != 0:
            raise ToolError("%s --version exited %d (expected %s): %s"
                            % (path, result.returncode, BACKLOG_VERSION, result.stderr.strip()), path)
        return result.stdout.strip()
