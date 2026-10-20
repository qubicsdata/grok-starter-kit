# Changelog

All notable changes to this repository are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Release notes up to
1.1.2 live in `docs/releases/`.

## [Unreleased]

### Added
- `scripts/ci-local.sh`: the local gate as one command (unit tests and the JavaScript syntax check;
  `--full` adds the browser smoke; `--baseline FILE` passes only when every failing test is already
  known). Offline, writes a log and a JSON summary to `~/.local/state/ci-local/folio/` (or
  `$CI_LOCAL_LOG_DIR`), exits non-zero on failure.
- `tests/characterization/`: golden tests that freeze the 1.1.2 brief/source JSON contract, the
  attention rule (blocked or overdue), and the approvals display and dialog contract. Goldens are
  regenerated only with `FOLIO_UPDATE_GOLDENS=1` (WP-1).
- `tests/KEEP.md` and `tests/characterization/test_http_security_keep.py`: the 1.1.2 local HTTP
  security behaviour as `@keep` tests KEEP-SEC-01..13, which later work must keep green (WP-1).
- `tests/backlog_contract/`: a Backlog.md contract suite pinned to exactly 1.53.0 (ADR-0001 facts
  1-6: reads JSON, projects, the dropped unknown key and surviving `fid:` label on edit, the title
  fold, the two-clone duplicate ID and `doctor --fix --yes`, the config pins). It runs against the
  binary named by `FOLIO_BACKLOG_BIN` and fails when that is unset or reports any other
  version; only the explicit, announced opt-out `FOLIO_BACKLOG_CONTRACT=skip` skips it. Every call goes through an argv guard that allows only `init`, `task`, `doctor`,
  `config`, `doc` and `--version`, and a static scan fails if `folio/`, `scripts/` or `tests/`
  invoke the Backlog.md web UI subcommand (WP-1).
- `folio/backlog/`: the Backlog.md adapter (WP-2), documented in `docs/backlog-adapter.md`. No CLI
  command uses it yet; the Ollama plugin's Accept route (WP-8) writes through it.
  - `BacklogClient` with `list`, `view`, `create`, `edit`, `resolve`, `doctor` and `doc_*`. Fixed argv
    with a first-word allowlist, a temporary `HOME` per call, values checked before any spawn (option-like
    values, NUL, titles over 79 characters or on several lines are refused with exit 4). `create` labels
    the task `fid:<hex>` and resolves `TASK-N` by re-listing. `list` is cached on the git `HEAD` plus the
    tasks-dir listing and `config.yml`.
  - `ToolResolver` checks the sha256 (before running anything) and `--version` == `1.53.0` exactly;
    any mismatch is exit 7. The lock cross-check test is skipped until WP-9.
  - The `onStatusChange` guard: an edit is refused (exit 4, binary not run) when the config or the task
    file contains the key in any case. `doctor` fails when `remote_operations`, `check_active_branches`
    or `auto_commit` is on.
  - Static tests: no `shell=True`, no write under `backlog/**` outside the subprocess.
- Review fixes (review r1, WP-1): the characterization fixtures use `/nonexistent/fixture-home`
  instead of a `/home/<name>` path (R-b), and `FOLIO_UPDATE_GOLDENS=1` refuses to rewrite `keep_*`
  goldens.
- `folio/approvals.py`: the approvals interface (WP-5a). A `DecisionProvider` supplies pending
  decisions; `Approvals` resolves one only after the native confirmation dialog (`dialogs.py`,
  reused) returns an exact Approve or Deny click, so a timeout, a close or a crash counts as
  Cancel and nothing reaches the provider. With no provider configured (the default; WP-7 lets a
  plugin supply one) the inbox is an empty state, "No approvals source configured", and resolve
  answers 404 `NO_APPROVALS_SOURCE` without opening a dialog or writing local state.
- `ApprovalLog` (WP-5a): a local, append-only trace at `$XDG_STATE_HOME/folio/approvals.jsonl` (or
  `~/.local/state/folio/approvals.jsonl`), created 0600 whatever the umask. Every open uses
  `O_NOFOLLOW` and `O_NONBLOCK`; a symlink, FIFO, folder or a file with another mode or owner is
  refused and left unchanged, and a refused log stops a resolve before the dialog opens. It records
  ids and the clicked choice only (no command text, note or answer, M-6), and its notification
  claims de-duplicate notifications across restarts.
- `GET /api/approvals` and `POST /api/approvals/<decision id>/resolve` (WP-5a), behind the existing
  `/api` owner-token or session-plus-CSRF checks.
- `folio/plugins/__init__.py`: the minimal plugin host (WP-7, D-10). Plugins are discovered through
  the `folio.plugins` entry-point group and enabled only by name in the local config
  `$XDG_CONFIG_HOME/folio/config.json` (else `~/.config/folio/config.json`) as
  `{"plugins": {"<name>": {<settings>}}}`; an entry point that is not named there is never imported,
  and with no config file nothing is imported. A plugin exposes `name`, `routes()`,
  `decision_provider()`, `on_task_change(fid)` and `close()`.
- Plugin routes (WP-7) are mounted under `/api/plugins/<name>/` behind the unchanged `/api` owner-token
  or session-plus-CSRF checks. A route outside the plugin's own prefix, a malformed name, a duplicate
  name, a configured plugin that is not installed, a factory that fails or a malformed config refuses
  the plugin (`PluginError`, fail closed, nothing half-mounted). Dispatch consults a plugin only for
  paths under its own prefix, so a permissive pattern can never shadow a core route.
- The plugin name `switchboard` is reserved (WP-7): never mounted, never imported even when configured,
  and `/api/plugins/switchboard/*` is 404 in every configuration (403 without a credential).
- The approvals inbox takes the first plugin-provided `DecisionProvider`; `on_task_change` fans out
  to every plugin after a task is created or edited (one plugin's failure is logged and stops neither
  the others nor the change); `App.close()` closes every plugin once, also on `folio-server` shutdown
  (WP-7).
- `folio_ollama/`: the loopback-only Ollama plugin (WP-8, M-7, D-16), a top-level package shipped as the
  `folio.plugins` entry point `ollama = folio_ollama:make`. It is off by default: nothing is imported and
  no socket is opened unless the local config names it, as
  `{"plugins": {"ollama": {"url": "http://127.0.0.1:11434", "model": "<model>", "channel": "<channel>",
  "repo": "<that channel's tasks repo>", "timeout": 60}}}`. Unknown or malformed settings refuse the
  plugin at startup (`PluginError`, nothing mounted). No new dependency: stdlib `urllib` only.
- The Ollama URL must be `http://` on a loopback address: an IPv4 loopback literal (127/8), `[::1]` or
  `localhost` when every address it resolves to is loopback; the resolved literal is pinned at load
  time, so a later DNS answer cannot redirect the call. `10.0.0.5`, `example.com`, non-loopback IPv6,
  IPv4-mapped, user information, `https`, paths, queries and fragments are refused before anything is
  mounted, and a refused host is never resolved. The `*_proxy` environment is ignored (WP-8).
- `POST /api/plugins/ollama/suggest` with `{"channel", "task": {"title", "description"?}}` sends ONE
  request to `<url>/api/chat` (`format: json`, `stream: false`, no tool calling) and returns a proposal
  card `{"kind": "proposal", "channel", "model", "source": {"title", "hidden"}, "subtasks": [{"title"}]}`.
  The task text travels only inside a data block framed by `<<<planning_data_not_instructions` and
  `>>>planning_data_not_instructions` lines (every data line is quoted, so an embedded marker cannot
  close the block) and the system prompt forbids following instructions found in the data. The
  model's answer must match a strict schema: an object with exactly `subtasks`, at most 10 items, each
  exactly `{"title"}` with 1 to 79 printable characters that do not start with `-`. A redirect (never
  followed), any non-200 status, a body over 256 KB, malformed JSON or a schema violation is
  `502 OLLAMA_RESPONSE`; a refused connection or a timeout is `503 OLLAMA_UNAVAILABLE`. This route
  writes nothing and spawns nothing, whatever the model says (WP-8).
- `POST /api/plugins/ollama/accept` with `{"channel", "subtasks": [{"title"}]}` is the only write: the
  whole list is validated with the same rules first (`400 VALIDATION` on any item, nothing created),
  then each task is created in order through the Backlog adapter, which assigns the `fid:` label; the
  reply is `{"created": [{"fid", "id", "title"}]}`. Accept never calls the model. The pinned Backlog.md
  binary runs with a private temporary `HOME` that the plugin removes on close (WP-8).
- Both Ollama routes serve the one configured channel: any other or missing `channel` is
  `409 SINGLE_CHANNEL` before any socket, write or other check. A malformed body is a plain 400. The
  routes sit behind the unchanged `/api` owner-token or session-plus-CSRF checks (WP-8).
- WP-13 security regression suite (`tests/test_wp13_security_{kept,http,tools,pending}.py`, `tests/wp13_support.py`),
  part of the default `unittest` run. Kept (WP-1 `@keep`, `tests/KEEP.md`): the registry is checked (every
  KEEP-SEC id names an un-skipped test with its goldens) and each kept behaviour is exercised again from an
  isolated fixture: unauthenticated -> 403, wrong Host or Origin -> 403, non-JSON -> 415, no token in
  `/api/state`, the cookie attributes, CSRF on browser writes, the 0600 discovery file read with O_NOFOLLOW,
  workspace permissions, credential rotation on restart, access logs without bodies, queries or tokens.
- New in the WP-13 suite: the launch credential is single-use (a second exchange is 403); the actor is never
  taken from `X-Folio-Origin` or `X-Folio-Via` on a browser session; plugin route auth and CSRF;
  `/api/plugins/switchboard/*` is 404 with any credential; Ollama non-loopback, look-alike, mapped-IPv6 and
  `https` URLs refused with no lookup and no socket, redirects off the loopback not followed; the
  `onStatusChange` guard refuses every edit kind and `doctor` before any spawn; no `backlog` board spawn
  (recording fake binary on PATH behind every adapter operation and every HTTP route, plus a static scan of the
  app, the plugin, the launchers and the tests); the approvals log is 0600 in 0700 folders, opened with
  O_NOFOLLOW, and a symlink, mode, directory or FIFO refuses before the dialog; no outbound socket with
  plugins off; the Backlog-board CSRF probe (no auth, any Host, cross-origin `text/plain` POST, form and
  `null`-origin variants, bodiless POSTs) replayed against Folio only, every variant 403 with nothing
  written. The board itself is never started.
- Pending seams in the WP-13 suite skip with a reason naming the owning WP and a tripwire that fails once the
  seam lands: native Windows refusal (WP-9), private-remote push, laptop `example-channel` profile and the
  pulled-`onStatusChange` banner (WP-10), the fail-closed migration fixture (WP-11). Until then: the exact
  `1.53.0` pin, no `git`, `push` or `--force` argv in the app, no lock file created.
- `docs/migration-runbook.md` (WP-12): the single-shot, fail-closed migration from a Folio 1.1.x workspace with
  `folio migrate` (WP-11): inventory and allow-list, counts-only dry run, review of the allow-list sha256,
  freeze, apply on a `folio-migration/<date>` branch, double-migration guard, count check and rollback.
- `docs/trial-note.md` (WP-12): the 4-week trial thresholds, the local usage counter and
  `folio usage report` (WP-14), and the retirement steps, which need no data work.
- The WP-12 doc-test and smoke harness: `tests/test_wp12_docs_inventory.py` and `tests/test_wp12_docs_run.py`
  with `tests/wp12_support.py`. It reads `README.md`, `docs/local-security.md`, `docs/migration-runbook.md`
  and `docs/trial-note.md`. Every fenced `sh` command must be a row of the inventory, and every row is
  exercised. The commands this tree has run offline in a temporary `HOME`: `folio --version`, `folio doctor`,
  `folio ui`, `folio ui --no-open` with `folio server-stop`, `folio brief`/`folio source`, the Backlog.md
  1.53.0 count check, `sha256sum`, the `chmod` freeze and the git rollback. A `folio` command that neither
  this tree nor a pending branch provides fails. The commands of WP-9 (`folio tools`), WP-10
  (`folio repos add`, `folio sync --repo`, `folio repair-ids --repo`), WP-11 (`folio migrate --from`) and
  WP-14 (`folio usage report`) are checked against the parser of their landed branch, then skip with a
  reason that names the WP and its branch. The checks also cover: no Homebrew or release-build install path,
  the never-run-the-board rule, the WP-6 path and bidi scanners on the docs, the README's Local API table
  against the served routes (`ROUTE_TABLE` plus `/api/session` and `/api/shutdown`), and the relative links
  and heading anchors of the README and the current `docs/*.md`.

### Changed
- `README.md` is rewritten for Folio on Backlog.md 1.53.0 (WP-12): a table of what is in this version and
  which work package brings the rest, the one-command source install
  (`uv tool install "git+https://github.com/example-org/folio-oss@<sha|tag>"`, with the `pipx` equivalent and
  `folio tools ensure` from WP-9) as the only install path, the `tasks-example-channel` write deploy key, lists and
  labels (`fid:`, `client:`, `ws:`), sync and `folio repair-ids`, the local-only Ollama plugin, the plugin
  host and the Switchboard freeze note, Windows = WSL2 only, and the security model with the rule
  **never run `backlog browser`**. The 1.1.x run-from-checkout, storage and backup text is removed; the
  Local API table gains `/api/session`.
- `docs/local-security.md` (WP-12) adds the Backlog.md board rule, the pinned and hash-checked binary, the
  `onStatusChange` guard and config pins, value checks, the private-remote push and laptop `example-channel` profile
  (WP-10), the plugin host, local state and the fail-closed migration (WP-11). The note about backup and
  project export downloads (cut in WP-6) is removed.
- `docs/ollama.md`, an Ollama section in `docs/local-security.md` and the two Ollama routes in the README's
  Local API table (WP-8). The `/api/chat` shape is not yet confirmed against an installed Ollama.
- R-b path cleanup (WP-6): `docs/acceptance/**` logs and `installed-pair.json` are redacted to `<HOME>` and
  `<TMP>`; `tests/test_dialogs.py`, `tests/test_wp7_plugin_discovery.py` and `scripts/export-source.py`
  take their home and temp paths from the temp dir or the environment (`$TMPDIR`), never literals.
- `pyproject.toml` package data is `static/*` only; `MANIFEST.in` no longer ships `folder_picker.py`
  or `scripts/*.json`. There are still 0 runtime dependencies (WP-6).
- The browser smoke seeds its fixture workspace through the owner API instead of `/api/demo` and types
  the project folder instead of mocking the native picker (WP-6).
- Docs follow the cuts (WP-6): `docs/distribution.md`, `docs/open-items.md`, `docs/product-workflows.md` and
  `docs/using-folio-and-switchboard.md` describe a source-only Folio; the Mac handoff and readiness
  notes are marked historical. Old release records under `docs/releases/` are unchanged.
- Folio 1.1.x project files still load (WP-7): the stored link keys are kept untouched but never acted on,
  and activity records whose origin is the frozen integration stay valid (new records cannot claim
  it). A formerly linked task is an ordinary task again: no `SYNC_OWNED` 409 on status or blocker,
  no 503 on delete, no relocate guard, and the stale-revision exception for sync-only revisions is
  gone. `folio restore` still detaches the old links; its result key is now `detached_links`
  (was `detached_switchboard_projects`).
- `--no-sync` and `--no-notifications` are still accepted by `folio-server` as no-ops (WP-7).
- The "no confirmation dialog can open" message now ends "Decide it in the tool that asked for it." (WP-7)

### Removed
- WP-6 cuts (D-13, M-8): the HTTP routes `/api/backup`, `/api/doctor`, `/api/projects/<id>/export`,
  `/api/folders/pick` and `/api/demo` answer 404, also when authenticated; `folio/api.py` now carries
  one `ROUTE_TABLE` (the core routes plus the `/api/plugins/` mount) and nothing else is dispatched.
- CLI (WP-6): the task CRUD group (`folio tasks list|add|update|done|reopen|delete`), `folio agent-guide`
  (and `folio/guide.py`, `folio/guide.md`) and `folio backup` are usage errors; tasks are edited through
  the Backlog CLI. `folio restore` and `folio migrate-workspace` still read 1.1.x files; `folio doctor`
  stays on the command line only.
- `folio-server --demo` and the demo seed (`Store.seed`), the appearance setting and `theme.js` (the UI
  follows the operating system appearance), the native folder picker (`folio/folder_picker.py`,
  `folder_picker.py`, `windows_desktop.py`; the project form takes a typed folder path), the project
  export and backup download buttons and the workspace health modal (WP-6).
- Build, installer, Homebrew and verify scripts (`scripts/build-*.py`, `scripts/install-folio*.py`,
  `scripts/homebrew-formula.py`, `scripts/verify-*.py`, `scripts/python-runtime-lock.json`) with their
  tests; releases are source only. `scripts/ci-local.sh --full` no longer builds a wheel (WP-6).
- Native Windows dialogs and notifications: `win32` now reads as "no confirmation dialog can open"
  (WSL2 is Linux and keeps Zenity and notify-send) (WP-6).
- Switchboard integration is frozen (WP-7, M-3, D-18): `folio/switchboard/` (sync service, outbox, runtime,
  runner thread, RPC client, decision service) and `folio/private_state.py` are deleted, with the fake
  daemon and every Switchboard test. The last code is kept at tag `archive/switchboard-1.1.2` and
  branch `archive/switchboard` (pushed at the WP-7 merge); it may return as a plugin. See the README's
  "Switchboard freeze". (WP-5a had switched `folio/switchboard/decisions.py` to the dialog text of
  `folio/approvals.py`; that Switchboard module is now gone with the rest.)
- Routes `/api/sync`, `/api/decisions`, `/api/decisions/<id>`, `/api/decisions/<id>/resolve`,
  `/api/projects/<id>/switchboard`, `/api/projects/<id>/switchboard/outbox/<id>/<retry|discard>`,
  `/api/projects/<id>/tasks/<id>/<dispatch|requeue|resend|force-status>` and
  `/api/projects/<id>/proposals/<id>/<action>` answer 404, also when authenticated (WP-7).
- CLI commands `folio sync [--watch]`, `folio projects link|unlink`,
  `folio tasks dispatch|requeue|resend|force-status`, `folio proposals ...` and `folio decisions ...`
  (usage error, exit 1). Exit code 6 (`SWITCHBOARD_UNAVAILABLE`) is no longer produced. `folio status`
  loses `totals.needs_you` and `sync_problems`; `folio tasks list` rows lose `switchboard` and
  `sending`; `folio projects list` rows lose `switchboard_detected` (WP-7).
- The browser UI loses the link section, agent badges, sync banners, proposals panel, decision inbox
  and the "Needs you" card. `folio-server --switchboard-home` and `FOLIO_SYNC_INTERVAL` are gone;
  `build_app()` takes no sync switches and `folio.web.start_sync` no longer exists (WP-7).
- `docs/drafts/wp-12/`: the WP-12a drafts, promoted to the README and the docs above (WP-12).

### Security
- The browser launch credential (`#folio-launch=<token>`) is single-use (WP-13). `POST /api/session` consumes
  it under the session lock and writes a fresh one to `.server.json` before answering, so a replay (with or
  without the live cookie) is 403 with no cookie, concurrent exchanges open exactly one session, a failed
  discovery rewrite grants nothing and leaves the credential live, and a later `folio ui` against the
  running server still opens an authenticated tab (with the live cookie it keeps the existing session).
- The actor is derived from the credential (WP-13): only the owner token (the CLI) may send
  `X-Folio-Origin: cli` and `X-Folio-Via`; a browser session is recorded as the `user` actor in the activity
  log and in plugin handlers whatever headers it sends.
