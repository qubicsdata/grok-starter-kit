# ai-baseline

Mandatory baseline plugin for every Claude Code agent build. Injected automatically by agent-builder into every generated plugin.

## What it provides

- **Audit trail** — append-only JSONL log of every agent invocation with full attribution (app, feature, session, command chain)
- **PII scrub** — pre-output gate that detects and redacts PII before any agent emits output
- **Cost gate** — pre-Opus gate that blocks invocations exceeding the session budget
- **Context manager** — sets the `app` and `feature` labels stamped on every audit entry

## Installation

Injected automatically by agent-builder. For existing plugins, copy `skills/baseline-enforcer.md` into the plugin's `skills/` directory and add `audit-trail-agent` to the plugin's agent list.

## Commands

- `/baseline-init` — first-run bootstrap: seed attribution, budget, and session identity, then prove the hooks fire
- `/context set app=<name> feature=<name>` — set current app and feature label
- `/context show` — print resolved app + feature with source
- `/context clear` — remove context.json, revert to git fallback
- `/accelerator "<goal>"` — route a natural-language goal to the most relevant plugin command(s) across all 25 plugins

## First-run bootstrap

Run `/baseline-init` once after installing (and any time you want to refresh). It seeds
`.ai-baseline/context.json` (audit attribution from git remote/branch, overridable),
`.ai-baseline/budget.json` (null limit = measure only; a number arms the Opus cost gate —
existing `spent_usd` is preserved), and `.ai-baseline/.session` (stable session UUID). It
then runs `hooks/scripts/self_check.py`, which exercises every shipped hook in a throwaway
repo and prints a PASS/FAIL table — proof the hooks fire on *your* machine, not just in the
dev repo. The dev-repo CI equivalent is `tools/check-installed-runtime.py` (fleet gate
step 15), which simulates a fresh consumer end to end against the shipped scripts.

## Audit log

All entries land in date-sharded `.ai-baseline/audit.<YYYY-MM-DD>.jsonl` files at the project root. See `skills/audit-schema.md` for the field contract.

## Author

<your-name> (you@example.com)

## Spec Enrichment

Run `/enrich <spec-path>` after writing a spec and before planning. It discovers every installed plugin's `agents/spec-enricher.md`, dispatches them in parallel against the spec, and injects a `## Production Requirements` section with each applicable plugin's mandatory requirements (each traceable by a plugin-prefixed ID).

- Plugins decide their own relevance — an enricher that doesn't apply abstains (`NOT_APPLICABLE`) and contributes nothing.
- Idempotent: re-running `/enrich` replaces the existing `## Production Requirements` section rather than duplicating it.
- If no enrichers are installed, the spec is left unchanged.

The contract every enricher follows lives in `skills/spec-enricher-spec.md`. agent-builder injects a tailored enricher into every plugin it generates, so installed plugins contribute their production discipline automatically.
