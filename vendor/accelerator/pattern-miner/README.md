# pattern-miner

Learn a project's established coding conventions on demand — scan a codebase, extract its recurring patterns, critique them for signal vs. noise, and codify the survivors into a reusable per-project catalog that feeds spec enrichment and code review.

## Installation

Copy or symlink this plugin directory into your accelerator fleet. Ensure `ai-baseline` is installed first (see Dependencies).

No additional configuration files are required. The catalog store (`mined-patterns/`) is created automatically on first run.

## Usage

### Mine patterns from a repository

```
/mine-patterns /path/to/your/repo
```

This runs the full pipeline:

1. **pattern-scanner** — reads the repo (read-only) and surfaces candidate recurring patterns with evidence locations.
2. **pattern-critic** — adversarially evaluates each candidate: real convention, coincidence/noise, or anti-pattern. Only approved candidates proceed.
3. **convention-extractor** — writes the approved candidates as schema-conformant entries to `mined-patterns/<project>.md`.

**Example:**

```
/mine-patterns /home/user/repos/billing-service
```

Output:

```
EXTRACT_RESULT: ok
  catalog: mined-patterns/billing-service.md
  entries_written: 7
  conflicts_flagged: 1
```

### View the catalog

```
/pattern-catalog billing-service
```

Displays the full catalog for the project. Omit the project name to list all available catalogs.

## Commands

- `/mine-patterns <repo>` — run the scan → critique → extract pipeline and produce or update the project's pattern catalog
- `/pattern-catalog [<project>]` — display the codified catalog for a project, or list all available catalogs

## Dependencies

- requires: ai-baseline
