# Migrating a Folio 1.1.x workspace to a Backlog.md tasks repository

This is a **single-shot, reviewed, fail-closed** migration. `folio migrate` (WP-11) copies the allow-listed
`example-channel` planning data from a Folio 1.1.x JSON workspace into a local clone of that channel's private tasks
repository. It never changes the JSON workspace, never pushes, and a failed run is rolled back by dropping a
local branch.

`folio migrate` arrives with WP-11. Every command here is exercised only against synthetic fixtures by the
doc-tests; running it on real data is a person's decision, made in the order below.

## What maps to what

| Folio 1.1.x | Tasks repository (Backlog.md 1.53.0) |
| --- | --- |
| Client | label `client:<alias>` |
| Project | a list: a `projects:` entry in `backlog/config.yml` and the task's `project` value |
| Workstream | label `ws:<slug>` |
| Task title | `title`, at most 79 characters; a longer title is cut at a word boundary and the full title goes first in the description |
| Description | the description |
| Owner | assignee `@<alias>` only when the owner is an alias on the allow-list's `assignees`; otherwise dropped |
| Status `backlog`, `in_progress`, `blocked`, `done` | `To Do`, `In Progress`, `Blocked`, `Done` (`Blocked` is added to `statuses:` when needed) |
| Priority `low`, `medium`, `high`, `urgent` | `Low`, `Medium`, `High`; `urgent` becomes `High` plus the label `urgent` |
| Task id | label `fid:<id>`, the idempotence key |
| Project notes and sections | one Backlog.md doc per list |
| Activity history, revisions, Switchboard fields | not migrated; they stay in the read-only JSON |

Only entries on your allow-list are migrated. Everything else stays in the JSON workspace.

## Before you start

- Use the machine that holds the JSON workspace. The workspace and its backup never leave that machine and
  never go into a repository.
- Install Folio ([install](../README.md#install)) next to the old version. In this runbook the old launcher
  is called `folio-1.1.2`.
- Prepare a clean local clone of the channel's tasks repository (`example-org/tasks-example-channel`): no uncommitted
  changes, `backlog doctor` clean, Backlog.md exactly 1.53.0.

## Step 0: inventory and allow-list

```sh
folio migrate --from <workspace> --inventory
```

`--from` is required and has no default; nothing searches the disk for a workspace. The inventory lists every
client and project by alias, or by `h:<hmac12>` when the name is not an alias, with **counts only** (tasks by
status, notes, sections) and a byte hash of the source. The `h:` values use a salt kept in
`$XDG_STATE_HOME/folio/migrate-salt` (mode 0600), which never leaves the machine. An alias is lowercase
letters and digits in words joined by `-`, 3 to 48 characters; every other name is listed as `h:`.

Write `example-channel-allow-list.json` from the inventory:

```json
{"schema_version": 1,
 "entries": [{"id": "client-alpha", "kind": "client", "channel": "example-channel", "as": "client-alpha"},
             {"id": "h:0123456789ab", "kind": "project", "channel": "example-channel", "as": "project-one"}],
 "assignees": ["owner-one"]}
```

- Only an entry whose `channel` is exactly `example-channel` migrates; a project also needs its client to migrate.
- `as` is the target label or list name and must be an alias; it is required for an `h:` id.
- Unknown keys, non-alias values, a missing `schema_version` or a repeated id are refused (exit code 4).
- The file is per machine and is never committed (a sync refuses to push it).

Record the allow-list's `sha256`:

```sh
sha256sum example-channel-allow-list.json
```

(On macOS use `shasum -a 256`.)

## Step 1: dry run

```sh
folio migrate --from <workspace> --dry-run --allow-list example-channel-allow-list.json --report dry-run-report.json
sha256sum dry-run-report.json
```

The dry run prints the inventory plus a decision and a reason per entry (`allow-listed`, `unlisted`,
`other-channel`, `unknown-channel`, `client-excluded`, `ambiguous-id`) and the `migrated` and `excluded`
totals. Check that `migrated + excluded` equals the source totals and that every other-channel and unknown
entry is excluded. The report carries the allow-list `sha256` and its own `report_sha256`; `--report` also
writes it at mode 0600. No git or Backlog.md process runs, and the titles, names, descriptions and paths of
excluded entries are never printed.

The dry run is **counts only**. It does not yet produce the would-be files or check them byte for byte; that
part of the design is still open.

## Step 2: review

Send the allow-list `sha256` and the dry-run counts table to the reviewer. Nothing is applied until the
reviewer confirms that allow-list `sha256`. Changing a single byte of the allow-list afterwards changes its
`sha256`, and the review starts again.

## Step 3: freeze the source

```sh
folio-1.1.2 server-stop
folio-1.1.2 backup --output folio-final-backup.json
sha256sum folio-final-backup.json
chmod -R a-w <workspace>
```

Record the backup's `sha256`. The workspace is now read-only and stays as the backup. **It is never deleted
by the migration.** The backup file stays on this machine.

## Step 4: apply

```sh
folio migrate --from <workspace> --apply --allow-list example-channel-allow-list.json --reviewed <allow-list-sha256> --to <clone>
```

`--reviewed` is the confirmed allow-list `sha256`. It is checked first: a mismatch is exit code 4 before any
process runs. A dirty or symlinked clone is refused too. Apply works on the branch `folio-migration/<date>`
with one commit per list (trailers `Folio-Op: task.migrate`, `Folio-Migration-Source` and
`Folio-Migration-Report`) and a final commit for `folio/migration-sources.json`. It writes nothing outside the
target clone and Folio's local state, and the source hash is checked again at the end (exit code 5 if it
changed). **Apply never pushes**; a later push goes through `folio sync --repo <path>` and its private-remote
check.

## Step 5: double-migration guard

A `fid` that is already in the clone (a `fid:` label, compared ignoring case, or an entry of
`folio/migration-sources.json`) is skipped as `already_migrated`. Running the same command again creates
nothing.

If an apply fails part-way, the tasks created so far stay uncommitted on the branch and the next run refuses
the dirty clone (exit code 4). **Do not re-run blindly:** review the branch, roll it back (Step 7), run a
fresh dry run and have the allow-list reviewed again if it changed.

## Step 6: verify the counts

For each list:

- the list's tasks by status in `backlog task list --json --project <list>` equal the migrated counts in the
  report;
- every `fid` is present exactly once;
- `backlog doctor` is clean.

```sh
cd <clone>
backlog task list --json --project <list>
backlog doctor
folio doctor
```

## Step 7: rollback

- **Branch not merged:** delete the local branch. Nothing was pushed, and nothing is ever force-pushed.

  ```sh
  git checkout main
  git branch -D folio-migration/<date>
  ```

- **Branch merged:** `git revert` the migration commits.

  ```sh
  git revert --no-edit <first-migration-commit>^..<last-migration-commit>
  ```

- The JSON workspace is untouched (its hash was checked before and after), so Folio 1.1.x can be started on
  it again at any time during the trial:

  ```sh
  chmod -R u+w <workspace>
  folio-1.1.2 ui
  ```

## Errors

| Code | Meaning |
| --- | --- |
| 1 | Usage: not exactly one of `--inventory`, `--dry-run`, `--apply`, or `--allow-list`, `--reviewed` or `--to` missing |
| 3 | Conflict: the clone is not ready (`backlog doctor` is not clean) |
| 4 | Refused: a bad allow-list, `--reviewed` not equal to the allow-list `sha256`, a dirty or symlinked clone, a refused Backlog.md argument |
| 5 | Storage: the source is unreadable or changed during the run, or git or Backlog.md failed |
| 7 | The Backlog.md binary is missing, or its version or hash is not the pin |
