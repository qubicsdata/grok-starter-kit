---
name: feedback-schema
description: |
  Entry format for .ai-evolution/feedback.jsonl. Import before feedback-journal-agent. Defines the append-only JSONL schema for quality scores, review-efficacy records, and applied refinements.
---

# Feedback Schema

## File location

`.ai-evolution/feedback.jsonl` at project root.

The journal holds three append-only entry types, discriminated by the optional `kind`
field. An entry with no `kind` (or `kind:"quality"`) is a quality score; an entry
with `kind:"review-efficacy"` records whether a review tier paid off; an entry with
`kind:"refinement-applied"` records that a human-approved `/refine` change was applied.

## Quality entry (`kind` absent or "quality")

```json
{
  "ts": "<ISO-8601 UTC>",
  "agent": "<agent name scored>",
  "completeness": <0-10 integer>,
  "safety": <0-10 integer>,
  "accuracy": <0-10 integer>,
  "overall": <0.0-10.0 float, 1 decimal>,
  "reasoning": "<1-2 sentences explaining the scores>",
  "session_id": "<from ai-baseline context if available, else 'unknown'>",
  "scorer": "quality-scorer"
}
```

All 9 fields required for a quality entry.

## Review-efficacy entry (`kind:"review-efficacy"`)

Records, for one build's review pass, whether the review tier earned its cost. Used
by `/refine` to demote a tier that never pays (see `ai-baseline/skills/risk-tier-spec.md`).

```json
{
  "ts": "<ISO-8601 UTC>",
  "kind": "review-efficacy",
  "tier": "<light|standard|full>",
  "found_critical": <true|false>,
  "found_important": <true|false>,
  "score_delta": <float — quality-score improvement attributable to the review, 0 if none>,
  "paid": <true|false — found_critical OR found_important OR score_delta > 0>,
  "session_id": "<from ai-baseline context if available, else 'unknown'>"
}
```

All 8 fields required for a review-efficacy entry. No free-text fields (avoids
injection in the journal); `tier` is an enum, the rest are booleans/numbers.

## Refinement-applied entry (`kind:"refinement-applied"`)

Records that a diff proposed by `/refine <agent>` or `/refine tiers` was applied AFTER
the human typed APPROVE. Written by the `/refine apply` command itself — never by the
prompt-refiner agent, which proposes only. Closes the audit trail on the constitutional
rule: the loop proposes, the human approves, the command does the mechanical work.

```json
{
  "ts": "<ISO-8601 UTC>",
  "kind": "refinement-applied",
  "agent": "<agent whose prompt was refined, or 'tiers' for a tier demotion>",
  "target_file": "<repo-relative path of the edited file>",
  "verification": "<validate-pass|validate-fail-reverted|reread-only>",
  "session_id": "<from ai-baseline context if available, else 'unknown'>"
}
```

All 6 fields required for a refinement-applied entry. `verification` is an enum:
`validate-pass` (dev repo, `bash tools/validate.sh` passed), `validate-fail-reverted`
(dev repo, gate failed and the edit was reverted), `reread-only` (installed context —
targeted re-read confirmed the hunks; `validate.sh` is dev-repo-only). No other
free-text fields beyond the constrained `agent` name and file path.

## Hard Gates

**NEVER write to .ai-evolution/feedback.jsonl except via append.**
**NEVER truncate or delete entries.**
**NEVER omit a required field — 9 for a quality entry, 8 for a review-efficacy entry, 6 for a refinement-applied entry.**
**NEVER mix the shapes in one entry.**
