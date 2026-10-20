# cost-monitor

Optional plugin — rich spend tracking on top of the ai-baseline audit log.

## Requirements

- requires: ai-baseline (reads `.ai-baseline/audit.jsonl`)

## Commands

- `/cost-report [app=<name>] [feature=<name>] [period=today|week|all]` — spend breakdown by app, feature, session, plugin, agent
- `/budget-status` — compare current spend against `.cost-monitor/budgets.json` thresholds

## Configuration

Create `.cost-monitor/pricing.json` to override default model prices:
```json
{
  "claude-opus-4-8": {"input": 0.000015, "output": 0.000075},
  "claude-sonnet-4-6": {"input": 0.000003, "output": 0.000015},
  "claude-haiku-4-5-20251001": {"input": 0.00000025, "output": 0.00000125}
}
```

Create `.cost-monitor/budgets.json` for budget alerts:
```json
{
  "daily_usd": 5.00,
  "weekly_usd": 20.00,
  "per_session_usd": 1.00,
  "per_app": {
    "billing": {"daily_usd": 2.00}
  }
}
```

## Author

<your-name> (you@example.com)
