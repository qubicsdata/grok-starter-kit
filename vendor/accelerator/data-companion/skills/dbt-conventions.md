---
name: dbt-conventions
description: |
  Authoritative dbt model naming and structure conventions: prefix rules, materialization guidelines, test minimum requirements, and ref/source hygiene. Used by dbt-reviewer and naming-validator.
---

# dbt Conventions

## Model Naming Prefixes

Every dbt model name MUST begin with one of these prefixes:

| Prefix | Layer | Purpose |
|---|---|---|
| `stg_` | Staging | One-to-one with source system tables. Minimal transformations only: rename columns, cast types, add surrogate keys. Never join. |
| `int_` | Intermediate | Business logic joins and transformations. Not exposed to end consumers directly. |
| `mart_` | Mart | Wide, denormalized models for analytics consumers. Exposed via BI tools. |
| `rpt_` | Report | One-off or stakeholder-specific report models. Not part of the main mart. |
| `fct_` | Fact (mart sublayer) | Fact tables within a mart. Acceptable alternative to `mart_` for fact tables. |
| `dim_` | Dimension (mart sublayer) | Dimension tables within a mart. Acceptable alternative to `mart_` for dimensions. |

**Severity:** Any model without one of these prefixes is a **High** finding — it is invisible to cross-project navigation and governance tooling.

## Model Structure Rules

1. **CTEs only.** Every model must use CTEs for intermediate logic. No subqueries in the `FROM` clause.
2. **Final SELECT is clean.** The last CTE or final SELECT must not contain transformations — it selects from the penultimate CTE.
3. **No DDL statements.** `CREATE`, `DROP`, `ALTER`, `TRUNCATE` are forbidden inside model `.sql` files. These belong in macros or operations.
4. **No hardcoded references.** `database.schema.table` literals are **Critical** — they break environment promotion. Always use `{{ ref('model_name') }}` or `{{ source('source_name', 'table_name') }}`.

## Test Minimum Requirements

Every model MUST have, at minimum, the following tests on its grain key column(s):

| Test | Requirement |
|---|---|
| `not_null` | Required on every grain key column |
| `unique` | Required on every grain key column |

**Missing these tests is a High finding.** No model is production-ready without grain key tests.

Additional recommended tests (Medium finding if absent):
- `accepted_values` on every categorical/enum column
- `relationships` on every foreign key column

## Documentation Requirements

Every model MUST have a `schema.yml` entry with:
- Model-level `description` (non-empty, non-generic)
- Column-level `description` for every column in the model's SELECT

**Missing `schema.yml` entry is a High finding.**
**Columns present in the model but absent from `schema.yml` is a Medium finding.**

## Materialization Guidelines

| Pattern | Guideline | Severity if violated |
|---|---|---|
| `ephemeral` used when model is referenced by 3+ downstream models | Use `table` or `view` instead | Medium |
| `table` (full refresh) on a model ingesting 100M+ rows | Use `incremental` instead | Medium |
| `incremental` without `unique_key` | Will duplicate on re-run | High |
| `incremental` without `is_incremental()` guard | Full refresh on every run | Medium |

## Source Naming

Source names in `sources.yml` MUST match the actual source system name (e.g. Salesforce source → `salesforce`, not `crm` or `sf`).

Source table names MUST match the actual table name in the source system exactly.

**Deviation is a Medium finding** — source names are the contract with the upstream system.

## File Naming

Model file name MUST match the model name exactly (e.g. `stg_orders` → `stg_orders.sql`). Case-sensitive on case-sensitive filesystems.

**Mismatch is a Medium finding.**
