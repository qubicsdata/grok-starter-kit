---
# <!-- perf-provenance: performance-companion v1.0.0 2026-07-03 -->
name: load-test-patterns
description: Import when selecting a load testing tool, modeling workload shape, or defining ramp/soak/spike profiles — ensures VU targets are grounded in production traffic data and workload model is explicitly chosen.
---

# Load Test Patterns

## Tool Selection Matrix

| Primary signal | Default tool | Rationale | Alternative |
|---|---|---|---|
| JavaScript / cloud-native team | k6 (Grafana) | JS scripting, native cloud execution, Grafana dashboard integration, GitHub Actions friendly | Artillery (simpler YAML API, good for short tests) |
| Python-centric team | Locust | Python scripting, distributed master-worker, live web UI, custom user behaviors | vegeta (CLI, static rate, Go binary — good for scripted pipelines) |
| JVM / enterprise | Gatling | Scala DSL, deterministic assertions, CI-first design, strong reporting | JMeter (large plugin ecosystem, GUI-first but scriptable via CLI) |
| HTTP protocol only, scripted pipelines | wrk / wrk2 | Minimal overhead, Lua scripting, single-binary | hey (simpler, no scripting) |
| gRPC services | ghz | Purpose-built gRPC load tester, protobuf-aware | k6 with xk6-grpc extension |

**Default for new projects: k6.** Override only if the team is Python-centric (use Locust) or JVM-native (use Gatling).

## Open vs Closed Workload Model

**This choice must be explicit in every load test design.** Conflating the two produces misleading results.

| Model | Description | When to use | Tool support |
|---|---|---|---|
| **Open** | New virtual users arrive at a constant (or shaped) rate independent of system response time. Rate = arrivals/sec. | Simulating real-world user traffic — users don't wait for the system before a new user arrives | k6 `open` model, Locust (default), Gatling `atOnceUsers` / `rampUsers`, wrk |
| **Closed** | A fixed pool of VUs loops continuously; new requests start only after the prior one completes. Response time increases reduce throughput automatically. | Connection pools, thread pools, queue-depth scenarios | k6 VU loop (default), JMeter thread groups |

**Default: open model** for HTTP API load tests simulating web traffic. Use closed model only when modeling a bounded concurrency resource (thread pool, connection pool).

## Profile Templates

### Ramp Profile (baseline discovery)
```
Stage 1 — 0 → target_rps over 5 min     (warm-up, find first bottleneck)
Stage 2 — hold target_rps for 10 min    (steady-state validation)
Stage 3 — target_rps → 0 over 2 min     (cool-down)
```
Purpose: discover where the system first saturates.

### Soak Profile (reliability/memory)
```
Stage 1 — 0 → 70% target_rps over 5 min
Stage 2 — hold 70% target_rps for 60–120 min
Stage 3 — ramp down over 5 min
```
Purpose: detect memory leaks, connection exhaustion, GC pressure over time.

### Spike Profile (elasticity)
```
Stage 1 — 0 → 10% target_rps over 1 min
Stage 2 — 10% → 300% target_rps in 30 s   (the spike)
Stage 3 — 300% → 10% target_rps in 30 s   (recovery)
Stage 4 — hold 10% for 5 min              (stability after recovery)
```
Purpose: test autoscaling, circuit breakers, and graceful degradation.

### Breakpoint Profile (capacity ceiling)
```
Stage 1 — Ramp continuously: 0 → 200% target_rps over 20–30 min
Observe: error rate, latency degradation, first hardware saturation
Stop: when error rate exceeds 5% or p99 > 3x SLO
```
Purpose: find the system's actual capacity ceiling.

## VU Target Derivation

**DO NOT fabricate VU counts.** Derive from production traffic data:

1. Obtain peak RPS (requests per second) from APM or access logs.
2. Obtain average request duration (p50 latency in seconds) at peak.
3. Apply Little's Law: `VUs ≈ peak_RPS × avg_response_time_seconds`
4. Add a safety margin: `target_VUs = VUs × 1.2` (20% headroom).
5. If no production data exists: state the approximation explicitly as `APPROXIMATION: [assumption]`.

## Hard Gates

**STOP if no production traffic data or explicit approximation is provided** — do not invent VU counts or RPS targets.
**DO NOT use closed model without stating why** — open model is the default; closed model requires explicit bottleneck justification.
**DO NOT run breakpoint tests in production** — always on a staging environment sized to production.
**NEVER report load test results without specifying which profile was run** (ramp/soak/spike/breakpoint).
