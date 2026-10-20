# Behavioral Test Scenarios — security-companion
Generated: 2026-07-03T00:00:00Z
Coverage: 12 scenarios across 7 agents

---

## Scenario 1: /stride produces a complete threat register with all 6 STRIDE categories covered

**Command/Trigger:** `/stride "A payment processing API built on Node.js. The API exposes REST endpoints to an external web frontend over HTTPS. Authenticated users POST payment data to /api/v1/payments. The service validates inputs, calls a third-party Stripe API, writes transaction records to a PostgreSQL database, and sends a confirmation event to an internal audit queue. JWT tokens (RS256) are issued at /auth/login with 15-minute expiry. An admin UI at /admin is restricted to internal IP range only."`
**Given:** A valid architecture description with identifiable trust zones, entry points, and cross-boundary data flows — no source code, no dependency manifests
**When:** `/stride` is invoked with the architecture description above
**Then:** The orchestrator runs scope-guard (returns SCOPE OK), two cost-gate PROCEED checks, attack-surface-mapper, stride-analyst; the final output is a ranked threat register containing at least one threat entry under each of the six STRIDE categories: Spoofing (S), Tampering (T), Repudiation (R), Information Disclosure (I), Denial of Service (D), Elevation of Privilege (E); each entry includes Likelihood, Impact, Risk score, Mitigation, Mitigation owner, and Mitigation pattern fields; the summary line shows "Threats identified: N (S:>=1 T:>=1 R:>=1 I:>=1 D:>=1 E:>=1)"
**Verifies:** stride-analyst STRIDE coverage requirement — all 6 categories must appear and zero-finding categories must include explicit rationale per the agent spec

---

## Scenario 2: /threat-model runs the full pipeline and presents the assembled document before any write

**Command/Trigger:** `/threat-model "A SaaS document collaboration platform. Users authenticate via OAuth2/OIDC (Google provider). Documents are stored in S3 with presigned URLs. Real-time edits use WebSocket connections to a Go service. Document metadata is stored in Postgres. An internal background worker processes async export jobs and writes to an outbound S3 bucket. The admin API is protected by API keys stored in AWS Secrets Manager."`
**Given:** A valid architecture description — no source code or manifests in the input; session budget has not been exceeded
**When:** `/threat-model` is invoked with the architecture description above
**Then:** The orchestrator runs scope-guard -> cost-gate -> attack-surface-mapper -> cost-gate -> stride-analyst, then in parallel runs security-design-reviewer and abuse-case-elicitor; the combined output (attack surface map + threat register + design findings + abuse cases + acceptance criteria) is presented in full in the terminal; the orchestrator then displays the exact prompt: "Review the assembled threat model above. Type CONFIRM to proceed to write the threat model document, or type CANCEL to stop." and halts; no file is written to disk at this point
**Verifies:** /threat-model pipeline completeness and the first confirm-gate — the document must be visible before any write is attempted, and the agent halts awaiting user input rather than auto-proceeding

---

## Scenario 3: /security-review produces findings with HANDOFF blocks for code-level issues

**Command/Trigger:** `/security-review "Authentication design for the Acme platform: Users submit username and password to POST /auth/login. The password is hashed with bcrypt and compared to the stored value. On success, a session cookie named 'session_id' is set. Session tokens are stored in the application database. There is no MFA requirement. Admin users access /admin using the same session mechanism. Token expiry is not specified in the design document."`
**Given:** A design document that has authentication decisions but omits session token lifetime, MFA for privileged access, and explicit token binding; the input contains no source code
**When:** `/security-review` is invoked with the design document text above
**Then:** Output contains at least one finding in the Authentication Model area (missing MFA for admin access, token lifetime not specified), at least one finding in the Session Management area (expiry not specified, storage location is application database), severity labels (Critical / High / Medium / Low) are present on each finding, and at least one HANDOFF block formatted as "HANDOFF -> dev-companion:security-reviewer" is present citing code-level validation as the reason
**Verifies:** security-design-reviewer's HANDOFF gate — every finding requiring code inspection must include the HANDOFF block; the agent must not attempt to validate implementation itself

---

## Scenario 4: /abuse-cases produces BDD-style security acceptance criteria

**Command/Trigger:** `/abuse-cases "Feature: Password Reset. User story: As a registered user, I want to reset my password by receiving a one-time link at my registered email address. Acceptance: The link expires after 30 minutes. Only one active reset token exists at a time per account. The link can only be used once."`
**Given:** A valid feature description with a named use case (Password Reset) and documented happy-path acceptance criteria
**When:** `/abuse-cases` is invoked with the feature description above
**Then:** Output contains at least 3 abuse cases, each naming a specific actor class (External attacker, Authenticated user acting maliciously, Malicious input submitter, Passive eavesdropper, or Compromised internal service); each abuse case is paired with a BDD-style acceptance criterion in exact Given/When/Then format; the output ends with the mandatory note "NOTE: Attach each security acceptance criterion above to the implementing user story as an explicit acceptance criterion before development begins. Unattached criteria will not be enforced."
**Verifies:** abuse-case-elicitor's output completeness — every abuse case must have a testable Given/When/Then criterion and the closing note must be present

---

## Scenario 5: scope-guard halts on source code input and returns a cross-link to the correct plugin

**Command/Trigger:** `/stride "def authenticate_user(username: str, password: str) -> bool:\n    user = db.query(User).filter(User.username == username).first()\n    if user and bcrypt.checkpw(password.encode(), user.password_hash):\n        return True\n    return False"`
**Given:** The user pastes Python source code (function definition with type annotations and bcrypt logic) directly as the argument to /stride
**When:** `/stride` is invoked with the Python source code above
**Then:** The orchestrator invokes scope-guard; scope-guard returns HALT; the orchestrator emits exactly the SCOPE BOUNDARY message: "SCOPE BOUNDARY — security-companion works at the design and architecture stage. Your input appears to be source code." followed by the cross-link listing "dev-companion -> /security [file-or-directory-path]" as the redirect; no specialist agents (attack-surface-mapper, stride-analyst) are invoked; no output is written to disk
**Verifies:** scope-guard HALT condition 1 (Source Code Detected) — the "def " keyword with ": str" type annotations must trigger HALT; the hard gate "DO NOT skip scope-guard" is enforced before any specialist agent runs

---

## Scenario 6: scope-guard halts on package.json input and deflects to dependency-auditor

**Command/Trigger:** `/stride "{\n  \"name\": \"acme-api\",\n  \"version\": \"1.0.0\",\n  \"dependencies\": {\n    \"express\": \"4.18.2\",\n    \"jsonwebtoken\": \"8.5.1\",\n    \"bcrypt\": \"5.1.0\",\n    \"pg\": \"8.11.0\"\n  },\n  \"devDependencies\": {\n    \"jest\": \"29.5.0\"\n  }\n}"`
**Given:** The user pastes a package.json manifest with "dependencies" and "devDependencies" keys as the argument to /stride
**When:** `/stride` is invoked with the package.json content above
**Then:** scope-guard returns HALT specifying "a dependency manifest"; the orchestrator emits the SCOPE BOUNDARY message including the cross-link "dependency-auditor -> /audit [manifest-path]"; no analysis agents are invoked; output does not contain any STRIDE categories, threat register entries, or risk scores
**Verifies:** scope-guard HALT condition 3 (Dependency Manifest Detected) — the "dependencies" key pattern must trigger HALT; the deflection to dependency-auditor must appear in the response

---

## Scenario 7: threat-model-writer does NOT write to disk without explicit CONFIRM at both gates

**Command/Trigger:** `/threat-model "A REST API for a fintech application. Users authenticate with API keys. Data is stored in a PostgreSQL database. API keys are hashed with SHA-256 before storage. All endpoints require HTTPS. Rate limiting is applied at the gateway level."` — followed by the user typing "no" at the first confirmation prompt instead of CONFIRM
**Given:** The /threat-model pipeline has completed successfully; the assembled threat model document is displayed in the terminal; the first confirmation prompt is shown: "Review the assembled threat model above. Type CONFIRM to proceed to write the threat model document, or type CANCEL to stop."
**When:** The user types "no" (neither CONFIRM nor CANCEL) at the first confirmation prompt
**Then:** threat-model-writer responds "Please type CONFIRM, CANCEL, or provide a path within the project." and re-displays the prompt; when the user subsequently types "CANCEL", threat-model-writer responds "Write aborted. No files written."; no file is created at any path under docs/threat-models/ or anywhere else
**Verifies:** threat-model-writer's double confirm-gate — any input other than CONFIRM or CANCEL at the first gate must re-prompt; CANCEL must result in zero disk writes; the hard gate "NEVER write to disk without TWO explicit CONFIRM responses" is enforced

---

## Scenario 8: attack-surface-mapper and stride-analyst do NOT proceed without cost-gate PROCEED

**Command/Trigger:** `/stride "A microservices platform with 12 services communicating over gRPC. An API gateway handles external HTTPS traffic. Services authenticate each other via mutual TLS. User data is stored in separate databases per service. A central auth service issues JWTs for user sessions."` — with the session budget already exhausted (BUDGET_EXCEEDED state)
**Given:** The session budget in .ai-baseline/budget.json has been depleted; cost-gate-agent is configured to return BUDGET_EXCEEDED for any new Opus call
**When:** `/stride` is invoked; scope-guard returns SCOPE OK; the orchestrator invokes cost-gate-agent for the attack-surface-mapper pre-check
**Then:** cost-gate-agent returns BUDGET_EXCEEDED; the orchestrator surfaces the full BUDGET_EXCEEDED message to the user and stops; attack-surface-mapper is NOT invoked; stride-analyst is NOT invoked; no threat register is produced; no output is written to disk
**Verifies:** The hard gate "DO NOT invoke attack-surface-mapper or stride-analyst without a prior cost-gate PROCEED response" — the BUDGET_EXCEEDED signal must be a hard stop, not a warning; the Opus agents must never be called without pre-authorization

---

## Scenario 9: No agent other than threat-model-writer writes to disk

**Command/Trigger:** Run `/stride`, `/attack-surface`, `/security-review`, `/abuse-cases`, and `/scan-strategy` in sequence with valid architecture descriptions; then run `/threat-model` and respond CANCEL at the confirmation prompt
**Given:** A fresh session with no prior disk writes; all five advisory commands are run; /threat-model is cancelled before write
**When:** All six commands complete (five advisory + one cancelled /threat-model)
**Then:** No new files appear under docs/, .security-companion/, or any other path in the project root; the only state changes are append-only entries in .ai-baseline/audit.YYYY-MM-DD.jsonl; the docs/threat-models/ directory does not exist (it was not created by the CANCEL run)
**Verifies:** The hard gate "DO NOT write any file to disk — threat-model-writer is the sole disk-write agent" for orchestrator, attack-surface-mapper, stride-analyst, security-design-reviewer, abuse-case-elicitor, and scan-strategy-advisor; confirmed by running "git status" and finding no tracked or untracked file changes outside .ai-baseline/

---

## Scenario 10: Threat register for a system with no repudiation threat includes explicit rationale for zero-finding category

**Command/Trigger:** `/stride "A static content delivery system. A CDN serves pre-built HTML/CSS/JS assets from S3. There are no user accounts, no login flows, no write operations, and no state mutations. All content is publicly readable. The only admin operation is a CI/CD pipeline that pushes new build artifacts to S3 using an IAM role with write-only permissions to the specific bucket."`
**Given:** An architecture description where the Repudiation (R) category is genuinely non-applicable — there are no authenticated sessions and no stateful user actions to repudiate
**When:** `/stride` is invoked with the static CDN description above
**Then:** The threat register includes an explicit record for the R (Repudiation) category: "No threats identified for R (Repudiation) — rationale: [specific reason why the category does not apply to this system, e.g., no authenticated sessions exist; all content is read-only and no user actions require audit trail coverage]"; this entry appears in the threat register body alongside entries for the other applicable STRIDE categories; the summary line still lists all six categories
**Verifies:** stride-analyst's zero-finding coverage requirement — "If a category produces zero threats, include an explicit 'No threats identified for [CATEGORY] — rationale: [reason]' record in the register"; a silent omission is a test failure

---

## Scenario 11: stride-analyst emits a HANDOFF to compliance-companion when PII flows are detected

**Command/Trigger:** `/stride "A healthcare appointment scheduling platform. Patients (EU-based) submit their full name, date of birth, NHS number, and GP details via a web form. This PII is transmitted over HTTPS to a Node.js backend, stored in a PostgreSQL database encrypted at rest, and shared with the patient's registered GP via a REST API call to an external GP system. Audit logs record patient IDs and action types."`
**Given:** An architecture description that explicitly names cross-boundary flows carrying PII (patient name, DOB, NHS number) and involves EU-based data subjects
**When:** `/stride` completes analysis and produces the threat register
**Then:** The output contains a HANDOFF block addressed to "compliance-companion" with the format: "HANDOFF -> compliance-companion / Reason: Threat [T-NNN] involves [regulated data type] crossing [boundary name]. This may trigger GDPR Art. 32, PCI DSS, HIPAA, or EU AI Act obligations. / Suggested command: /explain or /model-card for regulatory mapping / Rule: SEC-D-5 (regulatory-exposure-present -> compliance-companion handoff mandatory)"; the HANDOFF references at least one specific threat ID from the register
**Verifies:** stride-analyst's SEC-D-5 Regulatory Exposure Check — the HANDOFF to compliance-companion is mandatory whenever the threat register contains cross-boundary flows carrying PII, payment data, health data, or other regulated data; absence of this HANDOFF is a test failure

---

## Scenario 12: scan-strategy-advisor emits mandatory HANDOFF blocks to dependency-auditor and ops-companion

**Command/Trigger:** `/scan-strategy "Our project is a Python (FastAPI) backend with a React TypeScript frontend. CI runs on GitHub Actions. We use Docker for containerization and deploy to AWS ECS. We have no existing SAST or DAST tooling. Our team of 4 engineers is new to security tooling."`
**Given:** A tech stack description with a named language (Python, TypeScript), CI provider (GitHub Actions), and explicit statement that the team is new to security tooling
**When:** `/scan-strategy` is invoked with the stack description above
**Then:** The output contains: (1) SAST recommendations for both Python (Bandit or Semgrep) and TypeScript (ESLint-security + Semgrep or CodeQL) with gate placement (PR check, blocking on Critical/High); (2) DAST recommendation (OWASP ZAP passive mode) with cadence (nightly against staging); (3) Dependency scanning recommendation (Dependabot or Trivy with PR gate) with a "HANDOFF -> dependency-auditor" block containing "Suggested command: /audit [path/to/manifest]"; (4) A "HANDOFF -> ops-companion:secrets-auditor" block with "Suggested command: /secrets-audit"; (5) The mandatory advisory disclaimer "ADVISORY: This agent recommends scanning strategy — it does not execute scanners, modify CI configuration, or install tools."; the new-team override note is applied recommending starting with SAST only
**Verifies:** scan-strategy-advisor's two mandatory HANDOFF blocks (dependency-auditor and ops-companion:secrets-auditor) — both must be present in every scan-strategy output regardless of stack; the "NEVER omit the HANDOFF block for secret scanning and dependency scanning — they are mandatory" hard gate; the new-team maturity override is applied per the SEC-D-8 override hook

---
