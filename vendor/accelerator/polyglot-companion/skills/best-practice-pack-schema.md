---
name: best-practice-pack-schema
description: The canonical schema every polyglot-companion language pack must follow. Import this when authoring or validating a language pack.
---

# Best-Practice Pack Schema

Every language pack in `polyglot-companion/skills/` MUST provide all six sections below. Omitting a section or using placeholder text is a schema violation.

---

## Section 1 — Idioms & Preferred Constructs

Concrete language-idiomatic patterns that SHOULD be used. Each idiom names the preferred form and (where helpful) contrasts it with the non-idiomatic alternative. Be specific to the language's standard library and ecosystem — no generic advice.

Format:
```
- <IDIOM-N> <short name>: <description of the preferred construct and why>
  Prefer: <example or description>
  Avoid:  <the non-idiomatic alternative>
```

---

## Section 2 — Anti-Patterns to Flag

Concrete coding patterns that a reviewer MUST flag. Each entry names the anti-pattern, explains why it is harmful, and states the reviewer action.

Format:
```
- <AP-N> <short name>: <what the anti-pattern is>
  Why harmful: <brief rationale>
  Reviewer action: FLAG and cite this rule.
```

---

## Section 3 — Security Pitfalls

Language-specific vulnerabilities that MUST be guarded in production code. Each pitfall names the attack class, the dangerous pattern, and the required mitigation.

Format:
```
- <SEC-N> <attack class>: <description of the dangerous pattern>
  Mitigation: <the required safe pattern>
  Severity: CRITICAL | HIGH | MEDIUM
```

---

## Section 4 — Testing Framework & Convention

The language's standard test framework and the conventions that MUST be followed (file naming, assertion style, mock approach, coverage tooling).

Format:
```
Framework: <name and version range>
Convention:
- <convention-1>
- <convention-2>
Coverage tool: <tool name>
```

---

## Section 5 — Build / Dependency Norms

The canonical build tool and dependency management approach. Includes lock-file policy and any version-pinning requirements.

Format:
```
Build tool: <name>
Dependency manifest: <filename>
Lock file: <filename or "required">
Norms:
- <norm-1>
- <norm-2>
```

---

## Section 6 — Lint / Format Tool of Record

The single authoritative lint and format tool the codebase MUST use. Reviewer cites this when flagging style deviations.

Format:
```
Linter: <tool name and config file>
Formatter: <tool name and config file>
Enforcement: <CI check name or command>
```
