# Backlog.md adapter (developer notes)

`folio/backlog/` is the only code that talks to Backlog.md. It is an internal library: no CLI command or
HTTP route uses it yet (WP-3 and WP-10 wire it in). Backlog.md is pinned to exactly **1.53.0**.

| Module | Role |
| --- | --- |
| `folio/backlog/tools.py` | `ToolResolver(environ, home, expected_sha256=None).backlog()` finds the binary and checks its sha256 and version. |
| `folio/backlog/guard.py` | The `onStatusChange` guard: a raw scan of `backlog/config.yml` and the task file. |
| `folio/backlog/adapter.py` | `BacklogClient(binary, repo, home)`: `list`, `view`, `create`, `edit`, `resolve`, `doctor`, `doc_create`, `doc_view`, `doc_update`. |

## Resolving the binary

`ToolResolver.backlog()` takes the path from `FOLIO_BACKLOG_BIN` in the environment mapping it was
given, else `$XDG_DATA_HOME/folio/tools/backlog-1.53.0/backlog` (`XDG_DATA_HOME` defaults to
`<HOME>/.local/share`). It never reads the process environment itself. The sha256 is compared
**before** the binary is run, then `backlog --version` must print exactly `1.53.0`. A missing,
unreadable, wrong-hash or wrong-version binary raises `ToolError`, exit code **7**.

Until WP-9 lands `folio/locks/backlog.lock.json`, the version is the constant in `tools.py` and the
expected sha256 is passed in by the caller (`None` means version check only). The lock cross-check test
`test_resolver_pin_matches_the_lock` is skipped with a reason naming WP-9; WP-9 removes that skip.

## Calling the binary

- Fixed argv, never a shell. The first word must be one of `init`, `task`, `doctor`, `config`, `doc`,
  `--version`; the Backlog.md web UI subcommand is never allowed.
- Every subprocess gets a minimal environment with `HOME` set to the temporary home given to the client.
- Values are checked before anything is spawned. A value that starts with `-`, contains NUL, or (titles)
  is longer than 79 characters or spans lines raises `RefusedValue`, exit **4**, and no process starts.
  Ids must look like `TASK-N` / `doc-N`; labels may not contain commas or whitespace.
- Writes go through the binary only. The adapter and guard never write under `backlog/`.

## Identity and `create`

`task create` prints a banner, not JSON, and its number is not authoritative across clones. `create`
adds a `fid:<16 hex>` label (generated, or the pre-assigned `fid=` for the outbox), then **re-lists** and
returns `Created(fid, id)` where `id` is the `TASK-N` that carries that label. `resolve(fid)` does the
same lookup; no match is `NOT_FOUND`, several matches `AMBIGUOUS_REFERENCE`. Callers may not put their
own `fid:` label on a task.

## The list cache

`list()` runs `task list --json` once and serves later calls from memory while the cache key is
unchanged. The key is the resolved git `HEAD` (loose and packed refs, linked worktrees) plus the name,
mtime and size of every entry in `backlog/{tasks,drafts,completed,archive}` and of `config.yml`. The
client's own writes drop the cache. Results are deep copies, so a caller cannot corrupt the cache.

## The `onStatusChange` guard (D-8)

Backlog.md 1.53.0 runs a per-task `onStatusChange` command with `sh -c` on a status change, and the key
survives edits. `edit` therefore runs `validate -> task view (for the file path) -> guard -> task edit`.
The guard refuses with exit **4** when `backlog/config.yml` or the task file contains the key in any
case (`onStatusChange`, `on_status_change`, `on-status-change`), anywhere in the file (front matter,
body, nested, quoted). An unreadable or over-8-MiB file is refused too (fail closed). The scan is raw on
purpose, so a task whose body only *mentions* the key is also refused. Reads (`list`, `view`) are not
guarded.

## `doctor`

`doctor()` fails (`DoctorFailed`, exit **3**) before running the binary when `remote_operations`,
`check_active_branches` or `auto_commit` is on in `backlog/config.yml`, or the guard finds the key in the
config. Otherwise it runs `backlog doctor` and fails on a non-zero exit.

## Exit codes

| Code | Meaning |
| --- | --- |
| 2 | `NOT_FOUND`, `AMBIGUOUS_REFERENCE` |
| 3 | `CONFLICT` (doctor failed) |
| 4 | `VALIDATION`: refused value or guard refusal |
| 5 | `STORAGE`: binary failed, invalid JSON, unexpected document |
| 7 | `ToolError`: binary missing, wrong sha256 or wrong version |

## Tests

```
python3 -m unittest discover -s tests -v
```

The `tests/test_wp2_backlog_*.py` files use a recording fake binary where possible and the real binary
for the round-trip, doctor and sentinel tests. The contract suite and the real-binary tests need
`FOLIO_BACKLOG_BIN` set to the 1.53.0 binary at run time; without it they fail (not skip) on purpose.
Set `FOLIO_BACKLOG_CONTRACT=skip` to opt out explicitly. Never write the variable into a repo file.
