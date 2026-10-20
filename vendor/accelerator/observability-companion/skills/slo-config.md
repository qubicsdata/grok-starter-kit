---
name: slo-config
description: |
  Schema and defaults for .observability/slo.json. Import before any agent that reads or enforces SLO thresholds.
---

# SLO Configuration

## File location

`.observability/slo.json` at project root.

## Schema

```json
{
  "max_latency_ms": 30000,
  "min_success_rate": 0.95,
  "max_tokens_per_session": 100000
}
```

## Defaults (when file absent)

| Field | Default | Meaning |
|---|---|---|
| `max_latency_ms` | 30000 | 30-second session ceiling |
| `min_success_rate` | 0.95 | 95% of invocations must complete without BUDGET_EXCEEDED or AUDIT_REJECTED |
| `max_tokens_per_session` | 100000 | Token ceiling per session_id |

## Reading

```bash
cat "<root>/.observability/slo.json" 2>/dev/null || echo '{"max_latency_ms":30000,"min_success_rate":0.95,"max_tokens_per_session":100000}'
```

## Hard Gates

**NEVER write to .observability/slo.json from an agent — this file is user-managed.**
**NEVER treat missing slo.json as an error — use defaults silently.**
