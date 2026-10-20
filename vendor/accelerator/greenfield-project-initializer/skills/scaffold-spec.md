---
name: scaffold-spec
description: Defines and validates a well-formed repository scaffold. Invoke within repo-scaffold-agent before presenting the file manifest to the user. Rejects manifests that contain application logic, missing .env.example, or unpinned dependencies.
---

## Purpose

The scaffold-spec skill defines what a valid greenfield scaffold looks like and provides the validation rules that `repo-scaffold-agent` must apply before presenting a file manifest to the user. A scaffold that fails any rule must be corrected before the manifest is shown.

## Valid Scaffold Definition

A well-formed scaffold:
- Contains only configuration files, structural placeholders, and skeleton entry points
- Has zero lines of application logic, business rules, or sample data
- Has `.env.example` present whenever any environment variable is referenced anywhere
- Has all dependency files with exact pinned versions
- Has a `README.md` with a quick-start section of ≤5 commands
- Has a `.gitignore` appropriate to the tech stack
- Contains no binary files, vendored dependency directories, or generated artifacts

## Validation Rules

Apply these rules in order. A manifest fails at the first violated rule.

### Rule 1: No Application Logic

Inspect every file's placeholder content. A file fails this rule if it contains:
- Function implementations beyond an empty stub or TODO comment
- SQL schema with data (DDL is allowed; DML `INSERT` statements with sample data are not)
- Business rule expressions, conditional logic, or algorithmic content
- Hardcoded configuration values that should be env vars

STOP: if any file in the manifest contains application logic, remove that logic and replace it with a `# TODO: implement [description]` comment before presenting the manifest.

### Rule 2: .env.example Required When Env Vars Referenced

Scan all proposed files for environment variable references (patterns: `process.env.`, `os.environ`, `os.Getenv`, `ENV[`, `${VAR}`, `$VAR` in shell scripts, `env:` in CI config).

DO NOT present a file manifest that references env vars without a corresponding `.env.example` that lists every referenced variable.

If `.env.example` is missing and env vars are referenced, add `.env.example` to the manifest automatically — this is non-negotiable.

### Rule 3: Dependency Pinning

Check all dependency files against these patterns:

| File | Violation pattern | Required pattern |
|------|------------------|-----------------| 
| `package.json` | `^`, `~`, `*`, `>=` in version strings | Exact: `"4.18.2"` |
| `requirements.txt` | `>=`, `>`, `~=`, `!=` without exact pin | `==` only |
| `Cargo.toml` | No `=` prefix, bare version | `= "1.2.3"` |
| `pom.xml` | Version range expressions | Exact `<version>` tag |
| `go.mod` | No version tag | Explicit `v1.2.3` tag |

STOP: if any dependency file uses open version ranges, replace them with exact pins or `X.Y.Z` placeholders with a pinning comment before presenting the manifest.

### Rule 4: README Quick-Start Completeness

The `README.md` must include a `## Quick Start` section. That section must contain a numbered list of ≤5 commands that take a developer from `git clone` to a running local environment.

DO NOT present a manifest whose `README.md` lacks a Quick Start section.

### Rule 5: No Binary or Vendored Files

The manifest must not include:
- Binary files (`.exe`, `.dll`, `.so`, `.dylib`, `.jar`, `.war`, `.ear`, compiled objects)
- Vendored dependency directories (`vendor/`, `node_modules/`, `.venv/`, `__pycache__/`)
- Generated files that should be produced by the build (`.class`, `.pyc`, minified JS/CSS without a source map)

STOP: if any such file appears in the manifest, remove it and add the appropriate pattern to `.gitignore` before presenting.

## Validation Output (internal to repo-scaffold-agent)

After applying all rules, produce one of:

```
Scaffold-spec validation: PASSED — all 5 rules satisfied.
```

or:

```
Scaffold-spec validation: FAILED
- Rule 2: .env.example missing; DATABASE_URL referenced in src/config.js — added .env.example to manifest
- Rule 3: package.json uses "^4.18.2" for express — corrected to "4.18.2"
Auto-corrections applied. Presenting corrected manifest.
```

Surface auto-corrections to the user in the manifest presentation so they are aware of what was fixed.

## Rules

DO NOT present a file manifest to the user that has not passed all 5 validation rules (with auto-corrections applied where possible).

DO NOT allow `.env.example` to be absent when env vars are referenced — this rule has no exceptions.

STOP and report to the orchestrator if a validation failure cannot be auto-corrected (e.g. a file contains complex application logic that the agent inserted by mistake) — this indicates a generation error that requires the agent to regenerate.
