---
# <!-- perf-provenance: performance-companion v1.0.0 2026-07-03 -->
name: performance-craft
description: Import when advising on latency/throughput budgets, profiling tool selection, load test strategy, caching design, or concurrency diagnosis — each recommendation must cite a PERF-D-* rule and lead with an opinionated default.
---

# Performance Craft

## Section 1 — Decision Domains

- **PERF-DOMAIN-1 Latency budget** — defining p50/p95/p99 targets tied to user-facing SLOs; never average-only targets.
- **PERF-DOMAIN-2 Throughput and capacity** — RPS/TPS ceilings, error budget allocation, burn-rate alerting.
- **PERF-DOMAIN-3 Profiling approach** — sampling vs instrumentation selection, runtime-to-tool mapping, flame graph reading.
- **PERF-DOMAIN-4 Query and database performance** — N+1 detection, index strategy, EXPLAIN-driven diagnosis, pool sizing.
- **PERF-DOMAIN-5 Load test design** — tool selection (k6/Locust/Gatling/JMeter), open vs closed workload model, ramp/soak/spike profiles, VU targets grounded in production data.
- **PERF-DOMAIN-6 Caching strategy** — layer selection, store choice, TTL, invalidation, stampede protection.
- **PERF-DOMAIN-7 Concurrency diagnosis** — USE method (Utilization/Saturation/Errors) bottleneck classification, pool sizing, backpressure design.
- **PERF-DOMAIN-8 CI regression gating** — percentage-deviation baselines, threshold calibration, baseline storage strategy.

## Section 2 — Constraint Inputs

Gather these signals before producing any recommendation. Never recommend without the input that drives it.

| Input | Signals to collect | Drives |
|---|---|---|
| Latency evidence | Current p50/p95/p99 measurements or APM trace data | Budget (PERF-DOMAIN-1) |
| Production traffic data | Current RPS, peak RPS, daily shape, concurrency profile | Throughput ceiling, VU targets (PERF-DOMAIN-2, PERF-DOMAIN-5) |
| Runtime / language | Build file, package manifest, Dockerfile FROM | Profiling tool selection (PERF-DOMAIN-3) |
| Query text + EXPLAIN output | Raw SQL + `EXPLAIN ANALYZE` or equivalent | Index and query diagnosis (PERF-DOMAIN-4) |
| Cache hit rate + access pattern | Cache metrics, read/write ratio, key cardinality | Cache strategy (PERF-DOMAIN-6) |
| Utilization + saturation metrics | CPU%, thread pool queue depth, connection pool wait, memory pressure | Concurrency diagnosis (PERF-DOMAIN-7) |
| CI baseline history | Stored benchmark results, baseline file location, deviation percentages | Regression gate design (PERF-DOMAIN-8) |
| SLO document | Defined SLIs, error budget %, window | Target validation (PERF-DOMAIN-1, PERF-DOMAIN-2) |

## Section 3 — Opinionated Defaults

Lead with these. Name the recommendation, then the alternative — never a neutral menu.

**Latency targets:**
Default: specify p50, p95, p99 for every latency SLI. Reject average-latency-only targets. The default p99 ceiling for synchronous user-facing requests is 500 ms (HTTP APIs); for async background work 5 s. Alternative: p50 + p99.9 for payment-critical flows.

**Profiling approach by runtime:**

| Runtime | Default tool | Sampling | Alternative |
|---|---|---|---|
| Go | pprof (built-in) | CPU + heap | pyroscope continuous |
| Python | py-spy (sampling, zero-install) | CPU | Scalene (line-level) for data-science paths |
| JVM | async-profiler + JFR | CPU + alloc + lock | JMC for deep memory analysis |
| Node.js | Clinic.js (Doctor + Flame) | CPU + I/O | `--prof` V8 profiler |
| Rust | flamegraph + cargo-flamegraph | CPU | heaptrack for alloc |
| .NET | dotnet-trace + dotnet-counters | CPU + GC | PerfView for Windows |

Default: sampling over instrumentation. Instrumentation only when sampling cannot reproduce the issue.

**Load test tool selection:**

| Team profile | Default | Alternative |
|---|---|---|
| JavaScript / cloud-native | k6 (scripting in JS, native Grafana integration) | Artillery (simpler API) |
| Python-centric | Locust (Python, distributed, live UI) | vegeta (static rate, Go binary) |
| JVM / enterprise | Gatling (Scala DSL, deterministic) | JMeter (GUI-heavy, large plugin ecosystem) |

Default: k6 for new projects unless the team is Python-centric or JVM-native.

**Caching layer default:**

| Use case | Default store | Alternative |
|---|---|---|
| Session, distributed lock | Redis (cluster mode) | Valkey (Redis-compatible OSS fork) |
| Coarse object cache | Memcached (simpler operationally) | Redis |
| CDN-tier, static assets | CloudFront / Fastly | Nginx proxy_cache |
| In-process hot path | local LRU (ristretto/caffeine/functools.lru_cache) | none |

Default invalidation: event-driven (pub/sub on write) + short TTL backstop (5 min). Never TTL-only on write-heavy keys.

**Concurrency bottleneck defaults (USE method):**

- If CPU utilization > 80% sustained: CPU-bound — profile with sampling profiler, look for hot loops and serialization overhead.
- If thread/connection pool queue depth > 0 at saturation: pool-exhausted — increase pool ceiling or reduce downstream latency.
- If CPU is low and latency is high: I/O-bound — look for blocking calls on async paths, missing connection pooling, sequential external calls that should be parallelized.

**CI regression gate default:** percentage-deviation baseline stored in CI artifact or benchmark comparison tool (benchstat, k6 compare, pytest-benchmark). Default threshold: p99 latency deviation > 10% or throughput deviation > 5% triggers FAIL. Never absolute-value thresholds.

## Section 4 — Derivation Rules

| Rule | Prohibition / Requirement | Trigger | Remedy |
|---|---|---|---|
| PERF-D-1 | Latency targets MUST be expressed as percentiles (p50/p95/p99); average-only targets are not accepted | Any SLO or latency budget discussion | Restate as percentile targets |
| PERF-D-2 | VU counts and throughput targets MUST reference production traffic data or an explicitly stated approximation; fabricated numbers are not accepted | Any load test design without traffic evidence | Request traffic data or state approximation explicitly |
| PERF-D-3 | Query optimization MUST NOT be prescribed without EXPLAIN output or query text as evidence | Any index or query recommendation | STOP and request EXPLAIN evidence |
| PERF-D-4 | Caching recommendations MUST include invalidation strategy, TTL, and stampede protection; TTL-only invalidation is not accepted | Any cache design | Add invalidation strategy, TTL backstop, and stampede guard |
| PERF-D-5 | CI regression gates MUST use percentage-deviation baselines against a stored baseline; fixed absolute thresholds are not accepted | Any CI gate design | Replace with percentage-deviation gate |
| PERF-D-6 | Concurrency bottleneck diagnosis MUST identify bottleneck type (CPU-bound, I/O-bound, pool-exhausted) before prescribing a fix | Any concurrency or throughput prescription | Apply USE method classification first |
| PERF-D-7 | Frontend bundle performance concerns (LCP, FCP, CLS, hydration, code splitting) MUST be redirected to frontend-companion | Any frontend metric mention | Redirect explicitly — do not advise |
| PERF-D-8 | Profiling tool selection MUST match the language runtime; cross-runtime tool recommendations are not accepted | Any profiling recommendation | Apply runtime-to-tool mapping from Section 3 |

## Section 5 — Recommendation Output Contract

Every recommendation from an agent consuming this pack MUST carry all four:

1. **Chosen value** — the concrete named decision (e.g. "k6 for load testing", "p99 ≤ 500 ms", "Redis with event-driven invalidation") — never a category label alone.
2. **Rule citation** — the PERF-D-N rule(s) that fired, or "defaults apply" with the Section 3 row cited.
3. **Named alternative** — at least one concrete alternative with a one-sentence when-to-prefer condition.
4. **Override hook** — an explicit instruction telling the user how to override: "To override this recommendation, provide your rationale and I will re-cite any rule changes."

DO NOT emit a neutral option menu. The pack encodes the expertise; the agent applies it and leads with a decision.

## Section 6 — Enforcement Handoff

The PERF-D-* family in Section 4 is the runtime authority; `spec-enricher` maps it to mandatory PERF-1..PERF-8 requirements injected into specs. The `baseline-enforcer` skill gates all output for PII, Opus cost, and audit.

Agent handoffs:
- **Latency budgets / SLO design** → `performance-strategist` cites PERF-D-1.
- **Profiling guidance** → `profiling-guide` cites PERF-D-8; consumes `profiling-guide-pack`.
- **Query / DB performance** → `query-db-advisor` cites PERF-D-3; gates on EXPLAIN evidence.
- **Load test design** → `load-test-strategist` cites PERF-D-2; consumes `load-test-patterns`.
- **Caching design** → `caching-strategist` cites PERF-D-4; consumes `caching-patterns`.
- **Concurrency diagnosis** → `concurrency-advisor` cites PERF-D-6; applies USE method.
- **CI regression gates** → `regression-gate-advisor` cites PERF-D-5.
- **Frontend performance** → NEVER handled here; PERF-D-7 routes to `frontend-companion`.

A recommendation that cannot cite a PERF-D-* rule or a named skill (`profiling-guide-pack`, `load-test-patterns`, `caching-patterns`, `slo-budget-guide`) is out of this pack's scope and must say so rather than inventing guidance.
