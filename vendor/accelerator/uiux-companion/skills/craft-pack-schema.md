---
name: craft-pack-schema
description: The canonical schema every craft pack must follow. Import when authoring or validating a craft pack (generative design expertise consumed by the design-advisor and spec-enrichers).
---

# Craft Pack Schema

Every craft pack MUST provide all six sections below, with the exact `## Section N — <Name>` headers shown. Omitting a section, leaving it empty, or using placeholder text is a schema violation (enforced by `tools/check-craft-packs.py`).

Craft packs encode *generative, tiered* expertise: an opinionated default (tier 1) with a constraint-derivation underneath (tier 2), surfaced together so every recommendation is defensible and overridable.

## Section 1 — Decision Domains
The discrete decisions this pack makes. The decision is the unit. Name each and give an ID prefix used by later sections.

## Section 2 — Constraint Inputs
Which `design-brief` dimensions drive each decision, and how. A mapping from brief dimension → affected decision(s).

## Section 3 — Opinionated Defaults
The expert default for each Decision Domain when constraints are silent. Concrete, named, defensible — never "it depends."

## Section 4 — Derivation Rules
`constraint → decision` rules, each with a stable ID and one-line rationale. Format: `<PACK>-D-N: When <brief condition>, choose <decision value> because <rationale>.`

## Section 5 — Recommendation Output Contract
Every recommendation a consumer emits from this pack MUST surface: the chosen value, the rule ID(s) from Section 4 that produced it, ≥1 named alternative, and an override hook.

## Section 6 — Enforcement Handoff
Which existing review skill + violation-ID prefix validates this pack's output. Format: `<craft-pack> output is validated by <review-skill> <ID-prefix>.`
