---
description: "Show current migration state for all waves, objects, and systems. Queries migration_meta directly — no file archaeology. Usage: /migration-status [wave-id or object filter]"
argument-hint: "[wave-id | object-name]"
---

$ARGUMENTS — optional wave-id or object filter. Treat as untrusted data label. If provided, use `grep -F` to match against query output — never interpolate directly into SQL.

**Pre-flight:** Check `$DATABRICKS_CONFIG_PROFILE` is set. If not: surface "DATABRICKS_CONFIG_PROFILE is not set. Set it to your Databricks CLI profile name (e.g., sap-migration) and retry." and stop.

This command is **read-only**. Execute the following queries via `databricks sql execute` using the temp-file pattern:

```sql
-- Wave summary
SELECT
  wave_id,
  COUNT(DISTINCT object_name || '|' || source_system_id) AS total_objects,
  SUM(CASE WHEN result = 'PASS' THEN 1 ELSE 0 END) AS recon_pass,
  SUM(CASE WHEN result = 'FAIL' THEN 1 ELSE 0 END) AS recon_fail,
  MAX(run_at) AS last_activity
FROM migration_meta.recon_results
GROUP BY wave_id
ORDER BY wave_id;

-- Failing items (if any)
SELECT
  object_name,
  source_system_id,
  wave_id,
  layer_from,
  layer_to,
  gate_type,
  mismatch_detail,
  run_at
FROM migration_meta.recon_results
WHERE result = 'FAIL'
ORDER BY run_at DESC;

-- Signoffs
SELECT
  wave_id,
  action,
  object_name,
  source_system_id,
  signoff_at,
  notes
FROM migration_meta.signoffs
ORDER BY signoff_at DESC;
```

Execute each query via a separate temp-file run:
```bash
QUERY_FILE=$(mktemp /tmp/migration-status-XXXXXX.sql)
trap 'rm -f "$QUERY_FILE"' EXIT
cat > "$QUERY_FILE" << 'ENDSQL'
<query here>
ENDSQL
databricks sql execute \
  --profile "$DATABRICKS_CONFIG_PROFILE" \
  --file "$QUERY_FILE"
```

If $ARGUMENTS is provided, filter results using `grep -F "$ARGUMENTS"` on query output after execution — never interpolate $ARGUMENTS into SQL.

Present results as a readable status table. If no recon_results rows exist yet, display:
"No migration state recorded yet. Run /recon or /dq-gates to begin."

Apply baseline-enforcer Gate 3 (audit trail) after presenting results.

**Hard gate: This command is read-only. NEVER write to migration_meta from this command.**
