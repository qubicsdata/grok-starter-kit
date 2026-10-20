"""The folio command-line interface: JSON-first access to a Folio workspace."""

import argparse
import json
import os
import sys
import traceback
from datetime import date

from .api import build_app
from .core import COLORS, DEFAULT_WORKSPACE, PROJECT_STATUSES, VIA_LABEL, resolve_workspace
from .resolve import ResolveError, resolve
from .transport import TransportError, connect

EXIT_CODES = {"USAGE": 1, "CONFIRM_REQUIRED": 1, "NOT_FOUND": 2, "AMBIGUOUS_REFERENCE": 2, "CONFLICT": 3, "VALIDATION": 4,
              "STORAGE": 5, "FORBIDDEN": 5,
              "HUMAN_CONFIRMATION_CANCELLED": 7, "HUMAN_CONFIRMATION_UNAVAILABLE": 7, "INTERNAL_ERROR": 5,
              "CONFIRMATION_IN_PROGRESS": 3}
STATUS_CODES = {400: "VALIDATION", 403: "FORBIDDEN", 404: "NOT_FOUND", 409: "CONFLICT", 413: "VALIDATION", 415: "VALIDATION"}
REGISTRARS = []


class Raw(str):
    """Data written verbatim instead of inside the JSON envelope."""


class CliError(Exception):
    def __init__(self, code, message, candidates=None, exit_code=None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.candidates = candidates
        self.exit_code = exit_code if exit_code is not None else EXIT_CODES.get(code, 5)


def from_transport(error):
    if error.code in EXIT_CODES:
        return CliError(error.code, error.message)
    fallback = STATUS_CODES.get(error.status, "STORAGE")
    return CliError(error.code or fallback, error.message, exit_code=EXIT_CODES[fallback])


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise CliError("USAGE", message)


def common_parent():
    common = Parser(add_help=False)
    common.add_argument("--data-dir", default=argparse.SUPPRESS, help="Workspace directory")
    common.add_argument("--format", choices=("json", "table"), default=argparse.SUPPRESS)
    return common


COMMON = common_parent()


def leaf(sub, name, handler, help_text):
    parser = sub.add_parser(name, help=help_text, description=help_text, parents=[COMMON])
    parser.set_defaults(handler=handler)
    return parser


def group(sub, name, help_text):
    parser = sub.add_parser(name, help=help_text, description=help_text)
    parser.set_defaults(handler=None)
    actions = parser.add_subparsers(dest=f"{name}_action", parser_class=Parser)
    parser.folio_actions = actions
    return actions


def detect_via(env):
    override = env.get("FOLIO_VIA", "").strip().lower()[:60]
    if override and VIA_LABEL.fullmatch(override):
        return override
    if env.get("CLAUDECODE"):
        return "cli:claude-code"
    if any(key.startswith("CODEX_") for key in env):
        return "cli:codex"
    if any(key.startswith("COPILOT_") for key in env):
        return "cli:copilot"
    return "cli"


def pick(items, ref, kind, label="name"):
    try:
        return resolve(items, ref, kind, label)
    except ResolveError as error:
        raise CliError(error.code, error.message, error.candidates)


class Context:
    def __init__(self, transport):
        self.transport = transport
        self._state = None

    def call(self, method, path, data=None, timeout=None):
        try:
            if timeout is None:
                result = self.transport.request(method, path, data)
            else:
                result = self.transport.request(method, path, data, timeout=timeout)
        except TransportError as error:
            raise from_transport(error)
        if method != "GET":
            self._state = None
        return result

    def state(self, fresh=False):
        if fresh or self._state is None:
            self._state = self.call("GET", "/api/state")
        return self._state

    def client(self, ref):
        return pick(self.state()["clients"], ref, "client")

    def project(self, ref, fresh=False):
        return pick(self.state(fresh)["projects"], ref, "project")

    def project_by_id(self, project_id, fresh=True):
        for project in self.state(fresh)["projects"]:
            if project["id"] == project_id:
                return project
        raise CliError("NOT_FOUND", "Project not found.")

    def with_revision(self, project_id, send):
        for attempt in (1, 2):
            revision = self.project_by_id(project_id, fresh=True)["revision"]
            try:
                return send(revision)
            except CliError as error:
                if error.code != "CONFLICT" or attempt == 2:
                    raise


def summarize(state, include_archived, today):
    clients = {client["id"]: client for client in state["clients"]}
    rows, attention_items = {}, []
    totals = {"projects": 0, "tasks": 0, "done": 0, "open": 0, "blocked": 0, "overdue": 0, "attention": 0}
    for project in state["projects"]:
        if project["status"] == "archived" and not include_archived:
            continue
        client = clients.get(project["client_id"], {"name": "Unknown client"})
        row = rows.setdefault(project["client_id"], {"client": client["name"], "projects": 0, "tasks": 0, "done": 0,
                                                     "open": 0, "blocked": 0, "overdue": 0, "attention": 0})
        row["projects"] += 1
        totals["projects"] += 1
        for task in project["tasks"]:
            done = task["status"] == "done"
            blocked = not done and task["status"] == "blocked"
            overdue = not done and bool(task["due_date"]) and task["due_date"] < today
            for key, value in (("tasks", True), ("done", done), ("open", not done), ("blocked", blocked), ("overdue", overdue), ("attention", blocked or overdue)):
                if value:
                    row[key] += 1
                    totals[key] += 1
            if blocked or overdue:
                attention_items.append({"task_id": task["id"], "title": task["title"], "project": project["name"],
                                        "client": client["name"], "reason": "blocked" if blocked else "overdue",
                                        "due_date": task["due_date"], "blocker": task["blocker"]})
    return {"totals": totals, "clients": list(rows.values()), "attention_items": attention_items,
            "storage_errors": len(state.get("storage_errors", []))}


def emit(stream, fmt, payload):
    if payload.get("ok") and isinstance(payload.get("data"), Raw):
        stream.write(payload["data"] if payload["data"].endswith("\n") else payload["data"] + "\n")
    elif fmt == "table" and payload.get("ok"):
        stream.write(render_table(payload["data"]) + "\n")
    else:
        stream.write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


def render_table(data):
    if isinstance(data, list):
        if not data:
            return "(none)"
        columns = [key for key, value in data[0].items() if not isinstance(value, (list, dict))]
        rows = [[str(item.get(column, "")) for column in columns] for item in data]
        widths = [max([len(column)] + [len(row[index]) for row in rows]) for index, column in enumerate(columns)]
        lines = ["  ".join(column.ljust(widths[index]) for index, column in enumerate(columns))]
        lines += ["  ".join(value.ljust(widths[index]) for index, value in enumerate(row)) for row in rows]
        return "\n".join(lines)
    if isinstance(data, dict):
        return "\n".join(f"{key}: {json.dumps(value, ensure_ascii=False) if isinstance(value, (list, dict)) else value}"
                         for key, value in data.items())
    return str(data)


def only(args, mapping):
    return {key: getattr(args, attribute) for key, attribute in mapping.items() if getattr(args, attribute, None) is not None}


# --- status, clients, projects, workstreams -------------------------------------------------

def cmd_status(ctx, args):
    from . import __version__
    return {**summarize(ctx.state(), args.archived, date.today().isoformat()), "version": __version__}


def cmd_clients_list(ctx, args):
    state = ctx.state()
    return [{"id": c["id"], "name": c["name"], "description": c["description"], "color": c["color"],
             "projects": sum(1 for p in state["projects"] if p["client_id"] == c["id"])} for c in state["clients"]]


def cmd_clients_add(ctx, args):
    return ctx.call("POST", "/api/clients", only(args, {"name": "name", "description": "description", "color": "color"}))


def cmd_clients_update(ctx, args):
    client = ctx.client(args.client)
    return ctx.call("PATCH", f"/api/clients/{client['id']}", only(args, {"name": "name", "description": "description", "color": "color"}))


def project_row(state, project):
    clients = {client["id"]: client["name"] for client in state["clients"]}
    total = len(project["tasks"])
    done = sum(1 for task in project["tasks"] if task["status"] == "done")
    return {"id": project["id"], "name": project["name"], "client": clients.get(project["client_id"], ""),
            "status": project["status"], "tasks": total, "done": done,
            "progress": round(done * 100 / total) if total else 0, "target_date": project["target_date"],
            "folder": project.get("folder", "")}


def cmd_projects_list(ctx, args):
    state = ctx.state()
    client_id = ctx.client(args.client)["id"] if args.client else None
    return [project_row(state, project) for project in state["projects"]
            if (args.archived or project["status"] != "archived") and (client_id is None or project["client_id"] == client_id)]


def scoped_project(ctx, ref, client_ref=None):
    if not client_ref:
        return ctx.project(ref)
    client_id = ctx.client(client_ref)["id"]
    return pick([p for p in ctx.state()["projects"] if p["client_id"] == client_id], ref, "project")


def cmd_projects_show(ctx, args):
    project = scoped_project(ctx, args.project, args.client)
    return {**project, "activity": project["activity"][:20]}


def cmd_projects_add(ctx, args):
    data = only(args, {"name": "name", "description": "description", "target_date": "target_date", "folder": "folder"})
    data["client_id"] = ctx.client(args.client)["id"]
    return ctx.call("POST", "/api/projects", data)


def cmd_projects_update(ctx, args):
    if args.status == "archived" and not args.yes:
        raise CliError("USAGE", "Archiving a project requires --yes.")
    project = scoped_project(ctx, args.project, args.client)
    data = only(args, {"name": "name", "description": "description", "status": "status", "target_date": "target_date"})
    return ctx.with_revision(project["id"], lambda revision: ctx.call("PATCH", f"/api/projects/{project['id']}", {**data, "revision": revision}))


def cmd_brief(ctx, args):
    project = ctx.project(args.project)
    return ctx.call("POST", f"/api/projects/{project['id']}/brief", {"query": args.query, "max_chars": args.max_chars})


def cmd_source(ctx, args):
    project = ctx.project(args.project)
    return ctx.call("POST", f"/api/projects/{project['id']}/source", {"source_id": args.source, "offset": args.offset, "max_chars": args.max_chars, **({"hash": args.hash} if args.hash else {})})


def cmd_relocate(ctx, args):
    state = ctx.state()
    project = pick(state["projects"] + state.get("storage_errors", []), args.project, "project")
    return ctx.call("POST", f"/api/projects/{project['id']}/relocate", {"folder": args.folder})


def cmd_init(ctx, args):
    from pathlib import Path
    from .paths import path_identity
    folder = Path(args.folder).expanduser().resolve()
    if not folder.is_dir():
        raise CliError("VALIDATION", "Choose an existing project folder.")
    state = ctx.state()
    existing = next((p for p in state["projects"] if path_identity(p["folder"]) == path_identity(folder)), None)
    if existing:
        return {"project": existing, "created": False}
    clients = [c for c in state["clients"] if c["name"].casefold() == args.client.casefold()]
    if len(clients) > 1:
        raise CliError("AMBIGUOUS_REFERENCE", "Multiple clients have this name. Use projects add with an exact client ID.", clients)
    client = clients[0] if clients else ctx.call("POST", "/api/clients", {"name": args.client})
    project = ctx.call("POST", "/api/projects", {"client_id": client["id"], "name": args.name or folder.name, "folder": str(folder)})
    return {"project": project, "created": True, "next_step": "Run folio-server with the same workspace to open the web app."}


def cmd_restore(ctx, args):
    from .backup import read_backup, restore
    from .core import AppError
    try:
        return restore(read_backup(args.source), args.destination)
    except AppError as error:
        raise CliError("CONFLICT" if error.status == 409 else "VALIDATION", str(error))
    except (OSError, ValueError) as error:
        raise CliError("STORAGE", str(error))


cmd_restore.no_workspace = True


def cmd_doctor(ctx, args):
    from .doctor import diagnose
    return diagnose(args.resolved_workspace)


cmd_doctor.no_workspace = True


def cmd_ui(ctx, args):
    from .transport import find_server
    from .web import main as serve
    import webbrowser
    url = find_server(args.resolved_workspace)
    if url:
        if not args.no_open:
            from .local_auth import browser_url
            webbrowser.open(browser_url(args.resolved_workspace, url))
        return {"url": url, "already_running": True, "next_step": "Use folio ui to open an authenticated browser session."}
    serve(["--data-dir", str(args.resolved_workspace), "--port", str(args.port)] + ([] if args.no_open else ["--open"]))
    return {"stopped": True}


cmd_ui.no_workspace = True


def cmd_workstreams_add(ctx, args):
    project = ctx.project(args.project)
    data = {"name": args.name, **only(args, {"color": "color"})}
    return ctx.with_revision(project["id"], lambda revision: ctx.call("POST", f"/api/projects/{project['id']}/workstreams", {**data, "revision": revision}))


def register_core(sub):
    ui = leaf(sub, "ui", cmd_ui, "Open the workspace in your browser, reusing its running server")
    ui.add_argument("--port", type=int, default=8765)
    ui.add_argument("--no-open", action="store_true")
    init = leaf(sub, "init", cmd_init, "Register a folder and create its client if needed; safe to repeat")
    init.add_argument("folder", nargs="?", default=".")
    init.add_argument("--client", default="Personal")
    init.add_argument("--name")
    leaf(sub, "doctor", cmd_doctor, "Check setup and project storage without changing data")
    restore = leaf(sub, "restore", cmd_restore, "Restore a 1.1.x planning backup into a new workspace")
    restore.add_argument("--from", dest="source", required=True)
    restore.add_argument("--to", dest="destination", required=True)
    brief = leaf(sub, "brief", cmd_brief, "Retrieve bounded planning context for a project")
    brief.add_argument("project")
    brief.add_argument("--query", default="")
    brief.add_argument("--max-chars", type=int, default=12000)
    source = leaf(sub, "source", cmd_source, "Read an authoritative planning source in bounded pages")
    source.add_argument("source", help="Source reference returned by brief or notes list")
    source.add_argument("--project", required=True)
    source.add_argument("--hash", help="Reject changed source text")
    source.add_argument("--offset", type=int, default=0)
    source.add_argument("--max-chars", type=int, default=12000)
    status = leaf(sub, "status", cmd_status, "Portfolio summary: totals, per-client rollups, and attention items")
    status.add_argument("--archived", action="store_true", help="Include archived projects")

    clients = group(sub, "clients", "List, add, and update clients")
    leaf(clients, "list", cmd_clients_list, "List clients")
    add = leaf(clients, "add", cmd_clients_add, "Add a client")
    add.add_argument("--name", required=True)
    add.add_argument("--description")
    add.add_argument("--color", choices=COLORS)
    update = leaf(clients, "update", cmd_clients_update, "Update a client")
    update.add_argument("client")
    update.add_argument("--name")
    update.add_argument("--description")
    update.add_argument("--color", choices=COLORS)

    projects = group(sub, "projects", "List, show, add, and update projects")
    relocate = leaf(projects, "relocate", cmd_relocate, "Use a new project folder; keep source files intact")
    relocate.add_argument("project")
    relocate.add_argument("--folder", required=True)
    listing = leaf(projects, "list", cmd_projects_list, "List projects")
    listing.add_argument("--client")
    listing.add_argument("--archived", action="store_true")
    show = leaf(projects, "show", cmd_projects_show, "Show a project with tasks, workstreams, notes, and recent activity")
    show.add_argument("project")
    show.add_argument("--client")
    add = leaf(projects, "add", cmd_projects_add, "Add a project (or reopen a Folio folder)")
    add.add_argument("--client", required=True)
    add.add_argument("--name", required=True)
    add.add_argument("--description")
    add.add_argument("--target-date", dest="target_date")
    add.add_argument("--folder", help="Existing absolute folder; omit to create one in the workspace")
    update = leaf(projects, "update", cmd_projects_update, "Update project details or status")
    update.add_argument("project")
    update.add_argument("--client")
    update.add_argument("--name")
    update.add_argument("--description")
    update.add_argument("--status", choices=PROJECT_STATUSES)
    update.add_argument("--target-date", dest="target_date")
    update.add_argument("--yes", action="store_true", help="Confirm archiving")

    workstreams = group(sub, "workstreams", "Add workstreams")
    add = leaf(workstreams, "add", cmd_workstreams_add, "Add a workstream to a project")
    add.add_argument("project")
    add.add_argument("name")
    add.add_argument("--color", choices=COLORS)


REGISTRARS.append(register_core)


# --- notes ---------------------------------------------------------------------------------
# Task CRUD left the CLI in WP-6: agents and people edit tasks through the Backlog CLI (D-13).

def cmd_notes_show(ctx, args):
    project = ctx.project(args.project)
    return {"project_id": project["id"], "project": project["name"], "notes": project["notes"], "revision": project["revision"]}


def cmd_notes_append(ctx, args):
    if args.text == "-" and (sys.stdin is None or sys.stdin.isatty()):
        raise CliError("USAGE", "Pipe the note text on stdin when using --text -.")
    project = ctx.project(args.project)
    text = sys.stdin.read() if args.text == "-" else args.text
    result = ctx.call("POST", f"/api/projects/{project['id']}/notes/append", {"text": text})
    return {"project_id": project["id"], "project": project["name"], "notes_length": len(result["notes"])}


def cmd_notes_list(ctx, args):
    project = ctx.project(args.project)
    return ctx.call("GET", f"/api/projects/{project['id']}/notes/sections")


def cmd_notes_edit(ctx, args):
    if args.note_operation == "delete" and not args.yes:
        raise CliError("USAGE", "Deleting a note section requires --yes.")
    project = ctx.project(args.project)
    data = only(args, {"title": "title", "text": "text", "kind": "kind", "hash": "hash"})
    if data.get("text") == "-":
        if sys.stdin is None or sys.stdin.isatty():
            raise CliError("USAGE", "Pipe the note text on stdin when using --text -.")
        data["text"] = sys.stdin.read()
    endpoint = f"/api/projects/{project['id']}/notes/sections"
    if args.note_operation != "add":
        candidates = ctx.call("GET", endpoint)["sections"]
        section = next((s for s in candidates if s["source"] == args.section), None) or pick(candidates, args.section, "note section", "title")
        endpoint += f"/{section['id']}"
        data.setdefault("hash", section["hash"])
    method = {"add": "POST", "update": "PATCH", "delete": "DELETE"}[args.note_operation]
    return ctx.with_revision(project["id"], lambda revision: ctx.call(method, endpoint, {**data, "revision": revision}))


def register_notes(sub):
    notes = group(sub, "notes", "Read, remember, correct, or forget project note sections")
    leaf(notes, "show", cmd_notes_show, "Show project notes").add_argument("project")
    append = leaf(notes, "append", cmd_notes_append, "Append text to project notes (never overwrites)")
    append.add_argument("project")
    append.add_argument("--text", required=True, help="Text to append, or - to read stdin")
    leaf(notes, "list", cmd_notes_list, "List addressable note sections and decisions").add_argument("project")
    for name in ("add", "update", "delete"):
        parser = leaf(notes, name, cmd_notes_edit, {"add": "Remember a note or decision", "update": "Correct one note section", "delete": "Forget one note section"}[name])
        parser.set_defaults(note_operation=name)
        parser.add_argument("project")
        if name != "add":
            parser.add_argument("section", help="Section title, identifier, or source reference")
            parser.add_argument("--hash", help="Require this exact source version")
        if name == "delete":
            parser.add_argument("--yes", action="store_true")
        else:
            parser.add_argument("--title", required=name == "add")
            parser.add_argument("--text", required=name == "add", help="Text, or - to read stdin")
            parser.add_argument("--kind", choices=("note", "decision"))


REGISTRARS.append(register_notes)


def direct_app(store):
    # With no server, the CLI works on the store in-process, with the plugins enabled in local config.
    return build_app(store)


def cmd_server_stop(context, args):
    from .transport import HttpTransport, find_server
    url = find_server(args.resolved_workspace)
    if url is None:
        raise CliError("NOT_FOUND", "No Folio server is running for this workspace.")
    try:
        from .local_auth import owner_credential
        return HttpTransport(url, {"origin": "cli"}, token=owner_credential(args.resolved_workspace, url)).request("POST", "/api/shutdown", {})
    except TransportError as error:
        raise from_transport(error)


cmd_server_stop.no_workspace = True


def cmd_migrate_workspace(context, args):
    from .migration import migrate_workspace
    try:
        return migrate_workspace(args.source, args.destination)
    except (OSError, ValueError) as error:
        raise CliError("STORAGE", str(error))


cmd_migrate_workspace.no_workspace = True


def build_parser():
    parser = Parser(prog="folio", description="JSON-first command line for a Folio workspace. Output is JSON unless --format table.")
    parser.add_argument("--data-dir", help="Workspace directory (default: $FOLIO_WORKSPACE or the user data directory)")
    from . import __version__
    parser.add_argument("--version", action="version", version=f"folio {__version__}")
    parser.add_argument("--format", choices=("json", "table"), default="json")
    parser.set_defaults(handler=None)
    sub = parser.add_subparsers(dest="command", parser_class=Parser)
    leaf(sub, "server-stop", cmd_server_stop, "Gracefully stop the Folio server for this workspace")
    migrate = leaf(sub, "migrate-workspace", cmd_migrate_workspace, "Copy workspace metadata; preserve registered project folders")
    migrate.add_argument("--from", dest="source", required=True, help="Existing workspace directory (server must be stopped)")
    migrate.add_argument("--to", dest="destination", required=True, help="New workspace directory, which must not already exist")
    for register in REGISTRARS:
        register(sub)
    return parser


def main(argv=None, env=None, stdout=None):
    env = os.environ if env is None else env
    stdout = stdout or sys.stdout
    fmt = "json"
    transport = None
    try:
        args = build_parser().parse_args(argv)
        fmt = args.format
        args.resolved_workspace = resolve_workspace(args.data_dir, env)
        if args.handler is None:
            raise CliError("USAGE", "Choose a command. Run: folio --help")
        if getattr(args.handler, "no_workspace", False):
            data = args.handler(None, args)
        else:
            workspace = resolve_workspace(args.data_dir, env)
            try:
                transport = connect(workspace, {"origin": "cli", "via": detect_via(env)}, app_factory=direct_app)
            except TransportError as error:
                raise from_transport(error)
            data = args.handler(Context(transport), args)
        emit(stdout, fmt, {"ok": True, "data": data})
        return 0
    except CliError as error:
        if error.code == "CONFIRM_REQUIRED" and "--yes" not in error.message:
            error.message = f"{error.message} Re-run with --yes to confirm."
        payload = {"code": error.code, "message": error.message}
        if error.candidates:
            payload["candidates"] = error.candidates
        emit(stdout, "json", {"ok": False, "error": payload})
        return error.exit_code
    except SystemExit as exit_:
        return exit_.code if isinstance(exit_.code, int) else 0
    except Exception as error:
        if env.get("FOLIO_DEBUG") == "1":
            sys.stderr.write(traceback.format_exc())
        message = f"Unexpected error: {error.__class__.__name__}: {error}"
        emit(stdout, "json", {"ok": False, "error": {"code": "INTERNAL_ERROR", "message": message}})
        return EXIT_CODES["INTERNAL_ERROR"]
    finally:
        if transport is not None:
            transport.close()
