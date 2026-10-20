---
name: pyspark-optimization-craft
description: |
  Import before authoring or reviewing PySpark jobs. Provides liquid clustering guidance,
  AQE configuration, skew handling, join strategies, serverless job config, and the rule
  for triggering the deep optimization pass (explicit user request only).
  Triggers on: PySpark job authoring, optimization review request, skew or performance issue.
contract_version: 1.0.0
---

# PySpark Optimization Craft

Generative expertise for PySpark data layout, execution, and join strategy on Databricks. Consumed
by pyspark-engineer when authoring or reviewing a job. Every recommendation leads with a default and
carries the rule that produced it.

## Section 1 — Decision Domains

| ID prefix | Decision domain | The decision being made |
|-----------|-----------------|-------------------------|
| `PYSPARK-LAYOUT` | Data layout | Liquid clustering vs partitioning vs Z-ORDER, and the OPTIMIZE cadence |
| `PYSPARK-AQE` | Adaptive execution posture | Whether AQE stays on, and which knobs are tuned |
| `PYSPARK-SKEW` | Skew mitigation | Which rung of the skew ladder a job uses |
| `PYSPARK-JOIN` | Join strategy | Broadcast, sort-merge, shuffle-hash, or cartesian |
| `PYSPARK-COMPUTE` | Compute configuration | What the job declares about cluster shape |
| `PYSPARK-DEEP` | Deep optimization pass | When an expensive model-tier review is warranted |

## Section 2 — Constraint Inputs

| Brief dimension | Drives | How |
|-----------------|--------|-----|
| Cluster-key cardinality | `PYSPARK-LAYOUT` | Low-to-moderate cardinality favors liquid clustering; extreme cardinality forces a date partition |
| Query filter pattern (which columns, which date windows) | `PYSPARK-LAYOUT` | Filtering on one to four columns points to clustering; access by date window only allows partitioning |
| Table age (new vs existing partitioned) | `PYSPARK-LAYOUT` | Existing partition skew is the trigger to migrate to clustering |
| Measured partition skew | `PYSPARK-SKEW` | Determines whether AQE suffices or salting is justified |
| Relative table sizes | `PYSPARK-JOIN` | Build-side size against the broadcast threshold selects the strategy |
| Runtime environment (serverless vs classic) | `PYSPARK-COMPUTE` | Serverless forbids explicit cluster configuration |
| Explicit user request | `PYSPARK-DEEP` | The only permitted trigger for the deep pass |
| Budget posture (`budget.json`) | `PYSPARK-DEEP` | Cost gate verdict decides whether the deep pass proceeds |

## Section 3 — Opinionated Defaults

### Liquid Clustering

### When to Use Liquid Clustering vs. Partitioning

| Scenario | Recommendation |
|---|---|
| New table, cardinality < 100K distinct values per cluster key | Liquid clustering |
| New table, query filters on 1–4 columns, no predefined cardinality guarantee | Liquid clustering |
| Existing partitioned table, partition skew detected | Migrate to liquid clustering |
| Table ingested via CDC (bronze/silver) | Liquid clustering on source keys |
| Time-series table queried by date range only | Consider partitioning by date + liquid clustering by secondary key |
| Very high-cardinality key (e.g., UUID) as sole filter | Partition by date, cluster by UUID |

**Rule**: Default to liquid clustering for new tables in Databricks. Use Z-ORDER or partitioning only when there is a specific, measured reason (e.g., partition elimination for time-series at petabyte scale).

### Syntax

```sql
-- Create with clustering
CREATE TABLE bronze.sys01_ecc.bkpf
CLUSTER BY (bukrs, gjahr)
AS SELECT * FROM landing.sys01_ecc.bkpf;

-- Alter existing table
ALTER TABLE silver.finance.gl_line
CLUSTER BY (company_code, fiscal_year, fiscal_period);

-- Trigger clustering compaction
OPTIMIZE silver.finance.gl_line;

-- OPTIMIZE with WHERE predicate (partial compaction)
OPTIMIZE silver.finance.gl_line
WHERE fiscal_year = 2025;
```

```python
# PySpark: create clustered table
df.write \
  .format("delta") \
  .option("clusterByColumns", "company_code,fiscal_year") \
  .saveAsTable("silver.finance.gl_line")
```

### OPTIMIZE Cadence

- Run `OPTIMIZE` after bulk loads or large CDC batches.
- Automate via a Databricks job on a schedule (e.g., daily off-peak).
- Do not run `OPTIMIZE` inside a pipeline definition — run it as a separate maintenance job.

### Adaptive Query Execution (AQE)

AQE is **enabled by default** in Databricks Runtime 7.3 LTS and above. Do not disable it in production.

```python
# AQE is on by default — do not set this in production
# spark.conf.set("spark.sql.adaptive.enabled", "true")  # default: true

# Disable ONLY for debugging (AQE can obscure plan issues)
spark.conf.set("spark.sql.adaptive.enabled", "false")  # debug only
```

**AQE features active by default:**
- Coalescing post-shuffle partitions (reduces small file / small task overhead)
- Converting sort-merge join to broadcast join when build side fits in memory
- Optimizing skew joins automatically

### Skew Handling

### Adaptive Skew Join (AQE)

AQE handles most skew automatically. Tune with:

```python
# Increase skew factor threshold (default: 5.0 — skewed if >5x median partition size)
spark.conf.set("spark.sql.adaptive.skewJoin.skewedPartitionFactor", "5.0")

# Minimum skewed partition size in bytes (default: 256MB)
spark.conf.set("spark.sql.adaptive.skewJoin.skewedPartitionThresholdInBytes", "268435456")
```

### Broadcast Join (explicit)

```python
from pyspark.sql.functions import broadcast

result = large_df.join(broadcast(small_df), "key_col")
```

**Use broadcast when:**
- The smaller table fits in memory per executor (default threshold: 10MB, configurable up to ~2GB)
- The join key has high cardinality on the large side

### Broadcast Threshold

```python
# Increase broadcast threshold (in bytes) — default 10MB
spark.conf.set("spark.sql.autoBroadcastJoinThreshold", "104857600")  # 100MB

# Disable auto-broadcast
spark.conf.set("spark.sql.autoBroadcastJoinThreshold", "-1")
```

### Salting for Extreme Skew

For joins where AQE skew handling is insufficient:

```python
from pyspark.sql.functions import col, rand, floor, concat_ws, lit, explode, array

SALT_FACTOR = 20

# Salt the large (skewed) side
large_salted = large_df.withColumn(
    "salt_key",
    concat_ws("_", col("skewed_key"), floor(rand() * SALT_FACTOR).cast("string"))
)

# Replicate the small side
small_replicated = small_df.withColumn(
    "salt_range",
    array([lit(i) for i in range(SALT_FACTOR)])
).withColumn("salt_n", explode(col("salt_range"))) \
 .withColumn("salt_key", concat_ws("_", col("key"), col("salt_n").cast("string")))

result = large_salted.join(small_replicated, "salt_key")
```

Use salting only when AQE skew join still produces stragglers — it adds complexity and must be documented.

### Join Strategy Reference

| Strategy | Hint API | When to Use |
|---|---|---|
| Broadcast | `broadcast(df)` or `hint("broadcast")` | Small table (< broadcast threshold) + any size |
| Sort-merge | `hint("merge")` | Both tables large, equi-join, AQE default for large joins |
| Shuffle-hash | `hint("shuffle_hash")` | One side fits in memory but exceeds broadcast threshold |
| Cartesian | `hint("cartesian")` | Cross join (rare — explicit only) |

```python
# Hint API
df1.join(df2.hint("broadcast"), "key")
df1.hint("merge").join(df2, "key")
df1.join(df2.hint("shuffle_hash"), "key")
```

### Serverless Job Configuration

Serverless jobs on Databricks do not require explicit cluster configuration. Omit `cluster_type`, `node_type_id`, and `num_workers`:

```yaml
# databricks.yml — serverless job task
jobs:
  my_pyspark_job:
    tasks:
      - task_key: run_job
        python_wheel_task:
          package_name: my_package
          entry_point: main
        # No cluster config — serverless by default
        environment_key: default
    environments:
      - environment_key: default
        spec:
          client: "1"
          dependencies:
            - pyspark>=3.5
```

**Never hardcode:**
- `node_type_id`
- `num_workers`
- `spark_version` (use `auto`)
- Databricks host URLs

### Opus Optimization Pass

**Trigger: explicit user request only.** Examples of explicit requests:
- "optimize this job"
- "deep review the PySpark"
- "run the Opus pass"
- "performance review"

Do NOT trigger the Opus pass:
- Automatically on any job authoring
- When the user asks to "write a job" or "generate a pipeline"
- Based on detected complexity or estimated cost

**Protocol when triggered:**
1. Run baseline-enforcer Gate 2 (cost gate) with target tier `opus`.
2. If `PROCEED`: dispatch an `opus`-tier sub-agent with the job code and optimization context.
3. If `BUDGET_EXCEEDED`: surface the budget message. Stop. Do not call Opus.
4. If `budget.json` absent: proceed as PROCEED with visible warning.

## Section 4 — Derivation Rules

- `PYSPARK-D-1`: When a new Databricks table is created, choose liquid clustering because it adapts to observed query patterns without committing to a partition layout that later skews.
- `PYSPARK-D-2`: When an existing partitioned table shows partition skew, choose migration to liquid clustering because skewed partitions cannot be rebalanced in place.
- `PYSPARK-D-3`: When queries filter a time-series table by date range only, choose date partitioning plus a clustered secondary key because partition elimination is the dominant win at that access shape.
- `PYSPARK-D-4`: When the sole filter key is very high cardinality such as a UUID, choose partitioning by date and clustering by the key because a clustered UUID alone yields no useful file skipping.
- `PYSPARK-D-5`: When Z-ORDER or partitioning is proposed for a new table, choose it only with a measured justification because clustering is the cheaper default and the burden of proof sits with the exception.
- `PYSPARK-D-6`: When a bulk load or large CDC batch completes, choose to run OPTIMIZE as a scheduled maintenance job because compaction inside a pipeline definition couples maintenance to ingestion.
- `PYSPARK-D-7`: When the job runs in production, choose to leave AQE enabled because coalescing, dynamic broadcast conversion, and skew-join handling are the baseline the rest of these defaults assume.
- `PYSPARK-D-8`: When AQE is disabled, choose to restrict it to debugging and carry a comment explaining why, because a silently disabled AQE looks identical to a badly tuned job.
- `PYSPARK-D-9`: When skew appears, choose AQE adaptive skew join first because it costs nothing to try and resolves the common case.
- `PYSPARK-D-10`: When AQE skew handling still leaves stragglers, choose salting and document it inline because salting is real complexity that a later reader must be able to justify.
- `PYSPARK-D-11`: When one join side fits the broadcast threshold, choose a broadcast join because it removes the shuffle entirely.
- `PYSPARK-D-12`: When one side exceeds the broadcast threshold but still fits in memory, choose shuffle-hash because sort-merge pays an unnecessary sort.
- `PYSPARK-D-13`: When the job targets serverless, choose to omit `node_type_id`, `num_workers`, and pinned `spark_version` because declaring them contradicts the runtime and pins a stale shape.
- `PYSPARK-D-14`: When the user has not explicitly asked for optimization, choose not to run the deep pass because complexity heuristics are not consent to spend.
- `PYSPARK-D-15`: When the deep pass is explicitly requested, choose to clear the cost gate at the `opus` tier before dispatching because an ungated escalation defeats the budget control.

## Section 5 — Recommendation Output Contract

Every optimization recommendation MUST surface: the chosen value, the `PYSPARK-D-*` rule ID(s) that
produced it, at least one named alternative, and an override hook.

A job review MUST state, per domain in scope: the layout choice and its OPTIMIZE cadence, the AQE
posture, the skew rung reached and why, the join strategy per join, and the compute declaration.
Where a measurement drove the choice, name the measurement; where none exists, say the default
applies rather than implying evidence that was never collected.

**Override hook.** A user may override layout choice, broadcast threshold, skew factor thresholds,
join hints, and OPTIMIZE cadence by naming them. Five defaults are not overridable, because each
converts a visible cost into a hidden one: AQE stays enabled in production outside debugging
(`PYSPARK-D-7`, `PYSPARK-D-8`); salting is always documented (`PYSPARK-D-10`); cluster configs,
node types, and host URLs are never hardcoded (`PYSPARK-D-13`); the deep pass never auto-triggers
(`PYSPARK-D-14`); OPTIMIZE never runs inside a pipeline definition (`PYSPARK-D-6`). When a request
would violate one, refuse it, name the rule, and present a compliant alternative.

## Section 6 — Enforcement Handoff

pyspark-optimization-craft output is validated against medallion-architecture-spec (layer placement
and table layout must match the medallion contract), lakeflow-declarative-pipelines (maintenance
work must sit outside pipeline definitions), unity-catalog-conventions (table naming and catalog
placement), and spark-sql-dialect-notes (generated SQL must stay in the supported dialect). Any
layout, join, or execution choice that deviates from its cited `PYSPARK-D-*` rule without an
explicit user override is a finding.
