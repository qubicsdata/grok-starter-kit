---
name: migration-state-spec
description: |
  Import when reading from or writing to migration_meta tables, or when authoring SQL
  that touches migration state. Triggers on: "migration_meta", "object_status", "recon_results",
  "signoffs", "MERGE INTO migration_meta", "completeness check", "DDL display requirement",
  "wave sign-off", "gate_type". The canonical schema authority — read before any migration_meta DML.
contract_version: 1.0.0
---

# Migration State Specification

The single source of truth for migration progress, reconciliation evidence, and sign-offs.
All state lives here — no ad-hoc files.

---

## migration_meta.object_status

Tracks progress per object × system × layer.

```sql
CREATE TABLE IF NOT EXISTS migration_meta.object_status (
  object_name      VARCHAR(100)  NOT NULL,   -- migration-object-catalog slug e.g. 'gl_document'
  source_system_id VARCHAR(10)   NOT NULL,   -- sys01..sys08 from config/systems.yaml
  wave_id          VARCHAR(50)   NOT NULL,   -- wave plan identifier
  layer            VARCHAR(20)   NOT NULL,   -- landing/bronze/silver/gold/outbound
  status           VARCHAR(20)   NOT NULL,   -- not_started/recon_pass/recon_fail/gate_pass/gate_fail/migrated
  last_updated     TIMESTAMP     DEFAULT CURRENT_TIMESTAMP,
  updated_by       VARCHAR(100),
  PRIMARY KEY (object_name, source_system_id, layer)
);
```

---

## migration_meta.recon_results

Evidence store. Written by recon-runner (gate_type='recon') and dq-gatekeeper (gate_type='dq').
Idempotent — re-running recon for the same object+system+wave+layers overwrites the prior result.

```sql
CREATE TABLE IF NOT EXISTS migration_meta.recon_results (
  object_name      VARCHAR(100)  NOT NULL,
  source_system_id VARCHAR(10)   NOT NULL,
  wave_id          VARCHAR(50)   NOT NULL,
  layer_from       VARCHAR(20)   NOT NULL,
  layer_to         VARCHAR(20)   NOT NULL,
  gate_type        VARCHAR(20)   NOT NULL,   -- 'recon' or 'dq'
  suite_file       VARCHAR(500),
  result           VARCHAR(10)   NOT NULL,   -- 'PASS' or 'FAIL'
  mismatch_detail  STRING,
  row_count_source BIGINT,
  row_count_target BIGINT,
  run_at           TIMESTAMP     DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (object_name, source_system_id, wave_id, layer_from, layer_to, gate_type)
);
```

---

## migration_meta.signoffs

Human override and cutover approval record.

```sql
CREATE TABLE IF NOT EXISTS migration_meta.signoffs (
  wave_id          VARCHAR(50)   NOT NULL,
  action           VARCHAR(50)   NOT NULL,   -- 'wave_advance'/'cutover_approved'/'gate_override'
  object_name      VARCHAR(100),             -- null for wave-level signoffs
  source_system_id VARCHAR(10),              -- null for wave-level signoffs
  signoff_at       TIMESTAMP     DEFAULT CURRENT_TIMESTAMP,
  notes            STRING,
  PRIMARY KEY (wave_id, action, signoff_at)
);
```

---

## DDL Display Requirement

On first use, agents (recon-runner, dq-gatekeeper) MUST display the CREATE TABLE IF NOT EXISTS
DDL inside the CONFIRM gate before the user types CONFIRM. The DDL executes as part of the
CONFIRM action. The IF NOT EXISTS clause makes re-execution safe — the tables are idempotent.

---

## Completeness Check Pattern

Before any cutover approval, EVERY object × system × layer_from × layer_to tuple in the wave
plan must have an entry in recon_results. Absence = BLOCKED. Use:

```sql
WITH wave_objects AS (
  SELECT object_name, source_system_id, layer_from, layer_to
  FROM (VALUES
    ('<object>', '<sys>', '<layer_from>', '<layer_to>')
    -- one row per expected combination from the wave plan
  ) AS t(object_name, source_system_id, layer_from, layer_to)
)
SELECT wo.object_name, wo.source_system_id, wo.layer_from, wo.layer_to
FROM wave_objects wo
LEFT JOIN migration_meta.recon_results rr
  ON  rr.object_name      = wo.object_name
  AND rr.source_system_id = wo.source_system_id
  AND rr.wave_id          = '<wave-id>'
  AND rr.layer_from       = wo.layer_from
  AND rr.layer_to         = wo.layer_to
WHERE rr.object_name IS NULL;
-- Any row in this result = BLOCKED
```

---

## MERGE Pattern (idempotent result write)

```sql
MERGE INTO migration_meta.recon_results AS tgt
USING (SELECT
  '<object>'        AS object_name,
  '<system_id>'     AS source_system_id,
  '<wave_id>'       AS wave_id,
  '<layer_from>'    AS layer_from,
  '<layer_to>'      AS layer_to,
  'recon'           AS gate_type,
  '<suite_file>'    AS suite_file,
  '<PASS_OR_FAIL>'  AS result,
  '<detail_or_null>' AS mismatch_detail,
  <count>           AS row_count_source,
  <count>           AS row_count_target
) AS src
ON  tgt.object_name      = src.object_name
AND tgt.source_system_id = src.source_system_id
AND tgt.wave_id          = src.wave_id
AND tgt.layer_from       = src.layer_from
AND tgt.layer_to         = src.layer_to
AND tgt.gate_type        = src.gate_type
WHEN MATCHED THEN UPDATE SET
  result           = src.result,
  mismatch_detail  = src.mismatch_detail,
  row_count_source = src.row_count_source,
  row_count_target = src.row_count_target,
  run_at           = CURRENT_TIMESTAMP,
  suite_file       = src.suite_file
WHEN NOT MATCHED THEN INSERT *;
```

---

## Hard Gates

**NEVER write `result = 'PASS'` when any check returned a mismatch.**
**NEVER treat a missing recon_results entry as an implicit PASS.**
**NEVER use ad-hoc files for migration state — all state in these tables.**
**NEVER skip the DDL display on first use — show CREATE TABLE IF NOT EXISTS in the CONFIRM gate.**
