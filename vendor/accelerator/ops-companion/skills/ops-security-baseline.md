---
name: ops-security-baseline
description: |
  7 mandatory questions that must all be answered before any producer agent (pipeline-designer, monitoring-designer, rollback-planner) writes to disk. Deferred answers block producer writes. Used by ops-orchestrator as a gate and by pipeline-designer as a prerequisite check.
---

# ops-security-baseline

Ask the questions below in order, one per turn. Record each answer in `.ops-state.json` under `security_baseline_answers`. If a user skips or defers a question, record the value as `"DEFERRED"`.

**Gate rule:** The gate does NOT pass if any answer is `"DEFERRED"`. Before any producer agent runs a disk write, re-ask every DEFERRED question. A gate attempt with a single DEFERRED item must be blocked with the message:

> "ops-security-baseline gate not cleared. The following question(s) are still deferred: [list]. Answer each before I can generate or write any ops artifact."

---

## Questions (ask in order, one per turn)

### Q1 — Secrets manager

> How will runtime secrets (API keys, DB credentials, certificates) be stored and injected?
>
> Examples: AWS Secrets Manager, HashiCorp Vault, GCP Secret Manager, Kubernetes sealed-secrets, environment variables from CI vault.

Record key: `secrets_manager`

---

### Q2 — Branch protection

> What branch protection rules apply to the main branch?
>
> Examples: required PR reviews, required status checks, no direct push, signed commits.

Record key: `branch_protection`

---

### Q3 — CI least privilege

> What is the least-privilege strategy for the CI service account?
>
> Examples: OIDC short-lived tokens, scoped IAM role, read-only deploy key, no shared long-lived credentials.

Record key: `ci_least_privilege`

---

### Q4 — Dependency scanning

> How will third-party dependency vulnerabilities be detected?
>
> Examples: Dependabot, Renovate, `npm audit`/`pip-audit` in CI, Snyk, OWASP Dependency-Check.

Record key: `dependency_scanning`

---

### Q5 — Container image signing

> If containers are deployed, will images be signed and signature-verified before deploy?
>
> Examples: cosign + Sigstore, Docker Content Trust, or "no containers used."

Record key: `container_signing`

---

### Q6 — Environment promotion gate

> What gate exists between staging and production?
>
> Examples: manual approval step in CI, automated smoke test gate, QA sign-off required, or explicit "staging and prod deploy in parallel — rationale: [state rationale]."

Record key: `environment_promotion_gate`

---

### Q7 — Alerting target

> Where do production alerts go?
>
> Examples: PagerDuty via env var `PAGERDUTY_ROUTING_KEY`, Slack via env var `SLACK_ALERT_WEBHOOK`, email, or "monitoring not yet configured — document this as a gap."

Record key: `alerting_target`

---

## Completion check

After all 7 answers are recorded (no DEFERRED values remain), update `.ops-state.json`:

```json
{
  "security_baseline_answers": {
    "secrets_manager": "<answer>",
    "branch_protection": "<answer>",
    "ci_least_privilege": "<answer>",
    "dependency_scanning": "<answer>",
    "container_signing": "<answer>",
    "environment_promotion_gate": "<answer>",
    "alerting_target": "<answer>"
  }
}
```

Then confirm to the orchestrator: **"ops-security-baseline gate CLEARED. All 7 questions answered."**

---

## Deferred answer handling

- Any answer of "skip", "later", "TBD", "I don't know", or no response → record as `"DEFERRED"`.
- At every subsequent producer gate check, re-ask DEFERRED items before proceeding.
- DEFERRED answers never expire on their own — they must be answered explicitly.
- The gate status is binary: CLEARED (all 7 answered, none DEFERRED) or NOT CLEARED.
