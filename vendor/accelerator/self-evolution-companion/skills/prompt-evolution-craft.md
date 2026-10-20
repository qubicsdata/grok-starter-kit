---
name: prompt-evolution-craft
description: Prompt-improvement prioritization and change-vs-defer expertise. Consumed by prompt-refiner when deciding which dimension to target, what change to propose, and whether to defer. Encodes opinionated defaults so every recommendation is defensible and overridable.
---

# Prompt Evolution Craft

## Section 1 — Decision Domains

- EVOL-1 Improvement target selection (which agent dimension to address when multiple dimensions score below threshold)
- EVOL-2 Change-vs-defer judgment (whether to propose a change now or defer pending more evidence)
- EVOL-3 Rollout scope (surgical single-section patch vs. broader restructure of the agent system prompt)

## Section 2 — Constraint Inputs

- Weakest dimension score → EVOL-1 (lowest average score across the last window names the target; tie-breaks by worst-outcome risk: safety < accuracy < completeness)
- Number of feedback entries for the agent → EVOL-2 (fewer than 5 entries → defer; 5–9 entries → cautious patch; 10+ entries → confident patch or restructure)
- Score delta trend (improving/stable/declining over last 5 entries vs. prior) → EVOL-2 (improving trend → defer; stable or declining → act)
- Dimension gap magnitude (threshold – actual) → EVOL-3 (gap ≤ 2 points → surgical patch to one section; gap > 2 points on two or more dimensions → structured restructure)
- Agent model tier (haiku/sonnet/opus) → EVOL-3 (haiku agents get compact patches ≤ 5 lines; opus agents tolerate larger instruction additions)

## Section 3 — Opinionated Defaults

- EVOL-1: When multiple dimensions score below 7.0, **target safety first, accuracy second, completeness last**. Safety defects are user-facing risks; accuracy defects corrupt downstream state; completeness defects are recoverable with follow-ups. Never produce a neutral list — name the single target dimension.
- EVOL-2: **Defer if trend is improving** (last-5 moving average exceeds prior average by ≥ 0.5 points), even if the absolute score is below threshold. Propensity to over-intervene outweighs the cost of waiting one more data window.
- EVOL-3: **Surgical single-section patch** is the default rollout scope. A patch touches one prompt section (role, process step, or hard gate) and changes ≤ 10 lines. Broader restructures require a gap of > 2.0 points across ≥ 2 dimensions.

## Section 4 — Derivation Rules

- EVOL-D-1: When safety average < 7.0 regardless of other scores, choose EVOL-1 target = safety because a safety defect can leak PII or bypass hard gates, causing immediate user or compliance harm.
- EVOL-D-2: When safety ≥ 7.0 AND accuracy < 7.0, choose EVOL-1 target = accuracy because inaccurate outputs corrupt downstream agent state and are harder for users to catch than incomplete responses.
- EVOL-D-3: When safety ≥ 7.0 AND accuracy ≥ 7.0 AND completeness < 7.0, choose EVOL-1 target = completeness because gaps are visible to users but correctable with follow-ups — lowest urgency.
- EVOL-D-4: When feedback entry count < 5, choose EVOL-2 = defer because the signal window is too narrow to distinguish a genuine pattern from statistical noise; premature changes may degrade a prompt that would have self-corrected.
- EVOL-D-5: When trend is improving (last-5 mean > prior mean by ≥ 0.5) AND absolute score ≥ 5.0, choose EVOL-2 = defer because intervention on an improving trajectory prolongs instability and makes the improvement signal harder to read.
- EVOL-D-6: When gap (threshold 7.0 − actual) ≤ 2.0 points on the target dimension, choose EVOL-3 = surgical-patch because a small gap requires a precise, low-risk fix — not a full restructure that introduces unrelated risk.
- EVOL-D-7: When gap > 2.0 points AND ≥ 2 dimensions score below threshold, choose EVOL-3 = restructure because the agent's role, process, or hard-gate sections are likely misaligned and a coordinated change is less risky than sequential patches.
- EVOL-D-8: When agent model tier is haiku, constrain EVOL-3 patch size to ≤ 5 new lines because haiku agents have smaller effective context and benefit from shorter, directive instructions over lengthy explanatory prose.

## Section 5 — Recommendation Output Contract

Every recommendation prompt-refiner emits from this pack MUST include:

1. **Target dimension** (EVOL-1 chosen value — the single named dimension: safety, accuracy, or completeness).
2. **Action** (EVOL-2 chosen value — `propose` or `defer`, with the rule ID(s) that fired; if defaults apply, state "defaults apply (no derivation rule fired)").
3. **Rollout scope** (EVOL-3 chosen value — `surgical-patch` or `restructure`, with rule citation).
4. **Named alternative**: at least one alternative approach with brief rationale (e.g. "or defer one more data window if the downward trend reverses").
5. **Override hook**: a concrete instruction the implementer can follow to override the recommendation (e.g. "override EVOL-1 by appending `target: accuracy` to the /refine call").

Consumers MUST NOT omit the rule citation or override hook; omitting either makes the recommendation unauditable and prevents reconstruction of the decision from the audit trail.

## Section 6 — Enforcement Handoff

prompt-evolution-craft output is validated by scoring-rubric (all three dimension scores must be present in the feedback entry that motivates any change; a recommendation lacking a score foundation is a schema violation) and baseline-enforcer (PII gate, cost gate, and audit trail apply unconditionally to every prompt-refiner invocation that produces output from this pack).
