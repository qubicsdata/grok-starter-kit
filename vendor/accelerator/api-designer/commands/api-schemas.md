---
name: api-schemas
description: Run standalone schema definition. Reads docs/api-design/api-design-resources.md and produces docs/api-design/api-design-schemas.md.
argument-hint: ""
---

You are running a standalone schema definition session.

## Entry Logic

1. Check prerequisites:
   - `docs/api-design/api-design-intent.md` exists and is non-empty — if not: block with "Run `/api-intent` first."
   - `docs/api-design/api-design-resources.md` exists and is non-empty — if not: block with "Run `/api-resources` first."
   - If both exist: inform the user: "Intent and resource documents found. Routing to schema-agent."

2. Route to `schema-agent`.

## After Schemas Complete

Inform the user:

> Schema definition complete. `docs/api-design/api-design-schemas.md` has been written.
>
> Next steps:
> - Run `/api-security` to capture the security contract.
> - Run `/api-design` to continue the full design lifecycle.

## Constraints

- Do not proceed to security or spec generation automatically.
- Block if either prerequisite document is absent.
