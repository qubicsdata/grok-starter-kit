---
name: reconciliation-craft
description: |
  Import when authoring or executing a reconciliation suite for SAP migration objects.
  Triggers on: "recon suite", "hash total", "row count comparison", "financial integrity check",
  "BSEG", "ACDOCA", "ECC vs S/4", "mismatch triage", "synthetic self-test", "landing to bronze",
  "silver to gold recon". Read before generating any suite SQL or interpreting recon results.
contract_version: 1.0.0
---

# Reconciliation Craft

Generative expertise for SAP migration reconciliation across all five layer transitions. Consumed by
recon-designer when producing a suite and by recon-runner when classifying results. Every suite
choice leads with a default and carries the rule that produced it.

## Section 1 — Decision Domains

| ID prefix | Decision domain | The decision being made |
|-----------|-----------------|-------------------------|
| `RECON-CHK` | Check selection | Which check runs at which layer transition |
| `RECON-TOL` | Tolerance policy | What delta, if any, is an acceptable pass |
| `RECON-FLAVOR` | Source flavor binding | Whether a suite targets ECC or S/4HANA table shapes |
| `RECON-TEST` | Self-test posture | What proves the recon logic itself is correct before it touches real data |
| `RECON-TRIAGE` | Failure classification | How a failure is coded, and whether it blocks wave advancement |

## Section 2 — Constraint Inputs

| Brief dimension | Drives | How |
|-----------------|--------|-----|
| Layer transition (landing→bronze … gold→outbound) | `RECON-CHK` | Each transition has a designated check ladder |
| Object domain (financial vs non-financial) | `RECON-TOL` | Financial objects admit no tolerance |
| `sap_product` in `config/systems.yaml` | `RECON-FLAVOR` | Selects ECC (BKPF/BSEG) vs S/4 (ACDOCA) table shapes |
| Cluster-table involvement (BSEG, KONV, MSEG, CDPOS) | `RECON-FLAVOR`, `RECON-CHK` | Forbids `SELECT *`; forces ODP key-column extraction |
| Row volume | `RECON-CHK` | Sets whether hash total runs on full set or partitioned |
| Wave gate posture | `RECON-TRIAGE` | Determines which failure codes block advancement |

## Section 3 — Opinionated Defaults

Check ladder by layer transition: landing→bronze runs row count; bronze→silver runs row count then
hash total; silver→gold runs financial integrity; gold→outbound runs referential completeness.
Every suite opens with the CI self-test.

### Row Count Recon Pattern

**Use for:** landing → bronze, bronze → silver (first check).

```sql
-- Row count comparison: source vs target
WITH counts AS (
  SELECT
    'source' AS side,
    COUNT(*) AS row_count
  FROM <source_table>
  UNION ALL
  SELECT
    'target' AS side,
    COUNT(*) AS row_count
  FROM <target_table>
)
SELECT
  MAX(CASE WHEN side = 'source' THEN row_count END) AS source_count,
  MAX(CASE WHEN side = 'target' THEN row_count END) AS target_count,
  MAX(CASE WHEN side = 'source' THEN row_count END)
    - MAX(CASE WHEN side = 'target' THEN row_count END) AS delta,
  CASE
    WHEN MAX(CASE WHEN side = 'source' THEN row_count END)
       = MAX(CASE WHEN side = 'target' THEN row_count END)
    THEN 'PASS'
    ELSE 'FAIL'
  END AS result
FROM counts;
```

**Tolerance:** Zero for financial objects. No acceptable discard. Any delta = FAIL.

---

### Hash Total Pattern

**Use for:** bronze → silver (second check, after row count passes).

```sql
-- SHA2 hash total: deterministic cross-system comparison
WITH source_hashes AS (
  SELECT SHA2(CONCAT_WS('|', <key_cols>, <value_cols>), 256) AS row_hash
  FROM <source_table>
),
target_hashes AS (
  SELECT SHA2(CONCAT_WS('|', <key_cols>, <value_cols>), 256) AS row_hash
  FROM <target_table>
)
SELECT
  COUNT(s.row_hash) AS source_hash_count,
  COUNT(t.row_hash) AS target_hash_count,
  SUM(CASE WHEN t.row_hash IS NULL THEN 1 ELSE 0 END) AS missing_in_target,
  SUM(CASE WHEN s.row_hash IS NULL THEN 1 ELSE 0 END) AS extra_in_target,
  CASE
    WHEN SUM(CASE WHEN t.row_hash IS NULL THEN 1 ELSE 0 END) = 0
     AND SUM(CASE WHEN s.row_hash IS NULL THEN 1 ELSE 0 END) = 0
    THEN 'PASS'
    ELSE 'FAIL'
  END AS result
FROM source_hashes s
FULL OUTER JOIN target_hashes t ON s.row_hash = t.row_hash;
```

**Note on ordering:** CONCAT_WS must use the same column order on both sides. Agree on column
order in the suite header comment.

---

### Financial Integrity Checks

**Use for:** silver → gold.

### 3a. Trial Balance (GL Documents)

```sql
-- Trial balance: debit = credit per company code + fiscal year + period
SELECT
  bukrs,
  gjahr,
  monat,
  SUM(CASE WHEN shkzg = 'S' THEN dmbtr ELSE 0 END) AS total_debit,
  SUM(CASE WHEN shkzg = 'H' THEN dmbtr ELSE 0 END) AS total_credit,
  CASE
    WHEN SUM(CASE WHEN shkzg = 'S' THEN dmbtr ELSE 0 END)
       = SUM(CASE WHEN shkzg = 'H' THEN dmbtr ELSE 0 END)
    THEN 'PASS'
    ELSE 'FAIL'
  END AS result
FROM <gl_table>
GROUP BY bukrs, gjahr, monat
HAVING result = 'FAIL';
-- Zero rows = PASS; any row = FAIL
```

### 3b. Open-Item Balance

```sql
-- Open item balance: outstanding receivables/payables match source open-item report
SELECT
  lifnr_or_kunnr,
  bukrs,
  SUM(dmbtr * CASE WHEN shkzg = 'S' THEN 1 ELSE -1 END) AS open_balance,
  '<expected_value>' AS expected_balance,
  CASE
    WHEN ABS(SUM(dmbtr * CASE WHEN shkzg = 'S' THEN 1 ELSE -1 END) - CAST('<expected_value>' AS DECIMAL(18,2))) < 0.01
    THEN 'PASS'
    ELSE 'FAIL'
  END AS result
FROM <open_item_table>
GROUP BY lifnr_or_kunnr, bukrs;
```

### 3c. Document Completeness (ECC: BKPF/BSEG)

```sql
-- Every BKPF header must have at least one BSEG line item
-- NOTE: NEVER SELECT * on BSEG — this is a cluster table. Use key extraction only.
SELECT
  bkpf.mandt, bkpf.bukrs, bkpf.belnr, bkpf.gjahr,
  CASE
    WHEN COUNT(bseg.buzei) = 0 THEN 'FAIL'
    ELSE 'PASS'
  END AS result
FROM bronze.<sys>_ecc_bkpf bkpf
LEFT JOIN bronze.<sys>_ecc_bseg bseg  -- extracted via ODP, key columns only
  ON  bseg.mandt = bkpf.mandt
  AND bseg.bukrs = bkpf.bukrs
  AND bseg.belnr = bkpf.belnr
  AND bseg.gjahr = bkpf.gjahr
GROUP BY bkpf.mandt, bkpf.bukrs, bkpf.belnr, bkpf.gjahr
HAVING result = 'FAIL';
-- Zero rows = PASS
```

### 3d. Document Completeness (S/4: ACDOCA)

```sql
-- ACDOCA is the universal journal — single select, every entry must balance
SELECT
  rldnr, rbukrs, gjahr, belnr,
  SUM(HSL) AS net_amount,
  CASE
    WHEN ABS(SUM(HSL)) < 0.01 THEN 'PASS'
    ELSE 'FAIL'
  END AS result
FROM gold.finance.acdoca
GROUP BY rldnr, rbukrs, gjahr, belnr
HAVING result = 'FAIL';
-- Zero rows = PASS
```

---

### Gold → Outbound: Document Completeness Check

```sql
-- All expected FK references resolve (e.g., every document references a valid business partner)
SELECT
  doc.document_key,
  'missing_business_partner' AS failure_type
FROM gold.<domain>.<object_table> doc
LEFT JOIN gold.masterdata.business_partner bp
  ON bp.partner_id = doc.partner_id
WHERE bp.partner_id IS NULL
LIMIT 1000;
-- Zero rows = PASS
```

---

### ECC vs S/4 Flavor Rules

| Object | ECC Tables | S/4 Tables | Caveat |
|--------|-----------|------------|--------|
| GL Documents | BKPF (header) + BSEG (line) | ACDOCA | NEVER SELECT * on BSEG — cluster table; use ODP extraction, key columns only |
| Material Documents | MKPF (header) + MSEG (line) | MATDOC | MSEG is also cluster — same ODP restriction |
| Customer Invoices | VBRK + VBRP | VBRK + VBRP | Same in S/4 |
| Purchasing Docs | EKKO + EKPO | EKKO + EKPO | KONV is cluster — NEVER SELECT * |

Detection: read `sap_product` from `config/systems.yaml` for each system.
- `ECC` or `ecc` → use ECC tables
- `S4` or `S/4HANA` or `s4hana` → use S/4 tables
- `unknown` → generate ECC variant + emit WARNING; flag for re-run after profiling

---

### Synthetic Data Self-Test Structure

Every suite MUST start with this pattern (labeled `-- CI self-test (run first)`):

```sql
-- CI self-test (run first)
-- Purpose: verify recon logic is correct before running on real data.
-- If this block fails, the recon logic has a bug — do not proceed to real data.

WITH synthetic_source AS (
  SELECT
    'TEST001' AS document_key,
    'S'       AS shkzg,
    25000.00  AS dmbtr,
    'CC01'    AS bukrs,
    '2025'    AS gjahr,
    '03'      AS monat
  UNION ALL SELECT 'TEST002', 'H', 25000.00, 'CC01', '2025', '03'
  -- Add more rows to reach known totals: 100 rows, Σdebit = 50000.00, Σcredit = 50000.00
),
synthetic_target AS (
  SELECT * FROM synthetic_source  -- identical copy for baseline pass case
),
self_test_result AS (
  SELECT
    SUM(CASE WHEN shkzg = 'S' THEN dmbtr ELSE 0 END) AS total_debit,
    SUM(CASE WHEN shkzg = 'H' THEN dmbtr ELSE 0 END) AS total_credit
  FROM synthetic_source
)
SELECT
  CASE
    WHEN total_debit = 50000.00 AND total_credit = 50000.00
    THEN 'SELF-TEST PASS'
    ELSE RAISE_ERROR('CI self-test FAILED: recon logic is wrong — do not proceed to real data')
  END AS self_test_verdict
FROM self_test_result;
```

Adapt `synthetic_source` to the actual object's key and value columns. The known totals must be
pre-computed and hard-coded in the test. If the real recon logic cannot reproduce them, it has a bug.

---

### Mismatch Triage Taxonomy

When a recon fails, classify the failure before recording it in mismatch_detail:

| Code | Meaning | Severity | Action |
|------|---------|----------|--------|
| `MISSING_SOURCE` | Rows in source, not in target | CRITICAL — data loss | Investigate pipeline drop; block wave advancement |
| `EXTRA_TARGET` | Rows in target, not in source | CRITICAL — data fabrication | Investigate pipeline insert; block wave advancement |
| `VALUE_DRIFT` | Row exists in both, key value differs | HIGH — corruption | Identify transformation error; fix pipeline |
| `COUNT_DELTA` | Counts differ; hash needed to classify | MEDIUM — unknown loss or fabrication | Run hash total immediately |

Use these codes verbatim in `mismatch_detail` field of migration_meta.recon_results.

---

## Section 4 — Derivation Rules

- `RECON-D-1`: When the transition is landing→bronze, choose row count alone because at that boundary only completeness is claimed, not transformation correctness.
- `RECON-D-2`: When the transition is bronze→silver, choose row count first and hash total second because a count match is cheap and a hash is only meaningful once cardinality agrees.
- `RECON-D-3`: When the transition is silver→gold, choose financial integrity checks because gold is the layer business users reconcile against, and balance is the property they check.
- `RECON-D-4`: When the transition is gold→outbound, choose referential completeness because the receiving system rejects documents whose foreign keys do not resolve.
- `RECON-D-5`: When the object is financial, choose zero tolerance because any debit/credit imbalance is a defect, never an acceptable discard.
- `RECON-D-6`: When a hash total is built, choose an identical column order on both sides and state it in the suite header because ordering drift silently produces total mismatch.
- `RECON-D-7`: When `sap_product` reads ECC, choose the BKPF/BSEG shape; when it reads S/4HANA, choose ACDOCA, because the universal journal replaces the header/line split.
- `RECON-D-8`: When `sap_product` is unknown, choose the ECC variant and emit a warning flagged for re-run after profiling, because guessing S/4 silently produces an empty result rather than a visible failure.
- `RECON-D-9`: When a cluster table (BSEG, KONV, MSEG, CDPOS) is in scope, choose ODP key-column extraction because `SELECT *` against a cluster table is not a supported read path.
- `RECON-D-10`: When any suite is generated, choose to prepend the CI self-test because a suite that has never proven itself on known totals cannot be trusted on unknown data.
- `RECON-D-11`: When counts differ, choose to run the hash total before recording a verdict because a raw count delta cannot distinguish loss from fabrication.
- `RECON-D-12`: When a failure is classified `MISSING_SOURCE` or `EXTRA_TARGET`, choose to block wave advancement because data loss and data fabrication are both disqualifying at a wave gate.

## Section 5 — Recommendation Output Contract

Every recon recommendation MUST surface: the chosen check and tolerance, the `RECON-D-*` rule ID(s)
that produced it, at least one named alternative, and an override hook.

Every generated suite MUST carry: a header comment stating object, system, layer transition, source
flavor and the agreed column order; the CI self-test block labeled `-- CI self-test (run first)`;
the layer-appropriate checks; and a verdict column emitting `PASS` or `FAIL` per check. Results are
recorded to `migration_meta.recon_results`, with failures coded verbatim from the triage taxonomy in
the `mismatch_detail` field.

**Override hook.** A user may override check selection per transition, hash partitioning strategy,
and the open-item comparison threshold by naming them in the suite request. Four defaults are not
overridable, because each turns a detectable defect into a silent one: zero tolerance on financial
objects (`RECON-D-5`); no `SELECT *` on cluster tables (`RECON-D-9`); the CI self-test is always
present (`RECON-D-10`); a count delta is never passed without hash classification (`RECON-D-11`).
When a request would violate one, refuse it, name the rule, and present a compliant alternative.

## Section 6 — Enforcement Handoff

reconciliation-craft output is validated by cutover-gate-spec (a wave advances only when every
object's recon verdict is recorded and passing) and persisted through migration-state-spec (verdicts
and mismatch codes are read back from migration_meta, never asserted from memory). Source-flavor
bindings are cross-checked against ecc-s4-divergence-map. Any check, tolerance, or flavor binding
that deviates from its cited `RECON-D-*` rule without an explicit user override is a finding.
