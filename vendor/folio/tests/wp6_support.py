"""Shared helpers for the WP-6 red tests (cuts: route table, subprocess allow-list, tree hygiene).

Nothing here is a stub: the seams below do not exist on the base and every test reaches them through
`seam_attr()` so a missing name FAILS with a message naming the seam instead of erroring. The contract
the tests expect from WP6-2 (names are the wished-for API):

folio/api.py
  ROUTE_TABLE                       a tuple of (method, pattern) entries, the ONLY routes route() serves.
      method is "GET"/"POST"/"PATCH"/"DELETE", or "*" for the one plugin-mount entry; pattern is a regex
      string (a compiled pattern is accepted too) matched with re.fullmatch against the request path.
      The table holds the core routes (CORE_ROUTES below, one entry per method and path shape) plus the
      plugin mount under folio.plugins.PREFIX, and nothing else: no "/api/backup", "/api/doctor",
      "/api/demo", "/api/folders/pick" or "/api/projects/<id>/export". A (method, path) that matches no
      entry -> AppError("Not found.", 404), over HTTP (also with a valid credential) and over the
      direct transport alike.
  App(store, approvals=None, plugins=None)   no folder picker.
folio/web.py
  main() has no --demo; the static asset table has no /theme.js; the GET special cases for
  /api/backup and /api/projects/<id>/export are gone.
folio/cli.py
  no `tasks` group (list/add/update/done/reopen/delete) and no `agent-guide`: both are USAGE errors.
Deleted files (the tree checks): folio/folder_picker.py, folder_picker.py, folio/windows_desktop.py,
  folio/guide.py, folio/guide.md, folio/static/theme.js, scripts/build-*.py, scripts/install-folio*.py,
  scripts/homebrew-formula.py, scripts/verify-*.py, the internal records folder and every Mac home or temp path.
Process spawns: the only app modules that import subprocess (or pty/multiprocessing, or call
  os.system/popen/exec*/spawn*/posix_spawn*/fork*) are folio/backlog/adapter.py and
  folio/backlog/tools.py (the adapter allow-list, D-13) and folio/dialogs.py (the WP-5 approvals
  dialog over fixed system tool paths; see the open question in the WP6-1 report).

Every needle below is built from fragments or escapes so these files never match their own scans.
"""

import importlib
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
FOLIO = REPO_ROOT / "folio"
TESTS = REPO_ROOT / "tests"
SCRIPTS = REPO_ROOT / "scripts"
STATIC = FOLIO / "static"
PYPROJECT = REPO_ROOT / "pyproject.toml"

SKIP_DIRS = frozenset({".git", "__pycache__", "node_modules", ".browser-tests"})

# --- route contract -----------------------------------------------------------------------------
ID = "0123456789abcdef"
DECISION = "dec_0123456789abcdef"
CORE_ROUTES = (
    ("GET", "/api/state"),
    ("GET", "/api/approvals"),
    ("GET", "/api/projects/%s/brief" % ID),
    ("GET", "/api/projects/%s/notes/sections" % ID),
    ("POST", "/api/clients"),
    ("POST", "/api/projects"),
    ("POST", "/api/projects/%s/brief" % ID),
    ("POST", "/api/projects/%s/source" % ID),
    ("POST", "/api/projects/%s/notes/sections" % ID),
    ("PATCH", "/api/projects/%s/notes/sections/%s" % (ID, ID)),
    ("DELETE", "/api/projects/%s/notes/sections/%s" % (ID, ID)),
    ("POST", "/api/projects/%s/relocate" % ID),
    ("PATCH", "/api/clients/%s" % ID),
    ("PATCH", "/api/projects/%s" % ID),
    ("POST", "/api/projects/%s/workstreams" % ID),
    ("POST", "/api/projects/%s/tasks" % ID),
    ("PATCH", "/api/projects/%s/tasks/%s" % (ID, ID)),
    ("DELETE", "/api/projects/%s/tasks/%s" % (ID, ID)),
    ("POST", "/api/projects/%s/notes/append" % ID),
    ("POST", "/api/approvals/%s/resolve" % DECISION),
)
PLUGIN_ROUTES = (("GET", "/api/plugins/fake/ping"), ("POST", "/api/plugins/fake/items"))
# (method, path, body) for the routes WP-6 cuts; a GET carries no body.
REMOVED_ROUTES = (
    ("GET", "/api/backup", None),
    ("GET", "/api/doctor", None),
    ("GET", "/api/projects/%s/export" % ID, None),
    ("POST", "/api/folders/pick", {}),
    ("POST", "/api/demo", {}),
)
METHODS = ("GET", "POST", "PATCH", "DELETE")
NOT_FOUND = (404, {"error": "Not found."})

# --- tree rules (WP-0a local_path codes, WP-0b blocking) -------------------------------------------
LOCAL_PATH_RULES = (
    ("local_path.users", re.compile(re.escape("/" + "Users" + "/") + r"[A-Za-z0-9._-]+")),
    ("local_path.home", re.compile(re.escape("/" + "home" + "/") + r"(?!linuxbrew\b)[A-Za-z0-9._-]+")),
    ("local_path.tmp", re.compile(re.escape("/" + "private/var/folders" + "/"))),
)
BIDI_OVERRIDES = tuple(chr(code) for code in range(0x202A, 0x202E + 1))
BIDI_ISOLATES = tuple(chr(code) for code in range(0x2066, 0x2069 + 1))
BIDI_CHARS = frozenset(BIDI_OVERRIDES + BIDI_ISOLATES)


def seam_attr(case, module, name, wp="WP-6"):
    """Return folio.<module>.<name>, or fail the test with the missing-seam reason."""
    try:
        loaded = importlib.import_module("folio." + module)
    except ImportError as error:
        case.fail("%s seam folio/%s.py is missing: %s" % (wp, module, error))
    if not hasattr(loaded, name):
        case.fail("%s seam folio/%s.py has no %s" % (wp, module, name))
    return getattr(loaded, name)


def tree_files(root=REPO_ROOT):
    """Every file under root, sorted, skipping VCS, bytecode and dependency directories."""
    root = Path(root)
    pending = [root]
    found = []
    while pending:
        directory = pending.pop()
        for entry in sorted(directory.iterdir()):
            if entry.is_symlink():
                continue
            if entry.is_dir():
                if entry.name not in SKIP_DIRS:
                    pending.append(entry)
            elif entry.is_file():
                found.append(entry)
    return sorted(found)


def text_of(path):
    """The file as UTF-8 text, or None for binary content."""
    try:
        return Path(path).read_bytes().decode("utf-8")
    except UnicodeDecodeError:
        return None


def local_path_hits(root=REPO_ROOT):
    """["<path>:<line>: <code>"] for every local_path rule match in the tree (never the matched text)."""
    hits = []
    for path in tree_files(root):
        text = text_of(path)
        if text is None:
            continue
        for number, line in enumerate(text.splitlines(), 1):
            for code, rule in LOCAL_PATH_RULES:
                if rule.search(line):
                    hits.append("%s:%d: %s" % (path.relative_to(root).as_posix(), number, code))
    return hits


def bidi_counts(text):
    """{code point: number of CHARACTERS} for the bidi overrides and isolates in `text` (never bytes)."""
    counts = {}
    for char in text:
        if char in BIDI_CHARS:
            counts[char] = counts.get(char, 0) + 1
    return counts


def bidi_hits(root=REPO_ROOT):
    """{relative path: {code point: count}} for every file in the tree holding a raw bidi character."""
    hits = {}
    for path in tree_files(root):
        text = text_of(path)
        if text is None:
            continue
        counts = bidi_counts(text)
        if counts:
            hits[path.relative_to(root).as_posix()] = counts
    return hits


def describe_bidi(hits):
    return "; ".join("%s: %d (%s)" % (path, sum(counts.values()),
                                      ", ".join("U+%04X x%d" % (ord(char), count) for char, count in sorted(counts.items())))
                     for path, counts in sorted(hits.items()))


def app_python_files(root=REPO_ROOT):
    """The app's Python (folio/ including the plugin host and the adapter, the launchers) without plugins."""
    root = Path(root)
    files = [path for path in sorted((root / "folio").rglob("*.py")) if "__pycache__" not in path.parts]
    for name in ("server.py", "folder_picker.py", "bin/folio"):
        candidate = root / name
        if candidate.is_file():
            files.append(candidate)
    return files


def line_count(paths):
    return sum(len(Path(path).read_bytes().splitlines()) for path in paths)


def python_child_argv(script, *extra_paths):
    """argv for an isolated child interpreter (-I: no cwd, PYTHONPATH or user site on sys.path)."""
    paths = [str(REPO_ROOT), str(TESTS)] + [str(path) for path in extra_paths]
    return [sys.executable, "-I", "-c", "import sys; sys.path[:0] = %r\n%s" % (paths, script)]
