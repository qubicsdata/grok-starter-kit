---
description: Run standalone tech stack selection. Requires docs/system-design.md to exist. Proposes ≥2 options per layer with tech-radar classification and writes docs/tech-stack.md after user confirmation.
argument-hint: ""
---

You are running a standalone tech stack selection session.

## Entry Logic

1. Check whether `docs/system-design.md` exists and is non-empty.
   - If it does NOT exist: respond with:
     > BLOCKED: `docs/system-design.md` is required before tech stack selection can proceed. Run `/sys-design` first.
   - Stop here — do not proceed.

2. If `docs/system-design.md` exists: route to `tech-stack-agent`.

3. Check whether `docs/tech-stack.md` already exists.
   - If it exists: inform the user: "An existing tech stack document was found. Do you want to revise specific layers or start the selection fresh? (revise / restart)"
   - On "revise": `tech-stack-agent` reads the existing doc and presents only the layers the user wants to revisit.
   - On "restart": `tech-stack-agent` proceeds through all layers from scratch.

## After Tech Stack Complete

Inform the user:

> Tech stack selection complete. `docs/tech-stack.md` has been written.
>
> Pending ADRs identified: [list from tech-stack-agent output, or "none"]
>
> Deferred decisions (must be resolved before scaffold): [list or "none"]
>
> Next steps:
> - Run `/adr "[decision statement]"` to capture pending technology decisions.
> - Run `/scaffold` when all decisions are resolved to generate the repository scaffold.
> - Or run `/greenfield` to continue the full lifecycle.

## Constraints

- Do not proceed without `docs/system-design.md` — no exceptions.
- Do not generate system design content — that is sys-design-agent's concern.
- Do not write to disk without explicit user confirmation.
- Do not auto-advance to scaffold — this command is standalone.
- Do not allow the session to end with deferred tech decisions without flagging them clearly.
