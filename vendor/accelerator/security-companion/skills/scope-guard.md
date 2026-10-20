---
name: scope-guard
description: Invoke when the input to a security-companion analysis command is of uncertain type — triggers when the input might be source code, a running-system snapshot, or a dependency manifest rather than an architecture or design description.
---

# Scope Guard

security-companion works at the design and architecture stage. This skill enforces that boundary.

## HALT Conditions

Return HALT when the input satisfies ANY of the following:

### 1. Source Code Detected

Indicators (any one is sufficient):
- Presence of programming-language syntax: function/method definitions (`def `, `function `, `void `, `class `), import statements (`import `, `require(`, `from `, `#include`), control flow keywords in code context (`if (`, `for (`, `while (`), or type annotations (`: str`, `: int`, `<String>`)
- File extensions named or present: `.py`, `.js`, `.ts`, `.java`, `.go`, `.rs`, `.cs`, `.cpp`, `.rb`, `.php`, `.kt`, `.swift`
- Code fence blocks containing multiple lines of apparent programming-language syntax

### 2. Running System State

Indicators (any one is sufficient):
- Application logs (timestamps + log levels + stack traces in a log format)
- Live deployment output (`kubectl describe`, `docker ps`, `systemctl status`, runtime process listings)
- Live error messages referencing memory addresses, thread IDs, or file:line locations
- Monitoring alert payloads or APM data describing current system state

### 3. Dependency Manifest

Indicators (any one is sufficient):
- File names: `package.json`, `package-lock.json`, `requirements.txt`, `Pipfile`, `pom.xml`, `build.gradle`, `go.mod`, `go.sum`, `Gemfile`, `Cargo.toml`, `pyproject.toml`, `.csproj`
- File content patterns: JSON with `"dependencies"` or `"devDependencies"` keys, Python package version specifiers (`package>=1.0,<2.0`), Maven XML with `<dependency>` elements

## HALT Response Format

When any HALT condition is detected, return exactly:


```
SCOPE BOUNDARY — security-companion works at the design and architecture stage.

Your input appears to be [source code / a dependency manifest / running-system output — specify which].

For this input, use:
- Source code security review:   dev-companion → /security [file-or-directory-path]
- Secret scanning:               ops-companion → /secrets-audit [path]
- Dependency CVE scanning:       dependency-auditor → /audit [manifest-path]
- Runtime/infrastructure review: ops-companion → /iac-review [path]

security-companion accepts: architecture descriptions, data-flow descriptions, design documents, ADRs, feature specifications, and system diagrams.
```

## PROCEED Response

When NO HALT condition is detected (input is an architecture description, design doc, or similar), return exactly:

```
SCOPE OK
```

No additional text. The invoking agent continues with analysis after receiving SCOPE OK.

## Ambiguous Input Handling

If the input is ambiguous — for example, a design document that includes short code excerpts as illustrations — return SCOPE OK and append a scope note to the invoking agent's output:

```
SCOPE NOTE: Input contains code excerpts. security-companion analyzed the design context only. For code-level review, use: dev-companion → /security [path].
```

## Hard Gates

**NEVER return HALT without specifying which condition was triggered.**
**NEVER block ambiguous input — favor SCOPE OK with a SCOPE NOTE over a false HALT.**
**NEVER attempt to analyze the input yourself — scope determination only, no security analysis.**
**NEVER suggest a plugin or command that does not exist in the accelerator fleet.**
