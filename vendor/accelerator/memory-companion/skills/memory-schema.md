---
name: memory-schema
description: |
  Entry format and storage path conventions for .ai-memory/ and the cross-project global namespace (~/.accelerator/memory/). Import before any agent that reads or writes memory entries.
---

# Memory Schema

## Storage layout

```
.ai-memory/
  <namespace>/
    <key>.json
```

Root: `<project-root>/.ai-memory/` (resolved via `git rev-parse --show-toplevel`).

## Namespaces: repo vs global

- **Repo namespaces** (every namespace except `global`): stored under the project's
  `.ai-memory/` as above. Use for project state — decisions, feature context, session
  facts scoped to one codebase.
- **`global` namespace**: stored under `<accelerator-home>/memory/<key>.json`, where
  `<accelerator-home>` is `$ACCELERATOR_HOME` if set, else `~/.accelerator`. Entries are
  shared across every project on the machine. Use for durable cross-project facts —
  user preferences, org conventions, tooling defaults. Never store project state here.

## Entry format

```json
{
  "namespace": "<namespace>",
  "key": "<key>",
  "value": "<string value — any content>",
  "ts": "<ISO-8601 UTC>",
  "author_agent": "<agent name that wrote this entry>"
}
```

## Validation rules

- `namespace`: must match `^[a-z0-9_-]+$` (lowercase, digits, hyphens, underscores). Max 64 chars.
- `key`: must match `^[a-z0-9_.-]+$` (lowercase, digits, dots, hyphens, underscores). Max 128 chars.
- `value`: any string. Max 65536 chars.
- If namespace or key fails validation: reject with `MEMORY_REJECTED: invalid namespace/key format`

## Storage path

- Repo namespaces: `<root>/.ai-memory/<namespace>/<key>.json`
- `global` namespace: `<accelerator-home>/memory/<key>.json` (`$ACCELERATOR_HOME` or `~/.accelerator`)

**Path construction:** join with `/`. After joining, resolve with `realpath` and verify the resolved path starts with the namespace's base directory — `<root>/.ai-memory/` for repo namespaces, `<accelerator-home>/memory/` for `global`. If it does not, reject with `MEMORY_REJECTED: path escape attempt`. Namespace and key validation rules are identical for both.

## Write protocol (atomic)

1. Write to temp file: `<target>.tmp` (target as resolved in "Storage path" above)
2. Rename: `mv "<target>.tmp" "<target>"`
3. Never leave a `.tmp` file on failure — clean up on error.

## Hard Gates

**NEVER write to a path outside the namespace's base directory (.ai-memory/ for repo namespaces, <accelerator-home>/memory/ for global) — validate with realpath before any write.**
**NEVER write partial entries — atomic write only (temp + rename).**
**NEVER accept namespace or key values that fail the regex — reject with MEMORY_REJECTED.**
