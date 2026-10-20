---
name: contract-testing-patterns
description: Import when choosing between Pact CDC, Testcontainers, WireMock, or OpenAPI provider-driven contracts for an integration seam, or when enforcing QA-STRAT-D-7 Pact exclusion conditions — consumed by contract-testing-advisor.
---

# Contract Testing Patterns

## Section 1 — Decision Framework

Apply these branches IN ORDER. Stop at the first match.

| Priority | Seam type | Correct tool | Key condition |
|---|---|---|---|
| 1 | Owned dependency (DB, cache, queue, broker the team runs) | Testcontainers | Team owns and deploys the dependency |
| 2 | External or third-party HTTP (public API, vendor, SaaS) | WireMock (or MockServer, nock, msw) | Provider will not run pact:verify |
| 3 | Async messaging (AMQP, Kafka, SNS, SQS, EventBridge, any message bus) | WireMock message stubbing + schema registry validation; or Microcks | QA-STRAT-D-7: Pact blocked |
| 4 | Internal inter-team HTTP where BOTH teams cooperate and consumer count ≤ 10 | Pact CDC | Both teams adopt Pact broker; provider runs pact:verify in CI |
| 5 | Internal HTTP; provider has authoritative OpenAPI spec; won't run Pact | OpenAPI provider-driven contracts | Provider publishes spec; consumer validates client against spec |

**Decision gate:** If none of branches 1–5 match, the seam type is ambiguous — ask the user to clarify whether the dependency is owned/external, HTTP/async, and whether the provider team can cooperate with a Pact workflow.

## Section 2 — Tool Profiles

### Pact CDC (Consumer-Driven Contract Testing)

**When to use:**
- Internal inter-team HTTP, both teams cooperate
- Provider team can and will run `pact:verify` in their CI pipeline
- Consumer count is ≤ 10 (each consumer adds a verification obligation on the provider)
- Both teams have adopted or will adopt the Pact broker

**When NOT to use (QA-STRAT-D-7):**
- Public or external APIs (provider will not cooperate)
- Third-party vendors (Stripe, Twilio, Salesforce, etc.)
- Async messaging (AMQP, Kafka, SNS, SQS, EventBridge) — Pact messaging has very limited production adoption outside Pactflow
- Provider has >10 consumers (broker verification overhead becomes prohibitive)
- Provider team explicitly refuses to run `pact:verify`

**Key concepts:**
- Consumer writes a pact (JSON file defining the interactions they expect)
- Pact broker stores and versions pacts
- Provider runs `pact:verify` against the stored pact in CI
- Can-I-deploy gate: consumer cannot deploy unless provider verification is green

**Configuration pointers:**
- Pact broker: Pactflow (SaaS) or self-hosted open-source broker
- Consumer framework: `@pact-foundation/pact` (JS), `au.com.dius:pact-jvm` (Java), `pact-python` (Python)
- Provider verification: `pact:verify` Gradle/Maven task; Jest/Vitest provider verifier

---

### Testcontainers

**When to use:**
- The integration seam is an infrastructure dependency the team owns: PostgreSQL, MySQL, MongoDB, Redis, RabbitMQ, Kafka, Elasticsearch, MinIO
- Real wire-protocol behavior is needed (query planner, transaction semantics, queue acknowledgement)

**When NOT to use:**
- Third-party HTTP APIs — Testcontainers is for infrastructure, not HTTP service contracts
- In environments where Docker is not available (some CI runners, some corporate security policies)
- When test execution speed is more critical than realistic dependency behavior

**Key concepts:**
- Spins up real Docker containers for the dependency during the test run
- Container lifecycle is managed per-test-class or per-test-suite
- Data is isolated per container instance; no shared state between test runs
- JUnit 5 extension (`@Testcontainers`, `@Container`) or manual lifecycle management

**Configuration pointers:**
- Java: `org.testcontainers:testcontainers`, `org.testcontainers:junit-jupiter`
- Python: `testcontainers-python`
- Node.js: `testcontainers` npm package
- Pre-built modules: `PostgreSQLContainer`, `KafkaContainer`, `RedisContainer`, `RabbitMQContainer`

---

### WireMock

**When to use:**
- External/third-party HTTP APIs the team does not control
- Async messaging scenarios where schema registry validation is insufficient
- Any HTTP integration where the provider won't adopt Pact
- Deterministic testing of error conditions, rate limits, timeouts from external APIs

**When NOT to use:**
- Owned infrastructure dependencies (use Testcontainers instead for realism)
- Internal inter-team APIs where both teams cooperate (Pact CDC is more valuable — it provides provider-side verification, not just consumer-side mocking)

**Key concepts:**
- HTTP stub server that records or hand-authors expected request/response pairs
- Stubs can be defined statically (JSON) or programmatically (Java DSL, REST API)
- Supports recording mode: proxy to real service, capture interactions, replay deterministically
- Supports fault injection: latency, connection resets, 5xx responses
- WireMock Cloud provides hosted stub management

**Configuration pointers:**
- Java: `com.github.tomakehurst:wiremock-jre8` or `com.github.tomakehurst:wiremock`
- JUnit 5: `@WireMockTest` extension
- Node.js: `wiremock` npm package, `nock`, or `msw` (Mock Service Worker)
- Python: `responses`, `httpretty`, or `wiremock-python`

---

### OpenAPI Provider-Driven Contracts

**When to use:**
- Provider has an authoritative, maintained OpenAPI spec (not auto-generated from code)
- Provider will not adopt Pact broker but is willing to validate their implementation against the spec
- Consumer wants to validate their HTTP client against the published spec
- API-first development workflow where the spec is the contract source of truth

**When NOT to use:**
- Provider spec is auto-generated from code and does not lead design (spec follows code rather than driving it)
- No spec exists and the provider won't maintain one
- The relationship is owned-infra rather than HTTP service (use Testcontainers)

**Key concepts:**
- Provider validates their implementation against the spec using schema validation and example testing
- Consumer validates their HTTP client using the spec via contract test libraries
- Tools: Schemathesis (property-based spec testing), Dredd (example-based), OpenAPI-sampler
- Spec acts as the shared source of truth — no broker required

**Configuration pointers:**
- Consumer: Schemathesis, Dredd, or Pact Bidirectional Contract Testing (BDCT) with OpenAPI spec
- Provider: Schemathesis against the provider's running server; ensure spec stays authoritative (code-gen must not overwrite hand-authored spec)

---

## Section 3 — QA-STRAT-D-7 Exclusion Conditions

**Pact CDC SHALL NOT be used when ANY of the following is true:**

1. The API provider is a third-party or public service (Stripe, GitHub, Twilio, SendGrid, AWS services, any SaaS product) — the provider will not run `pact:verify`
2. The integration seam is asynchronous messaging (Kafka topics, AMQP queues, SNS, SQS, EventBridge, any message bus) — Pact's async support is niche and requires Pactflow
3. The provider team has explicitly declined to adopt the Pact broker or to run `pact:verify` in their CI
4. Consumer count exceeds 10 — verification overhead becomes prohibitive for the provider
5. The provider has no control over the Pact broker (external system, no operational access)

When any condition above is true, the correct tool is WireMock (for HTTP) or schema registry validation (for async messaging).

**Override:** A team may override conditions 3–5 with explicit written justification and team-lead sign-off. Conditions 1 and 2 are absolute — external providers and async messaging cannot be overridden to Pact CDC.

## Section 4 — Recommendation Output Contract

Every recommendation from contract-testing-advisor MUST include these four elements:

1. **Chosen tool** — the concrete named tool (Testcontainers / WireMock / Pact CDC / OpenAPI provider-driven), not a category
2. **Rule citation** — the QA-STRAT-D-N rule or "defaults apply" if no specific rule fired
3. **Named alternative** — at least one concrete alternative tool with a one-sentence when-to-prefer condition
4. **Override hook** — explicit instruction to the user on how to provide a blocker so the recommendation can be re-evaluated

DO NOT present a neutral menu of all four tools. Apply the decision framework. Lead with the chosen tool.
