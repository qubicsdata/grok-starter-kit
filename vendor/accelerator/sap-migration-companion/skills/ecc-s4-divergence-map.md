---
name: ecc-s4-divergence-map
description: |
  Import when a mapping spec must handle both ECC and S/4HANA source systems in flavor-conditional
  sections, or when ACDOCA, MATDOC, BUT000, PRCD_ELEMENTS, or CVI transformation logic is involved.
---

# ECC to S/4HANA Divergence Map

---

## Financial Accounting: BKPF+BSEG → ACDOCA

### ECC Structure
- **Header:** BKPF — key: MANDT, BUKRS, BELNR, GJAHR
  - Fields: BLDAT (document date), BUDAT (posting date), WAERS (currency), KURSF (exchange rate), BKTXT (header text)
- **Line items:** BSEG — CLUSTER TABLE (cannot SELECT *)
  - Key: MANDT, BUKRS, BELNR, GJAHR, BUZEI
  - Fields: KOART (account type), SAKNR (GL account), KOSTL (cost center), PRCTR (profit center), MWSKZ (tax code), DMBTR (local currency amount), WRBTR (document currency amount)

### S/4HANA Structure (ACDOCA)
ACDOCA is a single denormalized table replacing both BKPF and BSEG, with additional fields:
- Additional assignments inline: PRCTR, SEGMENT, RFAREA (functional area), GRANT_NBR, FUND
- CO assignments inline — replaces COEP, COSS, COSP for actuals
- Key: RCLNT, RBUKRS, BELNR, GJAHR, DOCLN (zero-padded line)

### Field Mapping Notes
| ECC Source | S/4 Target | Notes |
|---|---|---|
| BKPF.BUKRS | ACDOCA.RBUKRS | Company code |
| BKPF.BELNR | ACDOCA.BELNR | Document number |
| BKPF.GJAHR | ACDOCA.GJAHR | Fiscal year |
| BKPF.BUDAT | ACDOCA.BUDAT | Posting date |
| BSEG.BUZEI | ACDOCA.DOCLN | Line number (zero-padded to 6 digits in ACDOCA) |
| BSEG.SAKNR | ACDOCA.RACCT | G/L account |
| BSEG.KOSTL | ACDOCA.RCNTR | Cost center |
| BSEG.DMBTR | ACDOCA.HSL | Local currency amount |

### S/4 Compatibility Views
- **BSEG_NEW**: CDS-based compatibility view in S/4 exposing BSEG-like structure over ACDOCA.
  Do NOT use as primary extraction source for full history — read ACDOCA directly.
- **CDS: I_JournalEntry / C_JournalEntryItem**: preferred CDS views for S/4 FI extraction.

---

## Materials Management: MKPF+MSEG → MATDOC

### ECC Structure
- **Header:** MKPF — key: MANDT, MBLNR, MJAHR
  - Fields: BLDAT, BUDAT, USNAM (user name), BKTXT
- **Line items:** MSEG — transparent table
  - Key: MANDT, MBLNR, MJAHR, ZEILE
  - Fields: MATNR, WERKS, LGORT, MENGE, MEINS, DMBTR, BWART (movement type)

### S/4HANA Structure (MATDOC)
MATDOC is a single denormalized table:
- Key: MANDT, MBLNR, MJAHR, ZEILE
- Contains all MKPF and MSEG fields in one table
- Field names largely identical to MSEG; MKPF header fields merged in
- **CDS views:** I_MaterialDocument, I_MaterialDocumentItem

### Notes
MKPF and MSEG compatibility views exist in S/4 reading from MATDOC. Do not use them as primary
extraction sources for S/4 — read MATDOC directly or use CDS views.

---

## Business Partner: KNA1/LFA1 → BUT000 (CVI)

### ECC Split Model
- Customers: KNA1 (general) + KNB1 (company code) + KNVV (sales area)
- Vendors: LFA1 (general) + LFB1 (company code) + LFM1 (purchasing org)
- No unified person entity — same real-world company may have separate KNA1 and LFA1 records

### S/4HANA Unified BP Model (Customer Vendor Integration)
- BUT000: master BP table — name, category (person/organization/group)
- BUT020: address assignments (link to ADRC)
- BUT100: role assignments — FLCU01 = customer role; FLVN01 = vendor role
- A single BUT000 record carries both customer and vendor roles

### Transformation Complexity: HIGH
A customer who is also a vendor in ECC has two separate master records.
In S/4HANA they MUST be a single BP record. Deduplication MUST occur before loading to S/4.
Consult `harmonization-craft` for BP deduplication patterns.

| ECC | S/4HANA | Notes |
|---|---|---|
| KNA1.NAME1 | BUT000.BU_NAME1 | General name |
| KNA1.STCD1 | BUT000.BU_STCD1 | Tax number 1 |
| KNB1.BUKRS | BUT100 / KNB1 compat | Company code assignment |
| LFA1.NAME1 | BUT000.BU_NAME1 | Same BP, vendor name |
| LFA1.STCD1 | BUT000.BU_STCD1 | Must match customer Tax ID for dedup |

---

## Pricing: KONV → PRCD_ELEMENTS

### ECC (KONV — Cluster Table)
- KONV: cluster table — cannot SELECT *; requires ODP or RFC extraction
- Key: KNUMV (condition record number)
- Fields: KPOSN, STUNR, KAPPL, KSCHL (condition type), KAWRT, KBETR (rate), WAERS, KMEIN

### S/4HANA (PRCD_ELEMENTS)
- Standard transparent table — can SELECT *
- Key: KNUMV, KPOSN, STUNR, ZAEHK
- CDS view: I_PricingConditionRecord

---

## S/4 Compatibility Views and Preferred CDS Alternatives

| ECC Table | S/4 Compatibility View | S/4 Preferred CDS View | Warning |
|---|---|---|---|
| BKPF + BSEG | BSEG_NEW | I_JournalEntry / C_JournalEntryItem | Compat view does not expose all S/4 fields |
| MKPF + MSEG | MKPF / MSEG (read MATDOC) | I_MaterialDocument | Compat views are read-only overlays |
| KNA1 | KNA1 (via CVI) | I_Customer | CVI writes through to BUT000 |
| LFA1 | LFA1 (via CVI) | I_Supplier | CVI writes through to BUT000 |
| KONV | N/A | I_PricingConditionRecord | KONV fully replaced by PRCD_ELEMENTS |

---

## Hard Gates

**NEVER generate a mapping spec that uses ECC tables (BKPF, BSEG, KNA1, LFA1, MKPF, MSEG) as the source for an S/4HANA system without a flavor branch.**
**NEVER generate a mapping spec that uses S/4 tables (ACDOCA, MATDOC, BUT000) as the source for an ECC system without a flavor branch.**
**NEVER omit the BP CVI transformation requirement when migrating customer or vendor data from ECC.**
**NEVER recommend S/4 compatibility views as the primary extraction source — always prefer ACDOCA, MATDOC, or BUT000 directly.**