---
name: sensitive-content-scrub
description: |
  Mandatory pre-output gate applied by every agent before presenting any output. Checks for credential patterns, PII field names, and SQL schema verbatim content. Returns PASS or a list of flagged items to redact. This skill is blocking — flagged items must be redacted before the agent presents output. There are no exceptions and no advisory-only invocations.
---

# Sensitive Content Scrub

## Purpose

Apply this skill before any agent produces output. If any flagged pattern is found, the agent MUST redact the specific value (not the entire sentence) and re-check before presenting. The skill is not advisory — it blocks output until all flagged items are resolved.

## Flagged Patterns

### 1. Base64-like secrets

Regex: `[A-Za-z0-9+/]{40,}`

Any string of 40 or more consecutive base64 characters is a potential encoded secret. Redact the value. Record the variable name and its source location only.

### 2. Common secret prefixes

Regex: `(sk_|pk_|ghp_|xox[baprs]-|AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{35}|ya29\.[0-9A-Za-z_-]+)`

Any string beginning with one of these prefixes is a secret token (Stripe secret/publishable key, GitHub personal access token, Slack token, AWS access key ID, Google API key, Google OAuth token). Redact the value entirely.

### 3. Credential field assignments

Regex: `(?i)(password|passwd|secret|token|api_key|apikey|private_key|client_secret)\s*[=:"][^${\s<>][^\s"']{3,}`

A credential field name followed by `=`, `:`, or `"` and a non-placeholder value (a value that is not `$VAR`, `${VAR}`, `<placeholder>`, `your-`, `changeme`, `xxx`, or all-asterisks) is a live credential assignment. Redact the value. Record: field name and source file:line only.

**Placeholder indicators (do NOT flag):** values matching `^\$`, `^\${`, `^<`, `^your-`, `^changeme$`, `^xxx+$`, `^\*+$`

### 4. SQL CREATE TABLE statements

Regex: `CREATE\s+TABLE\s+\w+\s*\(`

Verbatim SQL schema definitions must not appear in generated output. Summarise the data model at the table/relationship level only (e.g., "the `users` table stores account credentials and profile data"). Do not transcribe column names, types, or constraints.

### 5. Full connection string URIs with credentials

Regex: `(postgres|mysql|mongodb|redis):\/\/[^:@\s]+:[^@\s]+@[^\s"']+`

A connection string URI that contains both a username and a password component is a live credential. Redact everything after `://` up to and including the `@`. Record: "connection string found at [file:line] — value suppressed."

## PII Handling

If the codebase processes personal data (email addresses, phone numbers, postal addresses, national ID numbers, date of birth), describe the data category flowing through the system without transcribing any sample values found in test fixtures, seed data, or comments. Write: "the [module] processes [data category]; sample values in fixtures have been omitted."

## Internal Business Logic

Do not transcribe pricing rules, fraud-detection thresholds, discount formulas, scoring algorithms, or rate-limit configurations verbatim. Describe at the category level: "the pricing module applies tier-based discounts; see `src/pricing/` for implementation details."

## Hardcoded Credential Escalation

If a credential value is found hardcoded in source code during analysis, do NOT include it in the architecture section or setup section. Instead, add a gotcha entry worded exactly as:

> **Hardcoded credential found in `[file]` — this should be rotated and moved to environment configuration.**

This entry goes in the Common Gotchas section only.

## Invocation Protocol

Every agent MUST invoke this skill at the end of its analysis, before presenting any output to the user:

1. Run all five regex patterns against the complete output draft.
2. Run the PII handling check against any data-flow descriptions.
3. If zero flags: output **PASS** — present the output.
4. If any flags: output **FLAGGED — [list of items]** — redact each flagged value, then re-run from step 1.
5. Present output only when the skill returns PASS.

**There is no bypass. There is no exception. Every agent invokes this skill.**
