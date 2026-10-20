# greenfield-project-initializer

A technology-agnostic, question-driven Claude Code plugin that guides development teams through every phase of a greenfield project — from requirements to working scaffold — producing durable, version-controlled artifacts with no unanswered assumptions.

## What it does

The plugin enforces a structured decision sequence so that every greenfield project starts with clarity rather than convention:

1. Requirements elicitation (one question at a time)
2. Team constraints and environment promotion strategy
3. Security baseline (6 mandatory questions)
4. System design (≥2 architecture shapes with trade-offs)
5. Tech stack selection (≥2 options per layer, tech-radar classified)
6. Architecture Decision Records for every significant choice
7. Repository scaffold (skeleton only — no application logic)
8. CI pipeline configuration (lint, tests, build, dependency scan, artifact versioning)

Every phase produces a human-readable artifact in `docs/`. Every write to disk requires explicit user confirmation. The session is resumable via `.greenfield-state.json`.

## Installation

Copy the `greenfield-project-initializer/` directory into your project's `.claude/plugins/` directory (or the global Claude Code plugins directory), then restart Claude Code.

## Commands

| Command | Description |
|---------|-------------|
| `/greenfield [optional: project description]` | Start or resume the full lifecycle |
| `/requirements` | Standalone requirements elicitation |
| `/sys-design` | Standalone system design (requires `docs/requirements.md`) |
| `/tech-stack` | Standalone tech stack selection (requires `docs/system-design.md`) |
| `/scaffold` | Standalone scaffold generation with gate checks |
| `/greenfield-adr "decision statement"` | Capture a single ADR scoped to this greenfield project — fully stateless |

## Quick Start

```
# Start a new project
/greenfield "a B2B SaaS invoicing platform for small businesses"

# Pick up where you left off
/greenfield

# Capture a decision without a full session
/greenfield-adr "Choice of message queue technology (Kafka vs RabbitMQ vs SQS)"
```

## Artifacts Produced

| Artifact | Phase | Written by |
|----------|-------|------------|
| `docs/requirements.md` | 1–4 | requirements-agent |
| `docs/system-design.md` | 5 | sys-design-agent |
| `docs/tech-stack.md` | 6 | tech-stack-agent |
| `docs/adr/NNNN-*.md` | 7 | adr-agent |
| Scaffold files (see below) | 8 | repo-scaffold-agent |
| CI config file | 9 | ci-designer |
| `.greenfield-state.json` | All | greenfield-orchestrator |

### Scaffold files always include

- `.env.example` (when any env var is referenced)
- `.gitignore` (tech-stack appropriate)
- `README.md` with Quick Start (≤5 commands)
- Dependency files with pinned exact versions
- Skeleton source directories and entry-point placeholders
- `docs/` directory with all generated artifacts

### Scaffold files never include

- Application logic or business rules
- Sample or seed data
- Vendored dependencies
- Binary files

## Security Baseline

The plugin asks 6 mandatory security questions before any scaffold is generated:

1. Secrets management strategy
2. Branch protection rules
3. Dependency scanning approach
4. CI service account privilege model
5. SAST tool selection
6. Authentication model

These answers are recorded in `docs/requirements.md` and cannot be skipped.

## Tech Radar

Every technology proposed by the plugin is classified on a four-ring radar:

- **Adopt** — safe for primary stack selection
- **Trial** — acceptable for non-critical paths; document the risk
- **Assess** — prototyping/spikes only
- **Hold** — cannot be recommended; flagged with explicit warning

Hold-rated technologies require explicit user acknowledgement and a documented ADR before selection.

## ADR Formats

The plugin produces ADRs in MADR format (teams of ≥5 engineers) or Nygard format (smaller teams), determined automatically from the requirements document. Every ADR requires ≥2 considered options and a decision rationale. ADRs are immutable once accepted — changes create a superseding ADR.

## Anti-Patterns This Plugin Prevents

- No secrets plan before scaffold
- Skipped environment promotion strategy
- Deferred security baseline
- Tech stack chosen by trend rather than fit
- Single-option "decisions" with no trade-off analysis
- Scaffold generated before architecture is agreed
- Missing `.env.example` when env vars are referenced
- Unpinned dependency versions
- Application logic in scaffold files
- Writing to disk without user confirmation

## Plugin Topology

```
greenfield-orchestrator (routes, gates, synthesises)
├── requirements-agent       [Sonnet]  writes docs/requirements.md
├── sys-design-agent         [Sonnet]  writes docs/system-design.md
├── tech-stack-agent         [Sonnet]  writes docs/tech-stack.md
├── adr-agent                [Sonnet]  writes docs/adr/NNNN-*.md
├── repo-scaffold-agent      [Haiku]   writes scaffold files
├── ci-designer              [Haiku]   writes CI config
└── Skills (inline validation)
    ├── greenfield-checklist  6-item gate before scaffold
    ├── scaffold-spec         validates file manifest
    ├── adr-template          validates ADR format
    ├── tech-radar            classifies technologies
    └── security-baseline     6 mandatory security questions
```

## Author

<your-name> — you@example.com

## Version

1.0.0

## Dependencies

- requires: ai-baseline
