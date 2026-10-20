---
name: observability-craft
description: |
  Observability decision expertise — SLI selection, SLO targets, signal type (metrics/logs/traces), cardinality budget, alert strategy, and dashboard structure. Consumed by spec-enricher and observability decision agents when instrumenting a service or agent-based system.
---

# Observability Craft

## Section 1 — Decision Domains

- OBSV-1 SLI selection (which signals define service health: request rate, error rate, latency, saturation, or custom domain signals)
- OBSV-2 SLO targets (numeric thresholds: latency percentile, error budget, success rate)
- OBSV-3 Signal type (metrics / structured logs / distributed traces — primary medium per signal)
- OBSV-4 Cardinality budget (maximum unique label/dimension combinations per metric series)
- OBSV-5 Alert strategy (symptom-based page-level vs. cause-based ticket-level; burn-rate vs. threshold)
- OBSV-6 Dashboard structure (layout of overview, drill-down, and dependency panels)

## Section 2 — Constraint Inputs

- Service type (synchronous API / async worker / batch pipeline / agent chain) → OBSV-1, OBSV-3 (sync APIs prioritise latency+rate SLIs; async workers prioritise queue depth+throughput; agent chains prioritise per-hop latency and token cost)
- Traffic volume (requests/sec or invocations/hour) → OBSV-4 (high-volume services must tighten cardinality budget; low-volume services can afford richer labels)
- Failure impact (user-facing / internal-only / compliance-gated) → OBSV-2 (user-facing tightens SLO targets), OBSV-5 (user-facing requires symptom-first paging)
- Traceability requirement (distributed call chain / single-service / audit-required) → OBSV-3 (distributed requires traces; audit-required requires structured logs with correlation IDs)
- Team operational maturity (on-call rotation exists / no on-call / SRE team) → OBSV-5, OBSV-6 (immature teams need fewer, higher-fidelity alerts and simpler dashboards)
- Cost constraint (metered storage / unlimited / unknown) → OBSV-4 (metered enforces strict cardinality caps)

## Section 3 — Opinionated Defaults

- OBSV-1: Use the four golden signals — request rate, error rate (5xx or task-failure), p99 latency, and saturation (CPU or queue depth). Prefer these over custom domain signals unless a specific domain signal is demonstrably more predictive.
- OBSV-2: p99 latency SLO = 2 000 ms; error rate SLO = 99.5% success; max token cost per session = 100 000 tokens. These defaults match slo-config skill baselines and are the starting point for all services.
- OBSV-3: Structured JSON logs are the primary signal for agent/LLM systems (every invocation emits one log line per OBS-1). Metrics (counters + histograms) are the primary signal for synchronous APIs. Distributed traces are required when a correlation_id chain crosses ≥2 service boundaries.
- OBSV-4: Cardinality cap = 1 000 unique label combinations per metric. High-cardinality dimensions (user_id, request_id, model_version hash) are NOT added as labels; they belong in structured log fields only.
- OBSV-5: Page on symptoms, ticket on causes. The primary page alert is "error rate > 1% for 5 min" or "p99 latency > SLO for 10 min". Cause alerts (disk full, OOM, elevated retries) route to tickets, not pages.
- OBSV-6: Three-panel dashboard structure — (1) Overview: golden signals as sparklines with SLO status, (2) Drill-down: per-agent or per-endpoint breakdown with latency heatmap, (3) Dependencies: upstream/downstream error rate and latency with correlation_id link to traces.

## Section 4 — Derivation Rules

- OBSV-D-1: When service type is agent chain or LLM-invocation pipeline, choose structured JSON logs (OBS-1 format) as the primary signal and add token_count and model_id as log fields, because the audit log already captures these fields and token cost is the dominant operational cost driver in agent systems — not latency or CPU saturation.
- OBSV-D-2: When traffic volume exceeds 1 000 invocations/hour, enforce cardinality cap ≤ 500 unique label combinations (half the default cap) because high-volume services exhaust metric storage budgets rapidly when label sets grow unchecked, leading to cardinality explosions that degrade query performance.
- OBSV-D-3: When failure impact is user-facing AND an on-call rotation exists, tighten the error-rate SLO to 99.9% success and reduce the paging threshold to error rate > 0.1% for 2 min, because user-facing failures directly degrade trust and the on-call rotation can absorb higher alert frequency.
- OBSV-D-4: When traceability requirement is distributed call chain (correlation_id crosses ≥2 services), add distributed traces as a required signal alongside logs, because log-only correlation requires manual grep across systems and misses timing relationships between concurrent sub-agents.
- OBSV-D-5: When team operational maturity is no on-call or single engineer, reduce alert count to ≤3 total pages (one per: error rate breach, latency breach, saturation breach) and widen burn-rate window to 1-hour rolling, because alert fatigue in small teams leads to acknowledgement blindness faster than in mature SRE organisations.
- OBSV-D-6: When cost constraint is metered storage, drop cardinality cap to 200 unique label combinations and strip all non-essential dimensions (environment, version, hostname) from metric labels, keeping them only in structured log fields, because metered metric ingestion charges per unique series.

## Section 5 — Recommendation Output Contract

For each Decision Domain emit: the chosen value (named signal type, concrete numeric target, or specific structure — never abstract categories), the OBSV-D-* rule(s) that produced it (or "defaults apply" when no derivation rule fired), ≥1 named alternative with a brief rationale, and an override hook.

Every recommendation block must follow this structure:

1. Domain name and chosen value as a concrete, named decision (e.g. "p99 latency SLO = 2 000 ms", not "use a reasonable latency target").
2. Rule citation — list each OBSV-D-N that fired; if defaults apply, state "defaults apply (no derivation rule fired)".
3. At least one named alternative with a brief rationale (e.g. "or p95 latency SLO = 1 500 ms if the workload is highly interactive and tail latency disproportionately affects perceived responsiveness").
4. Override hook — a concrete instruction for the implementer (e.g. "override OBSV-2 in .observability/slo.json and update the slo-monitor thresholds accordingly").

Consumers of this pack MUST NOT omit the rule citation or the override hook; doing so makes the recommendation unverifiable and prevents SLO audits from reconstructing the decision rationale.

## Section 6 — Enforcement Handoff

observability-craft output is validated by baseline-enforcer (gates OBS-1 structured log emission, OBS-2 correlation_id propagation, and OBS-3 SLO target presence) and by slo-config (numeric SLO thresholds — any OBSV-2 recommendation must be representable in the .observability/slo.json schema).
