---
name: layout-craft
description: Generative composition and layout expertise — screen-type composition patterns, grid system selection, density calibration, scan-pattern routing, and four-state design. Consumed by design-advisor and uiux spec-enricher.
---

# Layout Craft

## Section 1 — Decision Domains
- LAYOUT-1 Composition pattern by screen type (dashboard / form / landing / list / detail)
- LAYOUT-2 Grid system (column count, gutter width, margin, breakpoint set)
- LAYOUT-3 Information density (comfortable / compact / spacious)
- LAYOUT-4 Scan pattern (F-pattern for content-heavy; Z-pattern for action-oriented / marketing)
- LAYOUT-5 Supplementary states — all four required on every data surface (empty / loading / error / success)

## Section 2 — Constraint Inputs
- Content type → LAYOUT-1 composition choice (dashboard vs landing vs form vs list vs detail); LAYOUT-4 scan-pattern routing (marketing/action → Z; editorial/list → F)
- Platform → LAYOUT-2 grid system (responsive web → 12-column; native mobile → 4-column; desktop-dense data tool → 16-column); LAYOUT-3 density ceiling (mobile → comfortable-only; desktop-dense → compact permitted)
- Audience → LAYOUT-3 density (expert/power users → compact; general consumer → comfortable; healthcare/accessibility → spacious)
- Performance budget → LAYOUT-2 breakpoint count (tight budget → three breakpoints min; normal → five-breakpoint set)
- Screen type → LAYOUT-5 state requirements (all data surfaces: all four states mandatory; static marketing pages: loading/error optional but empty and success still scoped)

## Section 3 — Opinionated Defaults
- LAYOUT-1: single-column primary content with a right-rail for secondary information on dashboards; full-width single-column stack on all other screen types unless brief specifies otherwise.
- LAYOUT-2: 12-column responsive grid with 24 px gutters, 32 px outer margins (desktop), collapsing to 4-column with 16 px gutters on mobile. Maximum content width 1280 px.
- LAYOUT-3: comfortable density — adequate whitespace for a general consumer audience; line-heights ≥ 1.5 for body text; minimum 16 px spacing between interactive elements.
- LAYOUT-4: F-pattern for content-heavy screens (articles, dashboards, lists); Z-pattern for action-oriented screens (landing pages, onboarding, checkout).
- LAYOUT-5: all four supplementary states (empty, loading, error, success) are required on every screen that displays data or waits on an async operation. No state may be left to implementation-time inference.

## Section 4 — Derivation Rules
- LAYOUT-D-1: When content type is marketing or landing, use a Z-pattern single-focus hero with one dominant CTA because action-oriented pages need one primary conversion point — multiple competing CTAs fragment attention and reduce click-through.
- LAYOUT-D-2: When platform is desktop-dense (data tools, analytics dashboards, admin panels), raise LAYOUT-3 to compact density because expert users scan high-information tables and want maximum data visibility per viewport without excessive scrolling.
- LAYOUT-D-3: When content type is transactional (forms, checkout, registration), use one task per screen with a linear progress indicator because reducing competing choices and visible progress lowers abandonment rates and cognitive load.
- LAYOUT-D-4: When audience is healthcare or accessibility-first, raise LAYOUT-3 to spacious density and widen the minimum touch target to 48 px because larger targets reduce input error rates and meet WCAG 2.5.5 Target Size criteria.
- LAYOUT-D-5: When screen type is list or data table with more than 50 rows, introduce a sticky-header and in-column sort controls because users navigating long lists need orientation anchors as they scroll, preventing the loss-of-context anti-pattern.

## Section 5 — Recommendation Output Contract
For each Decision Domain emit: the chosen value (named layout pattern or grid spec, not raw pixel arithmetic unless illustrating a specific constraint), the LAYOUT-D-* rule(s) that produced it, at least one named alternative, and an override hook.

Every recommendation block must follow this structure:
1. Domain name and chosen value — state the named pattern or grid spec (e.g. "Z-pattern single-focus hero / 12-column responsive grid / comfortable density").
2. Rule citation — list each LAYOUT-D-N that fired; if defaults apply, state "defaults apply (no derivation rule fired)".
3. At least one named alternative with a brief rationale (e.g. "alternative: F-pattern if secondary editorial content is added alongside the CTA; alternative: 16-column grid if a persistent left-nav panel is required").
4. Override hook — a concrete instruction for the implementer (e.g. "override grid column count via the --grid-columns custom property in design-tokens/layout.css; override density tier via the data-density attribute on the root layout element").

## Section 6 — Enforcement Handoff
layout-craft output is validated by visual-hierarchy-principles VH-* (VH-1 primary-action clarity, VH-2 reading order matches chosen scan pattern, VH-5 density appropriate for screen type, VH-6 all four supplementary states present on every data surface).
