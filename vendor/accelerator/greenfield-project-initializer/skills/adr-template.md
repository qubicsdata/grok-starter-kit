---
name: adr-template
description: MADR and Nygard format validator for Architecture Decision Records. Invoke within adr-agent before presenting a draft to the user. Rejects ADRs with fewer than 2 options or missing required sections.
---

## Purpose

The adr-template skill defines the required structure for valid ADRs and validates drafts produced by `adr-agent` before they are shown to the user. An ADR that fails validation must be corrected or supplemented with information from the user before it is presented or written.

## Format Selection Rule

- Team ≥ 5 engineers (from `docs/requirements.md` Team Profile): use MADR
- Team < 5 engineers or team size not stated: use Nygard

## MADR Required Sections

A valid MADR ADR must contain all of the following sections in this order:

1. Title (H1: `# [NNNN] [Title]`)
2. Status line (`- Status: [value]`) — valid values: Proposed, Accepted, Deprecated, Superseded by NNNN
3. Date line (`- Date: YYYY-MM-DD`)
4. Deciders line (`- Deciders: [names or roles]`)
5. `## Context and Problem Statement` — minimum 2 sentences
6. `## Decision Drivers` — minimum 2 bullet points
7. `## Considered Options` — minimum 2 items listed
8. `## Decision Outcome` — must name the chosen option AND provide a rationale
9. `### Consequences` sub-section with at least one positive and one negative consequence
10. `## Pros and Cons of the Options` — one sub-section per considered option

## Nygard Required Sections

A valid Nygard ADR must contain all of the following sections:

1. Title (H1: `# [NNNN] [Title]`)
2. Status line (`- Status: [value]`)
3. Date line (`- Date: YYYY-MM-DD`)
4. `## Context` — minimum 2 sentences
5. `## Considered Options` — minimum 2 items with one-line descriptions
6. `## Decision` — must name chosen option AND provide rationale
7. `## Consequences` — must address both positive and negative outcomes

## Validation Checks

Apply these checks to every ADR draft before presentation:

| Check | Rule | Action if failed |
|-------|------|-----------------| 
| Minimum options | ≥2 options in Considered Options | Ask user for a second option before drafting |
| Decision rationale | Decision section names option AND gives reason | Add "because [rationale]" — ask user for rationale if missing |
| All required sections present | Per format checklist above | Add missing sections; ask user to provide content |
| Status set | Status line present with a valid value | Default to "Proposed" |
| Date set | Date line present | Use today's date |
| Sequence number | NNNN is correct based on existing ADR count | Correct automatically from directory scan |
| Consequences | At least one positive AND one negative | Ask user to supply consequences |

## Immutability Enforcement

DO NOT validate an edit to an existing accepted ADR that changes its decision. If the user requests this, respond:

> ADRs are immutable once accepted. To change this decision, create a new ADR that supersedes this one (Status: Superseded by [new NNNN]). I will draft the new ADR and can update the old one's status line as a separate confirmed write.

## Rules

DO NOT allow an ADR draft to proceed to user presentation if it has fewer than 2 considered options. Ask the user to provide a second option first.

STOP and report to the orchestrator if the user insists on an ADR with only one option — this violates the plugin's anti-pattern rules and cannot be waived.

DO NOT accept "N/A" or a blank entry as a valid second option. Options must be meaningfully distinct alternatives.

DO NOT allow the Consequences section to be absent or contain only "None" — every decision has consequences; ask the user to articulate them.

## Validation Output (internal to adr-agent)

```
ADR-template validation: PASSED — all checks satisfied. Format: MADR.
```

or:

```
ADR-template validation: FAILED
- Check: Minimum options — only 1 option provided. Requesting second option from user.
- Check: Consequences — section absent. Requesting consequences from user.
Blocked: presenting partial draft to user to gather missing information.
```
