---
name: harmonization-craft
description: |
  Import when designing cross-system deduplication, survivorship rules, golden-record structure,
  or value mapping tables — especially for 8-system consolidation where heterogeneous SAP sources
  must produce a single coherent gold layer.
contract_version: 1.0.0
---

# Harmonization Craft

Generative expertise for cross-system deduplication, survivorship, and value mapping in multi-system
SAP consolidation. Consumed by harmonization-designer when producing a silver→gold harmonization
spec. Every recommendation leads with a default and carries the rule that produced it.

## Section 1 — Decision Domains

| ID prefix | Decision domain | The decision being made |
|-----------|-----------------|-------------------------|
| `HARM-SURV` | Survivorship strategy | Which system's value wins for a given field class |
| `HARM-KEY` | Uniqueness key | Which match key establishes that two records are the same entity |
| `HARM-DEDUP` | Deduplication action | Whether a match auto-merges, goes to human review, or becomes a new entity |
| `HARM-ENV` | Merge envelope | Which fields merge across systems rather than resolving to one winner |
| `HARM-MAP` | Value normalization | How Chart of Accounts, unit of measure, and currency values map to canonical form |

## Section 2 — Constraint Inputs

| Brief dimension | Drives | How |
|-----------------|--------|-----|
| Field class (financial / contact / classification / multi-value) | `HARM-SURV`, `HARM-ENV` | Field class is the primary selector for survivorship vs merge |
| Source system ranking | `HARM-SURV` | Supplies `priority_order` for Source Priority resolution |
| Data quality profile (completeness, recency) | `HARM-SURV`, `HARM-DEDUP` | Gates Most-Recent-Wins and sets review thresholds |
| Available identifiers (tax ID, bank, address quality) | `HARM-KEY`, `HARM-DEDUP` | Determines achievable match confidence |
| Migration object type | `HARM-KEY` | Business partner, material, GL account and cost centre each have distinct key ladders |
| Source Chart of Accounts per system | `HARM-MAP` | Drives CoA mapping type (direct, range, derived) |
| Regulatory / audit posture | `HARM-DEDUP`, `HARM-MAP` | Tightens auto-merge eligibility and currency conversion documentation |

## Section 3 — Opinionated Defaults

**Survivorship (`HARM-SURV`).** Three strategies; choose by field class, never globally.

| Strategy | Definition | Default use | Risk | Required mitigation |
|----------|------------|-------------|------|---------------------|
| **Source Priority** | A ranked system list decides the winner per field | Financial master data — payment terms, credit limits, GL assignments, org units | Low-priority corrections silently ignored | Log every suppressed value to `harmonization_discards` |
| **Most-Recent-Wins** | Latest `LAEDA` or equivalent timestamp wins per field | Contact data — address, phone, email, free-text descriptions | A recently corrupted record overwrites good history | Apply only above a data-quality threshold (e.g. address completeness ≥ 80%) and within a 90-day recency window |
| **Merge Fields** | Concatenate non-null values from all systems, then deduplicate | Multi-value classification — keywords, tags, search terms | Semantic duplicates survive the merge | Normalize through the value mapping tables before merging |

**Uniqueness keys (`HARM-KEY`).** A golden record is the single authoritative representation of an
entity across all source systems. Key ladders, strongest first:

| Object | Match key — priority order |
|--------|----------------------------|
| Business Partner | Tax ID (strongest) → bank account → name + city → name + postal code |
| Material | `MATNR` cross-system after keymap → EAN/UPC barcode |
| GL Account | Chart of accounts code, after CoA harmonization |
| Company Code | `T001` code from the cross-reference table |
| Cost Center | Controlling area + cost centre number, after keymap |

**Deduplication actions (`HARM-DEDUP`).** Default decision ladder for business partners:

```
1. Exact match on Tax ID (STCD1/STCD2)  -> auto-merge, log to harmonization_decisions
2. Exact match on bank account (BANKL+BANKN) -> human review, never auto-merge
3. Fuzzy name+address match             -> human review
   (Levenshtein distance < 3 on normalized name AND exact postal code)
4. No match                             -> new entity; assign new BP number
```

Normalize before fuzzy comparison: strip legal suffixes, lowercase, trim.

**Merge envelope (`HARM-ENV`).** Merge rather than resolve: address fields (deduplicate by address
type — billing, shipping), contact fields (deduplicate email/phone by type), classification fields
(merge then normalize).

**Value normalization (`HARM-MAP`).** Chart of Accounts maps per source system to the target CoA:

```yaml
chart_of_accounts_mapping:
  - source_system: sysNN
    source_coa_id: CAUS
    source_account: "100000"
    target_coa_id: <target_coa>
    target_account: "11000000"
    mapping_type: direct  # direct | range | derived
```

Unit of measure normalizes to ISO: `ST`/`PC` → `EA`, `KGM` → `KG`, `TNE` → `T`, `MTR` → `M`,
`LTR` → `L`. Currency codes must be valid ISO 4217; historical codes (`DEM`, `FRF`, `ITL`) require
conversion to EUR at official ECB fixed rates, with the rate and its source documented.

## Section 4 — Derivation Rules

- `HARM-D-1`: When the field is financial master data, choose Source Priority because a payment term or credit limit must be traceable to one accountable system, not to whichever system was edited last.
- `HARM-D-2`: When the field is contact data, choose Most-Recent-Wins because contact detail decays with age and recency is the best available proxy for correctness.
- `HARM-D-3`: When Most-Recent-Wins is selected, choose to gate it behind a data-quality threshold and a 90-day recency window because an unqualified timestamp lets a corrupted recent write beat a good old one.
- `HARM-D-4`: When the field holds multiple legitimate values, choose Merge Fields because collapsing a set to one winner destroys information the business relies on.
- `HARM-D-5`: When any survivorship strategy suppresses a value, choose to write it to `harmonization_discards` because a silent discard is unauditable and unrecoverable.
- `HARM-D-6`: When a tax ID matches exactly, choose auto-merge because a shared tax number identifies the same legal entity with the highest available confidence.
- `HARM-D-7`: When only a bank account matches, choose human review because shared banking is common across related-but-distinct vendor entities.
- `HARM-D-8`: When only a fuzzy name and address match, choose human review because normalized-string proximity is evidence of similarity, not of identity.
- `HARM-D-9`: When no match key fires, choose to create a new entity with a newly issued number because forcing a weak match is more expensive to unwind than a duplicate.
- `HARM-D-10`: When source systems operate different Charts of Accounts, choose an explicit per-system mapping with a declared `mapping_type` because implicit account alignment silently misposts.
- `HARM-D-11`: When a currency code is not valid ISO 4217, choose to halt and document the conversion rate and source because an undocumented historical conversion cannot be audited or reproduced.
- `HARM-D-12`: When a golden record is produced, choose to record its unique-key strategy in the harmonization spec because a record whose identity rule is unstated cannot be re-derived.

## Section 5 — Recommendation Output Contract

Every harmonization recommendation MUST surface: the chosen strategy or key, the `HARM-D-*` rule
ID(s) that produced it, at least one named alternative, and an override hook.

A harmonization spec MUST state, per object: the uniqueness key ladder, the survivorship strategy
per field class with its `priority_order` where applicable, the merge envelope, the value mapping
tables in scope, and the deduplication decision ladder with the confidence tier of each action.

**Override hook.** A user may override the survivorship strategy for any field class, the
`priority_order`, the recency window, and the fuzzy-match threshold — each by naming it explicitly
in the spec. Four defaults are not overridable, because each converts a recoverable mistake into an
unrecoverable one: auto-merge always requires a high-confidence key (`HARM-D-6`); suppressed values
are always logged (`HARM-D-5`); Most-Recent-Wins never applies to financial master data
(`HARM-D-1`); historical currency conversion is always documented (`HARM-D-11`). When a request
would violate one, refuse it, name the rule, and present a compliant alternative.

## Section 6 — Enforcement Handoff

harmonization-craft output is validated against keymap-spec (cross-system key issuance and collision
state must be resolved before any merge is proposed), ecc-s4-divergence-map (field-level ECC vs
S/4HANA differences must be reconciled before survivorship is applied), and migration-object-catalog
(the object's declared identity fields must match the chosen key ladder). Any survivorship or
deduplication decision that deviates from its cited `HARM-D-*` rule without an explicit user
override is a finding.
