# legacy-modernizer

A Claude Code plugin for teams facing an existing codebase that has grown beyond its original design. Legacy Modernizer performs structured discovery of the existing system and produces a phased, sequenced migration roadmap: what to change, in what order, why that order, and how to verify each phase before moving to the next.

## What it does

The plugin enforces a structured analysis sequence so every modernization engagement starts with an accurate inventory rather than assumptions:

1. Discovery — surveys file tree, manifests, CI config, framework config, and representative source files; produces `docs/modernization/inventory.md`
2. Risk scoring — applies the migration-risk-scale rubric to every inventory item; produces `docs/modernization/risk-register.md`
3. Upgrade mapping — classifies every technology with tech-radar, maps a recommended target state for each with ≥2 options where alternatives exist; produces `docs/modernization/upgrade-map.md`
4. Readiness gate — five-item checklist that must pass before sequencing begins
5. Sequencing — orders upgrade tasks into phases, each phase leaving the codebase buildable and deployable; produces `docs/modernization/roadmap.md`
6. ADRs — MADR-format decision records for each key migration decision where ≥2 options were considered

Every write to disk requires explicit user confirmation. The session is resumable via `.modernize-state.json`.

**Scope boundary:** This plugin produces plans only. It does not write, patch, refactor, or execute migration code.

## Installation

Copy the `legacy-modernizer/` directory into your project's `.claude/plugins/` directory (or the global Claude Code plugins directory), then restart Claude Code.

## Commands

| Command | Description |
|---------|-------------|
| `/modernize [optional: brief codebase description]` | Start or resume the full modernization lifecycle |
| `/modernize-inventory [optional: directory path or scope filter]` | Standalone discovery — produces inventory.md |
| `/modernize-risks` | Standalone risk scoring — requires inventory.md |
| `/modernize-upgrade-map` | Standalone upgrade mapping — requires inventory.md and risk-register.md |
| `/modernize-roadmap` | Standalone sequencing — runs readiness gate then produces roadmap.md |
| `/modernize-adr "migration decision statement"` | Capture a single migration ADR — stateless |

## Quick Start

```
# Start a new modernization engagement
/modernize "Node 14 Express API with PostgreSQL, ~80k lines"

# Pick up where you left off
/modernize

# Run just the discovery phase
/modernize-inventory

# Scope discovery to one subdirectory
/modernize-inventory src/legacy-module

# Capture a migration decision without a full session
/modernize-adr "Replace Webpack 4 with Vite: evaluating Vite vs esbuild vs Parcel"
```

## Artifacts Produced

| Artifact | Written by | Location |
|----------|------------|----------|
| Codebase inventory | discovery-agent | `docs/modernization/inventory.md` |
| Risk register | risk-scorer | `docs/modernization/risk-register.md` |
| Upgrade map | upgrade-map-agent | `docs/modernization/upgrade-map.md` |
| Migration roadmap | sequencer-agent | `docs/modernization/roadmap.md` |
| ADRs | adr-agent | `docs/modernization/decisions/NNNN-[slug].md` |
| Session state | modernize-orchestrator | `.modernize-state.json` |

## Phase Order

```
Phase 1 — Discovery         →  inventory.md
Phase 2 — Risk Scoring      →  risk-register.md         (requires inventory.md)
Phase 3 — Upgrade Mapping   →  upgrade-map.md           (requires inventory.md + risk-register.md)
Readiness Gate              →  5-item checklist must pass
Phase 4 — Sequencing        →  roadmap.md               (requires gate cleared)
ADRs (N)                    →  decisions/NNNN-[slug].md (requires pending ADR list from sequencer-agent)
```

## Tech Radar

Every technology in the upgrade map is classified on a four-ring radar:

- **Adopt** — safe to recommend as a target state
- **Trial** — acceptable; document the risk
- **Assess** — prototyping only; not recommended for production migration target
- **Hold** — cannot be a recommended target state; requires ADR with explicit user acknowledgement if the user wishes to keep it

## Anti-Patterns This Plugin Prevents

- Sequencing migrations that break the build (buildability-invariant skill + sequencer-agent constraint)
- Recommending Hold-rated technologies as migration targets
- Inventorying a codebase without recording what was not surveyed
- Writing any artifact without explicit user confirmation
- Recommending migrations without trade-offs (upgrade-map-agent presents ≥2 options per technology)
- Exposing credential values found in the codebase
- All risk items scoring at the same priority
- Phases with no verifiable completion criteria
- Starting sequencing before the upgrade map is complete
- Producing execution code

## Plugin Topology

```
modernize-orchestrator (routes, gates, synthesises)
├── discovery-agent       [Sonnet]  writes docs/modernization/inventory.md
├── risk-scorer           [Sonnet]  writes docs/modernization/risk-register.md
├── upgrade-map-agent     [Sonnet]  writes docs/modernization/upgrade-map.md
├── sequencer-agent       [Sonnet]  writes docs/modernization/roadmap.md
├── adr-agent             [Sonnet]  writes docs/modernization/decisions/NNNN-[slug].md
└── Skills (inline rubrics)
    ├── migration-risk-scale   probability × impact scoring rubric
    ├── tech-radar             Adopt / Trial / Assess / Hold classification
    ├── readiness-checklist    5-item gate before sequencing
    ├── adr-template           MADR format
    └── buildability-invariant phase boundary deployment check
```

## Author

<your-name> — you@example.com

## Version

1.0.0

## Dependencies

- requires: ai-baseline
