---
name: frontend-stack-craft
description: Framework and tooling selection expertise — rendering model, CSS approach, state management, and build tool. Consumed by design-advisor and frontend spec-enrichers when choosing the foundational stack for a frontend project (greenfield or existing app).
---

# Frontend Stack Craft

## Section 1 — Decision Domains

- STACK-1 Framework & rendering model (CSR / SSR / SSG / islands / RSC)
- STACK-2 CSS approach (Tailwind utility-first / CSS Modules / runtime CSS-in-JS / plain CSS)
- STACK-3 State management strategy (server-state library / local useState-context / full client store)
- STACK-4 Build tool (Vite / Webpack / Turbopack / native ESM dev server)

## Section 2 — Constraint Inputs

- Content type → STACK-1 (app/dashboard favours RSC; content/editorial favours static or islands; marketing favours SSG)
- Performance budget → STACK-1 (tight budget rules out heavy client runtime), STACK-2 (tight budget rules out runtime CSS-in-JS)
- App complexity (derived from content type + interaction surface) → STACK-3 (high cross-cutting state needs a dedicated store)
- SEO requirement → STACK-1 (SEO-critical pages must pre-render HTML at build or request time)
- Team size & familiarity → STACK-1/STACK-4 (large unfamiliar team favours ecosystem breadth over cutting-edge)

## Section 3 — Opinionated Defaults

- STACK-1: React with React Server Components (RSC) for app/dashboard; Next.js App Router is the reference host.
- STACK-2: Tailwind CSS for utility composition, or CSS Modules when a design-system with explicit class contracts is preferred; no runtime CSS-in-JS (no styled-components, no Emotion) by default.
- STACK-3: React Query (TanStack Query) for server-state cache; local `useState` or React context for transient UI state only; no global client store unless complexity demands it.
- STACK-4: Vite for new projects (fast HMR, first-class ESM, light config); esbuild under the hood keeps production builds fast.

## Section 4 — Derivation Rules

- STACK-D-1: When content type is content/editorial or marketing AND SEO matters AND performance budget is tight, choose Astro because island architecture ships minimal JS by default and delivers the lightest First Contentful Paint for content-heavy pages.
- STACK-D-2: When content type is app/dashboard with rich interactivity, choose React + RSC because the component ecosystem is deep, streaming SSR covers data-heavy routes, and RSC offloads render cost to the server without giving up client interactivity.
- STACK-D-3: When performance budget is tight, choose Tailwind or CSS Modules over any runtime CSS-in-JS solution because runtime style computation adds bundle weight, increases main-thread work, and can delay the Critical Rendering Path.
- STACK-D-4: When app complexity is high — multiple independently updated cross-cutting client stores (e.g. cart, auth, notifications, real-time feed) — add a dedicated lightweight store (Zustand preferred; Redux Toolkit for teams already on Redux) because ad-hoc React context at scale causes unnecessary re-render storms and prop-threading anti-patterns.
- STACK-D-5: When SEO is critical and the content mix is hybrid (some static pages, some dynamic app pages), choose Next.js (Pages or App Router) with per-route rendering strategy (SSG for static, SSR/RSC for dynamic) because it enables fine-grained rendering control without introducing a separate static-site tool.
- STACK-D-6: When the project is a standalone static marketing site with no server runtime available, choose a pure SSG output (Next.js with `output: export`, Astro, or Eleventy) because a CDN-hosted static bundle is cheapest to operate and has no cold-start latency.

## Section 5 — Recommendation Output Contract

For each Decision Domain emit: the chosen value (named framework/library, not abstract category), the STACK-D-* rule(s) that produced it (or "defaults apply" when no derivation rule fired), ≥1 named alternative with a brief rationale, and an override hook.

Every recommendation block must follow this structure:

1. Domain name and chosen value as a named technology.
2. Rule citation — list each STACK-D-N that fired; if defaults apply, state "defaults apply (no derivation rule fired)".
3. At least one named alternative with a brief rationale (e.g. "or SvelteKit if bundle size is the top priority and RSC is not required").
4. Override hook — a concrete instruction for the implementer (e.g. "override STACK-1 in the project ADR and update the build pipeline accordingly").

Consumers of this pack MUST NOT omit the rule citation or the override hook; doing so makes the recommendation unverifiable and prevents later audits from reconstructing the decision.

## Section 6 — Enforcement Handoff

frontend-stack-craft output is validated by jsts-pack Section 5 (build/dependency norms — chosen build tool and dependency additions must comply with approved patterns) and jsts-pack Section 6 (lint/format of record — toolchain decisions must not conflict with the configured linter/formatter pipeline).
