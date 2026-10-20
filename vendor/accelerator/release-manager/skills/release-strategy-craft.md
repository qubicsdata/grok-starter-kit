---
name: release-strategy-craft
description: |
  Release strategy expertise consumed by release-orchestrator and version-advisor. Encodes opinionated defaults and constraint-derived rules for rollout strategy, version bump policy, feature-flag vs branch, rollback policy, release cadence, and change-risk gating. Every recommendation leads with a concrete default, cites the derivation rule, and remains overridable.
---

# Release Strategy Craft

## Section 1 — Decision Domains

- RELEASE-1 Rollout strategy (big-bang / blue-green / canary / rolling)
- RELEASE-2 Version bump policy (semver major / minor / patch, including pre-release promotion)
- RELEASE-3 Feature isolation mechanism (feature flag / long-lived branch / release branch)
- RELEASE-4 Rollback policy (immediate revert / flag flip / hotfix patch / blue-green swap)
- RELEASE-5 Release cadence (continuous / weekly train / sprint-aligned / milestone)
- RELEASE-6 Change-risk gate (none / lightweight self-check / full readiness gate / staged approval)

## Section 2 — Constraint Inputs

- blast_radius (traffic % exposed × severity of failure) → RELEASE-1, RELEASE-4, RELEASE-6
- service_criticality (LOW / MEDIUM / HIGH / CRITICAL based on revenue impact or SLA) → RELEASE-1, RELEASE-4, RELEASE-6
- breaking_change_count (from commit report) → RELEASE-2, RELEASE-3, RELEASE-6
- feature_count (feat commits since last tag) → RELEASE-2, RELEASE-5
- team_size (number of contributors active on this release) → RELEASE-3, RELEASE-5
- deployment_environment (single-region / multi-region / edge / serverless) → RELEASE-1, RELEASE-4
- has_feature_flag_system (boolean — whether the project has a flag runtime available) → RELEASE-3
- release_cadence_target (user-declared preferred cadence) → RELEASE-5

## Section 3 — Opinionated Defaults

- RELEASE-1: **Canary rollout** — expose 5 % of traffic first, monitor error rate for 15 minutes, then promote to 100 %. Rationale: catches regressions in production before full exposure without requiring a full blue-green infrastructure investment.
- RELEASE-2: **Minor bump** when any feat commit is present; patch bump when only fixes/chore; major bump when any breaking change is confirmed. Never skip directly from patch to major without an intermediate minor release cycle.
- RELEASE-3: **Feature flags** over long-lived branches for incomplete work. Merge to main behind a flag; delete the flag on full rollout. Rationale: eliminates merge-conflict accumulation and keeps the integration branch always deployable.
- RELEASE-4: **Flag flip first** (sub-second TTL) as the primary rollback mechanism when a flag system is present; fall back to immediate revert commit + patch release when no flag system exists.
- RELEASE-5: **Sprint-aligned cadence** (every 2 weeks) — frequent enough to keep feedback loops tight, infrequent enough to batch meaningful scope. Override to continuous only when deployment automation is fully proven.
- RELEASE-6: **Full readiness gate** (all 6 items: clean working tree, CI passing, tests green, version unique, changelog entry, release notes present) before any tag command is produced. No exceptions by default.

## Section 4 — Derivation Rules

- RELEASE-D-1: When service_criticality is CRITICAL and blast_radius is HIGH, choose blue-green over canary because a failed canary at high blast radius still corrupts a significant user cohort before detection; blue-green allows instantaneous full traffic swap-back at zero user impact.
- RELEASE-D-2: When deployment_environment is serverless or edge (no persistent process), choose rolling rollout because blue-green requires a warm standby fleet that serverless runtimes do not support; rolling cold-start distribution approximates progressive exposure.
- RELEASE-D-3: When breaking_change_count > 0, choose major bump AND a long-lived release branch (not a flag) because feature flags cannot hide API contract changes from external consumers; a release branch gives the team an explicit coordination boundary.
- RELEASE-D-4: When breaking_change_count > 0 AND service_criticality is HIGH or CRITICAL, add a staged approval gate (product owner sign-off + architecture review recorded in the release notes) before producing tag commands.
- RELEASE-D-5: When has_feature_flag_system is false AND feature_count > 3, choose a release branch over feature flags because without a runtime flag system, merging multiple unfinished features to main without isolation creates an always-broken integration branch.
- RELEASE-D-6: When blast_radius is LOW and service_criticality is LOW, choose big-bang rollout because the overhead of canary or blue-green infrastructure exceeds the risk; a simple deploy with immediate rollback on alert is sufficient.
- RELEASE-D-7: When release_cadence_target is continuous AND deployment_environment is not serverless, require feature flags for all in-progress work because continuous deployment without flags means partially complete features reach production users immediately.
- RELEASE-D-8: When feature_count is 0 and breaking_change_count is 0 (patch-only release), choose patch bump AND skip release notes (generate only a CHANGELOG entry) because a prose release document for a pure-fix release adds noise without informational value.
- RELEASE-D-9: When team_size > 8 and release_cadence_target is continuous, switch to weekly-train cadence because continuous deployment at large team size produces release-over-release instability without a batching checkpoint.

## Section 5 — Recommendation Output Contract

For each Decision Domain the release-orchestrator or version-advisor emits, the recommendation block MUST contain:

1. **Domain and chosen value** — name the concrete strategy (e.g. "Canary rollout"), not an abstract category.
2. **Rule citation** — list each RELEASE-D-N that fired. If no derivation rule fired, state "defaults apply (RELEASE-3 default)".
3. **At least one named alternative** with a brief rationale for when it would be preferred (e.g. "blue-green if you have a dedicated warm standby fleet and zero-tolerance for any user-facing error").
4. **Override hook** — a concrete instruction the implementer can act on (e.g. "To override: set rollout_strategy: big-bang in your release config and skip the canary monitoring step").

Consumers of this pack MUST NOT emit a strategy recommendation without the rule citation and override hook. Omitting either makes the recommendation unverifiable.

## Section 6 — Enforcement Handoff

release-strategy-craft output is validated by release-readiness (item completeness — every release recommendation must produce a matching gate entry before tag commands are issued) and semver-rules (version bump correctness — RELEASE-2 decisions must satisfy RELEASE-D-3 and the semver-rules bump-type derivation table).
