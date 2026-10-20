---
name: task-scoring
description: Use immediately after the intake interview, before dispatching any downstream agent — scores the task on 3 axes and produces the model routing table for the session
---

# Task Scoring

Score the task on three axes. Present scores and routing to the user before proceeding. Do not enter the design phase until the user confirms or adjusts.

## Scoring Axes (each 1–3)

| Axis | 1 — Low | 2 — Medium | 3 — High |
|---|---|---|---|
| **Scope** | Single agent or skill, clear boundaries | Multiple agents or a full plugin | Novel topology, cross-plugin dependencies, or marketplace integration |
| **Ambiguity** | Requirement is precise and complete | Some gaps, needs clarifying questions answered | Vague intent, conflicting constraints, or undefined success criteria |
| **Stakes** | Internal or personal use only | Publishing to a private marketplace | Publishing to a public marketplace or used as infrastructure by other agents |

**Total score = Scope + Ambiguity + Stakes (range: 3–9)**

## Routing Table

Tier → model ID resolution comes from `tools/model-ids.json` (`canonical` map; prose
rationale in ai-baseline's `model-tier-guide`). Never write a raw model ID in this
skill or any builder prose — `tools/check-model-ids.py` gates it.

| Total | Model | Applies to |
|---|---|---|
| 3–4 | haiku tier | Formatting, linting, boilerplate generation, specialist panel on well-defined tasks |
| 5–7 | sonnet tier | Design generation, file writing, UX review, publisher |
| 8–9 | opus tier | Orchestrator synthesis, design-agent on complex tasks |

## Review Tier (risk-proportional review)

The review machinery must scale with risk, not run at fixed maximum. Derive a
**review tier** from the total score — this is the builder's build-time supply of the
tier defined in `ai-baseline/skills/risk-tier-spec.md` (the builder has no `/enrich`
result, so it uses its own 3-axis total in place of the risk formula that `/enrich` uses;
both produce the same three tiers with the same meaning).

| Total | Review tier | Critic model | Panel that runs |
|---|---|---|---|
| 3–4 | **light** | sonnet tier | none (critic only)† |
| 5–7 | **standard** | sonnet tier | security-reviewer only† |
| 8–9 | **full** | opus tier | full panel (security + ux + topology)† |

† test-agent is NOT a reviewer and runs at EVERY tier — it produces the required
`tests/behavioral-scenarios.md` artifact (fleet invariant, see builder-orchestrator step 10).

**Force-floor:** if the plugin is security-sensitive (handles auth, secrets,
credentials, code execution, or is declared infrastructure / Stakes = 3), the tier
is **at least standard** even if the total says light.

**Critic floor:** the critic NEVER runs below the sonnet tier. The old "critic is
always opus" rule is replaced by this tier mapping — opus is reserved for full-tier
builds where the deep adversarial pass actually pays. The static output-hygiene gate
and PIT-1..11 checks run at EVERY tier regardless (mechanical coverage is decoupled
from the critic's model).

## Required Output Format

Present exactly this block to the user before proceeding:

```
Task Scoring
  Scope:     [1-3] — [one-line justification]
  Ambiguity: [1-3] — [one-line justification]
  Stakes:    [1-3] — [one-line justification]
  Total:     [3-9] → [haiku / sonnet / opus]
  Review tier: [light / standard / full]  (security force-floor: [applied / n/a])

Agent routing:
  intake-agent:           [model used for this scoring step]
  design-agent:           [routed model]
  generate-agent:         [routed model]
  critic-agent:           [sonnet at light/standard, opus at full]
  security-reviewer:      [routed model — runs at standard and full]
  ux-reviewer:            [routed model — runs at full only]
  topology-reviewer:      [routed model — runs at full only]
  publisher-agent:        [routed model]

You may override any assignment or the review tier. Confirm routing to proceed.
```

## STOP

DO NOT dispatch design-agent until the user has confirmed the routing (or provided overrides). Proceeding without confirmation skips the transparency guarantee and is a guardrail violation.
