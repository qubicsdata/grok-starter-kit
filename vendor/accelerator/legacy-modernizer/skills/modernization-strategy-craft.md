---
name: modernization-strategy-craft
description: Migration strategy expertise — approach selection, sequencing order, seam/interface strategy, data-migration approach, risk and rollback, and test-coverage-first gating. Consumed by the sequencer-agent and upgrade-map-agent when choosing how to migrate a legacy system.
---

# Modernization Strategy Craft

## Section 1 — Decision Domains

- APPROACH-1 Migration approach (strangler-fig / encapsulate-and-replace / rewrite / rehost)
- APPROACH-2 Sequencing order (blockers-first / risk-descending / dependency-topological)
- APPROACH-3 Seam and interface strategy (anti-corruption-layer / façade / strangler-proxy / direct cutover)
- APPROACH-4 Data-migration approach (dual-write / shadow-read / big-bang / event-replay)
- APPROACH-5 Risk and rollback strategy (feature-flag / blue-green / canary / branch by abstraction)
- APPROACH-6 Test-coverage-first gating (characterisation-test suite required before any refactor phase)

## Section 2 — Constraint Inputs

- Coupling density (derived from inventory.md module-dependency graph) → APPROACH-1, APPROACH-3 (high coupling forces strangler-fig or encapsulate; rewrite becomes viable only at low coupling)
- Risk register Critical/High item count → APPROACH-2 (Critical items mandate blockers-first sequencing regardless of business preference), APPROACH-5 (≥2 Critical items require blue-green or canary; feature-flag alone is insufficient)
- Live-traffic pattern (from inventory.md deployment section) → APPROACH-4 (continuous write traffic forbids big-bang data migration), APPROACH-5 (customer-facing traffic demands canary or blue-green over direct cutover)
- Business freeze window availability (user-supplied constraint) → APPROACH-4 (a confirmed maintenance window ≥4h unlocks big-bang for bounded datasets), APPROACH-3 (no freeze window forces strangler-proxy to maintain continuity)
- Existing test coverage percentage (from inventory.md quality section) → APPROACH-6 (coverage <60% on affected modules triggers characterisation-test requirement before any destructive refactor)
- Cross-service API consumer count (from inventory.md integration section) → APPROACH-3 (≥3 external consumers require an anti-corruption-layer or façade; direct cutover risks cascading failures)

## Section 3 — Opinionated Defaults

- APPROACH-1: Strangler-fig pattern. Route traffic through a façade that incrementally delegates functionality to the new service, retiring legacy endpoints component by component. Rewrites are rejected by default because they reset institutional knowledge and defer value delivery.
- APPROACH-2: Blockers-first sequencing. Address Critical risk register items (score ≥12) in Phase 1 regardless of business preference, then order remaining phases by descending risk score. Dependency-topological ordering is applied only within equal-risk groups.
- APPROACH-3: Anti-corruption-layer at every seam touching external consumers. The ACL translates between legacy and target-state contracts so neither side sees the other's internal model. Direct cutover is rejected unless the system has zero external consumers.
- APPROACH-4: Dual-write. New and legacy stores receive all writes in parallel during the migration window, with the legacy store as the read authority until the new store is verified. Big-bang migration is rejected by default due to rollback complexity.
- APPROACH-5: Feature-flag per migrated component, graduated to blue-green at the service boundary. Canary is preferred for customer-facing traffic once the feature-flag threshold reaches 10%. Branch by abstraction is the implementation mechanism inside each component.
- APPROACH-6: Characterisation-test gate. Before any destructive refactor step is permitted, a characterisation-test suite must exist that covers the observable behaviour of the module being changed. The gate is a hard prerequisite, not a best-effort aspiration.

## Section 4 — Derivation Rules

- MODERNIZE-D-1: When the inventory coupling density is HIGH (≥30% of modules have ≥5 inbound dependencies) and there is no confirmed maintenance window, choose strangler-fig because incremental delegation preserves continuity of service and avoids the big-bang risk of a rewrite or rehost against a tightly-coupled graph.
- MODERNIZE-D-2: When the risk register contains ≥1 Critical item (score 12–16) AND a business stakeholder requests sequencing that would defer the Critical item past Phase 1, reject the request and enforce blockers-first order because deferring a Critical risk means the engagement ships with a known production exposure; reorder non-blocker work instead.
- MODERNIZE-D-3: When the integration inventory lists ≥3 external API consumers of the legacy system, choose an anti-corruption-layer seam strategy because direct cutover of a shared contract surface produces cascading consumer failures that are harder to roll back than a single ACL deployment.
- MODERNIZE-D-4: When live write traffic is continuous (no confirmed maintenance window ≥4h) and the data store is being replaced, choose dual-write over big-bang migration because dual-write allows the legacy store to remain the authoritative read source until verification is complete, eliminating the need for emergency rollback of a bulk data move.
- MODERNIZE-D-5: When customer-facing traffic exists and the risk register has ≥2 High or Critical items, choose blue-green deployment for the service boundary rollback strategy rather than feature-flag alone because feature-flag rollback leaves the new binary running under traffic, while blue-green provides a clean environment boundary that can be switched in under 60 seconds.
- MODERNIZE-D-6: When existing test coverage on affected modules is below 60% (as reported in inventory.md), enforce the characterisation-test gate before scheduling any destructive refactor step in the roadmap because refactoring without a behavioural baseline converts known technical debt into unknown regressions that are impossible to attribute after the fact.
- MODERNIZE-D-7: When the codebase is a monolith with a single deployable unit and the upgrade map recommends a microservice split, choose encapsulate-and-replace over a full rewrite because encapsulation preserves the existing language runtime and test infrastructure while the new boundary is established, reducing the blast radius of the migration.
- MODERNIZE-D-8: When the upgrade map marks a technology as Hold-rated AND the only viable replacement requires a major seam change, choose anti-corruption-layer with a strangler-proxy in front of the Hold-rated component so that the internal replacement can proceed incrementally without forcing an external consumer contract change in the same phase.

## Section 5 — Recommendation Output Contract

For each Decision Domain emit: the chosen value (named pattern, not abstract category), the MODERNIZE-D-* rule(s) that produced it or "defaults apply (no derivation rule fired)" when no rule was triggered, ≥1 named alternative with a trade-off rationale, and an explicit override hook.

Every recommendation block must follow this structure:

1. Domain name and chosen value as a named pattern or technique.
2. Rule citation — list each MODERNIZE-D-N that fired; if defaults apply, state "defaults apply (no derivation rule fired)."
3. At least one named alternative with a brief trade-off note (e.g. "or big-bang migration if a confirmed 6h maintenance window is available and the dataset is under 10GB — eliminates dual-write complexity at the cost of rollback window").
4. Override hook — a concrete instruction the implementer must follow to change the recommendation (e.g. "override APPROACH-4 in the migration ADR, document the rollback procedure, and obtain stakeholder sign-off on the maintenance window before scheduling the data migration phase").

Consumers of this pack MUST NOT omit the rule citation or the override hook. A recommendation without a rule citation is unverifiable; one without an override hook prevents legitimate project-specific adaptation.

## Section 6 — Enforcement Handoff

modernization-strategy-craft output is validated by readiness-checklist (all five gate items check that the strategy-derived phase ordering and seam choices are consistent with the available inventory, risk register, and upgrade map before sequencing is permitted) and migration-risk-scale (risk scores drive MODERNIZE-D-2 and MODERNIZE-D-5 rule firing — any recommendation citing those rules must be traceable to a scored risk item in the register).
