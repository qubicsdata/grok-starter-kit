---
name: content-craft
description: |
  Opinionated content decision expertise — voice/tone, document structure, reading level, format/medium, CTA strategy, and headline pattern. Consumed by content-writer when making advisory decisions about how to shape a piece of content for a specific audience, goal, and channel. Every recommendation leads with a named default derived from constraints, cites the rule that produced it, and includes ≥1 alternative plus an override hook.
---

# Content Craft

## Section 1 — Decision Domains

- VOICE-1 Voice/tone register (direct-peer / conversational / formal-editorial / casual)
- STRUCT-1 Document structure (single-flow narrative / sectioned-with-headers / FAQ / listicle / inverted-pyramid)
- LEVEL-1 Reading level (expert / informed-generalist / newcomer)
- FORMAT-1 Format/medium (long-form article / short-form post / structured reference doc / micro-copy / email / thread/thread-style)
- CTA-1 CTA strategy (single-imperative / soft-invite / value-anchor / none)
- HEAD-1 Headline pattern (specificity-first / curiosity-gap / claim-then-proof / imperative / question)

## Section 2 — Constraint Inputs

- `audience` → VOICE-1, LEVEL-1 (audience expertise and context drives register and assumed knowledge depth)
- `purpose` → STRUCT-1, CTA-1 (purpose of piece determines logical architecture and whether/how to close with action)
- `channel` / `medium` → FORMAT-1, HEAD-1 (distribution context sets length norm, scanability need, and headline grammar)
- `voice` brief field → VOICE-1 (explicit voice statement overrides default; absent = default applies)
- `length` → STRUCT-1, FORMAT-1 (word target constrains structural complexity — short pieces cannot support full-section architecture)
- audience expertise level → LEVEL-1 (explicit "expert" / "beginner" / "mixed" in audience field flips reading-level default)
- goal (awareness / conversion / retention / instruction) → CTA-1 (conversion goal mandates single-imperative; instruction goal uses soft-invite or none)
- channel scan rate (social / email / long-form editorial) → HEAD-1 (high-scan channels demand specificity-first or claim-then-proof; long-form allows curiosity-gap)

## Section 3 — Opinionated Defaults

- VOICE-1: Direct peer register — second-person address, active voice, contractions welcome, 12–20 word average sentence length. No preamble, no throat-clearing.
- STRUCT-1: Single-flow narrative with a bold opening claim, 2–4 body paragraphs that each advance one point, and a forward-looking close. Sections only when length exceeds 500 words or multiple distinct topics are present.
- LEVEL-1: Informed-generalist — assume the reader knows the domain vocabulary but not the specific detail being explained. Define only terms the audience may genuinely not know; never define terms to appear thorough.
- FORMAT-1: Short-form post (200–400 words) for blog/social; long-form article (600–1200 words) when the purpose is to instruct or persuade a professional audience with durable reference value.
- CTA-1: Single-imperative — one action, stated concretely, placed at the close. Never present a list of options as the call-to-action.
- HEAD-1: Specificity-first — open with the concrete fact, number, or named outcome before any framing. "Latency dropped 60% after one config change" beats "How we improved performance."

## Section 4 — Derivation Rules

- CONTENT-D-1: When audience is identified as domain experts (engineers, specialists, practitioners) and purpose is instruction or reference, choose direct-peer register (VOICE-1) because experts read to extract, not to be guided; hedged or conversational framing wastes their time and reads as condescending.
- CONTENT-D-2: When audience is non-technical or mixed-expertise and purpose is awareness or onboarding, choose conversational register (VOICE-1) because newcomers process narrative before they absorb rules; a peer register without scaffolding creates comprehension gaps.
- CONTENT-D-3: When channel is social (Twitter/X thread, LinkedIn post, Slack announcement) or email subject line, choose specificity-first headline pattern (HEAD-1) because high-scan contexts reward the concrete noun or number in the first five words; curiosity-gap headlines lose clicks when the reader has no prior trust relationship.
- CONTENT-D-4: When channel is long-form editorial or thought-leadership blog AND the audience already follows the author/brand, choose curiosity-gap or claim-then-proof headline pattern (HEAD-1) because established trust allows the reader to invest in a setup before the payoff; specificity-first becomes predictable at volume.
- CONTENT-D-5: When purpose is conversion (free-trial signup, purchase, upgrade, demo request), choose single-imperative CTA (CTA-1) placed after the value proposition, before any caveats — because split CTAs reduce conversion by creating decision paralysis; the reader must complete one action, not evaluate three.
- CONTENT-D-6: When purpose is instruction or documentation and the audience will re-read or reference the piece, choose sectioned-with-headers structure (STRUCT-1) because navigability matters more than narrative flow for reference material; readers jump to the section they need, not start at paragraph one.
- CONTENT-D-7: When length target is under 300 words, choose single-flow narrative (STRUCT-1) and remove headers because structural chrome at that length occupies more cognitive space than it saves; the piece should read as a tight argument, not a sparse outline.
- CONTENT-D-8: When audience is identified as newcomers or the brief contains "introductory", "beginner", or "onboarding", choose newcomer reading level (LEVEL-1) — define domain terms on first use, avoid assumed acronyms, keep sentence length under 18 words on average — because a reader who does not understand a term stops reading; explanation overhead is always cheaper than churn.
- CONTENT-D-9: When purpose is retention, community engagement, or relationship maintenance with an existing user base, choose soft-invite CTA or no CTA (CTA-1) because a hard-sell close alienates users who are already committed; the close should reward them, not recruit them.
- CONTENT-D-10: When the topic is a product announcement or release and the audience is existing customers, choose inverted-pyramid structure (STRUCT-1) — lead with the change and its impact, follow with detail — because returning users need the "what changed" before context; narrative build-up delays the answer they came for.

## Section 5 — Recommendation Output Contract

For each Decision Domain, the content-writer MUST emit a recommendation block with the following structure:

1. **Domain name and chosen value** — a concrete, named choice (not a category description).
2. **Rule citation** — the CONTENT-D-N rule(s) that fired; if no derivation rule fired, state "defaults apply (CONTENT-D-* not triggered)".
3. **At least one named alternative** — with a brief rationale for when it would be the better choice instead.
4. **Override hook** — a concrete instruction the requester can follow to change the recommendation (e.g. "override VOICE-1 by specifying a voice statement in the brief; the content-writer will apply it in place of the default").

Recommendations MUST NOT be presented as a neutral menu of equal options. The chosen value is the recommendation; alternatives are for transparency and informed override, not for the reader to pick from.

Consumers of this pack MUST NOT omit the rule citation or the override hook. Omitting either makes the recommendation unverifiable and prevents the content-reviewer from auditing the decision chain.

## Section 6 — Enforcement Handoff

content-craft output is validated by content-reviewer (skill slug: `content-reviewer`). The content-reviewer checks that voice match holds (per its VOICE MATCH section), that claims are substantiated (per its CLAIMS section), and that the overall register is consistent with the recommendation produced by this pack. The content-reviewer's CON rule-ID prefix (CON-1 through CON-3, defined in spec-enricher) governs the production requirements this pack feeds into: CON-2 (audience and voice documented before drafting) is directly satisfied by VOICE-1 and LEVEL-1 recommendations; CON-3 (claims verifiable, filler removed) is enforced by the content-reviewer AUTHENTICITY and CLAIMS evaluations.
