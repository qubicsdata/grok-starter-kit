---
name: databricks-cli-reference
description: |
  Import before executing any Databricks CLI command. Provides auth setup, pre-flight
  checks, SQL execution syntax, bundle commands, the SAFE COMMAND LIST, MUTATING COMMAND
  list, error contract, and credential safety rules.
  Triggers on: any Databricks CLI invocation, bundle deployment, SQL execution via CLI.
---

# Databricks CLI Craft

## Authentication

### DATABRICKS_CONFIG_PROFILE

All CLI authentication uses named profiles from `~/.databrickscfg`. The active profile is selected via the `DATABRICKS_CONFIG_PROFILE` environment variable.

```bash
# Set the active profile
export DATABRICKS_CONFIG_PROFILE=my-workspace-profile

# Use in all CLI commands via --profile flag
databricks <command> --profile $DATABRICKS_CONFIG_PROFILE
```

### ~/.databrickscfg Format

```ini
[DEFAULT]
host  = https://adb-1234567890.1.azuredatabricks.net
token = dapi...

[prod-workspace]
host  = https://adb-9876543210.2.azuredatabricks.net
token = dapi...

[dev-workspace]
host  = https://adb-1111111111.3.azuredatabricks.net
token = dapi...
```

For OAuth M2M (service principals):
```ini
[svc-pipeline]
host          = https://adb-1234567890.1.azuredatabricks.net
client_id     = <service-principal-client-id>
client_secret = <service-principal-secret>
```

### Token vs OAuth M2M

| Auth Method | Use Case |
|---|---|
| PAT (Personal Access Token) | Developer workstations, ad-hoc CLI use |
| OAuth M2M | Service accounts, CI/CD pipelines, automated deployments |

Always prefer OAuth M2M for production automation — PATs are tied to individual users.

## Pre-flight Check (MANDATORY before any CLI command)

```bash
if [ -z "$DATABRICKS_CONFIG_PROFILE" ]; then
  echo "ERROR: DATABRICKS_CONFIG_PROFILE is not set."
  echo "Set this environment variable to your Databricks CLI profile name."
  echo "Example: export DATABRICKS_CONFIG_PROFILE=dev-workspace"
  exit 1
fi
```

If `DATABRICKS_CONFIG_PROFILE` is unset: surface the error above and stop. Do not proceed.

## SQL Execution

Always write queries to a temp file and pass via `--file` to prevent shell injection:

```bash
QUERY_FILE=$(mktemp)
echo "$QUERY" > "$QUERY_FILE"
databricks sql execute \
  --profile "$DATABRICKS_CONFIG_PROFILE" \
  --warehouse-id "$WAREHOUSE_ID" \
  --file "$QUERY_FILE"
rm -f "$QUERY_FILE"
```

For an existing `.sql` file:
```bash
databricks sql execute \
  --profile "$DATABRICKS_CONFIG_PROFILE" \
  --warehouse-id "$WAREHOUSE_ID" \
  --file query.sql
```

**Never hardcode the warehouse ID.** Obtain it from:
- User-provided context
- `databricks warehouses list --profile $DATABRICKS_CONFIG_PROFILE`
- Environment variable: `$DBX_WAREHOUSE_ID`

## Bundle Commands

```bash
# Validate bundle configuration
databricks bundle validate

# Deploy to a target
databricks bundle deploy --target <env>

# Run a job or pipeline resource
databricks bundle run <resource-name>

# Run with specific target
databricks bundle run <resource-name> --target <env>
```

Target values: `dev`, `qa`, `prod`, `smoke-ecc`, `smoke-s4` (or as defined in `databricks.yml`).

## SAFE COMMAND LIST (no confirmation required)

These commands are read-only and may be executed without user confirmation:

```
databricks pipelines list --profile $PROFILE
databricks pipelines get --pipeline-id <id> --profile $PROFILE
databricks pipelines list-pipeline-events --pipeline-id <id> --profile $PROFILE
databricks jobs list --profile $PROFILE
databricks jobs get --job-id <id> --profile $PROFILE
databricks jobs list-runs --job-id <id> --profile $PROFILE
databricks warehouses list --profile $PROFILE
databricks warehouses get --id <id> --profile $PROFILE
databricks catalogs list --profile $PROFILE
databricks schemas list --catalog-name <name> --profile $PROFILE
databricks tables list --catalog-name <name> --schema-name <name> --profile $PROFILE
databricks clusters list --profile $PROFILE
databricks bundle validate
databricks runs get --run-id <id> --profile $PROFILE
databricks sql execute --profile $PROFILE --warehouse-id <id> --file <query-file>
```

## MUTATING COMMANDS (require confirmation gate)

These commands create, modify, or delete workspace resources. Present a confirmation gate before executing:

```
databricks bundle deploy ...
databricks bundle run ...
databricks pipelines start --pipeline-id <id>
databricks pipelines stop --pipeline-id <id>
databricks pipelines reset --pipeline-id <id>
databricks pipelines delete --pipeline-id <id>
databricks jobs run-now --job-id <id>
databricks jobs cancel-run --run-id <id>
databricks clusters start --cluster-id <id>
databricks clusters delete --cluster-id <id>
databricks sql execute ... --file <file-with-INSERT|UPDATE|DELETE|MERGE|CREATE|ALTER|DROP|TRUNCATE>
```

## Error Contract

### Tool Failure (non-zero CLI exit code)

A tool failure is a CLI infrastructure failure: authentication error, network timeout, malformed request, missing resource.

**Protocol:**
1. Capture the exact stderr output.
2. Retry the command once with the same parameters.
3. If the second attempt also fails: surface the exact stderr from both attempts. Stop. Do not retry further.

### Data Failure (unexpected results, pipeline errors, data anomalies)

A data failure is when the CLI returns exit code 0 but the data outcome is wrong: unexpected nulls, row count mismatches, pipeline stage failures, DQ violations, empty results when records are expected.

**Protocol:**
1. NEVER retry a data failure — retrying a broken pipeline does not fix it.
2. Report the actual results verbatim as evidence.
3. Classify the failure type: schema mismatch, missing source data, DQ violation, CDC sequencing error, etc.
4. Stop and surface findings to the user.

## Credential Safety

- **Profile name** (`DATABRICKS_CONFIG_PROFILE` value): safe to log, display, and include in error messages.
- **Token values** (`dapi...`): NEVER log, display, interpolate into strings, or echo. If a token appears in stderr, redact it before surfacing.
- **Client secrets** (OAuth M2M): same rule as tokens — never log.
- **Host URLs**: safe to log.
- **Warehouse IDs**: safe to log.

## Hard Gates

**DO NOT proceed with any CLI command if DATABRICKS_CONFIG_PROFILE is unset — run the pre-flight check first.**
**DO NOT hardcode tokens, client secrets, host URLs, or warehouse IDs in any generated command, script, or config.**
**DO NOT interpolate a query string directly into a CLI command — always write to a temp file and pass via --file.**
**DO NOT retry a data failure — retry only on tool failure (non-zero exit), once.**
**DO NOT log or surface token values even if they appear in CLI output — redact before displaying.**
