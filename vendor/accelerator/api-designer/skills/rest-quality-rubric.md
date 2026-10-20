---
name: rest-quality-rubric
description: REST design quality rubric. Apply inline during contract review. Each of the 8 checks produces a finding at the defined severity level if violated.
---

## Purpose

The rest-quality-rubric applies 8 REST design checks to an OpenAPI spec. Used by `contract-reviewer` as part of its analysis. Each violated check produces a finding at the severity level defined below.

## The 8 Checks

Apply each check by reading the spec. Produce a finding only when the check is violated. If a check passes, do not include it in the findings list.

| # | Check | Severity if violated | Notes |
|---|-------|---------------------|-------|
| 1 | Resource paths use noun-plural form (`/users`, not `/user` or `/getUser`) | Medium | Plural nouns are the REST convention for collections. Singular resource identifiers (`/users/{id}`) are correct — check the collection path, not the individual-item path. |
| 2 | No verbs in paths — except endpoints explicitly marked with `x-rpc: true` in the spec | High | Verb paths (`/createUser`, `/sendEmail`, `/deleteItem`) indicate operation-as-resource anti-pattern. RPC-style endpoints are permitted only when marked `x-rpc: true`. |
| 3 | GET requests have no request body defined | High | GET with a request body is non-standard and breaks proxies, caches, and many HTTP clients. |
| 4 | DELETE returns `204 No Content` or `200` with a body — never `404` when the resource is already absent (idempotency) | Medium | DELETE must be idempotent: deleting a non-existent resource must not return 404. The spec should define DELETE responses as 204 (or 200), not conditional on prior existence. |
| 5 | POST returns `201 Created` with a `Location` header defined for resource creation operations | Medium | POST that creates a resource must return 201 and document the `Location` header pointing to the new resource URI. |
| 6 | PUT is used for full replacement only; PATCH is used for partial update only — they are not used interchangeably | Medium | If both PUT and PATCH are defined on the same path, verify their request body schemas reflect full-object vs partial-object semantics respectively. |
| 7 | 4xx responses use distinct status codes — 400 Bad Request vs 422 Unprocessable Entity vs 404 Not Found — not all mapped to 400 | High | Using 400 for all error conditions conflates client errors. 400 = malformed request syntax; 422 = valid syntax, failed business validation; 404 = resource not found. |
| 8 | Collection endpoints declare pagination parameters (`page`/`per_page` or `cursor`/`limit`) and include pagination metadata in the response schema | Medium | Collection endpoints that return arrays without pagination parameters will break at scale and surprise API consumers. |

## Output Format

For each violated check, produce a finding in this format:

```
### [Severity] Check [#]: [Check name]

**Path(s) affected:** `[list of affected paths or "all collection endpoints"]`
**Violation:** [One sentence describing what the spec does wrong]
**Recommendation:** [One sentence describing the correct approach]
```

Example:

```
### High Check 2: No verbs in paths

**Path(s) affected:** `/createUser`, `/deleteAccount`
**Violation:** These paths use verb-based naming, which is an operation-as-resource anti-pattern.
**Recommendation:** Rename to `/users` (POST to create) and `/accounts/{id}` (DELETE to remove).
```

If all 8 checks pass, output: `REST Quality Rubric: all 8 checks PASS — no findings.`
