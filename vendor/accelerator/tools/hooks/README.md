# Accelerator hooks

Stdlib-only (Python 3.8+) hook scripts wired in `.claude/settings.json`. Shared helpers
live in `_hooklib.py`. Hooks are **fail-open**: on any error they write a warning to
stderr and exit 0, so a broken hook never wedges a session — with ONE deliberate
exception: `cost_gate.py` is **fail-closed (exit 2) on the Opus path**, because a broken
gate must not silently allow unbounded Opus spend.

| Hook | Event(s) | Purpose |
|------|----------|---------|
| `session_gateway.py` | SessionStart | Inject the Accelerator "front door" so the fleet is present from turn one. |
| `audit_append.py` | Stop, SubagentStop | Append a per-dispatch audit record — model + tokens recovered from the session transcript — to `.ai-baseline/audit.<date>.jsonl`. Also accrues the record's USD cost into `.ai-baseline/budget.json` (feeds `cost_gate.py`) and fills null `app`/`feature` from context.json or git. |
| `cost_gate.py` | PreToolUse (Task) | Block an Opus dispatch when the session budget is exceeded. `limit_usd` null/absent = measurement mode (never blocks). |
| `secret_guard.py` | PreToolUse (Write/Edit/Bash) | Deny a tool call carrying a high-confidence secret. |

## Budget feed & the cost gate

`audit_append.py` is the sole writer of `.ai-baseline/budget.json`. After appending each
audit record it computes the record's incremental USD cost — rates from the data
file `pricing.json` at the suite root (`accelerator.pricing_table_file` in the kit
config; the one hook-side source of truth, mirroring
`cost-monitor/skills/pricing-table.md`), with `cache_read` tokens EXCLUDED per
`benchmarks/BENCHMARK-CONVENTIONS.md` §1 (`transcript_usage.py` already keeps them out of
`tokens_in`) — and adds it to `spent_usd`. The per-session transcript cursor makes every
record incremental, so re-running over the same transcript never double-counts.
Concurrency-safe: an advisory flock on `.ai-baseline/.lock` serializes overlapping
Stop/SubagentStop processes (parallel subagent dispatch, dual registration), and both
budget.json and the cursor are written atomically (temp + rename) so `cost_gate.py`
never reads a torn file. Segments spanning more than one model tier are costed per turn
model (`transcript_usage` `by_model` buckets), never all at the last turn's rate.

```json
{"limit_usd": null, "spent_usd": 0.014175}
```

- File absent → created as `{"limit_usd": null, "spent_usd": <increment>}`.
- `limit_usd` is **never** written by the hook — set it by hand (or via cost-monitor) to
  arm the gate. `null` (or absent) means "measure but never block".
- `cost_gate.py` reads the same file on every Opus `Task` dispatch: numeric `limit_usd`
  with `spent_usd >= limit_usd` denies the dispatch; null/absent limit always allows.
- An unparseable budget.json is left untouched (spend update skipped) so a hand-edited
  limit is never clobbered; on the gate side it still fail-closes the Opus path.

### Pricing data (`pricing.json`)

```json
{"unit": "usd_per_token",
 "models": {"<model id>": {"input": <rate>, "output": <rate>}},
 "tiers": {"opus": "<model id>", "sonnet": "<model id>", "haiku": "<model id>"},
 "default": "<model id>"}
```

`_hooklib.model_pricing()` looks up an exact model id, then the first tier name found in
the id, then `default` (Sonnet, a conservative estimate). The file is read once per hook
process: `pricing.json` beside `_hooklib.py` (the shipped copy in
`ai-baseline/hooks/scripts/`), else at the suite root two levels up (these canonical
scripts). Change rates in the suite-root file only, then run
`python3 tools/sync-shipped-hooks.py`; `tools/check-hooks-drift.py` fails on a stale
shipped copy and `tools/check-model-ids.py` on tiers that differ from
`tools/model-ids.json`. A missing or malformed file raises `_hooklib.PricingError` when a
cost is computed (never at import, so the other hooks keep working): `audit_append.py`
still writes the audit record, leaves budget.json untouched and warns on stderr.

## Attribution fallback (app/feature)

Audit records used to carry `app`/`feature` null unless `/context set` had written
`.ai-baseline/context.json`. `audit_append.py` now fills **null fields only**, in order:

1. `.ai-baseline/context.json` (`{"app": ..., "feature": ...}`) — explicit context wins.
2. Git fallback: `app` ← `git remote get-url origin` basename (`.git` stripped),
   `feature` ← `git branch --show-current`.

Both git calls run with `cwd=<repo root>` and the usual fail-open guards — no remote/no
branch/no git leaves the fields null. `plugin` is transcript-owned and never git-filled.

## Operational footguns (learned the hard way — read before editing hooks)

These are the highest-severity infra lessons from the 2026-06-22 horizontal-layer session
(its notes are not vendored in this kit). They live here, next to
the hooks, because this is where someone editing a hook will actually look.

### 1. Hook commands MUST be cwd-independent — use `$CLAUDE_PROJECT_DIR`, never a relative path

A hook wired as `python3 tools/hooks/x.py` works **only** when the shell cwd is the repo
root. The moment cwd drifts into a subdirectory, the script 404s, exits 2, and (for a
blocking event) **denies every hooked tool — Bash, Write, Edit, Task — with no in-band
recovery.** You cannot edit your way out, because editing is itself blocked. Always wire as:

```json
"command": "python3 $CLAUDE_PROJECT_DIR/tools/hooks/x.py"
```

In-script, resolve the repo root via `_hooklib.get_repo_root()` (`$CLAUDE_PROJECT_DIR` →
git → cwd — the env var wins so a cwd inside a different git repo, e.g. a worktree, can
never redirect state reads/writes away from the session's project), never `Path.cwd()`.

### 2. `settings.json` hook config is cached at session start — it does NOT hot-reload

Editing `.claude/settings.json` mid-session has **no effect on the live session**. The fix
lands next session (or after an explicit reload/restart). Plan accordingly: do not assume a
settings edit takes effect immediately, and do not debug a "hook didn't change" symptom by
re-editing settings in the same session.

### 3. A git worktree is the escape hatch from a cwd-induced hook lock

If a cwd-relative hook (footgun #1) has locked the session, switch into a git worktree: it
gives a fresh, valid repo-root cwd where relative hooks resolve again. From there you operate
on the main repo via absolute paths or `git -C <main-repo>`. This lever is why footgun #1 is
recoverable at all.

## Shipping

These scripts are the **canonical source**; the ai-baseline plugin ships byte-identical
copies in `ai-baseline/hooks/scripts/` (wired for installed consumers via
`ai-baseline/hooks/hooks.json` + `${CLAUDE_PLUGIN_ROOT}`). After editing any hook here, run:

```bash
python3 tools/sync-shipped-hooks.py
```

and commit both copies. The fleet gate enforces this: `tools/check-hooks-drift.py`
(validate.sh step 14) fails on any byte divergence, missing shipped script, or invalid
`hooks.json`. Never edit the shipped copies directly — see `ai-baseline/hooks/README.md`.

## Testing

Hook logic with non-trivial parsing (e.g. `transcript_usage.py`) has stdlib tests under
`tools/tests/`. Run them directly: `python3 tools/tests/test_<name>.py`. The fleet gate
(`bash tools/validate.sh`) also exercises the shipped hooks end-to-end:
`tools/check-installed-runtime.py` (step 15) runs every hook against a fake consumer
repo, and step 13 runs the whole `tools/tests/` suite via `tools/run-unit-tests.py`.
