# Behavioral Scenarios — cost-monitor v1.0.0

Generated from agent contracts, hard gates, and anti-pattern probes defined in the spec and agent files.

Total: 13 scenarios (CA-01–06, BA-01–07)

---

## cost-attributor Scenarios (CA-01 – CA-06)

### CA-01 — Happy path: full cost report from audit log

**Input:** `/cost-report`. Audit log has 30 entries across 2 apps, 3 features, 2 sessions, 4 agents, 3 models.

**Expected behavior:**
- Reads audit.jsonl
- Reads pricing.json (or uses defaults)
- Computes cost per entry: (tokens_in × input_rate) + (tokens_out × output_rate)
- Aggregates by app, feature, session, plugin, agent, day
- Returns COST REPORT with all 6 breakdown sections

**Pass condition:** COST REPORT with all 6 sections. Totals are arithmetically consistent.

---

### CA-02 — Filter by app

**Input:** `/cost-report app=billing`. Entries for billing and payments in log.

**Expected behavior:** Report scoped to billing entries only.

**Pass condition:** Only billing entries in report. Total matches billing-only sum.

---

### CA-03 — Filter by period=today

**Input:** `/cost-report period=today`.

**Expected behavior:** Filters to entries where ts date matches today (UTC).

**Pass condition:** Only today's entries included.

---

### CA-04 — Missing audit log: informative message

**Input:** `/cost-report`. No audit.jsonl.

**Expected behavior:** `No audit log found at .ai-baseline/audit.jsonl. Run any ai-baseline-enabled agent first.`

**Pass condition:** Informative message. No crash.

---

### CA-05 — Unknown model: Sonnet rate estimate used

**Input:** Audit log contains entry with model="claude-unknown-model-x".

**Expected behavior:** Agent uses Sonnet rate ($0.000003/$0.000015) with note "Unknown model claude-unknown-model-x — using Sonnet rate estimate."

**Pass condition:** Entry costed at Sonnet rate. Note included. No crash.

---

### CA-06 — $ARGUMENTS injection in app filter

**Input:** `/cost-report app=../../etc`.

**Expected behavior:** Filter value used as grep pattern against app field. No file system traversal. Results for app matching the pattern (likely none).

**Pass condition:** No traversal. Report returned (possibly empty for that filter).

---

## budget-alerter Scenarios (BA-01 – BA-05)

### BA-01 — Happy path: all budgets under threshold

**Input:** `/budget-status`. Daily spend = $1.20. Daily limit = $10.00. Weekly = $3.50 / $50.00. Session max = $0.45 / $2.00.

**Expected behavior:** All budgets under 80% threshold. Returns `BUDGET_OK` with summary table.

**Pass condition:** BUDGET_OK with actual vs. limit for all configured budgets.

---

### BA-02 — Warning at 80%: BUDGET_WARNING emitted

**Input:** `/budget-status`. Daily spend = $8.10. Daily limit = $10.00 (81%).

**Expected behavior:** `BUDGET_WARNING: daily_usd at 81% ($8.10 / $10.00)`

**Pass condition:** BUDGET_WARNING with percentage, actual, and limit.

---

### BA-03 — Alert at 100%: BUDGET_ALERT emitted

**Input:** `/budget-status`. Daily spend = $10.50. Daily limit = $10.00 (105%).

**Expected behavior:** `BUDGET_ALERT: daily_usd exceeded ($10.50 / $10.00)`

**Pass condition:** BUDGET_ALERT with actual and limit.

---

### BA-04 — Per-app budget alert

**Input:** `/budget-status`. budgets.json has per_app.billing.daily_usd = $2.00. billing daily spend = $2.30.

**Expected behavior:** `BUDGET_ALERT: per_app.billing.daily_usd exceeded ($2.30 / $2.00)`

**Pass condition:** Per-app alert raised separately from global budget.

---

### BA-05 — Missing budgets.json: defaults used

**Input:** `/budget-status`. budgets.json does not exist.

**Expected behavior:** Uses defaults (daily=$10, weekly=$50, session=$2). Reports actual spend vs. defaults. Includes note "budgets.json not found — using defaults."

**Pass condition:** Report produced with defaults. Note present.

---

### BA-06 — Advisory leads with opinionated default citing COST-D-3

**Input:** `/budget-status`. Audit log for the week shows: 35% of invocations used claude-opus-4-8 (Opus share > 20% threshold). Daily spend = $4.20, daily limit = $10.00.

**Expected behavior:** budget-alerter leads with ADVISORY RECOMMENDATION block before the spend status table. The model-tier routing recommendation cites COST-D-3 ("Opus share > 20%"), names Sonnet as the recommended replacement, gives at least one named alternative ("keep Opus for architectural review tasks"), and includes an override hook ("set per-agent model in agent frontmatter and document"). Spend table shows OK. Overall: BUDGET_OK.

**Pass condition:** ADVISORY RECOMMENDATION block appears first. COST-D-3 is cited by ID. Named alternative present. Override hook present. No neutral "it depends" language.

---

### BA-07 — Constraint flips default alert threshold (COST-D-1 fires)

**Input:** `/budget-status`. Current time is 11:30 UTC. Daily spend = $5.20, daily limit = $10.00 (52% burn by 11:30 UTC — exceeds 50% before 14:00 UTC).

**Expected behavior:** budget-alerter fires COST-D-1 and recommends burn-rate alert threshold of 60% (tighter than the default 70%) with rationale "front-loaded spend patterns will breach the absolute cap by end-of-day at the default trigger point." Spend status shows WARNING (≥ 50% but < 80%, so OK under default thresholds, but advisory note calls out burn-rate risk). Override hook present.

**Pass condition:** ADVISORY RECOMMENDATION block cites COST-D-1 by ID. Recommended alert threshold is 60% (not the default 70%). Rationale explains burn-rate risk. Named alternative ("keep default 70% if spend is exploratory or front-loaded by design") present. Override hook present.

---
