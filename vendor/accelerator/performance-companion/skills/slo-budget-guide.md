---
# <!-- perf-provenance: performance-companion v1.0.0 2026-07-03 -->
name: slo-budget-guide
description: Import when designing SLIs/SLOs, setting error budget percentages, or configuring burn-rate alerts — guides percentile target selection, error budget mechanics, and multi-window burn-rate alerting.
---

# SLO Budget Guide

## SLI / SLO Definitions

**SLI (Service Level Indicator):** A quantifiable measure of service behavior. Must be expressed as a ratio or percentile, not an average.

**SLO (Service Level Objective):** A target value or range for an SLI over a compliance window. Always includes: the SLI, the target value, and the window (rolling 30 days is the default).

**Error Budget:** `(1 − SLO target) × window duration`. Spendable reliability headroom. When exhausted, new feature work is blocked pending reliability investment.

**SLA (Service Level Agreement):** A contractual SLO with financial consequences. Always strictly looser than the SLO (a 99.9% SLO should have a 99.5% SLA at most).

## Percentile Target Guidelines

All latency SLIs MUST be expressed as percentiles. Average latency is NOT an acceptable SLI.

| Request type | p50 target | p95 target | p99 target | Notes |
|---|---|---|---|---|
| Interactive HTTP API (user-facing) | ≤ 100 ms | ≤ 300 ms | ≤ 500 ms | Degrade gracefully above p99 — do not cascade |
| Internal service-to-service RPC | ≤ 50 ms | ≤ 200 ms | ≤ 400 ms | Lower targets than user-facing; shorter call chain |
| Async job / background worker | ≤ 500 ms | ≤ 2 s | ≤ 5 s | Broader window; user-visible only indirectly |
| Batch processing | Define per-batch SLO (e.g. 95% of batches complete in < 30 min) | — | — | Percentile over runs, not individual operation latency |
| Database query | ≤ 10 ms | ≤ 50 ms | ≤ 100 ms | Per-query budget; allocate to leave headroom for network + app overhead |

These are starting defaults. Adjust based on user research and business requirements. Always override with measured baselines when available.

## Error Budget Mechanics

**Default compliance window: rolling 30 days.**

| SLO target | Monthly error budget (minutes) | Daily error budget (minutes) |
|---|---|---|
| 99.9% (three nines) | 43.8 min | 1.44 min |
| 99.5% | 216 min | 7.2 min |
| 99% (two nines) | 432 min | 14.4 min |
| 95% | 2,160 min | 72 min |

**Recommended SLO for new services: 99.5%.** This gives a meaningful error budget (3.6 h/month) while requiring genuine reliability investment. Start here unless the service is customer-critical (use 99.9%) or internal-tooling only (use 99%).

## Burn-Rate Alerting (Multi-Window)

Multi-window burn-rate alerting provides fast page for fast burns, slow burn for slow leaks. Default: two-window alert (Google SRE book Chapter 5 model).

| Alert tier | Short window | Long window | Burn rate | Error budget consumed in window | Severity |
|---|---|---|---|---|---|
| Page (fast) | 1 h | 5 min | 14× | 2% in 1 h | Critical — page on-call |
| Page (moderate) | 6 h | 30 min | 6× | 5% in 6 h | Critical — page on-call |
| Ticket (slow burn) | 3 days | 6 h | 1× | 10% in 3 days | Warning — create ticket |

**Default: implement all three tiers.** Omitting the slow-burn tier means silent budget exhaustion from steady low error rates.

## Error Budget Policy (recommended defaults)

1. When error budget > 50% remaining: no restrictions on deployments or experiments.
2. When error budget < 50% remaining: require reliability review before new risky deployments.
3. When error budget exhausted (0% remaining): freeze new feature deployments; redirect eng capacity to reliability fixes.
4. Error budget resets on the compliance window boundary; never carry forward.

## Hard Gates

**STOP if a latency SLO is expressed as average latency** — request percentile targets before proceeding.
**DO NOT define an SLA tighter than the SLO** — contractual commitments must be strictly looser than internal targets.
**DO NOT omit burn-rate alerting from any SLO design** — an SLO without alerting is a monitoring gap.
**NEVER define error budget in absolute minutes alone without the corresponding percentage** — both must be stated for the window to be actionable.
