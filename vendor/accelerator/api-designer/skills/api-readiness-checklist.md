---
name: api-readiness-checklist
description: Gate enforcer. Invoke before spec-generator writes to disk. Checks 7 required items and blocks spec generation if any fail. Also invoke at any phase transition where a prerequisite artifact is required.
---

## Purpose

The api-readiness-checklist is a hard gate that must fully pass before `spec-generator` writes `openapi.yaml`. It checks 7 items against the current state of the design artifacts on disk. If any item is incomplete, spec generation is BLOCKED and the user is routed back to the owning agent.

## The 7 Gate Items

Check each item by reading the relevant file. Do not infer — read the file. Report each as PASS or FAIL with a specific reason.

| # | Item | How to verify | Owning agent if failed |
|---|------|--------------|------------------------|
| 1 | `docs/api-design/api-design-intent.md` exists and is non-empty | File is present and has content beyond the header line | `intent-agent` |
| 2 | Security contract is complete | `## Security Contract` section is present in `api-design-intent.md` with all 5 security questions answered; any "none" answer has an explicit rationale (not just "it's internal") | `security-contract-agent` |
| 3 | `docs/api-design/api-design-resources.md` exists and is non-empty | File is present with at least one resource defined | `resource-modeler` |
| 4 | No verb-shaped paths remain unresolved | No entry in `api-design-resources.md` is marked `STATUS: PENDING-RESOLUTION` | `resource-modeler` |
| 5 | `docs/api-design/api-design-schemas.md` exists and is non-empty | File is present with at least one schema defined | `schema-agent` |
| 6 | Canonical error schema is defined | `api-design-schemas.md` contains an `## Error Schema` section with at least one error shape defined | `schema-agent` |
| 7 | Versioning strategy is declared | `api-design-intent.md` contains a `## Versioning Strategy` section with an explicit strategy choice (not "TBD" or empty) | `versioning-advisor` or user input |

A spec-generator write is BLOCKED until all 7 items PASS. No item auto-passes — each must be verified by reading the relevant file.

## Output Format

```
## API Readiness Checklist

| # | Item | Status | Action Required |
|---|------|--------|-----------------|
| 1 | Intent document | PASS | — |
| 2 | Security contract complete | FAIL | Run /api-security to capture the security contract |
| 3 | Resource model | PASS | — |
| 4 | No unresolved verb paths | PASS | — |
| 5 | Schema inventory | PASS | — |
| 6 | Canonical error schema | FAIL | Run /api-schemas — schema-agent must define the ## Error Schema section |
| 7 | Versioning strategy declared | PASS | — |

**Result: BLOCKED — 2 items failed. Resolve the above before spec generation can proceed.**
```

Or, if all pass:

```
## API Readiness Checklist

All 7 items: PASS

**Result: CLEARED — spec generation may proceed.**
```

## Routing on Failure

When one or more items fail, the orchestrator routes the user back to the owning agent for that item. This skill does not fix the failures — it identifies them and names the owning agent.

## Rules

- DO NOT allow spec generation to proceed if any of the 7 items is FAIL.
- STOP and surface a clear error message if the checklist cannot read a required file — do not default to PASS on file-read errors.
- DO NOT consider an item PASS if the relevant section exists but contains only placeholder text ("TBD", "N/A", empty bullet) — mark FAIL and route back to the owning agent.
- DO NOT skip item 2 (security contract) or item 7 (versioning strategy) under any circumstances — they are never optional.
- Item 4 (no unresolved verb paths) PASSES only if there are zero `STATUS: PENDING-RESOLUTION` entries in `api-design-resources.md`.
