---
name: adr-craft
description: Architecture Decision Record format selection and quality expertise — consumed by adr-agent when choosing ADR format, structuring options, and ensuring decision records are defensible and durable.
---

# ADR Craft

## Section 1 — Decision Domains

- ADR-1 Format selection (MADR / Nygard / Lightweight)
- ADR-2 Options structuring (how many options to surface, at what depth)
- ADR-3 Decision driver framing (what counts as a valid driver vs noise)
- ADR-4 Consequences articulation (positive / negative / neutral balance)

## Section 2 — Constraint Inputs

- Team size → ADR-1 (large teams need the structured cross-referencing and discoverability of MADR; small teams need Nygard's speed)
- Decision reversibility → ADR-2 (irreversible or expensive-to-reverse decisions need more options explored; reversible decisions can proceed with two)
- Audience breadth → ADR-1 (decisions reviewed by non-engineers or external stakeholders need MADR's explicit Consequences and Decision Drivers; internal dev-only decisions can use Nygard)
- Time pressure → ADR-1 / ADR-2 (acute time pressure allows Nygard with fewer options, but never fewer than two)
- Domain complexity → ADR-3 (high-complexity decisions require concrete, measurable decision drivers; vague drivers are rejected)

## Section 3 — Opinionated Defaults

- ADR-1: MADR format for all decisions when team size is unknown or ≥5 engineers. Nygard only for teams of <5 engineers with confirmed team size. Lightweight one-pager only for reversible tactical decisions where a full MADR or Nygard is disproportionate — requires explicit user opt-in.
- ADR-2: Exactly two meaningfully distinct options minimum; three when the decision is irreversible or affects more than one service boundary. Never fabricate options — only record options the team actually evaluated.
- ADR-3: Decision drivers must be concrete and scoped. "Maintainability" alone is not a driver; "reduces the number of files a new engineer must read to understand the auth flow" is. Each driver must be traceable to a specific project constraint or stakeholder concern.
- ADR-4: Every ADR requires at least one negative consequence. A decision with no downsides has either not been analysed or the alternatives were not real. Positive-only consequence lists are rejected.

## Section 4 — Derivation Rules

- ADR-D-1: When team size ≥ 5 engineers (or unknown), choose MADR because cross-team discoverability and structured Decision Drivers / Consequences scale better than Nygard's prose-light format; MADR's sections become a checklist that survives team turnover.
- ADR-D-2: When team size < 5 engineers and team size is confirmed, choose Nygard because its minimal structure imposes less ceremony cost on small teams and is faster to author and review without losing the essential context-decision-consequences triad.
- ADR-D-3: When the decision is irreversible (schema migration, public API contract, third-party lock-in) or crosses a service boundary, surface ≥3 options because the cost of a wrong irreversible choice exceeds the cost of one additional option evaluation turn.
- ADR-D-4: When a proposed decision driver is generic (contains "maintainability", "simplicity", "scalability", or "performance" without a concrete metric or project reference), reject it and prompt the user for a specific, scoped restatement because generic drivers cannot be evaluated or traced after the fact.
- ADR-D-5: When a user presents only positive consequences, prompt for at least one negative consequence before drafting because decisions with no tradeoffs are either trivial (and don't need an ADR) or the downsides are hidden (which makes the ADR misleading to future readers).

## Section 5 — Recommendation Output Contract

Every recommendation block emitted when adr-agent selects a format or advises on options MUST include:

1. **Chosen value** — the named format (MADR / Nygard) or options count (2 / 3), not an abstract label.
2. **Rule citation** — the ADR-D-N rule(s) that fired, or "defaults apply (ADR-1 default: MADR)" when team size is unknown.
3. **At least one named alternative** — e.g. "or Nygard if team size is confirmed at <5 engineers" or "or 2 options if the decision is reversible and affects only this repository."
4. **Override hook** — a concrete instruction for the user, e.g. "override format by stating team size explicitly" or "override options count in the decision statement: 'we evaluated three approaches: A, B, C.'"

Consumers MUST NOT omit the rule citation or the override hook; omitting them makes the format selection unverifiable in audit.

## Section 6 — Enforcement Handoff

adr-craft output is validated by baseline-enforcer (gate 1: PII scrub on draft ADR content before emitting; gate 3: audit trail after every adr-agent invocation). Format and options-count violations are detected by adr-agent's own pre-draft validation checklist (≥2 options, all required sections present, non-generic drivers, ≥1 negative consequence).
