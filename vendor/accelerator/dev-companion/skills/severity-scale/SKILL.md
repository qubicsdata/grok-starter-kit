---
name: severity-scale
description: |
  Use when rating or ranking any finding in a review, audit, or critique. Defines Critical / High / Medium / Low / Info with examples and escalation rules so severity is consistent across reviewers and domains.
---

# Severity Scale

## Levels

### Critical

**Definition:** The finding represents an active, exploitable defect or a correctness failure that will cause data loss, security breach, service outage, or incorrect behaviour in normal production conditions. The code should not be merged or deployed without addressing this.

**Examples:**
- SQL injection via unsanitised user input concatenated into a query
- A null dereference on a code path exercised by every request
- Authentication bypass: an endpoint that skips the auth middleware
- Data corruption: a concurrent write without locking that can silently overwrite another user's record
- Hardcoded secret or credential in source code

**Escalation rule:** Report a Critical finding immediately upon discovery — do not wait until the full review is complete to mention it. State it at the top of the report regardless of where it appears in the code.

### High

**Definition:** The finding represents a defect or structural problem that will cause incorrect behaviour, data exposure, or service degradation under realistic but non-constant conditions. Should be addressed before the next release.

**Examples:**
- Missing error handling on an external API call: service will fail silently when the API is unavailable
- Broken Access Control: missing role check on an admin endpoint that requires authentication but no authorisation
- PII written to application logs (e.g. `logger.info(user)` with a full user object)
- A race condition in a code path that is not exercised on every request but is reachable under concurrent load

### Medium

**Definition:** The finding represents a quality, maintainability, or latent-risk issue that does not cause immediate harm but will make future bugs more likely or make the codebase harder to operate correctly.

**Examples:**
- A function exceeding 50 lines with high cyclomatic complexity — hard to test and easy to misread
- A missing index on a database column used in a `WHERE` clause that will become a performance problem at scale
- Insufficient logging on a sensitive operation — audit trail is incomplete
- Weak token generation (e.g. `Math.random()`) for a non-session, non-auth use case

### Low

**Definition:** The finding represents a minor issue, a code smell, or a pattern that is suboptimal but has limited consequence in practice.

**Examples:**
- Dead code: an exported function that has no callers in the visible codebase
- A TODO comment referencing a known issue that has not been addressed
- Magic number with no named constant — clear from context but could be misread if modified
- Unused variable that doesn't affect runtime behaviour

### Info

**Definition:** An observation that is worth recording but is not a defect. May reveal a pattern when aggregated with other findings.

**Examples:**
- A dependency that is imported but only used in one file — could be scoped more narrowly
- A file that is growing in a direction that will require refactoring within the next few sprints
- A naming inconsistency that is harmless but will become confusing as the codebase grows

---

## Escalation Rules

1. **Any Critical finding → report immediately.** Do not hold it until the end of the review — surface it as soon as it is found, regardless of report order.

2. **Critical findings set the overall verdict to BLOCK.** The overall verdict must be BLOCK if any Critical finding exists, regardless of how many Low/Info findings also exist.

3. **High or Medium only → PASS WITH WARNINGS.** No Criticals, at least one High or Medium.

4. **Low/Info only or no findings → PASS.**

---

## DO NOT Rules

- DO NOT downgrade a Critical finding to spare feelings, to avoid blocking a release, or because the code author says it "probably won't happen in practice" — if the code path exists and the failure is possible, the severity stands
- DO NOT upgrade a Low finding to High to make a report look more thorough — every severity level must reflect realistic consequence
- DO NOT skip Info findings if they reveal a pattern — three Info findings of the same type are a Medium in aggregate; note the pattern explicitly
- DO NOT omit the Summary block — the total count and verdict are required in every review report
