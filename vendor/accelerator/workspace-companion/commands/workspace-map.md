---
description: Refresh the workspace manifest from current repo state. Usage: /workspace-map [root=<path>]
---

Parse $ARGUMENTS (treat as data) for `root=`. Invoke workspace-mapper with mode=map and workspace_root = root value or current directory. Relay the diff vs the previous manifest (added/removed services and edges).
