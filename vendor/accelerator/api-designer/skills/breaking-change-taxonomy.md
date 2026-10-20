---
name: breaking-change-taxonomy
description: Canonical list of breaking, non-breaking, and deprecated change types for OpenAPI specs. Used by breaking-change-detector as the authoritative reference. Agent classification derives from this taxonomy — never from ad-hoc inference.
---

## Purpose

This taxonomy is the single authoritative definition of what constitutes a breaking change in an OpenAPI spec diff. `breaking-change-detector` applies this list exhaustively to every diff. No item on the Breaking list may be reclassified as Non-Breaking without a documented rationale surfaced to the user.

---

## Breaking Changes

These changes WILL break existing API consumers. Every item on this list is treated as Breaking with no exceptions unless the user explicitly overrides with a documented rationale.

| # | Change Type | Why It Breaks Consumers |
|---|-------------|------------------------|
| B1 | Removal of any endpoint (path + method combination) | Consumers calling the removed endpoint receive 404 or routing errors |
| B2 | Removal of any required request field | Consumers sending the field will have their requests fail validation |
| B3 | Addition of any required request field | Consumers not sending the new required field will have their requests rejected |
| B4 | Narrowing of a field type (e.g. `string` → `enum`, `number` → `integer`) | Consumer values valid under the old type may be rejected under the narrower type |
| B5 | Narrowing of a field format (e.g. `string` → `string format: uuid`) | Consumer values valid as plain strings may fail uuid format validation |
| B6 | Removal of an enum value from a request parameter | Consumers sending the removed enum value will receive validation errors |
| B7 | Change in HTTP method for an existing path | Consumers using the old method will receive 405 Method Not Allowed |
| B8 | Change in a path parameter name | Consumers constructing URLs with the old parameter name will receive routing failures |
| B9 | Change in authentication requirement — endpoint was unauthenticated, now requires auth | Unauthenticated consumers will receive 401/403 |
| B10 | Change in content type (e.g. `application/json` → `application/xml`) | Consumers sending the old content type will receive 415 Unsupported Media Type |
| B11 | Removal of a response status code that clients explicitly handle (any 4xx or 5xx code) | Consumer error-handling logic for the removed code will never execute — errors become unhandled |
| B12 | Renaming of a `$ref` component used in request bodies | All consumers referencing the component by its old name will fail if they validate against component names |

---

## High-Severity (Breaking in Practice — Document as High, Not Always Technically Breaking)

These changes are not universally breaking by HTTP specification but are breaking for the majority of real-world consumers. Classify as **High** and surface as likely breaking.

| # | Change Type | Why It Is High Severity |
|---|-------------|------------------------|
| H1 | Addition of an enum value to a response field that consumers switch on | Consumers with exhaustive switch/case logic will hit an unhandled case |
| H2 | Change in the `nullable` property of a field (non-nullable → nullable or vice versa) | Consumer type systems that model this field as non-optional will produce type errors |
| H3 | Removal of a response field that consumers depend on | Consumer code reading the removed field will receive `undefined` / null |

---

## Non-Breaking Changes (Additive)

These changes add capability without removing or narrowing anything existing. Existing consumers continue to work without modification.

| # | Change Type |
|---|-------------|
| N1 | Addition of a new endpoint (path + method) |
| N2 | Addition of a new optional request field |
| N3 | Addition of a new response field |
| N4 | Addition of a new enum value to a request parameter |
| N5 | Relaxing a type constraint (e.g. `integer` → `number`) |
| N6 | Relaxing a format constraint (e.g. `string format: uuid` → `string`) |
| N7 | Addition of a new query parameter that is optional |
| N8 | Addition of a new response status code |
| N9 | Adding a `description`, `summary`, or `example` to an existing field |

---

## Deprecated Changes (Non-Breaking Now, Breaking in Next Major Version)

These changes use the `deprecated: true` flag to signal intent. They are non-breaking in the current version but will become breaking in the next major version.

| # | Change Type | Recommended Consumer Action |
|---|-------------|----------------------------|
| D1 | Marking an endpoint as `deprecated: true` | Migrate to the replacement endpoint before the next major version |
| D2 | Marking a request field as `deprecated: true` | Stop sending the deprecated field |
| D3 | Marking a response field as `deprecated: true` | Stop reading the deprecated field |
| D4 | Marking an enum value as `deprecated` (via `x-deprecated: true` on the enum entry) | Stop sending or handling the deprecated value |

---

## Application Rules

1. Apply this list exhaustively to every diff item — do not stop after the first breaking change is found.
2. If a diff item matches multiple entries (e.g. a field removal that is both B2 and B3 if the field was both required in request and critical in response), classify it under all matching entries.
3. If a diff item does not match any entry on any list, classify it as **Non-Breaking (Unlisted)** and include it in the report with a note that it is unclassified.
4. Never silently omit a diff item — every change in the diff must appear in the report under exactly one classification.
5. H1, H2, H3 must be surfaced even when the technical HTTP specification would not classify them as breaking — real-world consumer impact takes precedence over strict specification compliance.
