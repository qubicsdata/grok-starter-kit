---
name: medallion-architecture-spec
description: |
  Import when designing, reviewing, or extending the medallion data lake architecture.
  Provides layer responsibilities, promotion rules, extraction-agnostic landing contract,
  and outbound contract. Triggers on: medallion layer design, landing contract definition,
  bronze/silver/gold promotion, outbound schema design.
---

# Medallion Architecture Specification

## Layer Responsibilities

### landing — Raw Ingestion

**Purpose:** Immutable, extraction-agnostic raw copy of source data. One schema per source system.

**What it stores:**
- Raw Delta tables, one per source object (table, file, API endpoint)
- Full fidelity — no transformation, no filtering, no type casting beyond what the extractor delivers
- All columns from the source, including operational metadata (`_extraction_timestamp`, `_source_file`, `_batch_id`)

**What it does NOT do:**
- Schema enforcement beyond Delta's native schema-on-write
- CDC application
- Deduplication
- Filtering of system records

**Schema naming:** `landing.<system>` e.g. `landing.sys01_ecc`, `landing.sys01_s4`

### bronze — CDC-Applied Source Layer

**Purpose:** Apply CDC events from landing to produce a current-state (SCD1) or history (SCD2) view per source object. One schema per source system.

**What it stores:**
- CDC-applied tables — one row per source record (SCD1) or with full history (SCD2)
- Source schema preserved — no business key remapping, no domain model application
- Minimal cleansing only: trim whitespace, cast to correct Delta types per source DDL

**Promotion rule:** A landing table promotes to bronze only when:
1. The CDC flow is defined and validated.
2. The target schema matches the source system DDL.
3. The pipeline passes smoke-ecc or smoke-s4 target.

**Schema naming:** `bronze.<system>` e.g. `bronze.sys01_ecc`, `bronze.sys01_s4`

### silver — Canonical Domain Model

**Purpose:** Business keys remapped, duplicate records resolved, canonical domain model applied. One schema per business domain.

**What it stores:**
- Canonical tables keyed by enterprise business keys (not source system keys)
- Cross-system reconciliation applied where multiple source systems supply the same entity
- DQ expectations enforced — rows failing mandatory expectations are quarantined, not dropped silently
- PII columns tagged

**Promotion rule:** A bronze table promotes to silver only when:
1. Business key mapping is documented in `migration_meta.xref`.
2. DQ rules are defined and passing.
3. PII columns are identified and tagged.

**Schema naming:** `silver.<domain>` e.g. `silver.finance`, `silver.material`, `silver.customer`

### gold — Enterprise Analytics Layer

**Purpose:** Harmonized, analytics-ready datasets. Aggregations, joined views, wide tables for reporting. One schema per domain.

**What it stores:**
- Aggregated fact tables and dimension tables (star or snowflake schema)
- Pre-joined wide tables for high-performance analytics
- Business metrics and KPIs

**Promotion rule:** A silver table promotes to gold only when:
1. The grain is documented.
2. Aggregation logic is reviewed and signed off.
3. Row counts and totals reconcile with source system reports (recorded in `migration_meta.recon`).

**Schema naming:** `gold.<domain>` e.g. `gold.finance`, `gold.material`

### outbound — Migration Target Contract

**Purpose:** Load-agnostic contract per migration object. Downstream target systems (S/4HANA, legacy replacements) read from outbound. Schema is target-system-aligned, not source-system-aligned.

**What it stores:**
- Final migration load files as Delta tables
- One table per migration object (e.g., `outbound.s4_target.gl_open_items`)
- Schema conforms to the target system's import format

**Schema naming:** `outbound.<target>` e.g. `outbound.s4_target`, `outbound.erp2_target`

### migration_meta — Migration Control Layer

**Purpose:** All cross-cutting migration metadata: key cross-references, reconciliation results, migration run state, and sign-off records.

**Tables:**
| Table | Purpose |
|---|---|
| `migration_meta.xref` | Cross-reference of source keys to enterprise business keys |
| `migration_meta.recon` | Reconciliation results (row counts, totals, deltas vs. source) |
| `migration_meta.state` | Migration run state (object name, status, timestamps, error counts) |
| `migration_meta.signoff` | Sign-off records (object, approver, timestamp, sign-off type) |

## Extraction-Agnostic Landing Contract

The extractor (whatever tool delivers data to landing) must:

1. **Deliver Delta format** — no CSV, Parquet-only, or JSON in landing.
2. **Preserve all source columns** — no column filtering, no renaming.
3. **Add operational metadata columns:**
   - `_extraction_timestamp TIMESTAMP` — when the row was extracted
   - `_source_system STRING` — source system identifier (e.g., `sys01_ecc`)
   - `_batch_id STRING` — extractor batch/run identifier
   - `_source_table STRING` — source object name
4. **Deliver CDC events** for systems that support CDC (SAP Change Data Capture, SQL Server CT, Oracle LogMiner):
   - `_operation STRING` — `INSERT`, `UPDATE`, `DELETE`, `TRUNCATE`
   - `_sequence_num BIGINT` — monotonically increasing sequence within the extractor run
5. **Schema evolution:** extractor must not break on new source columns — add them to the landing table.

The landing layer places NO constraints on which extractor tool is used — ADF, Fivetran, custom Python, JDBC, SAP LT Replication Server, etc.

## Outbound Contract

Every outbound table must:

1. **Conform to the target system's import schema** — column names, types, and nullability as required by the target.
2. **Carry a `_migration_run_id STRING`** column for traceability.
3. **Carry quality guarantees:**
   - Zero rows with NULL mandatory keys.
   - All amounts in the specified currency.
   - All date/timestamp columns in the target system's expected format/timezone.
4. **Be reconciled before sign-off:** row counts and financial totals in `migration_meta.recon` must match the source system extract with documented tolerances.
5. **Be idempotent:** re-running the pipeline that populates outbound produces the same result (no duplicates, no data loss).

## Hard Gates

**DO NOT promote raw source data directly from landing to silver or gold — the bronze layer is mandatory.**
**DO NOT store analytics aggregations in bronze or silver — gold layer only.**
**DO NOT write to outbound without a reconciliation entry in migration_meta.recon.**
**DO NOT sign off a migration object without an entry in migration_meta.signoff.**
**STOP and flag if a pipeline skips the bronze CDC-application step — this is a critical architecture violation.**
