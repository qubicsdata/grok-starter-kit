---
name: greenfield-checklist
description: Gate enforcer. Invoke before scaffold generation begins. Checks 6 required items and blocks scaffold if any are unanswered or missing. Also invoke at any phase transition where a prerequisite artifact is required.
---

## Purpose

The greenfield-checklist is a hard gate that must pass before `repo-scaffold-agent` is invoked. It checks 6 items against the current state of the project artifacts and session. If any item is incomplete, scaffold generation is BLOCKED and the user is routed back to the owning agent.

## The 6 Gate Items

Check each item by reading the relevant file or session state. Report each as PASS or FAIL with a reason.

| # | Item | How to verify | Owning agent if failed |
|---|------|--------------|------------------------|
| 1 | `docs/requirements.md` exists and is non-empty | File exists and has content beyond the header | `requirements-agent` |
| 2 | Environment promotion strategy is documented | `## Environment Promotion Strategy` section present and non-empty in `docs/requirements.md` | `requirements-agent` (append mode) |
| 3 | Security baseline is fully answered | `## Security Baseline` section present with all 6 questions answered in `docs/requirements.md` | `security-baseline` skill → `requirements-agent` append |
| 4 | `docs/system-design.md` exists and is non-empty | File exists and has content beyond the header | `sys-design-agent` |
| 5 | `docs/tech-stack.md` exists and is non-empty | File exists and has content beyond the header | `tech-stack-agent` |
| 6 | No layer in `docs/tech-stack.md` has a deferred decision | No entry in the `## Deferred Decisions` section, or that section is absent | `tech-stack-agent` |

## Output Format

```
## Greenfield Checklist

| # | Item | Status | Action Required |
|---|------|--------|-----------------|
| 1 | Requirements document | PASS | — |
| 2 | Env promotion strategy | FAIL | Run /requirements to add the env strategy section |
| 3 | Security baseline | PASS | — |
| 4 | System design document | PASS | — |
| 5 | Tech stack document | PASS | — |
| 6 | No deferred tech decisions | FAIL | Return to tech-stack-agent to resolve deferred layers |

**Result: BLOCKED — 2 items failed. Resolve the above before scaffold generation can proceed.**
```

Or, if all pass:

```
## Greenfield Checklist

All 6 items: PASS

**Result: CLEARED — scaffold generation may proceed.**
```

## Routing on Failure

When one or more items fail, the orchestrator routes the user back to the owning agent for that item. The checklist skill does not fix the failures — it only identifies them and names the owning agent.

## Rules

DO NOT allow scaffold generation to proceed if any of the 6 items is FAIL. Scaffold is blocked until a re-run of this checklist shows all 6 PASS.

STOP and surface a clear error message if the checklist cannot read a required file (e.g. due to a filesystem error) — do not default to PASS in ambiguous cases.

DO NOT consider an item PASS if the relevant section exists but contains only placeholder text such as "TBD", "N/A", or is otherwise empty of meaningful content — mark it FAIL and route the user back to the owning agent for that item.

DO NOT skip item 3 (security baseline) under any circumstances — it is never optional.

## Auto-Pass Derivation (Standalone Entry)

When invoked from `/scaffold` with existing docs on disk, items 1, 4, and 5 auto-pass if the corresponding files exist and are non-empty. Items 2, 3, and 6 still require explicit section verification — they do not auto-pass from file existence alone.
