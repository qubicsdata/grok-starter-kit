# incident-companion

A Claude Code plugin for engineering teams that systematizes both the *during* and *after* phases of incident management. Five independently-invocable agents cover runbook generation, escalation template creation, incident timeline reconstruction, post-mortem authoring, and post-mortem adversarial critique.

**Core principle:** The plugin is a structured writing assistant, not an incident responder. It never assumes system topology, never invents events it was not given, and never assigns blame to individuals. Every artifact it produces is reviewed by the user before being written to disk.

## What It Does Not Do

- Does not monitor systems, send alerts, or integrate with PagerDuty/OpsGenie
- Does not create tickets or update project management tools
- Does not auto-detect incidents from logs
- Does not remediate anything — all remediation is the engineer's job
- Does not retain state between invocations — every agent is stateless

## Installation

Copy the `incident-companion/` directory into your project's `.claude/plugins/` directory (or the global Claude Code plugins directory), then restart Claude Code.

## Commands

| Command | Description |
|---------|-------------|
| `/runbook "system-name"` | Generate a runbook for a named system/service |
| `/escalation "team-name"` | Generate an escalation template for a named team |
| `/timeline` | Reconstruct a timeline from raw evidence (inline or `--file path`) |
| `/postmortem "incident-name"` | Author a post-mortem via guided Q&A |
| `/critique-postmortem "path or description"` | Run adversarial critique on a post-mortem |
| `/incident "incident-name"` | End-to-end orchestrator: timeline → post-mortem → critique → action items |

## Quick Start

```
# Generate a runbook for a service
/runbook "payments-service"

# Reconstruct an incident timeline from a log file
/timeline --file /tmp/incident-2026-06-19.log

# Author a complete post-mortem
/postmortem "payments outage 2026-06-19"

# Run adversarial critique on an existing post-mortem
/critique-postmortem "postmortems/2026-06-19-payments-outage.md"

# Full end-to-end workflow
/incident "database failover 2026-06-19"
```

## Artifacts Produced

| Artifact | Command | Default Location | Write Gate |
|----------|---------|-----------------|-----------|
| Runbook | `/runbook` | `runbooks/[slug].md` | Explicit confirmation |
| Escalation template | `/escalation` | `runbooks/escalation-[slug].md` | Explicit confirmation |
| Timeline (text) | `/incident` step 1 | `postmortems/timeline-[slug].txt` | User opts in |
| Post-mortem | `/postmortem` | `postmortems/YYYY-MM-DD-[slug].md` | Explicit confirmation |
| Action item export | `/incident` step 4 | `postmortems/action-items-[slug].md` | User opts in |

## Blameless Culture

The `blameless-culture` skill runs before every draft is presented. Any blame-assigning language surfaces as a flagged violation — the draft is not shown until violations are addressed. `postmortem-critic` treats unresolved blame language as a Critical finding.

---

Author: <your-name> — you@example.com

## Dependencies

- requires: ai-baseline
