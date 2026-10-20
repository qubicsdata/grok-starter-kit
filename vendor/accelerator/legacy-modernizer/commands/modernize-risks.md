---
name: modernize-risks
description: Standalone risk scoring — reads docs/modernization/inventory.md and produces docs/modernization/risk-register.md. Blocks with a clear error if the inventory is absent.
---

You are running a standalone risk scoring phase. Invoke `risk-scorer` directly.

## Entry Logic

1. Check whether `docs/modernization/inventory.md` exists and is non-empty.
   - If it does not exist: stop immediately and report: "docs/modernization/inventory.md is required but was not found. Run /modernize-inventory first to produce the codebase inventory, then re-run /modernize-risks."
   - If it exists but is empty: stop immediately and report: "docs/modernization/inventory.md exists but is empty. Re-run /modernize-inventory to produce a valid inventory, then re-run /modernize-risks."

2. If the inventory exists and is non-empty: dispatch `risk-scorer` with the path `docs/modernization/inventory.md`.

## Dispatch

Route to `risk-scorer` with:
- `docs/modernization/inventory.md` as the input document
- No orchestrator session context — this is a standalone invocation

## Constraints

- Do not invoke `modernize-orchestrator` — this command bypasses the orchestrator
- Do not enforce phase gates beyond the inventory prerequisite check above
- Do not write any files inline — `risk-scorer` handles all writes after user confirmation
- Do not generate any risk assessments inline — that is `risk-scorer`'s job
