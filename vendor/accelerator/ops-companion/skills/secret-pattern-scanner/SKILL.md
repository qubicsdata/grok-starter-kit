---
name: secret-pattern-scanner
description: |
  Use when scanning any text, diff, config, or pipeline file for hardcoded secrets. Combines regex patterns for known secret formats with Shannon-entropy analysis of string literals. Reports file:line and secret type — never the secret value.
---

# secret-pattern-scanner

Apply both detection methods below to every line of the target text. Report the file:line and the type of secret found. **Never output the secret value itself** — mask it as `[REDACTED]` in all output.

---

## Method 1: Known-format regex patterns

Check every line against the following patterns. When a match is found, report the type — not the matched value.

| Secret type | Pattern description | Severity |
|---|---|---|
| AWS Access Key ID | Starts with `AKIA`, `ASIA`, `AROA`, `AIDA` followed by 16 uppercase alphanumeric chars | CRITICAL |
| AWS Secret Access Key | 40-char base64 string following `aws_secret_access_key`, `AWS_SECRET`, or similar key name | CRITICAL |
| GitHub Personal Access Token | `ghp_`, `gho_`, `ghu_`, `ghs_`, `ghr_` prefix followed by alphanumeric string | CRITICAL |
| GitHub App Token | `github_pat_` prefix | CRITICAL |
| Stripe secret key | `sk_live_` or `sk_test_` prefix | CRITICAL |
| Stripe publishable key | `pk_live_` or `pk_test_` prefix | HIGH |
| Generic API key assignment | `API_KEY=`, `api_key=`, `apikey=`, `APIKEY=` followed by a non-empty non-placeholder value | HIGH |
| Generic secret assignment | `SECRET=`, `secret=`, `PASSWORD=`, `password=`, `PASSWD=`, `TOKEN=`, `token=` followed by a non-empty non-placeholder value | HIGH |
| Bearer token in config | `Bearer ` followed by a string of 20+ characters | HIGH |
| Private key header | `BEGIN RSA PRIVATE KEY`, `BEGIN EC PRIVATE KEY`, `BEGIN OPENSSH PRIVATE KEY` armour lines | CRITICAL |
| Slack webhook URL | `https://hooks.slack.com/services/` prefix | HIGH |
| PagerDuty routing key | 32-char hex string following `routing_key` or `PAGERDUTY` key name | HIGH |
| Twilio auth token | 32-char hex string following `auth_token` or `TWILIO` key name | HIGH |
| SendGrid API key | `SG.` prefix followed by alphanumeric string | CRITICAL |
| Heroku API key | 36-char UUID following `HEROKU` key name | HIGH |
| NPM token | `npm_` prefix followed by alphanumeric string | CRITICAL |
| Docker Hub password | `dckr_pat_` prefix | CRITICAL |
| GCP service account key | JSON block containing `"private_key"` and `"client_email"` | CRITICAL |

**Placeholder exclusion:** Do not flag values that are clearly placeholders: `<your-key-here>`, `YOUR_API_KEY`, `REPLACE_ME`, `example`, `changeme`, `todo`, `xxx`, `...`, `$VAR_NAME`, `${VAR_NAME}`, `$(command)`.

---

## Method 2: Shannon entropy scan

For every string literal (quoted string, environment variable value, or bare assignment value):
1. Compute the Shannon entropy of the string.
2. If entropy > 4.5 bits/char AND the string is 20+ characters long AND it is not a known hash, UUID, or URL → flag as a potential high-entropy secret.

Report as:
- Type: `HIGH_ENTROPY_STRING`
- Severity: HIGH (entropy alone is not CRITICAL — requires human verification)
- Note: "High-entropy string of [N] characters. Verify this is not a hardcoded secret."

**Exclusions from entropy scan:**
- File paths, URLs, and domain names
- Known hash digests (64-char hex = SHA-256, 40-char hex = SHA-1, 32-char hex = MD5)
- UUIDs (`xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx` format)
- Base64-encoded non-secret data that is documented inline

---

## Output format per finding

```
[file:line] [SECRET_TYPE] — [REDACTED] ([N] chars) — [severity]
```

Example:
```
.github/workflows/ci.yml:42 AWS_ACCESS_KEY_ID — [REDACTED] (20 chars) — CRITICAL
infra/main.tf:87 HIGH_ENTROPY_STRING — [REDACTED] (38 chars) — HIGH — verify this is not a hardcoded secret
```

**Never include the actual secret value in any output, log, or finding report.**

---

## Summary block

After scanning all targets:

```
## secret-pattern-scanner summary

Scanned: [N] files / [N] lines
Findings: [N] CRITICAL, [N] HIGH
```

If no secrets found: `No secrets detected. (Note: absence of findings does not guarantee absence of secrets — review manually for secrets stored in external config not covered by this scan.)`
