---
name: api-severity-scale
description: Maps review findings and breaking-change classifications to a 5-level severity scale (Critical → Info) with API-specific definitions. Apply when producing findings reports.
---

## Purpose

The api-severity-scale provides a single authoritative severity taxonomy for all findings produced by this plugin. Used by `contract-reviewer` and `breaking-change-detector`. Every finding must carry exactly one severity level from this scale.

## The 5 Severity Levels

| Severity | Definition | Examples |
|----------|------------|---------|
| **Critical** | The spec is structurally invalid or will cause API consumers to fail at parse or runtime | Unresolved `$ref`, missing required operation response, invalid YAML syntax, `openapi` field missing or set to wrong major version |
| **High** | The spec violates REST semantics or security contract in a way that will cause consumer misuse or security issues | Verb paths, GET with request body, missing securityScheme, 4xx responses all mapped to 400, path parameter without schema |
| **Medium** | The spec is technically valid but deviates from REST conventions in a way that increases consumer integration burden | Singular resource paths, missing pagination on collections, POST not returning 201, missing query parameter `required` field |
| **Low** | The spec is missing documentation or polish that reduces developer experience | Operations without `summary`, missing `description` on parameters, no `example` fields |
| **Info** | Informational observation; no action required | Opportunity to add `x-` extension metadata, optional HATEOAS links, optional deprecation markers |

## Report Ranking

When producing a findings report, rank findings in this order:
1. Critical (highest — address immediately; blocks shipping)
2. High
3. Medium
4. Low
5. Info (lowest — optional improvements)

Within each severity level, sort findings by the order the affected path/operation appears in the spec.

## Usage in breaking-change-detector

When `breaking-change-detector` applies this scale to a diff report:
- **Breaking** changes that will cause consumer runtime failures map to **Critical**
- **Breaking** changes that are non-obvious (semantic breaks) map to **High**
- **Deprecated** changes (breaking in next major version) map to **Medium**
- **Non-breaking additive** changes map to **Info**
