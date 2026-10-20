---
name: pricing-table
description: |
  Model pricing defaults and .cost-monitor/pricing.json override convention. Import before any agent that computes spend from token counts.
---

# Pricing Table

## Default prices (USD per token)

| Model | Input | Output |
|---|---|---|
| claude-opus-4-8 | $0.000015 | $0.000075 |
| claude-opus-4-7 | $0.000015 | $0.000075 |
| claude-sonnet-4-6 | $0.000003 | $0.000015 |
| claude-haiku-4-5-20251001 | $0.00000025 | $0.00000125 |

The ai-baseline budget feed reads these defaults from the accelerator's own `pricing.json` data file (not the project override below); keep this table in step with it.

## Cost formula

`cost = (tokens_in × input_rate) + (tokens_out × output_rate)`

## Override file

`.cost-monitor/pricing.json` at project root. If present, its values override defaults for matching model IDs. Missing model IDs fall back to defaults.

## Reading the override

```bash
cat "<root>/.cost-monitor/pricing.json" 2>/dev/null
```

If absent: use defaults silently. Do not error.

## Unknown model IDs

If an audit entry contains a model ID not in the pricing table or override: use $0.000003 input / $0.000015 output (Sonnet rate) as a conservative estimate. Note: "Unknown model <id> — using Sonnet rate estimate."

## Hard Gates

**NEVER write to pricing.json — user-managed.**
**NEVER report a cost of $0 for a known model with non-zero token counts — that indicates a pricing lookup failure.**
**NEVER treat a missing pricing.json as an error — use defaults silently.**
