---
plugin: performance-companion
generated_by: agent-builder:test-agent
generated: 2026-07-03T00:00:00Z
status: complete
---

# Behavioral Test Scenarios — performance-companion
Generated: 2026-07-03T00:00:00Z
Coverage: 20 scenarios across 9 agents (perf-orchestrator, performance-strategist, profiling-guide, query-db-advisor, load-test-strategist, caching-strategist, concurrency-advisor, regression-gate-advisor, perf-doc-writer)

---

## Scenario 1: Happy path — /perf-strategy produces p99-based SLO design

**Purpose:** Verify that performance-strategist produces a complete SLO design with p50/p95/p99 percentile targets, error budget derivation, and burn-rate alerting when given a valid service description.
**Tags:** happy-path, output-format

**Command triggered:** `/perf-strategy`

**Given:** A user-facing Node.js REST API checkout service with no existing SLO. No average latency data is provided — only a description of the service type and current deployment.

**When:**
```
/perf-strategy "Node.js REST API, user-facing checkout flow, 3 endpoints: POST /cart, POST /order, GET /order-status. No SLO defined yet. Deployed on AWS ECS, approximately 800 concurrent users at peak."
```

**Expected behavior:**
- performance-strategist classifies the service as "Interactive HTTP API (user-facing)".
- Output includes a latency budget table with p50, p95, and p99 columns for each endpoint (or service-level aggregate).
- Output cites PERF-D-1 explicitly.
- Output includes an SLO target (e.g., 99.5% rolling 30 days) with monthly and daily error budget in minutes.
- Output includes a burn-rate alerting table with at least two tiers (fast-page and moderate-page or ticket), each with short window, long window, burn rate multiplier, and severity label.
- Output does NOT contain the word "average" as a primary latency metric.
- Output includes a named alternative and override hook per the design spec.

**Pass condition:**
Output contains: (1) a table with p50, p95, p99 columns; (2) the string "PERF-D-1"; (3) a burn-rate alerting section with at least two severity tiers; (4) an error budget stated in minutes. The word "average" must not appear as a latency SLO target.

---

## Scenario 2: Happy path — /profiling-guide recommends Go-appropriate tool

**Purpose:** Verify that profiling-guide correctly detects a Go runtime, recommends pprof (not a cross-runtime tool), and provides sampling-focused setup guidance.
**Tags:** happy-path, output-format

**Command triggered:** `/profiling-guide`

**Given:** A Go service experiencing intermittent high CPU on its /api/process endpoint. No flame graph has been captured yet.

**When:**
```
/profiling-guide "Go service (go1.22), high CPU spikes on /api/process endpoint, happens under load (>500 RPS), intermittent in production. Need guidance on how to capture a profile."
```

**Expected behavior:**
- profiling-guide explicitly states the detected runtime as "Go".
- Recommends `pprof` as the default sampling tool, citing PERF-D-8.
- Does NOT recommend py-spy, async-profiler, Clinic.js, or any non-Go tool.
- Provides setup steps specific to Go (e.g., `import "net/http/pprof"` endpoint or `go tool pprof` command).
- States the overhead percentage for pprof at recommended settings.
- Recommends sampling approach (not instrumentation) for unknown hot path discovery in production.
- Includes flame graph reading guidance (widest frames at top, CPU-on vs CPU-off distinction).

**Pass condition:**
Output mentions "pprof" as the default tool, states "Go" as the detected runtime, cites PERF-D-8, and includes at least one concrete setup command. Output does not mention py-spy, async-profiler, Xdebug, or Clinic.js.

---

## Scenario 3: Happy path — /query-perf analyzes EXPLAIN output and issues index recommendation

**Purpose:** Verify that query-db-advisor produces a specific, evidence-grounded index recommendation when given actual EXPLAIN ANALYZE output showing a sequential scan.
**Tags:** happy-path, output-format

**Command triggered:** `/query-perf`

**Given:** A PostgreSQL EXPLAIN ANALYZE output showing a sequential scan on a large `orders` table.

**When:**
```
/query-perf "EXPLAIN ANALYZE output: Seq Scan on orders (cost=0.00..58432.10 rows=1823410 width=312) (actual time=0.042..3821.445 rows=1823410 loops=1). Query: SELECT * FROM orders WHERE user_id = 12345 AND status = 'pending' ORDER BY created_at DESC LIMIT 20. Table has 1.8M rows."
```

**Expected behavior:**
- query-db-advisor proceeds immediately (EXPLAIN output is present — no EVIDENCE_REQUIRED gate fires).
- Identifies the sequential scan on orders as the primary finding.
- Recommends a composite index on `(user_id, status, created_at)` citing the query pattern.
- The recommended index statement uses `CREATE INDEX CONCURRENTLY` (not `CREATE INDEX` without CONCURRENTLY).
- Recommendation format includes: index statement, reason citing the EXPLAIN node, and index type (B-tree).
- Does NOT recommend caching as a substitute for fixing the scan.

**Pass condition:**
Output contains "CREATE INDEX CONCURRENTLY" with columns from the WHERE and ORDER BY clauses. Output does not contain EVIDENCE_REQUIRED. Output cites the EXPLAIN node (Seq Scan) as the evidence basis.

---

## Scenario 4: Happy path — /load-test derives VU count via Little's Law

**Purpose:** Verify that load-test-strategist correctly derives target VUs using Little's Law from provided production traffic data, selects k6 by default, and specifies open workload model.
**Tags:** happy-path, output-format

**Command triggered:** `/load-test`

**Given:** Production traffic data is available: peak 1200 RPS, p50 response time 65ms. User prefers k6.

**When:**
```
/load-test "Node.js REST API, order processing service, peak 1200 RPS measured from APM, p50 response time 65ms at peak, k6 preferred by team. Need a load test strategy for a pre-release gate."
```

**Expected behavior:**
- cost-gate-agent is invoked before load-test-strategist (visible in execution flow or stated in output).
- load-test-strategist does NOT emit LOAD_DATA_MISSING (production data is provided).
- VU derivation shows the Little's Law calculation: 1200 RPS × 0.065 s = 78 VUs, plus 20% headroom = approximately 94 VUs. The exact arithmetic must appear in the output.
- Recommends k6 as the load test tool (matches user preference and load-test-patterns default for non-Python, non-JVM stacks).
- Specifies open workload model (the default) — not closed model.
- Success criteria uses p95/p99 latency thresholds (not average).
- Does NOT recommend running breakpoint tests in production.

**Pass condition:**
Output shows a VU derivation step that multiplies RPS by response time in seconds. Output contains "open" workload model. Output uses p99 (not "average") for success criteria thresholds. Output mentions k6.

---

## Scenario 5: Happy path — /caching-strategy produces complete three-part recommendation

**Purpose:** Verify that caching-strategist emits a recommendation containing all three mandatory elements: invalidation strategy, TTL (with jitter), and stampede protection.
**Tags:** happy-path, output-format

**Command triggered:** `/caching-strategy`

**Given:** A user profile API with 95% read traffic, Redis cluster available, no caching in place, and profiles updated only on explicit user action (low write frequency).

**When:**
```
/caching-strategy "User profile API, GET /users/{id}, 95% reads, profiles updated only on user action (< 5% write rate), Redis cluster available, no caching currently. 50k daily active users."
```

**Expected behavior:**
- caching-strategist classifies the access pattern as read-heavy.
- Recommends cache-aside as the default pattern, citing PERF-D-4.
- Recommends Redis as the default store.
- Specifies a concrete TTL value (e.g., 5 minutes or justified alternative) with ±10–20% jitter.
- Specifies an invalidation strategy with a named trigger (e.g., "invalidate cache key on user profile update event") — not TTL-only.
- Specifies stampede protection (TTL jitter plus probabilistic early expiry or distributed lock).
- Output includes the completeness check gate: `[invalidation ✓] [TTL ✓] [stampede ✓]` or equivalent.
- Does NOT recommend caching before fixing a query (no query issue is in scope here, so this check is not triggered, but the output must not instruct fixing queries that are not reported as slow).

**Pass condition:**
Output contains all three: a named invalidation trigger event, a TTL value with jitter specification, and a stampede protection mechanism. Output includes "PERF-D-4" or a completeness check marker. Output does not omit any of the three required elements.

---

## Scenario 6: Happy path — /concurrency-review classifies pool-exhausted and prescribes fix

**Purpose:** Verify that concurrency-advisor applies the USE method, classifies the bottleneck as pool-exhausted (not CPU-bound), and prescribes the correct fix sequence.
**Tags:** happy-path, output-format

**Command triggered:** `/concurrency-review`

**Given:** Java Spring Boot service, CPU 38%, connection pool queue depth 180 at peak, p99 latency 4.8s, 16 vCPUs, pool max configured at 10.

**When:**
```
/concurrency-review "Java Spring Boot service, 16 vCPUs, CPU utilization 38% at peak, DB connection pool queue depth 180 (pool max = 10), p99 response time 4.8s under load, error rate < 1%. Getting HikariCP pool timeout exceptions."
```

**Expected behavior:**
- cost-gate-agent is invoked before concurrency-advisor.
- concurrency-advisor applies USE method: states Utilization (CPU 38%), Saturation (pool queue 180), Errors (pool timeouts).
- Classifies bottleneck as pool-exhausted (CPU < 60%, pool queue depth > 0) citing PERF-D-6.
- Does NOT classify as CPU-bound.
- Prescriptions follow classification: (1) reduce downstream latency first, (2) pool ceiling increase using formula `(num_cores × 2) + effective_spindle_count`, (3) backpressure design with 429 Too Many Requests + Retry-After.
- Does NOT recommend "add more threads" as the solution.
- Does NOT recommend horizontal scaling as the first step.
- Pool sizing formula result is shown with numbers.

**Pass condition:**
Output explicitly states "pool-exhausted" as the bottleneck type before any prescription appears. Output contains the pool sizing formula with numerics. Output cites PERF-D-6. Output includes backpressure (429 + Retry-After).

---

## Scenario 7: Happy path — /regression-gate designs percentage-deviation CI gate for GitHub Actions Go service

**Purpose:** Verify that regression-gate-advisor recommends benchstat, GitHub Actions cache for baseline storage, and percentage-deviation thresholds only — no absolute threshold values.
**Tags:** happy-path, output-format

**Command triggered:** `/regression-gate`

**Given:** GitHub Actions CI, Go service with existing `testing.B` benchmarks, no comparison gate configured.

**When:**
```
/regression-gate "GitHub Actions, Go 1.22 service, have testing.B benchmarks in ./bench/ directory, run on every PR but no baseline comparison yet. Want to block PR merge on performance regression."
```

**Expected behavior:**
- regression-gate-advisor detects GitHub Actions as CI provider and Go as runtime.
- Recommends `benchstat` as the comparison tool (appropriate for Go testing.B output).
- Recommends GitHub Actions cache (`bench_baseline_${{ github.base_ref }}`) as the default baseline storage for GitHub Actions.
- Specifies percentage-deviation thresholds: warn at +5% and fail at +10% for p99 latency, warn at −5% and fail at −10% for throughput.
- Does NOT include any fixed absolute threshold (e.g., does not say "fail if p99 > 500ms").
- Provides a CI gate configuration skeleton (GitHub Actions YAML excerpt) with baseline fetch, benchmark run, comparison, and baseline update steps.
- Cites PERF-D-5.
- States explicitly that the gate uses percentage-deviation not absolute thresholds.

**Pass condition:**
Output contains "PERF-D-5", "benchstat", "percentage-deviation" or equivalent phrasing, and a GitHub Actions YAML skeleton. Output does not contain a fixed absolute latency threshold value (no "if p99 > NNN ms" pattern).

---

## Scenario 8: Happy path — /perf-plan orchestrates all 7 specialists and surfaces evidence gaps

**Purpose:** Verify that perf-orchestrator dispatches all 7 specialists in parallel, synthesizes their outputs with proper agent attribution, surfaces evidence gaps prominently, and requires 'confirm' before invoking perf-doc-writer.
**Tags:** happy-path, output-format, hard-gate

**Command triggered:** `/perf-plan`

**Given:** Python Django monolith running user dashboard. Known slow queries mentioned but no EXPLAIN output or query text provided. No SLO defined. GitHub Actions CI. Peak 500 RPS estimated (no APM data).

**When:**
```
/perf-plan "Python Django monolith, user dashboard feature, slow /api/dashboard endpoint (5–8s at peak). No SLO defined. GitHub Actions CI. No APM, estimated 500 RPS peak based on 20k DAU. Redis available but not used for caching."
```

**Expected behavior:**
- perf-orchestrator dispatches all 7 specialists concurrently (not sequentially).
- Synthesis is structured with the canonical sections: Evidence Gaps, Latency Budget, Profiling Approach, Query / Database, Load Test Strategy, Caching Strategy, Concurrency / Throughput, CI Regression Gate.
- Evidence Gaps section prominently lists EXPLAIN_EVIDENCE_MISSING (no query text or EXPLAIN output provided) and LOAD_DATA_MISSING (no APM data, only estimate).
- Every recommendation in the synthesis cites the specialist agent that produced it.
- perf-orchestrator does NOT add new domain recommendations not attributable to a specialist.
- After the synthesis, output shows exactly: "Type 'confirm' to write this plan..." (or equivalent confirm prompt).
- perf-doc-writer is NOT invoked and no file is written during this step.

**Pass condition:**
Synthesis output contains at least 7 named sections. Evidence Gaps section contains EXPLAIN_EVIDENCE_MISSING or equivalent. Synthesis ends with a 'confirm' prompt, not a written file. At least two specialists are cited by name in the body.

---

## Scenario 9: Hard gate — /perf-strategy refuses average-latency SLO request

**Purpose:** Verify that performance-strategist hard-stops when the user requests an SLO expressed as average latency, citing PERF-D-1, and refuses to set average latency as the primary metric.
**Tags:** hard-gate

**Command triggered:** `/perf-strategy`

**Given:** User explicitly requests an average latency SLO target.

**When:**
```
/perf-strategy "Python FastAPI checkout service. We want our SLO to be: average response time under 200ms. Can you design the SLO around that target?"
```

**Expected behavior:**
- performance-strategist detects "average response time" as the requested SLO metric.
- Refuses to set an average latency SLO. STOP fires.
- Explains why average latency hides tail behavior (brief explanation acceptable).
- Cites PERF-D-1.
- Requests the user provide a percentile-based target instead (p95 or p99).
- Does NOT produce any SLO design, burn-rate alerting table, or error budget based on the average latency input.

**Pass condition:**
Output contains "PERF-D-1" and a refusal to use average latency. Output does not contain a latency budget table or burn-rate alerting section derived from the average latency input. Output asks for a p95 or p99 target.

---

## Scenario 10: Hard gate — EVIDENCE_REQUIRED gate fires on /query-perf with no query text

**Purpose:** Verify that query-db-advisor emits EVIDENCE_REQUIRED and stops without prescribing any optimization when neither query text nor EXPLAIN output is provided.
**Tags:** hard-gate

**Command triggered:** `/query-perf`

**Given:** User describes slow database performance vaguely without providing any query text or EXPLAIN output.

**When:**
```
/query-perf "Our database is slow under load. We're seeing high response times on the dashboard page. We're using PostgreSQL with Django ORM. Can you recommend which indexes to add?"
```

**Expected behavior:**
- query-db-advisor detects the absence of both query text and EXPLAIN ANALYZE output.
- Emits EVIDENCE_REQUIRED verbatim (or equivalent structured gate response).
- Provides instructions on what to supply: slow query SQL text, EXPLAIN ANALYZE output, or both.
- Provides the example EXPLAIN ANALYZE command for PostgreSQL.
- Does NOT prescribe any index, query rewrite, or optimization.
- Does NOT guess at which indexes might help based on the vague description.

**Pass condition:**
Output contains "EVIDENCE_REQUIRED" (or the full structured gate message from the agent spec). Output does not contain "CREATE INDEX" or any specific query rewrite recommendation. Output contains an example EXPLAIN command.

---

## Scenario 11: Hard gate — LOAD_DATA_MISSING gate fires on /load-test with no traffic data

**Purpose:** Verify that load-test-strategist emits LOAD_DATA_MISSING and stops without generating VU counts when no production traffic data or approximation basis is provided.
**Tags:** hard-gate

**Command triggered:** `/load-test`

**Given:** User provides only a service description with no traffic metrics and no approximation reasoning.

**When:**
```
/load-test "Node.js Express API for an e-commerce site. We want to load test it before the holiday sale. Can you give us VU targets and a test profile?"
```

**Expected behavior:**
- load-test-strategist detects the absence of production traffic data (no peak RPS, no p50 response time, no concurrent session count).
- Emits LOAD_DATA_MISSING verbatim (or equivalent structured gate response).
- Lists the data that would be needed: peak RPS, p50 response time at peak, or current VU/concurrent session count from APM.
- Explains the APPROXIMATION escape hatch: user may provide explicit reasoning (e.g., DAU-based estimate) labeled as an approximation.
- Does NOT generate any VU count, RPS target, or test profile.
- Does NOT accept the holiday sale context as a basis for guessing VU counts.

**Pass condition:**
Output contains "LOAD_DATA_MISSING" (or the full gate message). Output does not contain any VU count, concrete RPS target, or k6/Locust profile configuration. Output explains what data is needed.

---

## Scenario 12: Hard gate — /regression-gate refuses fixed absolute threshold request

**Purpose:** Verify that regression-gate-advisor refuses to recommend a fixed absolute latency threshold and redirects to percentage-deviation baselines, citing PERF-D-5.
**Tags:** hard-gate

**Command triggered:** `/regression-gate`

**Given:** User explicitly asks for a gate configured with an absolute latency cutoff.

**When:**
```
/regression-gate "GitHub Actions, Go service, want a CI gate that fails if p99 latency exceeds 500ms or if throughput drops below 800 RPS. These are our production SLO values."
```

**Expected behavior:**
- regression-gate-advisor identifies "p99 > 500ms" and "throughput < 800 RPS" as fixed absolute thresholds.
- Refuses to design a gate using fixed absolute values.
- Cites PERF-D-5.
- Explains that fixed absolute thresholds are environment-sensitive (CI runners differ from production) and that percentage-deviation against a stored baseline is the correct approach.
- Proposes the percentage-deviation alternative (e.g., fail if p99 deviates +10% from baseline, fail if throughput deviates −10% from baseline).
- Does NOT produce a gate configuration using "p99 > 500ms" or "RPS < 800".

**Pass condition:**
Output contains "PERF-D-5" and a refusal to use fixed absolute thresholds. Output does not include "500ms" or "800 RPS" as gate fail conditions. Output proposes percentage-deviation thresholds as the alternative.

---

## Scenario 13: Hard gate — /concurrency-review refuses to prescribe without bottleneck classification

**Purpose:** Verify that concurrency-advisor does not prescribe adding threads or scaling out when the bottleneck type cannot yet be classified from the available metrics.
**Tags:** hard-gate

**Command triggered:** `/concurrency-review`

**Given:** User asks to "add more threads to the pool" as the proposed solution. Available metrics include only CPU% (45%) — pool depth is not provided.

**When:**
```
/concurrency-review "Node.js API, CPU around 45%, getting slow responses under load, team wants to increase the thread pool size. How many threads should we add?"
```

**Expected behavior:**
- concurrency-advisor applies the USE method with available data: Utilization (CPU 45%), Saturation (pool depth unknown — not provided), Errors (not stated).
- Does NOT prescribe "add more threads" as the solution.
- States explicitly that the bottleneck type cannot be classified without the pool saturation signal (pool queue depth).
- Requests the missing metric: thread pool or connection pool queue depth at peak.
- Cites PERF-D-6 as the reason for not prescribing before classifying.
- May describe what each bottleneck type would look like (guidance), but must not commit to a fix.

**Pass condition:**
Output does not recommend increasing thread pool size or adding threads. Output contains "PERF-D-6" or equivalent explanation. Output requests pool queue depth or equivalent saturation metric before classifying. Bottleneck type is stated as "unknown" or "cannot classify without saturation data."

---

## Scenario 14: Hard gate — /perf-plan confirm gate prevents write without explicit 'confirm'

**Purpose:** Verify that perf-orchestrator does not invoke perf-doc-writer and does not write any file when the user types something other than 'confirm' after receiving the synthesis.
**Tags:** hard-gate

**Command triggered:** `/perf-plan` (two-turn interaction)

**Given:** User runs /perf-plan and receives a synthesis. Instead of typing 'confirm', the user types approval language that is not the exact word.

**When (turn 1):**
```
/perf-plan "Go gRPC service, internal RPC, 200 RPS peak, p99 currently 900ms, GitHub Actions CI, PostgreSQL database with EXPLAIN output for slow query available."
```
*(User receives synthesis.)*

**When (turn 2):**
```
looks good, write it
```

**Expected behavior:**
- perf-orchestrator does NOT invoke perf-doc-writer after "looks good, write it".
- perf-orchestrator treats the response as a change request or asks the user to type exactly 'confirm'.
- No file is written under docs/performance/ at this point.
- perf-orchestrator re-presents the confirm prompt, making clear the exact word required.

**Pass condition:**
No file is written to docs/performance/ after turn 2. perf-orchestrator output after turn 2 does not contain "WRITE_OK". Output directs the user to type 'confirm' as the exact required input.

---

## Scenario 15: Hard gate — /caching-strategy must not omit stampede protection from output

**Purpose:** Verify that caching-strategist always includes stampede protection in its recommendation — a recommendation lacking this element is a gate failure.
**Tags:** hard-gate, output-format

**Command triggered:** `/caching-strategy`

**Given:** A high-read product inventory cache scenario where multiple clients may simultaneously query an expired key (a classic cache stampede condition). User does not mention stampede protection.

**When:**
```
/caching-strategy "Product inventory count cache, GET /products/{id}/inventory, 98% reads, counts updated on purchase (high-traffic flash sale scenario — counts can spike to 10k reads/sec on a popular item), Redis available. Key expires every 60 seconds."
```

**Expected behavior:**
- caching-strategist recognizes the flash sale / high-concurrent-read pattern as a stampede risk.
- Output includes stampede protection mechanism (probabilistic early expiry, distributed lock, or both) — not just TTL jitter alone.
- Output includes an invalidation strategy (e.g., event-driven on purchase event, not TTL-only given consistency sensitivity).
- Output includes TTL with jitter.
- The completeness gate (all three present) is explicitly confirmed in the output.
- Output cites PERF-D-4.

**Pass condition:**
Output contains all three: an invalidation strategy triggered by a named event (purchase event), a TTL value with jitter, and a stampede protection mechanism beyond simple TTL jitter (e.g., probabilistic early expiry or distributed lock). Completeness marker is present. PERF-D-4 is cited.

---

## Scenario 16: Anti-pattern probe — /load-test rejects user-stated VU count as evidence

**Purpose:** Verify that load-test-strategist does not accept a user's asserted VU count as production data — it must require derivation from measured traffic or an explicitly labeled approximation.
**Tags:** anti-pattern

**Command triggered:** `/load-test`

**Given:** User asserts a VU count based on intuition, with no measured traffic data and no derivation reasoning.

**When:**
```
/load-test "Python FastAPI checkout service. We think 500 VUs should be enough for our load test. Can you help us design the test profiles around 500 VUs?"
```

**Expected behavior:**
- load-test-strategist detects the absence of measured production traffic data supporting the 500 VU assertion.
- Does NOT accept "we think 500 VUs" as a valid basis for a load test design.
- Emits LOAD_DATA_MISSING and explains that VU counts must be derived from production data (RPS × response time via Little's Law) or supplied with an explicit APPROXIMATION label and derivation reasoning.
- Offers the APPROXIMATION escape hatch: if the user provides reasoning such as "estimated 10k DAU × 3 req/session / 60s = ~500 RPS", that labeled approximation is acceptable.
- Does NOT produce any k6 or Locust profile configuration based on the asserted 500 VUs.

**Pass condition:**
Output contains "LOAD_DATA_MISSING" or equivalent refusal. Output does not contain a k6/Locust stage configuration using 500 VUs. Output explains what constitutes a valid evidence basis (measured RPS or labeled APPROXIMATION with derivation).

---

## Scenario 17: Anti-pattern probe — perf-orchestrator must not generate domain content itself

**Purpose:** Verify that perf-orchestrator synthesis does not introduce performance recommendations that are not attributed to any specialist agent — guarding against the workflow-orchestrator anti-pattern of generating domain content instead of routing.
**Tags:** anti-pattern

**Command triggered:** `/perf-plan`

**Given:** A complete /perf-plan run where all 7 specialists return outputs.

**When:**
```
/perf-plan "Go REST API, user-facing order service, peak 600 RPS, p99 currently 1.1s, Redis available, GitHub Actions CI, PostgreSQL with EXPLAIN ANALYZE output attached showing seq scan on orders table."
```

**Expected behavior:**
- perf-orchestrator's synthesis section attributes every recommendation to a named specialist (e.g., "From performance-strategist:", "From query-db-advisor:", etc.).
- The synthesis does NOT contain paragraphs of new performance domain advice introduced by perf-orchestrator itself without specialist attribution.
- If any new content appears in the synthesis that is not attributable to a named specialist, that constitutes a hard gate violation.
- Cross-plugin boundary notes (e.g., "for observability dashboards, consult observability-companion") may appear as routing notes — these are acceptable as they are not domain performance prescriptions.

**Pass condition:**
Every recommendation in the synthesis body cites a specialist agent by name. No section of the synthesis contains unattributed performance prescriptions. The synthesis does not contain new optimization recommendations not found in any specialist's output.

---

## Scenario 18: Domain edge case — /perf-strategy redirects frontend Core Web Vitals to frontend-companion

**Purpose:** Verify that performance-strategist detects frontend-specific metrics (LCP, FCP, CLS) in the SLO scope, refuses to set them as backend targets, and redirects to frontend-companion citing PERF-D-7.
**Tags:** domain, scope

**Command triggered:** `/perf-strategy`

**Given:** User mixes backend service performance and frontend Core Web Vitals in a single /perf-strategy request.

**When:**
```
/perf-strategy "We want to improve overall page load performance. Our targets are: LCP < 2.5s, FCP < 1.8s, CLS < 0.1, and also the backend API p99 < 300ms. Can you design SLOs for all of these?"
```

**Expected behavior:**
- performance-strategist identifies LCP, FCP, and CLS as frontend Core Web Vitals (browser rendering metrics, not backend SLO targets).
- Refuses to design SLOs for LCP, FCP, or CLS as backend performance metrics.
- Explicitly redirects the user to frontend-companion for the Core Web Vitals targets, citing PERF-D-7.
- MAY proceed to design the backend API p99 < 300ms SLO since that is within scope.
- Output clearly separates "within scope" (backend API) from "redirect" (Core Web Vitals).

**Pass condition:**
Output contains "PERF-D-7" and an explicit redirect to frontend-companion for LCP/FCP/CLS. Output does not produce a p50/p95/p99 latency budget table that includes LCP, FCP, or CLS as rows. If a backend SLO is produced, it covers only the API p99 target.

---

## Scenario 19: Domain edge case — /perf-plan synthesis must not silently drop EXPLAIN_EVIDENCE_MISSING flag

**Purpose:** Verify that when query-db-advisor returns EVIDENCE_REQUIRED due to missing EXPLAIN output, perf-orchestrator surfaces this flag prominently in the synthesis rather than silently omitting the database section or presenting partial advice.
**Tags:** domain, hard-gate

**Command triggered:** `/perf-plan`

**Given:** User describes a service with clearly in-scope database performance issues but provides no query text or EXPLAIN output. The query-db-advisor specialist will return EVIDENCE_REQUIRED.

**When:**
```
/perf-plan "Ruby on Rails API, checkout service, slow database queries are the primary bottleneck (confirmed by traces), PostgreSQL backend, no EXPLAIN output available yet. GitHub Actions CI, estimated 300 RPS."
```

**Expected behavior:**
- perf-orchestrator receives EVIDENCE_REQUIRED from query-db-advisor.
- The Evidence Gaps section of the synthesis explicitly lists EXPLAIN_EVIDENCE_MISSING (or EVIDENCE_REQUIRED from query-db-advisor) as a named gap.
- The Query / Database section of the synthesis acknowledges the gap and notes what evidence is needed, rather than presenting a partial query optimization advisory without evidence.
- perf-orchestrator does NOT silently omit the Query / Database section.
- perf-orchestrator does NOT present partial synthesis as if the database section is complete.
- The confirm prompt still appears, but the evidence gap is clearly flagged as requiring resolution before the plan is actionable on the database side.

**Pass condition:**
Synthesis Evidence Gaps section contains a reference to EVIDENCE_REQUIRED or EXPLAIN_EVIDENCE_MISSING from query-db-advisor. The Query / Database section is not silently absent — it is present and explicitly notes the evidence gap. Output does not recommend specific indexes or query rewrites without evidence.

---

## Scenario 20: Out-of-scope rejection — /profiling-guide redirects frontend React profiling to frontend-companion

**Purpose:** Verify that profiling-guide refuses to advise on browser-side or frontend framework profiling and redirects explicitly to frontend-companion citing PERF-D-7.
**Tags:** scope, domain

**Command triggered:** `/profiling-guide`

**Given:** User asks profiling-guide about profiling a slow React component rendering in the browser.

**When:**
```
/profiling-guide "Our React checkout component is rendering slowly — it takes about 2–3 seconds to paint on mobile. I need to profile it. Should I use Chrome DevTools React Profiler or Lighthouse?"
```

**Expected behavior:**
- profiling-guide detects that the symptom is browser-side rendering performance of a React (JavaScript frontend framework) component.
- Refuses to advise on Chrome DevTools, React DevTools Profiler, or Lighthouse.
- Redirects the user explicitly to frontend-companion, citing PERF-D-7.
- Does NOT recommend any browser developer tools or frontend profiling workflows.
- Does NOT attempt to answer the Chrome DevTools vs Lighthouse question.

**Pass condition:**
Output contains "frontend-companion" as a redirect target and "PERF-D-7" as the cited rule. Output does not recommend Chrome DevTools, React DevTools, or Lighthouse. Output does not provide any browser-side profiling workflow.

---

## Coverage Summary

| Scenario type | Count | Source |
|---|---|---|
| Happy path (one per command) | 8 | Scenarios 1–8 |
| Hard gate trigger | 7 | Scenarios 9–15 |
| Anti-pattern probe | 2 | Scenarios 16–17 |
| Domain edge case | 2 | Scenarios 18–19 |
| Out-of-scope rejection | 1 | Scenario 20 |
| **Total** | **20** | |

### Gates and rules exercised

| Rule | Scenario(s) |
|---|---|
| PERF-D-1 (no average latency) | 9, 4, 7 |
| PERF-D-2 (no fabricated VU counts) | 11, 16 |
| PERF-D-3 (EXPLAIN required before prescribing) | 10, 3 |
| PERF-D-4 (caching completeness: invalidation + TTL + stampede) | 5, 15 |
| PERF-D-5 (percentage-deviation not absolute thresholds) | 12, 7 |
| PERF-D-6 (classify bottleneck before prescribing fix) | 13, 6 |
| PERF-D-7 (frontend boundary redirect) | 18, 19, 20 |
| PERF-D-8 (confirm runtime before tool recommendation) | 2 |
| Confirm gate (perf-doc-writer only after 'confirm') | 14, 8 |
| Orchestrator generates domain content (anti-pattern) | 17 |
| Evidence gap surfaced in synthesis (anti-pattern) | 19 |
