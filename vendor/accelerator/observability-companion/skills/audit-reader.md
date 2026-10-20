---
name: audit-reader
description: |
  Conventions for reading .ai-baseline/audit.jsonl and date-sharded .ai-baseline/audit.YYYY-MM-DD.jsonl files. Import before any agent that reads the audit log. Provides the standard Bash commands for filtering and aggregating JSONL entries. Handles corrupted lines gracefully and supports schema_version branching.
---

# Audit Reader

## File location

Audit entries are written to date-sharded files: `.ai-baseline/audit.YYYY-MM-DD.jsonl` (one file per UTC day). A legacy `.ai-baseline/audit.jsonl` may also exist from earlier versions and must be included when reading.

## Canonical compact form

Every audit entry is a single compact JSON object (no extra whitespace) on one line. Do not assume pretty-printed or multi-line JSON.

## Reading all entries (shard-aware)

Always glob the full shard set and include the legacy file if present:

```bash
ROOT=$(git rev-parse --show-toplevel)
AUDIT_DIR="$ROOT/.ai-baseline"
# Collect all shard files; include legacy audit.jsonl for back-compat
SHARD_FILES=$(ls "$AUDIT_DIR"/audit.*.jsonl "$AUDIT_DIR"/audit.jsonl 2>/dev/null)
# Read all entries, skip unparseable lines (degraded mode)
cat $SHARD_FILES 2>/dev/null | jq -c 'fromjson? // empty'
```

The `jq -c 'fromjson? // empty'` pattern silently skips any line that is not valid JSON (corrupted or truncated lines) and emits the rest. Count skipped lines:

```bash
ALL=$(cat $SHARD_FILES 2>/dev/null | wc -l)
GOOD=$(cat $SHARD_FILES 2>/dev/null | jq -c 'fromjson? // empty' | wc -l)
SKIPPED=$((ALL - GOOD))
echo "$SKIPPED line(s) skipped (unparseable)"
```

## Filtering entries

Always use `grep -F` (fixed-string mode) for user-supplied values — never interpolate values as regex patterns.

```bash
# Entries for a specific agent
cat $SHARD_FILES 2>/dev/null | jq -c 'fromjson? // empty' | grep -F '"agent":"<agent-name>"'

# Entries for a specific session
cat $SHARD_FILES 2>/dev/null | jq -c 'fromjson? // empty' | grep -F '"session_id":"<uuid>"'

# Entries for a specific correlation_id (command chain)
cat $SHARD_FILES 2>/dev/null | jq -c 'fromjson? // empty' | grep -F '"correlation_id":"<uuid>"'

# Entries for a specific app/feature
cat $SHARD_FILES 2>/dev/null | jq -c 'fromjson? // empty' \
  | grep -F '"app":"<app>"' | grep -F '"feature":"<feature>"'

# Today's entries (ISO date prefix)
TODAY=$(date -u +%Y-%m-%d)
cat "$AUDIT_DIR/audit.${TODAY}.jsonl" 2>/dev/null | jq -c 'fromjson? // empty'

# Entries spanning two specific date shards
cat "$AUDIT_DIR/audit.2026-06-20.jsonl" "$AUDIT_DIR/audit.2026-06-21.jsonl" 2>/dev/null \
  | jq -c 'fromjson? // empty'
```

## Schema version branching

When processing entries from multiple schema versions, branch on `schema_version`:

```bash
cat $SHARD_FILES 2>/dev/null | jq -c 'fromjson? // empty' | while IFS= read -r line; do
  version=$(echo "$line" | jq -r '.schema_version // "legacy"')
  case "$version" in
    "1.0.0") echo "$line" | jq '...' ;;  # current schema processing
    "legacy") echo "$line" | jq '...' ;; # handle pre-schema_version entries
    *) echo "Unknown schema_version: $version" >&2 ;;
  esac
done
```

## Computing latency

Latency per entry is not stored — the audit log records invocation events, not durations. Estimate session duration from first to last `ts` within a `session_id`. Per-agent latency approximation: not available from the log alone.

## Hard Gates

**NEVER write to any .ai-baseline/audit*.jsonl file — read only.**
**NEVER delete or truncate any audit shard file.**
**NEVER pass user-supplied values directly to grep without validation — resolve project root with git rev-parse first.**
**NEVER crash when a line is unparseable — skip it with `jq -c 'fromjson? // empty'` and report N skipped.**
