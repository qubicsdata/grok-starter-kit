---
name: pii-heuristic
description: |
  Column name heuristics for identifying likely PII: blocklist of column name patterns, escalation rules for flagging vs. asking. Used by contract-generator and naming-validator.
---

# PII Heuristic

## Purpose

Identify columns that are likely to contain personally identifiable information (PII) based on column name patterns. This is a heuristic — it finds candidates, not certainties. Always confirm with the user before classifying a column as PII in a contract.

## Confirmed PII Patterns

Columns whose names match these patterns (exact match or containing the token) are **confirmed PII candidates** — flag without asking:

| Pattern | PII Type | Example column names |
|---|---|---|
| `email` | Email address | `email`, `user_email`, `contact_email` |
| `phone` | Phone number | `phone`, `phone_number`, `mobile_phone` |
| `ssn` | Social Security Number | `ssn`, `social_security_number` |
| `dob` | Date of birth | `dob`, `date_of_birth`, `birth_date` |
| `passport` | Passport number | `passport_number` |
| `national_id` | National ID | `national_id`, `national_id_number` |
| `tax_id` | Tax ID | `tax_id`, `vat_number` |
| `credit_card` | Payment card | `credit_card_number`, `card_number` |
| `bank_account` | Bank account | `bank_account_number`, `iban` |
| `ip_address` | IP address | `ip_address`, `client_ip`, `user_ip` |
| `device_id` | Device fingerprint | `device_id`, `fingerprint` |
| `latitude` / `longitude` | Precise geo | `latitude`, `longitude`, `lat`, `lon` |

## Probable PII Patterns (ask before classifying)

Columns matching these patterns are probable but context-dependent. Ask the user to confirm:

| Pattern | Possible PII | Example |
|---|---|---|
| `name` (standalone or suffix) | Full name or person name | `name`, `first_name`, `last_name`, `full_name` |
| `address` | Street address | `address`, `street_address`, `billing_address` |
| `zip` / `postal` | Postal code (quasi-identifier) | `zip_code`, `postal_code` |
| `gender` | Gender | `gender`, `sex` |
| `age` | Age (quasi-identifier with other fields) | `age`, `age_group` |
| `salary` / `income` | Financial data | `salary`, `annual_income` |
| `health` / `medical` / `diagnosis` | Health data | `health_condition`, `diagnosis_code` |
| `ethnicity` / `race` | Sensitive category | `ethnicity`, `race` |
| `religion` | Sensitive category | `religion` |
| `user_id` / `customer_id` | Indirect identifier (links to PII) | `user_id`, `customer_id` |

## Escalation Rules

1. **Confirmed PII candidate found:** Flag in output with classification `"pii": true`. No confirmation needed for flagging — confirmation needed before writing to a contract.
2. **Probable PII candidate found:** Flag with `"pii": "probable"`. Ask: "Column `[name]` may contain [type] — should I classify it as PII in the contract?" One question per session, not one per column — group all probable candidates into one question.
3. **No match:** Column is `"pii": false` for contract purposes. Note that absence of a match is not a guarantee.

## Naming Convention Enforcement (for naming-validator)

The following naming conventions reduce PII exposure risk by making PII columns identifiable at a glance:

- Boolean columns: MUST start with `is_` or `has_`
- Timestamp columns: MUST end with `_at`
- Date columns: MUST end with `_date`

Violations of the above on any column adjacent to PII data are **Medium** findings in naming-validator.

## DO NOT Rules

- DO NOT classify a column as non-PII because its name does not match — absence of a match is not an absence of PII
- DO NOT write PII classification to a contract without user confirmation
- DO NOT ask once per column for probable PII — group all candidates into a single question
