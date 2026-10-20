---
name: prompt-corpus
description: |
  Annotated weak/strong prompt pairs tagged by audience track and by the pattern each one demonstrates. Grown from real cohort sessions under consent and anonymisation rather than invented examples. Consumed by workshop-companion agents when building prompting exercises and assessment material.
---

# Prompt Corpus

## Harvesting rules

These are not optional and are themselves teaching material.

1. Nothing enters the corpus without the author's explicit consent, obtained
   after the session rather than assumed by attendance.
2. Every entry is anonymised: no names, no repository names, no identifiers,
   no domain-specific strings that re-identify a team.
3. Entries record the track they came from, never the person.
4. A learner may withdraw an entry at any time.

## Entry format

Each entry carries: `track`, `pattern`, the weak prompt, the strong prompt, and
what changed between them.

## Seed entries

### C-1 — Unstated scope

- **track:** engineer
- **pattern:** PP-6 negative instruction
- **weak:** "fix the bug in the checkout handler"
- **strong:** "the checkout handler rejects valid coupon codes containing a hyphen. Change only the validation condition. Do not reformat, rename, or refactor anything else in the file."
- **what changed:** the failure is described rather than named, and the boundary is stated.

### C-2 — Conclusion instead of evidence

- **track:** data
- **pattern:** PP-4 demanded verification
- **weak:** "check that this dbt model is correct"
- **strong:** "run this model against the dev warehouse, then show me the row count before and after, and any rows where `order_total` is null. Do not tell me it looks correct; show me the output."
- **what changed:** the request asks for observable output rather than a verdict.

### C-3 — Compound instruction

- **track:** non-technical
- **pattern:** PP-2 task decomposition
- **weak:** "summarise these meeting notes and send follow-ups"
- **strong:** "step one: list every decision made, with who owns it. stop and show me that list. step two, after I confirm: draft one follow-up message per owner."
- **what changed:** a compound request became ordered steps with a checkpoint between them.

Entries C-4 onward are added from delivered cohorts.
