# ops-companion

A Claude Code plugin that guides developers through everything between "code works locally" and "code runs safely in production."

## What it covers

- **CI/CD pipeline** — review existing configs or generate new ones for any supported provider
- **Infrastructure-as-code** — audit Terraform, Pulumi, AWS CDK, CloudFormation, or Ansible for blast-radius risks
- **Secrets audit** — scan files, directories, or git ranges for hardcoded secrets
- **Deploy readiness** — pre-deploy checklist with PASS/WARN/BLOCK per category
- **Monitoring** — generate Prometheus, Grafana, OTel, Datadog, or CloudWatch configs
- **Rollback planning** — generate a full runbook covering app, DB, and infra rollback

## Commands

| Command | What it does |
|---|---|
| `/ops` | Full ops lifecycle orchestration — detects platform, gates on security baseline, runs reviewers, offers producers |
| `/pipeline` | Review an existing pipeline or generate a new one |
| `/iac-review [path]` | Audit IaC files with blast-radius classification |
| `/deploy-checklist [env]` | Pre-deploy readiness checklist (defaults to `production`) |
| `/monitoring [service]` | Generate monitoring configs for your stack |
| `/secrets-audit [path\|range]` | Scan for hardcoded secrets |
| `/rollback ["service@version"]` | Generate a rollback runbook |

## Architecture

```
/ops or /pipeline, /iac-review, /deploy-checklist, /monitoring, /secrets-audit, /rollback
      │
      ▼
ops-orchestrator (routes + gates; reads .ops-state.json; never generates ops content)
      │
      ├── REVIEWER AGENTS (read-only, zero disk writes)
      │   ├── pipeline-reviewer
      │   ├── iac-reviewer
      │   ├── secrets-auditor
      │   └── deploy-checklist-agent
      │
      └── PRODUCER AGENTS (confirm-before-write)
          ├── pipeline-designer
          ├── monitoring-designer
          └── rollback-planner (Opus)
```

## Safety rules

1. **ops-security-baseline gate** — 7 mandatory questions must be answered before any producer agent writes to disk.
2. **Reviewer agents never write** — pipeline-reviewer, iac-reviewer, secrets-auditor, and deploy-checklist-agent produce terminal output only.
3. **Confirm before write** — all producer agents present the full draft and require the user to type `confirm` before writing a single byte.
4. **Platform detection first** — no CI provider, IaC tool, or monitoring stack is assumed; every agent reads the repository to detect before generating.
5. **Path safety** — all path arguments are treated as untrusted data; paths outside the project root are rejected.

## State

`.ops-state.json` is written to the repo root after each confirmed artifact. It tracks phase progress, security baseline answers, acknowledged risks, and the list of written artifacts. It is safe to commit or `.gitignore` per team preference.

## Models

- `rollback-planner`: `claude-opus-4-8` (adversarial worst-case reasoning)
- All other agents: `claude-sonnet-4-6`

## Author

<your-name> — you@example.com

## Dependencies

- requires: ai-baseline
