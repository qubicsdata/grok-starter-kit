# security-companion

## Overview

security-companion is a design-level application-security and threat-modeling companion. It works at the **architecture and design stage** — before code is written — to surface threats, classify trust boundaries, map attack surfaces, and produce threat register entries with risk scores, mitigations, and security acceptance criteria.

**What it does:**
- STRIDE threat analysis with a ranked threat register (likelihood × impact, 1–25)
- Trust-boundary and attack-surface mapping per data-flow descriptions
- Security design review across authn, authz, session, cryptographic choices, input-trust, and secrets-at-design
- Abuse-case elicitation with BDD-style security acceptance criteria attached to user stories
- Scanning strategy advisory for SAST, DAST, and dependency scanning — advisory only, no scanner execution

**What it does NOT do:**
- Code-level OWASP Top 10 review → use `dev-companion / /security-review [path]`
- Secret scanning in committed files → use `ops-companion / /secrets-audit`
- Dependency CVE scanning → use `dependency-auditor / /audit [manifest]`
- Compliance framework mapping → use `compliance-companion / /explain`
- Running system or live traffic analysis — scope is design and architecture documents only

## Installation

1. Copy the `security-companion/` directory into your accelerator plugins directory.
2. Register the plugin in your fleet `registry.json`.
3. Verify `ai-baseline` is installed — it is a required dependency.

## Commands

| Command | Description | When to use |
|---|---|---|
| `/stride [description]` | STRIDE threat analysis on an architecture or data-flow description. Returns a ranked threat register with risk scores and mitigations. | When you have a design or DFD and need systematic threat coverage before implementation begins |
| `/threat-model [description or path]` | Full threat modeling session — attack surface mapping, STRIDE, design review, abuse cases, and confirm-gated document write to `docs/threat-models/`. | When you need a complete, written threat model artifact for a feature or system |
| `/attack-surface [description]` | Map trust zones, entry points, and cross-boundary data flows. Returns an attack surface inventory without running full STRIDE. | When scoping what is exposed before deciding where to invest threat analysis effort |
| `/security-review [doc or description]` | Design-level security review of authentication model, authorization design, session management, cryptographic choices, and input-trust model. No code scanning. | When reviewing an architecture doc or ADR for security posture before implementation |
| `/abuse-cases [description or story]` | Derive misuse cases and BDD-style security acceptance criteria from a feature description or user stories. | When hardening user stories with adversarial scenarios and testable security conditions |
| `/scan-strategy [stack description]` | Advise on SAST, DAST, and dependency-scanning tooling selection and SDLC gate placement. Advisory only — does not run scanners. | When setting up or auditing a security scanning pipeline for a new stack or project |

## Dependencies

- requires: ai-baseline
- Cross-link: `dev-companion / /security-review` — code-level OWASP Top 10 review (invoke after threat modeling surfaces implementation risks)
- Cross-link: `ops-companion / /secrets-audit` — hardcoded secret scanning in committed or staged files
- Cross-link: `dependency-auditor / /audit` — dependency CVE and license scanning
- Cross-link: `compliance-companion` — regulatory framework mapping when SEC-D-5 (regulatory-exposure-present) trigger fires

## Architecture

| Agent | Purpose | Model tier |
|---|---|---|
| `security-companion-orchestrator` | Routes all commands, enforces gate order (scope-guard → cost-gate → Opus agents → pii-scrub), records audit entries | claude-sonnet-4-6 |
| `attack-surface-mapper` | Maps trust zones, entry points, and cross-boundary data flows from an architecture description | claude-opus-4-8 |
| `stride-analyst` | Runs STRIDE analysis across all 6 categories; produces a ranked threat register validated against threat-register-schema | claude-opus-4-8 |
| `security-design-reviewer` | Reviews authn/authz/session/crypto/input-trust/secrets design across 6 concern areas; emits HANDOFF blocks for code-level findings | claude-sonnet-4-6 |
| `abuse-case-elicitor` | Derives misuse cases and BDD-style security acceptance criteria from feature descriptions or user stories | claude-sonnet-4-6 |
| `scan-strategy-advisor` | Advises on SAST/DAST/dependency-scan tooling and CI gate placement; advisory only, never executes scanners | claude-sonnet-4-6 |
| `threat-model-writer` | Sole disk-write agent; assembles the full threat model document, presents draft, and requires explicit CONFIRM before writing | claude-sonnet-4-6 |
| `spec-enricher` | Injects SEC-1..SEC-8 requirements during `/enrich` runs when auth, sensitive data, API boundaries, or untrusted input are present | claude-sonnet-4-6 |
| `audit-trail-agent` | Append-only audit logger (ai-baseline infra agent) | claude-haiku-4-5-20251001 |

## Workflow examples

### Run STRIDE on a new microservice

