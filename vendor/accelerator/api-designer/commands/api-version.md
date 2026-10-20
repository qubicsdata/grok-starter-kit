---
name: api-version
description: Get a versioning strategy recommendation tailored to your API and its consumers.
argument-hint: ""
---

You are running a standalone versioning advice session.

## Entry Logic

1. Check whether `docs/api-design/api-design-intent.md` exists.
   - If it exists: inform the user: "Intent document found. The versioning recommendation will be tailored to your API context."
   - If it does not exist: the versioning-advisor will ask the user for a brief API description.

2. Route to `versioning-advisor`.

## After Versioning Advice Complete

Inform the user:

> Versioning advice complete.
>
> To record the chosen strategy, add a `## Versioning Strategy` section to `docs/api-design/api-design-intent.md` with your chosen strategy and rationale. This is required by the api-readiness-checklist (item 7) before spec generation can proceed.

## Constraints

- Do not write any file. The versioning-advisor outputs to stdout only.
- Do not route to any other agent after versioning-advisor completes.
