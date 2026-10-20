# data-companion

A Claude Code plugin for data engineers working on existing data systems. Eight independently-invocable agents covering the full data engineering loop.

## Agents

| Agent | Model | Purpose |
|---|---|---|
| `schema-reviewer` | claude-sonnet-4-6 | Forensic schema review across SQL DDL, Avro, Protobuf, JSON Schema, dbt YAML |
| `pipeline-auditor` | claude-sonnet-4-6 | Pipeline audit for idempotency, error handling, freshness, resource contention, observability |
| `dbt-reviewer` | claude-sonnet-4-6 | dbt model structure, test coverage, documentation, ref hygiene, materialization |
| `dq-definer` | claude-sonnet-4-6 | Data quality check stub generation (Great Expectations, dbt-tests, Soda, Elementary) |
| `contract-generator` | claude-sonnet-4-6 | DCS v2.3.0 YAML + Markdown data contract generation |
| `lineage-reader` | claude-sonnet-4-6 | Upstream/downstream lineage from dbt manifest, Airflow DAGs, Prefect flows |
| `naming-validator` | claude-haiku-4-5-20251001 | Naming convention enforcement with blocklist and dbt prefix rules |
| `data-critic` | claude-opus-4-8 | Adversarial architecture critique across 6 dimensions — always finds problems |

## Commands

```
/schema-review [file path or inline DDL]
/pipeline-audit [file path or directory]
/dbt-review [model file, model name, or models/ directory]
/dq-define "table or model name" [--framework great-expectations|dbt-tests|soda|elementary]
/data-contract "table or model name" [--producer name] [--consumer name]
/lineage [model name, DAG id, or project root]
/naming [directory path or file]
/data-critique "path to doc or inline description"
```

## Core Principles

- **No framework assumptions.** Every agent detects dbt, Airflow, Prefect, Spark, or plain Python ETL from project files. When ambiguous, it asks.
- **No schema format assumptions.** SQL DDL, Avro, Protobuf, JSON Schema, and dbt YAML are all first-class inputs. Format detected from file extension and content.
- **No silent writes.** `dq-definer` and `contract-generator` present the full draft before writing. Confirmation required.
- **No shared state.** Every agent is independently invocable. No session setup.

## Configuration

Place a `data-companion.config.yml` at the project root to override naming conventions:

```yaml
naming:
  custom_prefixes:
    - prefix: "raw_"
      layer: "raw ingestion"
  blocklist_additions:
    - abbr: "ts"
      use_instead: "timestamp or created_at"
  severity_overrides:
    dbt_prefix_violation: medium  # default: high
```

## Artifacts

| Command | Output | Location |
|---|---|---|
| `/schema-review` | Ranked findings report | stdout only |
| `/pipeline-audit` | Ranked findings report | stdout only |
| `/dbt-review` | Ranked findings report | stdout only |
| `/dq-define` | Framework-native check stubs | `data-quality/[table-slug].[ext]` |
| `/data-contract` | DCS YAML + Markdown summary | `docs/contracts/[slug].yaml` + `[slug].md` |
| `/lineage` | Lineage tree report | stdout only |
| `/naming` | Naming findings report | stdout only |
| `/data-critique` | Dimension-by-dimension critique | stdout only |
```

---

**Author:** <your-name> — you@example.com

## Dependencies

- requires: ai-baseline
