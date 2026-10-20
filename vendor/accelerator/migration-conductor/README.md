# migration-conductor

Migration lifecycle verification for SAP to Databricks to SAP consolidation. This plugin
orchestrates the complete migration verification lifecycle: wave planning, SQL reconciliation
suites, DQ gate generation, and cutover runbook production. All migration state lives in
`migration_meta` tables — no ad-hoc files.

## Purpose

migration-conductor provides five commands that cover the full migration lifecycle:

1. **Plan** migration waves respecting SAP object dependency tiers
2. **Design and execute** reconciliation suites per object × source system
3. **Generate and run** DQ gate checks per wave
4. **Assemble** go/no-go evidence and produce cutover runbooks
5. **Query** current migration state from a single source of truth

## Prerequisites

### Required Plugins

- **ai-baseline** — mandatory baseline (audit trail, PII scrub, cost gate)
- **databricks-engineer** — SQL execution, pipeline building, Databricks auth
- **sap-migration-companion** — SAP profiling, object mapping, harmonization

### Required Environment

```bash
# Set your Databricks CLI profile before using any command
export DATABRICKS_CONFIG_PROFILE=sap-migration

# Optional: explicit warehouse ID (falls back to profile default)
export DATABRICKS_WAREHOUSE_ID=<warehouse-id>
```

Verify auth: `databricks workspace list --profile "$DATABRICKS_CONFIG_PROFILE"`

### Required Project Files

- `config/systems.yaml` — system registry (8 source systems + target)
- Databricks Unity Catalog with `migration_meta` schema (tables created on first use, idempotent)

## Installation

```bash
# From the accelerator marketplace
accelerator install migration-conductor

# Or clone directly
git clone <repo-url> ~/.claude/plugins/migration-conductor
```

After installation, verify:
```bash
claude /waves --help
```

## Agents

| Agent | Model | Role |
|-------|-------|------|
| `wave-planner` | claude-opus-4-8 | Sequences objects × systems into dependency-ordered waves; produces docs/waves/ documents |
| `recon-designer` | claude-sonnet-5 | Generates reconciliation SQL suites with ECC/S4 flavor detection and synthetic self-test |
| `recon-runner` | claude-haiku-4-5-20251001 | Mechanical executor — runs suites via Databricks CLI, writes results to migration_meta |
| `dq-gatekeeper` | claude-sonnet-5 | Generates @dp.expect_*() expectations (build-time) or runs wave sign-off gate checks |
| `cutover-orchestrator` | claude-opus-4-8 | Assembles go/no-go evidence from migration_meta and produces cutover runbooks |
| `spec-enricher` | claude-sonnet-5 | Returns MIGC-prefixed requirements when invoked by ai-baseline's enrich runner |
| `audit-trail-agent` | claude-haiku-4-5-20251001 | Append-only audit logger; records every invocation to .ai-baseline/audit.YYYY-MM-DD.jsonl |

## Skills

| Skill | Description |
|-------|-------------|
| `reconciliation-craft` | Row count, hash total, financial integrity, and ECC/S4 recon patterns; mismatch taxonomy; self-test structure |
| `wave-planning-craft` | Tier ordering rules, pilot-system-first strategy, wave sizing, business constraint application |
| `migration-state-spec` | Canonical DDL for migration_meta tables; MERGE patterns; completeness check query |
| `cutover-gate-spec` | Required evidence set for go/no-go; evidence table format; rollback checklist items |
| `baseline-enforcer` | Three unconditional gates: PII scrub, cost gate, audit trail (injected from ai-baseline) |

## Commands

### `/waves [constraint-hints]`

Plan and sequence migration waves. Reads `config/systems.yaml`, applies tier ordering, produces
`docs/waves/<wave-slug>.md`, and initializes `migration_meta.object_status`.

```bash
/waves
/waves pilot=sys01 blackout=2026-03
/waves pilot=sys01 wave-size=2 cutover-date=2026-09-01
```

### `/recon <object> [system-id]`

Design or execute a reconciliation suite. Defaults to design mode (generates suite SQL).
If a suite already exists, offers execute mode (runs via Databricks CLI).

```bash
/recon gl_document sys01          # design: generates docs/recon/gl_document/sys01/suite.sql
/recon gl_document sys01          # execute: if suite exists, runs it and writes to migration_meta
/recon business_partner           # design for all active systems
```

### `/dq-gates <wave-id> [--build-time | --signoff]`

Generate DQ expectations or run wave sign-off gate checks.

```bash
/dq-gates wave-1-foundation                  # build-time: generates @dp.expect_*() expectations
/dq-gates wave-1-foundation --build-time     # explicit build-time
/dq-gates wave-1-foundation --signoff        # sign-off: runs gate queries, emits GATE: PASS or BLOCKED
```

### `/cutover <wave-id>`

Assemble go/no-go evidence and produce the cutover runbook.

```bash
/cutover wave-1-foundation         # queries migration_meta, checks completeness, drafts runbook
```

Output: `docs/waves/wave-1-foundation-cutover.md` (after CONFIRM)

### `/migration-status [wave-id | object-name]`

Query current migration state. Read-only. No writes.

```bash
/migration-status                          # all waves, all objects
/migration-status wave-1-foundation        # filtered to one wave
/migration-status gl_document              # filtered to one object
```

## Migration State

All migration state lives in three `migration_meta` tables (created on first use, idempotent):

| Table | Purpose |
|-------|---------|
| `migration_meta.object_status` | Progress per object × source system × layer (`not_started` → `recon_pass` → `gate_pass` → `migrated`) |
| `migration_meta.recon_results` | Reconciliation evidence — written by recon-runner (`gate_type='recon'`) and dq-gatekeeper (`gate_type='dq'`) |
| `migration_meta.signoffs` | Wave advancement signoffs, cutover approvals, and gate override records |

## Artifact Paths

| Artifact | Path |
|----------|------|
| Wave plans | `docs/waves/<wave-slug>.md` |
| Cutover runbooks | `docs/waves/<wave-id>-cutover.md` |
| Reconciliation suites | `docs/recon/<object>/<system-id>/suite.sql` |
| DQ expectation specs | `docs/dq-specs/<wave-id>/<object>-expectations.md` |

## Key Design Principles

- **Evidence-only:** Cutover decisions are assembled from `migration_meta.recon_results` — never from memory.
- **Recon failures are evidence, not errors:** A `RECON: FAIL` result is recorded and surfaced; it is never retried.
- **BLOCKED is a first-class state:** Any failing gate emits `BLOCKED:` as its first output line. Wave advancement past a BLOCKED gate requires an explicit human override in `migration_meta.signoffs`.
- **CONFIRM is literal:** Every write or execution gate requires the user to type exactly `CONFIRM`. No aliases.

## Dependencies

- requires: ai-baseline
