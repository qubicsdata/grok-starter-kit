---
name: testing-strategy-craft
description: Import when recommending a test shape (pyramid/trophy/honeycomb), evaluating coverage thresholds, diagnosing suite anti-patterns, or citing a QA-STRAT-D-* rule — consumed by strategy-advisor, coverage-reviewer, and suite-auditor. Leads every recommendation with an opinionated default plus its derivation.
---

# Testing Strategy Craft

## Section 1 — Decision Domains

- **STRAT-1 Test shape selection** — which distribution of test types fits the architecture.
- **STRAT-2 Coverage threshold adequacy** — whether configured thresholds are meaningful or vanity metrics.
- **STRAT-3 "What NOT to test" scoping** — which code categories are excluded from the test budget.
- **STRAT-4 Suite anti-pattern detection** — which structural problems degrade suite value over time.
- **STRAT-5 Recommendation output contract** — what every recommendation from this pack must carry.

## Section 2 — Constraint Inputs

Each decision consumes concrete signals. Gather these before recommending; never recommend a shape or threshold without the input that drives it.

| Input | Signals to read | Drives |
|---|---|---|
| Architecture type | `package.json` (React/Vue/Next), `docker-compose.yml` service count, per-service build files, k8s Deployments, Terraform modules | Test shape (STRAT-1) |
| Module tier | Path/name heuristics: auth, payments, billing, checkout, access-control = critical-path; utils/formatters = supporting; generated/ORM/protobuf = excluded | Coverage thresholds (STRAT-2) |
| Integration seam type | Owned infra (DB/cache/queue) vs external HTTP vs async messaging vs internal inter-team HTTP | Contract-testing tool (see contract-testing-patterns) |
| Flakiness signals | sleeps, threads, random without seed, `now()`, network calls, shared state | Root-cause class (see flakiness-taxonomy) |
| Suite metrics | test-file counts per layer, mocks per test, assertion presence, selector style, CI lane structure | Anti-pattern findings (STRAT-4) |
| Language | file extensions / manifest | Mutation tool (see mutation-testing-guide) |

## Section 3 — Opinionated Defaults

Lead with these. State the recommendation, then the alternative — never a neutral menu.

**Test shape by architecture (default):**

| Architecture type | Recommended shape | Why |
|---|---|---|
| Monolith (single deployable) | Pyramid (Fowler/Cohn) | Unit-heavy maximises feedback rate at low seam count; E2E for critical journeys only |
| Frontend-heavy / JS-dominant / React+API | Trophy (Dodds) | Integration/component tests dominate — they test user-visible behavior at the component boundary |
| Microservices (≥3 independently deployed) | Honeycomb (Spotify) | PRIMARY layer = one service + its OWN real deps (real DB/cache), isolated; cross-service "integrated tests" = AVOID |
| Mixed (monolith + external APIs) | Pyramid + WireMock integration layer | Pyramid base for internal logic; a dedicated stubbed tier isolates external brittleness |

Never invert the honeycomb: a test of one service against its own real DB is an "integration test" (desirable); a test crossing a service boundary is an "integrated test" (avoid).

**Coverage thresholds by module tier (default):**

| Module tier | Line% | Branch% | Mutation | Notes |
|---|---|---|---|---|
| Critical-path (auth, payments, billing, checkout, access-control) | ≥80% | ≥70% | ≥80% required | Mutation is mandatory here; line/branch alone is insufficient |
| Supporting (utils, formatters, validators, mappers) | ≥70% | ≥60% | Not required | Branch coverage catches conditional logic |
| Generated code (ORM, protobuf, SDK bindings, migrations, Lombok) | Exclude | Exclude | Exclude | Excluding avoids inflating aggregate metrics |
| Test infrastructure (fixtures, factories, helpers) | Exclude | Exclude | Exclude | Testing test code is low value |

**Suite anti-pattern catalog (default detections):**

| Anti-pattern | Signal | Fix direction |
|---|---|---|
| Ice cream cone (inverted pyramid) | E2E > integration > unit; thin unit base | Add unit tests for logic; restrict E2E to critical journeys |
| Over-mocking | >3 mocks per test; self-mocking own module | Replace with integration tests / Testcontainers; remove self-mocks |
| Assertion-free tests | test fn with no assertion, or tautological asserts | Add behavioral assertions; delete tests that assert nothing |
| Brittle selectors | XPath, `nth-child`, auto-generated IDs | Use semantic selectors (`getByRole`, `getByLabelText`) |
| Testing implementation details | private-member invocation, internal-state asserts | Test public interfaces and observable outputs only |
| Slow suite without lane separation | all tests in one CI job, no parallelism | Split fast (unit) / slow (integration+E2E) lanes; run fast on every push |

## Section 4 — Derivation Rules

| Rule | Prohibition / Requirement | Trigger | Remedy |
|---|---|---|---|
| QA-STRAT-D-1 | Coverage gate MUST NOT be line% only | `lines` threshold with no `branches` | Add `branches` (≥ line−10pp) |
| QA-STRAT-D-2 | Microservices MUST separate within-service integration from cross-service integrated tests | ≥3 deployed services | Put cross-service tests in a separate CI lane |
| QA-STRAT-D-3 | Every strategy MUST include a "What NOT to Test" section | Always | Unconditional |
| QA-STRAT-D-4 | qa-companion MUST NOT generate test code | Any request for test code | Route to dev-companion:test-generator |
| QA-STRAT-D-5 | Mutation <60% with high line coverage MUST be flagged tautological | mutation<60% and line≥80% | Add assertions that catch injected mutations |
| QA-STRAT-D-6 | A 100% coverage mandate MUST NOT be the gate | any threshold = 100% | Lower to ≥80/≥70; exclude generated code |
| QA-STRAT-D-7 | Pact CDC SHALL NOT be used for public/external/async seams | seam external, public, or async | WireMock (HTTP) / schema registry (async) |
| QA-STRAT-D-8 | Flaky root cause MUST be classified before treatment | diagnosing a flaky test | Apply flakiness-taxonomy first |
| QA-STRAT-D-9 | Quarantined tests MUST have a named owner role + 14-day deadline | a test is quarantined | Role label (not a person) + today+14 |
| QA-STRAT-D-10 | Mutation testing MUST run scheduled, NOT per-commit | recommending mutation cadence | Nightly / pre-release gate only |

## Section 5 — Recommendation Output Contract

Every recommendation from an agent consuming this pack MUST carry all four:

1. **Chosen value** — the concrete named decision (e.g. "Trophy shape", "≥70% branches", "WireMock") — never a category label alone.
2. **Rule citation** — the QA-STRAT-D-N rule(s) that fired, or "defaults apply".
3. **Named alternative** — at least one concrete alternative with a one-sentence when-to-prefer condition.
4. **Override hook** — an explicit instruction telling the user how to override.

DO NOT emit a neutral option menu. The pack encodes the expertise; the agent applies it and leads with a decision.

## Section 6 — Enforcement Handoff

The QA-STRAT-D-* family in Section 4 is the runtime authority; the `spec-enricher` maps it to the mandatory `QA-1..QA-10` requirements injected into specs. Handoffs:

- **Shape / coverage / anti-patterns** → `strategy-advisor`, `coverage-reviewer`, `suite-auditor` cite QA-STRAT-D-* rules directly; the `coverage-thresholds` skill carries the numeric baselines.
- **Flakiness** → `flaky-test-triager` applies the `flakiness-taxonomy` skill (QA-STRAT-D-8, D-9).
- **Contract seams** → `contract-testing-advisor` applies the `contract-testing-patterns` skill (QA-STRAT-D-7).
- **Mutation** → `mutation-advisor` applies the `mutation-testing-guide` skill (QA-STRAT-D-5, D-10).
- **Test code generation** → NOT handled here; QA-STRAT-D-4 routes to `dev-companion:test-generator`.

A recommendation that cannot cite a QA-STRAT-D-* rule or a named sibling skill (`flakiness-taxonomy`, `contract-testing-patterns`, `mutation-testing-guide`, `coverage-thresholds`) is out of this pack's scope and must say so rather than inventing guidance.
