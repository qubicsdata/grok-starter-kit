"""WP-5a red tests (static, M-6): no code path from approvals writes a task note.

The scanner parses folio/approvals.py and every folio module it imports (the folio-internal import
closure) and flags:
  - in the closure: an import of folio.backlog.* or folio.switchboard.* (task edits, and
    DecisionService's Store.mutate history line), and any string constant that is a Backlog notes
    flag (`--notes`, `--append-notes`, `--notes-append`) or the argv word "edit";
  - in folio/approvals.py itself: an import of folio.notes, folio.core.Store, folio.migration or
    folio.backup (the JSON-store writers; folio/core.py imports folio.notes lazily inside Store
    methods, which is why this rule is direct-only), an import of subprocess or pty, a call to
    os.system/os.popen/os.exec*/os.spawn*/os.posix_spawn*, and a call of a task-writing method (edit,
    append_notes, mutate, create_task, update_task, change_section, doc_create, doc_update).
The approvals trace goes only to the local log (ApprovalLog). The dialog subprocess lives in
folio/dialogs.py, which is reused, not scanned for subprocess. The scanner is checked against planted
violations so a silent miss cannot pass.
"""

import ast
import re
import tempfile
import unittest
from pathlib import Path

from wp5_support import APPROVALS_PY, REPO_ROOT

FOLIO = REPO_ROOT / "folio"
BANNED_PACKAGES = ("folio.backlog", "folio.switchboard")
ENTRY_BANNED = ("folio.notes", "folio.core.Store", "folio.migration", "folio.backup")
NOTES_FLAG = re.compile(r"(?<![\w-])--(?:append-notes|notes-append|notes)(?![\w-])")
WRITE_METHODS = ("edit", "append_notes", "mutate", "create_task", "update_task", "change_section", "doc_create", "doc_update")
PROCESS_MODULES = ("subprocess", "pty")
OS_PROCESS = re.compile(r"(system|popen|exec\w*|spawn\w*|posix_spawn\w*|fork\w*)")


def dotted(node):
    if isinstance(node, ast.Attribute):
        head = dotted(node.value)
        return head + "." + node.attr if head else node.attr
    if isinstance(node, ast.Name):
        return node.id
    return ""


def module_name(path, root):
    parts = list(Path(path).relative_to(root.parent).with_suffix("").parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def imported(tree, name, is_package):
    """Absolute module names imported by a module called `name`."""
    package = name if is_package else name.rpartition(".")[0]
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.extend((alias.name, node.lineno) for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ""
            if node.level:
                anchor = package.split(".")
                anchor = anchor[:len(anchor) - (node.level - 1)]
                base = ".".join(anchor + ([base] if base else []))
            found.append((base, node.lineno))
            # `from . import notes` imports a submodule, not a name.
            found.extend((base + "." + alias.name, node.lineno) for alias in node.names)
    return found


def resolve_module(name, root):
    relative = name.split(".")[1:]
    for candidate in (root.joinpath(*relative).with_suffix(".py"), root.joinpath(*relative, "__init__.py")):
        if relative and candidate.is_file():
            return candidate
    if not relative:
        return root / "__init__.py"
    return None


def banned(name, entry=False):
    packages = BANNED_PACKAGES + (ENTRY_BANNED if entry else ())
    return any(name == package or name.startswith(package + ".") for package in packages)


def scan(entry, root=FOLIO):
    """Return ["<module>:<line>: <reason>"] for the entry module and its folio import closure."""
    root_name = root.name
    findings, seen, queue = [], set(), [Path(entry)]
    while queue:
        path = queue.pop()
        if path in seen:
            continue
        seen.add(path)
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        name = module_name(path, root)
        is_entry = path == Path(entry)
        flagged = set()  # one import finding per statement line
        for target, line in imported(tree, name, path.name == "__init__.py"):
            if line in flagged:
                continue
            if target.split(".")[0] != root_name:
                if is_entry and target.split(".")[0] in PROCESS_MODULES:
                    findings.append("%s:%d: imports %s" % (name, line, target))
                    flagged.add(line)
                continue
            if banned(target, is_entry):
                findings.append("%s:%d: imports %s" % (name, line, target))
                flagged.add(line)
                continue
            resolved = resolve_module(target, root)
            if resolved is not None:
                queue.append(resolved)
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                if NOTES_FLAG.search(node.value) or node.value == "edit":
                    findings.append("%s:%d: string %r" % (name, node.lineno, node.value[:40]))
            if is_entry and isinstance(node, ast.Call):
                target = dotted(node.func)
                head, _dot, tail = target.rpartition(".")
                if head == "os" and OS_PROCESS.fullmatch(tail):
                    findings.append("%s:%d: os.%s" % (name, node.lineno, tail))
                if isinstance(node.func, ast.Attribute) and node.func.attr in WRITE_METHODS:
                    findings.append("%s:%d: calls .%s()" % (name, node.lineno, node.func.attr))
    return sorted(findings)


class NoTaskNoteFromApprovalsTests(unittest.TestCase):
    def test_approvals_module_exists(self):
        self.assertTrue(APPROVALS_PY.is_file(), "WP-5a seam folio/approvals.py is missing")

    def test_no_task_edit_or_notes_path_from_approvals(self):
        self.assertTrue(APPROVALS_PY.is_file(), "WP-5a seam folio/approvals.py is missing")
        self.assertEqual(scan(APPROVALS_PY), [])

    def test_no_backlog_notes_flag_anywhere_in_folio(self):
        """Guard (green on the base): no folio module builds a Backlog notes argv at all."""
        hits = []
        for path in sorted(FOLIO.rglob("*.py")):
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
                if isinstance(node, ast.Constant) and isinstance(node.value, str) and NOTES_FLAG.search(node.value):
                    hits.append("%s:%d" % (path.relative_to(REPO_ROOT), node.lineno))
        self.assertEqual(hits, [])

    def test_adapter_edit_accepts_no_notes(self):
        """Guard (green on the base): BacklogClient.edit has no notes parameter to reach."""
        import inspect

        from folio.backlog.adapter import BacklogClient
        parameters = set(inspect.signature(BacklogClient.edit).parameters)
        self.assertFalse({name for name in parameters if "note" in name or "plan" in name}, parameters)


class ScannerSelfTests(unittest.TestCase):
    """Planted violations: each must be reported, and a clean module must not be."""

    def plant(self, files):
        tmp = tempfile.TemporaryDirectory(prefix="folio-wp5-scan-")
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name) / "folio"
        (root / "backlog").mkdir(parents=True)
        (root / "switchboard").mkdir()
        for name, text in {"__init__.py": "", "backlog/__init__.py": "", "switchboard/__init__.py": "",
                           "core.py": "class AppError(Exception):\n    pass\n", "dialogs.py": "import subprocess\n", **files}.items():
            (root / name).write_text(text, encoding="utf-8")
        return root

    def findings(self, approvals, extra=None):
        root = self.plant({"approvals.py": approvals, **(extra or {})})
        return scan(root / "approvals.py", root)

    def test_clean_module_passes(self):
        self.assertEqual(self.findings("from .core import AppError\nfrom .dialogs import subprocess\nimport os, json\n"
                                       "def f(log):\n    log.record_resolution('p', 'd', 'approve', None)\n"
                                       "    return os.open('x', os.O_RDONLY | os.O_NOFOLLOW)\n"), [])

    def test_planted_violations_are_reported(self):
        planted = {
            "relative backlog import": "from .backlog import adapter\n",
            "absolute backlog import": "import folio.backlog.adapter\n",
            "from-package backlog name": "from . import backlog\n",
            "notes module": "from .notes import change_section\n",
            "json store": "from .core import AppError, Store\n",
            "migration": "from . import migration\n",
            "switchboard decisions": "from .switchboard.decisions import DecisionService\n",
            "notes flag": "ARGV = ['task', 'x', '--notes', 'y']\n",
            "append notes flag": "ARGV = ('--append-notes=y',)\n",
            "edit argv word": "ARGV = ['task', 'edit']\n",
            "subprocess": "import subprocess\n",
            "subprocess from": "from subprocess import run\n",
            "os.system": "import os\nos.system('true')\n",
            "os.posix_spawn": "import os\nos.posix_spawn('/bin/true', [], {})\n",
            "client edit": "def f(client):\n    client.edit('TASK-1', status='Done')\n",
            "store mutate": "def f(store):\n    store.mutate('p', lambda _: 'Approved', None)\n",
            "append notes call": "def f(store):\n    store.append_notes('p', {}, None)\n",
        }
        for name, text in planted.items():
            with self.subTest(planted=name):
                self.assertTrue(self.findings(text), "the scanner missed: %s" % name)

    def test_violation_in_an_imported_folio_module_is_reported(self):
        found = self.findings("from .helper import go\n", {"helper.py": "from .backlog.adapter import BacklogClient\n"})
        self.assertEqual(found, ["folio.helper:1: imports folio.backlog.adapter"])
        found = self.findings("from . import helper\n", {"helper.py": "FLAG = '--notes'\n"})
        self.assertEqual(found, ["folio.helper:1: string '--notes'"])

    def test_store_writers_are_banned_only_as_direct_imports(self):
        # folio/core.py imports folio.notes lazily inside Store methods; approvals may still import AppError from it.
        lazy = {"helper.py": "def f():\n    from .notes import source_manifest\n", "notes.py": ""}
        self.assertEqual(self.findings("from .helper import f\n", lazy), [])
        self.assertEqual(self.findings("from .notes import source_manifest\n", {"notes.py": ""}),
                         ["folio.approvals:1: imports folio.notes"])


if __name__ == "__main__":
    unittest.main()
