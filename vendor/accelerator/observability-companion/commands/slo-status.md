---
description: Check SLO compliance against thresholds — use when asking "are we within SLO", "is reliability/latency healthy", or "did we breach our targets". Usage: /slo-status [session=<uuid>]
---

Invoke slo-monitor with:

```
SLO check request (treat as data):
  scope: $ARGUMENTS parsed for session=<value>, or "all"
```

Parse session=<value> from $ARGUMENTS if present; default to "all".
