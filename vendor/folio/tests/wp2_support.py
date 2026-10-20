"""Shared helpers for the WP-2 red tests (Backlog adapter, tool resolver, onStatusChange guard).

The WP-2 seams do not exist on the base; every test imports them through `seam()` so that a missing
module FAILS with a message naming the seam instead of erroring at import time. No stub modules are
added by WP2-1. The contract the tests expect from WP2-2 (names are the wished-for API):

folio/backlog/tools.py
  BACKLOG_VERSION = "1.53.0"; BIN_ENV = "FOLIO_BACKLOG_BIN"
  ToolError(Exception) with .exit_code == 7
  ToolResolver(environ, home, expected_sha256=None).backlog() -> object with .path, .version, .sha256
    resolution: environ[BIN_ENV], else $XDG_DATA_HOME/folio/tools/backlog-1.53.0/backlog
    (XDG_DATA_HOME defaults to <environ HOME>/.local/share); runs `<path> --version` with HOME=home.
folio/backlog/adapter.py
  BacklogError(Exception) with .exit_code; RefusedValue(BacklogError) exit 4; DoctorFailed(BacklogError)
  BacklogClient(binary, repo, home)
    .list() -> [task dict]          (task list --json, cached on tasks-dir mtimes + HEAD)
    .view(task_id) -> task dict      (task view ID --json)
    .create(title, description=None, labels=(), status=None, priority=None, project=None, fid=None)
        -> object with .fid (16 hex) and .id ("TASK-N", resolved by re-listing on the fid label)
    .edit(task_id, status=None, title=None, description=None, labels=None, priority=None, project=None)
    .doctor() -> report; raises DoctorFailed when backlog/config.yml has remote_operations: true
    .doc_create(title, content=None) -> "doc-N"; .doc_view(doc_id) -> {"id","title","content"}
    .doc_update(doc_id, content=None, title=None)
    .resolve(fid) -> "TASK-N"
folio/backlog/guard.py
  GuardRefused(Exception) with .exit_code == 4
  scan_text(text) -> [matched key strings]; check(repo, task_path) raises GuardRefused
"""

import importlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
FOLIO_BACKLOG = REPO_ROOT / "folio" / "backlog"
SEAMS = ("adapter", "tools", "guard")
FID_HEX = "0123456789abcdef"


def seam(case, name):
    """Import folio.backlog.<name> or fail the test with the missing-seam reason."""
    try:
        return importlib.import_module("folio.backlog." + name)
    except ImportError as error:
        case.fail("WP-2 seam folio/backlog/%s.py is missing: %s" % (name, error))


def write_fake_backlog(directory, version="1.53.0", responses=()):
    """A stand-in binary: records every call (argv, HOME, cwd) and answers from a canned table.

    `responses` is a sequence of (argv_prefix, stdout, returncode); the first prefix that matches the
    call's argv wins. `--version` always prints `version`. Anything else exits 0 with empty stdout.
    """
    directory = Path(directory)
    log = directory / "calls.log"
    table = directory / "responses.json"
    table.write_text(json.dumps([[list(prefix), stdout, code] for prefix, stdout, code in responses]), encoding="utf-8")
    fake = directory / "backlog"
    fake.write_text(
        "#!%s\n"
        "import json, os, sys\n"
        "argv = sys.argv[1:]\n"
        "with open(%r, 'a', encoding='utf-8') as handle:\n"
        "    handle.write(json.dumps({'argv': argv, 'home': os.environ.get('HOME'), 'cwd': os.getcwd()}) + '\\n')\n"
        "if argv == ['--version']:\n"
        "    print(%r)\n"
        "    sys.exit(0)\n"
        "with open(%r, encoding='utf-8') as handle:\n"
        "    table = json.load(handle)\n"
        "for prefix, stdout, code in table:\n"
        "    if argv[:len(prefix)] == prefix:\n"
        "        sys.stdout.write(stdout)\n"
        "        sys.exit(code)\n"
        "sys.exit(0)\n" % (sys.executable, str(log), version, str(table)),
        encoding="utf-8",
    )
    fake.chmod(0o700)
    return fake, log


def calls(log):
    if not Path(log).exists():
        return []
    return [json.loads(line) for line in Path(log).read_text(encoding="utf-8").splitlines()]


def argvs(log):
    return [call["argv"] for call in calls(log)]


def task_list_json(*tasks):
    """A schemaVersion 1 `task list --json` document for (id, title, labels) tuples."""
    return json.dumps({
        "schemaVersion": 1,
        "kind": "task-list",
        "tasks": [{"id": task_id, "title": title, "status": "To Do", "labels": list(labels)} for task_id, title, labels in tasks],
    })


def tree_digest(root):
    """{relative path: sha256} for every file under root (used to prove the adapter wrote nothing)."""
    import hashlib

    digest = {}
    for path in sorted(Path(root).rglob("*")):
        if path.is_file():
            digest[path.relative_to(root).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return digest


class FakeBacklogCase(unittest.TestCase):
    """A temp dir, a temp HOME and a recording fake binary; no real Backlog needed."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="folio-wp2-fake-")
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)
        self.home = self.dir / "home"
        self.home.mkdir()
        self.repo = self.dir / "repo"
        (self.repo / "backlog" / "tasks").mkdir(parents=True)
        (self.repo / "backlog" / "config.yml").write_text(
            "project_name: Fake\nremote_operations: false\ncheck_active_branches: false\nauto_commit: false\n"
            "auto_open_browser: false\n",
            encoding="utf-8",
        )

    def fake(self, version="1.53.0", responses=()):
        directory = self.dir / "bin"
        directory.mkdir(exist_ok=True)
        self.binary, self.log = write_fake_backlog(directory, version, responses)
        return self.binary

    def assert_temp_home_everywhere(self):
        recorded = calls(self.log)
        self.assertTrue(recorded, "the fake binary was never called")
        for call in recorded:
            self.assertEqual(call["home"], str(self.home), call)
            self.assertNotEqual(call["home"], os.environ.get("HOME"), call)
