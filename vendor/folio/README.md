# Folio

A local planning layer over [Backlog.md](https://github.com/MrLesk/Backlog.md). Tasks live as plain
Markdown files in private git repositories, one repository per channel. Folio adds cross-list views, a
brief for agents, a local approvals inbox and git sync on top, and keeps the Backlog.md files as the only
source of truth.

Folio source code and documentation are licensed under [Apache-2.0](LICENSE).
See [NOTICE](NOTICE) for copyright, trademark and third-party attribution.
Tests run locally; this repository contains no GitHub Actions workflows.

**Never run `backlog browser`.** Backlog.md's own web board is outside Folio's security model (see
[Security model](#security-model)). Folio never starts it, and you should not either.

## What is in this version

Folio on Backlog.md is delivered in work packages (WP). This tree still reports version 1.1.2, and its
browser UI still reads the Folio 1.1.x JSON workspace. The release number is set when the remaining work
packages are merged. Sections below that describe a later work package say so.

| Part | Status |
| --- | --- |
| Backlog.md adapter and the `onStatusChange` guard (WP-2) | in this version; the Ollama plugin's Accept writes through it |
| Approvals interface and local log (WP-5a) | in this version; no decision provider ships |
| Cuts (WP-6), plugin host and Switchboard freeze (WP-7), Ollama plugin (WP-8) | in this version |
| Security regression suite (WP-13) | in this version, part of the default test run |
| Lists and labels (WP-3), cross-list views and the list brief (WP-4) | arrive with WP-3 and WP-4 |
| Pinned Backlog.md download, `folio tools`, native-Windows refusal (WP-9) | arrive with WP-9 |
| Git sync, `folio repos add`, `folio repair-ids` (WP-10) | arrive with WP-10 |
| `folio migrate` (WP-11) and `folio usage report` (WP-14) | arrive with WP-11 and WP-14 |

## Requirements

- macOS or Linux. On Windows, use [WSL2](#windows-wsl2-only).
- [`uv`](https://docs.astral.sh/uv/) (or `pipx`) and `git`.
- Python 3.9 or newer. Folio has no third-party Python dependencies, no frontend build and no Node runtime
  requirement.

## Install

Folio is public code. Installing it needs no account and no credential. Install a pinned commit (a full
40-hex sha) or a tag of the source repository; do not install a moving branch:

```sh
uv tool install "git+https://github.com/example-org/folio-oss@<sha|tag>"
folio --version
```

The `pipx` equivalent:

```sh
pipx install "git+https://github.com/example-org/folio-oss@<sha|tag>"
```

Both put `folio` and `folio-server` on your `PATH`. There are no other install paths: no installer
script, no package-manager formula and no built archive.

Then fetch the pinned Backlog.md binary and open the UI (WP-9):

```sh
folio tools ensure
folio doctor
folio ui
```

`folio tools ensure` is the only command that downloads anything, and running it is the consent. It fetches
Backlog.md **1.53.0** for your platform once, over HTTPS, checks its `sha512` against the lock file shipped
inside the Folio package before extracting, keeps only the `backlog` executable under
`$XDG_DATA_HOME/folio/tools/backlog-1.53.0/` (default `~/.local/share/folio/tools/backlog-1.53.0/`) and records
its `sha256`. A second run downloads nothing. A binary whose version or hash drifts later is refused (exit
code 7), and no environment variable or config file changes the pin. `folio tools verify` re-checks the
installed binary without downloading. `folio doctor` is read-only; from WP-9 it also prints the pinned
Backlog.md version and the lock's `sha256`.

`folio ui` starts the local server and opens an authenticated browser session.

Upgrade or remove Folio with `uv`. The distribution is called `folio-workspace`. Removing it leaves your
tasks repositories and local state alone:

```sh
uv tool upgrade folio-workspace
uv tool uninstall folio-workspace
```

`uv tool upgrade` keeps the reference you installed. To move to a new commit or tag, run `uv tool install`
again with the new reference. Stop the server with `folio server-stop` before uninstalling.

### Windows (WSL2 only)

Folio does not run on native Windows: its file-permission checks and its confirmation dialog are not
available there. From WP-9, `folio` refuses to start on native Windows with a message that points to WSL2.
Open a WSL2 distribution (for example Ubuntu) and follow the Linux instructions inside it; WSL2 is Linux and
runs normally.

## The tasks repository and its deploy key

Each channel has one private tasks repository. The `example-channel` channel's repository is `example-org/tasks-example-channel`.
A machine that works on `example-channel` holds exactly one credential for it: a **write deploy key scoped to
`example-org/tasks-example-channel` only**. It is a normal git credential in `~/.ssh` with a host alias. Folio never
reads, prints or stores it; `git` uses it.

1. Create a key used for this repository and nothing else, and print its public half:

   ```sh
   ssh-keygen -t ed25519 -f ~/.ssh/folio_tasks_example_channel -C "folio tasks-example-channel"
   cat ~/.ssh/folio_tasks_example_channel.pub
   ```

2. Give the public half to the repository owner, who adds it as a **deploy key with write access** to
   `example-org/tasks-example-channel`. Never add it to a personal or organisation account.
3. Add a host alias to `~/.ssh/config` so that `git` picks that key for that repository only:

   ```text
   Host tasks-example-channel
     HostName github.com
     User git
     IdentityFile ~/.ssh/folio_tasks_example_channel
     IdentitiesOnly yes
   ```

4. Clone through the alias, register the clone with its channel (WP-10) and run the read-only doctor:

   ```sh
   git clone git@tasks-example-channel:example-org/tasks-example-channel.git
   folio repos add <path> --channel example-channel
   folio doctor
   ```

Registered clones are kept in the per-machine config `$XDG_CONFIG_HOME/folio/config.json` (default
`~/.config/folio/config.json`), which also names the enabled plugins. With `"machine_profile": "laptop"` in
that file, only `example-channel` repositories are accepted: registering, syncing or repairing a repository of any other
channel is refused (exit code 4) before any git or Backlog.md process runs, and a laptop never holds another
channel's key.

## Lists and labels

From WP-3, a **list** is a Backlog.md *project*, configured in the repository's `backlog/config.yml` under
`projects:`. Folio keeps the rest flat:

| Concept | Backlog.md 1.53.0 |
| --- | --- |
| List | a `projects:` entry; each task carries a `project` value |
| Status | `To Do`, `In Progress`, `Blocked`, `Done` |
| Priority | `Urgent`, `High`, `Medium`, `Low` |
| Client | the label `client:<alias>` (an alias, never a real name) |
| Workstream | the label `ws:<slug>` |
| Folio identity | the label `fid:<16 hex>`, exactly one per Folio-managed task |

- The statuses and priorities above are those of a repository bootstrapped by Folio. A plain `backlog init`
  repository has no `Blocked` status and no `Urgent` priority.
- Folio's local state (approvals, plugin mappings, usage counts) refers to the `fid` label, never to
  `TASK-N`, so a renumbered task stays the same task.
- A new task must name a configured list. A task for an unconfigured list is refused (exit code 4) and
  nothing is created.
- List names use letters, digits, space, `-`, `_` and `.`, at most 64 characters (a provisional limit), and
  are unique ignoring case. Renaming a list keeps every task and draft; if a task file that the Backlog.md
  CLI cannot reach still names the old list, the rename is refused before anything is written.
- Titles are at most 79 characters and one line, because Backlog.md folds longer titles into the file name.
  Longer text belongs in the description. A value that starts with `-` or contains a NUL is refused too.
- A repository bootstrapped by Folio has `remote_operations`, `check_active_branches` and `auto_commit` set
  to false and `auto_open_browser` off. It has no `onStatusChange` key, and Folio writes no `AGENTS.md` or
  `CLAUDE.md`.

Agents create and move tasks through the Backlog.md CLI or its stdio MCP server. A hand-made Backlog.md edit
made offline can collide on a task number; the next sync detects it (see [Sync](#sync)).

## Views and the brief

- **Portfolio, client and project views** show progress, blocked and overdue tasks. An attention item is a
  blocked or overdue unfinished task, counted once. From WP-4 the views roll up every list of a channel under
  per-channel headers, and a channel's view never shows another channel's record.
- **`folio brief`** prints a bounded summary of one list for an agent; `<list>` names the list (in this
  version, a project of the workspace). **`folio source`** fetches a source text the brief omitted, with
  content-hash verification. See [planning sources](docs/planning-sources.md).
- Task text is always rendered escaped.

```sh
folio brief <list> --query "release plan"
folio source <source-id> --project <list>
```

## Approvals (local only)

Folio has an approvals inbox with a native confirmation dialog, but **no decision provider ships in this
version**: `GET /api/approvals` answers "No approvals source configured" and nothing can be resolved. A
plugin can supply a provider. Resolving an approval needs the authenticated session, the CSRF value and an
explicit Approve or Deny click in the dialog; a dialog that times out or is closed counts as Cancel. The
record of what was resolved is a local file, `$XDG_STATE_HOME/folio/approvals.jsonl` (mode 0600, default
`~/.local/state/folio/approvals.jsonl`), and is never written to a task file or to git. See
[approvals](docs/approvals.md).

## Sync

From WP-10, `folio sync --repo <path>` keeps a registered tasks clone in step with its private remote:
fetch, rebase with autostash, the `onStatusChange` scan, `backlog doctor`, the `.gitattributes` and
`.gitignore` guards, the create outbox, then push.

```sh
folio sync --repo <path>
```

- **Different tasks** edited on two machines merge on their own (one file per task).
- **The same task** edited on two machines stops the sync with a conflict. The rebase is kept for you,
  nothing is pushed and writes are blocked until it is resolved. Nothing is overwritten silently.
- **Offline creates** are queued with a pre-assigned `fid` in `$XDG_STATE_HOME/folio/outbox.jsonl` (mode
  0600), shown as "pending sync", and created after the next successful pull, so two offline machines never
  take the same `TASK-N`.
- **Duplicate task numbers** (two machines created `TASK-7` with the raw Backlog.md CLI) are detected after
  every pull. They are not pushed, and every Folio write to that repository is blocked until you repair it:

  ```sh
  folio repair-ids --repo <path>
  ```

  Without `--yes` it prints Backlog.md's repair preview and the dependencies that point at a renumbered task
  for you to review, and changes nothing. With `--yes` it applies the repair, re-runs `backlog doctor` and
  commits it. Every `fid:` label is kept.
- **Push goes to a private remote only.** Before every push Folio asks whether each push URL is private; a
  public or unknown answer refuses the push (exit code 4), and there is no setting to allow it. Folio never
  forces a push. Until a token source for that check is decided, a push to a private GitHub remote is
  refused as well (fail closed).
- A pulled task or config that contains an `onStatusChange` key shows a banner. Folio will not edit that
  file, and a key in the config blocks writes until a person removes it.

| Stays on this machine, never synced | Synced through git |
| --- | --- |
| `config.json` (registered clones, channel aliases, enabled plugins and their settings) | `backlog/` (tasks, drafts, completed, archive, docs, decisions, `config.yml`) |
| `.server.json` (per-run credentials) | `.gitattributes`, `.gitignore` |
| `approvals.jsonl`, `outbox.jsonl`, `usage.json` | `folio/migration-sources.json` (after a migration) |
| The migration allow-list and its hash salt | |

A push is refused while any of the per-machine files is committed.

## Ollama (local models, optional)

The `ollama` plugin turns one task into **proposed** subtasks. It is off by default: nothing is imported and
no socket is opened until your local config names it. It talks only to a loopback address, for example
`http://127.0.0.1:11434`; any other host and `https` are refused before anything is mounted, proxy settings
are ignored and redirects are never followed. Its output is a proposal card with at most 10 items (titles of 1 to 79 characters). Nothing is
written until you accept, and Accept writes through the same Backlog.md adapter as every other edit. The model
gets no tools and no shell, and one channel's data only, framed as untrusted text. See
[the Ollama plugin](docs/ollama.md).

## Plugins

Folio has a minimal plugin host. Plugins are discovered through the `folio.plugins` entry-point group, but a
plugin is imported only if it is enabled by name in your local config. Its routes are mounted under
`/api/plugins/<name>/` behind the same authentication as the core.

## Switchboard freeze

Switchboard integration is frozen and removed from this tree; tag `archive/switchboard-1.1.2` keeps the last code, and it may return only as a plugin, through a new work package and a new review.
The branch `archive/switchboard` points at the same commit. `/api/plugins/switchboard/*` is reserved and
always answers 404.

- **Removed:** project linking, sending tasks to agents, agent badges and sync banners, proposals, the
  decision inbox and the background sync thread, with their CLI commands (`folio projects link|unlink`,
  `folio proposals`, `folio decisions`) and API routes.
- **Still accepted:** `--no-sync` and `--no-notifications` on `folio-server` do nothing, so existing
  launchers keep working.
- **Your data:** project files written by Folio 1.1.x keep their link data untouched, but Folio no longer
  reads it. Folio never reads or writes Switchboard's own data.

The work-package cuts also removed `folio tasks …`, `folio agent-guide` and `folio backup` (usage errors,
exit code 1): tasks are edited in the UI or through the Backlog.md CLI.

## Migrating from Folio 1.1.x

Migration is a single, reviewed, fail-closed step (WP-11): only entries on an allow-list that you confirmed are
copied, and the old JSON workspace is never modified or deleted. Follow the
[migration runbook](docs/migration-runbook.md). The [trial and retirement note](docs/trial-note.md) says how
Folio is kept or retired.

## Security model

The short version. The full text is in [the local security model](docs/local-security.md).

- **Loopback only, authenticated.** The server binds to `127.0.0.1`. Every `/api/` read and write needs the
  per-run owner credential or an authenticated browser session; Host, Origin, JSON content type, CSRF and a
  session proof are all checked. Credentials rotate on each start and the browser launch credential is
  single-use.
- **Folio changes tasks only through the pinned Backlog.md CLI** (version 1.53.0, hash-checked), with fixed
  argument lists, never a shell, and a temporary `HOME` per call. The adapter allows the `init`, `task`,
  `doctor`, `config` and `doc` commands and `--version`, and nothing else.
- **`onStatusChange` is blocked.** Backlog.md runs a shell command named in a task or config when a status
  changes, so a synced task file could run code on your machine. Folio refuses to edit a task (exit code 4,
  the binary is not run) when the key appears in `backlog/config.yml` or in the task file, in any spelling or
  case. The adapter's repository check fails when `remote_operations`, `check_active_branches` or
  `auto_commit` is on.
- **Never run `backlog browser`.** Backlog.md's own web board has no Host check and no CSRF protection, so any
  web page you visit could drive it. Do not start it, not even once and not for a quick look. Folio's UI is
  the only supported browser view, and it never starts the board. Use `backlog task list --plain` for a
  terminal view.
- **Plugins** are off by default; the Ollama plugin is loopback-only; approvals are recorded locally only.
- **One credential**, the `tasks-example-channel` deploy key, held by git and never read by Folio. A laptop works with
  `example-channel` only.
- **No telemetry.** The usage counter (WP-14) is a local file of per-day integer counts, and nothing leaves
  the machine.

## Command line and agents

Output is JSON; `--format table` gives a readable table.

```sh
folio --version
folio ui --no-open
folio server-stop
```

`folio ui --no-open` starts or reuses the server without printing a credential; run `folio ui` to sign in.
`folio server-stop` stops it. In this version the CLI also reads the 1.1.x workspace: `folio status`,
`folio clients`, `folio projects`, `folio workstreams`, `folio notes`, `folio restore` and
`folio migrate-workspace`. The server and the CLI choose the workspace the same way: `--data-dir`, else
`FOLIO_WORKSPACE`, else the user data directory (`$XDG_DATA_HOME/folio/workspace` on Linux, default
`~/.local/share/folio/workspace`).

Exit codes: 0 success, 1 usage (or a missing `--yes`), 2 not found or ambiguous, 3 conflict, 4 validation
or refusal, 5 storage, 7 human confirmation cancelled or unavailable, or a Backlog.md binary that is missing
or not the pin.

Agents that need to read or write tasks use Backlog.md directly, through its CLI or its stdio MCP server, and
read context with `folio brief`.

## Local API

`GET /api/state` returns the workspace and the per-process CSRF value. Mutations require JSON and
`X-Workspace-Token` from that response; existing-project changes also require the current project `revision`.
This table is checked against the served routes by `tests/test_wp12_docs_inventory.py`.

| Route | Method | Purpose |
| --- | --- | --- |
| `/api/session` | POST | Exchange the single-use launch credential for a browser session |
| `/api/state` | GET | Read the workspace |
| `/api/clients` | POST | Create a client |
| `/api/clients/<id>` | PATCH | Update a client |
| `/api/projects` | POST | Create or reopen a project folder |
| `/api/projects/<id>` | PATCH | Update project details, status, or notes |
| `/api/projects/<id>/workstreams` | POST | Add a workstream |
| `/api/projects/<id>/tasks` | POST | Create a task |
| `/api/projects/<id>/tasks/<task-id>` | PATCH, DELETE | Update or delete a task |
| `/api/projects/<id>/brief` | GET, POST | Read bounded planning context; POST accepts `query` and `max_chars` |
| `/api/projects/<id>/source` | POST | Read a source by `source_id`, optional expected `hash`, `offset`, and `max_chars` |
| `/api/projects/<id>/notes/sections` | GET, POST | List addressable notes, or remember a named note or decision |
| `/api/projects/<id>/notes/sections/<section-id>` | PATCH, DELETE | Correct or forget one section with project `revision` and optional source `hash` |
| `/api/projects/<id>/relocate` | POST | Register another folder for a project without moving source files |
| `/api/projects/<id>/notes/append` | POST | Append to notes |
| `/api/shutdown` | POST | Gracefully stop this server (`folio server-stop` uses it) |
| `/api/approvals` | GET | Pending approvals from a provider plugin, or the empty state |
| `/api/approvals/<decision-id>/resolve` | POST | Ask for confirmation in a native dialog, then approve, deny, or answer |
| `/api/plugins/<name>/...` | any | Routes of a plugin enabled in local config (`switchboard` is reserved: always 404) |
| `/api/plugins/ollama/suggest` | POST | Optional Ollama plugin: propose subtasks for a task (writes nothing) |
| `/api/plugins/ollama/accept` | POST | Optional Ollama plugin: create the accepted subtasks with `fid` labels |
| `/api/<anything else>` | any | 404, also with a valid credential |

The server serves no third-party scripts, fonts, analytics or remote resources. It is a single-user
application for a trusted local machine. Do not expose it through a public tunnel or reverse proxy.

## Development

```sh
python3 -m unittest discover -s tests -v
node --check folio/static/app.js
scripts/ci-local.sh
```

`scripts/ci-local.sh` runs both checks with a log and a JSON summary (`--full` adds the browser smoke). The
security regression suite and the doc-tests for this README run in the default `unittest` command.

The Backlog.md contract tests and the real-binary adapter tests need the 1.53.0 binary and fail, on purpose,
without it. Point `FOLIO_BACKLOG_BIN` at it for the run (never write it into a repository file); the version
and hash are still checked. `FOLIO_BACKLOG_CONTRACT=skip` is the explicit, announced opt-out. Tests never
start the Backlog.md board.
