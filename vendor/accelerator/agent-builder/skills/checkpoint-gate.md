---
name: checkpoint-gate
description: Use at Gate 1 (post-design, pre-generate) and Gate 2 (pre-publish) — runs the structured reflection exercise and writes the output to the session plan file before the next phase is allowed to proceed
---

# Checkpoint Gate

Checkpoint gates are mandatory reasoning exercises, not confirmations. The agent must answer the gate questions in writing before the next phase unlocks. Outputs are appended to the session plan file.

## Session Plan File

The session plan file is created by builder-orchestrator at `<output-dir>/.builder-session.md` at the start of every `/build-agent` invocation. It accumulates:
- Intake scores and routing table
- Knowledge patch summary (from runtime-knowledge-fetch)
- Gate 1 output
- Gate 2 output
- Specialist panel scorecard

Always append to this file — never overwrite it.

## Checkpoint Grammar (machine-parsed contract)

Checkpoints are appended as list items directly under `## Checkpoints` (insert into
that section — do not append to end-of-file), one per line:

    - <token> — <ISO timestamp>

Canonical token order for generate/workshop mode:
`intake complete` → `domain-research complete` → `gate-1 cleared` → `critic pass` →
`gate-2 cleared` → `efficacy journaled` → `publish complete`.
`efficacy journaled` is **required at publish** and is journaled by the orchestrator
after gate-2 clears, *before* the publisher runs (loop-closure spec 2026-07-03).
`efficacy skipped` is accepted ONLY in an installed context with no feedback writer;
in-repo it is a publish BLOCK. Audit mode records `intake complete` only.
`tools/check-builder-session.py` parses exactly these tokens in exactly this order — a
misspelled or out-of-order token blocks the publisher. Never invent new tokens.

## Gate 1 — Post-Design, Pre-Generate

Run this gate after the user approves the design and before generate-agent is invoked.

Answer each question in 2–4 sentences:

1. **Assumption risk:** What assumptions in this design could be wrong? Which, if wrong, would cause silent failure?
2. **Failure modes:** What would make this agent fail in a way the user wouldn't notice?
3. **Routing justification:** Is the model routing appropriate for the complexity of what's being generated? Would any agent benefit from a higher tier?

Append to `.builder-session.md`:

```markdown
## Gate 1 — Post-Design Reflection
[timestamp]

### Assumption risk
[answer]

### Failure modes
[answer]

### Routing justification
[answer]

Gate 1: CLEARED
```

## Gate 2 — Pre-Publish

Run this gate after the specialist panel has reported and before publisher-agent writes files to disk.

Answer each question:

1. **Panel blockers:** Does the specialist panel report contain any unresolved `fail` items? List them. If yes, Gate 2 does not clear.
2. **API safety:** Did the runtime-knowledge-fetch knowledge patch flag any breaking changes that affect this plugin? If yes, list them and confirm the plugin accounts for them. A `### Model-ID Drift` block in the knowledge patch must be listed here and acknowledged by the user before the gate clears.
3. **Version correctness:** Is the version bump (patch/minor/major) appropriate for the changes being published?

Append to `.builder-session.md`:

```markdown
## Gate 2 — Pre-Publish Reflection
[timestamp]

### Panel blockers
[list unresolved fail items, or "None"]

### API safety
[breaking changes flagged, or "None flagged"]

### Version correctness
[bump type and justification]

Gate 2: [CLEARED / BLOCKED — reason]
```

## STOP

DO NOT allow publisher-agent to write files to disk if Gate 2 status is BLOCKED. A blocked gate is a hard stop. Surface the blocking reason to the user and wait for resolution.
