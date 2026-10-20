---
name: api-resources
description: Run standalone resource modeling. Reads docs/api-design/api-design-intent.md and produces docs/api-design/api-design-resources.md.
argument-hint: ""
---

You are running a standalone resource modeling session.

## Entry Logic

1. Check whether `docs/api-design/api-design-intent.md` exists and is non-empty.
   - If it does not exist or is empty: block with "I need the API intent document before I can model resources. Run `/api-intent` first."
   - If it exists: inform the user: "Intent document found. Routing to resource-modeler."

2. Route to `resource-modeler`.

## After Resources Complete

Inform the user:

> Resource modeling complete. `docs/api-design/api-design-resources.md` has been written.
>
> Next steps:
> - Run `/api-schemas` to define request/response schemas.
> - Run `/api-design` to continue the full design lifecycle.

## Constraints

- Do not proceed to schema definition or any other phase automatically.
- If `api-design-intent.md` is absent, block and do not route to resource-modeler.
