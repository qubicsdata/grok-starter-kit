---
name: enrich-result-schema
description: |
  Schema for `.ai-baseline/enrich-result.json`, the structured record the enrich runner writes alongside the spec's `## Production Requirements` section. It persists which enrichers fired, the computed risk inputs, and the resulting review tier, so downstream machinery (and a consumer's review loop) can read structured data instead of re-parsing a prose report.
contract_version: 1.0.0
---

# Enrich Result Schema

The `/enrich` runner writes one JSON object to `.ai-baseline/enrich-result.json` in
the **consumer working directory** (never inside the accelerator tree) each time it
enriches a spec. It is the structured companion to the human-readable `## Production
Requirements` and `## Review Plan` sections written into the spec itself.

## Location

`.ai-baseline/enrich-result.json` — consumer cwd, like the audit log
(`.ai-baseline/audit.*.jsonl`). It is a runtime artifact, gitignored by consumers,
and MUST NOT be written into the accelerator repository.

## Fields

| # | Field | Type | Meaning |
|---|-------|------|---------|
| 1 | `schema_version` | string | always `"1.0.0"` |
| 2 | `ts` | string | ISO-8601 UTC write time |
| 3 | `spec_path` | string | absolute path of the enriched spec |
| 4 | `fired` | string[] | plugin names whose enricher returned requirements |
| 5 | `abstained` | string[] | plugin names whose enricher returned NOT_APPLICABLE |
| 6 | `surfaces` | integer | distinct runtime surfaces found in the spec (CLI, HTTP API, frontend/UI, datastore, queue/worker) |
| 7 | `security_sensitive` | boolean | a security/auth/compliance enricher fired, or the security keyword scan matched |
| 8 | `risk` | integer | `len(fired) + 2*surfaces + (3 if security_sensitive else 0)` |
| 9 | `tier` | string | `"light"` (risk 0–2), `"standard"` (3–6), or `"full"` (≥7), after force-floors |
| 10 | `must_ids` | string[] | every injected requirement ID (e.g. `["OBS-1","API-2",...]`) — the review checklist |

## Canonical example

```json
{"schema_version":"1.0.0","ts":"2026-06-21T20:14:05Z","spec_path":"/work/spec.md","fired":["api-designer","observability-companion","dev-companion"],"abstained":["data-companion","cost-monitor"],"surfaces":2,"security_sensitive":false,"risk":7,"tier":"full","must_ids":["API-1","API-2","OBS-1","OBS-2","DEV-1","DEV-2"]}
```

## Tier derivation

`risk` and `tier` follow `ai-baseline/skills/risk-tier-spec.md` exactly, including the
force-floors (security_sensitive ⇒ tier ≥ standard). The `tier` field is authoritative:
downstream readers use it directly rather than recomputing.

## Consumers

- A consumer's review loop reads `tier` and `must_ids` to size its review and anchor it
  to the requirement checklist (advisory — the superpowers SDD skill is external).
- The spec's `## Review Plan` section is the human-readable mirror of `tier` + the model
  tiers + a pointer to `must_ids`.
