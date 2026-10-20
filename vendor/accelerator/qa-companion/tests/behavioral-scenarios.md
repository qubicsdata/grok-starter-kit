# Behavioral Test Scenarios — qa-companion
Generated: 2026-07-03T00:00:00Z
Coverage: 19 scenarios across 8 agents

---

## Agents covered

| Agent | Scenarios |
|---|---|
| strategy-advisor | 1, 2, 3, 4, 5, 6 |
| coverage-reviewer | 7, 8, 9 |
| flaky-test-triager | 10, 11 |
| suite-auditor | 12, 13 |
| spec-enricher | 14, 15 |
| contract-testing-advisor | 16, 17 |
| mutation-advisor | 18 |
| strategy-doc-writer | 19 |

---

## Scenario 1: strategy-advisor happy path — monolith architecture

**Purpose:** Verify strategy-advisor produces a complete Pyramid recommendation for a Django monolith — confirms architecture, recommends Pyramid shape, cites QA-STRAT-D-*, and includes "What NOT to Test" list.
**Tags:** happy-path, output-format

**Input:**
```
/qa-strategy "Python Django 4.2 REST API monolith. Single PostgreSQL database. Celery background tasks backed by Redis as broker. Ships as one Docker image via one Dockerfile. django-allauth for authentication. Internal user management only. No separately deployed services. No third-party HTTP integrations."
```

**Expected behavior:**
1. Agent outputs an architecture detection block identifying type as "Monolith" with specific signal evidence (single Dockerfile, single deploy unit). Presents: "Is this correct? Reply 'yes' to proceed, or correct the architecture type."
2. STOP — no test shape recommendation appears in this response.
3. After user replies "yes", agent outputs: Recommended shape = Pyramid, cites QA-STRAT-D-* rule, layer guidance for this stack (unit tests for Django views/models/services; integration tests for database interactions; E2E for critical user journeys only), named alternative, override hook.
4. "What NOT to Test" section appears with at minimum: Django ORM-generated SQL, Django middleware internals, trivial model property accessors with no conditional logic, migration files, Celery retry-backoff framework behavior.

**Pass condition:**
- Response 1 contains "Architecture detected: Monolith" and "Is this correct?" with no test shape recommendation text.
- Response 3 (after "yes") contains "Recommended test shape: Pyramid" or equivalent, a QA-STRAT-D-N citation, and a "What NOT to Test" section with ≥5 entries. Output does NOT contain any test code (no `def test_`, `it(`, `describe(`).

---

## Scenario 2: strategy-advisor happy path — microservices architecture

**Purpose:** Verify strategy-advisor recommends Honeycomb shape for a microservices stack and correctly distinguishes within-service integration tests from cross-service integrated tests.
**Tags:** happy-path, output-format

**Input:**
```
/qa-strategy "Node.js microservices stack. docker-compose.yml defines six services: api-gateway (Express 4), auth-service (Express 4 + Redis sessions), product-catalog-service (Express 4 + MongoDB), order-service (Express 4 + PostgreSQL), fulfillment-service (Node.js + PostgreSQL), notification-service (Node.js + SendGrid SDK). Each service has its own package.json and Dockerfile. Services call each other over internal REST HTTP. Each service deploys and scales independently."
```

**Expected behavior:**
1. Architecture detected as "Microservices" citing docker-compose.yml service count (≥3) and per-service build files as signals.
2. Confirmation gate presented before any shape recommendation.
3. After "yes": Honeycomb shape recommended, explicitly distinguishing: "one service + its own real deps" (desired integration tests) versus "cross-service boundary tests" (avoid). Cites QA-STRAT-D-2 for lane separation of cross-service tests, named alternative (e.g. pyramid if most services are trivially thin), override hook.
4. "What NOT to Test" includes: individual service health-check endpoints that the platform monitors, auto-generated OpenAPI client stubs, Docker networking configuration, Kubernetes liveness probe response content.

**Pass condition:**
- Architecture detected as "Microservices" with docker-compose service count signal cited.
- Recommended shape is "Honeycomb" with explicit mention of "integrated test" anti-pattern to avoid.
- QA-STRAT-D-2 cited for cross-service lane separation.
- "What NOT to Test" section present with ≥5 entries.
- No test code in output.

---

## Scenario 3: strategy-advisor happy path — frontend-JS architecture

**Purpose:** Verify strategy-advisor recommends Trophy shape for a Next.js/React frontend-dominant stack.
**Tags:** happy-path, output-format

**Input:**
```
/qa-strategy "Next.js 14 application using React 18 and TypeScript. The backend is implemented entirely as Next.js API routes at /api/**. All user-facing screens are React components rendered in the browser using React Query for data fetching. Authentication is NextAuth.js. One deployment: a single Next.js container serving both the frontend and the API routes. No separately deployed backend service."
```

**Expected behavior:**
1. Architecture detected as "Frontend-heavy / JS-dominant" citing React and Next.js in the same deployable, browser rendering as primary surface.
2. Confirmation gate before any recommendation.
3. After "yes": Trophy shape recommended (Dodds), explaining that integration/component tests dominate (testing user-visible behavior at the component boundary), and E2E for user journeys. Named alternative: Pyramid — prefer if the API route logic is complex and needs heavy unit coverage independent of the UI.
4. "What NOT to Test" includes: exact pixel dimensions and computed CSS values, NextAuth.js session token format, React Query cache invalidation internals, Next.js router internals, auto-generated types from `next/types`.

**Pass condition:**
- Architecture detected as "Frontend-heavy / JS-dominant" with React/Next.js signals cited.
- Recommended shape is "Trophy".
- "What NOT to Test" present with ≥5 entries including at least one React/Next.js-specific exclusion.
- No test code in output.

---

## Scenario 4: strategy-advisor Gate 1B — architecture confirmation blocks early recommendation

**Purpose:** Verify that strategy-advisor never outputs a test shape recommendation before receiving explicit user confirmation of the detected architecture type. Tests the hard gate at Step 1.
**Tags:** hard-gate, output-format

**Input:**
```
/qa-strategy "Express.js REST API with PostgreSQL. The API calls the Stripe payment API and the SendGrid transactional email API. Single Node.js server process. No microservices. Deployed as one Docker container."
```

**Expected behavior:**
The FIRST response from strategy-advisor must contain:
1. An architecture detection block (expected: "Mixed" — monolith + significant external HTTP surface).
2. The exact confirmation prompt: "Is this correct? Reply 'yes' to proceed, or correct the architecture type so I can adjust the recommendation."
3. NO test shape recommendation, NO layer guidance, NO "What NOT to Test" list.

**Pass condition:**
First response contains "Is this correct?" (or the exact gate phrase from the agent spec).
First response does NOT contain "Recommended test shape", "pyramid", "trophy", or "honeycomb" (case-insensitive).
The phrase "What NOT to Test" does NOT appear in the first response.

---

## Scenario 5: strategy-advisor QA-STRAT-D-3 — "What NOT to Test" list always present

**Purpose:** Verify QA-STRAT-D-3 fires unconditionally on every strategy-advisor invocation regardless of architecture type. This is a Java Spring Boot monolith to confirm the constraint is not architecture-specific.
**Tags:** hard-gate, anti-pattern

**Input (two-turn test):**

Turn 1:
```
/qa-strategy "Java 17 Spring Boot 3.2 monolith. Maven build. JPA with Hibernate for PostgreSQL. Spring Security for auth. Single WAR deployed to a single Tomcat server. No microservices."
```

Turn 2 (after architecture confirmation gate):
```
yes
```

**Expected behavior:**
The strategy recommendation output (after "yes") MUST include a "What NOT to Test" section containing at minimum:
- JPA/Hibernate-generated SQL statements
- Lombok-generated builders, equals(), hashCode() methods (if Lombok is in scope; if not, equivalent generated boilerplate)
- Spring framework internals (DispatcherServlet routing, Spring Security filter chain internals)
- Trivial getters/setters with no conditional logic
- Database migration scripts (Flyway/Liquibase)
- At least one Java/Spring-specific entry beyond the universal four

**Pass condition:**
Output contains a section labelled "What NOT to Test" (or equivalent heading).
Section contains ≥5 bullet entries.
At least one entry is specific to Java/Spring (not generic).
No test code appears in the output.

---

## Scenario 6: strategy-advisor cross-link — routes to dev-companion:test-generator for test code requests

**Purpose:** Verify that strategy-advisor refuses to generate test code and explicitly routes to dev-companion:test-generator. QA-STRAT-D-4 applies to all qa-companion agents.
**Tags:** hard-gate, scope

**Input (sent to strategy-advisor after it has completed a strategy recommendation):**
```
Great, now please write the JUnit 5 unit test class for OrderService covering the happy path and the out-of-stock error scenario.
```

**Expected behavior:**
strategy-advisor must NOT produce any test code. It must output a refusal statement that references `dev-companion:test-generator` as the correct agent. The exact phrasing from the agent spec is: "Writing test code is outside qa-companion's scope. Use `/test` (dev-companion:test-generator) for test file generation." Any equivalent refusal citing dev-companion:test-generator is acceptable.

**Pass condition:**
Output does NOT contain `@Test`, `@BeforeEach`, `void test`, `it(`, `describe(`, or any recognizable test function body.
Output contains the string "dev-companion:test-generator" (exact match).

---

## Scenario 7: coverage-reviewer happy path — adequate coverage configuration

**Purpose:** Verify coverage-reviewer correctly interprets a well-configured coverage setup (both lines and branches thresholds at adequate levels) and returns an ADEQUATE posture verdict.
**Tags:** happy-path, output-format

**Prerequisite setup:**
```bash
mkdir -p /tmp/qa-test-adequate && cd /tmp/qa-test-adequate && git init
cat > jest.config.js << 'EOF'
module.exports = {
  collectCoverage: true,
  coverageThreshold: {
    global: {
      lines: 80,
      branches: 70,
      functions: 75,
      statements: 80
    }
  },
  coverageReporters: ['json-summary', 'lcov', 'text']
};
EOF
echo '{"name":"test-project"}' > package.json
```

**Input:**
```
/coverage-review /tmp/qa-test-adequate
```

**Expected behavior:**
Phase 1 finds jest.config.js and extracts threshold values: lines 80%, branches 70%, functions 75%, statements 80%.
Phase 2 reports: no QA-STRAT-D-1 violation (branches threshold IS present), no QA-STRAT-D-6 violation (no 100% mandate).
Posture verdict: ADEQUATE (or notes any remaining gaps without misclassifying the branch presence).

**Pass condition:**
Output contains "Configuration detected" section listing jest.config.js.
Output does NOT contain "VIOLATION [QA-STRAT-D-1]".
Posture verdict is "ADEQUATE" (not "INADEQUATE" or "UNKNOWN").
No test code in output.

---

## Scenario 8: coverage-reviewer Gate 1A — no coverage tooling outputs "not clean"

**Purpose:** Verify that when no coverage configuration files or report files are found, coverage-reviewer emits the mandatory Gate 1A output: "posture is unknown, not clean" — never "clean", never "adequate", never silent.
**Tags:** hard-gate, output-format

**Prerequisite setup:**
```bash
mkdir -p /tmp/qa-test-bare && cd /tmp/qa-test-bare && git init
echo '{"name":"bare-project","version":"1.0.0"}' > package.json
```
(No jest.config.js, no .nycrc, no coveragerc, no vitest.config, no coverage-summary.json, no coverage directory.)

**Input:**
```
/coverage-review /tmp/qa-test-bare
```

**Expected behavior:**
Phase 1 finds no coverage configuration files and no report files.
Agent outputs the Gate 1A block containing:
- "No coverage tooling detected in this repository"
- Explicit statement that coverage posture is "unknown, not clean" (not "clean", not "adequate", not a neutral default)
- Recommended next steps (add coverage tool, configure thresholds, integrate CI gate)
- STOP: does not proceed to Phase 2.

**Pass condition:**
Output contains "No coverage tooling detected" (verbatim or equivalent).
Output contains "unknown, not clean" (or "is unknown" AND "not clean" in close proximity).
Output does NOT contain "ADEQUATE", "PASS", or any phrasing that could be read as a passing posture.
No test code in output.

---

## Scenario 9: coverage-reviewer QA-STRAT-D-1 — line-only coverage gate triggers violation

**Purpose:** Verify that a jest configuration with only a `lines` threshold and no `branches` threshold triggers VIOLATION [QA-STRAT-D-1].
**Tags:** hard-gate, anti-pattern

**Prerequisite setup:**
```bash
mkdir -p /tmp/qa-test-line-only && cd /tmp/qa-test-line-only && git init
cat > jest.config.js << 'EOF'
module.exports = {
  collectCoverage: true,
  coverageThreshold: {
    global: {
      lines: 75,
      statements: 75
    }
  }
};
EOF
echo '{"name":"line-only-project"}' > package.json
```
(No `branches` key in coverageThreshold.)

**Input:**
```
/coverage-review /tmp/qa-test-line-only
```

**Expected behavior:**
Phase 1 detects jest.config.js with lines: 75, statements: 75, and no branches threshold.
Phase 2 flags: "VIOLATION [QA-STRAT-D-1]: Line coverage gate has no branch coverage requirement."
Output includes the gap description: branch coverage misses conditional logic paths entirely.
Output includes a remediation: add `branches` threshold at minimum lines−10pp (i.e., ≥65%).
Posture verdict: INADEQUATE.

**Pass condition:**
Output contains "VIOLATION [QA-STRAT-D-1]".
Output mentions "branches" as missing.
Posture verdict is "INADEQUATE".
No test code in output.

---

## Scenario 10: flaky-test-triager QA-STRAT-D-8 — classification map precedes all treatment

**Purpose:** Verify that the flaky-test-triager outputs the full Classification Map table BEFORE any "Remediation direction" sections. QA-STRAT-D-8 is absolute: classify before verdict.
**Tags:** hard-gate, output-format

**Input (paste the following CI log text directly to flaky-test-triager):**
```
Analyze these CI test failures for flakiness root causes:

FAIL src/services/payment.test.js
  ● PaymentService › processPayment › should charge card
    Error: connect ECONNREFUSED 127.0.0.1:3001
    Timeout: Async callback was not invoked within timeout specified by jasmine.DEFAULT_TIMEOUT_INTERVAL (5000ms).
    at TCPConnectWrap.afterConnect [as oncomplete] (node:net:1300:16)
    at Object.<anonymous> (src/services/payment.test.js:28:5)

FAIL src/utils/dateFormatter.test.js
  ● DateFormatter › formatOrderDate › should format date as YYYY-MM-DD
    expect(received).toBe(expected)
    Expected: "2026-07-03"
    Received: "2026-07-02"
    at Object.<anonymous> (src/utils/dateFormatter.test.js:14:3)

FAIL src/db/userRepository.test.js
  ● UserRepository › findByEmail › should find user
    Error: relation "users" does not exist
    at Object.<anonymous> (src/db/userRepository.test.js:33:7)

Tests: 3 failed intermittently across 10 CI runs
```

**Expected behavior:**
Step 2 produces a Classification Map table as the first major output block, mapping each test/indicator to a Luo 2014 taxonomy category with evidence. Categories expected:
- `payment.test.js` timeout + ECONNREFUSED → Network / Async Wait
- `dateFormatter.test.js` date mismatch → Time / System Resource Usage
- `userRepository.test.js` missing relation → Test Order Dependency / Async Wait (database state not isolated)

Only AFTER the complete Classification Map does the agent emit the Ranked Findings with "Remediation direction" for each category.

**Pass condition:**
Output structure: "## Classification Map" (or equivalent heading with a table) appears BEFORE any "Remediation direction:" label.
All 3 tests appear in the classification map with a Luo 2014 category assigned.
No treatment text ("fix", "remediate", "should", "must change") appears before the classification table is complete.
No test code in output.

---

## Scenario 11: flaky-test-triager QA-STRAT-D-9 — quarantine plan must include owner role and deadline

**Purpose:** Verify that the quarantine plan at the end of every triage report has a named owner role (not a personal name) and a resolution deadline 14 days from today. QA-STRAT-D-9 is absolute.
**Tags:** hard-gate, output-format

**Input:** Same CI log as Scenario 10.

**Expected behavior:**
The triage report ends with a "## Quarantine Plan" section containing a table with these fields:
- "Owner role" — must be a role descriptor (QA Engineer, Backend Engineer, Platform Engineer, or similar) — NEVER a personal name.
- "Resolution deadline" — a specific date (today + 14 calendar days, formatted as YYYY-MM-DD or equivalent).
- "Pipeline status while quarantined" — Non-blocking (skip tag or quarantine suite).
- "Ticket required?" — Yes.

**Pass condition:**
Output contains "## Quarantine Plan" (or equivalent heading) with a table.
"Owner role" field contains a role label (QA, Backend, Platform, etc.) and NOT a personal name (e.g., not "Alice", "Bob", "John").
"Resolution deadline" field contains a date that is exactly 14 days after the date the test is run, or a formula expressing that.
No test code in output.

---

## Scenario 12: suite-auditor happy path — all 6 dimensions addressed (Fired or Abstained-with-reason)

**Purpose:** Verify that suite-auditor addresses all 6 anti-pattern dimensions in every audit. Each dimension must either Fire (with ≥1 finding) or Abstain-with-reason (one explicit sentence). A dimension with no entry is an audit gap and a fail.
**Tags:** happy-path, output-format

**Prerequisite setup:**
Create a minimal test suite with mixed patterns to exercise detection:
```bash
mkdir -p /tmp/qa-test-suite/src/__tests__ /tmp/qa-test-suite/.github/workflows
cd /tmp/qa-test-suite && git init
cat > package.json << 'EOF'
{"name":"test-suite","version":"1.0.0","devDependencies":{"jest":"^29.0.0"}}
EOF
cat > jest.config.js << 'EOF'
module.exports = { testEnvironment: 'node' };
EOF
# Three test files with varying patterns
cat > src/__tests__/order.test.js << 'EOF'
const { jest } = require('@jest/globals');
jest.mock('../services/orderService');
jest.mock('../services/inventoryService');
jest.mock('../db/orderRepository');
jest.mock('../utils/logger');
test('creates order', () => {
  // no assertion
});
EOF
cat > src/__tests__/user.test.js << 'EOF'
test('finds user by email', () => {
  expect(true).toBe(true);
});
EOF
cat > .github/workflows/ci.yml << 'EOF'
name: CI
on: [push]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: npm test
EOF
```

**Input:**
```
/suite-review /tmp/qa-test-suite/src/__tests__
```

**Expected behavior:**
After cost-gate approval, the audit addresses all 6 dimensions:
1. Ice Cream Cone — Abstain-with-reason (only unit tests present, no E2E) OR Fire if distribution is inverted.
2. Over-Mocking — Fire: order.test.js has 4 mock definitions for one test (exceeds the >3 threshold).
3. Assertion-Free Tests — Fire: order.test.js has a test with no assertion; user.test.js has a tautological `expect(true).toBe(true)`.
4. Brittle Selectors — Abstain-with-reason (no UI selector patterns in Node.js test files).
5. Testing Implementation Details — Abstain-with-reason (no private method access patterns found).
6. Slow Suite Without Lane Separation — Fire: .github/workflows/ci.yml runs a single `npm test` step with no lane separation.

**Pass condition:**
Output contains all 6 dimension names (Dimension 1 through Dimension 6, or their labels: Ice Cream Cone, Over-Mocking, Assertion-Free Tests, Brittle Selectors, Testing Implementation Details, Slow Suite Without Lane Separation).
Each dimension has either findings with file:line references OR an "Abstained Dimensions" entry with an explicit one-line reason.
No dimension is silently absent from the output.
No test code suggested in output.
Verdict is either BLOCK (if Critical), PASS WITH WARNINGS (High/Medium), or PASS (Low only).

---

## Scenario 13: suite-auditor QA-STRAT-D-4 — refuses to generate test code

**Purpose:** Verify that suite-auditor (and qa-companion generally) refuses any test code generation request and routes to dev-companion:test-generator. QA-STRAT-D-4 is absolute.
**Tags:** hard-gate, scope

**Input (sent to suite-auditor after it has delivered an audit report):**
```
Based on the Assertion-Free Tests findings, can you write the missing assertions for the order.test.js file? Just show me what the corrected test should look like.
```

**Expected behavior:**
suite-auditor must NOT produce any test code, corrected test functions, or test stubs. It must output a refusal that references `dev-companion:test-generator` as the correct agent for test writing. No partial test code is acceptable — even a "just showing an example" snippet violates QA-STRAT-D-4.

**Pass condition:**
Output does NOT contain `test(`, `it(`, `describe(`, `expect(`, `@Test`, `def test_`, or any test function body.
Output contains "dev-companion:test-generator" (exact match, case-sensitive).
Output contains a clear refusal statement, not just a redirect.

---

## Scenario 14: spec-enricher NOT_APPLICABLE — purely static artifact

**Purpose:** Verify spec-enricher correctly returns NOT_APPLICABLE with a specific reason when the spec describes a purely static artifact with no code logic, no testing surface, and no integration seams.
**Tags:** scope, output-format

**Input (feed the following spec text to spec-enricher):**
```
Replace the application logo in public/images/logo.png with the updated brand logo. The new file is a 400x120 PNG exported from Figma. No code changes. No React component updates. No logic changes. This is a static file replacement only — swap the PNG and redeploy.
```

**Expected behavior:**
spec-enricher outputs:
```
NOT_APPLICABLE
REASON: <specific reason — e.g., "spec describes a static image file replacement with no application logic, no testable behavior, no service integration, and no coverage surface">
```
No QA requirements are emitted. The REASON must be specific about which NOT_APPLICABLE condition matched (purely static artifact / UI copy change with no code).

**Pass condition:**
Output starts with or prominently contains "NOT_APPLICABLE".
Output contains "REASON:" followed by a concrete explanation.
Output does NOT contain "PLUGIN: qa-companion", "QA-1", or any QA requirement lines.

---

## Scenario 15: spec-enricher returns QA-1 through QA-5 for microservices spec with critical paths

**Purpose:** Verify spec-enricher returns QA-1, QA-2, QA-3, QA-4, and QA-5 when the spec describes a microservices feature with payment critical path, inter-service HTTP integration, and no documented test strategy.
**Tags:** happy-path, output-format

**Input (feed the following spec text to spec-enricher):**
```
Feature: E-commerce Checkout Flow

Architecture: Three microservices — order-service (Node.js/Express), payment-service (Node.js/Express with Stripe SDK), inventory-service (Python/Flask). Each service is independently deployed on Kubernetes.

Integration flows:
1. Customer submits cart — order-service receives the request
2. order-service calls inventory-service via HTTP POST /api/v1/reserve-stock to reserve line items
3. order-service calls payment-service via HTTP POST /api/v1/charge to process payment
4. payment-service calls Stripe external API to charge the card

Critical paths: payment processing (charge must be atomic with stock reservation) and inventory reservation (must roll back if payment fails).

Current state: No test strategy has been documented. No coverage gates are configured in any of the three services. No contract testing approach has been defined for the inter-service HTTP calls between order-service, payment-service, and inventory-service.
```

**Expected behavior:**
spec-enricher returns:
```
PLUGIN: qa-companion
APPLIES_BECAUSE: <one concrete sentence naming the trigger — e.g., "spec describes a microservices checkout flow with payment critical path and inter-service HTTP integration seams, with no documented test strategy or coverage gates">
REQUIREMENTS:
- [QA-1] Project MUST define a test shape ...
- [QA-2] Coverage gates MUST use branch coverage ...
- [QA-3] Critical-path modules MUST have mutation scores ...
- [QA-4] Every strategy document MUST include a "what NOT to test" section ...
- [QA-5] Service integration seams MUST have an explicit contract or integration testing approach documented ...
```

All five of QA-1 through QA-5 must be present. QA-6 (flakiness classification) and QA-7 (quarantine) must NOT appear because the spec contains no flakiness signals or quarantine references.

**Pass condition:**
Output contains "PLUGIN: qa-companion".
Output contains "APPLIES_BECAUSE:" with a concrete sentence.
Output contains QA-1, QA-2, QA-3, QA-4, and QA-5 (all five).
Output does NOT contain QA-6, QA-7, or QA-9 (no flakiness, quarantine, or slow suite triggers present in spec).
Output uses mandatory language ("MUST", "SHALL NOT") not guidance language ("consider", "you might").

---

## Scenario 16: contract-testing-advisor happy path — Pact CDC for internal inter-team HTTP

**Purpose:** Verify contract-testing-advisor correctly recommends Pact CDC when the integration scenario matches Branch 4 (internal inter-team HTTP, both teams cooperate, consumer count ≤10). Tests that the agent leads with an opinionated recommendation, not a neutral menu.
**Tags:** happy-path, output-format

**Input:**
```
We have two internal teams. Team A owns the user-service (Node.js REST API). Team B owns the notification-service (Node.js) which calls the user-service's GET /api/users/{id} endpoint to fetch user data for email personalization. Team A is willing to run pact:verify in their CI pipeline. There are 3 consumers total of the user-service. Both teams are on the same Pact Broker instance already. What contract testing approach should we use?
```

**Expected behavior:**
Decision tree Branch 4 matches: internal HTTP, both teams cooperate, consumer count (3) ≤ 10.
Output:
- Recommended tool: Pact CDC
- States "defaults apply" (this is the intended Pact use case)
- Explains: consumer defines contract, provider verifies it in CI via `pact:verify`
- Named alternative: OpenAPI provider-driven contracts — prefer if Team A later refuses the Pact broker workflow
- Override hook present

**Pass condition:**
Output contains "Pact CDC" as the recommended tool.
Output states "defaults apply" or equivalent for the rule citation.
Output contains a named alternative.
Output does NOT recommend Testcontainers or WireMock as the primary choice.
No test code, Pact JSON definitions, or WireMock stub files generated.

---

## Scenario 17: contract-testing-advisor QA-STRAT-D-7 — blocks Pact CDC for async messaging

**Purpose:** Verify contract-testing-advisor refuses to recommend Pact CDC for an async messaging scenario and cites QA-STRAT-D-7. This is an absolute constraint.
**Tags:** hard-gate, anti-pattern

**Input:**
```
We have Kafka-based event streaming. The order-service publishes an OrderPlaced event to the orders Kafka topic (JSON schema: orderId, customerId, items[], totalAmount, currency). The fulfillment-service consumes that topic and triggers warehouse picking. We want to write consumer-driven contract tests using Pact to ensure the OrderPlaced event schema stays backward-compatible when we add new fields. Is Pact CDC the right approach for this Kafka consumer-producer relationship?
```

**Expected behavior:**
Decision tree Branch 3 matches: async messaging (Kafka topic).
Output:
- Does NOT recommend Pact CDC as primary tool
- Explicitly states Pact CDC SHALL NOT be used for async messaging, citing QA-STRAT-D-7
- Recommends: WireMock message stubbing + schema registry validation (or Microcks for AsyncAPI scenarios)
- Alternative: Pactflow Bidirectional Contract Testing — only if both teams have agreed to Pactflow adoption and provider publishes AsyncAPI spec. Noted as NOT a drop-in for standard Pact.
- Override hook present

**Pass condition:**
Output contains "QA-STRAT-D-7" (exact match).
Output does NOT recommend "Pact CDC" as the primary tool.
Output recommends "WireMock" or "schema registry" or "Microcks" as the primary approach.
No Pact JSON files, contract definitions, or stub files generated in output.

---

## Scenario 18: mutation-advisor happy path — Java project

**Purpose:** Verify mutation-advisor detects Java from project signals, selects PiTest, recommends ≥80% mutation score for critical-path modules, and mandates nightly/pre-release cadence (NOT per-commit). QA-STRAT-D-10 must be observed.
**Tags:** happy-path, output-format

**Input:**
```
Our project is a Java 17 Spring Boot 3.2 application built with Maven (pom.xml present). The core business logic lives in src/main/java/com/acme/billing/ — BillingService.java, InvoiceCalculator.java, PaymentProcessor.java. We use JUnit 5 for testing. We want to add mutation testing starting with the billing module. Which tool should we use, what threshold, and how often should we run it?
```

**Expected behavior:**
1. Language detection: Java (from pom.xml signal or .java file extension description).
2. Selected tool: PiTest (PIT) — the mutation tool for Java per the tool selection table.
3. Recommendation output:
   - Critical-path modules (billing/payment): ≥80% mutation score (required, not optional).
   - Supporting modules: ≥60% mutation score.
   - Cadence: nightly or pre-release gate — NOT per-commit. QA-STRAT-D-10 cited or referenced.
   - Scoping: how to limit PiTest to the `com.acme.billing` package only.
   - Alternative: a different approach or tool with one-sentence when-to-prefer.
   - Override hook present.
4. Two most common objections for PiTest addressed (e.g., "too slow for CI" — addressed with scoping and scheduled cadence; "too many equivalent mutants" — addressed with threshold calibration).

**Pass condition:**
Output contains "PiTest" (or "PIT") as the selected tool.
Output specifies ≥80% mutation score for critical-path modules.
Cadence is "nightly" or "pre-release gate" — NOT "per-commit" or "on every push".
Output does NOT say per-commit mutation testing is acceptable.
No mutation configuration files generated (pom.xml edits, pitest plugin config blocks, etc.).

---

## Scenario 19: strategy-doc-writer happy path — write gate blocks premature file write

**Purpose:** Verify that strategy-doc-writer presents the full draft and explicitly requires "confirm" before writing any file. The agent must NOT write docs/qa-strategy/QA-STRATEGY-*.md when the user responds with a non-confirmation phrase.
**Tags:** hard-gate, output-format

**Input (two-turn test):**

Turn 1 — provide assembled advisory outputs:
```
Assemble this session's advisory output into a QA strategy document:

Architecture: Monolith (Django 4.2). Detected signals: single Dockerfile, single PostgreSQL database.
Recommended test shape: Pyramid. Rule: QA-STRAT-D-* defaults apply for monolith. Unit tests for business logic; integration tests against real PostgreSQL; E2E for critical journeys only.
What NOT to Test: ORM-generated SQL, Django middleware internals, Celery retry-backoff framework internals, trivial model property accessors, Flyway migration scripts.
Coverage posture: coverage-reviewer found jest config with lines: 65% only — VIOLATION [QA-STRAT-D-1] flagged. No branches threshold configured.
Flakiness triage: not run this session.
Suite audit: not run this session.
Contract testing: not run this session.
Mutation: not run this session.
```

Turn 2 — respond with a non-confirmation phrase:
```
Looks good to me, this seems fine.
```

**Expected behavior:**
Turn 1: Agent assembles the draft, presents the COMPLETE document (not truncated), and ends with: `Reply "confirm" to write this document to docs/qa-strategy/QA-STRATEGY-[date].md, or provide corrections and I will revise before writing.`
Turn 2 ("Looks good to me, this seems fine."): Agent does NOT write any file. It re-presents the confirmation requirement and waits for an explicit "confirm".

To verify the gate opens correctly, optionally send Turn 3:
```
confirm
```
Expected Turn 3: Agent writes the file to `docs/qa-strategy/QA-STRATEGY-2026-07-03.md` (or current date) and confirms write success.

**Pass condition:**
Turn 1 response ends with the confirmation prompt containing "confirm".
Turn 1 response presents the FULL draft (all sections from the input are visible — no "[content omitted]" truncation).
Turn 2 response does NOT include "Written to" or any confirmation that a file was written.
Turn 2 response re-states the need for explicit "confirm" before writing.
(If Turn 3 is run) File is written to `docs/qa-strategy/` only — NOT to any other path.

---

**Note:** Scenarios 7–9, 10, 12, 13 require local filesystem prerequisites. The exact shell setup commands are included inline. Run them before executing the Claude command. All prerequisite paths use `/tmp/` to avoid contaminating the project repository.
