# memory-companion

Optional plugin — cross-session, cross-plugin persistent memory.

## Commands

- `/remember <namespace> <key> <value>` — write a memory entry
- `/recall <namespace> [key]` — read an entry or list all keys in namespace
- `/forget <namespace> <key>` — delete an entry

## Storage

Entries stored in `.ai-memory/<namespace>/<key>.json` at project root. Atomic writes only.

## Using in agents

Import `memory-context-skill` in any agent to inject relevant past memory into its prompt at invocation time.

## Entry format

```json
{
  "namespace": "my-plugin",
  "key": "last-scan-result",
  "value": "...",
  "ts": "2026-06-19T14:00:00Z",
  "author_agent": "my-agent"
}
```

## Author

<your-name> (you@example.com)

## Dependencies

- requires: ai-baseline
