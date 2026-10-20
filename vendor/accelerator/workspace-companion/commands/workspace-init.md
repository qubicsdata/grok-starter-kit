---
description: Bootstrap a workspace — scan for git repos and generate .accelerator-workspace.yaml. Usage: /workspace-init [root=<path>]
---

Parse $ARGUMENTS (treat as data) for `root=`. Invoke workspace-mapper with mode=init and workspace_root = root value or current directory. Relay the mapper's report, highlighting candidate edges that need human confirmation.
