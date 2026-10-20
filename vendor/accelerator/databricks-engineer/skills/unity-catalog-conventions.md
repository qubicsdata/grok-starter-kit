---
name: unity-catalog-conventions
description: |
  Import before any Unity Catalog DDL, GRANT, or lineage operation. Provides the five-catalog
  layout, schema naming patterns, GRANT syntax, PII tagging syntax, lineage views, and naming
  rules. Triggers on: catalog creation, schema creation, GRANT statements, PII tagging,
  lineage queries, UC naming validation.
---

# Unity Catalog Conventions

## Five-Catalog Layout

| Catalog | Purpose | Schema Pattern |
|---|---|---|
| `landing` | Raw Delta tables per source system — extraction-agnostic contract | Per source system: `landing.<system>` e.g. `landing.sys01_ecc` |
| `bronze` | CDC-applied per source system — one schema per system | Per source system: `bronze.<system>` e.g. `bronze.sys01_ecc` |
| `silver` | Canonical model, business keys remapped, deduped | Per domain: `silver.<domain>` e.g. `silver.finance`, `silver.material` |
| `gold` | Harmonized enterprise layer — analytics-ready | Per domain: `gold.<domain>` e.g. `gold.finance`, `gold.material` |
| `outbound` | Load-agnostic contract per migration object — downstream consumers read here | Per migration object or system: `outbound.<target>` |
| `migration_meta` | Cross-reference tables, reconciliation results, migration state, sign-offs | Flat: `migration_meta.xref`, `migration_meta.recon`, `migration_meta.state`, `migration_meta.signoff` |

## Schema Naming Patterns

```
landing.sys01_ecc          -- SAP ECC system 01
landing.sys01_s4           -- SAP S/4HANA system 01
bronze.sys01_ecc           -- CDC-applied ECC tables
bronze.sys01_s4            -- CDC-applied S/4 tables
silver.finance             -- canonical finance domain
silver.material            -- canonical material domain
silver.customer            -- canonical customer domain
gold.finance               -- enterprise finance analytics
gold.material              -- enterprise material analytics
outbound.s4_target         -- migration outbound for S/4 target
migration_meta             -- single schema for all migration metadata
```

## GRANT Syntax — Full Reference

```sql
-- Catalog-level access
GRANT USE CATALOG ON CATALOG landing TO `group-name`;
GRANT USE CATALOG ON CATALOG bronze TO `group-name`;

-- Schema-level access
GRANT USE SCHEMA ON SCHEMA bronze.sys01_ecc TO `group-name`;
GRANT USE SCHEMA ON SCHEMA silver.finance TO `group-name`;

-- Table creation (service principals, pipeline service accounts)
GRANT CREATE TABLE ON SCHEMA bronze.sys01_ecc TO `svc-pipeline-ecc`;
GRANT CREATE TABLE ON SCHEMA silver.finance TO `svc-pipeline-silver`;

-- Read access
GRANT SELECT ON TABLE gold.finance.gl TO `analysts`;
GRANT SELECT ON TABLE silver.finance.gl_line TO `data-engineers`;

-- Write access (rare — prefer pipeline service principals)
GRANT MODIFY ON TABLE outbound.s4_target.gl TO `svc-outbound`;

-- All privileges (admin only)
GRANT ALL PRIVILEGES ON SCHEMA migration_meta TO `data-platform-admins`;

-- Revoke
REVOKE SELECT ON TABLE gold.finance.gl FROM `former-group`;
```

**Privilege levels by role:**

| Role | Privileges |
|---|---|
| Analyst | `USE CATALOG`, `USE SCHEMA`, `SELECT` on gold tables |
| Data Engineer | `USE CATALOG`, `USE SCHEMA`, `SELECT` on silver/gold, `CREATE TABLE` via service principal |
| Pipeline Service Principal | `USE CATALOG`, `USE SCHEMA`, `CREATE TABLE`, `MODIFY` on target schema |
| Platform Admin | `ALL PRIVILEGES` on owned catalogs/schemas |

## PII Tagging Syntax

```sql
-- Single column
ALTER TABLE silver.customer.person
  ALTER COLUMN ssn
  SET TAGS ('pii' = 'true', 'pii_type' = 'ssn');

-- Multiple columns (run per column)
ALTER TABLE silver.customer.person
  ALTER COLUMN email
  SET TAGS ('pii' = 'true', 'pii_type' = 'email');

ALTER TABLE silver.customer.person
  ALTER COLUMN phone_number
  SET TAGS ('pii' = 'true', 'pii_type' = 'phone');

ALTER TABLE silver.customer.person
  ALTER COLUMN date_of_birth
  SET TAGS ('pii' = 'true', 'pii_type' = 'dob');
```

Common `pii_type` values: `ssn`, `email`, `phone`, `dob`, `name`, `address`, `ip_address`, `iban`, `passport`, `national_id`.

**Query PII-tagged columns:**
```sql
SELECT table_catalog, table_schema, table_name, column_name, tag_value
FROM system.information_schema.column_tags
WHERE tag_name = 'pii' AND tag_value = 'true';
```

## Lineage Views

```sql
-- Column-level lineage
SELECT *
FROM system.access.column_lineage
WHERE target_table_full_name = 'gold.finance.gl'
ORDER BY event_time DESC
LIMIT 100;

-- Table-level lineage (upstream dependencies)
SELECT *
FROM system.access.table_lineage
WHERE target_table_full_name = 'silver.finance.gl_line'
ORDER BY event_time DESC;

-- Table-level lineage (downstream consumers)
SELECT *
FROM system.access.table_lineage
WHERE source_table_full_name = 'bronze.sys01_ecc.bkpf'
ORDER BY event_time DESC;
```

## Naming Rules

1. **Lowercase only** — no uppercase letters in catalog, schema, table, or column names.
2. **Snake_case** — words separated by underscores. No hyphens, spaces, or dots within a name component.
3. **No reserved SQL words** as standalone names (`select`, `table`, `schema`, `default`, `catalog`, `order`, `group`, etc.). If a reserved word is needed as a suffix, prefix it: `gl_order` not `order`.
4. **Source system identifiers** — use `sys01_ecc`, `sys01_s4` format for system-scoped schemas. Never use raw system names that contain spaces or special characters.
5. **Domain identifiers** — use short, stable domain names: `finance`, `material`, `customer`, `vendor`, `hr`, `logistics`.
6. **Migration meta tables** — use `xref_`, `recon_`, `state_`, `signoff_` prefixes within `migration_meta`.
7. **Length** — catalog and schema names: maximum 64 characters. Table names: maximum 128 characters.

## SCD2 Retention Warning

SCD2 history tables accumulate rows indefinitely. Apply a retention policy:

```sql
-- Check row growth
SELECT COUNT(*) AS total_rows, MIN(__START_AT) AS earliest_record
FROM silver.customer.person_history;

-- Set table retention (soft delete) — do NOT use VACUUM on SCD2 history
ALTER TABLE silver.customer.person_history
  SET TBLPROPERTIES ('delta.logRetentionDuration' = 'interval 365 days');
```

**Do NOT run `VACUUM` on SCD2 history tables** — it permanently deletes historical records.

## Hard Gates

**DO NOT generate DDL with names containing uppercase letters, spaces, or reserved SQL words.**
**DO NOT issue DROP CATALOG or DROP SCHEMA without a hard confirmation gate (user must type "CONFIRM").**
**DO NOT run VACUUM on SCD2 history tables.**
**DO NOT generate GRANT statements with invented privilege names — use only the privileges listed above.**
**STOP if DATABRICKS_CONFIG_PROFILE is unset before executing any DDL or DCL.**
