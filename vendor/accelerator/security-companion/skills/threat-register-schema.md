---
name: threat-register-schema
description: Invoke before accepting or emitting any structured threat register entry — validates that all required fields are present, types are correct, and risk_score equals likelihood × impact.
---

# Threat Register Schema

Import this skill before accepting or emitting any threat register entry. Validate every entry. Reject entries that fail — do not include them in output until they are corrected.

## Required Fields

Every valid threat register entry MUST have ALL of the following fields:

| Field | Type | Constraints |
|---|---|---|
| `id` | string | Format: T-NNN (e.g., T-001, T-012). Sequential. Must be unique within the register. |
| `stride_category` | string | EXACTLY one of: S, T, R, I, D, E (corresponding to the six STRIDE categories) |
| `component` | string | Non-empty. Names the specific component, service, or data store affected. |
| `boundary_crossed` | string | Non-empty. Names the trust boundary crossing where the threat occurs, or "none (internal)" if the threat is wholly within one trust zone. |
| `likelihood` | integer | 1–5 inclusive. 1 = very unlikely, 5 = near-certain. |
| `impact` | integer | 1–5 inclusive. 1 = negligible, 5 = catastrophic. |
| `risk_score` | integer | MUST equal `likelihood × impact`. Range 1–25. |
| `mitigation` | string | Non-empty. Specific and actionable — not "add authentication" but a named mechanism (e.g., "Implement PKCE on the authorization endpoint to prevent authorization code interception"). |
| `mitigation_owner` | string | Non-empty. A role name (e.g., "Security Engineer", "Backend Team Lead") — never a person's name. |
| `sec_acceptance_criterion` | string or null | REQUIRED to be a non-null, non-empty BDD-style condition (Given/When/Then) when `risk_score ≥ 15`. May be null when `risk_score < 15`. |

## Validation Rules

Apply ALL of the following validations to each entry:

1. **All 10 fields present**: If any field is missing, REJECT the entry: `REJECT: entry [id or position] missing field [name]`.
2. **id format**: Must match the pattern `T-[0-9]{3,}`. If not: `REJECT: id format invalid — expected T-NNN`.
3. **stride_category value**: Must be exactly one of S, T, R, I, D, E. If not: `REJECT: stride_category must be one of S/T/R/I/D/E`.
4. **likelihood and impact range**: Both must be integers 1–5 inclusive. If not: `REJECT: likelihood and impact must be integers 1-5`.
5. **risk_score correctness**: Must equal `likelihood × impact`. If not: `REJECT: risk_score [value] does not equal likelihood [L] × impact [I] = [L×I]`.
6. **mitigation non-empty**: Must not be empty or "TBD" or a placeholder. If empty/placeholder: `REJECT: mitigation must be specific and actionable`.
7. **mitigation_owner non-empty**: Must not be empty or a person's name pattern (single name or "First Last"). If empty: `REJECT: mitigation_owner must be a role name`.
8. **sec_acceptance_criterion when risk_score ≥ 15**: Must be non-null and non-empty. If null or empty: `REJECT: sec_acceptance_criterion is required for risk_score ≥ 15 (HIGH or above)`.

## Risk Level Classification

For reference (informational, not a separate validation):
- LOW: risk_score 1–7
- MEDIUM: risk_score 8–14
- HIGH: risk_score 15–20
- CRITICAL: risk_score 21–25

## Validation Response

When all entries in a register pass:

```
REGISTER_VALID
Entries validated: [N]
All entries pass threat-register-schema. Register is ready for inclusion in the threat model document.
```

## Partial Failure Handling

If some entries pass and some fail:
1. Return REJECT messages for all failing entries first
2. The calling agent MUST correct all REJECT entries before producing output
3. Re-invoke validation after corrections
4. Do not include any entry in the output register until it passes

Entries MUST NOT be silently omitted from the register — fix them, do not drop them.

## Hard Gates

**NEVER pass an entry with a missing field — all 10 fields are required.**
**NEVER pass an entry where risk_score ≠ likelihood × impact.**
**NEVER pass an entry with sec_acceptance_criterion = null when risk_score ≥ 15.**
**NEVER accept "TBD", "TODO", or placeholder text as valid mitigation or mitigation_owner values.**
**NEVER pass an entry where mitigation_owner appears to be a person's name rather than a role.**
