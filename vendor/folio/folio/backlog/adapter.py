"""BacklogClient: list, view, create, edit, doctor and doc notes through the pinned Backlog.md binary.

Every call is a fixed argv (never a shell) whose first word is one of ALLOWED_FIRST_WORDS; the web UI
subcommand is never allowed. Every user-supplied value is validated before anything is spawned: values
that start with `-`, contain NUL, or (for titles) exceed 79 characters or span lines are refused with
exit 4 and no subprocess. Edits run the onStatusChange guard between `task view` and `task edit`.

`create` has no JSON output and no `--id`, so the new TASK-N is resolved by re-listing on the `fid:`
label. `list` is cached on a key of the tasks-dir listing (name, mtime, size) plus the resolved git
HEAD; the client's own writes drop the cache.
"""

import copy
import json
import os
import re
import secrets
import subprocess
from pathlib import Path

from . import guard
from .tools import tool_env

ALLOWED_FIRST_WORDS = ("init", "task", "doctor", "config", "doc", "--version")
TITLE_MAX = 79
TIMEOUT = 60
FID_RE = re.compile(r"^[0-9a-f]{16}$")
TASK_ID_RE = re.compile(r"^[A-Za-z][A-Za-z0-9]*-[0-9]+(\.[0-9]+)*$")
DOC_ID_RE = re.compile(r"^doc-[0-9]+$")
CREATED_DOC_RE = re.compile(r"^Created document (doc-[0-9]+)\s*$", re.MULTILINE)
FID_LABEL = "fid:"
# D-8 pins: a repo whose config turns any of these on fails `doctor` before the binary is asked.
PINNED_FALSE = ("remote_operations", "check_active_branches", "auto_commit")
EXIT_CODES = {"VALIDATION": 4, "NOT_FOUND": 2, "AMBIGUOUS_REFERENCE": 2, "CONFLICT": 3, "STORAGE": 5}
TASK_DIRS = ("tasks", "drafts", "completed", "archive")


class BacklogError(Exception):
    def __init__(self, code, message, exit_code=None, stderr=""):
        super().__init__(message)
        self.code = code
        self.message = message
        self.exit_code = exit_code if exit_code is not None else EXIT_CODES.get(code, 5)
        self.stderr = stderr


class RefusedValue(BacklogError):
    """A value that must never reach the binary (option-like, too long, malformed): exit 4."""

    def __init__(self, message):
        super().__init__("VALIDATION", message, 4)


class DoctorFailed(BacklogError):
    def __init__(self, message, stderr=""):
        super().__init__("CONFLICT", message, 3, stderr)


class Created:
    def __init__(self, fid, task_id):
        self.fid = fid
        self.id = task_id

    def __repr__(self):
        return "Created(fid=%r, id=%r)" % (self.fid, self.id)


def _text(value, field):
    if not isinstance(value, str):
        raise RefusedValue("%s must be a string, not %s" % (field, type(value).__name__))
    if "\x00" in value:
        raise RefusedValue("%s must not contain NUL" % field)
    if value.startswith("-"):
        raise RefusedValue("%s must not start with '-' (refused: %r)" % (field, value))
    return value


def _word(value, field):
    """A single-line, non-empty value such as a status, priority, project or id."""
    value = _text(value, field)
    if not value.strip():
        raise RefusedValue("%s must not be empty" % field)
    if "\n" in value or "\r" in value:
        raise RefusedValue("%s must be a single line" % field)
    return value


def _title(value, field="title"):
    value = _word(value, field)
    if value != value.strip():
        raise RefusedValue("%s must not start or end with whitespace" % field)
    if len(value) > TITLE_MAX:
        raise RefusedValue("%s is %d characters; the limit is %d" % (field, len(value), TITLE_MAX))
    return value


def _label(value):
    value = _word(value, "label")
    if "," in value or any(char.isspace() for char in value):
        raise RefusedValue("label must not contain commas or whitespace (refused: %r)" % value)
    return value


def _labels(values, field="labels"):
    if isinstance(values, str) or not hasattr(values, "__iter__"):
        raise RefusedValue("%s must be a sequence of labels" % field)
    labels = [_label(value) for value in values]
    if any(label.lower().startswith(FID_LABEL) for label in labels):
        raise RefusedValue("%s must not carry a %s label; it is assigned by Folio" % (field, FID_LABEL))
    return labels


def _fid(value):
    value = _text(value, "fid")
    if not FID_RE.match(value):
        raise RefusedValue("fid must be 16 lowercase hex characters (refused: %r)" % value)
    return value


def _task_id(value):
    value = _word(value, "task id")
    if not TASK_ID_RE.match(value):
        raise RefusedValue("task id must look like TASK-N (refused: %r)" % value)
    return value


def _doc_id(value):
    value = _word(value, "doc id")
    if not DOC_ID_RE.match(value):
        raise RefusedValue("doc id must look like doc-N (refused: %r)" % value)
    return value


def _body(value, field):
    """Multi-line markdown (description, doc content): only the option-like and NUL refusals apply."""
    return _text(value, field)


def _stat_signature(path):
    try:
        with os.scandir(path) as entries:
            rows = []
            for entry in entries:
                try:
                    stat = entry.stat(follow_symlinks=False)
                except OSError:
                    rows.append((entry.name, None))
                    continue
                rows.append((entry.name, stat.st_mtime_ns, stat.st_size))
    except OSError:
        return None
    return tuple(sorted(rows))


def _git_dir(repo):
    dot_git = Path(repo) / ".git"
    if dot_git.is_dir():
        return dot_git
    if dot_git.is_file():
        text = dot_git.read_text(encoding="utf-8", errors="replace")
        for line in text.splitlines():
            if line.startswith("gitdir:"):
                return (Path(repo) / line[len("gitdir:"):].strip()).resolve()
    return None


def _read_ref(git_dir, ref):
    for base in _ref_bases(git_dir):
        loose = base / ref
        if loose.is_file():
            return loose.read_text(encoding="utf-8", errors="replace").strip()
    for base in _ref_bases(git_dir):
        packed = base / "packed-refs"
        if packed.is_file():
            for line in packed.read_text(encoding="utf-8", errors="replace").splitlines():
                parts = line.split()
                if len(parts) == 2 and parts[1] == ref:
                    return parts[0]
    return None


def _ref_bases(git_dir):
    bases = [git_dir]
    common = git_dir / "commondir"
    if common.is_file():
        bases.append((git_dir / common.read_text(encoding="utf-8", errors="replace").strip()).resolve())
    return bases


def head_key(repo):
    """The resolved HEAD (commit id or unborn ref text), or a stat signature when refs are opaque."""
    try:
        git_dir = _git_dir(repo)
        if git_dir is None:
            return None
        head = (git_dir / "HEAD").read_text(encoding="utf-8", errors="replace").strip()
        if not head.startswith("ref:"):
            return head
        ref = head[len("ref:"):].strip()
        resolved = _read_ref(git_dir, ref)
        if resolved is not None:
            return resolved
        signature = tuple(_stat_signature(base) for base in _ref_bases(git_dir))
        return (head, signature)
    except OSError:
        return None


class BacklogClient:
    def __init__(self, binary, repo, home, environ=None):
        self.binary = str(binary)
        self.repo = Path(repo)
        self.home = Path(home)
        self.environ = dict(os.environ if environ is None else environ)
        self._cache = None

    # -- subprocess ---------------------------------------------------------------------------------

    def _run(self, argv, check=True):
        argv = [str(item) for item in argv]
        if not argv or argv[0] not in ALLOWED_FIRST_WORDS:
            raise RefusedValue("refused backlog argv %r; allowed first words: %s" % (argv, ", ".join(ALLOWED_FIRST_WORDS)))
        try:
            result = subprocess.run(
                [self.binary, *argv],
                cwd=str(self.repo),
                env=tool_env(self.environ, self.home),
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                timeout=TIMEOUT,
            )
        except (OSError, subprocess.SubprocessError) as error:
            raise BacklogError("STORAGE", "could not run backlog %s: %s" % (" ".join(argv[:2]), error)) from error
        if check and result.returncode != 0:
            detail = (result.stderr or result.stdout).strip()
            raise BacklogError("STORAGE", "backlog %s exited %d: %s" % (" ".join(argv[:2]), result.returncode, detail),
                               stderr=result.stderr)
        return result

    def _json(self, argv, kind):
        result = self._run(argv)
        try:
            document = json.loads(result.stdout)
        except ValueError as error:
            raise BacklogError("STORAGE", "backlog %s returned invalid JSON: %s" % (" ".join(argv[:2]), error)) from error
        if not isinstance(document, dict):
            document = {}
        if document.get("kind") != kind or document.get("schemaVersion") != 1:
            raise BacklogError("STORAGE", "backlog %s returned an unexpected document (kind %r, schemaVersion %r; expected %s, 1)"
                               % (" ".join(argv[:2]), document.get("kind"), document.get("schemaVersion"), kind))
        return document

    # -- cache ---------------------------------------------------------------------------------------

    def _cache_key(self):
        backlog = self.repo / "backlog"
        parts = [head_key(self.repo)]
        for name in TASK_DIRS:
            parts.append(_stat_signature(backlog / name))
        try:
            config = (backlog / "config.yml").stat()
            parts.append((config.st_mtime_ns, config.st_size))
        except OSError:
            parts.append(None)
        return tuple(parts)

    def invalidate(self):
        self._cache = None

    # -- reads ---------------------------------------------------------------------------------------

    def list(self):
        key = self._cache_key()
        if self._cache is not None and self._cache[0] == key:
            return copy.deepcopy(self._cache[1])
        document = self._json(["task", "list", "--json"], "task-list")
        tasks = document.get("tasks")
        if not isinstance(tasks, list) or not all(isinstance(task, dict) for task in tasks):
            raise BacklogError("STORAGE", "backlog task list returned no task array")
        self._cache = (key, tasks)
        return copy.deepcopy(tasks)

    def view(self, task_id):
        task_id = _task_id(task_id)
        document = self._json(["task", "view", task_id, "--json"], "task-view")
        task = document.get("task")
        if not isinstance(task, dict):
            raise BacklogError("STORAGE", "backlog task view returned no task object")
        return task

    def resolve(self, fid):
        fid = _fid(fid)
        wanted = FID_LABEL + fid
        matches = [task.get("id") for task in self.list() if wanted in (task.get("labels") or [])]
        if not matches:
            raise BacklogError("NOT_FOUND", "no task carries the label %s" % wanted)
        if len(matches) > 1:
            raise BacklogError("AMBIGUOUS_REFERENCE", "%d tasks carry the label %s: %s" % (len(matches), wanted, ", ".join(map(str, matches))))
        return matches[0]

    # -- writes (through the binary only) ------------------------------------------------------------

    def create(self, title, description=None, labels=(), status=None, priority=None, project=None, fid=None):
        title = _title(title)
        fid = _fid(fid) if fid is not None else secrets.token_hex(8)
        argv = ["task", "create", title, "-l", FID_LABEL + fid]
        for label in _labels(labels):
            argv += ["-l", label]
        if description is not None:
            argv += ["-d", _body(description, "description")]
        if status is not None:
            argv += ["-s", _word(status, "status")]
        if priority is not None:
            argv += ["--priority", _word(priority, "priority")]
        if project is not None:
            argv += ["--project", _word(project, "project")]
        try:
            self._run(argv)
        finally:
            self.invalidate()
        # `task create` prints a banner, not JSON, and the number it names is not authoritative across
        # clones (fact 5): the TASK-N comes from re-listing on the fid label.
        return Created(fid, self.resolve(fid))

    def edit(self, task_id, status=None, title=None, description=None, labels=None, priority=None, project=None):
        task_id = _task_id(task_id)
        changes = []
        if status is not None:
            changes += ["-s", _word(status, "status")]
        if title is not None:
            changes += ["-t", _title(title)]
        if description is not None:
            changes += ["-d", _body(description, "description")]
        if labels is not None:
            if isinstance(labels, str) or not hasattr(labels, "__iter__"):
                raise RefusedValue("labels must be a sequence of labels")
            # An empty sequence adds no change and is refused below as "changes nothing".
            checked = [_label(label) for label in labels]
            if sum(label.lower().startswith(FID_LABEL) for label in checked) > 1:
                raise RefusedValue("labels must carry at most one %s label" % FID_LABEL)
            for label in checked:
                changes += ["-l", label]
        if priority is not None:
            changes += ["--priority", _word(priority, "priority")]
        if project is not None:
            changes += ["--project", _word(project, "project")]
        if not changes:
            raise RefusedValue("edit of %s changes nothing" % task_id)
        task = self.view(task_id)
        path = task.get("path")
        if not isinstance(path, str) or not path:
            raise BacklogError("STORAGE", "backlog task view %s reported no file path; the edit is refused" % task_id)
        try:
            guard.check(self.repo, self.repo / path)
        except guard.GuardRefused as error:
            raise RefusedValue(str(error)) from error
        try:
            self._run(["task", "edit", task_id, *changes])
        finally:
            self.invalidate()

    # -- doctor --------------------------------------------------------------------------------------

    def config_pins(self):
        """{key: raw value} for the top-level `key: value` lines of backlog/config.yml."""
        path = guard.config_path(self.repo)
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError as error:
            raise DoctorFailed("backlog/config.yml is unreadable: %s" % error) from error
        pins = {}
        for line in text.splitlines():
            if not line or line[0] in " \t#":
                continue
            key, sep, value = line.partition(":")
            if sep:
                pins[key.strip()] = value.split("#", 1)[0].strip().strip("'\"")
        return pins

    def doctor(self):
        pins = self.config_pins()
        bad = [key for key in PINNED_FALSE if pins.get(key, "false").lower() not in ("false", "no", "off", "0", "")]
        if bad:
            raise DoctorFailed("backlog/config.yml must pin %s to false (found: %s)"
                               % (", ".join(PINNED_FALSE), ", ".join("%s: %s" % (key, pins[key]) for key in bad)))
        try:
            guard.check_file(guard.config_path(self.repo), "backlog/config.yml")
        except guard.GuardRefused as error:
            raise DoctorFailed(str(error)) from error
        result = self._run(["doctor"], check=False)
        if result.returncode != 0:
            raise DoctorFailed("backlog doctor exited %d: %s" % (result.returncode, (result.stdout + result.stderr).strip()),
                               stderr=result.stderr)
        return {"pins": pins, "stdout": result.stdout, "ok": True}

    # -- docs (list notes) ---------------------------------------------------------------------------

    def doc_create(self, title, content=None):
        title = _title(title)
        if content is not None:
            content = _body(content, "content")
        result = self._run(["doc", "create", title])
        match = CREATED_DOC_RE.search(result.stdout)
        if not match:
            raise BacklogError("STORAGE", "backlog doc create did not report a document id: %s" % result.stdout.strip())
        doc_id = match.group(1)
        if content is not None:
            self.doc_update(doc_id, content=content)
        return doc_id

    def doc_update(self, doc_id, content=None, title=None):
        doc_id = _doc_id(doc_id)
        changes = []
        if content is not None:
            changes += ["--content", _body(content, "content")]
        if title is not None:
            changes += ["--title", _title(title)]
        if not changes:
            raise RefusedValue("update of %s changes nothing" % doc_id)
        self._run(["doc", "update", doc_id, *changes])

    def doc_view(self, doc_id):
        doc_id = _doc_id(doc_id)
        result = self._run(["doc", "view", doc_id, "--plain"])
        # 1.53.0 exits 0 and prints "Document doc-N not found." on stderr for a missing document.
        if not result.stdout.strip():
            raise BacklogError("NOT_FOUND", "backlog doc view %s: %s" % (doc_id, result.stderr.strip() or "no output"))
        front, content = _split_front_matter(result.stdout)
        return {"id": front.get("id", doc_id), "title": front.get("title", ""), "content": content}


def _split_front_matter(text):
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise BacklogError("STORAGE", "backlog doc view returned no front matter")
    try:
        end = lines.index("---", 1)
    except ValueError:
        raise BacklogError("STORAGE", "backlog doc view returned unterminated front matter") from None
    return _parse_front_matter(lines[1:end]), "\n".join(lines[end + 1:])


def _parse_front_matter(lines):
    """A small reader for the flat `key: value` front matter Backlog writes (block scalars folded)."""
    front = {}
    index = 0
    while index < len(lines):
        line = lines[index]
        index += 1
        if not line.strip() or line.startswith((" ", "\t")):
            continue
        key, sep, value = line.partition(":")
        if not sep:
            continue
        value = value.strip()
        if value in (">", ">-", "|", "|-"):
            block = []
            while index < len(lines) and (lines[index].startswith((" ", "\t")) or not lines[index].strip()):
                block.append(lines[index].strip())
                index += 1
            value = ("\n" if value.startswith("|") else " ").join(part for part in block if part)
        elif len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
            inner = value[1:-1]
            value = inner.replace("''", "'") if value[0] == "'" else inner.replace('\\"', '"')
        front[key.strip()] = value
    return front
