---
name: sap-table-reference
description: |
  Import when writing or reviewing any SQL query, extraction rule, or mapping spec that references
  SAP table names — especially when cluster tables (BSEG, KONV, CDPOS, BSET), flavor-dependent
  table pairs (BKPF/ACDOCA, KNA1/BUT000, MKPF/MATDOC), or MANDT-scoped queries are involved.
---

# SAP Table Reference

---

## Financial Accounting (FI)

### ECC FI Tables
| Table | Description | Notes |
|---|---|---|
| BKPF | Accounting Document Header | Key: MANDT, BUKRS, BELNR, GJAHR |
| BSEG | Accounting Document Segment | **CLUSTER TABLE** — cannot SELECT *; use ODP or RFC extraction |
| SKA1 | G/L Account Master (Chart of Accounts data) | Key: KTOPL, SAKNR |
| SKAT | G/L Account Master Texts | Key: SPRAS, KTOPL, SAKNR |
| SKB1 | G/L Account Master (Company Code) | Key: BUKRS, SAKNR |

### S/4HANA FI Tables
| Table | Description | Notes |
|---|---|---|
| ACDOCA | Universal Journal Entry Line Items | Replaces BKPF+BSEG; also covers CO actuals. Key: RCLNT, RBUKRS, BELNR, GJAHR, DOCLN |
| ACDOCP | Planning Data — Universal Journal | S/4HANA only |

### ECC Controlling (CO) Tables — replaced by ACDOCA in S/4
| Table | Description |
|---|---|
| COEP | CO Object: Line Items (by Period) |
| COSS | CO Object: Cost Totals for Internal Postings |
| COSP | CO Object: Cost Totals for External Postings |

---

## Materials Management (MM)

### ECC MM Transactional Tables
| Table | Description | Notes |
|---|---|---|
| MKPF | Header: Material Document | Key: MANDT, MBLNR, MJAHR |
| MSEG | Document Segment: Material | Transparent (not cluster) |

### S/4HANA MM Transactional Tables
| Table | Description | Notes |
|---|---|---|
| MATDOC | Material Documents (Unified) | Replaces MKPF+MSEG. Key: MANDT, MBLNR, MJAHR, ZEILE |

### Material Master Tables (ECC and S/4HANA)
| Table | Description |
|---|---|
| MARA | General Material Data |
| MARC | Plant Data for Material |
| MARD | Storage Location Data for Material |
| MAKT | Material Descriptions |

---

## Sales and Distribution (SD)

| Table | Description | Notes |
|---|---|---|
| VBAK | Sales Document: Header Data | |
| VBAP | Sales Document: Item Data | |
| VBEP | Sales Document: Schedule Line Data | |
| VBFA | Sales Document Flow | Key for order-to-delivery-to-invoice tracing |
| VBRK | Billing Document: Header Data | |
| VBRP | Billing Document: Item Data | |

---

## Customer / Vendor Master

### ECC Split Model
| Table | Description |
|---|---|
| KNA1 | General Data in Customer Master |
| KNB1 | Customer Master (Company Code) |
| KNVV | Customer Master Sales Data |
| LFA1 | Vendor Master General Section |
| LFB1 | Vendor Master (Company Code) |
| LFM1 | Vendor Master Purchasing Organization Data |

### S/4HANA Business Partner Unified Model (CVI)
| Table | Description | Notes |
|---|---|---|
| BUT000 | BP: General Data I | Unified customer+vendor |
| BUT020 | BP: Addresses | |
| BUT100 | BP: Roles | FLCU01 = customer role; FLVN01 = vendor role |

Note: S/4HANA CVI compatibility views (KNA1, LFA1) read from BUT000. Always prefer BUT000 for S/4
mapping specs; do not rely on compatibility views as authoritative extraction sources.

---

## Pricing

| Table | System | Description | Notes |
|---|---|---|---|
| KONV | ECC | Conditions (Transaction Data) | **CLUSTER TABLE** — cannot SELECT *; use ODP or RFC extraction |
| PRCD_ELEMENTS | S/4HANA | Pricing Conditions | Replaces KONV; transparent, can SELECT * |

---

## Cluster and Pool Tables (CRITICAL)

These tables CANNOT be read with standard `SELECT *` in ECC. They require ODP extraction, RFC calls,
or a third-party connector that handles cluster storage.

| Table | Description | Impact |
|---|---|---|
| BSEG | Accounting Document Segment | HIGH — core FI extraction |
| KONV | Conditions (Pricing) | HIGH — SD/MM pricing data |
| CDPOS | Change Document Items | MEDIUM — audit trail data |
| BSET | Tax Data Document Segment | MEDIUM — tax reporting |

**Standard extraction_note for all cluster tables:**
```
cluster_table — standard SELECT not viable in ECC; use ODP or RFC extraction
```

---

## MANDT (Client) Handling

Every table query MUST include a MANDT filter:
```sql
WHERE MANDT = '<client_id>'
```
- Default client for extraction: `000` unless overridden in `config/systems.yaml`
- Never extract cross-client data
- Confirm the MANDT value from the system's `config/systems.yaml` entry before running any query

---

## Hard Gates

**NEVER generate a `SELECT *` or a query without a WHERE clause on BSEG, KONV, CDPOS, or BSET.**
**NEVER omit the MANDT filter from any extraction SQL.**
**NEVER use ECC-specific tables (KNA1, LFA1, BKPF+BSEG) for an S/4HANA source without a flavor branch.**
**NEVER use S/4-specific tables (ACDOCA, MATDOC, BUT000) for an ECC source without a flavor branch.**