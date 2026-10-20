---
name: api-security
description: Run standalone security contract capture. Reads docs/api-design/api-design-intent.md and appends ## Security Contract to it.
argument-hint: ""
---

You are running a standalone security contract capture session.

## Entry Logic

1. Check whether `docs/api-design/api-design-intent.md` exists and is non-empty.
   - If it does not exist or is empty: block with "I need the API intent document before I can capture the security contract. Run `/api-intent` first."
   - If it exists: inform the user: "Intent document found. Routing to security-contract-agent."

2. Route to `security-contract-agent`.

## After Security Complete

Inform the user:

> Security contract captured. `## Security Contract` section has been appended to `docs/api-design/api-design-intent.md`.
>
> Next steps:
> - Run `/api-spec` to generate the OpenAPI spec (requires all 7 readiness checklist items to pass).
> - Run `/api-design` to continue the full design lifecycle.

## Constraints

- Do not proceed to spec generation automatically.
- Block if `api-design-intent.md` is absent.
