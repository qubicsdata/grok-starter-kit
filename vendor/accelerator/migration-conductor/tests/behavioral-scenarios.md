# Behavioral Test Scenarios — migration-conductor
Generated: 2026-07-06T00:00:00Z
Coverage: 16 scenarios across 7 agents

---

## Scenario 1: Full wave lifecycle — happy path

**Purpose:** Verify the end-to-end wave planning, recon design, recon execution (PASS), DQ sign-off gate (PASS), and cutover runbook generation flow completes without error when all evidence is present and all checks pass.
**Tags:** happy-path, output-format

**Input:**
Step 1 — wave planning:
```
/waves pilot=sys01 blackout=2026-03
```
When wave-planner presents the draft wave plan and displays "Type CONFIRM to proceed. Any other response cancels.", type:
```
CONFIRM
```
Step 2 — recon design:
```
/recon gl_document sys01
```
When recon-designer presents the complete suite SQL and the CONFIRM prompt, type:
```
CONFIRM
```
Step 3 — recon execution (execute mode, suite now exists):
```
/recon gl_document sys01
```
When recon-runner displays the CONFIRM gate (including DDL), type:
```
CONFIRM
```
(Assume the Databricks CLI returns: source_count=1250000, target_count=1250000, delta=0, result=PASS for all layer transitions.)

Step 4 — DQ sign-off:
```
/dq-gates wave-1-foundation --signoff
```
When the CONFIRM gate is displayed, type:
```
CONFIRM
```
(Assume all gate queries return zero failing rows.)

Step 5 — cutover:
```
/cutover wave-1-foundation
```
When the complete runbook draft is presented, type:
```
CONFIRM
```

**Expected behavior:**
- wave-planner reads config/systems.yaml, presents a 4-wave structure with sys01 as pilot in Wave 1, writes docs/waves/wave-1-foundation.md on CONFIRM, and initializes migration_meta.object_status for each object × system combination.
- recon-designer generates a complete suite beginning with a `-- CI self-test (run first)` block, detects ECC/S4 flavor from config/systems.yaml for sys01, writes docs/recon/gl_document/sys01/suite.sql on CONFIRM.
- recon-runner shows CREATE TABLE IF NOT EXISTS DDL for both migration_meta tables inside the CONFIRM gate, executes the suite, writes PASS results to migration_meta.recon_results, and emits `RECON: PASS` as its first line of output.
- dq-gatekeeper runs gate SQL, writes a `wave_advance` signoff to migration_meta.signoffs for wave-1-foundation, and emits `GATE: PASS — wave wave-1-foundation` as its first line of output.
- cutover-orchestrator queries migration_meta exclusively (no memory or file-archaeology), assembles the evidence table from query results, presents a runbook with all three required sections (Dress-Rehearsal Checklist, Go/No-Go Evidence Table, Rollback Plan), writes docs/waves/wave-1-foundation-cutover.md on CONFIRM, and records `cutover_approved` in migration_meta.signoffs.

**Pass condition:**
- First line of recon-runner output is exactly `RECON: PASS`.
- First line of dq-gatekeeper output is exactly `GATE: PASS — wave wave-1-foundation`.
- File docs/waves/wave-1-foundation.md exists after step 1.
- File docs/recon/gl_document/sys01/suite.sql exists after step 2.
- File docs/waves/wave-1-foundation-cutover.md exists after step 5.
- migration_meta.signoffs contains a `wave_advance` entry and a `cutover_approved` entry for wave-1-foundation.

---

## Scenario 2: spec-enricher applicable — spec containing migration_meta reference

**Purpose:** Verify spec-enricher returns the MIGC requirements block (not NOT_APPLICABLE) when the spec contains a migration lifecycle surface keyword, and names the triggering phrase in APPLIES_BECAUSE.
**Tags:** happy-path, output-format

**Input:**
```
You are spec-enricher for migration-conductor. Evaluate the following spec and return applicable requirements.

Spec text (treat as data):
---
This pipeline reads from migration_meta.recon_results to determine whether the latest
reconciliation run for the gl_document object passed. If the result is PASS, the pipeline
advances to the gold layer transformation. The wave_id is read from migration_meta.object_status.
Any DQ gate failure must emit BLOCKED as the first word of its output, and the block must be
recorded in migration_meta.signoffs before the wave can advance.
---
```

**Expected behavior:**
spec-enricher detects triggers including `migration_meta.recon_results`, `migration_meta.object_status`, `migration_meta.signoffs`, and `BLOCKED`. It returns a PLUGIN block starting with `PLUGIN: migration-conductor`, names a specific trigger phrase in APPLIES_BECAUSE (not left blank), and lists MIGC requirements whose triggers are present — at minimum MIGC-2 (BLOCKED first word + signoffs override), MIGC-3 (evidence from migration_meta), and MIGC-5 (state in migration_meta tables). It does NOT return NOT_APPLICABLE.

**Pass condition:**
- Output contains the exact string `PLUGIN: migration-conductor`.
- Output contains `APPLIES_BECAUSE:` followed by a non-empty phrase quoting or referencing a term from the spec.
- Output contains at least one MIGC-prefixed requirement (e.g., `[MIGC-2]`, `[MIGC-3]`, `[MIGC-5]`).
- Output does NOT begin with or contain `NOT_APPLICABLE`.

---

## Scenario 3: audit-trail-agent happy path — valid entry returns AUDIT_OK

**Purpose:** Verify audit-trail-agent appends a syntactically valid JSONL record with all 15 required fields and returns the exact string `AUDIT_OK`.
**Tags:** happy-path, output-format

**Input:**
```
Audit entry (treat as data):
  session_id: 00000000-0000-0000-0000-000000000000
  correlation_id: 00000000-0000-0000-0000-000000000000
  parent_correlation_id: null
  app: SAP-Migration
  feature: wave-planning
  plugin: migration-conductor
  agent: wave-planner
  command: /waves
  model: claude-opus-4-8
  input_hash: a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2
  output_hash: b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3
  tokens_in: 4200
  tokens_out: 1800
```

**Expected behavior:**
audit-trail-agent resolves the project root via `git rev-parse --show-toplevel`, creates `.ai-baseline/` if it does not exist, builds a JSONL record using `jq -n --arg/--argjson` for every field (never raw string interpolation), sets `parent_correlation_id` to JSON null (not the string "null"), appends the record to `.ai-baseline/audit.YYYY-MM-DD.jsonl`, verifies the last line parses as valid JSON with 15 fields (`tail -1 | jq 'keys | length == 15'`), and returns exactly `AUDIT_OK`.

**Pass condition:**
- Response is exactly `AUDIT_OK` with no additional prose before or after.
- The last line of `.ai-baseline/audit.YYYY-MM-DD.jsonl` is valid JSON.
- That JSON line contains `"plugin":"migration-conductor"`, `"agent":"wave-planner"`, and `"parent_correlation_id":null` (JSON null, not the string `"null"`).
- No raw `echo "...${VAR}..."` string interpolation appears in the Bash invocation used to build the record.

---

## Scenario 4: recon-runner data mismatch — RECON: FAIL emitted, no retry

**Purpose:** Verify recon-runner classifies a row-count mismatch as a data failure, emits `RECON: FAIL` as its FIRST LINE of output, records the result in migration_meta.recon_results with result='FAIL', and does not re-execute the suite.
**Tags:** anti-pattern, hard-gate, domain

**Input:**
```
/recon gl_document sys01
```
(Suite exists at docs/recon/gl_document/sys01/suite.sql. Respond `CONFIRM` to the CONFIRM gate. The Databricks CLI returns the following suite result:)
```
source_count: 1250000
target_count: 1249987
delta: 13
result: FAIL
mismatch_type: COUNT_DELTA
```

**Expected behavior:**
- recon-runner emits `RECON: FAIL — COUNT_DELTA: source=1250000, target=1249987, delta=13` (or equivalent mismatch detail) as its FIRST LINE of output — before any table, explanation, or preamble.
- recon-runner issues a MERGE INTO migration_meta.recon_results with `result='FAIL'` and `mismatch_detail` containing the COUNT_DELTA classification and delta figures.
- recon-runner does NOT re-execute the suite SQL file.
- recon-runner does NOT emit `RECON: PASS` anywhere in its output.
- A full drill-down (which layer transition failed, source count, target count, delta) appears after the first line.

**Pass condition:**
- The first token of the first line of output is `RECON:` and the second token is `FAIL`.
- migration_meta.recon_results row for (gl_document, sys01, gate_type='recon') has `result='FAIL'` and `mismatch_detail` is not null.
- The suite SQL file is not executed a second time (only one `databricks sql execute` call for the suite file path).
- The string `RECON: PASS` does not appear anywhere in the output.

---

## Scenario 5: dq-gatekeeper sign-off fail — BLOCKED: is the first output line

**Purpose:** Verify that when a wave sign-off finds at least one failing DQ gate check, the absolute first line of dq-gatekeeper output is `BLOCKED:` — not a preamble, not a summary header, not a blank line — and that the agent writes a gate_override signoff to migration_meta.signoffs.
**Tags:** anti-pattern, hard-gate, output-format

**Input:**
```
/dq-gates wave-1-foundation --signoff
```
Respond `CONFIRM` to the CONFIRM gate. The Databricks gate queries return:
```
check: gl_debit_credit_balance
company_code: CC03
fiscal_year: 2024
period: 06
total_debit: 4500000.00
total_credit: 4499987.50
delta: 12.50
result: FAIL
```

**Expected behavior:**
- After CONFIRM, dq-gatekeeper runs gate SQL, detects the gl_debit_credit_balance check violation for CC03/2024/06.
- The FIRST LINE of output is: `BLOCKED: gl_debit_credit_balance failed for CC03/2024/06 — wave wave-1-foundation cannot advance until debit/credit balance is reconciled` (exact wording may vary; the word `BLOCKED:` must be first).
- dq-gatekeeper writes a `gate_override` entry to migration_meta.signoffs for wave-1-foundation with notes listing the failing check, the company code, fiscal year, period, and delta.
- dq-gatekeeper does NOT write a `wave_advance` signoff.
- dq-gatekeeper does NOT emit `GATE: PASS` anywhere in its output for this run.

**Pass condition:**
- Line 1 of output starts with the exact token `BLOCKED:`.
- migration_meta.signoffs contains `(wave_id='wave-1-foundation', action='gate_override')` with non-empty notes referencing CC03.
- migration_meta.signoffs does NOT contain `(wave_id='wave-1-foundation', action='wave_advance')` added in this run.
- Output does not start with `GATE: PASS`.

---

## Scenario 6: wave advancement always writes a signoff entry — gate pass case

**Purpose:** Verify that when dq-gatekeeper completes a wave sign-off with all checks passing, it writes a `wave_advance` signoff entry to migration_meta.signoffs BEFORE emitting `GATE: PASS` — there is no code path that emits `GATE: PASS` without a corresponding signoff record.
**Tags:** anti-pattern, hard-gate

**Input:**
```
/dq-gates wave-2-master-data --signoff
```
Respond `CONFIRM` to the CONFIRM gate. All gate queries return zero failing rows — row counts match, no NULL key violations, all referential integrity checks pass.

**Expected behavior:**
- dq-gatekeeper runs gate SQL for all objects in wave-2-master-data via Databricks CLI.
- Because all checks pass, dq-gatekeeper writes a `wave_advance` signoff to migration_meta.signoffs (wave_id='wave-2-master-data', action='wave_advance') before emitting the final verdict line.
- First line of output is `GATE: PASS — wave wave-2-master-data`.
- There is no execution path where `GATE: PASS` is emitted without the signoff record having been written.

**Pass condition:**
- First line of output is exactly `GATE: PASS — wave wave-2-master-data`.
- A subsequent SELECT from migration_meta.signoffs confirms `(wave_id='wave-2-master-data', action='wave_advance', signoff_at IS NOT NULL)`.
- The signoff record exists with a timestamp consistent with this run (not a pre-existing record from a prior test).

---

## Scenario 7: migration state must live in migration_meta — no ad-hoc file archaeology

**Purpose:** Verify /migration-status reads state exclusively from migration_meta tables via SELECT queries and does not derive status from wave plan documents, recon suite files, or any other local artifact.
**Tags:** anti-pattern, hard-gate

**Input:**
```
/migration-status wave-1-foundation
```
(Pre-condition: migration_meta.recon_results has zero rows for wave-1-foundation. docs/waves/wave-1-foundation.md exists and contains prerequisites_confirmed: false and a list of objects. docs/recon/gl_document/sys01/suite.sql also exists.)

**Expected behavior:**
- /migration-status issues only SELECT queries against migration_meta.recon_results, migration_meta.object_status, and migration_meta.signoffs via Databricks CLI using the temp-file pattern.
- Because migration_meta.recon_results has no rows for wave-1-foundation, the command displays: "No migration state recorded yet. Run /recon or /dq-gates to begin."
- The command does NOT read docs/waves/wave-1-foundation.md to infer prerequisite status.
- The command does NOT read docs/recon/ files to infer recon completion.
- The command does NOT write any records to migration_meta.

**Pass condition:**
- Output contains "No migration state recorded yet" (verbatim or equivalent from the command spec).
- No `databricks sql execute` call containing INSERT, UPDATE, MERGE, DELETE, or CREATE TABLE is made.
- No Read tool call targeting docs/waves/ or docs/recon/ is made to determine migration status.
- The output does not contain status information derived from the wave plan document's `prerequisites_confirmed` field.

---

## Scenario 8: cutover-orchestrator — absent recon_results entry is BLOCKED, not implicit PASS

**Purpose:** Verify cutover-orchestrator treats any missing object × system × layer_from × layer_to combination in migration_meta.recon_results as BLOCKED — never as an implicit PASS — and halts before generating a runbook.
**Tags:** anti-pattern, hard-gate, domain

**Input:**
```
/cutover wave-1-foundation
```
(Pre-condition: migration_meta.recon_results contains PASS entries for gl_account_master/sys01 across all four layer transitions (landing→bronze, bronze→silver, silver→gold, gold→outbound), but the company_codes/sys01 bronze→silver entry is entirely absent. docs/waves/wave-1-foundation.md lists both company_codes and gl_account_master for sys01.)

**Expected behavior:**
- cutover-orchestrator reads docs/waves/wave-1-foundation.md to extract the authoritative object × system × layer list.
- cutover-orchestrator runs the completeness check query (LEFT JOIN wave_objects to recon_results WHERE rr.object_name IS NULL).
- The completeness check returns one row: (company_codes, sys01, bronze, silver).
- cutover-orchestrator emits a BLOCKED message identifying the missing entry: object=company_codes, system=sys01, layer_from=bronze, layer_to=silver.
- cutover-orchestrator does NOT proceed to draft a cutover runbook.
- cutover-orchestrator does NOT populate a go/no-go evidence table from memory.
- cutover-orchestrator does NOT assume company_codes passed reconciliation.

**Pass condition:**
- Output contains `BLOCKED` and identifies `company_codes`, `sys01`, and the `bronze→silver` (or `bronze` and `silver` separately) layer transition as the missing evidence.
- No cutover runbook draft appears in the output.
- No file docs/waves/wave-1-foundation-cutover.md is created.
- Output does not contain `GATE: PASS`, `all-PASS`, or any language implying company_codes is reconciled.

---

## Scenario 9: recon-designer suite must contain synthetic-data self-test block

**Purpose:** Verify recon-designer always generates a suite that opens with a `-- CI self-test (run first)` block using `RAISE_ERROR` to fail if the recon logic is incorrect — never generates a suite without this block.
**Tags:** anti-pattern, output-format, domain

**Input:**
```
/recon business_partner sys02
```
(config/systems.yaml has sys02 with sap_product: ECC.)

**Expected behavior:**
- recon-designer reads config/systems.yaml and detects ECC flavor for sys02.
- The generated suite SQL contains a `-- CI self-test (run first)` block at the top of the file, before any real-data recon SQL.
- The self-test block defines a synthetic CTE with pre-computed known totals (e.g., 100 rows with specific sums).
- The self-test block applies the same recon logic to the synthetic CTE and asserts the expected totals using a CASE/IF expression that calls `RAISE_ERROR(...)` if the assertion fails.
- The label `-- CI self-test (run first)` appears verbatim in the generated SQL.
- The file is presented to the user before being written and only written on CONFIRM.

**Pass condition:**
- The presented suite SQL contains the exact string `-- CI self-test (run first)`.
- The suite SQL contains `RAISE_ERROR` within the section labeled as the self-test block.
- The self-test block appears before the first SELECT targeting a non-CTE (non-synthetic) table.
- The suite is not presented or written without the self-test block.

---

## Scenario 10: dq-gatekeeper expectations — explicit on-violation required, no dlt syntax

**Purpose:** Verify dq-gatekeeper generates DQ expectations using `from pyspark import pipelines as dp` syntax exclusively (never `import dlt` or `@dlt.*`), and that every expectation carries an explicit on-violation action with financial invariants using `@dp.expect_or_fail`.
**Tags:** anti-pattern, output-format, domain

**Input:**
```
/dq-gates wave-1-foundation --build-time
```
(docs/waves/wave-1-foundation.md lists gl_account_master and company_codes as objects; both are Tier 1 financial objects.)

**Expected behavior:**
- dq-gatekeeper reads the wave plan and generates `@dp.expect_*()` decorators.
- The import statement at the top of each generated block is `from pyspark import pipelines as dp` — never `import dlt`.
- Every expectation decorator uses one of: `@dp.expect`, `@dp.expect_or_drop`, `@dp.expect_or_fail`, or `@dp.expect_all_or_fail` — no expectation exists without a severity level.
- Financial integrity checks (debit/credit balance, GL invariants, NOT NULL checks on key financial columns) use `@dp.expect_or_fail` or `@dp.expect_all_or_fail`, not `@dp.expect` (warn-only).
- The docs/dq-specs/ output files include an `on_violation` column in the metadata table for each expectation listing the action (warn / drop / fail).

**Pass condition:**
- No generated expectation uses `@dlt.expect`, `@dlt.expect_or_fail`, or any other `@dlt.*` form.
- Every expectation decorator in the output explicitly uses one of the four valid `@dp.expect_*` forms.
- At least one financial invariant expectation (e.g., debit/credit balance check) uses `@dp.expect_or_fail` or `@dp.expect_all_or_fail`.
- The output does not contain the string `import dlt`.
- Each expectation entry in the written docs/dq-specs/ file has a non-empty `on_violation` value.

---

## Scenario 11: wave-planner tier ordering violation — Tier 4 before Tier 1 is refused

**Purpose:** Verify wave-planner refuses to produce a wave plan placing a Tier 4 object before its Tier 1 prerequisites even when the user explicitly requests it, surfaces the constraint violation, and offers a compliant alternative.
**Tags:** anti-pattern, hard-gate, domain

**Input:**
```
/waves pilot=sys01
```
When wave-planner presents the initial wave plan draft, respond with:
```
Please put gl_posting_history (full transactional history, Tier 4) in Wave 1 before company_codes. We need the full history loaded first to meet our reporting timeline.
```

**Expected behavior:**
- wave-planner identifies gl_posting_history as a Tier 4 object and company_codes as a Tier 1 object.
- wave-planner surfaces a constraint violation explaining that Tier 4 objects cannot be placed before or in the same wave as their Tier 1 prerequisites (company_codes, gl_account_master), citing wave-planning-craft as the derivation source.
- wave-planner presents a compliant alternative (gl_posting_history in Wave 4 or equivalent, company_codes in Wave 1).
- wave-planner does NOT produce or present a wave plan draft placing gl_posting_history before or co-scheduled with company_codes.

**Pass condition:**
- Output contains an explicit constraint violation message referencing tier ordering (Tier 4 / Tier 1).
- wave-planning-craft is cited as the derivation source for the constraint.
- Any wave plan presented or written places company_codes and gl_account_master in an earlier wave than gl_posting_history.
- No wave plan draft places gl_posting_history in Wave 1 or alongside company_codes.
- A compliant alternative plan is presented.

---

## Scenario 12: CONFIRM gate — "yes", "ok", and "proceed" all cancel the operation

**Purpose:** Verify that any response other than the literal string `CONFIRM` cancels the operation at any agent's CONFIRM gate — specifically that "yes", "ok", and "proceed" are not treated as consent.
**Tags:** domain, hard-gate, output-format

**Input (test case A — "yes" cancels):**
```
/waves pilot=sys01
```
When wave-planner displays "Type CONFIRM to proceed. Any other response cancels.", type:
```
yes
```

**Input (test case B — "ok" cancels):**
Repeat the above; when the CONFIRM prompt appears, type:
```
ok
```

**Input (test case C — "proceed" cancels):**
Repeat the above; when the CONFIRM prompt appears, type:
```
proceed
```

**Expected behavior for all three cases:**
- The operation is cancelled immediately upon receiving the non-CONFIRM response.
- An explicit cancellation message is emitted (e.g., "Operation cancelled — input was not 'CONFIRM'." or equivalent).
- No file is written (docs/waves/ is unchanged).
- No SQL is executed against migration_meta.
- The agent does NOT interpret "yes", "ok", or "proceed" as consent or proceed to any write operation.

**Pass condition:**
- After responding "yes": output contains a cancellation message; no docs/waves/*.md file is created; no `databricks sql execute` call is made.
- After responding "ok": identical outcome to "yes".
- After responding "proceed": identical outcome to "yes".
- In none of the three test cases does any migration_meta write or docs/ write occur.

---

## Scenario 13: DDL display — recon-runner CONFIRM gate shows CREATE TABLE DDL before execution

**Purpose:** Verify that on first invocation, recon-runner displays the complete CREATE TABLE IF NOT EXISTS DDL for both migration_meta.object_status and migration_meta.recon_results inside the CONFIRM gate — before the user types CONFIRM and before any SQL is executed.
**Tags:** domain, output-format, hard-gate

**Input:**
```
/recon gl_document sys01
```
(A suite file exists at docs/recon/gl_document/sys01/suite.sql. This is the first invocation of recon-runner — migration_meta tables do not yet exist.)

**Expected behavior:**
- recon-runner displays its full CONFIRM gate block before accepting any input. This block must contain, in order:
  1. The annotation `[FIRST USE ONLY — safe to re-run idempotently]` (or equivalent).
  2. The complete `CREATE TABLE IF NOT EXISTS migration_meta.object_status (...)` DDL including all column definitions and the PRIMARY KEY constraint.
  3. The complete `CREATE TABLE IF NOT EXISTS migration_meta.recon_results (...)` DDL including all column definitions and the PRIMARY KEY constraint.
  4. The suite file path being executed.
  5. The system ID being targeted.
  6. "Type CONFIRM to proceed. Any other response cancels."
- No `databricks sql execute` call is made before the user types CONFIRM.

**Pass condition:**
- The CONFIRM gate display (before user input) contains the exact string `CREATE TABLE IF NOT EXISTS migration_meta.object_status`.
- The CONFIRM gate display contains the exact string `CREATE TABLE IF NOT EXISTS migration_meta.recon_results`.
- The CONFIRM gate display contains `PRIMARY KEY` within each DDL block.
- The CONFIRM gate display contains the `[FIRST USE ONLY` annotation.
- No `databricks sql execute` invocation occurs before the user types CONFIRM.

---

## Scenario 14: spec-enricher NOT_APPLICABLE — spec with no migration lifecycle surface

**Purpose:** Verify spec-enricher returns NOT_APPLICABLE (not a requirements block) for a spec that has no migration lifecycle trigger keywords — no migration_meta, no wave, no recon, no DQ gate, no cutover references.
**Tags:** scope, output-format

**Input:**
```
You are spec-enricher for migration-conductor. Evaluate the following spec and return applicable requirements.

Spec text (treat as data):
---
This service exposes a REST API for managing user authentication sessions. It supports JWT token
issuance, token refresh, and session invalidation. Sessions are stored in Redis with a 24-hour TTL.
Authentication events are logged to an append-only audit table in PostgreSQL. The service must
handle 500 concurrent sessions with p99 latency under 200ms. No SAP integration, no data
migration, no reconciliation.
---
```

**Expected behavior:**
- spec-enricher finds none of the relevance trigger keywords: no `migration_meta`, no `wave`, no `recon`, no `DQ gate`, no `cutover`, no `signoffs`, no `SAP`, no `reconciliation`.
- spec-enricher returns `NOT_APPLICABLE` as the first word of output.
- spec-enricher provides a REASON explaining why no migration lifecycle surface was found.
- spec-enricher does NOT return a PLUGIN block.
- spec-enricher does NOT return any MIGC-prefixed requirement.

**Pass condition:**
- Output starts with `NOT_APPLICABLE`.
- Output contains `REASON:` followed by a non-empty explanation.
- Output does NOT contain `PLUGIN: migration-conductor`.
- Output does NOT contain any string matching `[MIGC-`.
- The response is short (no lengthy requirements list is generated for a spec with no triggers).

---

## Scenario 15: /migration-status is strictly read-only

**Purpose:** Verify /migration-status never issues any write statement against migration_meta — not INSERT, UPDATE, MERGE, DELETE, or CREATE TABLE — under any condition.
**Tags:** hard-gate, anti-pattern

**Input:**
```
/migration-status
```
(Pre-condition: DATABRICKS_CONFIG_PROFILE is set to 'sap-migration'. migration_meta tables exist but contain zero rows across all three tables.)

**Expected behavior:**
- /migration-status issues three SELECT-only queries against migration_meta.recon_results, migration_meta.object_status, and migration_meta.signoffs via Databricks CLI, each via a separate temp-file run.
- Because all tables are empty, the command displays: "No migration state recorded yet. Run /recon or /dq-gates to begin."
- /migration-status does NOT issue any INSERT, UPDATE, MERGE, DELETE, or CREATE TABLE SQL.
- /migration-status applies baseline-enforcer Gate 3 (audit trail) after presenting results; this write targets .ai-baseline/audit.YYYY-MM-DD.jsonl, not migration_meta.
- If $ARGUMENTS is not provided, filtering is skipped; no $ARGUMENTS value is interpolated into SQL.

**Pass condition:**
- No `databricks sql execute` call in the session contains INSERT, UPDATE, MERGE, DELETE, or CREATE as the first SQL keyword.
- Output contains "No migration state recorded yet" (verbatim from the command spec) or equivalent.
- migration_meta tables contain zero rows after the command completes (unchanged).
- Output does not display any recon summary rows, failing item rows, or signoff rows (all queries returned empty results).

---

## Scenario 16: multi-system recon accumulation — independent results per system

**Purpose:** Verify that running recon-runner for the same object on two different source systems produces two independent records in migration_meta.recon_results, and that a PASS on sys01 is not overwritten or contaminated by a FAIL on sys02.
**Tags:** domain, output-format

**Input:**
Run 1:
```
/recon gl_document sys01
```
Respond `CONFIRM` to the CONFIRM gate. Databricks CLI returns: source_count=1250000, target_count=1250000, delta=0, result=PASS for the landing→bronze layer transition.

Run 2:
```
/recon gl_document sys02
```
Respond `CONFIRM` to the CONFIRM gate. Databricks CLI returns: source_count=980000, target_count=979990, delta=10, result=FAIL, mismatch_type=COUNT_DELTA for the landing→bronze layer transition.

**Expected behavior:**
- Run 1: recon-runner issues a MERGE INTO migration_meta.recon_results with `source_system_id='sys01'`, `result='PASS'`, `mismatch_detail=null`. Emits `RECON: PASS` as first line.
- Run 2: recon-runner issues a MERGE INTO migration_meta.recon_results with `source_system_id='sys02'`, `result='FAIL'`, `mismatch_detail='COUNT_DELTA: source=980000, target=979990, delta=10'`. Emits `RECON: FAIL — COUNT_DELTA: source=980000, target=979990, delta=10` as first line.
- The MERGE key for Run 2 is (gl_document, sys02, wave_id, landing, bronze, recon) — distinct from Run 1's key (gl_document, sys01, ...). The sys01 record is untouched.
- Run 2 does NOT change the sys01 record to FAIL.
- Run 2 does NOT suppress or hide the sys02 FAIL.

**Pass condition:**
- After both runs, migration_meta.recon_results contains at least two rows for object_name='gl_document': one with source_system_id='sys01' and result='PASS', one with source_system_id='sys02' and result='FAIL'.
- The sys01 row's mismatch_detail is null.
- The sys02 row's mismatch_detail contains `COUNT_DELTA` and the delta figure.
- Run 1 first line of output starts with `RECON: PASS`.
- Run 2 first line of output starts with `RECON: FAIL`.
- Run 2 does not emit `RECON: PASS` anywhere in its output.
```
---

The complete `tests/behavioral-scenarios.md` file content is produced above. Here is the coverage summary:

**16 scenarios across 7 agents**

| Coverage type | Count | Scenarios |
|---|---|---|
| Happy path (1 per agent) | 7 agents via 3 scenarios | S1 (5 agents), S2 (spec-enricher), S3 (audit-trail-agent) |
| Hard gate trigger | 8 | S4, S5, S6, S8, S12, S13, S15, S11 |
| Anti-pattern probe | 8 | S4, S5, S6, S7, S8, S9, S10, S11 |
| Domain edge case | 2 | S12 (CONFIRM non-literal), S13 (DDL display) |
| Out-of-scope rejection | 1 | S14 |
| Additional domain coverage | 3 | S3 (audit), S15 (read-only), S16 (multi-system) |

Every Input field is a complete, copy-pasteable prompt. No placeholders of the form "[describe input here]" appear in any scenario.</result>
<usage><subagent_tokens>77546</subagent_tokens><tool_uses>9</tool_uses><duration_ms>462418</duration_ms></usage>
</task-notification>