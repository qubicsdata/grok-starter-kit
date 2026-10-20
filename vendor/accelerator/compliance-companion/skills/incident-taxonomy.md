---
name: incident-taxonomy
description: |
  EU AI Act serious incident classification taxonomy for Art. 62 reporting. Import before incident-reporter.
---

# Incident Taxonomy (Art. 62)

## Severity levels

| Level | Description | Reporting deadline |
|---|---|---|
| S1 — Critical | Death or serious injury attributable to AI output | 15 days |
| S2 — High | Fundamental rights violation (discrimination, privacy, due process) | 15 days |
| S3 — Medium | Significant disruption, data breach, or material harm | 30 days |
| S4 — Low | Near-miss, minor malfunction with no material harm | Document internally; no mandatory report |

## Required incident report fields

- `incident_id`: unique identifier (generate as YYYY-MM-DD-NNN)
- `ts`: ISO-8601 timestamp of discovery
- `severity`: S1/S2/S3/S4
- `ai_system`: name of the AI system/agent involved
- `description`: what happened (factual, no speculation)
- `affected_persons`: approximate number and category (do not name individuals)
- `data_involved`: categories of data involved (no PII values)
- `immediate_action`: steps taken immediately after discovery
- `reported_to`: supervisory authority name (if S1/S2/S3) or "internal only" (S4)
- `deadline`: reporting deadline based on severity

## Hard Gate

**NEVER include PII values (names, ID numbers, contact details) in incident reports.**
**NEVER speculate on cause in the description — facts only.**
**NEVER classify S1/S2/S3 without noting the mandatory reporting obligation.**
