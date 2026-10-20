---
description: Run standalone system design. Requires docs/requirements.md to exist. Proposes ≥2 architecture shapes with trade-offs and writes docs/system-design.md after user confirmation.
argument-hint: ""
---

You are running a standalone system design session.

## Entry Logic

1. Check whether `docs/requirements.md` exists and is non-empty.
   - If it does NOT exist: respond with:
     > BLOCKED: `docs/requirements.md` is required before system design can proceed. Run `/requirements` first.
   - Stop here — do not proceed.

2. If `docs/requirements.md` exists: route to `sys-design-agent`.

3. Check whether `docs/system-design.md` already exists.
   - If it exists: inform the user: "An existing system design document was found at `docs/system-design.md`. Do you want to revise it or start fresh? (revise / restart)"
   - On "revise": `sys-design-agent` reads the existing doc and presents delta options.
   - On "restart": `sys-design-agent` proceeds from scratch.

## After System Design Complete

Inform the user:

> System design complete. `docs/system-design.md` has been written.
>
> Pending ADRs identified: [list from sys-design-agent output, or "none"]
>
> Next steps:
> - Run `/tech-stack` to continue to tech stack selection.
> - Run `/adr "[decision statement]"` to capture any pending architectural decisions.
> - Or run `/greenfield` to continue the full lifecycle from the current state.

## Constraints

- Do not proceed without `docs/requirements.md` — no exceptions.
- Do not generate tech-stack recommendations — that is tech-stack-agent's concern.
- Do not write to disk without explicit user confirmation.
- Do not auto-advance to tech stack — this command is standalone.
