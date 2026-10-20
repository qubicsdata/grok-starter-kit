# sap-migration-companion

SAP domain intelligence plugin for an 8-systems-to-1 consolidation on Databricks. Provides source
profiling, extraction advisory, migration-object mapping, cross-system harmonization, keymap
management, and target load advisory for SAP ECC and S/4HANA sources.

## Dependencies

- requires: ai-baseline
- requires: databricks-engineer (pipeline-builder consumes mapping spec output from `/sap-map`)

## Installation

```bash
# Clone to your accelerator plugins directory
git clone <repo-url> /path/to/accelerator/sap-migration-companion

# Ensure ai-baseline is installed
ls /path/to/accelerator/ai-baseline/.claude-plugin/plugin.json

# Ensure config/systems.yaml exists in your project root
cat config/systems.yaml
```

Agents read `config/systems.yaml` from the git root of your project. The file must exist before
running any command. See the expected structure below.

## config/systems.yaml Structure

```yaml
schema_version: 1
target:
  id: tgt01
  sap_product: s4hana
  load_mechanism: undecided
sources:
  - id: sys01
    sap_product: unknown   # ecc | s4hana | unknown
    version: unknown
    modules: []
    extraction:
      mechanism: undecided
      status: not_started
    landing_schema: landing.sys01
    bronze_schema: bronze.sys01
  # ... sys02..sys08 same structure
```

## Commands

### `/sap-profile <system_id>`
Profile a landed source system. Runs read-only SQL against the landing schema to fingerprint SAP
flavor, count key tables, discover Z-tables, and flag cluster-table remnants.

**Example:**
```
/sap-profile sys01
```
Writes `docs/profiles/sys01-profile.md` after CONFIRM.

---

### `/sap-extract-advise <system_id>`
Get an extraction mechanism recommendation for a source system. Options: ODP+SLT replication,
SAP Datasphere/BDC Delta Sharing, third-party (Qlik Replicate, SNP Glue), or file-based.

Note: No native Lakeflow Connect SAP connector exists as of 2026.

**Example:**
```
/sap-extract-advise sys02
```
Writes `docs/contracts/sys02-extraction-advisory.md` after CONFIRM.

---

### `/sap-map <object_name>`
Build a pipeline-builder-consumable YAML mapping spec for a migration object across all source
systems. Specs are flavor-conditional (separate ECC and S/4HANA sections). Cluster tables are
flagged with `extraction_note`.

**Example:**
```
/sap-map gl_document
/sap-map business_partner
/sap-map material_master
```
Writes `docs/mapping-specs/<object_name>-mapping-spec.yaml` after CONFIRM.

---

### `/sap-harmonize <object_name>`
Design cross-system harmonization: deduplication, survivorship rules, value mappings (CoA, UoM,
currency), and golden-record definitions. Requires the mapping spec to exist first.

**Example:**
```
/sap-harmonize business_partner
```
Prerequisite: `/sap-map business_partner` must have been run first.
Writes `docs/harmonization/<object_name>-harmonization-spec.yaml` after CONFIRM.

---

### `/sap-keymap <object_name>`
Design the migration_meta keymap table and key-issuance strategy for a migration object.
Always queries existing collision state before proposing any new-key strategy.

**Example:**
```
/sap-keymap customer
/sap-keymap gl_document
```
Writes `docs/keymap/<object_name>-keymap-design.md` after CONFIRM.

---

### `/sap-load-advise <object_name>`
Get a target load mechanism recommendation: LTMC file-based, IDoc batch, or custom ABAP staging.
Surfaces LTMC full-history limitation explicitly for full-history objects.

**Example:**
```
/sap-load-advise gl_document
/sap-load-advise material_master
```
Writes `docs/contracts/<object_name>-load-advisory.md` after CONFIRM.

---

## Recommended Migration Workflow

Run commands in this order for each migration object:

1. `/sap-profile sys01` (repeat for sys01..sys08)
2. `/sap-extract-advise sys01` (repeat for each system)
3. `/sap-keymap customer` (run before mapping customer-dependent objects)
4. `/sap-map gl_document`
5. `/sap-harmonize gl_document`
6. `/sap-load-advise gl_document`

Consult the migration-object-catalog skill for the full dependency-ordered object list.

## Key Domain Notes

- **No native Lakeflow Connect SAP connector.** As of 2026, there is no managed connector for SAP ECC or S/4HANA in the Databricks connector index.
- **LTMC full-history limitation.** LTMC is for cutover loads only (master data + open items). Full transactional history requires custom ABAP or BAPI batch posting.
- **8-system number range collisions are certain.** Run `/sap-keymap` before any document-level load.
- **Cluster tables.** BSEG, KONV, CDPOS, BSET cannot be read with standard SELECT in ECC — ODP or RFC required.
- **Flavor-conditional specs.** Every mapping spec has separate ECC and S/4HANA sections — never merged.

## CONFIRM Gate Convention

All write operations use an exact-string CONFIRM gate:

```
Type CONFIRM to write <file>. Any other response cancels.
```

Only the exact string `CONFIRM` proceeds. `yes`, `ok`, `proceed`, or any other string cancels.

## Author

<your-name> — you@example.com
