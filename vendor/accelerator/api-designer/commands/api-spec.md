---
name: api-spec
description: Run standalone spec generation. Reads all three design documents, runs the api-readiness-checklist gate, then generates openapi.yaml.
argument-hint: ""
---

You are running a standalone spec generation session.

## Entry Logic

1. Check prerequisites:
   - `docs/api-design/api-design-intent.md` exists and is non-empty — if not: block with "Run `/api-intent` first."
   - `docs/api-design/api-design-resources.md` exists and is non-empty — if not: block with "Run `/api-resources` first."
   - `docs/api-design/api-design-schemas.md` exists and is non-empty — if not: block with "Run `/api-schemas` first."
   - If all three exist: inform the user: "All three design documents found. Routing to spec-generator."

2. Route to `spec-generator`.

## After Spec Complete

Inform the user:

> Spec generation complete. `openapi.yaml` has been written to the project root.
>
> Next steps:
> - Run `/api-review openapi.yaml` to review the spec for REST quality and completeness.
> - Run `/api-breaking-changes [old-spec] openapi.yaml` to detect breaking changes against a previous version.

## Constraints

- Do not write the spec without routing through spec-generator.
- Block if any prerequisite document is absent.
- The spec-generator will run the api-readiness-checklist gate — do not bypass it.

## Next step

After the spec is written, suggest (do not auto-run) the natural follow-on so the work flows on:

> Next: run `/api-review` to check the generated spec for REST quality, completeness, and security surface.

<!-- handoff: `/api-review` -->

