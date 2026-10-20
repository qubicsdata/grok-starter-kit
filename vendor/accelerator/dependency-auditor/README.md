# dependency-auditor

A Claude Code plugin that gives development teams a clear, actionable picture of their dependency health across five concerns: license compliance, CVE surface, freshness, upgrade path planning, and supply chain risk.

## ⚠️ Hard Limitation — No Live Scanning

**This plugin reads manifest files and lock files only.** It does NOT invoke `npm audit`, `pip-audit`, `govulncheck`, `cargo audit`, `bundle-audit`, or any external vulnerability database at runtime.

CVE findings are based on the model's training knowledge of known vulnerable version ranges. They may be incomplete or out of date. **Every CVE finding carries a mandatory advisory disclaimer.** For production-grade CVE assurance, run the appropriate live scanner after reviewing this report.

## What It Does

1. **License compliance** — SPDX analysis, GPL contamination chain tracing, unknown-license flagging
2. **CVE surface** — advisory-based detection of known-vulnerable version ranges (with mandatory disclaimer)
3. **Freshness classification** — Active / Stable-Maintenance / Slow / Stale / Abandoned per package
4. **Upgrade path planning** — prioritised upgrade list, semver delta, known breaking-change surface
5. **Supply chain risk** — typosquatting candidates, dependency confusion, bus-factor, maintainer anomalies

## Supported Ecosystems

| Ecosystem | Manifest | Lock file |
|---|---|---|
| Node.js (npm) | `package.json` | `package-lock.json` |
| Node.js (yarn) | `package.json` | `yarn.lock` |
| Node.js (pnpm) | `package.json` | `pnpm-lock.yaml` |
| Python (pip) | `requirements.txt` | `requirements.txt` (pinned) |
| Python (Poetry) | `pyproject.toml` | `poetry.lock` |
| Python (Pipenv) | `Pipfile` | `Pipfile.lock` |
| Go | `go.mod` | `go.sum` |
| Rust | `Cargo.toml` | `Cargo.lock` |
| Ruby | `Gemfile` | `Gemfile.lock` |
| Java (Maven) | `pom.xml` | — |
| Java (Gradle) | `build.gradle` / `build.gradle.kts` | `gradle.lockfile` (if present) |

**Monorepo support:** All agents discover manifests recursively from the root path. Findings are attributed to their specific manifest path.

## Commands

| Command | Description |
|---|---|
| `/audit [path]` | Full five-concern audit via audit-orchestrator |
| `/licenses [path]` | License compliance only |
| `/cve [path]` | CVE surface only (advisory disclaimer always shown) |
| `/freshness [path]` | Freshness classification only |
| `/upgrade [path]` | Upgrade path planning only |
| `/supply-chain [path]` | Supply chain risk only (uses Opus — may be slower) |

`path` defaults to `.` (current directory) when omitted.

## Artifacts

| Artifact | When | Written by |
|---|---|---|
| `docs/dependency-audit-[YYYY-MM-DD].md` | After `/audit`, on explicit user confirmation | audit-orchestrator only |
| Console findings report | Every command | Always — no confirmation needed |

**No agent other than audit-orchestrator writes to disk.** Individual concern commands are permanently read-only.

## Agent Topology

```
User invokes /audit [path]
       │
       ▼
audit-orchestrator
       │
       ├─── manifest-parser      (Haiku: parse + inventory)
       │         │
       │         └── structured package list → shared context
       │
       ├─── license-agent        (Sonnet: SPDX + compat matrix)
       ├─── cve-surface-agent    (Sonnet: advisory-based CVE flags)
       ├─── freshness-agent      (Sonnet: staleness classification)
       ├─── upgrade-planner      (Sonnet: semver delta + migration notes)
       └─── supply-chain-agent   (Opus: adversarial provenance analysis)
                    │
                    ▼
        Aggregated Audit Report
        (console + optional file write on confirmation)
```

## Installation

Copy the `dependency-auditor/` directory into your project's `.claude/plugins/` directory (or the global Claude Code plugins directory), then restart Claude Code.

## Quick Start

```
# Full audit of current directory
/audit

# License check only, scoped to backend
/audit ./backend

# CVE surface check
/cve

# Supply chain analysis (Opus — slower but thorough)
/supply-chain
```

## Author

<your-name> — you@example.com

## Version

1.0.0

## Dependencies

- requires: ai-baseline
