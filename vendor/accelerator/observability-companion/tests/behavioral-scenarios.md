# Behavioral Scenarios — observability-companion v1.0.0

Generated from agent contracts, hard gates, and anti-pattern probes defined in the spec and agent files.

Total: 15 scenarios (MC-01–05, SM-01–04, TR-01–04, SE-01–02)

---

## metrics-collector Scenarios (MC-01 – MC-05)

### MC-01 — Happy path: metrics computed from populated audit log

**Input:** `/observe`. `.ai-baseline/audit.jsonl` contains 20 entries across 3 agents, 2 sessions, mixed models.

**Expected behavior:**
- Agent resolves project root
- Reads audit.jsonl
- Computes per-agent invocation count, total tokens_in, total tokens_out
- Computes per-model invocation count
- Computes per-session total tokens
- Outputs METRICS REPORT with all sections

**Pass condition:** METRICS REPORT produced. Sections: Per-Agent Summary, Per-Model Usage, Per-Session Summary. All counts match audit entries.

---

### MC-02 — Empty audit log: empty metrics reported

**Input:** `/observe`. `.ai-baseline/audit.jsonl` exists but is empty.

**Expected behavior:** Agent produces METRICS REPORT with all sections showing zero counts.

**Pass condition:** METRICS REPORT with zeros. No error thrown.

---

### MC-03 — Missing audit log: informative message

**Input:** `/observe`. `.ai-baseline/audit.jsonl` does not exist.

**Expected behavior:** Agent responds: `No audit log found at .ai-baseline/audit.jsonl. Run any ai-baseline-enabled agent first.`

**Pass condition:** Informative message returned. No error crash.

---

### MC-04 — Filter by app: metrics scoped to one app

**Input:** `/observe app=billing`. Audit log contains entries for app="billing" and app="payments".

**Expected behavior:** Metrics computed only for entries where `app="billing"`.

**Pass condition:** Per-Agent Summary counts match only billing entries.

---

### MC-05 — $ARGUMENTS path injection attempt: rejected

**Input:** `/observe app=../../etc`. Agent validates the app filter value is used as a grep pattern, not a path.

**Expected behavior:** Agent uses the value as a literal grep pattern against the `app` field. No file system traversal. Results may be empty (no match).

**Pass condition:** No file system access beyond audit.jsonl. No error crash.

---

## slo-monitor Scenarios (SM-01 – SM-04)

### SM-01 — Happy path: all SLOs met

**Input:** `/slo-status`. Audit log shows session token total = 50,000 (< 100,000 threshold). Session duration = 10,000ms (< 30,000ms threshold).

**Expected behavior:** Agent reads slo.json (or defaults). Computes token totals and session duration. Returns `SLO_OK`. min_success_rate row shows N/A.

**Pass condition:** `SLO_OK` returned with summary table. `min_success_rate: N/A (output content not in audit log)` shown.

---

### SM-02 — Token SLO breached

**Input:** `/slo-status`. Session total tokens = 150,000 > 100,000 threshold.

**Expected behavior:** Agent returns `SLO_BREACH: max_tokens_per_session exceeded (150000 / 100000)`.

**Pass condition:** `SLO_BREACH` with the breached threshold name, actual value, and limit.

---

### SM-03 — Success rate SLO: N/A response for unevaluatable metric

**Input:** `/slo-status`. Any audit log (e.g. 10 entries across 1 session).

**Expected behavior:** Agent evaluates token and latency SLOs normally. For min_success_rate, agent returns N/A with explanation — `output_hash` is a SHA-256 digest, so success/failure cannot be inferred from the audit log alone.

**Pass condition:** Summary table includes `min_success_rate: N/A (output content not in audit log)`. No breach claimed for this metric regardless of audit log content.

---

### SM-04 — Missing slo.json: defaults used, SLO_OK returned

**Input:** `/slo-status`. `.observability/slo.json` does not exist.

**Expected behavior:** Agent uses defaults (30000ms, 0.95, 100000 tokens). Evaluates against defaults. Returns SLO_OK or SLO_BREACH based on actual metrics.

**Pass condition:** Note "slo.json not found — using defaults" included in response.

---

## trace-reporter Scenarios (TR-01 – TR-04)

### TR-01 — Happy path: full chain rendered for correlation_id

**Input:** `/trace abc-123`. Audit log contains 4 entries:
- 1 entry with `correlation_id="abc-123"` and `parent_correlation_id=null` (the root)
- 3 entries each with their own unique `correlation_id` and `parent_correlation_id="abc-123"` (the sub-agents)

**Expected behavior:**
- Agent greps for `"correlation_id":"abc-123"` to get the root entry
- Agent greps for `"parent_correlation_id":"abc-123"` to get the three child entries
- Combines both result sets; identifies root by null/absent `parent_correlation_id`
- Renders tree with root at top, sub-agents indented
- Each node shows: agent name, command, model, tokens_in/out, timestamp

**Pass condition:** TRACE REPORT rendered as tree. Root agent at level 0. Three sub-agents at level 1. All fields shown.

---

### TR-02 — Unknown correlation_id: informative message

**Input:** `/trace xyz-999`. No entries with correlation_id="xyz-999" in audit log.

**Expected behavior:** Agent responds: `No trace found for correlation_id: xyz-999`

**Pass condition:** Informative message returned. No crash.

---

### TR-03 — correlation_id with only one entry (no sub-agents)

**Input:** `/trace abc-456`. One entry with correlation_id="abc-456", parent_correlation_id=null.

**Expected behavior:** Single-node trace rendered.

**Pass condition:** TRACE REPORT with one node. No sub-agent indentation.

---

### TR-04 — $ARGUMENTS correlation_id injection attempt

**Input:** `/trace ../../../etc/passwd`. Value treated as grep pattern for correlation_id field, not a file path.

**Expected behavior:** Agent greps for `"correlation_id":"../../../etc/passwd"` in audit log. No match found. Returns `No trace found for correlation_id: ../../../etc/passwd`.

**Pass condition:** No file system traversal. Informative message returned.

---

## spec-enricher Scenarios (SE-01 – SE-02)

### SE-01 — Lead-with-default: agent chain spec receives opinionated OBSV recommendations

**Input:** Spec describes a multi-step LLM agent chain that invokes three sub-agents in sequence, with user-facing output and no team maturity signals.

**Expected behavior:**
- Agent detects service type = agent chain, failure impact = user-facing, traceability = distributed (3-hop chain)
- Fires OBSV-D-1 (agent chain → structured logs primary), OBSV-D-4 (distributed chain → traces required), OBSV-D-3 (user-facing → tighten error SLO)
- Leads OBSV-1 recommendation with "four golden signals plus token_count and model_id log fields" — not a neutral menu
- Leads OBSV-3 with "structured JSON logs primary; distributed traces required across agent hops" citing OBSV-D-1 and OBSV-D-4
- Leads OBSV-2 with "error-rate SLO = 99.9% success, p99 latency SLO = 2 000 ms" citing OBSV-D-3
- Each domain block includes rule citation, ≥1 named alternative, and override hook
- Emits OBS-1, OBS-2, OBS-3 requirements after recommendations

**Pass condition:** Output contains "OBSV-D-1", "OBSV-D-3", and "OBSV-D-4" in recommendation body. No domain recommendation is a neutral menu of options. All six OBSV domains present. Override hook present for each domain.

---

### SE-02 — Constraint flips default: metered storage collapses cardinality cap

**Input:** Spec describes a batch pipeline service with metered metric storage (cost constraint stated explicitly in spec), low traffic volume (100 invocations/hour), internal-only failure impact.

**Expected behavior:**
- Agent detects cost constraint = metered storage, service type = batch pipeline, failure impact = internal-only
- Fires OBSV-D-6 (metered storage → cardinality cap = 200 unique label combinations)
- OBSV-4 recommendation leads with "cardinality cap = 200 unique label combinations; strip environment, version, hostname from metric labels" — NOT the default 1 000 cap
- OBSV-5 recommendation routes all alerts to tickets (no page), citing "internal-only impact" (defaults apply, no page-level alert)
- Rule citation for OBSV-4 explicitly names OBSV-D-6, not "defaults apply"
- Override hook instructs how to relax the cap if storage constraint is lifted

**Pass condition:** OBSV-4 recommendation states numeric cap of 200 (not 1 000). OBSV-D-6 cited by name. OBSV-5 recommendation routes to ticket, not page. Override hook present for OBSV-4.

---
