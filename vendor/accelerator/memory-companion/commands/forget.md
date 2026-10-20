---
description: Delete a memory entry. Usage: /forget <namespace> <key>
---

Parse $ARGUMENTS: first word = namespace, second word = key.

If fewer than 2 words: `Usage: /forget <namespace> <key>`

Validate namespace (`^[a-z0-9_-]+$`) and key (`^[a-z0-9_.-]+$`). If invalid: `MEMORY_REJECTED: invalid namespace/key format`

Resolve project root via `git rev-parse --show-toplevel`. Construct path: `.ai-memory/<namespace>/<key>.json`. Verify resolved path starts with `<root>/.ai-memory/`. If path escape: `MEMORY_REJECTED: path escape attempt`.

If file exists: delete it and respond `MEMORY_DELETED: <namespace>/<key>`. If not: `MEMORY_NOT_FOUND: <namespace>/<key>`.
