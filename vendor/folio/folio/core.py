"""Storage, validation, and domain operations for Folio workspaces."""

import json
import os
import re
import tempfile
import threading
import uuid
from datetime import date, datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
from .locking import lock_file
from .paths import default_workspace, path_identity

DEFAULT_WORKSPACE = default_workspace()
STORAGE_MESSAGE = "Unable to read or save workspace data. Check folder permissions and JSON files. Existing files have not been reset."
# Left in a workspace after `migrate-workspace`, whose destination registers the same project folders.
MIGRATED_MARKER = ".migrated.json"


def resolve_workspace(data_dir=None, env=None):
    """The one workspace rule shared by the server and the CLI."""
    env = os.environ if env is None else env
    return data_dir or env.get("FOLIO_WORKSPACE") or str(default_workspace(env))


STATUSES = ("backlog", "in_progress", "blocked", "done")
PRIORITIES = ("low", "medium", "high", "urgent")
PROJECT_STATUSES = ("active", "on_hold", "completed", "archived")
COLORS = ("purple", "blue", "green", "orange", "pink", "teal")


class AppError(Exception):
    def __init__(self, message, status=400, code=None):
        super().__init__(message)
        self.status = status
        self.code = code


ORIGINS = ("user", "cli")
USER = {"origin": "user", "via": None}
VIA_LABEL = re.compile(r"[a-z0-9][a-z0-9:._-]{0,59}")

# The sync integration frozen in WP-7 (see the README freeze note). Its name stays reserved for plugins
# (folio.plugins.RESERVED). Folio 1.1.x files may still carry it as an activity origin, as a project key
# holding the old link and as the task keys in LEGACY_TASK_KEYS. Those load and are kept untouched, but
# Folio never acts on them; a restore detaches them (folio.backup). This is the only spelling of the name.
FROZEN = "switchboard"
LEGACY_TASK_KEYS = ("sb", "sb_unlinked")
# Origins a stored activity record may carry; new records use ORIGINS only.
RECORDED_ORIGINS = ORIGINS + (FROZEN,)


def now():
    return datetime.now(timezone.utc).isoformat()


def identifier():
    return uuid.uuid4().hex[:16]


def string(data, key, default="", required=False, limit=10000):
    value = data.get(key, default)
    if not isinstance(value, str) or len(value) > limit:
        raise AppError(f"{key.replace('_', ' ').capitalize()} must be text of at most {limit} characters.")
    value = value.strip()
    if required and not value:
        raise AppError(f"{key.replace('_', ' ').capitalize()} is required.")
    return value


def choice(data, key, choices, default):
    value = data.get(key, default)
    if value not in choices:
        raise AppError(f"Invalid {key.replace('_', ' ')}.")
    return value


def due_date(data, key="due_date", default=""):
    value = string(data, key, default, limit=10)
    if value:
        try:
            if date.fromisoformat(value).isoformat() != value:
                raise ValueError()
        except ValueError:
            raise AppError("Use a valid date in YYYY-MM-DD format.")
    return value


def read_json(path):
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor, temporary = tempfile.mkstemp(dir=path.parent, prefix=".write-", suffix=".tmp")
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def validate_project(project):
    if not isinstance(project, dict) or project.get("schema_version") != 1:
        raise AppError("Unsupported project schema.")
    if not re.fullmatch(r"[a-f0-9]{16}", string(project, "id")):
        raise AppError("Invalid project identity.")
    if type(project.get("revision")) is not int or project["revision"] < 1:
        raise AppError("Invalid project revision.")
    for key in ("name", "description", "status", "notes", "target_date", "created_at", "updated_at"):
        if key not in project:
            raise AppError("Missing project data.")
        string(project, key, limit=100000)
    string(project, "name", required=True, limit=160)
    choice(project, "status", PROJECT_STATUSES, "active")
    due_date(project, "target_date")
    stream_ids = set()
    task_ids = set()
    for key in ("workstreams", "tasks", "activity"):
        if not isinstance(project.get(key), list):
            raise AppError("Invalid project collection.")
    for stream in project["workstreams"]:
        if not isinstance(stream, dict) or not re.fullmatch(r"[a-f0-9]{16}", string(stream, "id")):
            raise AppError("Invalid workstream identity.")
        if stream["id"] in stream_ids:
            raise AppError("Duplicate workstream identity.")
        stream_ids.add(stream["id"])
        string(stream, "name", required=True, limit=100)
        choice(stream, "color", COLORS, "purple")
    for task in project["tasks"]:
        if not isinstance(task, dict) or not re.fullmatch(r"[a-f0-9]{16}", string(task, "id")):
            raise AppError("Invalid task identity.")
        if task["id"] in task_ids:
            raise AppError("Duplicate task identity.")
        task_ids.add(task["id"])
        for key in ("title", "description", "owner", "status", "priority", "due_date", "workstream_id", "blocker", "created_at", "updated_at"):
            if key not in task:
                raise AppError("Missing task data.")
            string(task, key, limit=50000)
        string(task, "title", required=True, limit=300)
        choice(task, "status", STATUSES, "backlog")
        choice(task, "priority", PRIORITIES, "medium")
        due_date(task)
        if task["workstream_id"] and task["workstream_id"] not in stream_ids:
            raise AppError("Task refers to an unknown workstream.")
    for event in project["activity"]:
        if not isinstance(event, dict):
            raise AppError("Invalid activity record.")
        string(event, "message", required=True)
        string(event, "at", required=True, limit=100)
        if "origin" in event and event["origin"] not in RECORDED_ORIGINS:
            raise AppError("Invalid activity origin.")
        if "revision" in event and (type(event["revision"]) is not int or event["revision"] < 1):
            raise AppError("Invalid activity revision.")
        if "via" in event:
            string(event, "via", limit=60)


class Store:
    def __init__(self, root):
        self.root = Path(root).expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.lock = threading.RLock()
        self.lock_file = (self.root / ".server.lock").open("a+b")
        try:
            lock_file(self.lock_file)
        except (BlockingIOError, PermissionError):
            self.lock_file.close()
            raise AppError("This workspace is already open in another server.", code="WORKSPACE_LOCKED")
        migrated = self.root / MIGRATED_MARKER
        if migrated.exists():
            self.lock_file.close()
            try:
                destination = read_json(migrated)["destination"]
            except (OSError, ValueError, KeyError, TypeError):
                destination = "another workspace"
            raise AppError(f"This workspace was migrated to {destination}, which now owns its project folders. Open that workspace, "
                           f"or stop using the destination before deleting {migrated} to abandon the migration.", 409)
        self.registry_path = self.root / "registry.json"
        if not self.registry_path.exists():
            write_json(self.registry_path, {"schema_version": 1, "clients": [], "projects": []})

    def close(self):
        self.lock_file.close()

    def registry(self):
        return read_json(self.registry_path)

    def save_registry(self, registry):
        write_json(self.registry_path, registry)

    def registration(self, project_id):
        return next((item for item in self.registry()["projects"] if item["id"] == project_id), None)

    def project_path(self, registration):
        folder = Path(registration["path"])
        storage = folder / ".task-manager"
        if not folder.is_dir() or storage.is_symlink() or (storage / "project.json").is_symlink():
            raise AppError("Project storage is unavailable or uses an unsupported symlink.", 503)
        return storage / "project.json"

    def project(self, project_id):
        registration = self.registration(project_id)
        if not registration:
            raise AppError("Project not found.", 404)
        try:
            project = read_json(self.project_path(registration))
            validate_project(project)
            if project["id"] != project_id:
                raise ValueError("Project identity or schema does not match.")
            project["client_id"] = registration["client_id"]
            return project
        except (OSError, ValueError, KeyError, TypeError, AppError):
            raise AppError("Cannot read this project's .task-manager/project.json. Restore the folder or repair the file; its data has not been overwritten.", 503)

    def save_project(self, project):
        registration = self.registration(project["id"])
        if not registration:
            raise AppError("Project not found.", 404)
        project["revision"] += 1
        project["updated_at"] = now()
        from .notes import source_manifest
        project["planning_sources"] = source_manifest(project)
        write_json(self.project_path(registration), project)

    def check_revision(self, project, data):
        requested = data.get("revision")
        if type(requested) is int and requested == project["revision"]:
            return
        raise AppError("This project changed in another window. Refresh and try again; your edits have not been saved.", 409)

    def activity(self, project, message, actor=None):
        actor = actor or USER
        if not isinstance(actor, dict):
            raise AppError("Invalid actor.")
        origin = actor.get("origin", "user")
        if origin not in ORIGINS:
            raise AppError("Invalid activity origin.")
        via = actor.get("via")
        if via is not None and (not isinstance(via, str) or not VIA_LABEL.fullmatch(via)):
            raise AppError("Invalid activity label.")
        entry = {"id": identifier(), "message": message, "at": now(),
                 "origin": origin, "revision": project["revision"] + 1}
        if via:
            entry["via"] = via
        project["activity"].insert(0, entry)

    def state(self):
        with self.lock:
            registry = self.registry()
            projects, errors = [], []
            for registration in registry["projects"]:
                try:
                    project = self.project(registration["id"])
                    project["folder"] = registration["path"]
                    projects.append(project)
                except AppError as error:
                    errors.append({**registration, "error": str(error)})
            return {"clients": registry["clients"], "projects": projects, "storage_errors": errors,
                    "workspace": str(self.root), "schema_version": 1}

    def create_client(self, data):
        with self.lock:
            registry = self.registry()
            client = {"id": identifier(), "name": string(data, "name", required=True, limit=120),
                      "description": string(data, "description"),
                      "color": choice(data, "color", COLORS, "purple"), "created_at": now()}
            registry["clients"].append(client)
            self.save_registry(registry)
            return client

    def update_client(self, client_id, data):
        with self.lock:
            registry = self.registry()
            client = next((item for item in registry["clients"] if item["id"] == client_id), None)
            if not client:
                raise AppError("Client not found.", 404)
            client.update(name=string(data, "name", client["name"], True, 120),
                          description=string(data, "description", client["description"]),
                          color=choice(data, "color", COLORS, client["color"]))
            self.save_registry(registry)
            return client

    def create_project(self, data, actor=None):
        with self.lock:
            registry = self.registry()
            client_id = string(data, "client_id", required=True)
            if not any(client["id"] == client_id for client in registry["clients"]):
                raise AppError("Choose an existing client.")
            name = string(data, "name", required=True, limit=160)
            description = string(data, "description")
            target_date = due_date(data, "target_date")
            project_id = identifier()
            custom_path = string(data, "folder", limit=4096)
            if custom_path:
                folder = Path(custom_path).expanduser()
                if not folder.is_absolute() or not folder.is_dir():
                    raise AppError("Choose an existing, absolute project folder path.")
                folder = folder.resolve()
            else:
                slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:60] or "project"
                folder = self.root / "clients" / client_id / "projects" / f"{slug}-{project_id[:6]}"
            if any(path_identity(item["path"]) == path_identity(folder) for item in registry["projects"]):
                raise AppError("That folder is already registered.", 409)
            storage = folder / ".task-manager"
            path = storage / "project.json"
            if storage.is_symlink() or path.is_symlink():
                raise AppError("Project storage must not be a symlink.")
            if path.exists():
                try:
                    project = read_json(path)
                    validate_project(project)
                except (KeyError, ValueError, TypeError, AppError):
                    raise AppError("Existing project data is invalid or uses an unsupported version. It has not been modified.")
                if any(item["id"] == project["id"] for item in registry["projects"]):
                    raise AppError("This project identity is already registered in another folder.", 409)
            else:
                project = {"schema_version": 1, "id": project_id, "client_id": client_id, "name": name,
                           "description": description, "status": "active", "target_date": target_date,
                           "revision": 1, "created_at": now(), "updated_at": now(), "notes": "",
                           "workstreams": [{"id": identifier(), "name": title, "color": color}
                                           for title, color in [("Discovery", "purple"), ("Architecture", "blue"), ("Delivery", "green")]],
                           "tasks": [], "activity": []}
                self.activity(project, "Project created", actor)
                project["activity"][0]["revision"] = 1
                from .notes import source_manifest
                project["planning_sources"] = source_manifest(project)
                write_json(path, project)
            registry["projects"].append({"id": project["id"], "client_id": client_id, "path": str(folder)})
            self.save_registry(registry)
            return project

    def update_project(self, project_id, data, actor=None):
        with self.lock:
            project = self.project(project_id)
            self.check_revision(project, data)
            project.update(name=string(data, "name", project["name"], True, 160),
                           description=string(data, "description", project["description"]),
                           status=choice(data, "status", PROJECT_STATUSES, project["status"]),
                           target_date=due_date(data, "target_date", project["target_date"]),
                           notes=string(data, "notes", project["notes"], limit=100000))
            self.activity(project, "Project notes updated" if "notes" in data else "Project details updated", actor)
            self.save_project(project)
            return project

    def relocate_project(self, project_id, data, actor=None):
        """Rebind planning data to a folder without moving or deleting source files."""
        with self.lock:
            registry = self.registry()
            registration = next((r for r in registry["projects"] if r["id"] == project_id), None)
            if registration is None:
                raise AppError("Project not found.", 404)
            folder = Path(string(data, "folder", required=True, limit=4096)).expanduser()
            if not folder.is_absolute() or not folder.is_dir():
                raise AppError("Choose an existing absolute project folder.")
            folder = folder.resolve()
            if any(r["id"] != project_id and path_identity(r["path"]) == path_identity(folder) for r in registry["projects"]):
                raise AppError("That folder is already registered.", 409)
            storage = folder / ".task-manager"
            path = storage / "project.json"
            if storage.is_symlink() or path.is_symlink():
                raise AppError("Project storage must not be a symlink.")
            try:
                original = self.project(project_id)
            except AppError:
                original = None
            if path.exists():
                project = read_json(path)
                validate_project(project)
                if project["id"] != project_id:
                    raise AppError("That folder belongs to another project.", 409)
                if original and project != original:
                    # client_id is registry-owned and can differ in a copied file.
                    project["client_id"] = original["client_id"]
                    if project != original:
                        raise AppError("Both folders contain different project revisions. Keep the desired copy before relocating.", 409)
            elif original:
                project = original
            else:
                raise AppError("The old folder is unavailable. Choose a folder containing this project's .task-manager/project.json.")
            if not path.exists():
                write_json(path, project)
            registration["path"] = str(folder)
            self.save_registry(registry)
            return {"id": project_id, "folder": str(folder), "source_files_moved": False}

    def append_notes(self, project_id, data, actor=None):
        with self.lock:
            project = self.project(project_id)
            text = string(data, "text", required=True, limit=100000)
            combined = f"{project['notes']}\n\n{text}" if project["notes"] else text
            if len(combined) > 100000:
                raise AppError("Notes would exceed 100000 characters.")
            project["notes"] = combined
            self.activity(project, "Notes appended", actor)
            self.save_project(project)
            return project

    def create_workstream(self, project_id, data, actor=None):
        with self.lock:
            project = self.project(project_id)
            self.check_revision(project, data)
            stream = {"id": identifier(), "name": string(data, "name", required=True, limit=100),
                      "color": choice(data, "color", COLORS, "purple")}
            if any(item["name"].casefold() == stream["name"].casefold() for item in project["workstreams"]):
                raise AppError("A workstream with this name already exists.")
            project["workstreams"].append(stream)
            self.activity(project, f"Added workstream: {stream['name']}", actor)
            self.save_project(project)
            return stream

    def task_fields(self, project, data, existing=None):
        existing = existing or {}
        task = {"title": string(data, "title", existing.get("title", ""), True, 300),
                "description": string(data, "description", existing.get("description", ""), limit=50000),
                "owner": string(data, "owner", existing.get("owner", ""), limit=120),
                "status": choice(data, "status", STATUSES, existing.get("status", "backlog")),
                "priority": choice(data, "priority", PRIORITIES, existing.get("priority", "medium")),
                "due_date": due_date(data, default=existing.get("due_date", "")),
                "workstream_id": string(data, "workstream_id", existing.get("workstream_id", "")),
                "blocker": string(data, "blocker", existing.get("blocker", ""))}
        if task["workstream_id"] and not any(item["id"] == task["workstream_id"] for item in project["workstreams"]):
            raise AppError("Choose a workstream in this project.")
        return task

    def create_task(self, project_id, data, actor=None):
        with self.lock:
            project = self.project(project_id)
            self.check_revision(project, data)
            task = {**self.task_fields(project, data), "id": identifier(), "created_at": now(), "updated_at": now()}
            project["tasks"].append(task)
            self.activity(project, f"Added task: {task['title']}", actor)
            self.save_project(project)
            return task

    def update_task(self, project_id, task_id, data, delete=False, actor=None):
        with self.lock:
            project = self.project(project_id)
            task = next((item for item in project["tasks"] if item["id"] == task_id), None)
            if not task:
                self.check_revision(project, data)
                raise AppError("Task not found.", 404)
            if delete:
                self.check_revision(project, data)
                project["tasks"].remove(task)
                self.activity(project, f"Deleted task: {task['title']}", actor)
            else:
                fields = self.task_fields(project, data, task)
                self.check_revision(project, data)
                old_status = task["status"]
                task.update(fields, updated_at=now())
                message = f"Moved to {task['status'].replace('_', ' ')}: {task['title']}" if old_status != task["status"] else f"Updated task: {task['title']}"
                self.activity(project, message, actor)
            self.save_project(project)
            return task
