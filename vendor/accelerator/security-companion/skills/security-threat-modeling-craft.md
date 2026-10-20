---
name: security-threat-modeling-craft
description: Invoke when any security-companion agent is about to make a threat-modeling methodology choice, trust-boundary classification, risk scoring calculation, mitigation pattern selection, or scan cadence decision — ensures every recommendation is opinionated, traceable to SEC-D-* rules, and overridable.
---

# Security Threat Modeling Craft Pack

This craft pack encodes opinionated defaults, derivation rules, and output contracts for every decision-making agent in security-companion. Import before making any threat-modeling or security-design recommendation.

## Section 1 — Decision Domains

This pack covers six decision domains, each with an SEC-TM-* identifier:

| ID | Decision Domain | Decision Type |
|---|---|---|
| SEC-TM-1 | Threat modeling methodology: STRIDE / PASTA / LINDDUN / TRIKE | Methodology selection |
| SEC-TM-2 | Risk scoring scheme: DREAD vs CVSS-lite (likelihood × impact) | Scoring calibration |
| SEC-TM-3 | Trust boundary classification scheme: network-zone vs application-level | Boundary taxonomy |
| SEC-TM-4 | Threat register format: tabular Markdown vs structured JSON vs tool-native | Register format |
| SEC-TM-5 | Mitigation strategy pattern: defense-in-depth vs perimeter-only vs compensating control | Mitigation pattern |
| SEC-TM-6 | Iterative review cadence: one-time vs per-feature vs per-sprint vs continuous | Cadence selection |

## Section 2 — Constraint Inputs

These input signals drive derivation rule selection. Agents must assess these before applying defaults:

| Input Signal | Affects |
|---|---|
| System type (greenfield vs existing codebase) | SEC-TM-1 (methodology), SEC-D-3 vs SEC-D-4 |
| External integrations count (0, 1–3, 4+) | SEC-TM-3 (boundary complexity), SEC-D-2 |
| Regulatory exposure (GDPR, PCI-DSS, HIPAA, SOC2, none) | SEC-TM-3 overlay, SEC-D-5 compliance handoff |
| CI/CD maturity (no pipeline, basic, mature with gates) | SEC-TM-6 (cadence), SEC-D-6 |
| Team threat-modeling experience (new, familiar, expert) | SEC-TM-1, SEC-D-8 |
| Sensitive data types present (PII, payment, health, API keys, none) | SEC-TM-3 data-classification overlay, SEC-D-5 |

When context does not supply one of these signals explicitly, apply the default for that signal (stated in Section 3).

## Section 3 — Opinionated Defaults

When no constraint input overrides apply, use these concrete defaults:

- **SEC-TM-1 default — Methodology:** STRIDE. Rationale: most widely understood, tooling-agnostic, maps directly to security properties, and produces a threat register format transferable to any team. Alternative: PASTA (see SEC-D-4).
- **SEC-TM-2 default — Risk scoring:** CVSS-lite (likelihood 1–5 × impact 1–5 = risk score 1–25). Thresholds: LOW 1–7, MEDIUM 8–14, HIGH 15–20, CRITICAL 21–25. Rationale: simpler than full CVSS, more rigorous than qualitative LOW/MEDIUM/HIGH labels. Alternative: DREAD (allowed when team has prior DREAD history).
- **SEC-TM-3 default — Trust boundary classification:** Network-zone boundaries. Classify every zone as Untrusted (public internet, external clients), Semi-trusted (internal services with partial auth), or Trusted (internal services with mutual auth + encryption in transit). Every external-API-boundary is Untrusted by default until trust evidence is present. Alternative: Application-level trust (per-user session) for serverless or multi-tenant SaaS.
- **SEC-TM-4 default — Threat register format:** Tabular Markdown with columns: ID, STRIDE category, component, boundary crossed, likelihood, impact, risk score, mitigation, mitigation owner, security acceptance criterion. Rationale: human-readable, version-controllable, directly embeddable in design docs.
- **SEC-TM-5 default — Mitigation strategy pattern:** Defense-in-depth. Every mitigation must name at least two independent control layers (e.g., input validation + parameterized queries, not just "add validation"). Rationale: defense-in-depth degrades gracefully when one control fails. Perimeter-only mitigations are rejected for HIGH and CRITICAL threats. Alternative: Compensating controls (acceptable for legacy systems where the primary control cannot be applied, but must be documented with a timeline for remediation).
- **SEC-TM-6 default — Review cadence:** Per-feature — every feature that touches a trust boundary gets a threat model delta review. For teams using CI/CD with sprint cadence, reviews happen at sprint boundaries that include trust-surface changes (SEC-D-6). Alternative: one-time-only (acceptable only for MVP/prototype — must be revisited before production deployment).

## Section 4 — Derivation Rules

Exactly eight rules, SEC-D-1 through SEC-D-8. Every recommendation must cite the applicable rule or state "defaults apply":

| Rule | Condition → Applied Decision |
|---|---|
| SEC-D-1 | Untrusted input present → defense-in-depth mitigation pattern REQUIRED for all threats touching that input. Perimeter-only mitigation is not acceptable. |
| SEC-D-2 | External-API-boundary present (REST, gRPC, webhook, WebSocket, message queue) → network-zone trust classification REQUIRED. That boundary is classified Untrusted until explicit trust evidence (mutual TLS, API key verification, signed payloads) is documented. |
| SEC-D-3 | Greenfield system (no prior codebase) → apply STRIDE + CVSS-lite as the default methodology pair. OWASP Threat Dragon recommended as tooling. |
| SEC-D-4 | Existing codebase with documented PASTA experience in the team → PASTA methodology allowed; overrides SEC-D-3 default. Override must be stated explicitly with rationale. |
| SEC-D-5 | Regulatory exposure present (GDPR, PCI-DSS, HIPAA, SOC2) → data-classification trust-boundary overlay REQUIRED (identify which trust boundaries sensitive data crosses and under which regulatory scope). Handoff to compliance-companion is mandatory: HANDOFF → compliance-companion for regulatory control mapping. |
| SEC-D-6 | CI pipeline present + per-sprint development cadence → threat model delta review is REQUIRED at every sprint boundary that includes changes to trust surfaces. No trust-surface change ships without a delta review sign-off. |
| SEC-D-7 | Threat with HIGH or CRITICAL risk score (risk score ≥ 15) → perimeter-only mitigation is REJECTED. Defense-in-depth with at least two independent control layers is REQUIRED. Rationale: a single-layer control failing on a HIGH/CRITICAL threat is unacceptable. |
| SEC-D-8 | Team new to threat modeling (no prior TM experience documented) → STRIDE is chosen (SEC-D-3 applies). OWASP Threat Dragon recommended as the primary tool. A hand-drawn data flow diagram is acceptable as the DFD input format — do not require automated tooling as a prerequisite. |

## Section 5 — Recommendation Output Contract

Every agent importing this craft pack MUST emit recommendations in this format per domain:

1. **Domain ID + chosen value**: Name the SEC-TM-N domain and the concrete chosen option (e.g., "SEC-TM-1: STRIDE").
2. **Rule citation**: Cite the SEC-D-N rule that drove the choice, or state "defaults apply" if no rule fired.
3. **Named alternative with rationale**: At least one alternative option with a one-sentence rationale for when it would be preferred over the default.
4. **Override hook**: State how the caller can override this choice (e.g., "Override: pass `methodology=PASTA` if the team has prior PASTA experience per SEC-D-4").

Recommendations use the word "recommended" or "default" — never "MUST" or "SHALL". Hard requirements are in the Hard Gates section of the agent, not in craft pack recommendations.

## Section 6 — Enforcement Handoff

The threat-register-schema skill is the enforcement mechanism for output conformance. Any threat register entry missing a SEC-D-* citation for its mitigation choice, or any recommendation missing its override hook, is a threat-register-schema violation and must be corrected before the entry is included in output.

Enforcement cascade:
1. Agents self-validate their entries against threat-register-schema before returning output.
2. The orchestrator re-validates the assembled register before passing to threat-model-writer.
3. threat-model-writer validates again at Step 7 of its write process.

Cross-plugin enforcement: when SEC-D-5 fires, compliance-companion MUST be referenced in the threat model's Recommended Next Steps section and in the Cross-Plugin References section of the final document.
