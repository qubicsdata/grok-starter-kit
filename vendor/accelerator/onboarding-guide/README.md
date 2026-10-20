# onboarding-guide

A Claude Code plugin that reads an existing codebase and produces a practical `docs/onboarding.md` for a new hire or first-time contributor. Eight agents run in a pipeline; every agent applies a sensitive-content scrub before producing any output.

## Commands

| Command | What it does |
|---|---|
| `/onboarding` | Full pipeline — generates complete `docs/onboarding.md` |
| `/onboarding architecture` | Regenerates the Architecture Overview + Key Modules sections only |
| `/onboarding dataflow` | Regenerates the Data Flow section only |
| `/onboarding local-setup` | Regenerates the Running Locally section only |
| `/onboarding testing` | Regenerates the Testing section only |
| `/onboarding gotchas` | Regenerates the Common Gotchas section only |

## Arguments

- **`[path]`** — optional path to analyse (default: `.`, the current directory)
- **`--depth shallow|standard|deep`** — analysis depth (default: `standard`)

## Examples

```
/onboarding
/onboarding src/ --depth deep
/onboarding architecture
/onboarding local-setup src/
```

## How it works

1. **repo-surveyor** (Haiku) — scans the file tree, detects language/framework via the `stack-detection` skill, identifies entry points and key config files.
2. **architecture-analyser** (Sonnet) — reads entry points and the import graph of the top 10 most-imported modules to produce an architecture report.
3. **dataflow-tracer** (Sonnet) — traces at most 2 request lifecycles (primary sync + primary async if present).
4. **setup-extractor** (Haiku) — extracts exact install, run, test, and seed commands from README, Makefile, package.json scripts, and docker-compose files.
5. **test-landscape-agent** (Haiku) — detects the test runner, counts test files, and extracts run-all and run-one commands.
6. **gotcha-hunter** (Sonnet) — reviews architecture and dataflow reports for patterns that trip up newcomers; max 10 evidenced gotchas.
7. **content-writer** (Sonnet) — synthesises all reports into a complete `docs/onboarding.md`, presents the full draft for user confirmation, writes only on approval.
8. **section-updater** (Sonnet) — when `docs/onboarding.md` already exists, rewrites one section only and presents the diff before writing.

## Safety rules

- **No silent writes.** Every write to `docs/onboarding.md` is preceded by a full draft (or diff) and requires explicit user confirmation.
- **No credential echo.** The `sensitive-content-scrub` skill is a mandatory pre-output gate on every agent. Credential values, connection strings, and PII field values are never included in output.
- **No fabrication.** `setup-extractor` notes "not found in project docs — verify with team" for any step it cannot evidence. `gotcha-hunter` produces only evidenced gotchas.
- **No partial writes.** `content-writer` writes the complete document or nothing.

## Output

A single `docs/onboarding.md` in the analysed project with anchor-linked sections:

- Architecture Overview
- Key Modules
- Data Flow
- Running Locally
- Testing
- Where to Find Things
- Common Gotchas
- Keeping This Document Current

## Author

<your-name> — you@example.com

## Dependencies

- requires: ai-baseline
