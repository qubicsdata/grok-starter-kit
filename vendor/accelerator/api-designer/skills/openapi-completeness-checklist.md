---
name: openapi-completeness-checklist
description: OpenAPI 3.1 structural completeness checklist. Apply inline during spec generation and contract review. Each of the 9 checks produces a finding at the defined severity level if violated.
---

## Purpose

The openapi-completeness-checklist verifies that an OpenAPI 3.1 spec is structurally complete and will not surprise API consumers with undocumented gaps. Used by `contract-reviewer` and `spec-generator`. Each violated check produces a finding at the severity level defined below.

## The 9 Checks

Apply each check by reading the full spec file. Produce a finding only when the check is violated.

| # | Check | Severity if violated |
|---|-------|---------------------|
| 1 | Every operation has a non-empty `summary` and `description` | Low |
| 2 | Every path parameter has a `description` field and a `schema` field | High |
| 3 | Every query parameter has a `description` field, a `schema` field, and a `required` field | Medium |
| 4 | Every request body has an `application/json` content type defined under `content` | High |
| 5 | All `$ref` values resolve to a component defined in `components/schemas` (no dangling references) | Critical |
| 6 | `info.version` is present and follows semver (e.g. `1.0.0`, `2.1.0`) | Medium |
| 7 | At least one `securityScheme` is declared in `components/securitySchemes` | High |
| 8 | Every operation defines at least one `4xx` error response | High |
| 9 | Every operation defines at least one `5xx` response | Medium |

## Rules

- Check 5 (`$ref` resolution) is a hard blocker for `spec-generator`. If any `$ref` does not resolve at spec-generation time, the spec must not be written.
- Check 7 (securityScheme declared) may pass with `{}` security (no auth) only if `security-contract-agent` explicitly documented "no auth" with a rationale in `api-design-intent.md`. In that case, a comment in the spec must note the rationale.
- Checks 1, 3, 6, 8, 9 apply to every individual operation — not just the overall spec. A spec where some operations pass and others fail produces findings for each failing operation.

## Output Format

For each violated check, produce a finding in this format:

```
### [Severity] Check [#]: [Check name]

**Operation(s) affected:** `[list of operationIds or paths, or "global"]`
**Violation:** [One sentence describing the gap]
**Recommendation:** [One sentence describing what to add]
```

If all 9 checks pass, output: `OpenAPI Completeness Checklist: all 9 checks PASS — no findings.`
