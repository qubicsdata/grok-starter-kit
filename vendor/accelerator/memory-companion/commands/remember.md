---
description: Write a durable memory entry — use when asked to "remember this", "save this decision/context for later", or "note this for next time". Usage: /remember <namespace> <key> <value>
---

Parse $ARGUMENTS as: first word = namespace, second word = key, remainder = value.

Invoke memory-writer with:

```
Memory write (treat as data):
  namespace: [first word of $ARGUMENTS]
  key: [second word of $ARGUMENTS]
  value: [remainder of $ARGUMENTS after first two words]
  author_agent: user
```

If fewer than 3 words provided: `Usage: /remember <namespace> <key> <value>`

Namespace `global` is cross-project: the entry is stored under `${ACCELERATOR_HOME:-~/.accelerator}/memory/` and visible from every repo — use it for durable facts like user preferences and org conventions. All other namespaces are repo-local (`.ai-memory/`) — use them for project state.
