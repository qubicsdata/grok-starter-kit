---
name: mutation-testing-guide
description: Import when recommending a mutation testing tool, threshold, or cadence, or when addressing "too slow" or "hard to interpret" objections to mutation testing — consumed by mutation-advisor.
---

# Mutation Testing Guide

## Section 1 — Tool Selection Table

| Language signal | Primary tool | Notes |
|---|---|---|
| `.java` files, or `pom.xml` / `build.gradle` present | **PiTest** (pit-test.org) | JVM-native; fastest mutation engine for Java/Kotlin; Maven plugin `org.pitest:pitest-maven` or Gradle plugin `info.solidsoft.pitest`; produces line and mutation coverage in the same report |
| `.ts`, `.tsx`, `.js`, `.jsx` files, or `package.json` present | **Stryker** (stryker-mutator.io) | First-class TypeScript and JavaScript support; runs Jest, Vitest, Jasmine, Karma; `@stryker-mutator/core` + framework runner; JSON, HTML, and dashboard reporter |
| `.cs` files or `.csproj` present | **Stryker.NET** (stryker-mutator.io) | .NET port of Stryker; supports MSTest, xUnit, NUnit; `dotnet tool install -g dotnet-stryker`; produces HTML dashboard per file |
| `.py` files, or `setup.py` / `pyproject.toml` present | **mutmut** (github.com/boxed/mutmut) | Pure Python; runs pytest; `pip install mutmut`; `mutmut run` then `mutmut results` for survivor list; `cosmic-ray` is an alternative with more mutation operators |

**Mixed-language projects:** Select the tool for the primary language (highest source file count). Each language requires a separate tool invocation scoped to its own source directory.

## Section 2 — Threshold Recommendations

| Module tier | Mutation score minimum | Notes |
|---|---|---|
| Critical-path (auth, payments, billing, checkout, core business logic, access control) | ≥80% | Mandatory, not a goal. Below 80% means tests do not adequately verify critical behavior. |
| Supporting (utilities, formatters, validators, data mappers, configuration loaders) | ≥60% | Below 60% = tautological warning — tests execute the code but assertions do not catch injected faults. |
| Generated code (ORM entities, protobuf stubs, Lombok output, migration files) | Exclude | Exclude via package filter or file glob in tool config. No mutation value. |
| Test infrastructure (factories, fixtures, test helpers) | Exclude | Mutation-testing test code produces no actionable signal. |

**Tautological warning:** When mutation score < 60% alongside line coverage ≥ 80%, the test suite is tautological — code is executed but behavioral changes go undetected. The fix is not more tests; it is more precise assertions. Flag as QA-STRAT-D-5.

**Why 80% and not 100%:** Equivalent mutations (Section 4) make 100% mutation score mathematically unachievable for most modules. Industry consensus and PiTest documentation both target 80% as the meaningful upper bound for critical-path code.

## Section 3 — Cadence Guidance

**Rule: QA-STRAT-D-10 — Mutation testing MUST run on a scheduled cadence, NOT per-commit.**

| Cadence option | When appropriate | Notes |
|---|---|---|
| Nightly scheduled CI job | Most teams | Runs against main after merges; reports available next morning; does not block PR authors |
| Pre-release gate | Teams with infrequent release cycles | Runs before each release tag is created; gates the release, not individual commits |
| Per-commit | Never recommended | Mutation testing adds 5–30 minutes depending on suite size; per-commit runs create queue pressure and slow developer feedback |

**Scoping to high-value modules only:**

- **PiTest:** Set `targetClasses` in plugin config to include only critical-path packages (e.g. `com.example.auth.*`, `com.example.payments.*`). Set `excludedClasses` to exclude generated code packages.
- **Stryker:** Set `mutate` array in `stryker.config.js` to include only the critical-path source directories (e.g. `["src/auth/**/*.ts", "src/payments/**/*.ts"]`). Exclude `**/*.generated.ts`.
- **Stryker.NET:** Use `--mutate` flag to scope to specific project files or namespaces.
- **mutmut:** Use `--paths-to-mutate` to restrict to a module subdirectory (e.g. `src/billing/`).

**Integration pattern (nightly):**
Add a scheduled CI job (GitHub Actions `schedule: cron`, GitLab CI `rules: - if: $CI_PIPELINE_SOURCE == "schedule"`, Jenkins cron trigger) that runs only the mutation testing step. Publish the HTML report as a CI artifact. Fail the job if mutation score drops below the configured threshold — this alerts the team before the next release rather than blocking every commit.

## Section 4 — Equivalent Mutations

**What they are:**
An equivalent mutation is a code change that alters the implementation without changing the observable behavior for any valid input. Example: changing `i <= n` to `i < n + 1` in a loop — these are semantically equivalent under integer arithmetic. No test can kill an equivalent mutation because no input produces a different observable output.

**Why they matter:**
Equivalent mutations inflate the "survived" count in the mutation report, making the mutation score appear lower than the true quality of the test suite. A mutation score of 75% on a well-tested module is acceptable if a significant fraction of survivors are equivalent mutations.

**How tools handle them:**

- **PiTest:** Provides an equivalent mutation filter configuration (`avoidCallTo`) and publishes known-equivalent mutation operator categories. The PiTest team recommends reviewing the survivor list before concluding the test suite is inadequate.
- **Stryker:** Marks some survivors as "no coverage" (not run by any test) vs "survived" (run by a test but not killed). "No coverage" survivors often indicate dead code or unreachable paths, not inadequate tests.
- **mutmut:** No automatic equivalent mutation detection; requires manual survivor review.

**Practical guidance:**
When mutation score falls below threshold, review the survivor list before adding tests. Categorize each survivor as: (a) killed by an existing test that was not collected — reconfigure the test runner; (b) equivalent mutation — document and ignore; (c) genuine coverage gap — add a test targeting that behavior. Only category (c) warrants new tests.

## Section 5 — Common Objections

**Objection: "Mutation testing is too slow to run."**

Response: Mutation testing should never run per-commit. Schedule it nightly or as a pre-release gate. Scope it to critical-path modules only — not the entire codebase. PiTest with incremental analysis runs only on changed classes since the last run, reducing runtime by 60–90% on large codebases. Stryker with `--since` flag does the same for JavaScript/TypeScript. A nightly run of 15–30 minutes on scoped critical-path modules is operationally acceptable for most teams.

**Objection: "The mutation report is hard to interpret — we don't know what to do with the survivor list."**

Response: Apply survivor analysis in three steps: (1) open the HTML report and filter to "Survived" status only; (2) for each surviving mutation, read the mutant diff and ask "if this change were in production, would any of our tests fail?" — if yes, the test framework may not be running that test against this code path (a scoping issue, not a test quality issue); (3) if no test would catch it, that is a genuine coverage gap — write an assertion targeting the specific behavioral outcome the mutation disrupts. The HTML reports from PiTest, Stryker, and Stryker.NET all show the exact line and the mutant diff, making the gap explicit.

DO NOT use mutation testing reports as a reason to write more tests without reading the survivors. More tests that do not kill more mutants do not improve the mutation score.
