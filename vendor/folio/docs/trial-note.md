# Trial and retirement note

Folio on Backlog.md is a trial. It earns its place by being used, and if it is not used it is removed without
any data work, because the tasks live in plain Backlog.md repositories that work without Folio.

Never run `backlog browser`, during the trial or after it. See the [security model](local-security.md).

## The trial

- **Length:** 4 weeks.
- **Start:** go-live on the laptop and on the box, that is, once the public install works and the migration
  has been applied.
- **Instrument:** a local usage counter on each machine (WP-14), `$XDG_STATE_HOME/folio/usage.json` (default
  `~/.local/state/folio/usage.json`, mode 0600). It holds integer per-day counts for `view.cross_list`,
  `view.attention`, `view.approvals`, `approval.resolved`, `brief.cli` and `ollama.accept`, and nothing else:
  no ids, titles or content. Only authenticated requests from a person count as views; a CLI or agent request
  is not a view. There is no telemetry and nothing leaves the machine. Each week, on each machine, run:

  ```sh
  folio usage report
  ```

  It prints one row per ISO week with every key (`--since YYYY-MM-DD` limits it; `--format table` prints a
  table). Read the totals yourself. Deleting the file resets the counts.

## Keep Folio if any one of these holds

| Evidence | Measure |
| --- | --- |
| The cross-list or attention views are used on at least 2 distinct days per week in at least 3 of the 4 weeks | days with `view.cross_list` or `view.attention` |
| Approvals are resolved through Folio at least 3 times per week in at least 3 of the 4 weeks | `approval.resolved` |
| `folio brief` is used by agents at least 10 times per week | `brief.cli` |

The weekly report sums whole weeks, so count the distinct days for the first line from the file itself (one
entry per day). The second line cannot fire while no decision provider ships (see
[approvals](../README.md#approvals-local-only)); in practice the decision rests on the views and the brief.

## Retire Folio if none holds

Fall back to plain Backlog.md: its command line and its stdio MCP server for agents, and **no Backlog.md web
board** on either machine. Humans use the terminal view:

```sh
backlog task list --plain
```

### Retirement steps (no data work)

1. Flush the create outbox for each registered clone, then stop Folio:

   ```sh
   folio sync --repo <path>
   folio server-stop
   ```

2. Uninstall the tool:

   ```sh
   uv tool uninstall folio-workspace
   ```

3. Delete Folio's local state. This removes the counts, the approvals log and the outbox, so do it only after
   step 1:

   ```sh
   rm -r "${XDG_STATE_HOME:-$HOME/.local/state}/folio"
   ```

4. The tasks repositories stay as they are. The `fid:` labels are ignored by Backlog.md and may stay; to
   remove them, edit them out with `backlog task edit`.
5. The Folio 1.1.x JSON backup stays read-only and archived. The migration never changed it.

The downloaded Backlog.md binary lives in `$XDG_DATA_HOME/folio/tools/` (default `~/.local/share/folio/tools/`)
and the local config in `$XDG_CONFIG_HOME/folio/`. Delete them by hand after uninstalling if you want them gone.

## Recording the decision

At the end of week 4, write the totals and the keep or retire decision into the tasks repository as a normal
task, using an alias for any person or client. Do not paste task titles, client names or paths into the note.
