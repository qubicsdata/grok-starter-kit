---
name: type-craft
description: Generative typography scale + pairing expertise — type-scale ratio, font pairing, weight character, and web-font performance strategy. Consumed by design-advisor and uiux spec-enricher.
---

# Type Craft

## Section 1 — Decision Domains
- TYPE-1 Type-scale ratio (the multiplier between steps in the modular scale)
- TYPE-2 Font pairing (heading vs body typeface family choice)
- TYPE-3 Weight and character (body weight, heading weight, overall personality)
- TYPE-4 Web-font performance strategy (loading behaviour, family count, subsetting)

## Section 2 — Constraint Inputs
- Content type → TYPE-1 ratio (editorial content benefits from tighter ratios; marketing content warrants larger jumps); TYPE-2 pairing (editorial → serif body; marketing → expressive display)
- Brand personality → TYPE-2 pairing (premium → high-contrast serif/sans pairing; playful → rounded sans; utilitarian → neutral mono-weight sans); TYPE-3 weight character (premium → 300–600 range; bold → 700–900 headings)
- Performance budget → TYPE-4 strategy (tight → single variable font; normal → two families; rich → decorative display family permitted)
- Platform → TYPE-1 ratio (desktop-dense → smaller ratio 1.2; responsive web → 1.25; marketing landing → 1.333–1.414)
- Audience → TYPE-3 character (finance/enterprise → conservative weight spread; consumer → moderate; healthcare → high legibility, generous line-height)

## Section 3 — Opinionated Defaults
- TYPE-1: 1.25 (major third). Produces a clear hierarchy without the extremes of a minor second (1.125, too flat) or a golden ratio (1.618, too dramatic for most UIs).
- TYPE-2: single neutral sans super-family — Inter — for both heading and body, differentiated by weight. One family = zero pairing friction, consistent metrics, and a single font file.
- TYPE-3: body 400 (Regular), headings 600 (SemiBold). Sufficient contrast within a single super-family; avoids 700+ weight for headings except on marketing hero copy.
- TYPE-4: `font-display: swap` on every web font declaration, subset to the Unicode ranges actually used (Latin subset at minimum), maximum 2 font families loaded. Each additional family is a render-blocking asset.

## Section 4 — Derivation Rules
- TYPE-D-1: When content type is content/editorial, choose a serif body (e.g. Source Serif 4 or Lora) paired with a neutral sans heading (e.g. Inter) because long-form reading favours serif legibility — the stroke variation and serifs guide horizontal eye movement across line lengths over 65 characters.
- TYPE-D-2: When content type is marketing, raise the TYPE-1 ratio to 1.333 (perfect fourth) because larger heading steps increase visual hierarchy and impact on promotional layouts where scanning, not reading, is the primary mode.
- TYPE-D-3: When brand personality is premium, pair a high-contrast display serif heading (e.g. Playfair Display, Cormorant) with a neutral sans body (e.g. Inter, DM Sans) because the contrast of refined letterform detail against utilitarian body text reads as high-end and considered.
- TYPE-D-4: When performance budget is tight, restrict to one variable font (e.g. Inter Variable) and eliminate the second family entirely because each additional font family is a separate render-blocking network asset that delays First Contentful Paint.

## Section 5 — Recommendation Output Contract
For each Decision Domain emit: the chosen value (named scale step or family name, not raw pixel sizes), the TYPE-D-* rule(s) that produced it, at least one named alternative, and an override hook.

Every recommendation block must follow this structure:
1. Domain name and chosen value — state the named value (e.g. "major-third scale / Inter / 400 body / font-display: swap").
2. Rule citation — list each TYPE-D-N that fired; if defaults apply, state "defaults apply (no derivation rule fired)".
3. At least one named alternative with brief rationale (e.g. "alternative: minor third 1.2 ratio if the layout is dense; alternative: Lora body if editorial richness is wanted").
4. Override hook — a concrete instruction for the implementer (e.g. "override by replacing the --type-ratio custom property in design-tokens/typography.css; change the font-family stack in tokens/font-families.json").

## Section 6 — Enforcement Handoff
type-craft output is validated by design-system-spec DS-TP-* (named type styles, no raw font sizes in implementation; every heading and body size must resolve to a named type-style token, not an ad-hoc numeric value).
