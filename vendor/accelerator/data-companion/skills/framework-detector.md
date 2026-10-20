---
name: framework-detector
description: |
  Detect pipeline/transformation framework from project files. Returns {framework, version_hint} for downstream agents. Used by pipeline-auditor, dbt-reviewer, dq-definer, lineage-reader. Call before any framework-specific processing.
---

# Framework Detector

## Purpose

Determine the data framework in use before any agent applies framework-specific rules. Never assume a framework. Always detect from project files.

## Detection Algorithm

### Step 1: Check for well-known marker files

Scan the project root and immediate subdirectories for these marker files. Stop at first match (most specific wins).

| Marker file / pattern | Framework |
|---|---|
| `dbt_project.yml` present | dbt |
| `packages.yml` with `elementary-data` dependency | dbt + Elementary |
| `great_expectations/` directory present | Great Expectations |
| `soda/` directory present OR `checks.yml` with `soda` header | Soda |
| `airflow_settings.yaml` OR `dags/` directory OR file with `from airflow` import | Airflow |
| File with `from prefect` import OR `@flow` decorator | Prefect |
| File with `from pyspark` import OR `SparkSession.builder` | PySpark |
| File with `.scala` extension + `import org.apache.spark` | Spark (Scala) |
| None of the above, `.py` files with ETL-shaped functions (extract/load/transform naming) | Plain Python ETL |

### Step 2: Version Hint

After identifying the framework, look for a version hint:

- dbt: read `dbt_project.yml` → `require-dbt-version` field
- Airflow: read `requirements.txt` or `pyproject.toml` for `apache-airflow==`
- Prefect: read `requirements.txt` or `pyproject.toml` for `prefect==`
- PySpark: read `requirements.txt` for `pyspark==`
- Great Expectations: read `great_expectations/great_expectations.yml` for version

### Step 3: Ambiguity

If multiple frameworks are detected (e.g. dbt AND Airflow), the project uses both. Return both.

If no framework markers are found after scanning:
- If the input is a single file, infer from file content (Step 1 file-level heuristics)
- If still ambiguous, ask the user: "I could not detect a framework from project files. Are you using dbt, Airflow, Prefect, Spark, or plain Python ETL?" — one question, then wait.

### Step 4: Return

```
{
  "framework": ["dbt"] | ["airflow"] | ["prefect"] | ["pyspark"] | ["spark-scala"] | ["plain-python-etl"] | ["great-expectations"] | ["soda"] | ["elementary"] | ["dbt", "airflow"],
  "version_hint": "1.7.0" | null,
  "confidence": "certain" | "inferred" | "ambiguous"
}
```

## DO NOT Rules

- DO NOT apply dbt-specific rules before confirming dbt is in use
- DO NOT ask for framework if `dbt_project.yml` is present — that is certain
- DO NOT return ambiguous without first scanning the project root
