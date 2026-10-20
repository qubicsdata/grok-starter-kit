---
name: sre-postmortem-format
description: |
  Defines the Google/SRE post-mortem template: section names, descriptions, required vs. optional fields, and ordering. Used as the default format by postmortem-agent. Also includes the Atlassian format mapping table for --format atlassian.
---

# SRE Post-Mortem Format

## Purpose

Define the canonical structure for post-mortem documents produced by `postmortem-agent`. The default format is Google/SRE. This skill is the single source of truth for section names, ordering, and required vs. optional designations.

## Default Template (Google/SRE Format)

Every post-mortem produced by `postmortem-agent` must use this exact template unless the user invokes `--format atlassian` or `--format custom`.

```markdown
# Post-Mortem: [Incident Title]

**Date:** YYYY-MM-DD
**Incident Duration:** [start UTC] → [resolution UTC]
**Severity:** [P0 / P1 / P2 / P3]
**Status:** [Draft / Final]

## Summary
[2–3 sentence plain-language summary of what happened and impact. Written for a non-technical reader. Do not include jargon.]

## Impact
- Affected users: [number or percentage — required; use "unknown" only if no data was available and explain why]
- Duration: [minutes/hours of user-visible impact]
- Affected services: [list each service by name]
- Customer-visible symptoms: [what users experienced — error messages, unavailability, data inconsistency, slowness]

## Timeline
[Chronological entries with timestamps in UTC. If produced by timeline-agent, paste directly. Each entry must include a source citation in the format: `HH:MM UTC — [event] (source: [evidence type])`. Entries without citations are not allowed.]

## Root Cause
[The specific systemic condition that made this incident possible. Not "human error". Must name a technical, process, or tooling gap. Example: "The database connection pool had no maximum timeout configured, allowing connections to accumulate under load until the pool was exhausted."]

## Contributing Factors
[Conditions that made the incident worse or harder to detect. Each contributing factor is a separate bullet. Examples: missing alert thresholds, unclear runbook steps, cascading dependency without circuit breaker, on-call rotation gap.]

## Detection
[How the incident was detected — automated alert, user report, or internal discovery. Include: what fired (or what didn't), at what time, and how long the incident had been occurring before detection. If detection was delayed, state how long it went undetected.]

## Resolution
[What action resolved the incident. Include the specific step that stopped user impact. Note if the resolution was a workaround rather than a fix.]

## Lessons Learned

### What Went Well
[Systems, processes, or behaviors that limited impact or aided response. Be specific — "the on-call runbook was up to date and accurate" is useful; "communication was good" is not.]

### What Went Wrong
[Systemic gaps exposed by this incident. These should map directly to the Root Cause and Contributing Factors sections.]

### Where We Got Lucky
[Things that could have been worse but weren't — these are risks that still exist and should be addressed. Example: "The incident occurred at 2pm on a Tuesday; if it had occurred during a peak traffic window, estimated impact would have been 10x higher."]

## Action Items

| # | Action | Owner | Due Date | Status |
|---|--------|-------|----------|--------|
| 1 | [specific, verifiable task — not "improve monitoring" but "add alert for payments.connection_pool_utilization > 80%"] | [role or name] | YYYY-MM-DD | Open |
```

## Section Reference

| Section | Required | Notes |
|---|---|---|
| Summary | Required | 2–3 sentences, plain language |
| Impact | Required | At least one quantified field (users, %, duration) |
| Timeline | Required | At least one cited entry |
| Root Cause | Required | Systemic condition; not "human error" |
| Contributing Factors | Required | At least one; may be "None identified" only if explicitly justified |
| Detection | Required | Must name detection method and time |
| Resolution | Required | Specific action that ended user impact |
| Lessons Learned — What Went Well | Required | At least one entry |
| Lessons Learned — What Went Wrong | Required | At least one entry |
| Lessons Learned — Where We Got Lucky | Optional | Omit only if no lucky factors exist |
| Action Items | Required | At least one; each row requires Owner and Due Date |

## Atlassian Format Mapping

When `postmortem-agent` is invoked with `--format atlassian`, use this section mapping. All other rules (blameless culture, quality gates, write confirmation) apply unchanged.

| SRE Section | Atlassian Equivalent |
|---|---|
| Summary | Summary |
| Impact | Impact |
| Timeline | Timeline of Events |
| Root Cause + Contributing Factors | Root Cause Analysis (merged) |
| Detection | Detection |
| Resolution | Resolution |
| Lessons Learned (all three subsections) | What Went Well / What Went Wrong (no "Where We Got Lucky") |
| Action Items | Action Items |

**Atlassian format note:** The Atlassian template merges "Root Cause" and "Contributing Factors" into a single "Root Cause Analysis" section. When writing in Atlassian format, include both the primary root cause and contributing factors as subsections under one header. The systemic root cause requirement applies to both formats.

## Custom Format

When `postmortem-agent` is invoked with `--format custom "path/to/template.md"`:

1. Read the template file at the provided path
2. Map the template's sections to the required elements from `postmortem-quality` skill:
   - Timeline → required section in template
   - Root cause → required section in template
   - User impact (quantified) → required section in template
   - Detection method → required section in template
   - Action items with owners → required section in template
   - Action items with due dates → required section in template
3. Adapt elicitation questions to match the template's terminology
4. All quality gates and blameless culture enforcement apply regardless of custom template structure

If a required element has no obvious corresponding section in the custom template, add a clearly labelled section for it and note the addition to the user before writing.
