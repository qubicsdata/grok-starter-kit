---
name: cost-strategy-craft
description: |
  Budget threshold setting, alert strategy, model-tier routing, optimization action selection, and cost-attribution granularity expertise. Consumed by budget-alerter when making advisory recommendations about spend control.
---

# Cost Strategy Craft

## Section 1 — Decision Domains

- COST-1 Budget threshold calibration (daily / weekly / per-session / per-app limit values)
- COST-2 Alert strategy selection (burn-rate progressive vs. absolute hard-stop)
- COST-3 Model-tier routing policy (Haiku / Sonnet / Opus assignment per task class)
- COST-4 Optimization action selection (cache / batch / downgrade / rate-limit)
- COST-5 Cost-attribution granularity (app-level / feature-level / session-level / per-call)

## Section 2 — Constraint Inputs

- Daily spend velocity → COST-1 (fast-burning spend requires tighter thresholds), COST-2 (burn-rate strategy fires earlier warnings)
- Session count and variance → COST-1 (high session volume raises per-session limit risk), COST-4 (high volume favors batching or caching)
- Model mix in audit log → COST-3 (Opus-heavy mix is the primary cost lever), COST-4 (downgrade is highest-ROI action when Opus share > 20%)
- Per-app spend concentration → COST-1 (single app consuming > 60% share warrants per-app cap), COST-5 (concentrated spend justifies feature-level attribution)
- Budget.json presence → COST-1 (absent file means defaults apply — treat as uncalibrated), COST-2 (default thresholds assume low-volume exploratory use)
- Criticality of workflow → COST-3 (user-facing / latency-critical routes may not be downgradeable), COST-4 (rate-limiting only for non-critical background workflows)

## Section 3 — Opinionated Defaults

- COST-1: Set daily limit at 3× the trailing 7-day average daily spend; weekly at 5× average daily; per-session at 2× the median session cost. This provides a growth buffer without unconstrained spend.
- COST-2: Use burn-rate progressive alerting — warn at 70% of daily limit (not 80%) because burn-rate signals allow time to act before the absolute cap is hit; reserve hard-stop at 100%.
- COST-3: Route haiku for all classification, routing, extraction, and short-context summarization tasks; sonnet for multi-step reasoning and code tasks; opus only for architectural review or tasks explicitly flagged high-complexity. Default ratio target: ≤ 10% Opus, ≤ 50% Sonnet, ≥ 40% Haiku.
- COST-4: Apply prompt-caching first (zero latency cost); then batching for non-real-time tasks; then model downgrade; rate-limiting is the last resort and only for background tasks.
- COST-5: Attribute at feature level by default — per-call granularity adds log volume with limited incremental insight unless a single feature accounts for > 30% of spend.

## Section 4 — Derivation Rules

- COST-D-1: When daily spend velocity exceeds 50% of the daily limit before 14:00 UTC, choose burn-rate alert threshold of 60% (instead of default 70%) because front-loaded spend patterns will breach the absolute cap by end-of-day at the default trigger point.
- COST-D-2: When budgets.json is absent and defaults are in use, recommend setting explicit limits because default thresholds (daily=$10, weekly=$50) reflect low-volume exploratory use and will be silently insufficient for production workloads.
- COST-D-3: When Opus-model share of invocations exceeds 20% of weekly spend, choose model downgrade to Sonnet as the primary optimization action because Opus costs 5× Sonnet per token and most multi-step tasks do not require the quality delta.
- COST-D-4: When a single app accounts for > 60% of daily spend, choose per-app budget cap for that app because global limits mask the concentration and delay corrective action.
- COST-D-5: When session count per day exceeds 50, choose feature-level attribution over app-level because app-level aggregation loses the signal needed to identify the high-frequency feature driving cost.
- COST-D-6: When spend is under 40% of all budget limits and model mix is already Haiku-dominant (≥ 60%), recommend no optimization action and report COST_HEALTHY because further tuning risks degrading output quality for marginal savings.
- COST-D-7: When a workflow is user-facing (latency-sensitive) and Opus is the configured model, do not recommend downgrade; instead recommend batching or caching because latency constraints make model downgrade inadvisable even at elevated cost.

## Section 5 — Recommendation Output Contract

Every advisory output from budget-alerter that references this pack MUST surface:

1. The chosen value for each applicable Decision Domain (named threshold, strategy, model tier, action, granularity — never an abstract category).
2. The COST-D-* rule(s) that produced the recommendation, or "defaults apply (no derivation rule fired)" when no rule fired.
3. At least one named alternative with a brief rationale (e.g. "alternative: raise per-session limit to $3.00 if session variance is high").
4. An override hook — a concrete instruction for the implementer (e.g. "override COST-3 by setting `preferred_model` in .cost-monitor/budgets.json; document reason in ADR").

Consumers MUST NOT omit the rule citation or the override hook; omitting them makes the advisory unverifiable.

## Section 6 — Enforcement Handoff

cost-strategy-craft output is validated by budget-schema. Budget-schema enforces the hard gates: NEVER write to budgets.json (user-managed), NEVER treat missing budgets.json as an error, NEVER report BUDGET_OK when any threshold is at or above 100%. Any advisory recommendation that violates these gates is rejected at enforcement time.
