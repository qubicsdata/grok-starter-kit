---
name: stack-detection
description: |
  Use when you need to identify a project's language, framework, build system, test runner, or database from its files. Canonical heuristics over file patterns and config files; returns a structured stack object. On conflicting signals it halts and asks the user to confirm the primary stack.
---

# Stack Detection

## Purpose

Apply this skill when any agent needs to determine the project's language, framework, build system, test runner, or database. This is the single source of stack truth. No agent may derive stack information independently.

## Detection Heuristics

| Signal file / pattern | Language / Framework detected |
|---|---|
| `package.json` with `"next"` in dependencies or devDependencies | TypeScript/JavaScript + Next.js |
| `package.json` with `"express"` in dependencies | Node.js + Express |
| `package.json` with `"react"` in dependencies (no `"next"`) | React SPA |
| `package.json` with `"vue"` in dependencies | JavaScript/TypeScript + Vue.js |
| `package.json` with `"@nestjs/core"` in dependencies | TypeScript + NestJS |
| `go.mod` present | Go |
| `go.mod` + `require github.com/gin-gonic/gin` | Go + Gin |
| `go.mod` + `require github.com/labstack/echo` | Go + the labstack web framework |
| `pyproject.toml` or `setup.py` with `"fastapi"` in dependencies | Python + FastAPI |
| `pyproject.toml` with `"django"` in dependencies | Python + Django |
| `pyproject.toml` with `"flask"` in dependencies | Python + Flask |
| `Cargo.toml` present | Rust |
| `Cargo.toml` with `actix-web` in `[dependencies]` | Rust + Actix-web |
| `pom.xml` present | Java + Maven |
| `build.gradle` present | Java/Kotlin + Gradle |
| `*.csproj` file present | C# / .NET |
| `mix.exs` present | Elixir |
| `Gemfile` with `"rails"` | Ruby on Rails |
| `Gemfile` without `"rails"` | Ruby |
| None of the above | "Unknown — survey manually" |

## Test Runner Detection

| Signal | Test runner detected |
|---|---|
| `package.json` with `"jest"` in devDependencies | Jest |
| `package.json` with `"vitest"` in devDependencies | Vitest |
| `package.json` with `"mocha"` in devDependencies | Mocha |
| `pytest.ini` or `pyproject.toml` with `[tool.pytest.ini_options]` | pytest |
| `go.mod` present (no override) | `go test` (standard library) |
| `Cargo.toml` present (no override) | `cargo test` (standard library) |
| `.rspec` file or `Gemfile` with `"rspec"` | RSpec |
| `build.gradle` with `test { useJUnitPlatform() }` | JUnit 5 |
| `pom.xml` with `junit` dependency | JUnit |
| None of the above | "Unknown — check package manifests" |

## Build System Detection

| Signal | Build system detected |
|---|---|
| `Makefile` present | Make |
| `package.json` with `"scripts"` section | npm/yarn/pnpm scripts |
| `Cargo.toml` | Cargo |
| `go.mod` | Go toolchain |
| `pom.xml` | Maven |
| `build.gradle` | Gradle |
| `Dockerfile` present | Docker |
| `docker-compose*.yml` present | Docker Compose |

## Database Detection

| Signal | Database detected |
|---|---|
| `DATABASE_URL` in `.env.example` starting with `postgres://` | PostgreSQL |
| `DATABASE_URL` in `.env.example` starting with `mysql://` | MySQL/MariaDB |
| `DATABASE_URL` in `.env.example` starting with `mongodb://` or `MONGO_URI` | MongoDB |
| `REDIS_URL` in `.env.example` | Redis |
| `sqlite` in package manifests or `*.db` files in repo root | SQLite |
| ORM config files: `ormconfig.*`, `prisma/schema.prisma` | Detected ORM (Prisma / TypeORM) |
| `alembic.ini` or `migrations/` directory | SQL database with migrations (framework inferred from stack) |
| None of the above | "No database detected — verify with team" |

## Conflict Resolution

If two or more signals conflict (e.g., both `go.mod` and `package.json` are present with framework dependencies), the skill returns:

```
CONFLICT DETECTED
  Signal A: [file] → [stack A]
  Signal B: [file] → [stack B]
  Action required: confirm primary stack before proceeding.
```

The calling agent must halt and ask the user:
> "Stack detection found conflicting signals: [Signal A] and [Signal B]. Which is the primary language and framework for this project?"

The agent does not proceed until the user confirms.

## Output Format

```
stack:
  language: [detected language]
  framework: [detected framework or "none"]
  build_system: [detected build system or "unknown"]
  test_runner: [detected test runner or "unknown"]
  database: [detected database or "none"]
  detection_confidence: [high | medium | low]
  notes: [any ambiguity or conflict notes]
```

`detection_confidence` is:
- **high** — single unambiguous signal
- **medium** — signal present but framework not confirmed (e.g., `go.mod` present, framework not detected)
- **low** — multiple conflicting signals or no signals; user confirmation required before proceeding
