---
name: compliance-craft
description: |
  Compliance decision and advisory expertise — framework selection, control tailoring, data-classification handling, remediation prioritization, and evidence strategy. Consumed by the spec-enricher when recommending which controls apply and in what priority order. Recommendations are overridable advice, never legal certainty; EU AI Act Art. 43 conformity requires a qualified notified body.
---

# Compliance Craft

## Section 1 — Decision Domains

- COMPLY-1 Framework selection — which regulatory regime(s) govern this system (EU AI Act, GDPR, SOC 2, ISO 27001, HIPAA, PCI-DSS, or a combination)
- COMPLY-2 Control selection and tailoring — which controls from the selected framework(s) apply and which are scoped out
- COMPLY-3 Data-classification handling — how data is categorised (personal, sensitive-personal, financial, health, anonymous) and what obligations follow
- COMPLY-4 Remediation prioritization — the order in which gaps should be closed when resources are constrained
- COMPLY-5 Evidence and audit strategy — what artefacts to collect and retain to demonstrate compliance

## Section 2 — Constraint Inputs

- Jurisdiction (EU/EEA, US, global) → COMPLY-1 (EU/EEA triggers EU AI Act + GDPR; US with healthcare triggers HIPAA; US with card payments triggers PCI-DSS)
- AI system risk tier (high-risk per Annex III, limited-risk, minimal-risk) → COMPLY-1, COMPLY-2 (high-risk expands mandatory control set; minimal-risk limits it)
- Data types present (personal, sensitive-personal, financial, health, biometric) → COMPLY-3, COMPLY-2 (each type activates a distinct obligation layer)
- Deployment scale and blast radius (number of affected persons, irreversibility) → COMPLY-4 (higher scale or irreversibility elevates gap-closure urgency)
- Existing audit infrastructure (none, partial, mature) → COMPLY-5 (gaps in audit infrastructure are always highest-priority evidence controls)
- Time-to-deployment constraint (weeks vs. months) → COMPLY-4 (mandatory statutory controls precede discretionary hardening)

## Section 3 — Opinionated Defaults

- COMPLY-1: Default framework is EU AI Act + GDPR for any AI system processing personal data in or targeting the EU/EEA. When jurisdiction is ambiguous, assume EU/EEA scope until explicitly scoped out — the cost of under-compliance exceeds the cost of over-compliance.
- COMPLY-2: Default control set is the minimal mandatory set for the selected framework tier. For EU AI Act high-risk: human-oversight gate (Art. 14), immutable audit trail (Art. 12), transparency/model card (Art. 13), and right-to-explanation handler (Art. 86). Do not apply the full high-risk control set to minimal-risk systems.
- COMPLY-3: Default data-classification policy is: treat any field that could identify a natural person as personal data; treat health, biometric, financial, and criminal-record data as sensitive-personal (Article 9 GDPR special category) until proven otherwise. When in doubt, classify up.
- COMPLY-4: Default remediation order is statutory-before-discretionary: (1) mandatory reporting obligations, (2) human-oversight gates, (3) audit trails, (4) PII redaction in logs, (5) transparency artefacts, (6) discretionary hardening. Within the same tier, close higher-blast-radius gaps first.
- COMPLY-5: Default evidence strategy is continuous append-only audit logging correlated by session and correlation IDs, plus a pre-deployment model card and a signed risk assessment. Periodic (quarterly) evidence reviews are preferred over one-off point-in-time audits.

## Section 4 — Derivation Rules

- COMPLY-D-1: When jurisdiction includes EU/EEA AND the system processes personal data, choose EU AI Act + GDPR as the governing framework because both are directly applicable EU regulations; failure to apply them is a statutory violation regardless of the system's risk tier.
- COMPLY-D-2: When the AI system falls under EU AI Act Annex III (e.g. biometric categorisation, credit scoring, employment screening, law enforcement, critical infrastructure), choose the full high-risk control set (Arts. 9–15 + 17) because Annex III classification is mandatory and carries conformity-assessment obligations under Art. 43.
- COMPLY-D-3: When data types include health, biometric, racial/ethnic origin, or criminal-record data, classify as GDPR Article 9 special-category data and activate explicit-consent or explicit-legal-basis controls because processing Article 9 data without a lawful basis is prohibited under Art. 9(1) GDPR and carries the highest fine tier.
- COMPLY-D-4: When deployment scale exceeds 10 000 affected persons OR the action is irreversible (e.g. permanent record flagging, automated benefit denial), elevate ALL outstanding gaps to P1 remediation because the blast radius exceeds acceptable discretionary-deferral thresholds.
- COMPLY-D-5: When time-to-deployment is under 8 weeks, sequence remediation as: mandatory statutory controls first (human-oversight gate, audit trail), PII redaction second, transparency artefacts third — defer discretionary hardening to a post-launch sprint because shipping without mandatory controls is a statutory violation, whereas shipping without discretionary hardening is a risk acceptance.
- COMPLY-D-6: When the system has no existing audit infrastructure (no append-only log, no correlation IDs), choose audit-trail implementation as the highest-priority single control because without an audit trail no other compliance claim is verifiable and incident reporting (Art. 62) becomes impossible.
- COMPLY-D-7: When jurisdiction includes US healthcare data (PHI), add HIPAA Security Rule controls (access control, audit controls, integrity, transmission security) alongside or instead of GDPR — they address the same threat model and the more stringent rule prevails per data-residency; do not assume GDPR alone covers US PHI.
- COMPLY-D-8: When the system is minimal-risk under EU AI Act (no Annex III classification, no personal data) AND jurisdiction is outside the EU/EEA, choose a lightweight voluntary framework (e.g. NIST AI RMF) and document the scoping rationale, because mandatory EU AI Act controls do not apply and over-engineering compliance creates unjustified cost.

## Section 5 — Recommendation Output Contract

Every recommendation the spec-enricher emits from this pack MUST include:

1. **Domain name and chosen value** — the specific framework, control set, data-classification tier, remediation order, or audit strategy selected (named concretely, never abstract).
2. **Rule citation** — list each COMPLY-D-N that fired; if no derivation rule fired, state "tier-1 default (no constraint override)".
3. **At least one named alternative** — with a brief rationale for when that alternative would be preferable (e.g. "or SOC 2 Type II if the customer base is US-SaaS-only and EU/EEA is out of scope").
4. **Override hook** — a concrete instruction: what the implementer must do to legitimately override the recommendation (e.g. "override COMPLY-1 by documenting a jurisdictional scoping decision in the project's risk register and obtaining sign-off from the data-protection officer").

Recommendations are overridable advisory outputs — they are NOT legal opinions, regulatory rulings, or conformity certifications. Each recommendation must carry the following disclaimer inline: *(overridable advice — not legal certainty; Art. 43 conformity requires a qualified notified body).*

Consumers MUST NOT omit the rule citation or override hook; doing so makes the recommendation unverifiable.

## Section 6 — Enforcement Handoff

compliance-craft output is validated by baseline-enforcer: the baseline-enforcer gates verify that every agent output has passed PII scrub (Gate 1), cost check (Gate 2), and audit logging (Gate 3) before any recommendation from this pack is emitted or persisted.
