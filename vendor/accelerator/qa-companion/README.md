# qa-companion

Test and QA strategy companion for the Claude Code accelerator fleet. The advisory layer above individual test authorship — covering test shape selection, coverage posture review, flakiness triage, suite anti-pattern auditing, contract testing guidance, and mutation testing planning.

**Advisory only.** qa-companion never writes test code, test file stubs, or test configuration. For test file generation, use `dev-companion:test-generator` (`/test`).

---

## Commands

| Command | Argument | Agent | Description |
|---|---|---|---|
| `/qa-strategy` | `"stack or project description"` | strategy-advisor | Detects architecture type, confirms with user, recommends test shape (pyramid/trophy/honeycomb), coverage approach, and "what NOT to test" list |
| `/coverage-review` | `[path]` | coverage-reviewer | Locates coverage tooling and report files; flags line-only gates, 100% mandates, and missing mutation requirements for critical-path modules |
| `/flaky-triage` | `[test-output or path]` | flaky-test-triager | Classifies flaky test root causes using the Luo 2014 taxonomy and produces a quarantine plan |
| `/suite-review` | `[path]` | suite-auditor | Adversarial audit of 6 suite anti-patterns (ice cream cone, over-mocking, assertion-free, brittle selectors, implementation details, slow suite without lane separation). Invokes cost-gate before Opus dispatch. |
| `/contract-test` | `"integration scenario description"` | contract-testing-advisor | Recommends Testcontainers, WireMock, Pact CDC, or OpenAPI contracts for a described integration seam |
| `/mutation-advice` | `[module path or description]` | mutation-advisor | Detects language, selects mutation tool (PiTest/Stryker/Stryker.NET/mutmut), and recommends threshold and cadence |

---

## Quick-Start Examples

```bash
# Get a test strategy recommendation for a Node.js microservices project
/qa-strategy "Node.js API with React frontend, 3 microservices communicating over HTTP and Kafka"

# Review coverage configuration in the current repo
/coverage-review ./

# Triage a flaky test failure from CI logs
/flaky-triage ./ci-logs/test-run-2026-07-03.txt

# Audit the test suite for anti-patterns
/suite-review ./src/__tests__

# Get contract testing guidance for a payment service integration
/contract-test "checkout-service calling payment-service over internal HTTP, both teams internal, 3 consumers"

# Get mutation testing recommendation for the auth module
/mutation-advice ./src/auth
```

---

## Agents

| Agent | Model | Write? | Description |
|---|---|---|---|
| strategy-advisor | claude-sonnet-4-6 | No | Architecture detection + test shape recommendation + "what NOT to test" |
| coverage-reviewer | claude-sonnet-4-6 | No | Two-phase coverage posture review: parse config, analyse against thresholds |
| flaky-test-triager | claude-sonnet-4-6 | No | Luo 2014 taxonomy classification + quarantine plan |
| suite-auditor | claude-opus-4-8 | No | Adversarial 6-dimension suite audit; cost-gated |
| contract-testing-advisor | claude-sonnet-4-6 | No | Four-branch contract testing decision framework |
| mutation-advisor | claude-sonnet-4-6 | No | Language detection + mutation tool + threshold + cadence |
| strategy-doc-writer | claude-sonnet-4-6 | Yes — after explicit confirm | Assembles session advisory outputs into `docs/qa-strategy/` |
| spec-enricher | claude-haiku-4-5-20251001 | No | Injects qa-companion requirements (QA-1 through QA-10) during `/enrich` runs |
| audit-trail-agent | claude-haiku-4-5-20251001 | Yes — append-only | Writes structured JSONL entries to `.ai-baseline/audit.YYYY-MM-DD.jsonl` |

---

## Skills

| Skill | Consumed by |
|---|---|
| testing-strategy-craft | strategy-advisor, coverage-reviewer, suite-auditor |
| flakiness-taxonomy | flaky-test-triager |
| contract-testing-patterns | contract-testing-advisor |
| mutation-testing-guide | mutation-advisor |
| coverage-thresholds | coverage-reviewer |
| baseline-enforcer | All agents except spec-enricher and audit-trail-agent |

---

## Dependencies

- requires: ai-baseline

qa-companion relies on ai-baseline for:
- `audit-trail-agent` — JSONL audit logging for cost attribution and observability
- `cost-gate-agent` — pre-Opus budget check (mandatory before suite-auditor runs)
- `baseline-enforcer` skill — imported by every authored agent at session start

---

## Cross-Links

**For test code generation** (qa-companion does not write test code):
- `/test` — `dev-companion:test-generator` generates test files in the project's existing framework and style

**For language-specific test idioms**:
- `polyglot-companion` covers per-language testing conventions (Python pytest idioms, Java JUnit 5 patterns, Go table-driven tests, etc.)

**For CI/CD pipeline setup**:
- `ops-companion:pipeline-designer` generates CI pipeline configuration including test lane separation

**For spec enrichment**:
- qa-companion's `spec-enricher` is auto-invoked by `ai-baseline:enrich-orchestrator` during `/enrich` runs. It injects QA-1 through QA-10 requirements into specs that describe testable deliverables, critical-path flows, or integration seams.

---

## Boundaries — What qa-companion Does NOT Do

| Out of scope | Where to go instead |
|---|---|
| Writing test code, test files, or test suites | `/test` (dev-companion:test-generator) |
| Generating CI pipeline YAML | `/pipeline` (ops-companion:pipeline-designer) |
| Security testing strategy | `/security` (dev-companion:security-reviewer) |
| Performance/load testing strategy | Not currently in fleet — raise as a feature request |
| Running tests or executing test commands | Use Bash directly; qa-companion is advisory only |
| Writing WireMock stub files or Pact JSON | Advisory only; stubs are generated by the developer or test tooling |
| Reviewing test code for correctness | `/review` (dev-companion:code-reviewer) covers test code in a diff |

---

## Key Rules

The following rules are enforced across all qa-companion agents and are cited explicitly in every recommendation:

- **QA-STRAT-D-1:** Coverage gates MUST include branch coverage, not line% alone
- **QA-STRAT-D-3:** Every strategy document MUST include a "What NOT to Test" section
- **QA-STRAT-D-4:** qa-companion NEVER generates test code — absolute
- **QA-STRAT-D-6:** 100% coverage mandates are an anti-pattern
- **QA-STRAT-D-7:** Pact CDC is blocked for external APIs and async messaging
- **QA-STRAT-D-8:** Flaky test root cause MUST be classified before treatment
- **QA-STRAT-D-9:** Quarantined tests MUST have an owner role and a 14-day deadline
- **QA-STRAT-D-10:** Mutation testing runs on a scheduled cadence only, never per-commit

Full rule table is in `skills/testing-strategy-craft.md`.

---

## Installation

1. Copy the `qa-companion/` directory into your project or into your global Claude Code plugins directory.
2. Ensure `ai-baseline` is installed and initialised (`/context` to set app and feature labels).
3. Run `/qa-strategy "your stack description"` to begin.
