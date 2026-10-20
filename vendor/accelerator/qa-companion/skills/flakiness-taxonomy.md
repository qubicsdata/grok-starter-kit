---
name: flakiness-taxonomy
description: Import when classifying a flaky test's root cause, building a quarantine plan, or enforcing QA-STRAT-D-8 (classify before treatment) or QA-STRAT-D-9 (quarantine with owner and deadline) — consumed by flaky-test-triager.
---

# Flakiness Taxonomy

## Section 1 — Luo 2014 Taxonomy

Based on "An Empirical Analysis of Flaky Tests" (Luo et al., 2014). Classify every flaky indicator into exactly one category.

### Category 1: Async Wait

**Description:** The test does not properly synchronise with an asynchronous operation. The assertion fires before the async work completes, producing a race between test code and the system under test.

**Detection signals:** `setTimeout`, `setInterval`, `sleep`, `Thread.sleep`, `time.sleep`, `await` on a non-awaited promise, polling loops without completion checks, `waitFor` absent where it should be present.

**Remediation direction:** Replace fixed sleeps with deterministic waits. Use `waitFor` (RTL), `cy.wait()` with alias (Cypress), `async/await` with proper Promise resolution, or condition-based polling with a timeout. Never use `sleep(N)` as a substitute for a real completion signal.

---

### Category 2: Concurrency

**Description:** The test exercises or depends on concurrent execution paths. Race conditions, deadlocks, or non-deterministic thread interleaving cause different outcomes on different runs.

**Detection signals:** `Thread`, `ExecutorService`, `async`, `Promise.all`, `concurrent`, `parallel`, `synchronized`, thread pools, `@Async` annotations, worker threads, `multiprocessing`.

**Remediation direction:** Isolate concurrency from the test by making the component synchronous in test mode, or by controlling thread scheduling (test executors, single-threaded dispatchers). Do not suppress the race — expose and control it.

---

### Category 3: Test Order Dependency

**Description:** The test relies on state established by a previously run test. When test execution order changes, the implicit dependency breaks and the test fails.

**Detection signals:** Shared module-level variables modified by tests, `beforeAll`/`afterAll` state not cleaned up, database records left from a prior test, global singletons, shared fixtures without isolation.

**Remediation direction:** Each test must set up its own preconditions and tear down after itself. Use `beforeEach`/`afterEach` (not `beforeAll`/`afterAll`) for state that must be isolated. Use database transactions rolled back after each test. Use dependency injection to swap shared singletons per-test.

---

### Category 4: Resource Leak

**Description:** The test acquires a resource (file handle, DB connection, network socket, port, temp file) and does not release it. Subsequent tests on the same resource fail.

**Detection signals:** `open(`, `File(`, `new FileInputStream(`, `socket.bind(`, `listen(`, temp file creation without cleanup, DB connections opened in test body without `with` / `try-finally`, no `afterEach` cleanup for acquired resources.

**Remediation direction:** Use `try/finally` or `with` blocks (Python context managers), `afterEach`/`afterAll` cleanup, database connection pooling with automatic release, and temp file cleanup hooks. For ports, use random port assignment.

---

### Category 5: Network

**Description:** The test makes real network calls to external endpoints. Network latency, DNS lookup failures, rate limiting, service outages, or connection resets cause non-deterministic failures.

**Detection signals:** `fetch(`, `axios.get(`, `http.get(`, `requests.get(`, hard-coded external URLs (not localhost), HTTP calls to third-party domains in test code.

**Remediation direction:** Stub all network calls with WireMock, nock, msw, responses, or an equivalent HTTP mock. Seal the test from the network. If real network calls are required (integration tests), run them in a separate slow lane with appropriate retry and timeout configuration.

---

### Category 6: Time

**Description:** The test depends on the system clock — real timestamps, time zones, date arithmetic, or elapsed time windows — producing different behavior at different wall-clock times.

**Detection signals:** `new Date()`, `Date.now()`, `datetime.now()`, `LocalDateTime.now()`, `System.currentTimeMillis()`, time zone assumptions, date string formatting without explicit locale or zone, `cron`-based triggers in tests.

**Remediation direction:** Inject a clock interface and use a fake/controllable clock in tests. Never call system clock directly in production code that must be tested; always inject the time source. For date arithmetic, use a fixed reference date in tests.

---

### Category 7: IO

**Description:** The test reads from or writes to the filesystem in a way that depends on prior state, available disk space, file ordering, or platform path conventions.

**Detection signals:** `fs.readFile`, `open(path)`, `File(path).exists()`, temp file paths that are shared across tests, relative path assumptions (`./`), file sort order dependencies.

**Remediation direction:** Use per-test temp directories (unique per test run), clean up in `afterEach`, use absolute paths, and avoid platform-specific path assumptions. For tests that read fixtures, embed fixture data in the test or use a test-scoped resource directory.

---

### Category 8: Randomness

**Description:** The test uses random number generation without a fixed seed, producing non-deterministic data that causes assertions to pass sometimes and fail other times.

**Detection signals:** `Math.random()`, `random.randint()`, `faker`, `uuid()` (without seed), `Faker()` (without seed parameter), UUID generation in test assertions without tolerance for variability.

**Remediation direction:** Always seed random generators in tests. Use a fixed seed for repeatable test data. For UUID generation, mock or inject the UUID generator and return a fixed value in tests. For property-based tests, document the seed in the test output.

---

### Category 9: Floating Point

**Description:** The test asserts exact equality on floating-point values that are subject to precision differences across platforms, JVM versions, or CPU architectures.

**Detection signals:** `assertEquals(0.1 + 0.2, 0.3)` or equivalent exact float equality; `toBe(3.14159...)` on a calculated float; raw division results compared to exact decimal literals.

**Remediation direction:** Use approximate equality assertions with an explicit epsilon: `assertApproximatelyEqual(actual, expected, epsilon)`, `toBeCloseTo(value, numDigits)` (Jest), `pytest.approx()`. Never use exact equality for floating-point arithmetic results.

---

### Category 10: Unordered Collections

**Description:** The test iterates over a map, set, or dictionary and asserts on the iteration order, which is not guaranteed to be stable across runs or JVM versions.

**Detection signals:** Assertions on the order of `.keys()`, `.values()`, `.entrySet()`, Python dict iteration order (pre-3.7), Set iteration order, JSON object key order assertions.

**Remediation direction:** Sort collection output before asserting, or use order-independent matchers (`containsInAnyOrder`, `toEqual(expect.arrayContaining([]))`, set equality). If ordering matters, use an explicitly ordered collection type.

---

## Section 2 — Quarantine Template

Use this template for every quarantine plan. Populate all fields.

```
## Quarantine Plan

| Field | Value |
|---|---|
| Tests to quarantine | [list of test names or IDs] |
| Luo 2014 category | [category name from taxonomy] |
| Owner role | [QA Engineer / Backend Engineer / Platform Engineer / Frontend Engineer — role only, not a person's name] |
| Resolution deadline | [today's date + 14 days, formatted YYYY-MM-DD] |
| Pipeline status while quarantined | Non-blocking — apply skip tag or move to quarantine suite |
| Annotation required | Yes — link quarantine ticket in the skip annotation comment |
| Escalation if unresolved by deadline | Raise in team retrospective; re-evaluate test value vs removal cost |
| Ticket URL | [leave as placeholder — team fills in] |
```

DO NOT name a specific person as the owner. Always use a role label.

## Section 3 — Quarantine Governance

**Quarantine size as a team health metric:**
The number of quarantined tests is a leading indicator of test suite health. A growing quarantine is a signal that root causes are not being addressed — not a normal operating state.

**Maximum quarantine age:**
No quarantined test should remain quarantined for more than 14 calendar days without an escalation event. After 14 days without resolution, the options are:
1. Fix it (preferred)
2. Delete it (if test coverage is redundant or the scenario is no longer relevant)
3. Escalate to team lead for prioritisation

**Required dashboard tracking:**
Teams with >5 quarantined tests should track quarantine count in the sprint dashboard. A quarantine count that grows sprint-over-sprint is a process failure indicator requiring a dedicated retrospective item.

DO NOT treat quarantine as a long-term holding state. Quarantine is a two-week window, not a permanent category.
