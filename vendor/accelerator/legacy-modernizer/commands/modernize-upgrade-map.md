---
name: modernize-upgrade-map
description: Standalone upgrade mapping — reads docs/modernization/inventory.md and docs/modernization/risk-register.md, then produces docs/modernization/upgrade-map.md. Blocks with a clear error if either prerequisite is absent.
---

You are running a standalone upgrade mapping phase. Invoke `upgrade-map-agent` directly.

## Entry Logic

1. Check whether `docs/modernization/inventory.md` exists and is non-empty.
   - If absent or empty: stop and report: "docs/modernization/inventory.md is required but was not found or is empty. Run /modernize-inventory first."

2. Check whether `docs/modernization/risk-register.md` exists and is non-empty.
   - If absent or empty: stop and report: "docs/modernization/risk-register.md is required but was not found or is empty. Run /modernize-risks first."

3. If both documents exist and are non-empty: dispatch `upgrade-map-agent` with both document paths.

## Dispatch

Route to `upgrade-map-agent` with:
- `docs/modernization/inventory.md`
- `docs/modernization/risk-register.md`
- No orchestrator session context — this is a standalone invocation

## After upgrade-map-agent Completes

Once upgrade-map-agent has confirmed writing `docs/modernization/upgrade-map.md`:

1. If the upgrade-map.md contains a "Pending ADR Decisions" section, present each decision statement to the user.
2. For each pending decision, offer: "You can capture this as an ADR with: `/adr "[decision statement]"`"
3. If there are no pending decisions, confirm completion with no further prompts.

## Constraints

- Do not invoke `modernize-orchestrator` — this command bypasses the orchestrator
- Do not enforce phase gates beyond the two prerequisite checks above
- Do not write any files inline — `upgrade-map-agent` handles all writes after user confirmation
- Do not generate technology assessments or recommendations inline — that is `upgrade-map-agent`'s job
