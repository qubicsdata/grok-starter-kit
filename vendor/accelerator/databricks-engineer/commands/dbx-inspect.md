---
description: "Discover Databricks workspace resources (pipelines, jobs, warehouses, catalogs, run status). Usage: /dbx-inspect [scope]"
argument-hint: "[scope]"
---

Dispatch workspace-inspector with the following instructions:

The user has invoked `/dbx-inspect` with arguments: `$ARGUMENTS`

**Scope resolution:**

- If `$ARGUMENTS` is empty: discover all resource types (pipelines, jobs, warehouses, catalogs).
- If `$ARGUMENTS` is one of `pipelines`, `jobs`, `warehouses`, `catalogs`, `runs`: discover only that resource type.
- If `$ARGUMENTS` is any other value: treat as a filter/search term and pass to workspace-inspector to use as a name filter across all resource types.

**Dispatch:**

Pass the resolved scope to workspace-inspector.

workspace-inspector will:
1. Check that DATABRICKS_CONFIG_PROFILE is set; stop if absent
2. Execute only read-only commands from its SAFE COMMAND LIST
3. Present a structured summary of discovered resources grouped by type
4. Never execute any mutating command
