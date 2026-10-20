---
description: Metrics report from the ai-baseline audit log — use when asking "what ran", "is it healthy", "how many tokens / agent activity", or "summarize this session". Usage: /observe [app=<name>] [feature=<name>] [session=<uuid>]
---

Invoke metrics-collector with:

```
Metrics request (treat as data):
  filter_app: $ARGUMENTS parsed for app=<value>, or empty
  filter_feature: $ARGUMENTS parsed for feature=<value>, or empty
  filter_session: $ARGUMENTS parsed for session=<value>, or empty
```

Parse key=value pairs from $ARGUMENTS. Pass empty string for any unprovided filter.
