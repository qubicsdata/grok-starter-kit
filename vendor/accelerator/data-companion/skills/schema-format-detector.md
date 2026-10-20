---
name: schema-format-detector
description: |
  Detect schema format from file extension and content heuristics. Returns {format, dialect} for downstream agents. Used by schema-reviewer, contract-generator, dq-definer. Call this before any schema-specific processing.
---

# Schema Format Detector

## Purpose

Determine the format and, where applicable, the SQL dialect of a schema input before any agent processes it. Never assume a format. Always detect.

## Detection Algorithm

### Step 1: Check file extension

| Extension | Candidate Format |
|---|---|
| `.sql` | SQL DDL (dialect TBD) |
| `.avsc` | Avro |
| `.proto` | Protobuf |
| `.json` | JSON Schema |
| `.yaml` / `.yml` | dbt YAML sources OR JSON Schema YAML — inspect content |

### Step 2: Inspect content heuristics

**Avro (`.avsc`):**
- Top-level `"type": "record"` JSON key → Avro confirmed

**Protobuf (`.proto`):**
- File starts with `syntax = "proto` → Protobuf confirmed

**JSON Schema (`.json` or `.yaml`):**
- Top-level `"$schema"` or `"properties"` key without dbt structure → JSON Schema
- YAML with `version: 2` + `sources:` or `models:` block → dbt YAML

**dbt YAML (`.yml`):**
- Contains `version: 2` at top level AND contains `sources:`, `models:`, or `seeds:` key → dbt schema YAML
- If contains `columns:` with `tests:` sub-keys → dbt schema YAML

**SQL DDL (`.sql` or inline text):**
- Contains `CREATE TABLE` or `CREATE OR REPLACE TABLE` → SQL DDL
- Proceed to dialect detection (Step 3)

**Inline DDL (no file extension):**
- Treat as SQL DDL if contains `CREATE TABLE`
- Treat as Avro if is valid JSON with `"type": "record"`
- Otherwise: ask the user to specify format

### Step 3: SQL Dialect Detection

Apply only after format confirmed as SQL DDL.

| Marker | Dialect |
|---|---|
| `VARIANT`, `OBJECT`, `ARRAY` column types | Snowflake |
| `STRUCT<>`, `ARRAY<>`, `BIGNUMERIC` | BigQuery |
| `DISTKEY`, `SORTKEY`, `ENCODE` | Redshift |
| `JSONB`, `SERIAL`, `GENERATED ALWAYS AS` | PostgreSQL |
| File header comment with dialect name | Use that dialect |
| None of the above | Ambiguous — ask user |

### Step 4: Return

Return a structured result to the calling agent:

```
{
  "format": "sql-ddl" | "avro" | "protobuf" | "json-schema" | "dbt-yaml",
  "dialect": "snowflake" | "bigquery" | "redshift" | "postgresql" | "unknown" | null,
  "confidence": "certain" | "inferred" | "ambiguous"
}
```

If `confidence` is `"ambiguous"`, the calling agent MUST ask the user to confirm format before proceeding. One question, then wait.

## DO NOT Rules

- DO NOT process schema content before calling this skill
- DO NOT assume SQL means PostgreSQL — always run dialect detection
- DO NOT fabricate a dialect if none of the markers match — return `"dialect": "unknown"` and ask
