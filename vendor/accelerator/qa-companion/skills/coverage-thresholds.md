---
name: coverage-thresholds
description: Import when evaluating coverage gate adequacy against module-tier baselines, identifying which modules qualify as critical-path, or explaining why line-only coverage or 100% mandates are vanity metrics — consumed by coverage-reviewer.
---

# Coverage Thresholds

## Section 1 — Module Tier Table

| Module tier | Line% minimum | Branch% minimum | Mutation score | Config action |
|---|---|---|---|---|
| Critical-path (auth, payments, billing, checkout, core business logic, access control, revenue-critical flows) | ≥80% | ≥70% | ≥80% — required, not optional | Include explicitly; never exclude |
| Supporting (utilities, formatters, validators, data mappers, configuration loaders, logging helpers) | ≥70% | ≥60% | Not required | Include; may be lower-priority in gate enforcement |
| Generated code (ORM entities, protobuf stubs, SDK client bindings, Lombok output, migration files, GraphQL schema types) | Exclude | Exclude | Exclude | Add to `coveragePathIgnorePatterns`, `exclude`, or `excludedClasses` in tool config |
| Test infrastructure (test factories, test fixtures, test utilities, mocks, stubs written by the team) | Exclude | Exclude | Exclude | Exclude by path pattern (`__mocks__`, `testUtils`, `fixtures`) |

**Gate minimum:** Any project with a coverage tool MUST have at minimum a `branches` threshold configured. A `lines`-only gate is a QA-STRAT-D-1 violation regardless of the percentage value.

**Two-metric minimum:** Every enforced gate must set both `lines` (or `statements`) AND `branches`. Functions and statements may be added but are secondary.

## Section 2 — Critical-Path Identification Heuristics

A module is critical-path if ANY of the following is true:

1. **Revenue transaction surface:** the module handles payment processing, subscription billing, order placement, refund logic, or any financial calculation
2. **Authentication and authorization:** login flows, token generation/validation, session management, permission checks, role-based access control enforcement
3. **Data integrity:** modules that write to the primary data store with no undo path (irreversible writes, financial ledger entries, audit log production)
4. **Core business logic:** the domain layer that encodes the primary value proposition of the product — pricing engines, inventory allocation, discount calculation, fraud scoring
5. **Access control enforcement:** any module that decides whether a user is allowed to see or modify a resource
6. **Data pipeline correctness:** ETL transform logic, data aggregation, reporting calculations, ML feature engineering — anywhere incorrect output propagates silently
7. **Explicit team designation:** the team has explicitly labelled the module as P0 or critical in a threat model, runbook, or SLA document

**When in doubt:** if a bug in the module would trigger a P0 incident (see incident-companion thresholds), it is critical-path for coverage purposes.

## Section 3 — Vanity Metric Warnings

### Why line coverage alone is insufficient

Line coverage measures which lines of source code were executed by at least one test. It does not measure whether the test verified anything about those lines. A test that executes `if (user.isPremium()) { return discount; }` and asserts nothing about the return value still registers 100% line coverage for that branch.

**The branch gap:** Line coverage with no branch threshold misses entire conditional paths. The `else` branch of an `if` statement, the `false` arm of a ternary, the `catch` block of a try/catch — all can be 0% branch coverage while line coverage appears high.

**Consequence:** A project reporting 85% line coverage with no branch threshold may have critical conditional paths that are entirely untested. This is a QA-STRAT-D-1 violation. The fix is mandatory: add `branches: ≥70%` (critical-path) or `branches: ≥60%` (supporting) alongside the existing line threshold.

---

### Why 100% coverage mandates are a quality anti-pattern (QA-STRAT-D-6)

A 100% line coverage mandate produces these failure modes:

1. **Trivial test inflation:** developers write tests for generated code, configuration files, getters/setters, and infrastructure glue — not because those tests have value but because the gate requires them. Coverage goes to 100%; quality does not.
2. **Refactoring drag:** any code restructuring that temporarily drops coverage below 100% is blocked by the gate — even when the tests themselves are not changed. This makes coverage enforcement an obstacle to clean code.
3. **False confidence:** 100% line coverage does not mean the behavior is correct. A module with 100% line coverage and 40% mutation score has tests that exercise every line but fail to detect most injected faults.
4. **Exclusion pressure:** developers exclude edge-case modules from coverage measurement rather than test them, because 100% on the full codebase is unachievable. This creates invisible blind spots.

**Correct target:** ≥80% lines and ≥70% branches for critical-path modules, with generated code excluded. The 80/70 threshold captures meaningful coverage without the failure modes of 100% mandates.

---

### Mutation score as a stronger signal

When line and branch coverage gates are met, mutation score is the next-level signal:

- **Mutation score ≥ 80%** on a critical-path module: tests are not just executing the code — they are verifying that behavioral changes produce test failures. This is the meaningful quality bar.
- **Mutation score 60–79%:** tests are present and exercising the code, but a significant minority of behavioral changes go undetected. Acceptable for supporting modules; requires attention for critical-path.
- **Mutation score < 60%:** the test suite is tautological (QA-STRAT-D-5). Tests pass through the code without making behavioral assertions strong enough to catch injected changes. High line coverage here is actively misleading — it implies quality that does not exist.

**The combined signal:** high line coverage + low mutation score = the most dangerous coverage posture. It provides false confidence to teams and management while leaving genuine behavioral gaps undetected. Flag this pattern explicitly whenever both data points are available.

DO NOT report "coverage is adequate" when only line coverage data is available and no branch threshold or mutation data exists. The correct finding is "coverage posture is partially visible — branch threshold and mutation data are required for a complete assessment."
