# Approvals interface and local log (developer notes)

`folio/approvals.py` is the seam between Folio and whatever supplies pending human decisions: the first
`decision_provider()` of a plugin enabled in local config (WP-7). No provider ships in v1, because
Switchboard is frozen (see the README's "Switchboard freeze"). This is WP-5a: the interface, the local log
and the empty state's API. The inbox UI (`app.js`) is WP-5b.

## Pieces

| Name | Role |
| --- | --- |
| `DecisionProvider` | Base class: `pending()`, `show(id)` (`None` when unknown or no longer pending), `resolve(id, choice, note, remember)`. `name` keys the log; `label` is shown in dialogs. |
| `Approvals(provider=None, dialog=None, notifier=None, log=None)` | `status()`, `poll()`, `resolve(id, data, actor)`, `close()`. The dialog is `dialogs.ConfirmDialog`, reused. |
| `ApprovalLog(path=None)` | The local append-only trace. |

## Empty state

With no provider (the default) `GET /api/approvals` returns
`{"configured": false, "message": "No approvals source configured", "decisions": []}`. Resolve answers
404 `NO_APPROVALS_SOURCE` before any dialog opens or any local state is touched; the log object is not
even built.

## Resolving

`POST /api/approvals/<decision id>/resolve` sits behind the normal `/api` checks: the owner token, or a
browser session cookie plus its CSRF value. Then, in order:

1. `requested` must be `approve`, `deny` or `answer`.
2. `provider.show(id)`; `None` returns `no_longer_pending`.
3. `log.check()`; a refused log fails closed (500 `APPROVALS_LOG_REFUSED`) before anyone is asked.
4. The native dialog asks. Only an exact `approve` or `deny` click continues. A timeout, a close, an
   unavailable dialog or a malformed result is Cancel (409 `HUMAN_CONFIRMATION_CANCELLED`, or 503 when
   no dialog exists) and nothing reaches the provider. A second concurrent dialog is 409.
5. `provider.resolve(...)`, then one `resolution` record in the log. If the log write fails after the
   provider acted, the result carries a `warning` instead of an error.

Resolving writes nothing into a tasks repo, so its `git status` stays clean. The module must not import
`folio.notes`, `Store` or migration code, and never runs `task edit --notes` (M-6); a static test pins this.

## The log

`$XDG_STATE_HOME/folio/approvals.jsonl` (an absolute `XDG_STATE_HOME`, else
`~/.local/state/folio/approvals.jsonl`). JSON lines, never synced.

- Created 0600 (and its folders 0700) whatever the umask. Every open uses `O_NOFOLLOW` and
  `O_NONBLOCK`. A symlink, FIFO, folder, or a file with another owner or mode is refused and left
  unchanged (`ApprovalLogError`).
- Reads take a shared and writes an exclusive `flock`; a torn last line after a crash is skipped.
- Record types: `resolution` (provider, decision id, `approve`/`deny`, Folio task id or null),
  `notified` and `seen`. Never command text, notes or answers.
- `claim_notifications()` persists which decision ids were already notified, so a restart does not
  notify again.

## Tests

`tests/test_wp5_approvals_{log,resolve,http,static}.py` with helpers in `tests/wp5_support.py`. Run them
with `python3 -m unittest discover -s tests -p "test_wp5_approvals_*.py"`.
