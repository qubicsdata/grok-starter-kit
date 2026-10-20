# dev-companion

A Claude Code plugin for teams working on existing projects. Eight independently-invocable agents covering the full development loop: code review, security review, technical debt analysis, test generation, feature specification, design documentation, architecture decision records, and adversarial critique. No session setup. No shared state. Run any command at any time.

---

## Installation

```bash
# From your project root, install the plugin:
claude plugin install dev-companion

# Or reference locally during development:
claude plugin install /path/to/dev-companion
```

---

## Commands

| Command | Description | Example |
|---|---|---|
| `/review [target]` | Forensic code review on a diff, file, or git range. Defaults to `git diff HEAD`. | `/review src/auth/login.ts` |
| `/security [target]` | Security review against all OWASP Top 10 (2021) categories. Defaults to `git diff HEAD`. | `/security git diff main..feature/payments` |
| `/tech-debt [path]` | Categorised, prioritised technical debt register for a directory. Defaults to `.`. | `/tech-debt src/` |
| `/test "subject"` | Test file generation matching the project's framework and style. | `/test "user login with email and password"` |
| `/spec "name"` | Feature specification via structured Q&A. Writes `docs/specs/NNNN-[slug].md`. | `/spec "password reset flow"` |
| `/design "subject"` | Design doc with ≥2 implementation approaches. Writes `docs/designs/NNNN-[slug].md`. | `/design "docs/specs/0001-password-reset.md"` |
| `/adr "statement"` | Architecture Decision Record capture. Writes `docs/adr/NNNN-[slug].md`. Stateless. | `/adr "Choice of message queue technology"` |
| `/critique "subject"` | Adversarial critique: assumptions, failure modes, missing constraints. | `/critique "docs/designs/0002-caching-layer.md"` |

---

## Agents

### code-reviewer

Forensic code reviewer focused on correctness, not style. Finds logic errors, null dereferences, missing awaits, deleted invariants, broken call sites, swallowed exceptions, dead code, and complexity hotspots. Produces a ranked findings report — Critical first. Never modifies files. Never suggests style changes — that is the linter's job.

Use when: reviewing a PR, checking a file before merge, auditing a git range for correctness issues.

### security-reviewer

Security reviewer that checks every OWASP Top 10 (2021) category systematically. Covers A01 (Broken Access Control), A02 (Cryptographic Failures), A03 (Injection), A04 (Insecure Design), A05 (Security Misconfiguration), A06 (Vulnerable and Outdated Components), A07 (Identification and Authentication Failures), A08 (Software and Data Integrity Failures), A09 (Security Logging and Monitoring Failures), and A10 (SSRF). Every category appears in the report — PASS for clean categories, findings for problematic ones. Injection and auth issues are Critical by default.

Use when: reviewing code that handles user input, authentication, payments, data access, or configuration.

### tech-debt-agent

Surveys a codebase or module, classifies every debt item into Structural / Quality / Dependency / Coverage / Docs categories, scores each item by effort × impact, and produces a prioritised register. Presents the register for user confirmation before writing to `docs/tech-debt-register.md`. Never suggests inline fixes — it identifies and prioritises. Never includes literal credential values found in source — records location and type only.

Use when: onboarding a legacy codebase, preparing a tech debt sprint, understanding what maintenance work has been deferred.

### test-generator

Generates test files that match the project's existing testing conventions. Reads existing tests first to detect framework, assertion style, file naming, and mock patterns. Generates scenarios covering happy paths, boundaries, error paths, and edge cases. Every test asserts something specific — no smoke stubs. Places generated files in the same directory as the source file using the detected naming convention.

Use when: adding tests for an untested module, generating a starting test suite for a new feature.

### feature-spec-agent

Elicits a complete feature specification through seven structured questions — one at a time, no batching. Captures problem statement, acceptance criteria, out of scope, edge cases, dependencies, rollout strategy, and rollback plan. Presents the full draft before writing to `docs/specs/NNNN-[slug].md`.

Use when: starting a new feature, formalising a verbal requirement, creating a shared artifact for a feature before design or implementation begins.

### design-agent

Proposes ≥2 meaningfully distinct implementation approaches for a feature, with advantages, disadvantages, and complexity estimates for each. Does not recommend — presents trade-offs. Reads existing code in affected modules before proposing. Writes the chosen design to `docs/designs/NNNN-[slug].md` after user confirmation.

Use when: deciding how to implement a feature, creating a design doc for team review, documenting the approach taken.

### adr-agent

Captures Architecture Decision Records in MADR format (teams ≥5 engineers) or Nygard format (teams <5). Stateless — works in any project at any time with no prior session. Requires a decision statement and at least two considered options before drafting. Never fabricates a second option. Reads `docs/requirements.md` for team size; asks if not found. Writes to `docs/adr/NNNN-[slug].md` after confirmation.

Use when: formalising an architectural decision, recording a technology choice, documenting why an alternative was rejected.

### critic-agent

Adversarial reviewer using claude-opus-4-8. Examines every design across six dimensions: hidden assumptions, failure modes, missing constraints, scope creep risk, operability, and security surface. Always finds something — if the design looks solid, it looks harder. Never validates without critiquing. Never suggests fixes — it identifies problems; solutions are the developer's job. Rejects file paths containing `..`, `~`, or absolute paths outside the project root.

Use when: stress-testing a design before committing to it, getting a second opinion on an ADR, preparing for a design review by anticipating hard questions.

---

## Findings Severity Guide

| Severity | Meaning | Verdict contribution |
|---|---|---|
| **Critical** | Active defect or exploitable vulnerability that will cause data loss, breach, or outage under normal conditions | BLOCK |
| **High** | Defect that causes incorrect behaviour or data exposure under realistic (non-constant) conditions | PASS WITH WARNINGS |
| **Medium** | Quality or latent-risk issue that makes future bugs more likely | PASS WITH WARNINGS |
| **Low** | Minor issue or code smell with limited practical consequence | PASS |
| **Info** | Observation worth recording; may indicate a pattern when aggregated | PASS |

**BLOCK** = any Critical. **PASS WITH WARNINGS** = High or Medium only. **PASS** = Low/Info only or none.

---

## Artifacts Produced

| Artifact | Agent | Location |
|---|---|---|
| Tech debt register | `tech-debt-agent` | `docs/tech-debt-register.md` |
| Feature specs | `feature-spec-agent` | `docs/specs/NNNN-[slug].md` |
| Design documents | `design-agent` | `docs/designs/NNNN-[slug].md` |
| Architecture Decision Records | `adr-agent` | `docs/adr/NNNN-[slug].md` |
| Test files | `test-generator` | Follows project convention (same dir as source) |

Review agents (`code-reviewer`, `security-reviewer`, `critic-agent`) produce reports only — no files written.

---

## Anti-Patterns This Plugin Prevents

1. **Auto-fixing findings**: Review agents produce reports. They never modify code. Fixes are the developer's decision.

2. **Smoke-only tests**: `test-generator` requires every test to assert a specific expected value or behaviour. No `expect(true).toBe(true)`. No empty test bodies.

3. **Uncritiqued designs**: `critic-agent` is adversarial by design. It finds at least one problem in every dimension of every design it reviews. "Everything looks fine" is not a valid output.

4. **Stack assumptions**: No agent assumes a language, framework, or testing library. All are inferred from the code; the agent asks if ambiguous.

5. **Confirmation-free writes**: Every artifact-producing agent presents the full draft for explicit user confirmation before writing. Nothing is written silently.

6. **Single-option ADRs**: `adr-agent` requires at least two considered options. An ADR with one option is not a decision record — it is a statement.

7. **Rollout-free specs**: `feature-spec-agent` always asks for rollout strategy and rollback plan, regardless of feature size. These questions are never skipped.

8. **Path traversal reads**: `critic-agent` and `tech-debt-agent` reject paths containing `..`, `~`, or absolute paths outside the project root. Scope paths are resolved with realpath before use.

## Dependencies

- requires: ai-baseline
