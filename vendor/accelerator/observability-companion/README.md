# observability-companion

Optional plugin — structured telemetry on top of the ai-baseline audit log.

## Requirements

- requires: ai-baseline (reads `.ai-baseline/audit.jsonl`)

## Commands

- `/observe` — per-agent metrics: invocation counts, token usage, model breakdown
- `/slo-status` — compare metrics against SLO thresholds in `.observability/slo.json`
- `/trace <correlation_id>` — render full invocation chain for a command run

## SLO configuration

Create `.observability/slo.json` at project root:
```json
{
  "max_latency_ms": 30000,
  "min_success_rate": 0.95,
  "max_tokens_per_session": 100000
}
```

## Author

<your-name> (you@example.com)
