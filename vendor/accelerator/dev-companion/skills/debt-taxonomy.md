---
name: debt-taxonomy
description: |
  Apply when classifying and scoring technical debt findings. Defines five debt categories with examples and a scoring rubric. Used exclusively by tech-debt-agent.
---

# Technical Debt Taxonomy

## Categories

### Structural

**Definition:** Debt arising from wrong architectural choices — layers in the wrong place, circular dependencies, god classes, spaghetti coupling between modules that should be independent.

**Examples:**
- A business logic function imported directly into a database migration script
- Circular imports between two modules (`A` imports `B`, `B` imports `A`)
- A single class or module with more than 5 distinct responsibilities
- Presentation layer code (HTML templates, JSON serialisation) mixed into data access functions
- Two services that call each other synchronously in a loop

**Identifying markers:** `grep` for cross-layer imports; look for files with 500+ lines; look for classes with 10+ public methods spanning unrelated concerns.

---

### Quality

**Definition:** Debt arising from substandard implementation — excessive duplication, oversized functions, magic numbers, commented-out code left in the tree.

**Examples:**
- The same validation logic copy-pasted in 4+ files
- A function exceeding 50 lines with no helper extraction
- A constant like `86400` used in 6 places with no named `SECONDS_PER_DAY` definition
- Blocks of commented-out code that have not been removed
- Deeply nested conditionals (4+ levels) that could be simplified with early returns

**Identifying markers:** `grep -rn "TODO\|FIXME\|HACK\|XXX"`; `wc -l` on source files; grep for duplicate string literals.

---

### Dependency

**Definition:** Debt arising from outdated, vulnerable, or abandoned third-party packages.

**Examples:**
- A package that is more than 2 major versions behind its current release (e.g. using v1.x when v3.x is current)
- A package with a known CVE in the installed version
- A package whose repository has been archived or abandoned (no commits in 2+ years, no maintainer)
- A package imported for a single utility function that could be inlined

**Identifying markers:** Read `package.json` / `pyproject.toml` / `go.mod` / `Gemfile`; compare major versions against known current versions where identifiable; flag archived or abandoned packages.

**Note:** Cannot verify exact CVE status without running `npm audit` / `pip-audit` / `bundler-audit` / `govulncheck`. Flag packages for audit rather than asserting a specific CVE.

---

### Coverage

**Definition:** Debt arising from missing, misleading, or unreliable tests.

**Examples:**
- No test files exist for a module that handles payment processing, authentication, or data deletion
- Test files that mock the module under test (testing the mock, not the code)
- Tests that always pass because they assert `true` or make no assertions
- Flaky tests that intermittently fail due to timing or external dependencies
- Integration tests that require a specific external service to be running and have no documented setup

**Identifying markers:** `find` for test files; count test files vs source files; look for `expect(true)` / `assert True` / empty test bodies; look for tests that import and mock the module they are in.

---

### Docs

**Definition:** Debt arising from missing, stale, or misleading documentation.

**Examples:**
- A public module with no `README.md` that other teams or future engineers are expected to use
- A public API (REST endpoint, exported function, SDK method) with no parameter documentation
- An architecture diagram that depicts a service that no longer exists or a flow that was changed 6 months ago
- A `CONTRIBUTING.md` that describes a development workflow that is no longer used
- Inline comments that contradict the code they describe

**Identifying markers:** `find` for README files at module level; grep for `@param` / docstring presence in exported functions; check date on architecture docs against recent code changes.

---

## Scoring Rubric

Every debt item receives a priority score: **effort × impact**.

### Effort

| Label | Score | Meaning |
|---|---|---|
| S | 1 | Small — one engineer, one day or less |
| M | 2 | Medium — one engineer, 2–5 days |
| L | 3 | Large — one engineer, 1–2 weeks, or requires coordination |
| XL | 4 | Extra-large — multiple engineers, multiple weeks, or requires a migration |

### Impact

| Score | Meaning |
|---|---|
| 1 | Low — cosmetic or minor; minimal effect on velocity or reliability |
| 2 | Medium — slows development or causes occasional confusion |
| 3 | High — causes regular pain, bugs, or onboarding friction |
| 4 | Critical — blocking or likely to cause production incidents |

### Priority Score

```
priority = effort_score × impact_score
```

| Score Range | Priority Label |
|---|---|
| 12–16 | Critical priority |
| 8–11 | High priority |
| 4–7 | Medium priority |
| 1–3 | Low priority |

---

## DO NOT Rules

- DO NOT rate all debt items at the same priority — the scoring rubric must differentiate findings; if every item scores 6, revisit the effort and impact estimates; a register where everything is Medium is not useful
- DO NOT create a debt item for something already tracked in an existing project issue — if a TODO comment references a GitHub issue number or Jira ticket, note the cross-reference (`see: GH-1234`) instead of duplicating the item
- DO NOT assign a high effort score to justify a low priority — effort and impact are independent axes; a one-day fix with Critical impact is a Critical-priority item regardless of small effort
- DO NOT create debt items for personal style preferences — debt items must describe a specific, nameable category from this taxonomy with a concrete consequence
