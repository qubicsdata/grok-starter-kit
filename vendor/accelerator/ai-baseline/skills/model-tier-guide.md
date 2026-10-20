---
name: model-tier-guide
description: |
  Canonical guidance for choosing a model tier (haiku / sonnet / opus) per agent role across the fleet. Read when authoring an agent's `model:` frontmatter, when routing a builder role, or when a risk tier prescribes a model. The cheapest tier that meets the role's judgment bar wins — turn count, not sticker price, is the real cost.
contract_version: 1.0.0
---

# Model Tier Guide

One source of truth for "which model for which role." Before this guide the fleet
was 112 sonnet / 43 haiku / 10 opus, chosen ad hoc. The rule: **use the cheapest
tier that clears the role's judgment bar.** A cheaper model that takes 3× the turns
on work it can't really do is not cheaper.

## The three tiers

| Tier | `model:` value | Use for |
|------|----------------|---------|
| **haiku** | `haiku` | Mechanical, well-specified, low-judgment work: transcription of a complete spec into code, formatting, boilerplate, single-file edits, fixed-format extraction, audit/log/scrub utilities. |
| **sonnet** | `sonnet` | The default workhorse: design from prose, multi-file integration, code review scaled to a normal diff, orchestration, most spec-enrichment and analysis. When unsure, this is the floor. |
| **opus** | `opus` | Adversarial or high-stakes judgment: final whole-branch review, subtle security/concurrency review, architecture decisions, the deepest critic pass on a high-risk build. |

These three tier aliases are the ONLY permitted `model:` values (enforced by
`tools/validate-fleet.py`, `tools/check-model-ids.py`, and PIT-9).

**Write the alias, never a pinned model ID.** Claude Code resolves `haiku` /
`sonnet` / `opus` to the current model for that tier at dispatch time, so the
fleet picks up a new model release without a 300-file sweep. A pinned ID
(`claude-sonnet-4-6`, `claude-opus-4-8`, …) is listed as **deprecated** in
`tools/model-ids.json` and fails the gate — that is deliberate, it is how the
decoupling stays decoupled. Never write an ARN.

Adding a tier (e.g. `fable`) is a deliberate act: add it to `allowed` in
`tools/model-ids.json` and give it a row here, in the same change.

## Choosing by role

- **Implementer / generator** — haiku when the task text contains the complete
  code to write (transcription + tests); sonnet when building from a prose
  description across files; opus only for genuine design work.
- **Reviewer / critic** — scale to the diff's size, complexity, and risk, NOT to a
  fixed default. A small mechanical diff gets sonnet; a subtle concurrency or
  security change gets opus. **Never below sonnet** for a review that exercises
  judgment.
- **Mechanical utilities** (audit-trail, pii-scrub, cost-gate, context-manager,
  formatters) — haiku.
- **Orchestrators that only route/synthesize** — sonnet (no generative load).

## Hard constraints (do not violate)

- **Spec-enrichers are pinned to the `sonnet` tier** by the spec-enricher
  contract and `tools/validate-fleet.py`. Enrichment is a judgment task; do NOT
  retier enrichers to haiku. Tiering applies to *builder roles* and *consumer
  review roles*, never to enrichers.
- A reviewer's model floor is **sonnet**. Risk tiering may raise a critic to opus
  but must never drop it below sonnet.
- Always set `model:` explicitly when dispatching a subagent. An omitted model
  inherits the caller's (often the most expensive) model and silently defeats this
  guide.

## Empirical note — tier for COST, not token count (measured 2026-06-21)

A measured builder review found the **sonnet critic used MORE tokens than the opus
critic** on the same artifact (33.6k over 36 turns vs 28.5k over 16 turns) — the
"cheaper model takes more turns" effect. So tiering a role down is a **price-per-token
win (~5× opus→sonnet), not a token-count win**; the extra turns partly eat it back, but
cost still falls ~4× on the critic. Two consequences:

- Judge a tiering decision by **cost** (price × tokens), never by token count alone, or
  you will wrongly conclude it doesn't help.
- Token-count reductions come from doing **fewer dispatches** (e.g. dropping panel
  reviewers), not from a smaller model. The two effects are separate and compound.

See the builder-panel re-benchmark in `benchmarks/2026-06-21-escalating/` and the
review-cost notes of the same day (neither is vendored in this kit).

## Relationship to risk tiering

`risk-tier-spec.md` consumes this guide: it maps a build's risk tier to the model
each review role should run at (light → critic sonnet, no panel; full → critic
opus, full panel). This guide defines the tiers; the risk spec decides which to
apply per build.
