---
description: Run standalone scaffold generation. Requires docs/tech-stack.md. Runs greenfield-checklist gate and security-baseline gate before generating scaffold, then invokes ci-designer for CI configuration.
argument-hint: ""
---

You are running a standalone scaffold generation session.

## Entry Logic

1. Check whether `docs/tech-stack.md` exists and is non-empty.
   - If it does NOT exist: respond with:
     > BLOCKED: `docs/tech-stack.md` is required before scaffold generation. Run `/tech-stack` first.
   - Stop here — do not proceed.

2. Apply the `greenfield-checklist` skill directly (this command is standalone — the orchestrator is not involved). All 6 items must pass before scaffold proceeds.
   - Items 1, 4, 5 auto-pass if the corresponding files exist and are non-empty.
   - Items 2, 3, 6 require section verification.

3. If the checklist result is BLOCKED:
   - Present the checklist result table to the user.
   - For each failed item, name the owning agent/command and ask the user to address it.
   - Do not proceed to scaffold until a re-run of the checklist passes all 6 items.

4. If any security baseline answers are DEFERRED: re-ask those questions now (using `security-baseline` skill), collect answers, and update `docs/requirements.md` via `requirements-agent` append mode before proceeding.

5. When all 6 checklist items pass: route to `repo-scaffold-agent`.

## After Scaffold Complete

Immediately route to `ci-designer` for CI configuration.

After CI configuration is complete, present:

> Scaffold and CI configuration complete.
>
> ### Files Written
> [file list from repo-scaffold-agent and ci-designer]
>
> ### Open Items
> [Any deferred items or X.Y.Z version placeholders that need manual pinning]
>
> ### Next Steps
> 1. Pin any dependency versions marked X.Y.Z to current stable releases
> 2. Populate `.env.example` values in your secrets manager
> 3. Enable branch protection on your main branch
> 4. Run the quick-start commands from README.md to verify local setup

## Constraints

- Do not skip the greenfield-checklist gate — it must pass before scaffold generation.
- Do not skip the security-baseline re-check for deferred items — they must be answered.
- Do not write any scaffold files without explicit user confirmation of the file manifest.
- Do not write CI config without explicit user confirmation.
- Do not generate application logic — scaffold only.
- Do not assume the CI provider — ci-designer must ask first.

## Next step

After the scaffold and CI config are written, suggest (do not auto-run) the natural follow-ons so the new repo starts safe:

> Next: run `/secrets-audit` to confirm no secrets landed in the scaffold, and `/pipeline` to review the generated CI for safety.

<!-- handoff: `/secrets-audit` and `/pipeline` -->

