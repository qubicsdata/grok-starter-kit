---
name: product-planning-craft
description: Product planning expertise — backlog granularity, WSJF-lite ordering, story readiness, estimation, persona binding, and lifecycle-stage advancement. Consumed by backlog-author-agent, backlog-agent, and /build-next when making or explaining planning decisions.
---

# Product Planning Craft

## Section 1 — Decision Domains

- PLAN-1 Artifact granularity (epic / feature / story)
- PLAN-2 Backlog ordering scheme
- PLAN-3 Story readiness strictness (DoR)
- PLAN-4 Estimation scale
- PLAN-5 Persona binding
- PLAN-6 Stage advancement policy

## Section 2 — Constraint Inputs

- Team size → PLAN-1/PLAN-2 (solo dev flattens the hierarchy; features only when earned)
- Backlog size → PLAN-2 (<8 items permits stack-rank)
- Project stage → PLAN-3 (hardening raises DoR strictness — no draft-quality stories enter a release-target epic)
- Arc-run capacity → PLAN-4 (a story must fit one /build-next arc run)
- External stakeholders / user-base heterogeneity → PLAN-5 (more personas, explicit success criteria)
- Work risk/reversibility → PLAN-3/PLAN-4 (risky stories need stricter ACs and earn deeper review)

## Section 3 — Opinionated Defaults

- PLAN-1: epic→story; introduce features only past 5 direct stories per epic.
- PLAN-2: WSJF-lite = (business_value + time_criticality + risk_reduction) / job_size, all ∈ {1,2,3,5,8}; deterministic tie-breaks; stack-rank only for <8 items.
- PLAN-3: DoR = DOR-1..7 (backlog-schema); DoD = DOD-1..4. Never negotiable per-story.
- PLAN-4: relative Fibonacci job_size capped at 8; 8 is unschedulable (split).
- PLAN-5: every story binds to a registered active persona; free-text roles rejected.
- PLAN-6: stages advance only on the lifecycle-stages evidence table, user-confirmed.

## Section 4 — Derivation Rules

- PLAN-D-1: When a work item is demonstrable to its persona within one /build-next arc run, make it a story; when it needs several stories but one release, a feature; when it carries an outcome hypothesis across releases, an epic — because the story is sized to the arc's unit of execution.
- PLAN-D-2: When an epic exceeds 5 direct stories, introduce features, because a flat list past 5 loses ordering signal; below that, a feature layer is ceremony.
- PLAN-D-3: When a story lacks ≥2 Given/When/Then acceptance criteria, it is not ready (INVEST-T; enforced as DOR-2) — draft criteria for confirmation; never invent them silently.
- PLAN-D-4: When job_size = 8, split before scheduling (INVEST-S; enforced as DOR-4), because a story larger than one arc run defeats /build-next and produces unreviewably large diffs.
- PLAN-D-5: When the beneficiary is not a registered active persona, create the persona first (INVEST-V; enforced as DOR-1), because free-text roles rot and stories lose their named beneficiary.
- PLAN-D-6: When ordering a backlog of ≥8 items, use WSJF-lite because bounded Fibonacci inputs make every position auditable and computable from frontmatter by a haiku agent; stack-rank when <8 items because ceremony would exceed value.
- PLAN-D-7: When WSJF ties, older `created` wins because aging items accumulate hidden cost; then smaller job_size (finish small things); then lexical ID (total order).
- PLAN-D-8: When advancing the passport stage, require the lifecycle-stages evidence row, because a self-declared lifecycle is worthless to every downstream consumer.
- PLAN-D-9: When an epic outcome contains only unmeasurable terms ("better", "improved", "modern") without a metric or observable, reject and re-elicit, because an epic without a falsifiable outcome can never be evidenced done.
- PLAN-D-10: When a story's "so that" clause restates the "I want" clause, re-elicit the benefit, because value duplication signals a task masquerading as a story (INVEST-V).
- PLAN-D-11: When eliciting any artifact, draft the full artifact from these rules and ask the user to confirm/trim (≤3 answers), because an open interrogation costs more than an editable expert draft — and a drafted default is always presented, never silently assumed.
- PLAN-D-12: When a claimed story has job_size ≥ 5, pass a raise-one-review-tier hint to the arc's review phase, because spend must stay proportional to risk and diff size correlates with review-worthy surface.

## Section 5 — Recommendation Output Contract

Every recommendation (next-story pick, granularity call, split proposal, stage proposal, drafted default) MUST surface: (1) the chosen value; (2) the PLAN-D-N rule(s) that produced it, or "defaults apply (Section 3 PLAN-n)"; (3) ≥1 named alternative; (4) an override hook (a concrete command or argument). Omitting the citation or override makes the decision unverifiable in audit.

## Section 6 — Enforcement Handoff

product-planning-craft output is validated by baseline-enforcer (gate 1: PII scrub on drafted artifact content; gate 3: audit trail after every agent invocation) and by backlog-schema's DOR-/DOD- gate predicates as run by backlog-agent and mirrored deterministically in tools/check-passport.py. PLAN- requirement violations surface via the enrich runner's Review Plan and the /build-next close gate.
