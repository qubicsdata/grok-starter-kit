# ai-baseline shipped hooks

Installing the ai-baseline plugin activates deterministic governance in the consumer
project — no settings edits required. Claude Code reads `hooks.json` from this directory
at session start and wires the bundled scripts via `${CLAUDE_PLUGIN_ROOT}`.

## What ships

| Script | Event(s) | Purpose |
|--------|----------|---------|
| `scripts/session_gateway.py` | SessionStart | Inject the Accelerator "front door" context. |
| `scripts/audit_append.py` | Stop, SubagentStop | Append per-dispatch audit records (model + tokens from the transcript) to `.ai-baseline/audit.<date>.jsonl`. |
| `scripts/secret_guard.py` | PreToolUse (Write/Edit/Bash) | Deny a tool call carrying a high-confidence secret. |
| `scripts/cost_gate.py` | PreToolUse (Task) | Block an Opus dispatch when the session budget is exceeded. |

`scripts/_hooklib.py`, `scripts/scoreable_agents.py`, and `scripts/transcript_usage.py` are
shared helpers imported by the hooks above — they are not wired to events directly.
`scripts/pricing.json` holds the model rates the budget feed uses (USD per token).

## Canonical-vs-shipped contract

**Do not edit anything under `scripts/` by hand.** The canonical source of truth is
`tools/hooks/` in the accelerator repo (live there via `.claude/settings.json`) and, for
the pricing data, `pricing.json` at the accelerator root; this directory holds
byte-identical copies produced by:

```bash
python3 tools/sync-shipped-hooks.py
```

The fleet gate (`tools/check-hooks-drift.py`, validate.sh step 14) fails on any byte
difference, any canonical script or data file missing from this set, any stray script with no
canonical source, or a `hooks.json` that is missing, malformed, or missing one of the
four event types. Edit the canonical file, run the sync script, commit both.

## Dual-firing caveat

If a consumer repo ALSO wires these same scripts in its own `.claude/settings.json`,
**both registrations fire on every event** — duplicate audit records, double secret
scans, and a cost gate consulted twice. Don't do that. Installed consumers should rely
solely on this plugin's `hooks.json`; only the accelerator repo itself wires
`tools/hooks/` directly (and it does not install its own plugin copy on top).

## State location

Hooks resolve all state relative to the **consumer's project root** (via `_hooklib`'s
`$CLAUDE_PROJECT_DIR` → git-root resolution — the env var wins, so a shell cwd inside a
different git repo such as a worktree can never redirect state; never the plugin root).
Audit logs land in `<consumer-repo>/.ai-baseline/`, budgets and session state in
the consumer project — exactly as when the hooks run from `tools/hooks/` in this repo.
