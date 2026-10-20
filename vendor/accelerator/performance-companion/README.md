# performance-companion

Advisory backend/server-side performance and scalability companion for the accelerator fleet. Owns latency/throughput budgets, profiling guidance, query/DB performance, load testing strategy, caching, concurrency diagnosis, and CI regression gating.

**Advisory-only** except for a confirm-gated plan document writer (`perf-doc-writer`). No agent modifies your codebase, queries, or configuration without explicit confirmation.

## Installation

```bash
# From the accelerator repo root
claude mcp add performance-companion
```

Requires `ai-baseline` to be installed first:

```bash
claude mcp add ai-baseline
```

## Commands

| Command | Description | Model |
|---|---|---|
| `/perf-strategy` | Design latency/throughput budgets as p50/p95/p99 percentile targets tied to SLOs | Sonnet |
| `/profiling-guide` | Select the right profiler for your runtime; sampling vs instrumentation guidance | Sonnet |
| `/query-perf` | Diagnose N+1 issues, index strategy, EXPLAIN analysis, pool sizing | Sonnet |
| `/load-test` | Tool selection (k6/Locust/Gatling/JMeter), workload modeling, VU derivation | Opus |
| `/caching-strategy` | Cache pattern, store selection, TTL, invalidation, stampede protection | Sonnet |
| `/concurrency-review` | USE method diagnosis: CPU-bound / I/O-bound / pool-exhausted | Opus |
| `/regression-gate` | CI performance regression gates using percentage-deviation baselines | Sonnet |
| `/perf-plan` | Full orchestration: all 7 specialists in parallel → synthesis → confirm → write plan | Sonnet |

### Example Usage

```bash
# Design latency budget for a checkout API
/perf-strategy "Go REST API, checkout service, currently no SLO, peak 800 RPS observed"

# Get profiling guidance for a slow Python service
/profiling-guide "Python FastAPI, intermittent slow responses, need production profiling"

# Analyze a slow query
/query-perf "SELECT o.*, u.name FROM orders o JOIN users u ON o.user_id = u.id WHERE o.status = 'pending' ORDER BY created_at DESC LIMIT 100"

# Design load test with production traffic data
/load-test "Node.js checkout API, peak 1200 RPS, p50 response 90ms"

# Full performance plan (writes to docs/performance/ after confirm)
/perf-plan "Go microservice, 3 services, Redis available, GitHub Actions CI, peak 500 RPS"
```

## Agent Roster

| Agent | Model | Role |
|---|---|---|
| `perf-orchestrator` | Sonnet | Routes /perf-plan; dispatches all specialists in parallel |
| `performance-strategist` | Sonnet | Latency budgets, SLO design, error budget, burn-rate alerts |
| `profiling-guide` | Sonnet | Profiling tool selection, sampling vs instrumentation |
| `query-db-advisor` | Sonnet | N+1, index strategy, EXPLAIN analysis, pool sizing |
| `load-test-strategist` | Opus | Load test tool selection, workload modeling, VU derivation |
| `caching-strategist` | Sonnet | Cache pattern, store, TTL, invalidation, stampede protection |
| `concurrency-advisor` | Opus | USE method diagnosis, pool sizing, backpressure |
| `regression-gate-advisor` | Sonnet | CI percentage-deviation regression gates |
| `perf-doc-writer` | Sonnet | Confirm-gated plan writer (docs/performance/ only) |
| `spec-enricher` | Sonnet | PERF-1..PERF-8 applicability gate for /enrich |
| `audit-trail-agent` | Haiku | Append-only audit logger |

## Key Constraints

- **Latency targets are percentiles only** (p50/p95/p99) — average-latency targets are rejected.
- **VU counts require production traffic data** — fabricated numbers are not accepted.
- **Query optimization requires EXPLAIN evidence** — the agent stops and requests it.
- **Caching recommendations always include** invalidation strategy + TTL + stampede protection.
- **Frontend performance is a hard boundary** — LCP, FCP, CLS, bundle size redirect to `frontend-companion`.
- **Concurrency diagnosis classifies the bottleneck type first** — no prescription before classification.
- **CI gates use percentage-deviation** — no fixed absolute thresholds.
- **Plan documents write to `docs/performance/` only** — after explicit user `confirm`.

## Cross-Plugin Handoffs

| Plugin | Boundary | Scope |
|---|---|---|
| `frontend-companion` | Hard | Bundle size, LCP, FCP, CLS, hydration, code splitting |
| `data-companion` | Soft | Schema/data-model design, pipeline architecture |
| `observability-companion` | Soft | Metrics instrumentation, SLO dashboards, alerting |
| `ops-companion` | Soft | Infra capacity changes, autoscaling, container limits |
| `dev-companion` | Soft | Structural code architecture issues, ADRs |

## Dependencies

- requires: ai-baseline
