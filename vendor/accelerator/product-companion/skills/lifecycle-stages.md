---
name: lifecycle-stages
description: The project passport's stage enum, the evidence table each transition requires, and the stage→earned-handoff map. Import when proposing a stage transition or surfacing stage-appropriate next steps.
---

# Lifecycle Stages

## Stage enum

`idea | scaffolded | building | hardening | released | operating`

The current stage lives in `docs/product/passport.json` (`stage`), with every transition recorded in the append-only `stage_history` (see the backlog-schema skill).

## Transition discipline

- Transitions advance ONLY on machine-checkable evidence (PLAN-D-8): proposed with evidence, **user-confirmed, never silently flipped**.
- **Propose once:** each proposal fires once per transition, recorded in `stage_history` — never re-nagged.
- **Forward-only.** Regression (e.g. operating → building) requires explicit user confirmation and is logged with `evidence: "user-declared regression: <reason>"`.
- **Highest earned rung wins.** A stage-check evaluates every forward evidence row (highest target first) and proposes the highest stage whose row passes — rungs may be skipped when higher evidence exists (e.g. `idea → building` on the first DoD-passed done story in a repo where `docs/requirements.md` never existed). A lower rung's evidence is never a prerequisite for a higher rung's row; the proposal records the evidence actually observed.
- `/product-init` on an existing repo starts at the **earned** stage (runs the evidence table bottom-up; an existing repo with code never starts at `idea`).

## Evidence table

Each transition requires the mechanical file/git check below, run by passport-agent. No evidence row, no proposal.

| Transition | Evidence (mechanical file/git check run by passport-agent) |
|---|---|
| idea → scaffolded | `docs/requirements.md` exists AND repo contains source files beyond `docs/` (greenfield handoff completed) |
| scaffolded → building | first story reaches `status: done` (DoD-passed) |
| building → hardening | every non-dropped story of an epic with `release_target` set is `done` |
| hardening → released | a git tag matching the `release_target` exists AND `CHANGELOG.md` contains the version entry |
| released → operating | ≥1 tag exists AND post-release signal present (`.observability/slo.json` exists, or a new story was created after the latest tag's date) |

## Stage → earned-handoff map

Each row fires only when the stage's evidence is present — earned only, never unconditional. Silence is the default.

| stage | earned handoff |
|---|---|
| idea | `/greenfield` (personas + epics seed docs/requirements.md) |
| scaffolded | `/story` then `/build-next` |
| building | `/build-next` |
| hardening | `/release-ready`, `/deploy-checklist`, `/security` |
| released | `/release` (next cycle), `/observe` |
| operating | `/observe`, `/slo-status`; incidents re-enter as stories via `/story` |

<!-- handoff: stage=idea → consider `/greenfield` -->
<!-- handoff: stage=scaffolded → consider `/story` then `/build-next` -->
<!-- handoff: stage=building → consider `/build-next` -->
<!-- handoff: stage=hardening → consider `/release-ready`, `/deploy-checklist`, `/security` -->
<!-- handoff: stage=released → consider `/release`, `/observe` -->
<!-- handoff: stage=operating → consider `/observe`, `/slo-status`, `/story` -->
