# Folio 0.3: setup, briefs and portable planning

Folio remains a standard-library Python application. No frontend build, database
service, cloud account or Switchboard instance is needed for planning.

```sh
folio ui
```

This opens your workspace in a browser, reuses its running server, or starts one
in the foreground. `--no-open` prints the URL without opening a browser. All commands
share the existing `--data-dir` / `FOLIO_WORKSPACE` / user data directory selection.
Keep the terminal running, or use the existing server launcher under your preferred
process manager. `folio server-stop` shuts down gracefully.

To register a repository from the command line:

```sh
folio init /path/to/repository --client "Client name" --name "Project name"
folio doctor
```

Initialization is safe to repeat. It reuses the folder registration and a uniquely
named client. The doctor checks the registry, every project document and the running
server without creating or repairing files. Missing folders offer a relocation path.

## A project brief

Open project **Details → Project brief**, or run:

```sh
folio brief "Project name" --query "routing" --max-chars 12000
```

The brief includes saved project context, notes, and relevant tasks. Blocked/overdue
work comes first, followed by priority and due date; a query ranks matching tasks.
It reports stable project/task references, revision, a SHA-256 of the planning
document, character count and truncation. Unsaved browser drafts are excluded.
The text is planning data for a person or agent, not a new source of authorization.
The same operation is available at `GET/POST /api/projects/ID/brief`.

## Backup and restore

The workspace backup download, `/api/backup` and `folio backup` were cut in WP-6.
Until the Backlog-backed storage lands, back up by copying the workspace directory
and each registered project's `.task-manager/` folder while the server is stopped.
`folio restore` still reads a 1.1.x backup file (a new owner-only file made by an
earlier version):

```sh
folio restore --from /path/to/folio-backup.json --to /path/to/new-workspace
folio ui --data-dir /path/to/new-workspace
```

Restore verifies the checksum, schemas, IDs and relationships before publishing a
new workspace. It never replaces an existing destination. Original data stays intact.
Client/project/task IDs, notes, workstreams and activity survive; restored projects
live under the new workspace's `projects/ID` folders. Old Switchboard links and
pending sends are detached. Previously agent-owned in-progress tasks become blocked
with an explanation so an old execution is not silently dispatched again.

This is a planning backup. Source repositories, Switchboard history, native harness
transcripts and credentials are separate. Back up source/project folders separately
when moving the complete development environment. The JSON checksum detects accidental
changes; it is not a digital signature. Portable backups are limited to 50 MiB.

## Change a project's folder

Use **Project details → Change project folder** and type the new absolute path (the
native folder picker was cut in WP-6), or `folio projects relocate PROJECT --folder /new/repository`. Folio copies planning
data into an empty planning folder, or registers an identical copy that already
exists there. It never moves or deletes repository source files. Different copies
are rejected instead of guessing which one is current. Disconnect Switchboard before
relocating a linked project, then reconnect at the new root.

If the old folder has disappeared, **Workspace storage → Locate project folder**
can register a moved folder containing that project's `.task-manager/project.json`.
From the CLI use its project ID. Restored projects can similarly be relocated from
their backup workspace to their actual repositories.

## Work with Switchboard

The existing manual/workstream/project sync scopes, offline outbox and review inbox
continue unchanged. Preferred dispatch harnesses now include Gemini alongside Claude,
Codex and Copilot. Switchboard 0.6 adds a repository context index and managed worker
security classes; see its `docs/context-and-security.md` and the existing
[paired setup guide](using-folio-and-switchboard.md).

## Durable planning context (0.4)

With Switchboard 0.7, dispatched tasks carry a versioned snapshot of project scope,
workstream, target date and saved notes. Planning changes propagate on sync without
resending unchanged context. Switchboard task details expose Continuation context,
including human instructions and worker checkpoints. Interrupted requests retry the
original snapshot; later changes follow as a separate edit. Older daemons keep the
existing title/description contract. No new setup or cloud service is required.
