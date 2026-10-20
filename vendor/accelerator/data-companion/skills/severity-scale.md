---
name: severity-scale
description: |
  Apply before rating any finding in a data engineering review report. Defines Critical / High / Medium / Low / Info with data-engineering-specific examples and escalation rules. Used by schema-reviewer, pipeline-auditor, dbt-reviewer, naming-validator.
---

# Severity Scale — Data Engineering

## Levels

### Critical

**Definition:** The finding will cause data loss, silent data corruption, pipeline failure, or environment-breaking behaviour in normal production conditions. Do not leave as-is.

**Examples (data engineering):**
- Missing primary key on a fact table — duplicate rows cannot be detected or removed
- Nullable foreign key on a dimension join — silent NULLs fan out to every downstream aggregate
- Hardcoded `database.schema.table` reference in dbt SQL — breaks in every environment except the one it was written on
- Implicit type coercion that silently truncates data (e.g. FLOAT cast to INT on a currency column)
- Non-idempotent pipeline step with no deduplication — re-run doubles the data

**Escalation rule:** Emit an inline alert immediately upon discovery: "⚠ CRITICAL FOUND: [location] — [one-line summary] — continuing review." Include the finding again in its ranked position in the final report.

### High

**Definition:** The finding will cause incorrect behaviour, data exposure, or pipeline degradation under realistic but non-constant conditions. Address before next release.

**Examples (data engineering):**
- Missing error handling on external API call or database write — silent failure on transient error
- dbt model with no `schema.yml` entry — undocumented, untested, invisible to governance
- Non-idempotent step that might double-count under realistic retry conditions
- dbt prefix violation (`stg_`/`int_`/`mart_`/`rpt_`) — breaks cross-project discoverability
- Undocumented, untested model that is depended on by 3+ downstream models (critical lineage path)
- Missing freshness configuration on a source used by time-sensitive reporting models

### Medium

**Definition:** A quality, maintainability, or latent-risk issue that does not cause immediate harm but will make future failures more likely or harder to diagnose.

**Examples (data engineering):**
- Unbounded full-table scan on a large table — will fail or degrade at scale
- Blocklisted column abbreviation (`dt`, `amt`, `qty`, `num`, `val`, `flg`, `cd`, `id` standalone) — naming debt
- Missing row count anomaly check on a key model — silent load failures go undetected
- Boolean column not prefixed `is_`/`has_` — ambiguous meaning at scale
- Timestamp column not suffixed `_at`; date column not suffixed `_date`
- Ephemeral materialization on a model referenced by multiple downstream models

### Low

**Definition:** A minor issue or code smell with limited consequence in practice.

**Examples (data engineering):**
- Inconsistent casing in SQL keywords (cosmetic)
- TODO comment referencing a known gap not yet addressed
- Column description present but generic ("the column value") — not useful but not harmful
- Unused source definition in `sources.yml`

### Info

**Definition:** An observation worth recording that is not a defect. May reveal a pattern when aggregated.

**Examples (data engineering):**
- A model is growing in column count in a direction that will require splitting
- A source is referenced in only one model — could be inlined as a seed
- A naming pattern that is harmless today but will become confusing at 100+ models

---

## Escalation Rules

1. **Any Critical finding → report immediately.** Surface it as soon as found, not at the end of the review.
2. **Critical findings set overall verdict to BLOCK.** No exceptions.
3. **High or Medium only → PASS WITH WARNINGS.**
4. **Low/Info only or no findings → PASS.**
5. **Three Info findings of the same type → escalate to Medium.** Note the pattern explicitly.

---

## DO NOT Rules

- DO NOT downgrade a Critical to avoid blocking a release — if the failure mode exists, the severity stands
- DO NOT upgrade a Low to High to make a report look more thorough
- DO NOT omit the Summary block — total count and verdict are required
- DO NOT skip the escalation rule for Critical findings
