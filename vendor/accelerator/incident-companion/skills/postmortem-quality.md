---
name: postmortem-quality
description: |
  Validates a post-mortem draft against 6 required elements: incident timeline, systemic root cause (not "human error"), quantified user impact, detection method, action items with owners, action items with due dates. Reports each as PASS/FAIL. Used by postmortem-agent (before presenting draft) and postmortem-critic (as critique input).
---

# Post-Mortem Quality Gate

## Purpose

Ensure that a post-mortem document meets the minimum bar to be useful: it must be honest about impact, accountable about remediation, and actionable. A post-mortem that fails any gate must not be presented to the user until the failing agent fixes it.

## Gates

Run all 6 gates against the draft. Report each as PASS or FAIL.

### Gate 1 — Timeline Present

**Check:** Is there a Timeline section that is non-empty and contains at least one timestamped entry?

- **PASS:** Timeline section present with at least one entry in chronological format with a UTC timestamp
- **FAIL:** Timeline section absent, empty, or contains only placeholder text

**FAIL Response:** Route back to elicitation question 5: "Walk me through what happened, in your own words. Include what actions were taken and when."

---

### Gate 2 — Root Cause Is Systemic

**Check:** Does the Root Cause section describe a systemic condition (a gap in process, tooling, or infrastructure) rather than attributing cause to a person or using the phrase "human error"?

- **PASS:** Root cause names a specific technical or process condition (e.g. "The database connection pool was not configured with a maximum timeout, allowing connections to accumulate indefinitely under load")
- **FAIL:** Root cause says "human error", names a person as the cause, or is a tautology ("the service went down because the database failed")

**FAIL Response:** Prompt: "Human error and tautological causes are not root causes. What system, process, or tooling condition made this incident possible or likely? Try: 'The [system/process/tool] lacked [safeguard], which allowed [specific condition] to occur.'"

---

### Gate 3 — User Impact Quantified

**Check:** Does the Impact section include at least one of: number of users affected, percentage of users affected, or duration of user-visible impact?

- **PASS:** Impact section contains a specific number, percentage, or duration (e.g. "~2,300 users", "15% of checkout requests", "47 minutes of elevated error rate")
- **FAIL:** Impact is described in qualitative terms only ("some users experienced errors") without any quantification

**FAIL Response:** Prompt: "How many users were affected and for how long? Approximate figures are acceptable if exact numbers are unavailable."

---

### Gate 4 — Detection Method Stated

**Check:** Does the Detection section state how the incident was first detected (automated alert, user report, internal discovery, monitoring dashboard)?

- **PASS:** Detection section names the detection method (e.g. "Datadog alert `payments.error_rate > 5%` fired at 14:23 UTC", "User report via support ticket at 14:31 UTC")
- **FAIL:** Detection section absent, empty, or says only "we noticed it"

**FAIL Response:** Prompt: "How was this incident first detected — automated alert, user report, or internal observation? Name the specific alert or channel."

---

### Gate 5 — All Action Items Have Owners

**Check:** Does every row in the Action Items table have a non-empty Owner column?

- **PASS:** All action item rows have an owner (role or name)
- **FAIL:** One or more rows have an empty, "TBD", or "N/A" Owner field

**FAIL Response:** For each ownerless action item, prompt individually: "Who owns '[action item text]'? Please assign a role or name."

---

### Gate 6 — All Action Items Have Due Dates

**Check:** Does every row in the Action Items table have a non-empty Due Date column in YYYY-MM-DD format?

- **PASS:** All action item rows have a due date
- **FAIL:** One or more rows have an empty, "TBD", or "ongoing" Due Date field

**FAIL Response:** For each dateless action item, prompt individually: "What is the due date for '[action item text]'? A specific date is required."

---

## Output Format

```
## Post-Mortem Quality Check

- Gate 1 (Timeline Present): PASS
- Gate 2 (Root Cause Systemic): FAIL — root cause says "human error"
- Gate 3 (User Impact Quantified): PASS
- Gate 4 (Detection Method): PASS
- Gate 5 (Action Items — Owners): FAIL — action item 3 has no owner
- Gate 6 (Action Items — Due Dates): PASS

Result: BLOCKED — 2 gate(s) failed. Fix before presenting draft.
```

If all 6 gates pass:
```
## Post-Mortem Quality Check

All 6 gates: PASS
Result: READY — present draft to user.
```

## Invariant

This skill is read-only. The invoking agent is responsible for re-entering elicitation to resolve failures and then re-running this skill. Never present a draft with one or more FAIL results.
