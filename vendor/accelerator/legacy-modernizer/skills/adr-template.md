---
name: adr-template
description: MADR format template for migration decision records. Invoked by adr-agent for every ADR written to docs/modernization/decisions/. Requires ≥2 options. Blocks on single-option inputs.
---

## Purpose

The adr-template skill provides adr-agent with the MADR (Markdown Architectural Decision Record) format for all migration decision records. Migration ADRs are written to `docs/modernization/decisions/` to distinguish them from greenfield architectural ADRs (`docs/adr/`).

## File Naming

ADR files are named: `NNNN-[slug].md`

- `NNNN` is a zero-padded four-digit sequence number (e.g., `0001`, `0042`)
- `[slug]` is a kebab-case summary of the decision (e.g., `replace-webpack-4-with-vite`)
- Example: `0001-replace-webpack-4-with-vite.md`

Sequence numbers are assigned by scanning `docs/modernization/decisions/` for the highest existing NNNN prefix, then incrementing. If the directory is empty or absent, start at `0001`.

NEVER overwrite an existing ADR. If the same decision is revisited, create a new ADR that supersedes the prior one.

## Minimum Options Requirement

Every ADR requires ≥2 options in the "Considered Options" section. adr-agent BLOCKS if only one option is provided and asks the user to supply at least one alternative before proceeding.

## MADR Format

```markdown
# [Short imperative title — e.g., "Replace Webpack 4 with Vite"]

**Date:** YYYY-MM-DD
**Status:** Proposed | Accepted | Superseded by [NNNN-slug]
**Deciders:** [names or roles — leave blank if not provided]

## Context

[1–3 paragraphs. What situation makes this decision necessary? What problem does the current state cause? What constraints apply (timeline, team expertise, compatibility requirements)?]

## Decision Drivers

- [Most important factor driving this decision]
- [Second most important factor]
- [Additional factors as needed]

## Considered Options

- [Option A name]
- [Option B name]
- [Option C name — if applicable]

## Decision Outcome

**Chosen option:** [Option name], because [1–2 sentences stating why this option was selected over the alternatives, referencing the decision drivers].

**Consequences:**
- Good: [positive consequence]
- Bad: [accepted trade-off or downside]
- Neutral: [side effect that is neither good nor bad]

## Pros and Cons of the Options

### [Option A name]

[1–2 sentence description of what this option is]

- Good: [advantage]
- Good: [advantage]
- Bad: [disadvantage]
- Bad: [disadvantage]

### [Option B name]

[1–2 sentence description of what this option is]

- Good: [advantage]
- Good: [advantage]
- Bad: [disadvantage]
- Bad: [disadvantage]

### [Option C name — if applicable]

[1–2 sentence description of what this option is]

- Good: [advantage]
- Bad: [disadvantage]
```

## Rules

DO NOT write an ADR with fewer than 2 options in the Considered Options section. Block and ask the user to provide alternatives.

DO NOT copy-paste the decision statement as the Context section. Context must explain the situation, constraints, and why a decision is needed — not merely restate the decision.

DO NOT leave the Decision Outcome section blank. If the user has not chosen, set Status to "Proposed" and leave a placeholder: "Decision pending — to be resolved by [role/date]."

DO NOT number ADRs by memory or estimation. Always scan the `docs/modernization/decisions/` directory for the highest existing NNNN prefix before assigning a sequence number.

NEVER overwrite an existing ADR file.
