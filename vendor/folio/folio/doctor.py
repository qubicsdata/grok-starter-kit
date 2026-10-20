"""Read-only first-run and recovery diagnostics."""
from pathlib import Path
import platform

from . import __version__
from .core import read_json, validate_project
from .transport import find_server


def diagnose(workspace):
    root = Path(workspace).expanduser().resolve()
    checks = []
    path = root / "registry.json"
    if not path.exists():
        checks.append({"name": "workspace", "status": "info", "message": "New workspace. Start folio-server to create your first client and project."})
    else:
        try:
            registry = read_json(path)
            if registry.get("schema_version") != 1 or not isinstance(registry.get("clients"), list) or not isinstance(registry.get("projects"), list):
                raise ValueError("Unsupported workspace registry")
            checks.append({"name": "workspace", "status": "ok", "message": f"{len(registry['clients'])} clients, {len(registry['projects'])} projects."})
            for registration in registry["projects"]:
                try:
                    storage = Path(registration["path"]) / ".task-manager"
                    project_path = storage / "project.json"
                    if storage.is_symlink() or project_path.is_symlink():
                        raise ValueError("Unsupported storage symlink")
                    project = read_json(project_path)
                    validate_project(project)
                    if project["id"] != registration["id"]:
                        raise ValueError("Project identity mismatch")
                    checks.append({"name": registration["id"], "status": "ok", "message": project["name"]})
                except Exception:
                    checks.append({"name": str(registration.get("id", "project")), "status": "error", "message": "Project folder unavailable or invalid. Restore it or use folio projects relocate with its new folder."})
        except Exception:
            checks.append({"name": "workspace", "status": "error", "message": "Registry cannot be read. Restore a backup into a new workspace; the original was not modified."})
    if (root / ".migrated.json").exists():
        checks.append({"name": "migration", "status": "error", "message": "This workspace was migrated. Open the destination recorded in .migrated.json."})
    server = find_server(str(root))
    checks.append({"name": "server", "status": "ok" if server else "info", "message": f"Running at {server}" if server else "No server is running. The CLI works offline; folio-server opens the web workspace."})
    return {"ok": not any(c["status"] == "error" for c in checks), "version": __version__, "platform": platform.system(), "workspace": str(root), "server": server, "checks": checks}
