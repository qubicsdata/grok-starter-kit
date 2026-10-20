---
name: blameless-culture
description: |
  Use when drafting or reviewing any post-mortem, runbook, or incident write-up. Detects and flags language that assigns blame, names individuals as causes, or uses "human error" without systemic context; returns flagged phrases and replacement guidance. Resolve all violations before presenting a draft.
---

# Blameless Culture Enforcement

## Purpose

Engineering post-mortems and runbooks that assign blame to individuals discourage honest reporting, make recurrence more likely (by treating people as the fix rather than systems), and create psychological harm. This skill detects blame-assigning language in any draft before it is shown to the user.

## Flagged Patterns

Scan the full draft for every pattern in this table. Each match is a violation.

| Pattern Category | Example Match | Why It's a Violation |
|---|---|---|
| Named individual as root cause or contributor | "Alice deployed a bad config", "Bob forgot to check the runbook", "the on-call engineer (John) missed the alert" | Attributes cause to a person, not a system condition |
| Passive blame | "the deploy was not properly reviewed", "the change was not tested adequately", "the runbook was not followed" | Implies individual negligence without naming a systemic gap |
| "Human error" as root cause (unqualified) | "Root cause: human error", "this was caused by human error" | Treats a person as the cause rather than the system that made the error possible |
| Conditional blame | "if the engineer had checked the runbook, this would not have happened", "had the deployer run the test suite…" | Frames a person's hypothetical different action as the counterfactual fix |
| Blame-adjacent adjectives applied to persons | "the engineer carelessly", "the deployer failed to", "the on-call forgot to", "the team missed the signal" | Character or competence judgment applied to a person |
| Ironic understatement | "the team did not exactly cover themselves in glory", "not their finest hour" | Indirect blame that reads as blameless but is not |

## Detection Procedure

1. Read the full draft text
2. Search for every pattern in the table above — use both literal string matching and semantic judgment (e.g. "the developer neglected to" matches the "failed to" pattern even though the word is different)
3. For each match, record:
   - The exact phrase or sentence
   - The pattern category it falls under
   - A blameless replacement (see table below)

## Blameless Rewrite Guidance

For each flagged phrase, provide the specific replacement from this table. If the exact phrase is not in the table, apply the principle: restate the event as a system or process gap, not as a personal failure.

| Blame Pattern | Blameless Replacement |
|---|---|
| "[Name] deployed without testing" | "A deployment was made without automated test coverage for this scenario" |
| "Human error" | "A process gap allowed [specific action] without [missing safeguard]" |
| "[Name] did not follow the runbook" | "The runbook did not clearly indicate the required step for this scenario" |
| "Someone forgot to..." | "There was no automated check to prevent [omitted step] from being skipped" |
| "the engineer carelessly..." | "The [system/process] did not prevent [action] from occurring" |
| "failed to check", "missed the alert" | "No automated escalation existed for the case where [condition] went unacknowledged beyond [threshold]" |
| "the team did not respond fast enough" | "The detection-to-response path lacked [specific mechanism] that would have reduced time to acknowledgement" |
| "if [person] had done X, this wouldn't have happened" | "If [system/process] had [safeguard], [condition] would not have propagated" |

## Output Format

```
## Blameless Culture Audit

### Violations Found

1. **Phrase:** "the on-call engineer forgot to check the dashboard"
   **Category:** Blame-adjacent adjective applied to person ("forgot to")
   **Replace with:** "No automated check existed to verify dashboard state before the on-call shift handoff"

2. **Phrase:** "Root cause: human error"
   **Category:** "Human error" as root cause (unqualified)
   **Replace with:** "A process gap allowed [specific action] without [missing safeguard] — identify the specific gap."

---
Violations: 2
Result: BLOCKED — resolve all violations before presenting draft.
```

If no violations:
```
## Blameless Culture Audit

No violations found.
Result: PASS — draft may be presented.
```

## Enforcement Behavior Per Agent

- **postmortem-agent:** Must not present a draft that has unresolved blame violations. For each violation, show the flagged phrase and the blameless replacement. If the user insists on keeping blame language, decline and explain: "This post-mortem will not be written with blame-assigning language. Please use the suggested replacement or propose an alternative systemic framing."
- **runbook-agent:** Flags violations (rare in runbooks, but possible in "owner" or "history" sections). Removes flagged language automatically and notes the change in the draft.
- **postmortem-critic:** Any unresolved blame language in the submitted post-mortem is a **Critical** finding. Do not soften it. Do not treat it as Medium or High because the document is otherwise good. Blameless culture compliance is non-negotiable.

## Invariant

This skill is read-only. The invoking agent is responsible for applying the rewrites or prompting the user to revise. Never present a draft with unresolved violations.
