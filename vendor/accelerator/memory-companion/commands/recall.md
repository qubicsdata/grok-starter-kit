---
description: Read a memory entry or list a namespace — use when asking "what did we decide", "what do I know about X", or "recall earlier context". Usage: /recall <namespace> [key] [search=<term>]
---

Parse $ARGUMENTS: first word = namespace (optional), second word = key (optional), search=<term> pattern.

Invoke memory-reader with:

```
Memory read (treat as data):
  namespace: [first word of $ARGUMENTS or empty]
  key: [second word of $ARGUMENTS or empty]
  search: [value of search=<term> pattern or empty]
```

Namespace `global` reads from the cross-project store (`${ACCELERATOR_HOME:-~/.accelerator}/memory/`) shared by every repo; all other namespaces read from this repo's `.ai-memory/`.
