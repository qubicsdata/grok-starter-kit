"""Portable planning snapshots. Restoration only publishes into a new workspace."""
import copy
import hashlib
import hmac
import json
import os
import re
import shutil
import tempfile
from pathlib import Path

from .core import AppError, COLORS, FROZEN, LEGACY_TASK_KEYS, now, string, validate_project, write_json
from .migration import publish_directory, sync_directory

MAX_BYTES = 50 * 1024 * 1024


def checksum(payload):
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()


def snapshot(store):
    with store.lock:
        registry = store.registry()
        # Fail rather than produce a backup that silently omits an unavailable project.
        projects = [store.project(r["id"]) for r in registry["projects"]]
        payload = {"kind": "folio-planning-backup", "schema_version": 1, "created_at": now(), "clients": registry["clients"], "projects": projects}
        document = {"payload": payload, "sha256": checksum(payload)}
        if len(json.dumps(document, ensure_ascii=False, indent=2).encode()) + 1 > MAX_BYTES:
            raise AppError("Planning data exceeds the 50 MiB portable backup limit. Export projects individually.", 413)
        return document


def validate_snapshot(document):
    if not isinstance(document, dict) or not isinstance(document.get("payload"), dict):
        raise AppError("Choose a Folio workspace backup.")
    payload = document["payload"]
    if not isinstance(document.get("sha256"), str) or not re.fullmatch(r"[a-f0-9]{64}", document["sha256"]) or not hmac.compare_digest(document["sha256"], checksum(payload)):
        raise AppError("Backup checksum does not match. The file may be incomplete or changed.")
    if payload.get("kind") != "folio-planning-backup" or payload.get("schema_version") != 1:
        raise AppError("Unsupported backup format.")
    clients, projects = payload.get("clients"), payload.get("projects")
    if not isinstance(clients, list) or not isinstance(projects, list) or len(clients) > 10000 or len(projects) > 10000:
        raise AppError("Invalid backup collections.")
    ids, project_ids = set(), set()
    for client in clients:
        if not isinstance(client, dict) or not re.fullmatch(r"[a-f0-9]{16}", str(client.get("id", ""))) or client["id"] in ids:
            raise AppError("Invalid or duplicate client identity.")
        string(client, "name", required=True, limit=120)
        string(client, "description")
        string(client, "created_at", required=True)
        if client.get("color") not in COLORS:
            raise AppError("Invalid client color.")
        ids.add(client["id"])
    for project in projects:
        validate_project(project)
        if project["id"] in project_ids or project.get("client_id") not in ids:
            raise AppError("Duplicate project or missing client.")
        project_ids.add(project["id"])
    return payload


def restore(document, destination):
    payload = validate_snapshot(document)
    destination = Path(destination).expanduser().absolute()
    if destination.exists() or destination.is_symlink():
        raise AppError("Restore needs a new workspace folder. Existing data has not been changed.", 409)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination = destination.parent.resolve() / destination.name
    staged = Path(tempfile.mkdtemp(prefix=".folio-restore-", dir=destination.parent))
    detached = 0
    try:
        registry = {"schema_version": 1, "clients": payload["clients"], "projects": []}
        for original in payload["projects"]:
            project = copy.deepcopy(original)
            # Links of the frozen integration (folio.core.FROZEN) are detached, never carried over.
            linked = project.pop(FROZEN, None)
            if linked:
                detached += 1
            for task in project["tasks"]:
                was_linked = bool(task.get("sb"))
                for key in LEGACY_TASK_KEYS:
                    task.pop(key, None)
                if was_linked and task["status"] == "in_progress":
                    task["status"] = "blocked"
                    task["blocker"] = "Restored planning snapshot. Agent work was linked to this task; check it before continuing."
            project.pop("folder", None)
            project["revision"] += 1
            project["updated_at"] = now()
            project["activity"].insert(0, {"id": os.urandom(8).hex(), "at": now(), "message": "Restored planning backup.", "origin": "cli", "revision": project["revision"]})
            from .notes import source_manifest
            project["planning_sources"] = source_manifest(project)
            validate_project(project)
            relative = Path("projects") / project["id"]
            write_json(staged / relative / ".task-manager" / "project.json", project)
            registry["projects"].append({"id": project["id"], "client_id": project["client_id"], "path": str(destination / relative)})
        write_json(staged / "registry.json", registry)
        # Flush the directory tree before publishing the new registry and project set together.
        for directory, _, _ in os.walk(staged, topdown=False):
            sync_directory(directory)
        publish_directory(staged, destination)
        sync_directory(destination.parent)
        return {"workspace": str(destination), "clients": len(registry["clients"]), "projects": len(registry["projects"]), "detached_links": detached,
                "next_step": "Start folio-server --data-dir with this workspace. Source repositories and native agent histories are separate."}
    finally:
        if staged.exists():
            shutil.rmtree(staged)


def read_backup(path):
    with Path(path).expanduser().open("rb") as stream:
        data = stream.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise AppError("Backup exceeds the 50 MiB import limit.")
    try:
        return json.loads(data)
    except (ValueError, UnicodeDecodeError) as error:
        raise AppError("Backup is not valid UTF-8 JSON.") from error


def write_backup(path, document):
    """Publish a fully flushed snapshot without overwriting an existing backup."""
    path = Path(path).expanduser().absolute()
    descriptor, temporary = tempfile.mkstemp(prefix=".folio-backup-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(document, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, path)
        sync_directory(path.parent)
    finally:
        os.unlink(temporary)
    return str(path)
