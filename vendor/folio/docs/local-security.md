# Folio local security model

The loopback UI serves public static application assets and legal texts, but all `/api/` reads and writes require authentication. The session exchange accepts only the per-server browser launch credential in a JSON request body. `folio ui` gives that credential to the browser as a fragment; the UI clears it before exchanging it for an HttpOnly, SameSite=Strict, session-only cookie. It does not store the launch credential in browser storage. Every browser API request also requires a separate proof returned only by the valid exchange and held in origin-scoped sessionStorage. Cookie alone and proof alone grant no access: cookies are not port-scoped, while sessionStorage is. The proof is never returned by API state. An additional CSRF value authorizes session mutations. The existing exact Host, Origin and JSON-content checks apply. Responses use `no-store` and `no-referrer`; access logs exclude query values, headers and request bodies.

The CLI loads the owner credential from `.server.json` and includes it on every API request. It never obtains an owner credential from an HTTP bootstrap response. Discovery must be a regular file owned by the current OS account with mode 0600; symlinks and other permissions are rejected. The workspace directory must belong to that account and must not be writable by other accounts. Credentials rotate on each start and the owning server removes its discovery file on close. Old browser sessions no longer authorize a restarted server.

The launch credential is single-use. `POST /api/session` consumes it under the session lock and writes a fresh one to `.server.json` before answering, so replaying a captured fragment is 403 with no cookie, even with the live cookie. Concurrent exchanges open exactly one session, and a failed discovery rewrite grants nothing. A later `folio ui` against the running server reads the fresh credential and opens an authenticated tab.

The actor recorded in the activity log and passed to plugin handlers is derived from the credential, not from headers. Only the owner token (the CLI) may send `X-Folio-Origin: cli` and `X-Folio-Via`; a browser session is always the `user` actor.

Use `folio ui` to open an authenticated browser (add `--data-dir` for a workspace other than the default). A bookmarked bare URL works only while that browser retains its current session. `--no-open` starts or reuses the server without exposing a credential in terminal output; run `folio ui` separately to sign in. `folio server-stop` authenticates through private discovery. Keep workspace files and browser profiles private. Do not publish the launch fragment, credential file, cookies or request bodies in logs or support reports.

This is an OS-account ownership boundary, not isolation from software running as the owner. Such software can read the workspace, private discovery and project files or act as the owner. Static assets contain no workspace data. A compromised owner account or browser can access that account’s Folio workspace. Folio is not intended as a remotely hosted or shared multi-user server.

Native Windows is not supported: the ownership and mode checks above are skipped there, and no confirmation dialog can open. From WP-9, `folio` refuses to start on native Windows and points to WSL2, where the Linux checks apply.

## Backlog.md and its browser board

Folio stores tasks as Backlog.md 1.53.0 files in a private git repository and changes them only through the
pinned Backlog.md command line.

**Never run `backlog browser`.** Backlog.md ships its own web board. It does not check the Host header and
has no CSRF protection, so a web page you visit can send it requests, and it can write task files. It is
outside Folio's authentication, session proof and CSRF checks. Folio never starts it; the adapter refuses the
subcommand; a static test fails the build if `folio/`, `scripts/` or `tests/` call it; and the security suite
puts a recording fake `backlog` on `PATH` behind every adapter operation and HTTP route to prove it is never
spawned. A repository bootstrapped by Folio is written with `auto_open_browser: false`. Do not start the board
by hand for a quick look. Use `backlog task list --plain` for a terminal view. The security suite also replays
the board's CSRF probe (no credential, any Host, cross-origin `text/plain` POST, form and `null`-origin
variants) against Folio's own API: every variant is 403 and nothing is written.

The exposure is upstream's. Until it is fixed in a version Folio pins, the rule above stands.

### The pinned binary

- Version **1.53.0** exactly. Folio does not follow newer releases; an upgrade is a reviewed change.
- Before each use Folio checks the binary's `sha256` (before running it at all) and that `backlog --version`
  reports exactly 1.53.0. A mismatch is exit code 7.
- From WP-9 the version, download URL and `sha512` per platform come from the lock file shipped inside the
  Folio package, and only `folio tools ensure` downloads: over HTTPS, `sha512`-checked before extracting,
  refusing archive members that are absolute, contain `..` or are links, and recording the extracted
  binary's `sha256`. A platform with no entry (native Windows included) is refused with no unpinned fallback.
- No environment variable or config setting changes the pin. `FOLIO_BACKLOG_BIN` only tells the developer
  test run where the binary is; its version and hash are still checked.
- Every Backlog.md subprocess runs with a fixed argument list (no shell), a minimal environment and a
  temporary `HOME`. The allowed first words are `init`, `task`, `doctor`, `config`, `doc` and `--version`.

### `onStatusChange`

Backlog.md can run a shell command, named by the `onStatusChange` key in `backlog/config.yml` or in a task
file, whenever a task's status changes. The key survives edits. A task file that arrives through `git pull`
could therefore run code as you the next time a status changes.

- Before every edit Folio scans `backlog/config.yml` and the task file, as raw text, for the key in any case
  or spelling (`onStatusChange`, `on_status_change`, `on-status-change`), anywhere in the file. A hit refuses
  the edit (exit code 4) and the Backlog.md binary is not run. A file that cannot be read, or is over 8 MiB,
  is refused too.
- A repository Folio bootstraps sets `remote_operations`, `check_active_branches` and `auto_commit` to false
  and has no `onStatusChange`. The adapter's `doctor` fails when any of those three is on.
- From WP-10, every sync runs the same scan after the pull. A key that arrived from the remote shows a banner;
  Folio does not edit that file, a key in the config blocks writes, and nothing is executed. Remove it by
  hand.

### Titles and values

Folio checks every value before it starts a process. A value that starts with `-`, contains a NUL, or (for
titles) is longer than 79 characters or spans lines is refused with exit code 4, so a task title cannot
become an option to the CLI.

## Tasks repositories, sync and the deploy key

These arrive with WP-10.

- One private repository per channel. With `"machine_profile": "laptop"` in the local config, only `example-channel`
  repositories are accepted; registering, syncing or repairing a repository of another channel is refused
  (exit code 4) before any git or Backlog.md process runs.
- The only credential on the laptop is a write deploy key scoped to `example-org/tasks-example-channel`. It lives in
  `~/.ssh` and is used by `git`. Folio never reads, prints, logs or stores it.
- A push needs a positive answer that every push URL of `origin` is private, asked again on every push. A
  public or unknown answer, an error or no checker refuses the push (exit code 4). No environment variable,
  flag or setting overrides this, and no Folio git command forces or rewrites remote history. Credentials in
  remote URLs are masked in banners.
- A per-machine file (`.server.json`, `outbox.jsonl`, `approvals.jsonl`, `usage.json`, `example-channel-allow-list.json`)
  that is committed blocks the push.
- A duplicate task number blocks writes for that repository until `folio repair-ids --repo <path> --yes` is
  run. Task identity is the `fid:` label, so a renumbering does not change which task local state refers to.
- Repository contents are trusted only as far as the repository's writers are trusted. The checks above
  protect format and storage consistency and stop code execution through `onStatusChange`; they do not
  authenticate who wrote a task, and they do not make a shared repository a safe boundary. Do not add a
  collaborator you would not trust with your account.

## Plugins

Plugins are discovered through the `folio.plugins` entry-point group, but a plugin is imported only if it is
enabled by name in the local config (`$XDG_CONFIG_HOME/folio/config.json`, else `~/.config/folio/config.json`);
an entry point that is not named there is never imported, and with no plugin enabled Folio opens no extra
socket. Plugin routes are mounted under `/api/plugins/<name>/` behind the same owner-token or session-plus-CSRF
checks and cannot mount anywhere else. A malformed or failing plugin is refused at startup with nothing
half-mounted. The name `switchboard` is reserved: `/api/plugins/switchboard/*` always answers 404.

## Approvals

`POST /api/approvals/<id>/resolve` needs the same owner token or session plus CSRF as every `/api` write, and nothing is sent to the approvals source until a native confirmation dialog returns an explicit Approve or Deny; a timeout or close counts as Cancel. With no provider (the default) nothing can be resolved. Folio keeps a local trace at `$XDG_STATE_HOME/folio/approvals.jsonl` (mode 0600 in 0700 folders, never opened through a symlink, ids and the clicked choice only, no command text), and never writes it to a task file or to git. See `docs/approvals.md`.

## Ollama plugin

The optional `ollama` plugin is off unless the local config names it. It talks only to a loopback URL: an
IPv4 loopback literal, `[::1]`, or `localhost` when every address it resolves to is loopback. Other hosts,
`https`, IPv4-mapped addresses and user information are refused before anything is mounted, redirects are
never followed and proxies are ignored. Replies are capped at 256 KB and must match a strict schema (at most
10 items, titles of 1 to 79 characters, no leading `-`). The task text is framed as untrusted data and the
model gets no tools and no shell. Text in a task that tells the model to ignore its instructions can change a
proposal and nothing else: only Accept writes, through the same adapter. See `docs/ollama.md`.

## Local state

Folio's per-machine state lives under `$XDG_STATE_HOME/folio` (default `~/.local/state/folio`) and
`$XDG_CONFIG_HOME/folio` (default `~/.config/folio`): the approvals log, the local config and, with the later
work packages, the create outbox (WP-10), the usage counter (WP-14) and the migration salt (WP-11). Per-run
discovery (`.server.json`) lives in the workspace. None of it is synced. The usage counter holds integer
per-day counts only, opens no network connection, and is reset by deleting the file. Files that hold anything
private are mode 0600 and symlinks are refused.

## Migration

Migration from Folio 1.1.x (WP-11) is fail-closed. Only allow-list entries whose channel is exactly `example-channel` are
copied; unknown, unlisted and other-channel entries produce no file, path, title or commit. The source JSON is
read with plain file reads, hashed before and after, and never written or copied into a repository. Reports
and logs show aliases or `h:` hashes and counts, never a client, project or task name. Apply needs the
allow-list's sha256 as reviewed; editing the allow-list afterwards makes apply refuse (exit code 4). Apply
never pushes. See the [migration runbook](migration-runbook.md).

## Regression suite

`tests/test_wp13_security_{kept,http,tools,pending}.py` (with `tests/wp13_support.py`) run in the default `python3 -m unittest discover -s tests`. They re-check the kept behaviours listed in `tests/KEEP.md` and cover the single-use launch credential, credential-derived actors, plugin route auth, the reserved `/api/plugins/switchboard/*` prefix (404), Ollama loopback refusal, the `onStatusChange` guard, no `backlog` board spawn, approvals-log file mode, no sockets with plugins off, and a replay of the Backlog-board CSRF probe against Folio (every variant 403, nothing written). Items whose code belongs to WP-9 (native Windows refusal), WP-10 (private-remote push, laptop `example-channel` profile) and WP-11 (fail-closed migration) skip with a reason naming the WP and fail once that seam lands, so the skip cannot outlive it.

## Project-file trust

Folio 1.1.x projects store portable planning data in `.task-manager/project.json`. Folio validates the supported schema, project identity, revisions and task fields, and refuses known storage symlinks. These checks protect format and storage consistency; they do not authenticate who authored an imported project or make a shared repository a safe boundary. A project file written by Folio 1.1.x may still carry its old Switchboard link data; Folio keeps it untouched and never acts on it. Only register or restore project folders and backups you trust. Editing or importing owner-trusted files is not equivalent to granting read-only access.

## What this does not cover

- Software running as your OS account, and a compromised browser profile.
- Backlog.md itself beyond the pin and the checks above. Folio does not sandbox it.
- The security of the git host, or of a repository you are not the only writer of.
- A model's output. A proposal is a suggestion that a person accepts or rejects.
