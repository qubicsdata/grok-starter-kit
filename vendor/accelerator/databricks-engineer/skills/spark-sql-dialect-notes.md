---
name: spark-sql-dialect-notes
description: |
  Import before writing or reviewing Spark SQL on Databricks, especially for SAP migration
  workloads. Provides ANSI mode notes, dialect differences, SAP migration pitfalls, Delta-specific
  SQL, and streaming SQL syntax. Triggers on: Spark SQL authoring, SQL dialect review,
  SAP-to-Databricks migration SQL, Delta SQL operations.
---

# Spark SQL Dialect Notes

## ANSI Mode

**ANSI SQL compliance is enabled by default since DBR 8.0+.** All Databricks clusters and SQL warehouses run with `spark.sql.ansi.enabled = true` by default.

**Implications:**
- Integer overflow raises an error (not silent wrap-around).
- Division by zero raises an error (not NULL).
- String-to-numeric cast failure raises an error (not NULL).
- Strict NULL handling: `NULL = NULL` is `NULL`, not `TRUE`.

To temporarily disable ANSI for a session (debugging only, not production):
```sql
SET spark.sql.ansi.enabled = false;
```

To check current mode:
```sql
SELECT current_setting('spark.sql.ansi.enabled');
-- OR
SHOW CONF spark.sql.ansi.enabled;
```

## Key Dialect Differences from Standard SQL

### NULL Handling

```sql
-- Standard SQL: NULL comparisons
NULL = NULL    -- result: NULL (not TRUE)
NULL != NULL   -- result: NULL (not FALSE)
NULL IS NULL   -- result: TRUE (use this)
NULL IS NOT NULL  -- result: FALSE

-- Safe equality (treats NULL as equal)
NULL <=> NULL  -- result: TRUE (Spark-specific operator)
col1 <=> col2  -- TRUE if both NULL or both equal
```

### BOOLEAN Casting

```sql
-- Spark accepts:
CAST('true' AS BOOLEAN)   -- TRUE
CAST('false' AS BOOLEAN)  -- FALSE
CAST('1' AS BOOLEAN)      -- TRUE
CAST('0' AS BOOLEAN)      -- FALSE
CAST('yes' AS BOOLEAN)    -- error in ANSI mode
```

### Date and Timestamp Literals

```sql
-- Preferred — explicit type
DATE '2025-01-31'
TIMESTAMP '2025-01-31T00:00:00.000Z'

-- Also accepted
'2025-01-31'::DATE
'2025-01-31T00:00:00Z'::TIMESTAMP

-- Avoid: implicit string-to-date coercion (ANSI mode may reject)
WHERE order_date = '2025-01-31'  -- prefer explicit CAST or DATE literal
```

### String Functions

```sql
-- Trim (ANSI standard form)
TRIM(LEADING ' ' FROM col)   -- left trim
TRIM(TRAILING ' ' FROM col)  -- right trim
TRIM(BOTH ' ' FROM col)      -- both
LTRIM(col)                    -- Spark shorthand
RTRIM(col)                    -- Spark shorthand

-- String concatenation
CONCAT(a, b, c)               -- preferred
a || b                        -- also supported (ANSI)
```

### LATERAL VIEW / EXPLODE

```sql
SELECT id, tag
FROM events
LATERAL VIEW EXPLODE(tags) t AS tag;

-- Modern form (preferred)
SELECT id, tag
FROM events, LATERAL EXPLODE(tags) AS t(tag);
```

## Common SAP Migration Pitfalls

### CHAR Padding

SAP ABAP stores `CHAR` fields right-padded with spaces to their declared length. Databricks `STRING` does not pad.

**Problem:**
```sql
-- SAP delivers: bukrs = 'US  ' (4-char CHAR field, padded)
-- Databricks join fails:
JOIN dim_company ON bkpf.bukrs = dim_company.company_code
-- If dim_company.company_code = 'US' (no padding), the join produces 0 rows
```

**Fix — trim on ingest at bronze:**
```sql
TRIM(bukrs) AS bukrs
```

Or apply globally in the bronze CDC transformation:
```python
from pyspark.sql.functions import trim, col

char_columns = ["bukrs", "blart", "koart", "waers"]
for c in char_columns:
    df = df.withColumn(c, trim(col(c)))
```

### Implicit Numeric Coercions

SAP ABAP `CURR` and `QUAN` fields are often stored as `DECIMAL(n, m)` or as strings with internal decimal notation (comma as decimal separator in some locales).

**Problem:**
```sql
-- Source delivers: wrbtr = '1234,56' (German locale, comma decimal)
-- Direct CAST fails in ANSI mode:
CAST(wrbtr AS DECIMAL(15,2))  -- error: '1234,56' cannot be cast
```

**Fix:**
```python
from pyspark.sql.functions import regexp_replace, col

df = df.withColumn(
    "wrbtr",
    regexp_replace(col("wrbtr"), ",", ".").cast("decimal(15,2)")
)
```

### NULL vs. Empty String

SAP often uses empty string `''` where SQL semantics expect `NULL`.

**Problem:**
```sql
-- SAP delivers: augbl = '' (not NULL) for open items
-- Standard IS NULL check misses them:
WHERE augbl IS NULL   -- misses '' rows
```

**Fix — normalize on ingest:**
```sql
NULLIF(augbl, '') AS augbl
```

### Date Fields

SAP stores dates as `DATS` (8-char string `YYYYMMDD`) and times as `TIMS` (6-char string `HHMMSS`).

```python
from pyspark.sql.functions import to_date, col, when, lit

df = df.withColumn(
    "bldat",
    when(col("bldat") == "00000000", lit(None))
    .otherwise(to_date(col("bldat"), "yyyyMMdd"))
)
```

Zero-date `00000000` is SAP's "not set" — always convert to NULL.

### Numeric Field Lengths

SAP `INT4` = 32-bit integer (max 2,147,483,647). Map to Spark `INT`.
SAP `INT8` = 64-bit integer. Map to Spark `BIGINT`.
SAP `FLTP` = double-precision float. Map to Spark `DOUBLE` (be aware of precision loss for financial amounts — use `DECIMAL` instead).

**Never use `FLOAT` or `DOUBLE` for financial amounts** — use `DECIMAL(15, 2)` or `DECIMAL(23, 2)` for SAP CURR fields.

## Delta-Specific SQL

```sql
-- Optimize table (trigger liquid clustering compaction)
OPTIMIZE silver.finance.gl_line;

-- Vacuum (remove old file versions — default retention 7 days)
VACUUM silver.finance.gl_line;
VACUUM silver.finance.gl_line RETAIN 168 HOURS;  -- 7 days explicit

-- Describe history (time travel audit trail)
DESCRIBE HISTORY silver.finance.gl_line;
DESCRIBE HISTORY silver.finance.gl_line LIMIT 10;

-- Time travel query (by version)
SELECT * FROM silver.finance.gl_line VERSION AS OF 42;

-- Time travel query (by timestamp)
SELECT * FROM silver.finance.gl_line TIMESTAMP AS OF '2025-06-01T00:00:00Z';

-- Restore table to previous version
RESTORE TABLE silver.finance.gl_line TO VERSION AS OF 42;
RESTORE TABLE silver.finance.gl_line TO TIMESTAMP AS OF '2025-06-01T00:00:00Z';

-- Table properties
ALTER TABLE silver.finance.gl_line
  SET TBLPROPERTIES (
    'delta.autoOptimize.optimizeWrite' = 'true',
    'delta.autoOptimize.autoCompact' = 'true'
  );

-- Check table details
DESCRIBE DETAIL silver.finance.gl_line;
```

## Streaming SQL

```sql
-- STREAM() function: read a Delta table as a streaming source
SELECT * FROM STREAM(landing.sys01_ecc.bkpf);

-- Create streaming table (in Lakeflow Declarative Pipeline)
CREATE OR REFRESH STREAMING TABLE bronze_bkpf
AS SELECT * FROM STREAM(landing.sys01_ecc.bkpf);

-- Streaming with expectations
CREATE OR REFRESH STREAMING TABLE bronze_bkpf (
  CONSTRAINT valid_bukrs EXPECT (bukrs IS NOT NULL),
  CONSTRAINT valid_blart EXPECT (blart IS NOT NULL) ON VIOLATION DROP ROW
)
AS SELECT * FROM STREAM(landing.sys01_ecc.bkpf);
```

## Hard Gates

**DO NOT disable ANSI mode in production SQL — fix the query instead.**
**DO NOT use FLOAT or DOUBLE for financial amount columns — use DECIMAL(15,2) or DECIMAL(23,2).**
**DO NOT compare SAP date fields to date literals without first converting DATS string to DATE type.**
**DO NOT assume SAP empty strings are NULL — normalize with NULLIF on ingest.**
**STOP and warn if SAP CHAR fields are joined without trimming — silent join failures are a common migration bug.**
