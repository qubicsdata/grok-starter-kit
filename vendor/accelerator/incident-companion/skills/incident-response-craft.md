---
name: incident-response-craft
description: |
  Opinionated incident-response decision expertise consumed by the runbook-agent and escalation-agent. Encodes defaults for severity classification, escalation path, comms cadence/channels, runbook structure, mitigation-vs-rollback choice, and postmortem trigger. Every recommendation leads with a named default, cites the INCIDENT-D-* rule that produced it, and offers ≥1 override.
---

# Incident Response Craft

## Section 1 — Decision Domains

- RESP-1 Severity classification (P0 / P1 / P2 / P3) — the priority tier assigned at incident onset, driving all downstream decisions
- RESP-2 Escalation path — who is paged, in what order, at what SLA, when the primary cannot resolve
- RESP-3 Comms cadence and channels — how frequently to broadcast status and via which channels
- RESP-4 Runbook structure — whether the runbook is triage-first or detection-first; what sections are mandatory vs optional
- RESP-5 Mitigation vs rollback choice — whether to remediate forward (mitigation) or revert to a known-good state (rollback)
- RESP-6 Postmortem trigger — whether and when to initiate a formal postmortem after incident close

## Section 2 — Constraint Inputs

- User-visible impact scope (% of users affected, revenue-bearing surface) → RESP-1 (high scope → P0/P1); RESP-3 (customer-facing outage mandates external comms channel)
- Incident duration at time of triage → RESP-1 (>30 min unresolved elevates tier); RESP-6 (>15 min or any P0/P1 → postmortem)
- Blast radius (number of services/teams affected) → RESP-1 (multi-service → P0); RESP-2 (multi-team blast radius escalates beyond service on-call)
- Data integrity risk (writes corrupted, data loss possible) → RESP-1 (any data risk is at minimum P1); RESP-5 (data risk forbids forward mitigation; rollback preferred)
- Rollback availability (reversible deploy, feature flag, DB migration state) → RESP-5 (reversible deploy → prefer rollback; migration-locked → mitigation only)
- Service tier (revenue-critical vs internal tooling) → RESP-1 (revenue-critical baseline is P1 regardless of scope); RESP-3 (revenue-critical requires executive notification channel)
- Failure mode novelty (known runbook exists vs unknown failure) → RESP-4 (unknown mode → detection-first structure; known mode → triage-first)

## Section 3 — Opinionated Defaults

- RESP-1: Default severity is **P2** for any new incident until evidence of user-visible impact is confirmed. Treat an unknown scope as P2, not P3 — underclassification is costlier than overclassification.
- RESP-2: Default escalation path is **primary on-call → service lead (15 min SLA) → VP Engineering (30 min SLA)**. Two escalation tiers minimum; a single-contact path is not an escalation path.
- RESP-3: Default comms cadence is **every 15 minutes on the incident Slack channel** (#incidents or equivalent); executive channel notification only at P0/P1. External status-page update within 5 minutes of P0/P1 declaration.
- RESP-4: Default runbook structure is **triage-first**: Detection Signals → Triage Checklist → Mitigation Steps → Rollback → Escalation Path → Verification. Triage before action — unknown environments need context before remediation.
- RESP-5: Default choice is **rollback when a clean revert path exists** (deploy rollback or feature flag disable). Prefer a known-good state over an untested forward fix during an active incident. Mitigation-only when no revert path is available or the failure mode is configuration drift.
- RESP-6: Default postmortem trigger is **any P0 or P1**, and any incident lasting > 15 minutes regardless of severity. Postmortem is mandatory, not optional, for these cases.

## Section 4 — Derivation Rules

- INCIDENT-D-1: When user-visible impact exceeds 5% of active users OR a revenue-bearing transaction surface (checkout, payments, auth) is unavailable for any users, choose **P0** because revenue impact compounds every minute and delayed escalation increases MTTR.
- INCIDENT-D-2: When user-visible impact is confirmed but affects <5% of users and no revenue transaction surface is fully down, choose **P1** because measurable customer harm demands rapid (not war-room) response without over-mobilising the full org.
- INCIDENT-D-3: When blast radius spans more than two services or more than one team, escalate to **VP Engineering or equivalent** at the 15-minute mark (not 30) because cross-team coordination requires organisational authority that a service on-call lacks.
- INCIDENT-D-4: When data integrity risk is detected (corrupted writes, partial transactions, data loss window open), choose **rollback** over forward mitigation and classify at minimum **P1** because data loss cannot be undone; forward fixes risk compounding the loss window.
- INCIDENT-D-5: When a clean rollback path is unavailable (e.g., schema migration applied, stateful queue consumed, no previous artifact), choose **forward mitigation** and document the rollback unavailability explicitly in the runbook because attempting an unsupported rollback during an incident causes additional failures.
- INCIDENT-D-6: When the failure mode has no existing runbook, use **detection-first runbook structure** (lead with observable signals before remediation steps) because an on-call engineer encountering a novel failure needs situational awareness before action.
- INCIDENT-D-7: When the incident is a known failure mode with an existing runbook, use **triage-first structure** (lead with a quick triage checklist to confirm mode match before mitigation) because false runbook matches waste time and can worsen a different failure.
- INCIDENT-D-8: When the incident is P0 or P1 or lasted >15 minutes, trigger a **mandatory postmortem**; do not make it optional or elective because incidents below the postmortem threshold systematically miss their own contributing factors.
- INCIDENT-D-9: When a feature flag is available to disable the failing code path, choose **feature-flag disable** as the first mitigation step over a code hotfix because flag toggles are instant, require no deploy, and are reversible in seconds.

## Section 5 — Recommendation Output Contract

Every recommendation the runbook-agent or escalation-agent emits from this pack MUST contain the following four elements:

1. **Chosen value** — the named, concrete decision (e.g. "P1", "rollback via `kubectl rollout undo`", "15-minute Slack cadence"). Never abstract categories.
2. **Rule citation** — the INCIDENT-D-N rule(s) that fired, or "defaults apply (no derivation rule fired)" if none matched. Multiple rules may fire; list all.
3. **Named alternative** — at least one concrete alternative with a brief rationale for when it would be preferred (e.g. "or P0 if checkout revenue impact is confirmed — see INCIDENT-D-1").
4. **Override hook** — a concrete instruction for the responding engineer, stating exactly what to do to override the recommendation (e.g. "override RESP-5 by documenting rollback unavailability in the Rollback section and setting mitigation-only flag in the runbook header").

Consumers MUST NOT emit a neutral menu of options. Lead with the chosen value. The rule citation must appear before any alternative. An override hook with no actionable instruction is a violation of this contract.

## Section 6 — Enforcement Handoff

incident-response-craft output is validated by runbook-quality (RESP-4 runbook structure compliance — Gate 1 trigger conditions, Gate 2 ordered mitigation steps, Gate 3 rollback step, Gate 5 secondary escalation) and postmortem-quality (RESP-6 postmortem trigger compliance — Gate 1 timeline, Gate 2 systemic root cause, Gate 5 action item owners).
