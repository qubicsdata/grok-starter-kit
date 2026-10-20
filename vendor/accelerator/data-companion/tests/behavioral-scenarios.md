# data-companion — Behavioral Test Scenarios

These scenarios verify the plugin meets all success criteria from the design spec. Each scenario describes the input, expected behavior, and pass condition. Run manually against a test dbt project or the provided inline fixtures.

Total: 24 scenarios (Scenario 1–24)

---

## Scenario 1: schema-reviewer — SQL DDL, no format specified

**Command:** `/schema-review`
**Input:** Current directory contains `orders.sql` with a `CREATE TABLE` statement (no `--format` flag)
**Expected:** Agent detects SQL DDL automatically via schema-format-detector, identifies dialect from SQL syntax, produces ranked findings report.
**Pass:** Report is produced without prompting for format. Format and dialect appear in the report header or are implicit in the findings.

---

## Scenario 2: schema-reviewer — Avro schema

**Command:** `/schema-review src/schemas/events.avsc`
**Input:** `.avsc` file with `"type": "record"` structure
**Expected:** Agent detects Avro format, reviews field types and nullability, produces findings.
**Pass:** Report references Avro-specific field structure (e.g. `"type": ["null", "string"]` for nullable fields). No SQL-specific findings emitted.

---

## Scenario 3: schema-reviewer — dbt schema.yml

**Command:** `/schema-review models/staging/schema.yml`
**Input:** dbt `schema.yml` with `version: 2` and `sources:` block
**Expected:** Agent detects dbt YAML format, reviews column descriptions, tests declared, freshness config, not just data types.
**Pass:** Findings include dbt-specific concerns (missing `not_null` tests, missing `freshness` block, undescribed columns) — not just DDL-style type findings.

---

## Scenario 4: pipeline-auditor — Airflow DAG, framework auto-detected

**Command:** `/pipeline-audit dags/orders_pipeline.py`
**Input:** Airflow DAG file (contains `from airflow` import, `@dag` decorator)
**Expected:** Agent detects Airflow framework automatically, audits across 5 dimensions.
**Pass:** Framework detection produces "Airflow" without prompting user. Airflow-specific findings present (e.g. missing `retries` parameter, missing `on_failure_callback`).

---

## Scenario 5: pipeline-auditor — Missing idempotency flagged as High

**Command:** `/pipeline-audit etl/load_orders.py`
**Input:** Python ETL script with `INSERT INTO orders SELECT ...` (raw insert, no deduplication)
**Expected:** Agent flags missing idempotency as High.
**Pass:** Report contains at least one High finding mentioning idempotency or "INSERT INTO without deduplication" with consequence stated.

---

## Scenario 6: dbt-reviewer — Directory mode, single aggregated report

**Command:** `/dbt-review models/`
**Input:** `models/` directory with 10 dbt model files
**Expected:** Agent reviews all 10 models, produces one ranked report with per-model findings grouped under each severity level.
**Pass:** Report covers all 10 models. Summary shows total count across all models plus a per-model breakdown.

---

## Scenario 7: dbt-reviewer — Hardcoded reference detected as Critical

**Command:** `/dbt-review models/marts/fct_orders.sql`
**Input:** dbt model containing `FROM production.public.orders` (hardcoded cross-database reference)
**Expected:** Agent flags hardcoded reference as Critical with inline alert.
**Pass:** Inline alert emitted before full report. Critical finding present in report with consequence stated ("breaks environment promotion").

---

## Scenario 8: dq-definer — No invented column names

**Command:** `/dq-define orders --framework dbt-tests`
**Input:** `orders` model exists in `models/marts/fct_orders.sql` with columns `order_id`, `customer_id`, `order_date`, `total_amount`, `status`
**Expected:** Generated check stubs reference only `order_id`, `customer_id`, `order_date`, `total_amount`, `status`. No invented columns.
**Pass:** Every column referenced in the generated YAML exists in the actual model. No column named `created_at`, `updated_at`, or any other non-existent field appears.

---

## Scenario 9: dq-definer — Confirmation required before write

**Command:** `/dq-define payments --framework soda`
**Input:** `payments` model exists
**Expected:** Agent presents full draft, does NOT write until user says "yes" or "confirm".
**Pass:** Running the command produces a draft. No file is written to `data-quality/` until explicit confirmation. After "confirm", file is written to `data-quality/payments-checks.yml`.

---

## Scenario 10: contract-generator — DCS v2.3.0 YAML validity

**Command:** `/data-contract orders --producer orders-service --consumer analytics-warehouse`
**Input:** `orders` model with known schema
**Expected:** YAML output conforms to DCS v2.3.0 structure (required fields present, UUID v4 id, quality block present).
**Pass:** Generated YAML contains `dataContractSpecification: "2.3.0"`, valid UUID in `id`, all required fields present, at least one check in `quality` block.

---

## Scenario 11: contract-generator — PII detected and confirmed before writing

**Command:** `/data-contract users --producer auth-service --consumer analytics-warehouse`
**Input:** `users` table with columns `user_id`, `email`, `phone`, `first_name`, `created_at`
**Expected:** `email` and `phone` classified as confirmed PII (no question). `first_name` flagged as probable PII — one grouped question asked before drafting.
**Pass:** Agent groups probable PII candidates into one question. Does not ask once per column. Contract draft marks `email` and `phone` as `pii: true, classification: restricted` without requiring confirmation for those.

---

## Scenario 12: lineage-reader — Full dbt upstream/downstream tree

**Command:** `/lineage fct_orders`
**Input:** `target/manifest.json` present, `fct_orders` node exists in manifest with 3 upstream models and 2 downstream exposures
**Expected:** Report shows complete upstream tree (sources → intermediates → fct_orders) and downstream tree (fct_orders → exposures), with depth counts.
**Pass:** Upstream tree shows all 3 upstream nodes at correct depths. Downstream tree shows 2 exposures. Lineage depth count is accurate.

---

## Scenario 13: lineage-reader — Critical path finding

**Command:** `/lineage`
**Input:** `target/manifest.json` where `int_order_items` has no `schema.yml` entry and is depended on by 5 downstream models
**Expected:** Report identifies `int_order_items` as a critical path node with a High finding.
**Pass:** Report contains a High finding for `int_order_items` citing "undocumented, untested node in critical path" and "depended on by 5 downstream models".

---

## Scenario 14: naming-validator — Blocklist abbreviations detected

**Command:** `/naming models/staging/`
**Input:** `models/staging/` contains a model `stg_payments.sql` with column aliases `dt`, `amt`, `flg_active`
**Expected:** Agent flags `dt` (Medium), `amt` (Medium), `flg_active` (Medium — `flg` prefix not `is_`/`has_`).
**Pass:** Report contains Medium findings for each blocklist violation with specific column locations and suggested alternatives.

---

## Scenario 15: naming-validator — dbt prefix violation

**Command:** `/naming models/`
**Input:** `models/` contains `customer_lifetime_value.sql` (no `stg_`, `int_`, `mart_`, `rpt_`, `fct_`, or `dim_` prefix)
**Expected:** Agent flags missing dbt prefix as High.
**Pass:** Report contains a High finding for `customer_lifetime_value` with consequence "breaks cross-project discoverability".

---

## Scenario 16: naming-validator — 50+ models, all validated

**Command:** `/naming models/`
**Input:** `models/` directory with 55 dbt model files
**Expected:** Agent validates all 55 models — does not sample.
**Pass:** Report summary references all 55 models validated. No sampling or truncation.

---

## Scenario 17: data-critic — At least one finding per dimension

**Command:** `/data-critique docs/contracts/orders.md`
**Input:** A well-designed data contract with no obvious flaws
**Expected:** Agent produces at least one finding in each of the 6 dimensions (hidden assumptions, failure modes, missing constraints, scale cliff, operability, contract gap).
**Pass:** Report contains non-empty content under all 6 dimension sections. "No issues found" does not appear in any section. "Most Critical Concern" callout is present.

---

## Scenario 18: data-critic — Rejects path traversal

**Command:** `/data-critique ../../etc/passwd`
**Input:** Path containing `..`
**Expected:** Agent rejects the input immediately.
**Pass:** Agent responds "Invalid input: path traversal detected." and produces no critique output.

---

## Scenario 19: No agent writes without confirmation — dq-definer

**Command:** `/dq-define orders --framework great-expectations`
**Action:** Run command. Observe draft. Do NOT confirm. Close session.
**Expected:** No file written to `data-quality/` after the session.
**Pass:** `find data-quality/ -name "orders*"` returns no results after an unconfirmed session.

---

## Scenario 20: No agent writes without confirmation — contract-generator

**Command:** `/data-contract orders --producer orders-service --consumer analytics`
**Action:** Run command. Observe draft. Do NOT confirm. Close session.
**Expected:** No files written to `docs/contracts/` after the session.
**Pass:** `find docs/contracts/ -name "orders*"` returns no results after an unconfirmed session.

---

## Scenario 21: Framework ambiguity — agent asks one question

**Command:** `/pipeline-audit src/etl/`
**Input:** Directory with `.py` files, no framework markers (`dbt_project.yml`, `from airflow`, `@flow`, `SparkSession` all absent)
**Expected:** Agent asks exactly one question about the framework and waits.
**Pass:** Agent output contains exactly one question. Agent does not proceed to audit before receiving an answer.

---

## Scenario 22: Schema format ambiguity — agent asks one question

**Command:** `/schema-review src/data/schema.json`
**Input:** `.json` file that could be JSON Schema or Avro (no `"$schema"` or `"type": "record"` at top level — ambiguous)
**Expected:** Agent asks exactly one question about the format and waits.
**Pass:** Agent output contains exactly one question. Agent does not proceed to review before receiving an answer.

---

## Scenario 23: data-critic — Leads with opinionated recommendation citing DATAMODEL-D-* rule

**Command:** `/data-critique`
**Input:** Inline description: "We are designing an orders table. It will be a transactional OLTP workload. Reads and writes are roughly equal. Entity relationships are normalized. Expected volume is 5 million rows at 1x scale."
**Expected:** Agent emits a `## Modeling Recommendations` section BEFORE the `## Data Architecture Critique` section. Under DATAMODEL-1 (Store Type), the recommendation is labeled `**Recommendation:**` and names a concrete technology (e.g. PostgreSQL). The rule citation states "defaults apply (no DATAMODEL-D-N rule fired)" because no workload constraint triggers a derivation rule. At least one named alternative is provided. An override hook is present. The critique section follows after recommendations.
**Pass:** Output contains `## Modeling Recommendations` before `## Data Architecture Critique`. Under DATAMODEL-1, the word `**Recommendation:**` appears explicitly. Rule citation mentions "defaults apply". At least one alternative is named. Override hook is present. Critique section contains all 6 dimensions with at least one finding each.

---

## Scenario 24: data-critic — Write-heavy workload flips store-type recommendation via DATAMODEL-D-2

**Command:** `/data-critique`
**Input:** Inline description: "We are ingesting 50,000 IoT sensor events per second into a central events table. The workload is 95% writes — downstream analytics consumers read the data in batch queries once per hour. We need sub-second write throughput."
**Expected:** Agent emits `## Modeling Recommendations` first. Under DATAMODEL-1 (Store Type), the recommendation is NOT PostgreSQL (the default) — instead it recommends a wide-column store (e.g. Cassandra or ScyllaDB) or a time-series store (e.g. TimescaleDB). The rule citation explicitly cites DATAMODEL-D-2 (write-to-read ratio exceeds 80% writes / high-frequency event ingestion) as the reason the default is overridden. The PostgreSQL default is mentioned as the alternative that was displaced, not as the recommendation. The critique section follows with all 6 dimensions.
**Pass:** Output contains `## Modeling Recommendations` before `## Data Architecture Critique`. Under DATAMODEL-1, the recommendation is a non-relational or time-series store. The citation "DATAMODEL-D-2" appears in the recommendation block. PostgreSQL (or "relational") appears as the alternative or displaced default, not as the recommendation.

## Scenario 25: migration-planner — rename becomes expand-contract

**Input:** `/migration-plan "rename users.email to email_address"` on a large Postgres table.
**Expected:** Agent refuses an in-place `RENAME COLUMN` and produces a phased expand-contract plan (add new column → dual-write + batched backfill → switch reads → drop old), with per-phase lock/downtime risk and reversibility, and a point-of-no-return CAUTION on the drop.
**Pass:** No in-place rename is recommended; the plan has distinct expand and contract phases; the contract (drop) phase is flagged as point-of-no-return with a paired rollback note.

## Scenario 26: migration-planner — add NOT NULL without a blocking lock

**Input:** `/migration-plan "add NOT NULL to orders.tenant_id"` on a populated Postgres table.
**Expected:** Agent recommends `ADD CONSTRAINT ... CHECK (tenant_id IS NOT NULL) NOT VALID` → batched throttled backfill → `VALIDATE CONSTRAINT`, avoiding a long table lock.
**Pass:** The plan avoids a blocking full-table rewrite; uses NOT VALID → VALIDATE (or the engine equivalent); the backfill is explicitly batched/idempotent and reversible steps state their rollback.

---

## Success Criteria Mapping

| Spec criterion | Covered by scenario |
|---|---|
| 1. /schema-review accepts SQL DDL, Avro, Protobuf, JSON Schema, dbt YAML without format spec | 1, 2, 3 |
| 2. /pipeline-audit detects framework automatically | 4 |
| 3. /dbt-review on models/ produces single aggregated report | 6 |
| 4. /dq-define generates stubs referencing only existing columns | 8 |
| 5. /data-contract produces DCS v2.3.0-valid YAML | 10 |
| 6. /lineage on dbt manifest produces complete upstream/downstream tree | 12 |
| 7. /naming detects all blocklist violations across 50+ models | 14, 15, 16 |
| 8. /data-critique always produces finding in every dimension | 17 |
| 9. No agent writes without explicit confirmation | 9, 19, 20 |
| 10. No agent assumes tech stack without reading project files | 21, 22 |
| 11. /data-critique leads with opinionated recommendation citing DATAMODEL-D-* rule | 23 |
| 12. /data-critique flips default recommendation when workload constraint triggers DATAMODEL-D-2 | 24 |
| 13. /migration-plan produces a zero-downtime expand-contract plan; never in-place rename/type change; contract phase flagged point-of-no-return | 25, 26 |
