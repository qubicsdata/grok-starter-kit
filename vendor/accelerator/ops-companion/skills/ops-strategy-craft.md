---
name: ops-strategy-craft
description: Deployment topology, CI/CD toolchain, scaling policy, capacity/limits, remediation playbook, and maintenance-window strategy expertise. Consumed by pipeline-designer when making opinionated ops recommendations. Each domain leads with a named default grounded in constraint derivation rules.
---

# Ops Strategy Craft

## Section 1 — Decision Domains

- OPS-1 Deployment topology (rolling / blue-green / canary / recreate)
- OPS-2 CI/CD provider selection (GitHub Actions / GitLab CI / CircleCI / Buildkite / Jenkins / Azure Pipelines)
- OPS-3 Scaling policy (manual / scheduled / metric-based HPA / KEDA event-driven / predictive)
- OPS-4 Capacity and limits (CPU/memory request-to-limit ratio, replica floor, resource quotas)
- OPS-5 Remediation playbook choice (auto-rollback / manual-confirm rollback / circuit-breaker + drain / full failover)
- OPS-6 Maintenance-window strategy (in-band zero-downtime / scheduled low-traffic window / blue-green cutover)

## Section 2 — Constraint Inputs

- `security_baseline_answers.environment_promotion_gate` → OPS-1 (manual approval requirement constrains topology; if manual gate required, canary or blue-green is preferred over rolling)
- `security_baseline_answers.container_signing` → OPS-2 (if cosign/Sigstore required, CI provider must support OIDC and image attestation steps)
- `security_baseline_answers.ci_least_privilege` → OPS-2 (OIDC short-lived token requirement limits providers; Jenkins cannot use OIDC natively without plugins)
- Detected CI provider (from repo survey) → OPS-2 (existing investment overrides default when provider is Adopt-rated)
- Traffic pattern (from tech-stack or user description) → OPS-3 (spiky / event-driven traffic favours KEDA; steady traffic favours metric-based HPA)
- SLA / RTO target (from user input or ops-security-baseline) → OPS-1 and OPS-5 (tight RTO < 5 min requires auto-rollback; loose RTO allows manual-confirm)
- Stateful vs. stateless workload → OPS-1 (stateful workloads cannot use recreate; sticky sessions constrain rolling windows)
- Database migrations present → OPS-5 and OPS-6 (irreversible migrations tighten remediation to manual-confirm; zero-downtime window is required)
- Blast radius classification from `iac-risk-classifier` → OPS-5 (GLOBAL blast radius forces manual-confirm rollback or full failover)

## Section 3 — Opinionated Defaults

- OPS-1: Rolling deployment with a 25 % max-surge / 0 max-unavailable policy. This minimises blast radius for stateless services without requiring a full parallel environment. Blue-green is the upgrade when RTO < 5 min or canary when gradual traffic shift is required.
- OPS-2: GitHub Actions. Broad action ecosystem, native OIDC for AWS/GCP/Azure, Dependabot integration, and no self-hosted infrastructure required for most team sizes.
- OPS-3: Metric-based Horizontal Pod Autoscaler (HPA) targeting 60 % CPU utilisation with a 2-minute stabilisation window. This prevents thrashing on transient spikes while tracking sustained load.
- OPS-4: CPU request = 0.5 × limit; memory request = 0.8 × limit; minimum 2 replicas; namespace resource quota enforced. This guarantees scheduling headroom without over-provisioning.
- OPS-5: Auto-rollback triggered on health-check failure within the first 5 minutes post-deploy, followed by a manual-confirm gate for any rollback that involves a database migration.
- OPS-6: Zero-downtime in-band rolling update during normal business hours. Scheduled maintenance window (off-peak) only when an irreversible IaC change is required.

## Section 4 — Derivation Rules

- OPS-D-1: When `environment_promotion_gate` requires manual approval AND the workload is stateless, choose blue-green topology because it allows instant traffic cutback to the previous version without waiting for a rolling drain, satisfying the manual-approval gate intent with a faster rollback path.
- OPS-D-2: When a stateful workload uses sticky sessions or persistent local state (e.g. WebSocket server, session-affinity required), choose rolling deployment with `maxUnavailable: 0` and a pre-drain hook because recreate causes downtime and canary splits traffic in ways that break session affinity.
- OPS-D-3: When `ci_least_privilege` specifies OIDC short-lived tokens AND the existing provider is Jenkins, flag Jenkins as Hold-rated (ref: ops-tech-radar) and recommend GitHub Actions or GitLab CI because Jenkins cannot issue OIDC tokens without third-party plugins, creating a least-privilege gap.
- OPS-D-4: When the detected CI provider already exists in the repository and is Adopt-rated per `ops-tech-radar`, retain that provider as the default and apply the generation rules to it; do not propose switching providers without user request.
- OPS-D-5: When traffic pattern is event-driven (queue depth, webhook bursts, or cron-triggered batch) rather than steady HTTP load, choose KEDA event-driven autoscaling over metric-based HPA because HPA's pull-based CPU metric lags queue depth by one polling interval, causing cold-start latency under burst conditions.
- OPS-D-6: When RTO target is < 5 minutes (stated by user or implied by SLA), choose auto-rollback on health-check failure with a 2-minute observation window because manual-confirm rollback cannot reliably meet a 5-minute RTO under production incident stress.
- OPS-D-7: When `iac-risk-classifier` returns a GLOBAL blast-radius change in the same deployment, choose manual-confirm rollback and a scheduled off-peak maintenance window because the blast radius of an automated rollback affecting shared infrastructure is unacceptable without a human decision point.
- OPS-D-8: When database migrations are present and at least one migration has no down-migration, promote the remediation playbook to manual-confirm rollback and set the maintenance window to off-peak because automated rollback cannot safely reverse an irreversible schema change; the DBA must confirm the state before traffic is restored.

## Section 5 — Recommendation Output Contract

For each Decision Domain emit in this exact order:

1. **Domain and chosen value** — name the specific topology, tool, or policy (never "it depends").
2. **Rule citation** — list each `OPS-D-N` that fired; if no derivation rule fired, state "defaults apply (no derivation rule fired)".
3. **≥1 named alternative** — with a one-sentence rationale explaining when to prefer it.
4. **Override hook** — a concrete instruction (e.g. "Override OPS-1 by setting `strategy: Recreate` in the Deployment manifest and documenting the downtime acceptance in the project ADR").

Consumers MUST NOT emit a recommendation without a rule citation and an override hook. Omitting either makes the recommendation unverifiable and violates PIT-11.

## Section 6 — Enforcement Handoff

ops-strategy-craft output is validated by pipeline-safety-check OPS (generated pipeline configs must implement the chosen topology, scaling policy, and remediation strategy; any deviation from the cited OPS-D-* rule without an explicit user override is a finding).
