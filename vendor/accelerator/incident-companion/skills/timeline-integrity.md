---
name: timeline-integrity
description: |
  Audits every entry in a reconstructed timeline for a source citation. Reports UNCITED entries (those lacking a `(source: ...)` tag). Flags temporal contradictions between evidence sources. Used by timeline-agent before presenting any timeline output.
---

# Timeline Integrity Audit

## Purpose

A reconstructed incident timeline is only trustworthy if every event is traceable to evidence the user provided. This skill audits the timeline for two failure modes:

1. **Uncited entries** — events without a `(source: ...)` tag
2. **Temporal contradictions** — two evidence sources placing the same event at different times

## Citation Rule

Every timeline entry must follow this format:

```
HH:MM UTC — [event description] (source: [evidence type and identifier])
```

Examples of valid entries:
- `14:23 UTC — Datadog alert "payments.error_rate > 5%" fired (source: Datadog alert notification, alert ID #42891)`
- `14:31 UTC — First user report received via support channel (source: Slack #incidents, message from @support-bot)`
- `14:35 UTC — On-call engineer acknowledged alert and began investigation (source: PagerDuty audit log)`

Examples of UNCITED entries (violations):
- `14:23 UTC — Alert fired` ← no source tag
- `14:30 UTC — Engineers likely noticed the problem` ← no source tag AND uses "likely"
- `14:35 UTC — Investigation began` ← no source tag

## Audit Procedure

### Step 1 — Citation Scan

Read every entry in the reconstructed timeline. For each entry:

- If the entry contains `(source: ...)` → mark CITED
- If the entry does not contain `(source: ...)` → mark UNCITED (violation)
- If the entry contains "likely", "probably", "presumably", "may have", or "would have" → mark INFERRED (violation — inferred events are forbidden)

### Step 2 — Contradiction Scan

Compare timestamps across all entries. For each event that appears in more than one evidence source:

- If both sources agree on timing → mark CONSISTENT
- If sources differ on timing by any amount → mark CONTRADICTION

Surface each contradiction explicitly:
```
Conflict: [source A] places [event] at [time A], [source B] places [event] at [time B] — reconcile before finalizing.
```

### Step 3 — Gap Detection

Identify any gap in the timeline longer than 15 minutes between consecutive entries. Surface each gap:
```
Gap: [time A] to [time B] — [N] minutes with no evidence. Note: this is a gap in the evidence, not necessarily a gap in activity.
```

Gaps must be noted but are not violations. Do not fill gaps with inferred events.

## Output Format

```
## Timeline Integrity Audit

### Citation Scan
- 14:23 UTC entry: CITED
- 14:31 UTC entry: UNCITED — violation: no (source: ...) tag
- 14:35 UTC entry: INFERRED — violation: contains "likely"

### Contradiction Scan
- "Alert fired" event: CONTRADICTION — Datadog alert log shows 14:23 UTC, Slack message shows 14:25 UTC — reconcile before finalizing.

### Gap Detection
- Gap: 14:45 UTC to 15:12 UTC — 27 minutes with no evidence.

---
Citations: 1 PASS, 2 FAIL
Contradictions: 1
Gaps: 1

Result: BLOCKED — uncited or inferred entries present. Fix before presenting timeline.
```

If all entries are cited and no contradictions:
```
## Timeline Integrity Audit

All entries: CITED
Contradictions: 0
Gaps: 0

Result: READY — present timeline to user.
```

## Invariant

This skill is read-only. The invoking agent must remove or re-source any UNCITED or INFERRED entries before presenting the timeline. The agent must surface CONTRADICTION findings to the user for manual reconciliation before finalizing.
