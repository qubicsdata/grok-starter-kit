---
name: migration-object-catalog
description: |
  Import when sequencing migration objects, validating load order prerequisites, determining LTMC
  suitability for an object, or deciding whether an object is master data (cutover) versus full
  transactional history.
---

# Migration Object Catalog

Objects are listed in dependency order. An object MUST NOT be loaded before all objects it
depends on are confirmed loaded and keymap entries exist.

---

## Tier 1: Foundation Objects (no dependencies)

### 1. Company Codes and Chart of Accounts
- **SAP objects:** T001 (company codes), T004 (CoA definition), T077S
- **Source tables (ECC and S/4):** T001, T004, T077S (same in both flavors)
- **Cluster table caveats:** None
- **LTMC suitability:** YES — master data cutover
- **Recommended load mechanism:** LTMC file-based
- **Prerequisite for:** ALL other objects

### 2. GL Account Master
- **SAP objects:** SKA1, SKAT, SKB1
- **Source tables:** SKA1 (chart of accounts), SKAT (texts), SKB1 (company code data)
- **Cluster table caveats:** None
- **LTMC suitability:** YES
- **Recommended load mechanism:** LTMC file-based (template: GL_ACCT_MASTER)
- **Prerequisite for:** Open GL items, Historical GL documents, Cost center plans

---

## Tier 2: Master Data (depends on Tier 1)

### 3. Business Partners
- **ECC source:** KNA1+KNB1+KNVV (customers), LFA1+LFB1+LFM1 (vendors) — separate records
- **S/4 source:** BUT000+BUT020+BUT100 — unified BP
- **Transformation complexity:** HIGH — CVI deduplication and merge required for ECC sources
- **Cluster table caveats:** None
- **LTMC suitability:** YES — master data
- **Recommended load mechanism:** LTMC file-based or IDoc batch (DEBMAS06, CREDTR)
- **Prerequisite for:** All document types (GL, PO, SO, FI postings)

### 4. Material Master
- **Source tables:** MARA, MARC, MARD, MAKT (identical structure in ECC and S/4)
- **Cluster table caveats:** None
- **LTMC suitability:** YES
- **Recommended load mechanism:** LTMC file-based
- **Prerequisite for:** Material documents, Purchase orders, Sales orders

### 5. Customer Master (from KNA1 or BP — ECC vs S/4 branch)
- ECC branch: KNA1 + KNB1 + KNVV
- S/4 branch: BUT000 + BUT020 + BUT100 (role FLCU01)
- **Cluster table caveats:** None
- **LTMC suitability:** YES — via Business Partner migration object in LTMC
- **Prerequisite for:** Sales orders, Billing documents, Open customer items

### 6. Vendor Master (from LFA1 or BP — ECC vs S/4 branch)
- ECC branch: LFA1 + LFB1 + LFM1
- S/4 branch: BUT000 + BUT020 + BUT100 (role FLVN01)
- **Cluster table caveats:** None
- **LTMC suitability:** YES — via Business Partner migration object in LTMC
- **Prerequisite for:** Purchase orders, Goods receipts, Open vendor items

---

## Tier 3: Open Items (depends on Tier 1 + Tier 2)

### 7. Open GL Items (open at cutover date)
- **ECC source:** BKPF + BSEG (cluster)
- **S/4 source:** ACDOCA (filter on open item indicator)
- **Cluster table caveats:** BSEG — cluster table; use ODP or RFC
- **LTMC suitability:** YES — open items ONLY, NOT full history
- **Recommended load mechanism:** LTMC file-based (open item migration object)
- **Note:** For full history, see Object 8

---

## Tier 4: Full Transactional History (depends on Tier 1 + Tier 2)

### 8. Historical GL Documents (all posted periods)
- **ECC source:** BKPF + BSEG (cluster)
- **S/4 source:** ACDOCA
- **Cluster table caveats:** BSEG — cluster table; use ODP or RFC
- **LTMC suitability:** NO — LTMC is NOT suitable for full GL line item history
- **Recommended load mechanism:** Custom ABAP staging or BAPI batch (BAPI_ACC_DOCUMENT_POST, FB01)
- **Volume:** HIGH — all fiscal years from all 8 systems
- **Risk:** HIGHEST risk, highest volume object in the migration

### 9. Purchase Orders and Goods Receipts
- **ECC source:** EKKO, EKPO (PO header/item); MKPF+MSEG (goods receipts)
- **S/4 source:** EKKO, EKPO (same structure); MATDOC (goods receipts)
- **Cluster table caveats:** None (EKKO/EKPO are transparent)
- **LTMC suitability:** YES for open POs; NO for full GR history
- **Recommended load mechanism:** LTMC for open; custom ABAP for full history

### 10. Sales Orders
- **Source tables:** VBAK, VBAP, VBEP, VBFA, VBRK, VBRP (same in ECC and S/4)
- **Cluster table caveats:** None
- **LTMC suitability:** YES for open sales orders; depends on scope for history
- **Recommended load mechanism:** LTMC for open; IDoc batch (ORDERS05) for full history

### 11. Material Documents (full history)
- **ECC source:** MKPF + MSEG
- **S/4 source:** MATDOC
- **Cluster table caveats:** None (MSEG is transparent)
- **LTMC suitability:** NO for full history
- **Recommended load mechanism:** Custom ABAP or BAPI_GOODSMVT_CREATE for full history
- **Volume:** HIGH

### 12. Asset Master and Transactions
- **Source tables:** ANLA (master), ANLN1, ANLZ, ANKT; ANEK (document header), ANEP (line items)
- **Cluster table caveats:** None
- **LTMC suitability:** YES for asset master; PARTIAL for transactions (LTMC handles cutover values)
- **Recommended load mechanism:** LTMC for asset master; LTMC legacy data transfer for depreciation cutover values; custom for full transaction history

---

## LTMC Suitability Quick Reference

| Object | LTMC Suitable | Reason if No |
|---|---|---|
| Company codes / CoA | YES | Master data |
| GL Account Master | YES | Master data |
| Business Partners | YES | Master data |
| Material Master | YES | Master data |
| Customer / Vendor Master | YES | Via BP object |
| Open GL Items | YES | Open items only |
| Historical GL Documents | NO | Full history — LTMC not designed for this |
| Open Purchase Orders | YES | Open items only |
| Full GR History | NO | Full history |
| Open Sales Orders | YES | Open items only |
| Full Material Documents | NO | Full history |
| Asset Master | YES | Master data |
| Asset Historical Transactions | PARTIAL | Cutover values only |

---

## Hard Gates

**NEVER classify Historical GL Documents (Object 8) or Full Material Documents (Object 11) as LTMC-suitable.**
**NEVER load Tier 3 or Tier 4 objects before all their Tier 1 and Tier 2 prerequisites are confirmed loaded.**
**NEVER skip the cluster-table caveat for BSEG when describing GL document extraction.**