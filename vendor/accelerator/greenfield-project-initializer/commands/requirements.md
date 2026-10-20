---
description: Run standalone requirements elicitation. Extends an existing docs/requirements.md if present; creates it fresh if absent.
argument-hint: ""
---

You are running a standalone requirements elicitation session.

## Entry Logic

1. Check whether `docs/requirements.md` exists and is non-empty.
   - If it exists: read it and inform the user: "An existing requirements document was found. I will extend it with any missing sections rather than overwriting it."
   - If it does not exist: begin fresh requirements elicitation.

2. Route to `requirements-agent`.

## Behaviour

- If extending an existing document: `requirements-agent` should identify which of the 8 requirement topics are already covered and ask only about missing or incomplete topics. Present the additions as a diff (new content only) for confirmation before writing.
- If starting fresh: `requirements-agent` works through all 8 topics in order.

## After Requirements Complete

Inform the user:

> Requirements elicitation complete. `docs/requirements.md` has been written.
>
> Next steps:
> - If this is part of a full greenfield session, run `/greenfield` to continue to system design (or pick up where the session left off).
> - If you need only system design next, run `/sys-design`.
> - Run `/enrich docs/requirements.md` to inject production requirements from all installed plugins before planning? This adds a `## Production Requirements` section with each applicable plugin's mandatory constraints (traceable IDs). Opt-in — skip if you don't have enricher plugins installed or don't need it yet.

## Constraints

- Do not proceed to any other phase automatically — this command is standalone.
- Do not run security baseline or env promotion questions in this standalone command — those are handled in the full `/greenfield` flow. If the user asks, direct them to `/greenfield`.
- Do not overwrite existing confirmed sections without surfacing the change for user approval.
