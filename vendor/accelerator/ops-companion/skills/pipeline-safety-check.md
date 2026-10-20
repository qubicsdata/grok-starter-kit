---
name: pipeline-safety-check
description: |
  Validates a pipeline file or draft against a fixed checklist: pinned versions, no hardcoded secrets, required stages present, fail-fast order correct. Returns PASS / FAIL with specific line-level findings. Used by pipeline-reviewer on every review and by pipeline-designer before presenting any draft to the user.
---

# pipeline-safety-check

Apply every check below to the pipeline file or draft. Return PASS if all checks pass, or FAIL with the specific line-level findings that triggered failure.

---

## Checks

### 1. No hardcoded secrets (CRITICAL if found)

Delegate to `secret-pattern-scanner`. If any secret is found:
- File a CRITICAL finding: `[file:line] Hardcoded secret — [type]. Remove and inject via the CI secret/variable mechanism.`
- Verdict is automatically FAIL.

### 2. All action/image versions pinned (HIGH if violated)

For each `uses:`, `image:`, `FROM`, or `docker pull` reference:
- `@latest`, `@main`, `@master`, `:latest` → HIGH finding: `[file:line] Unpinned reference '[value]' — pin to an exact SHA or version tag.`
- Any reference without a version tag or SHA → HIGH finding.

### 3. Required stages present (HIGH if any missing)

The following stages must all be present (detect by job/step names or script commands):
1. Lint
2. Unit tests
3. Build
4. Dependency scan (`npm audit`, `pip-audit`, `trivy`, `grype`, `snyk`, or equivalent)
5. SAST (Semgrep or equivalent)

For each missing stage: `Missing required stage: [stage name] — add this stage before the pipeline is production-ready.`

### 4. Fail-fast order (MEDIUM if violated)

Lint and unit tests must run before build and dependency scan. If build or scan precedes lint/test:
- MEDIUM finding: `[file:line] Fail-fast order violated — [build/scan stage] runs before [lint/test stage]. Reorder so lint and tests run first.`

### 5. No environment promotion without a staging gate (CRITICAL if violated)

If a job deploys to a production environment (job name contains `prod`, `production`, or `deploy` with no `staging` predecessor):
- Check for a manual approval step, environment gate, or required status check gating prod deploy.
- If absent: CRITICAL finding: `Production deploy job '[job-name]' has no staging gate. Add a manual approval step or required staging environment before this job runs.`

### 6. Least-privilege service account (HIGH if absent)

Check for comments or configuration indicating a least-privilege service account or OIDC token usage. If absent:
- HIGH finding: `No least-privilege service account configuration found. Add a comment or configuration specifying the scoped IAM role or OIDC short-lived token strategy.`

### 7. Cache correctness (MEDIUM if suspect)

For each `cache:` block:
- If the cache key does not include a lock file hash (`package-lock.json`, `yarn.lock`, `requirements.txt`, `go.sum`, `Cargo.lock`, `pom.xml`), file a MEDIUM finding: `[file:line] Cache key does not include lock file hash — stale cache may produce non-reproducible builds.`

---

## Output format

```
## pipeline-safety-check

### CRITICAL
- [file:line] Finding

### HIGH
- [file:line] Finding

### MEDIUM
- [file:line] Finding

### Summary
N critical, N high, N medium
Verdict: PASS | FAIL
```

- **FAIL** — any CRITICAL or HIGH finding
- **PASS** — MEDIUM or below only

If the pipeline is a draft (not yet written to disk), substitute `[draft:line]` for the file reference.
