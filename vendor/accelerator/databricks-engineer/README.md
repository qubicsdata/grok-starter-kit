# databricks-engineer

A Claude Code plugin that brings full Databricks platform capability to your workspace: building Lakeflow Declarative Pipelines with the `pyspark.pipelines` module, executing SQL against Databricks SQL warehouses, authoring PySpark serverless jobs, governing Unity Catalog, and deploying Asset Bundles.

## Prerequisites

Before using any command in this plugin, ensure the following:

1. **Databricks CLI installed and configured:**
   ```bash
   pip install databricks-cli
   # or
   brew install databricks
   ```

2. **`DATABRICKS_CONFIG_PROFILE` environment variable set:**
   ```bash
   export DATABRICKS_CONFIG_PROFILE=my-workspace-profile
   ```
   This must point to a named profile in `~/.databrickscfg`. Every agent in this plugin checks for this variable at pre-flight and stops with a clear error if it is absent. Never hardcode tokens or host URLs.

3. **`databricks.yml` present** for bundle operations (pipeline generation and deployment commands).

4. **Databricks Runtime**: Lakeflow Declarative Pipelines require Serverless or Pro/Advanced edition. Classic compute is not supported by `pyspark.pipelines`.

5. **`ai-baseline` plugin installed** (required dependency).

## Installation

Add to your `.claude-plugin/plugin.json` `requires` array, or install the plugin into your accelerator workspace:

```bash
# From your accelerator workspace root
cp -r databricks-engineer .claude-plugin/
```

Ensure `ai-baseline` is also installed — it provides the audit trail, PII scrub, and cost gate infrastructure that every agent in this plugin depends on.

## Command Reference

| Command | Arguments | Description |
|---|---|---|
| `/dbx-pipeline` | `<spec-path>` | Generate a Lakeflow Declarative Pipeline from a mapping spec file |
| `/dbx-sql` | `<query or question>` | Execute SQL against a Databricks SQL warehouse |
| `/dbx-deploy` | `[target]` | Deploy an Asset Bundle to a target (default: `dev`) |
| `/dbx-inspect` | `[scope]` | Discover workspace resources (pipelines, jobs, warehouses, catalogs) |
| `/uc-setup` | _(none)_ | Interactive Unity Catalog setup: catalogs, schemas, grants, PII tags |

### /dbx-pipeline

Generates Lakeflow Declarative Pipeline source files and a `databricks.yml` Asset Bundle from a mapping spec.

```bash
/dbx-pipeline specs/gl_mapping.yaml
/dbx-pipeline mappings/bkpf_to_bronze.json
```

- Validates the spec path (rejects `..` and absolute paths outside project root)
- Generates `.py` pipeline source using `from pyspark import pipelines as dp`
- Generates `databricks.yml` with `dev`, `qa`, `prod`, `smoke-ecc`, and `smoke-s4` targets
- Presents full draft before writing — no files written without confirmation

### /dbx-sql

Execute a SQL query or answer a data question using the Databricks CLI.

```bash
/dbx-sql SELECT COUNT(*) FROM gold.finance.gl WHERE fiscal_year = 2025
/dbx-sql DESCRIBE HISTORY bronze.sys01_ecc.bkpf
/dbx-sql How many open items are in the AR aging table?
```

- Read-only queries execute immediately
- Mutating statements (INSERT, UPDATE, DELETE, MERGE, CREATE, ALTER, DROP, etc.) require typing `CONFIRM`
- Retries tool failures once; reports data failures as evidence without retrying

### /dbx-deploy

Validate and deploy a Databricks Asset Bundle.

```bash
/dbx-deploy          # deploys to dev (default)
/dbx-deploy qa       # deploys to qa
/dbx-deploy prod     # deploys to prod (requires CONFIRM)
```

- Calls workspace-inspector for pre-flight before every deploy
- Runs `bundle validate` first — stops on validation failure
- Hard confirmation gate for `prod`/`production` target

### /dbx-inspect

Discover Databricks workspace resources.

```bash
/dbx-inspect               # discover all resources
/dbx-inspect pipelines     # list pipelines only
/dbx-inspect jobs          # list jobs only
/dbx-inspect warehouses    # list warehouses only
/dbx-inspect catalogs      # list Unity Catalog catalogs
```

- Read-only — never executes mutating commands
- Structured summary grouped by resource type

### /uc-setup

Interactive Unity Catalog governance setup.

```bash
/uc-setup
```

Guides through: catalog/schema creation per five-catalog layout, GRANT statements, PII column tagging, lineage queries, and naming convention validation.

## Agent Roster

| Agent | Model | Role |
|---|---|---|
| `pipeline-builder` | claude-sonnet-5 | Generate Lakeflow Declarative Pipelines + Asset Bundle manifests |
| `sql-analyst` | claude-sonnet-5 | Execute SQL via Databricks CLI with read/write gates |
| `pyspark-engineer` | claude-sonnet-5 | Author PySpark serverless jobs with optimization guidance |
| `uc-steward` | claude-sonnet-5 | Unity Catalog governance, grants, PII tags, lineage |
| `bundle-deployer` | claude-haiku-4-5-20251001 | Asset Bundle validate/deploy/run lifecycle |
| `workspace-inspector` | claude-haiku-4-5-20251001 | Read-only workspace discovery and pre-flight |
| `spec-enricher` | claude-sonnet-5 | Emits DBX-1 through DBX-6 requirements for enrich runner |
| `audit-trail-agent` | claude-haiku-4-5-20251001 | Append-only audit log (from ai-baseline) |

## Skill List

| Skill | Purpose |
|---|---|
| `lakeflow-declarative-pipelines` | Single idiom source for `pyspark.pipelines` (dp module) — decorators, CDC, expectations, smoke-test conventions |
| `databricks-cli-reference` | Auth, pre-flight, SQL execution, bundle commands, safe/mutating command lists, error contract |
| `unity-catalog-conventions` | Five-catalog layout, schema patterns, GRANT syntax, PII tagging, lineage views, naming rules |
| `pyspark-optimization-craft` | Liquid clustering, AQE, skew handling, join strategies, serverless config, Opus pass rules |
| `medallion-architecture-spec` | Layer responsibilities, promotion rules, landing contract, outbound contract |
| `spark-sql-dialect-notes` | ANSI mode, SAP migration pitfalls, Delta SQL, streaming SQL |
| `baseline-enforcer` | Unconditional PII scrub, cost gate, and audit trail gates (from ai-baseline) |

## Example Workflows

### 1. Generate a Bronze Pipeline from a Mapping Spec

```bash
# Create a spec file
cat > specs/bkpf_mapping.yaml << 'EOF'
source_system: sys01_ecc
source_table: BKPF
target_catalog: bronze
target_schema: sys01_ecc
target_table: bkpf
cdc_type: scd1
keys: [mandt, bukrs, belnr, gjahr]
sequence_col: _sequence_num
operation_col: _operation
EOF

# Generate the pipeline
/dbx-pipeline specs/bkpf_mapping.yaml
```

### 2. Validate and Deploy to Dev

```bash
/dbx-deploy dev
```

### 3. Run a Data Quality Query

```bash
/dbx-sql SELECT bukrs, COUNT(*) AS cnt, SUM(wrbtr) AS total FROM bronze.sys01_ecc.bseg GROUP BY bukrs ORDER BY cnt DESC
```

### 4. Inspect Pipeline Status

```bash
/dbx-inspect pipelines
```

### 5. Set Up Unity Catalog for a New Source System

```bash
/uc-setup
# Follow interactive prompts to:
# - Create landing.sys01_s4 schema
# - Create bronze.sys01_s4 schema
# - Grant USE CATALOG and USE SCHEMA to pipeline service principal
# - Grant CREATE TABLE on bronze.sys01_s4 to svc-pipeline-s4
```

### 6. Deploy to Production

```bash
/dbx-deploy prod
# Agent presents: "You are about to deploy to PRODUCTION. Type CONFIRM to proceed, or press Ctrl+C to cancel."
# Type: CONFIRM
```

### 7. Tag PII Columns After Silver Layer Creation

```bash
/uc-setup
# Select "Apply PII column tags"
# Specify table: silver.customer.person
# Specify columns: ssn, email, date_of_birth
```

## Error Handling

All agents in this plugin follow a two-class error contract:

| Class | Trigger | Response |
|---|---|---|
| **Tool failure** | Non-zero CLI exit code | Retry once, then surface exact stderr and stop |
| **Data failure** | Unexpected results, pipeline errors, data anomalies | Never retry — report as evidence, classify, stop |

This distinction prevents cascading failures: a broken pipeline should not be retried indefinitely, and a transient auth error should not cause the agent to give up immediately.

## Dependencies

This plugin requires:

- **`ai-baseline`** — provides `audit-trail-agent`, `pii-scrub-agent`, `cost-gate-agent`, `context-manager-agent`, and the `baseline-enforcer` skill. Every agent in this plugin imports `baseline-enforcer` and invokes audit-trail-agent after each invocation.

The `requires` field in `plugin.json`:
```json
"requires": ["ai-baseline"]
```
