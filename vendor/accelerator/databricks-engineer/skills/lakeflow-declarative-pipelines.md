---
name: lakeflow-declarative-pipelines
description: |
  Import before generating any Lakeflow Declarative Pipeline code. Provides the single
  authoritative idiom source for pyspark.pipelines (dp module) — decorators, expectations,
  CDC, SQL syntax, smoke-test convention, and deprecated dlt patterns.
  Triggers on: pipeline generation, LDP code review, CDC flow authoring, smoke-test scaffolding.
---

# Lakeflow Declarative Pipelines — Authoritative Idiom Reference

## CRITICAL: Minimum Runtime

`pyspark.pipelines` requires **Serverless** or **Pro/Advanced** edition Databricks Runtime for Lakeflow Declarative Pipelines. Classic compute is not supported.

## Module Import

**CORRECT — always use this:**
```python
from pyspark import pipelines as dp
```

**WRONG — never use this (deprecated module):**
```python
import dlt  # DEPRECATED — this module no longer exists
```

## Decorator Reference Table

| Decorator | Purpose | Notes |
|---|---|---|
| `@dp.table` | Streaming table — incremental, append/merge | Default for CDC targets and streaming sources |
| `@dp.materialized_view` | Materialized view — batch refresh on full dataset | Use for aggregations, joins, reporting layers |
| `@dp.temporary_view` | Temporary view — replaced `@dlt.view` | Not persisted; used for intermediate transformations within a pipeline |
| `@dp.append_flow` | Append-only flow into an existing streaming table | Use when combining multiple sources into one target |
| `@dp.update_flow` | Update flow for SCD2 or complex merge semantics | Use with `dp.create_auto_cdc_flow` targets |

## Decorator Usage Examples

```python
from pyspark import pipelines as dp
from pyspark.sql.functions import col, expr, current_timestamp

@dp.table(
    name="bronze_bkpf",
    comment="Streaming ingest of SAP ECC BKPF change events",
    table_properties={"quality": "bronze"}
)
@dp.expect_or_drop("valid_bukrs", "bukrs IS NOT NULL")
@dp.expect("valid_blart", "blart IS NOT NULL")
def bronze_bkpf():
    return (
        spark.readStream
            .format("delta")
            .table("landing.sys01_ecc.bkpf_cdf")
    )


@dp.materialized_view(
    name="gold_gl_summary",
    comment="GL balance summary aggregated by company and period"
)
@dp.expect_all_or_fail({
    "valid_company": "company_code IS NOT NULL",
    "valid_period": "fiscal_period BETWEEN 1 AND 16"
})
def gold_gl_summary():
    return spark.sql("""
        SELECT company_code, fiscal_year, fiscal_period,
               SUM(amount_lc) AS total_amount_lc
        FROM silver.finance.gl_line
        GROUP BY company_code, fiscal_year, fiscal_period
    """)


@dp.temporary_view
def stg_open_items():
    return spark.sql("SELECT * FROM bronze.sys01_ecc.bseg WHERE augdt IS NULL")
```

## Expectations Syntax — Full Reference

### Python decorator form

```python
# Warn only — row survives, violation recorded in event log
@dp.expect("non_negative_price", "price >= 0")

# Drop row on violation
@dp.expect_or_drop("valid_date", "date <= current_date()")

# Fail pipeline on any violation
@dp.expect_or_fail("valid_id", "id IS NOT NULL")

# Multiple expectations — warn
@dp.expect_all({
    "valid_company": "company_code IS NOT NULL",
    "valid_amount": "amount_lc IS NOT NULL"
})

# Multiple expectations — drop row on any violation
@dp.expect_all_or_drop({
    "valid_company": "company_code IS NOT NULL",
    "valid_amount": "amount_lc IS NOT NULL"
})

# Multiple expectations — fail pipeline on any violation
@dp.expect_all_or_fail({
    "valid_id": "id IS NOT NULL",
    "valid_date": "event_date IS NOT NULL"
})
```

### SQL CONSTRAINT form

```sql
CREATE OR REFRESH STREAMING TABLE orders (
  CONSTRAINT valid_price EXPECT (price >= 0),
  CONSTRAINT valid_id    EXPECT (id IS NOT NULL) ON VIOLATION DROP ROW,
  CONSTRAINT valid_date  EXPECT (order_date IS NOT NULL) ON VIOLATION FAIL UPDATE
)
AS SELECT * FROM STREAM(landing.sys01_ecc.orders_raw);
```

## AUTO CDC — Python API

### `dp.create_auto_cdc_flow()` — Full Signature

```python
dp.create_auto_cdc_flow(
    target             = "target_table",        # streaming table name (must be declared with @dp.table)
    source             = "source_table",        # source streaming table or view
    keys               = ["key_col"],           # primary key column(s) — list of strings
    sequence_by        = col("seq_col"),        # ordering expression — determines which row wins
    stored_as_scd_type = 1,                     # 1 (default), "2", or "bitemporal"
    apply_as_deletes   = expr("op = 'DELETE'"), # optional — expression identifying delete rows
    apply_as_truncates = expr("op = 'TRUNCATE'"), # optional — expression identifying truncate rows
    except_column_list = ["op", "seq_col"],     # columns to exclude from the target
    ignore_null_updates= False,                 # optional — ignore rows where all non-key cols are NULL
    track_history_column_list = None,           # optional — SCD2: columns that trigger history row
)
```

### SCD Type 1 Example

```python
from pyspark import pipelines as dp
from pyspark.sql.functions import col, expr

@dp.table(name="silver_customers")
def silver_customers():
    pass  # target declared; create_auto_cdc_flow populates it

dp.create_auto_cdc_flow(
    target             = "silver_customers",
    source             = "bronze_customers_cdf",
    keys               = ["customer_id"],
    sequence_by        = col("seq_num"),
    stored_as_scd_type = 1,
    apply_as_deletes   = expr("operation = 'DELETE'"),
    except_column_list = ["operation", "seq_num"],
)
```

### SCD Type 2 Example

```python
dp.create_auto_cdc_flow(
    target                    = "silver_customers_history",
    source                    = "bronze_customers_cdf",
    keys                      = ["customer_id"],
    sequence_by               = col("seq_num"),
    stored_as_scd_type        = "2",
    track_history_column_list = ["name", "address", "email"],
    apply_as_deletes          = expr("operation = 'DELETE'"),
    except_column_list        = ["operation", "seq_num"],
)
```

### Bitemporal Example

```python
dp.create_auto_cdc_flow(
    target             = "silver_customers_bitemporal",
    source             = "bronze_customers_cdf",
    keys               = ["customer_id"],
    sequence_by        = col("valid_from"),
    stored_as_scd_type = "bitemporal",
    except_column_list = ["operation"],
)
```

### Snapshot CDC

```python
dp.create_auto_cdc_from_snapshot_flow(
    target             = "silver_products_snapshot",
    source             = "bronze_products_snap",
    keys               = ["product_id"],
    stored_as_scd_type = 2,
)
```

## AUTO CDC — SQL Syntax

```sql
-- SCD Type 1
CREATE OR REFRESH STREAMING TABLE users;

CREATE FLOW apply_users_cdc AS
AUTO CDC INTO users
FROM STREAM(users_cdf)
KEYS (user_id)
SEQUENCE BY seq_num
STORED AS SCD TYPE 1
APPLY AS DELETE WHEN operation = 'DELETE'
EXCEPT COLUMNS (operation, seq_num);

-- SCD Type 2
CREATE OR REFRESH STREAMING TABLE users_history;

CREATE FLOW apply_users_history AS
AUTO CDC INTO users_history
FROM STREAM(users_cdf)
KEYS (user_id)
SEQUENCE BY seq_num
STORED AS SCD TYPE 2
TRACK HISTORY ON (name, email, address)
APPLY AS DELETE WHEN operation = 'DELETE'
EXCEPT COLUMNS (operation, seq_num);
```

## Streaming Tables vs. Materialized Views

| Feature | Streaming Table (`@dp.table`) | Materialized View (`@dp.materialized_view`) |
|---|---|---|
| Processing model | Incremental — processes new records only | Full refresh — recomputes entire result |
| Source requirement | Streaming source (STREAM(), Auto Loader, CDC) | Any query (batch or streaming) |
| Use case | Bronze ingest, silver CDC targets | Aggregations, joins, gold reporting |
| Expectations | Supported | Supported |
| AUTO CDC target | Yes — required | No |
| Retains history | Yes (SCD2 via create_auto_cdc_flow) | No |

**Rule**: Use `@dp.table` for anything that receives CDC events or streams from landing. Use `@dp.materialized_view` for aggregated/joined results in silver and gold.

## Smoke-Test Bundle Targets Convention

**Every pipeline must ship two smoke-test bundle targets:**

- `smoke-ecc`: synthetic mini-dataset shaped like SAP ECC source tables (BKPF/BSEG structure: `mandt`, `bukrs`, `belnr`, `gjahr`, `blart`, `bldat`, `cpudt`, `xblnr`, `waers`, `wrbtr`)
- `smoke-s4`: synthetic mini-dataset shaped like SAP S/4HANA source tables (ACDOCA structure: `mandt`, `rldnr`, `rbukrs`, `gjahr`, `belnr`, `buzei`, `augdt`, `augbl`, `waers`, `hsl`)

Smoke targets use static Delta tables with 10–50 rows. They run in a dedicated workspace or use Unity Catalog's `smoke` catalog, and they validate the pipeline compiles, runs, and produces non-empty output.

**databricks.yml smoke target example:**

```yaml
targets:
  smoke-ecc:
    variables:
      env: smoke-ecc
      source_catalog: smoke_ecc
      source_schema: sys01_ecc
  smoke-s4:
    variables:
      env: smoke-s4
      source_catalog: smoke_s4
      source_schema: sys01_s4
```

## DEPRECATED PATTERNS — dlt → dp Migration Table

| Deprecated (dlt) | Correct (dp) |
|---|---|
| `import dlt` | `from pyspark import pipelines as dp` |
| `@dlt.table` | `@dp.table` |
| `@dlt.view` | `@dp.temporary_view` |
| `@dlt.expect(...)` | `@dp.expect(...)` |
| `@dlt.expect_or_drop(...)` | `@dp.expect_or_drop(...)` |
| `@dlt.expect_or_fail(...)` | `@dp.expect_or_fail(...)` |
| `@dlt.expect_all(...)` | `@dp.expect_all(...)` |
| `@dlt.expect_all_or_drop(...)` | `@dp.expect_all_or_drop(...)` |
| `@dlt.expect_all_or_fail(...)` | `@dp.expect_all_or_fail(...)` |
| `dlt.apply_changes(...)` | `dp.create_auto_cdc_flow(...)` |
| `dlt.apply_changes_from_snapshot(...)` | `dp.create_auto_cdc_from_snapshot_flow(...)` |
| `dlt.read(...)` | `spark.readStream.table(...)` or `spark.read.table(...)` |
| `dlt.read_stream(...)` | `spark.readStream.table(...)` |

## Hard Gates

**DO NOT generate any code using `import dlt` or `@dlt.*` — the dlt module is deprecated and will cause runtime errors.**
**DO NOT use `@dp.materialized_view` as the target of `dp.create_auto_cdc_flow()` — the target must be declared with `@dp.table`.**
**DO NOT generate a pipeline without smoke-ecc and smoke-s4 bundle targets.**
**STOP and surface an error if the user's spec or context indicates Classic compute — pyspark.pipelines requires Serverless or Pro/Advanced.**
