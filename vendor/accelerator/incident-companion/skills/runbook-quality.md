---
name: runbook-quality
description: |
  Validates a runbook draft against 5 required elements: trigger conditions, ordered mitigation steps, rollback step, owner (role), and secondary escalation path. Reports each as PASS/FAIL with repair guidance. Used by runbook-agent and escalation-agent before presenting any draft.
---

# Runbook Quality Gate

## Purpose

Validate that a runbook draft is complete enough to be actionable in an incident at 2am. A runbook that fails any gate must not be presented to the user. The invoking agent must fix the failing item by returning to the appropriate elicitation question, then re-run this skill.

## Gates

Run all 5 gates against the draft. Report each as PASS or FAIL.

### Gate 1 — Trigger Conditions

**Check:** Is there a section (labelled "Trigger Conditions", "Detection Signals", or equivalent) that is non-empty and contains at least one specific alert name, metric threshold, log pattern, or observable signal?

- **PASS:** Section present and contains at least one specific, observable signal (e.g. "Datadog alert `payments.error_rate > 5%`", not "high error rate")
- **FAIL:** Section absent, empty, or contains only general descriptions without named signals

**FAIL Response:** Return to elicitation question 2: "What specific signals indicate this failure mode? Name specific alerts, dashboards, or log patterns."

---

### Gate 2 — Ordered Mitigation Steps

**Check:** Is there a mitigation section with numbered steps (1, 2, 3…), not bullet prose?

- **PASS:** Mitigation section contains a numbered list with at least 2 steps
- **FAIL:** Mitigation section is absent, is bullet prose, or contains a single undifferentiated block

**FAIL Response:** Ask user: "Please provide the mitigation steps as an ordered numbered list (1. Do X, 2. Do Y, 3. Verify Z)."

---

### Gate 3 — Rollback Step

**Check:** Is there a rollback section (labelled "Rollback", "Revert", or equivalent) that describes a specific reversible action and an estimated time to revert?

- **PASS:** Section present, names a specific action (e.g. "run `kubectl rollout undo deployment/payments-api`"), and includes a time estimate
- **FAIL:** Section absent, or says only "N/A" or "cannot roll back" without further detail

**FAIL Response:** Re-ask elicitation question 5: "What is the rollback step if mitigation makes things worse? What does reverting look like and how long does it take?" — even if the service is stateful or 'cannot roll back', the user must document why and what partial remediation is available.

---

### Gate 4 — Owner (Role)

**Check:** Is there an Owner field that contains a role designation (not a personal name)?

- **PASS:** Owner field present and contains a role (e.g. "payments-oncall", "SRE lead", "platform team on-call")
- **FAIL:** Owner field absent, contains a personal name (e.g. "Alice"), or is empty

**FAIL Response:** Re-ask elicitation question 7: "Who owns this runbook? Use a role, not a name — e.g. 'payments-oncall', 'database SRE'."

---

### Gate 5 — Secondary Escalation

**Check:** Is there an escalation path that names a second contact beyond the immediate owner?

- **PASS:** Escalation path names at least two tiers (primary and secondary)
- **FAIL:** Only one escalation contact listed, or escalation section absent

**FAIL Response:** Re-ask elicitation question 7: "Who do you escalate to if the primary owner is unreachable or cannot resolve within 30 minutes?"

---

## Output Format

```
## Runbook Quality Check

- Gate 1 (Trigger Conditions): PASS
- Gate 2 (Ordered Mitigation Steps): FAIL — mitigation is prose, not numbered steps
- Gate 3 (Rollback Step): PASS
- Gate 4 (Owner): PASS
- Gate 5 (Secondary Escalation): FAIL — only one escalation contact listed

Result: BLOCKED — 2 gate(s) failed. Fix before presenting draft.
```

If all 5 gates pass:
```
## Runbook Quality Check

All 5 gates: PASS
Result: READY — present draft to user.
```

## Invariant

This skill is read-only. It reports results. The invoking agent is responsible for returning to elicitation and re-running this skill after fixes. Never present a draft with one or more FAIL results.
