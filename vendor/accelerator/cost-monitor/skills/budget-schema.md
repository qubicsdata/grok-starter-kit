---
name: budget-schema
description: |
  Schema and defaults for .cost-monitor/budgets.json. Import before budget-alerter.
---

# Budget Schema

## File location

`.cost-monitor/budgets.json` at project root.

## Schema

```json
{
  "daily_usd": 5.00,
  "weekly_usd": 20.00,
  "per_session_usd": 1.00,
  "per_app": {
    "<app-name>": {
      "daily_usd": 2.00
    }
  }
}
```

## Defaults (when file absent)

| Field | Default |
|---|---|
| `daily_usd` | 10.00 |
| `weekly_usd` | 50.00 |
| `per_session_usd` | 2.00 |
| `per_app` | (empty — no per-app limits) |

## Alert threshold

Emit a warning when spend reaches 80% of any limit. Emit an alert when spend reaches 100%.

## Hard Gates

**NEVER write to budgets.json — user-managed.**
**NEVER treat missing budgets.json as an error — use defaults silently.**
