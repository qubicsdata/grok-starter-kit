---
name: buildability-invariant
description: Phase boundary checklist invoked by sequencer-agent before finalising any phase. Every phase must leave the project buildable and deployable. Any failing check requires the phase to be split into smaller increments.
---

## Purpose

The buildability-invariant skill is invoked by sequencer-agent at every proposed phase boundary in the roadmap. Its job is to confirm that the state of the codebase after a phase completes is buildable and deployable. If any check fails, the phase must be split into smaller increments until all checks pass.

## The Invariant

> After every phase of the migration roadmap completes, the codebase must be in a state where it can be built, tested, and deployed using the project's normal CI/CD pipeline.

No phase may produce a "dark period" — a state where the codebase is neither fully old nor fully new and cannot be built or deployed.

## Checklist (run before finalising each phase boundary)

### Check 1: No broken imports at phase end

**Question:** Do the upgrade steps in this phase remove or rename any module, package, or API that is still imported or referenced elsewhere in the codebase at the end of the phase?

**PASS:** All removed or renamed APIs have been replaced within the same phase, OR the phase explicitly includes a migration step that introduces a compatibility shim before removing the old API.
**FAIL:** At least one import or reference in the codebase will be broken at phase completion.
**On FAIL:** Split the phase: (1) introduce the new API alongside the old one, (2) migrate all call sites, (3) remove the old API — each as separate phases or sub-steps.

---

### Check 2: No removed API contracts still referenced

**Question:** Does this phase remove any externally-facing API contract (REST endpoint, exported function, event type, database schema column) that is still referenced by another service, consumer, or test at the end of the phase?

**PASS:** All contract removals are preceded by deprecation notices and consumer migrations within earlier phases, OR the removed contract has no active consumers.
**FAIL:** At least one external consumer (service, test, downstream code) still references a contract being removed in this phase.
**On FAIL:** Add a preceding phase that deprecates the contract and migrates or removes consumers. The removal phase may only proceed after consumers are gone.

---

### Check 3: No partial migrations that block tests from running

**Question:** At the end of this phase, are there any files in a half-migrated state (e.g., mixed old and new import syntax, partial type annotation, half-converted module format) that would cause the test suite to fail to parse or run?

**PASS:** Either the migration within this phase is complete (all files converted), or a compatibility layer is in place that allows mixed states to coexist and the test suite runs against both.
**FAIL:** Mixed-state files cause parse errors, import failures, or test runner crashes at phase end.
**On FAIL:** Require the phase to either complete the migration fully or introduce a compatibility adapter. Document the adapter as a temporary measure with a removal step in a later phase.

---

### Check 4: CI pipeline remains executable

**Question:** Does this phase change the build toolchain, test runner, or CI configuration in a way that would cause the CI pipeline to fail or produce no output?

**PASS:** CI configuration is updated within the same phase as the toolchain change, and the new configuration is verified to produce a green build.
**FAIL:** The build toolchain changes but CI configuration is deferred to a later phase, leaving CI broken at phase end.
**On FAIL:** Include the CI configuration update in this phase before marking it complete.

---

### Check 5: Deployable to at least one environment

**Question:** At the end of this phase, can the codebase be deployed to at least the staging environment using the standard deployment process?

**PASS:** The deployment process works end-to-end for at least one environment at phase completion.
**FAIL:** The deployment process is broken (missing environment variables, changed secrets management approach not reflected in deploy config, changed container base image not yet pushed).
**On FAIL:** Include the deployment configuration update in this phase, or split to produce a smaller phase that maintains deployability.

---

## Output Format

sequencer-agent applies this skill at each proposed phase boundary and records the result in the roadmap:

```markdown
**Buildability invariant:** All 5 checks PASS — this phase leaves the project buildable and deployable.
```

Or if a split is required:

```markdown
**Buildability invariant:** Check 2 FAIL — removing the `/api/v1/users` endpoint in this phase while the mobile client still references it breaks the API contract. Phase split required: Phase 3a migrates the mobile client to `/api/v2/users`; Phase 3b removes the v1 endpoint.
```

## Rules

DO NOT allow a phase to be written to the roadmap if any buildability-invariant check fails without a corresponding split.

DO NOT skip this skill for any phase boundary. Every phase — including the first and last — must be checked.

DO NOT assume that "the developer will fix it before running CI." The roadmap must be executable as written. If it produces a broken state, it is a defective roadmap.
