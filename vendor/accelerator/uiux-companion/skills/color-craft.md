---
name: color-craft
description: Generative palette expertise — harmony models, neutral-ramp construction, semantic mapping, contrast-aware generation, dark-mode derivation. Consumed by design-advisor and uiux spec-enricher.
---

# Color Craft

## Section 1 — Decision Domains
- COLOR-1 Base hue & harmony model (mono / analogous / complementary / triadic)
- COLOR-2 Neutral ramp (warm vs cool, number of steps)
- COLOR-3 Saturation & distribution (60-30-10)
- COLOR-4 Semantic mapping (success/warning/error/info hues)
- COLOR-5 Dark-mode derivation

## Section 2 — Constraint Inputs
- Audience → COLOR-1 hue family, COLOR-3 saturation ceiling
- Brand personality → COLOR-1 harmony model, COLOR-3 saturation
- Accessibility target → contrast floors applied across all domains
- Content type → COLOR-2 neutral warmth, COLOR-3 distribution
- Platform → COLOR-5 dark-mode applicability (native dark-mode APIs vs CSS)
- Performance budget → COLOR-2 ramp step count (fewer tokens = lighter design token payload)

## Section 3 — Opinionated Defaults
- COLOR-1: single brand hue with an analogous accent; harmony = analogous.
- COLOR-2: 11-step neutral ramp, slightly warm (hue 30–40°, very low saturation).
- COLOR-3: 60-30-10 — 60% neutral surface, 30% secondary, 10% brand accent for primary actions.
- COLOR-4: success=green 140°, warning=amber 40°, error=red 10°, info=blue 220°, each tuned to meet 4.5:1 on surface.
- COLOR-5: derive dark mode by inverting the neutral ramp and reducing brand saturation ~15%, never by simple color inversion.

## Section 4 — Derivation Rules
- COLOR-D-1: When audience is finance or enterprise, choose a blue/teal hue family because it signals trust and stability.
- COLOR-D-2: When brand personality is playful, raise the accent saturation and use a complementary or triadic harmony because energy and contrast read as approachable.
- COLOR-D-3: When brand personality is premium, lower saturation and widen neutral spacing because restraint reads as high-end.
- COLOR-D-4: When accessibility target is AAA, raise all text/surface contrast floors to 7:1 (normal) / 4.5:1 (large) because AAA requires it.
- COLOR-D-5: When content type is content/editorial, choose a near-neutral warm ramp with a single restrained accent because long-form reading favours low chroma.
- COLOR-D-6: When platform is native mobile, collapse the neutral ramp to 7 steps because native system colors already supply mid-range tones.
- COLOR-D-7: When brand personality is trustworthy and audience is healthcare, add a secondary green accent (hue 140°) because green carries a universal safe/positive signal in clinical contexts.

## Section 5 — Recommendation Output Contract
For each Decision Domain emit: the chosen value (named tokens, not raw hex unless illustrating), the COLOR-D-* rule(s) that produced it, ≥1 alternative (e.g. "or a complementary scheme if more energy is wanted"), and the override hook ("override per token in the design-system").

Every recommendation block must follow this structure:
1. Domain name and chosen value as a named token or range.
2. Rule citation — list each COLOR-D-N that fired; if defaults apply, state "defaults apply (no derivation rule fired)".
3. At least one named alternative with a brief rationale.
4. Override hook — a concrete instruction for the implementer to override the value in the design token file.

## Section 6 — Enforcement Handoff
color-craft output is validated by design-system-spec DS-CL-* (token discipline) and by the a11y-checklist A11Y-1.4.3 contrast requirement (4.5:1 normal / 3:1 large).
