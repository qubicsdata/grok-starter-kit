---
name: security-baseline
description: Asks 6 mandatory security questions one at a time and blocks progression to scaffold until all are answered. Invoke within the requirements phase, after env promotion strategy is captured. All 6 questions must be answered; deferred items are re-asked before scaffold.
---

## Purpose

The security-baseline skill ensures that every greenfield project addresses foundational security concerns before a single file is scaffolded. It asks 6 questions in sequence, one at a time, and records the answers in `docs/requirements.md` under `## Security Baseline`. No question may be skipped or deferred past the scaffold gate.

## The 6 Security Questions

Ask these questions in order, one per turn, waiting for the user's answer each time:

1. **Secrets management**: How will secrets (API keys, database credentials, private keys) be stored and accessed at runtime? (e.g. environment variables injected at deploy time, a secrets manager such as HashiCorp Vault / AWS Secrets Manager / GCP Secret Manager, sealed Kubernetes secrets)

2. **Branch protection**: What branch protection rules will be applied to the main branch? (e.g. required PR reviews, status checks must pass, no direct push to main, signed commits required)

3. **Dependency scanning**: How will third-party dependency vulnerabilities be detected? (e.g. Dependabot, Renovate, `npm audit` / `pip-audit` in CI, Snyk, OWASP Dependency-Check)

4. **CI service account privileges**: What is the least-privilege strategy for CI service accounts? (e.g. read-only deploy keys, OIDC short-lived tokens, scoped IAM roles, no shared long-lived credentials)

5. **SAST (Static Application Security Testing)**: Will SAST be run in CI? If so, which tool? (e.g. Semgrep, CodeQL, Bandit for Python, gosec for Go, SonarQube — or explicitly "none, with documented rationale")

6. **Authentication model**: What is the authentication model for end users or system consumers? (e.g. OAuth 2.0 / OIDC with a provider, API keys, mTLS for service-to-service, no auth because internal-only service — must be explicit)

## Handling Deferred Answers

If the user answers "I don't know", "TBD", "later", or equivalent for any question:

- Record the question as `DEFERRED` in the `## Security Baseline` section
- Add it to `open_items` in `.greenfield-state.json`
- Continue to the next question — do not block the rest of the dialogue
- When the greenfield-checklist gate runs before scaffold, re-ask all DEFERRED security questions before allowing the gate to pass
- The gate DOES NOT pass if any security baseline answer remains DEFERRED

## Security Baseline Section Format

The `requirements-agent` appends this section to `docs/requirements.md` after all 6 answers are collected:

```markdown
## Security Baseline

1. **Secrets management**: [user's answer]
2. **Branch protection**: [user's answer]
3. **Dependency scanning**: [user's answer]
4. **CI service account privileges**: [user's answer]
5. **SAST**: [user's answer — or "None — rationale: [stated rationale]"]
6. **Authentication model**: [user's answer]
```

If any answer is DEFERRED at the time of writing, include:
```
   _Status: DEFERRED — must be resolved before scaffold generation._
```

## Rules

DO NOT skip any of the 6 questions. All 6 must be asked in every session that progresses through the security baseline phase.

DO NOT allow scaffold generation to proceed if any security baseline question remains DEFERRED — re-ask deferred items at the greenfield-checklist gate.

STOP and surface this message if the user attempts to skip the security baseline entirely:

> The security baseline is a mandatory phase of greenfield project initialisation and cannot be skipped. These 6 questions must be answered (or explicitly deferred and revisited) before scaffold generation proceeds. Let's work through them one at a time.

DO NOT accept a blank answer as a valid response. If the user submits a blank answer, restate the question with a prompt for a specific approach.

DO NOT interpret "none" as acceptable for questions 1, 2, 3, 4, and 6 without the user providing an explicit rationale. For question 5 (SAST), "none" is acceptable if the user provides a documented rationale.
