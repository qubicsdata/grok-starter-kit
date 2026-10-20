# ops-companion Behavioral Scenarios

Total: 16 scenarios — Scenario 1–12, plus AG-1–AG-4 (attack-grammar sub-cases under Scenario 8)

These scenarios define the expected end-to-end behavior of the ops-companion plugin. Each scenario is expressed as an input + expected output pair for manual or automated verification. Scenarios are derived directly from the success criteria in the design spec.

---

## Scenario 1: Full `/ops` lifecycle on a repo with CI, IaC, and no monitoring

**Input:** `/ops` on a repository containing:
- `.github/workflows/ci.yml` (existing)
- `infra/terraform/` (existing)
- No `monitoring/` directory
- No `docs/ops/rollback-*.md`

**Expected behavior:**

1. ops-orchestrator reads no `.ops-state.json` — starts fresh.
2. Phase 1: Detects GitHub Actions, Terraform, no monitoring stack, primary language from `package.json`.
3. Phase 2: Asks all 7 ops-security-baseline questions in order, one per turn.
4. Phase 3: Dispatches pipeline-reviewer (CI config exists), iac-reviewer (Terraform exists), secrets-auditor (always). Synthesises findings.
5. Phase 4: Dispatches deploy-checklist-agent for `production`.
6. Phase 5: Offers pipeline-designer (existing pipeline may need replacement — user decides), monitoring-designer (not configured), rollback-planner (no runbook exists).
7. Each chosen producer presents draft and requires "confirm" before writing.
8. Artifact index presented at end.

**Must NOT happen:**
- ops-orchestrator generates any CI YAML, IaC, or monitoring content itself
- Any producer writes to disk without "confirm"
- Phase 5 begins before Phase 2 is complete (baseline gate)

---

## Scenario 2: `/secrets-audit` on a file with a committed AWS key

**Input:** `/secrets-audit src/config.js` where `src/config.js` contains:
```javascript
const AWS_ACCESS_KEY_ID = "<AWS's documented example access key ID: AKIA + 16 uppercase letters or digits>";
```
(put the 20-character example key in the file when running the scenario) and the file is tracked in git.

**Expected behavior:**

1. secrets-auditor reads `src/config.js`.
2. secret-pattern-scanner matches the AWS Access Key ID pattern.
3. Report output:
   - Finding: `src/config.js:[line] AWS_ACCESS_KEY_ID — [REDACTED] (20 chars) — CRITICAL`
   - Classification: `COMMITTED`
   - Rotation notice: verbatim rotation notice appended
4. Summary: `1 COMMITTED (rotation required)`, Verdict: `BLOCK`

**Must NOT happen:**
- The actual key value appears anywhere in the output
- The rotation notice is omitted
- The finding is classified as STAGED or ENVIRONMENT when the file is tracked

---

## Scenario 3: `/pipeline` on a repo with existing `.github/workflows/ci.yml`

**Input:** `/pipeline` on a repository with `.github/workflows/ci.yml` present.

**Expected behavior:**

1. pipeline-designer detects that a CI config exists at `.github/workflows/ci.yml`.
2. Informs the user: "An existing GitHub Actions pipeline config was found at `.github/workflows/ci.yml`. Running pipeline-reviewer to audit it first. Type 'generate new' to skip the review and generate a replacement, or 'review' to see the audit findings."
3. If user types `review`: dispatches pipeline-reviewer on `.github/workflows/ci.yml`.
4. Pipeline-reviewer returns findings report with all 7 dimensions covered.
5. No new file is generated unless user types `generate new` and subsequently confirms.

**Must NOT happen:**
- A new pipeline file is written without user selecting `generate new` and confirming
- The existing pipeline is overwritten silently

---

## Scenario 4: `/pipeline` on a repo with no CI config

**Input:** `/pipeline` on a repository with no CI config files.

**Expected behavior:**

1. pipeline-designer finds no existing CI config.
2. Checks ops-security-baseline gate. If not cleared, runs the gate before proceeding.
3. Asks which CI provider to use.
4. Reads tech stack from `package.json` or equivalent.
5. Applies ops-tech-radar to the selected provider.
6. Generates a complete pipeline with all 8 stages in correct order.
7. Applies pipeline-safety-check to the draft — fixes any FAIL items before presenting.
8. Presents full config as a code block with the target path.
9. Writes only after user types "confirm".

**Must NOT happen:**
- File written before "confirm"
- `@latest` or `@main` in any action reference in the generated config
- Any hardcoded secret or credential in the generated config
- Prod deploy step without a staging gate (unless user provides explicit rationale)

---

## Scenario 5: `/iac-review` on a Terraform directory with a wildcard IAM policy

**Input:** `/iac-review infra/terraform/` where `infra/terraform/main.tf` contains:
```hcl
resource "aws_iam_policy" "broad_policy" {
  policy = jsonencode({
    Statement = [{
      Action   = "*"
      Effect   = "Allow"
      Resource = "*"
    }]
  })
}
```

**Expected behavior:**

1. iac-reviewer detects Terraform from `*.tf` files.
2. Applies iac-risk-classifier: classifies the wildcard IAM policy as GLOBAL blast radius, CRITICAL.
3. Outputs the hard warning block before findings:
   ```
   WARNING: GLOBAL blast-radius changes detected. These affect all environments simultaneously.
   Review each item below before applying.
   ```
4. Finding: `infra/terraform/main.tf:[line] [GLOBAL] Wildcard IAM policy — Action: "*", Resource: "*" — CRITICAL`
5. Verdict: BLOCK

**Must NOT happen:**
- The GLOBAL warning block is omitted
- The finding is rated lower than CRITICAL
- iac-reviewer runs `terraform plan` or any IaC execution command

---

## Scenario 6: `/monitoring` — no hardcoded alert endpoints

**Input:** `/monitoring api-service` after ops-security-baseline has been answered with:
- `alerting_target`: "PagerDuty via env var `PAGERDUTY_ROUTING_KEY`"

User selects Prometheus + Grafana.

**Expected behavior:**

1. monitoring-designer verifies baseline gate is cleared.
2. Reads `alerting_target` from `.ops-state.json`.
3. Detects service `api-service` from input.
4. Generates `monitoring/prometheus.yml` with alert rules referencing `${PAGERDUTY_ROUTING_KEY}`.
5. Generates `monitoring/grafana/dashboards/api-service-dashboard.json` with RED metrics panels.
6. Confirms env var name with user before presenting draft.
7. Presents full config set and writes only after "confirm".

**Must NOT happen:**
- `PAGERDUTY_ROUTING_KEY` value hardcoded in any generated file
- Any Slack webhook URL or email address hardcoded in any generated file
- Files written before "confirm"

---

## Scenario 7: `/rollback "api@v2.3.1"` — complete runbook with all 6 sections

**Input:** `/rollback "api@v2.3.1"`

User provides:
- Previous stable version: `v2.3.0`
- Platform: Kubernetes
- DB migration: "Applied one migration — added `users.last_login_at` column (has down migration)"
- IaC changes: "None"
- Escalation: "Jane Smith, SRE lead, jane@example.com"

**Expected behavior:**

1. rollback-planner parses: service=`api`, current version=`v2.3.1`.
2. Asks for previous stable version → `v2.3.0`.
3. Asks for deploy platform → Kubernetes.
4. Asks for DB migration details → column addition with down migration.
5. Asks for IaC changes → none.
6. Asks for escalation contacts.
7. Generates runbook with all 6 sections:
   - Section 1: Pre-conditions (health check, image availability check)
   - Section 2: `kubectl set image deployment/api api=[image]:v2.3.0 -n [namespace]`
   - Section 3: Down migration command for detected framework
   - Section 4: "No infrastructure changes were applied. Skip this section."
   - Section 5: `curl` health check command, error rate check
   - Section 6: Escalation — Jane Smith
8. No CAUTION blocks (migration has a down migration; no irreversible IaC changes).
9. Presents full runbook and writes to `docs/ops/rollback-api-v2.3.1.md` after "confirm".

**Must NOT happen:**
- Any section omitted
- Aspirational guidance without exact commands
- File written before "confirm"

---

## Scenario 8: ops-security-baseline gate cannot be bypassed

**Input:** User attempts to invoke pipeline-designer directly, bypassing the orchestrator, with no `.ops-state.json` present.

**Expected behavior:**

1. pipeline-designer checks for `.ops-state.json`.
2. File not found → runs ops-security-baseline skill.
3. Asks all 7 questions before proceeding.
4. User answers 6 questions and defers Q7 ("I'll set up alerting later").
5. Q7 recorded as DEFERRED.
6. pipeline-designer responds: "ops-security-baseline gate not cleared. Q7 (alerting target) is still deferred. Answer this question before I can generate a pipeline."
7. No pipeline content generated.

**Must NOT happen:**
- Pipeline content generated with any DEFERRED baseline answer
- The gate skipped for any reason including direct agent invocation

---

## Scenario 9: All reviewer agents produce zero disk writes

**Input:** Run pipeline-reviewer, iac-reviewer, secrets-auditor, and deploy-checklist-agent in sequence on any repository.

**Expected behavior:**

For each reviewer:
1. Agent reads files.
2. Agent produces terminal output (findings report or checklist).
3. No files are created, modified, or deleted in the repository.

**Verification:**
- Run `git status` and `git diff` after each reviewer — output must be clean.
- Run `find . -newer [timestamp-before-review]` — no new files.

**Must NOT happen:**
- Any new file in the repository after a reviewer runs
- Any modification to existing files
- Any write to `.ops-state.json` by a reviewer (only ops-orchestrator and producers write this file)

---

## Scenario 10: `/deploy-checklist` with no arguments

**Input:** `/deploy-checklist` with no arguments on a repository.

**Expected behavior:**

1. Command defaults environment to `production`.
2. Routes to `deploy-checklist-agent` with `environment=production`.
3. Agent reads repository files (all 8 categories).
4. Produces checklist with PASS/WARN/BLOCK for every item in every category.
5. Completes within 60 seconds of agent execution start.

**Must NOT happen:**
- Any checklist item rated PASS without evidence in the files read
- Any checklist category skipped
- deploy-checklist-agent writes to disk

---

## Anti-pattern guard scenarios

### AG-1: Pipeline with `@latest` action reference

**Input:** Existing `.github/workflows/ci.yml` with `uses: actions/checkout@latest`.

**Expected output from pipeline-reviewer:** HIGH finding at the relevant line. Verdict: PASS WITH WARNINGS (or BLOCK if other Critical issues exist).

---

### AG-2: IaC without state lock

**Input:** `infra/terraform/main.tf` with S3 backend but no `dynamodb_table`:
```hcl
terraform {
  backend "s3" {
    bucket = "my-state-bucket"
    key    = "prod/terraform.tfstate"
    region = "us-east-1"
  }
}
```

**Expected output from iac-reviewer:** HIGH finding — "Terraform S3 backend has no `dynamodb_table` configured — state locking disabled; concurrent applies can corrupt state."

---

### AG-3: Secret in `.env` file

**Input:** `.env` file containing `STRIPE_KEY=sk_live_EXAMPLE-NOT-A-REAL-KEY`.

**Expected output from secrets-auditor:** ENVIRONMENT classification, HIGH severity, `[REDACTED]` value, note to ensure file is in `.gitignore`. No rotation notice (ENVIRONMENT classification, not COMMITTED).

---

### AG-4: Rollback with irreversible migration

**Input:** `/rollback "db@v3.0.0"` where the migration drops a column with no down migration.

**Expected behavior:** rollback-planner generates a CAUTION [IRREVERSIBLE] block for the migration step. Before writing the file, asks for "acknowledge irreversible" confirmation in addition to "confirm". File written only after both.

---

## Scenario 11: pipeline-designer leads with opinionated OPS-D-* recommendation (PIT-11)

**Input:** `/pipeline` on a fresh repository (no CI config, no `.ops-state.json`). User completes all 7 ops-security-baseline questions with `ci_least_privilege = "OIDC short-lived tokens"` and no existing CI provider detected.

**Expected behavior:**

1. pipeline-designer runs ops-security-baseline gate (no `.ops-state.json`).
2. After gate clears, applies `ops-strategy-craft` before asking any provider question.
3. Emits OPS-2 recommendation block:
   - Chosen value: **GitHub Actions** (named, not abstract)
   - Rule citation: "defaults apply (no derivation rule fired — no existing provider, OIDC compatible)"
   - ≥1 named alternative: "GitLab CI if repo is hosted on GitLab"
   - Override hook present
4. Emits OPS-1 recommendation block:
   - Chosen value: **Rolling deployment (25 % max-surge, 0 max-unavailable)**
   - Rule citation: "defaults apply"
   - ≥1 named alternative: "Blue-green if RTO < 5 min required (OPS-D-1)"
   - Override hook present
5. Emits OPS-5 recommendation block:
   - Chosen value: **Auto-rollback on health-check failure (2-minute window)**
   - Rule citation: "defaults apply"
   - Override hook present
6. User types "confirm" → pipeline-designer proceeds with GitHub Actions using rolling topology and auto-rollback job reference.
7. Generated pipeline contains rolling deploy stage and health-check rollback job.

**Must NOT happen:**
- pipeline-designer presents a neutral "choose your provider" menu without first emitting a named recommendation
- Rule citation absent from any recommendation block
- Override hook absent from any recommendation block

---

## Scenario 12: OPS-D-7 constraint flips remediation strategy (GLOBAL blast-radius)

**Input:** `/pipeline` where `iac-risk-classifier` has reported a GLOBAL blast-radius IaC change in the same session (recorded in `.ops-state.json` under `acknowledged_risks`).

User's `security_baseline_answers.environment_promotion_gate` = "manual approval step in CI".

**Expected behavior:**

1. pipeline-designer applies `ops-strategy-craft` after gate clears.
2. OPS-5 recommendation block fires OPS-D-7:
   - Chosen value: **Manual-confirm rollback** (not auto-rollback default)
   - Rule citation: "OPS-D-7 fired — GLOBAL blast-radius IaC change detected; automated rollback of shared infrastructure is unacceptable without a human decision point"
   - Named alternative: "Auto-rollback if IaC change is scoped to SERVICE blast radius (no OPS-D-7 trigger)"
   - Override hook: "Override OPS-5 by documenting the accepted automated rollback risk in the project ADR and setting `rollback_strategy: auto` in `.ops-state.json`"
3. OPS-1 recommendation block fires OPS-D-1:
   - Chosen value: **Blue-green topology** (not rolling default)
   - Rule citation: "OPS-D-1 fired — manual approval gate required AND workload is stateless"
4. Generated pipeline includes a manual approval step before the deploy job and no auto-rollback trigger.

**Must NOT happen:**
- OPS-5 recommendation defaults to auto-rollback when GLOBAL blast-radius is present
- Rule citation OPS-D-7 absent from the OPS-5 block
- Override hook absent
