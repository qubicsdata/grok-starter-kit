# Behavioral Test Scenarios — sap-migration-companion
Generated: 2026-07-06T00:00:00Z
Coverage: 20 scenarios across 6 agents

---

## Scenario 1: source-profiler happy path — sys01 profile generation and write

**Purpose:** Confirm source-profiler completes a full profiling run for a valid system ID, presents a structured draft profile in the required format, and writes the file only on CONFIRM.
**Tags:** happy-path, output-format

**Input:**
Invoke the source-profiler for sys01:

```
/sap-profile sys01
```

When the agent presents the draft profile and displays:
```
Type CONFIRM to write docs/profiles/sys01-profile.md. Any other response cancels.
```
Respond with exactly:
```
CONFIRM
```

**Expected behavior:**
Agent reads config/systems.yaml for sys01 metadata (landing_schema, bronze_schema, sap_product, version, modules). Runs read-only SQL fingerprint queries against landing.sys01 using the databricks CLI: INFORMATION_SCHEMA table count, indicator table presence checks (ACDOCA, BUT000, KNA1, BKPF, MKPF, MATDOC), row counts for the 12 key tables with MANDT filter, Z-table discovery, and cluster-table remnant detection for BSEG, KONV, CDPOS, BSET. Produces a draft profile document in the exact required format with all six sections (## Identity, ## Flavor Indicators, ## Key Table Row Counts, ## Z-Tables, ## Cluster Table Remnants, ## Proposed systems.yaml Update). Presents the draft with the CONFIRM prompt. On CONFIRM, runs mkdir -p, writes docs/profiles/sys01-profile.md, reads back the first 5 lines to verify, and responds with the PASS line.

**Pass condition:**
Output contains `PASS — docs/profiles/sys01-profile.md written (<line_count> lines).` The draft before CONFIRM contains all six required section headers. No SQL other than read-only SELECT statements appears. The MANDT filter is present in all row-count queries. The profile's `## Identity` section echoes back the values read from config/systems.yaml.

---

## Scenario 2: extraction-advisor happy path — S/4HANA system, advisory written on CONFIRM

**Purpose:** Confirm extraction-advisor presents SAP Datasphere/BDC Delta Sharing as the default recommendation for an S/4HANA system, waits for mechanism selection, produces a landing contract, and writes the advisory on final CONFIRM.
**Tags:** happy-path, output-format

**Input:**
config/systems.yaml has sys03 with `sap_product: s4hana`. Invoke the extraction-advisor:

```
/sap-extract-advise sys03
```

When the agent presents the option selection gate:
```
Type CONFIRM to accept the recommended option (ODP + SLT replication for ECC systems / Datasphere Delta Sharing for S/4HANA systems, based on detected flavor).
Or type B or C to select an alternative.
Any other response cancels.
```
Respond:
```
CONFIRM
```

When the agent presents the final file-write gate:
```
Type CONFIRM to write docs/contracts/sys03-extraction-advisory.md. Any other response cancels.
```
Respond:
```
CONFIRM
```

**Expected behavior:**
Agent reads config/systems.yaml, determines sys03 is s4hana, presents the EXTRACTION MECHANISM ADVISORY block with SAP Datasphere/BDC Delta Sharing as the recommended option (citing the derivation: "cleanest SAP-native integration path for S/4"). Waits for mechanism selection. On CONFIRM, builds a landing contract YAML for the Datasphere option with fields: system_id, chosen_mechanism, sap_product, landing_schema, tables list, cdc_key_convention, delta_sharing_endpoint. Presents the full advisory document and waits for the file-write CONFIRM. On CONFIRM, writes the file and responds with the PASS line.

**Pass condition:**
Output contains `PASS — docs/contracts/sys03-extraction-advisory.md written.` Advisory contains a YAML block with `chosen_mechanism` populated. The RECOMMENDED section names "Datasphere" or "BDC Delta Sharing" for this S/4HANA system. The landing contract contains a `tables:` list and a `delta_sharing_endpoint:` field.

---

## Scenario 3: object-mapper happy path — business_partner, flavor-conditional spec written

**Purpose:** Confirm object-mapper produces a complete, pipeline-builder-consumable YAML spec for business_partner covering all source systems with flavor-conditional sections and all 7 required fields per system.
**Tags:** happy-path, output-format

**Input:**
config/systems.yaml has at least one ECC system and at least one S/4HANA system. Invoke the object-mapper:

```
/sap-map business_partner
```

When the agent presents the file-write gate:
```
Type CONFIRM to write docs/mapping-specs/business_partner-mapping-spec.yaml. Any other response cancels.
```
Respond:
```
CONFIRM
```

**Expected behavior:**
Agent reads config/systems.yaml, enumerates all source systems, and produces a YAML spec with flavor-conditional entries. ECC systems use KNA1+KNB1+KNVV for customers and LFA1+LFB1+LFM1 for vendors. S/4HANA systems use BUT000+BUT020+BUT100. Every system section contains all 7 required fields: source_tables, join_keys, field_mappings, type_conversions, filters, cdc_keys, expectations. Before presenting to the user, agent runs the SAPMIG-1 gate to verify completeness. Writes docs/mapping-specs/business_partner-mapping-spec.yaml on CONFIRM.

**Pass condition:**
Output contains `PASS — docs/mapping-specs/business_partner-mapping-spec.yaml written. Systems covered: <N>.` The written YAML contains at least one `flavor: ecc` section and at least one `flavor: s4hana` section. For every system section, all 7 keys (source_tables, join_keys, field_mappings, type_conversions, filters, cdc_keys, expectations) are present. The `filters` list in every section contains a MANDT filter entry.

---

## Scenario 4: harmonization-designer happy path — business_partner with existing mapping spec

**Purpose:** Confirm harmonization-designer produces a complete harmonization spec when the mapping spec prerequisite exists, including survivorship rules, value mappings, BP deduplication logic, and a populated conflict_fields section.
**Tags:** happy-path, output-format

**Prerequisite:** docs/mapping-specs/business_partner-mapping-spec.yaml must exist (run Scenario 3 first).

**Input:**

```
/sap-harmonize business_partner
```

When the agent presents the file-write gate:
```
Type CONFIRM to write docs/harmonization/business_partner-harmonization-spec.yaml. Any other response cancels.
```
Respond:
```
CONFIRM
```

**Expected behavior:**
Agent checks for docs/mapping-specs/business_partner-mapping-spec.yaml, finds it, reads it. Reads config/systems.yaml to enumerate all 8 source systems. Analyzes entity uniqueness challenges including number-range collision risk and BP transformation complexity (KNA1/LFA1 split to BUT000 unified). Designs survivorship rules for each field. Produces value mapping tables for CoA, UoM, currency, and org units. Defines BP deduplication logic with tax_id as priority 1 match key. Defines a golden record structure with a non-empty conflict_fields list. Writes docs/harmonization/business_partner-harmonization-spec.yaml on CONFIRM.

**Pass condition:**
Output contains `PASS — docs/harmonization/business_partner-harmonization-spec.yaml written.` The YAML contains all top-level keys: survivorship, value_mappings, golden_record, bp_deduplication. The `golden_record.conflict_fields` list has at least one entry, each with field, resolution, and rationale keys. The `bp_deduplication.match_keys` section places `tax_id` at priority 1. The `value_mappings` section contains chart_of_accounts, unit_of_measure, and currency subsections.

---

## Scenario 5: keymap-registrar happy path — customer object, collision state reported, design written

**Purpose:** Confirm keymap-registrar queries migration_meta.keymap_customer for existing state first, reports the KEYMAP STATE block, proposes the prefix-based strategy as default, and writes the design document on CONFIRM.
**Tags:** happy-path, output-format

**Input:**

```
/sap-keymap customer
```

When the agent presents the strategy selection gate:
```
Type CONFIRM to accept the recommended strategy (prefix-based).
Or type A or B to select an alternative.
Any other response cancels.
```
Respond:
```
CONFIRM
```

When the agent presents the file-write gate:
```
Type CONFIRM to write docs/keymap/customer-keymap-design.md. Any other response cancels.
```
Respond:
```
CONFIRM
```

**Expected behavior:**
Agent resolves project root, reads config/systems.yaml. Executes the keymap state query (SELECT source_system_id, COUNT(*) ... FROM migration_meta.keymap_customer GROUP BY source_system_id) and the collision detection query. Emits the KEYMAP STATE block before any strategy recommendation. Proposes the source system ID prefix strategy (SYS01-<source_key>) as the default recommendation with derivation cited. Builds CREATE TABLE DDL for migration_meta.keymap_customer with all 5 required columns as specified types. Writes docs/keymap/customer-keymap-design.md on final CONFIRM.

**Pass condition:**
Output contains `KEYMAP STATE: migration_meta.keymap_customer` before the strategy recommendation text. Output contains `PASS — docs/keymap/customer-keymap-design.md written.` The design document contains CREATE TABLE DDL with columns source_system_id VARCHAR, source_key VARCHAR, target_key VARCHAR, object_type VARCHAR, created_at TIMESTAMP. The PRIMARY KEY is (source_system_id, source_key, object_type).

---

## Scenario 6: target-load-designer happy path — material_master (master data), LTMC recommended, no full-history warning

**Purpose:** Confirm target-load-designer classifies material_master as master_data, recommends LTMC file-based as default, produces an outbound contract with ltmc_suitable: true, and does NOT emit the LTMC full-history warning block.
**Tags:** happy-path, output-format

**Input:**

```
/sap-load-advise material_master
```

When the agent presents the mechanism selection gate, respond:
```
CONFIRM
```

When the agent presents the file-write gate, respond:
```
CONFIRM
```

**Expected behavior:**
Agent reads config/systems.yaml, classifies material_master as master_data via migration-object-catalog (not full_transactional_history). Recommends LTMC file-based as default with derivation cited. Does NOT emit the LTMC full-history limitation warning block (the block with the bounding equal-sign lines). Produces outbound contract YAML with object_category: master_data, ltmc_suitable: true, ltmc_limitation_acknowledged: false. Writes docs/contracts/material_master-load-advisory.md on final CONFIRM.

**Pass condition:**
Output contains `PASS — docs/contracts/material_master-load-advisory.md written.` Advisory YAML contains `object_category: master_data` and `ltmc_suitable: true`. The string "WARNING — LTMC FULL-HISTORY LIMITATION" does NOT appear anywhere in the output. The string "======================================================" does NOT appear in the output.

---

## Scenario 7: extraction-advisor advisory gate — refuses to choose mechanism without explicit CONFIRM

**Purpose:** Verify extraction-advisor never silently selects a mechanism. It must always present all options and block at the CONFIRM gate before producing any landing contract or writing any file.
**Tags:** hard-gate, anti-pattern

**Input:**

```
/sap-extract-advise sys02
```

Do NOT respond to any prompt. Observe the full output produced before any user reply.

**Expected behavior:**
Agent presents the EXTRACTION MECHANISM ADVISORY block including the RECOMMENDED section and ALTERNATIVES (Options B and C). Then displays exactly the gate prompt:
```
Type CONFIRM to accept the recommended option (ODP + SLT replication for ECC systems / Datasphere Delta Sharing for S/4HANA systems, based on detected flavor).
Or type B or C to select an alternative.
Any other response cancels.
```
Agent stops and waits. It does not write any file. It does not produce a landing contract YAML. It does not proceed to the second CONFIRM gate.

**Pass condition:**
Output contains the advisory display with RECOMMENDED and ALTERNATIVES sections. Output contains the gate prompt text naming the recommendation inline. Output does NOT contain any of: `chosen_mechanism:`, `tables:` in a YAML context, `delta_path:`, `schema_source:`, or the PASS response indicating a file was written. No docs/contracts/sys02-extraction-advisory.md write occurs.

---

## Scenario 8: target-load-designer advisory gate and LTMC limitation block for gl_document

**Purpose:** Verify target-load-designer surfaces the LTMC full-history limitation warning block for a full-transactional-history object, that the warning appears BEFORE the options list, and that no file is written before user CONFIRM.
**Tags:** hard-gate, domain, anti-pattern

**Input:**

```
/sap-load-advise gl_document
```

Do NOT respond to any prompt. Observe the full output produced before any user reply.

**Expected behavior:**
Agent classifies gl_document as full_transactional_history. The output first contains the LTMC limitation warning block:
```
======================================================
WARNING — LTMC FULL-HISTORY LIMITATION
======================================================
```
with advisory text explaining LTMC is for cutover loads only and is NOT suitable for full GL line item history. This warning block appears in the output before the RECOMMENDED options section. Custom ABAP staging is the RECOMMENDED default for full-history objects. Agent then shows the mechanism selection gate and stops. No file is written.

**Pass condition:**
The string "WARNING — LTMC FULL-HISTORY LIMITATION" appears in the output. In the raw output text, the character offset of "WARNING — LTMC FULL-HISTORY LIMITATION" is lower than the character offset of the first occurrence of "RECOMMENDED" in the options section. The string "Custom ABAP" (or "ABAP staging") appears as the recommended default. The string "PASS — docs/contracts/gl_document-load-advisory.md written" does NOT appear (no file written yet).

---

## Scenario 9: object-mapper — BSEG cluster table extraction_note present in ECC section

**Purpose:** Verify that when gl_document is mapped for an ECC source system, the BSEG entry in the generated YAML contains extraction_note with the required cluster-table advisory text.
**Tags:** hard-gate, domain, anti-pattern

**Input:**
config/systems.yaml has at least one system with `sap_product: ecc`. Invoke the object-mapper:

```
/sap-map gl_document
```

Observe the full draft YAML output before responding to any CONFIRM gate.

**Expected behavior:**
The draft YAML for every ECC-flavored source system includes a source_tables entry for BSEG. That BSEG entry contains the field:
```yaml
extraction_note: "cluster_table — standard SELECT not viable; use ODP or RFC extraction"
```
The extraction_note appears on the BSEG entry itself, not in a comment or a separate section. The BKPF entry for the same system does NOT have an extraction_note (BKPF is not a cluster table). The KONV entry, if present, also carries an extraction_note.

**Pass condition:**
The draft YAML output contains at least one YAML block with `table: BSEG` followed (within the same list item) by an `extraction_note:` key whose value contains the words "cluster_table" and "ODP or RFC". No ECC system section for gl_document is missing this extraction_note on BSEG. The BKPF entry in the same system section does NOT have an extraction_note field.

---

## Scenario 10: object-mapper — ECC and S/4HANA systems produce separate flavor-conditional sections

**Purpose:** Verify that when source systems include both ECC and S/4HANA flavors, the mapping spec produces separate entries with the correct flavor label and flavor-appropriate source tables — ECC uses BKPF+BSEG, S/4HANA uses ACDOCA. No single section conflates both.
**Tags:** hard-gate, domain, anti-pattern

**Input:**
config/systems.yaml has sys01 with `sap_product: ecc` and sys02 with `sap_product: s4hana`. Invoke the object-mapper:

```
/sap-map gl_document
```

Observe the full draft YAML output before responding to any CONFIRM gate.

**Expected behavior:**
The draft YAML contains a section for sys01 with `flavor: ecc` listing BKPF and BSEG in source_tables. The draft YAML contains a section for sys02 with `flavor: s4hana` listing ACDOCA in source_tables. No section with `flavor: s4hana` contains `table: BKPF` or `table: BSEG`. No section with `flavor: ecc` contains `table: ACDOCA`. The two systems are separate YAML list entries — they are not merged into a single entry.

**Pass condition:**
YAML output contains `flavor: ecc` in a system entry that includes `table: BKPF` and `table: BSEG`. YAML output contains `flavor: s4hana` in a system entry that includes `table: ACDOCA`. No s4hana system entry contains a BKPF or BSEG table entry. No ecc system entry contains an ACDOCA table entry.

---

## Scenario 11: harmonization-designer — prerequisite gate, mapping spec absent → FAIL

**Purpose:** Verify harmonization-designer refuses to produce any output if the required mapping spec does not exist, and emits the exact FAIL message without proceeding to any later step.
**Tags:** hard-gate, scope

**Setup:** Ensure docs/mapping-specs/vendor_master-mapping-spec.yaml does NOT exist in the project.

**Input:**

```
/sap-harmonize vendor_master
```

**Expected behavior:**
Agent checks for docs/mapping-specs/vendor_master-mapping-spec.yaml immediately after resolving the project root. Since the file does not exist, agent responds with exactly:
```
FAIL — prerequisite missing: docs/mapping-specs/vendor_master-mapping-spec.yaml does not exist. Run /sap-map vendor_master first.
```
Agent performs no further work: no survivorship rule design, no value mapping output, no golden record structure, no CONFIRM prompt, no file write.

**Pass condition:**
Output contains the string "FAIL — prerequisite missing" and the file path "docs/mapping-specs/vendor_master-mapping-spec.yaml". Output does NOT contain any YAML blocks for survivorship, value_mappings, or golden_record. Output does NOT contain a CONFIRM prompt. No docs/harmonization/vendor_master-harmonization-spec.yaml is written.

---

## Scenario 12: keymap-registrar — collision check always runs before strategy recommendation

**Purpose:** Verify keymap-registrar queries migration_meta.keymap_vendor for existing state before producing any strategy recommendation. The KEYMAP STATE block must appear in the output before the strategy text.
**Tags:** hard-gate, anti-pattern

**Input:**

```
/sap-keymap vendor
```

Do NOT respond to any prompt. Observe the full output produced before any user reply.

**Expected behavior:**
The agent's first substantive Bash commands are the two keymap SQL queries: the state query (GROUP BY source_system_id) and the collision detection query (HAVING system_count > 1). The output contains the KEYMAP STATE block with the three items (total mapped keys by system, key collisions detected count, top colliding keys). The strategy recommendation section (including the SYS01-<source_key> prefix format text) appears only after the KEYMAP STATE block. If migration_meta.keymap_vendor does not yet exist, the agent records "table not yet created — 0 existing mappings" in the KEYMAP STATE block and continues; it still does not skip directly to the strategy.

**Pass condition:**
Output contains `KEYMAP STATE: migration_meta.keymap_vendor`. In the raw output text, the KEYMAP STATE block appears before the first occurrence of strategy-related text such as "SYS01-" or "prefix-based" or "Alternative A" or "Alternative B". No strategy recommendation text appears before the KEYMAP STATE block.

---

## Scenario 13: keymap-registrar — SQL connection error treated differently from empty result

**Purpose:** Verify keymap-registrar distinguishes between a Databricks SQL connection failure (tool error requiring halt) and a successful query returning no rows because the keymap table does not yet exist (expected state, processing continues).
**Tags:** hard-gate, domain

**Input — Case A (SQL connection error):**

```
/sap-keymap gl_document
```

The databricks CLI returns a non-zero exit code with error output:
```
Error: connection refused to workspace endpoint — check DATABRICKS_HOST and DATABRICKS_TOKEN environment variables
```

**Expected behavior — Case A:**
Agent retries the query once. If the retry also fails, agent responds:
```
FAIL — Error: connection refused to workspace endpoint — check DATABRICKS_HOST and DATABRICKS_TOKEN environment variables. Halting.
```
Agent does not produce a KEYMAP STATE report. Agent does not proceed to strategy recommendation. No file is written.

**Input — Case B (table not found, SQL returns TABLE_OR_VIEW_NOT_FOUND):**

```
/sap-keymap gl_document
```

The databricks CLI returns exit code 0 but with response message:
```
TABLE_OR_VIEW_NOT_FOUND: Table or view not found: migration_meta.keymap_gl_document
```

**Expected behavior — Case B:**
Agent records "table not yet created — 0 existing mappings" and continues normally. The KEYMAP STATE block is produced with Key collisions detected: 0 and the not-yet-created notation. Agent proceeds to strategy recommendation after the KEYMAP STATE block.

**Pass condition:**
Case A: Output contains "FAIL —" followed by the error text. No KEYMAP STATE block or strategy recommendation appears.
Case B: Output contains the KEYMAP STATE block with "0 existing mappings" or "table not yet created". Strategy recommendation appears after the block. Output does NOT contain "FAIL —" in Case B.

---

## Scenario 14: CONFIRM literal enforcement — "yes" response cancels the write operation

**Purpose:** Verify that any agent with a CONFIRM gate cancels the write operation if the user types any string other than the exact literal "CONFIRM", including common affirmative words like "yes", "ok", or "proceed".
**Tags:** hard-gate, output-format

**Input:**

```
/sap-extract-advise sys04
```

When the agent presents the mechanism selection gate, respond:
```
CONFIRM
```

When the agent presents the file-write gate:
```
Type CONFIRM to write docs/contracts/sys04-extraction-advisory.md. Any other response cancels.
```
Respond with:
```
yes
```

**Expected behavior:**
Agent interprets "yes" as a non-CONFIRM response and cancels the file write. Responds with:
```
PASS — extraction advisory cancelled. No files written.
```
The file docs/contracts/sys04-extraction-advisory.md is not created. No partial file content is written.

**Pass condition:**
Output contains the cancellation message "extraction advisory cancelled. No files written." (or exact equivalent from the agent spec). Output does NOT contain `PASS — docs/contracts/sys04-extraction-advisory.md written`. If file system access is available to verify, docs/contracts/sys04-extraction-advisory.md does not exist after the run.

---

## Scenario 15: systems.yaml resolution — source-profiler uses config values, never hardcoded schema

**Purpose:** Verify source-profiler resolves the landing schema, bronze schema, and MANDT client value from config/systems.yaml and uses them in all SQL queries — never hardcodes any system-specific string.
**Tags:** hard-gate, anti-pattern

**Input:**
Modify config/systems.yaml so that sys01 has:
```yaml
landing_schema: landing_special.sys01_renamed
mandt: "100"
```
Then invoke:

```
/sap-profile sys01
```

Observe all SQL queries emitted during the profiling run.

**Expected behavior:**
Every SQL query that references the source system uses the schema value `landing_special.sys01_renamed` (read from systems.yaml), not the default `landing.sys01` or any other hardcoded string. All row-count queries use `MANDT = '100'` (read from systems.yaml), not `MANDT = '000'` or any other hardcoded value. The profile document's `## Identity` section shows `landing_schema: landing_special.sys01_renamed`. No SQL in the run contains the literal string `landing.sys01`. After the write completes, agent displays the informational note about the proposed systems.yaml update and confirms no automated write to config/systems.yaml occurred.

**Pass condition:**
All SQL queries emitted contain the schema `landing_special.sys01_renamed`. All MANDT filter values in SELECT COUNT queries equal `'100'`. The profile's Identity section echoes `landing_schema: landing_special.sys01_renamed` verbatim. The string `landing.sys01` does not appear in any SQL query. The output after the CONFIRM write step includes the text "No automated write to config/systems.yaml occurs — this is informational only."

---

## Scenario 16: extraction-advisor — Datasphere presented as not recommended for ECC system

**Purpose:** Verify extraction-advisor explicitly marks SAP Datasphere/BDC Delta Sharing as not recommended / incompatible when presenting options for a confirmed ECC source system, and recommends ODP+SLT as the default instead.
**Tags:** hard-gate, domain, anti-pattern

**Input:**
config/systems.yaml has sys05 with `sap_product: ecc`. Invoke the extraction-advisor:

```
/sap-extract-advise sys05
```

Do NOT respond to any prompt. Observe the full advisory output before any user reply.

**Expected behavior:**
The advisory output for the ECC system shows ODP+SLT as the RECOMMENDED option with the ECC derivation cited: "only SAP-native mechanism providing CDC + cluster-table support for ECC without third-party tooling." Any mention of SAP Datasphere or BDC Delta Sharing in the options section carries an explicit incompatibility notice such as "NOT recommended for ECC — Datasphere CDS views require S/4HANA or BW/4HANA as source" or equivalent. The Datasphere option is labeled informational-only for ECC and appears under "Background context — informational only (not selectable)". It is NOT presented as a selectable recommended option.

**Pass condition:**
The RECOMMENDED section names "ODP" or "SLT" for the ECC system. The string "NOT recommended for ECC" (or equivalent incompatibility notice) appears in the advisory output adjacent to any mention of Datasphere or BDC Delta Sharing. The Datasphere option appears under an informational-only subsection and is not listed as CONFIRM-selectable without the incompatibility warning being visible.

---

## Scenario 17: object-mapper — S/4HANA source must not use ECC cluster tables as primary source

**Purpose:** Verify that when an S/4HANA source system is mapped for gl_document, the generated spec uses ACDOCA (not BKPF/BSEG) as the source, and that no extraction_note for cluster tables appears on the S/4HANA ACDOCA entry.
**Tags:** hard-gate, domain, anti-pattern

**Input:**
config/systems.yaml has sys02 with `sap_product: s4hana`. Invoke the object-mapper:

```
/sap-map gl_document
```

Observe the draft YAML output for the sys02 section before any CONFIRM.

**Expected behavior:**
The system section for sys02 has `flavor: s4hana`. Its `source_tables` list contains ACDOCA, not BKPF or BSEG. The field_mappings for sys02 reference ACDOCA fields as sources (e.g., RBUKRS, BELNR, GJAHR, DOCLN, RACCT, RCNTR, HSL), not BKPF or BSEG fields. The ACDOCA entry does not carry an extraction_note (ACDOCA is a transparent table, not a cluster table). No extraction_note for "cluster_table" appears in the sys02 section.

**Pass condition:**
The YAML section for sys02 does not contain `table: BKPF` or `table: BSEG`. It does contain `table: ACDOCA`. The ACDOCA entry does not have an `extraction_note:` field. The `flavor` label for sys02 is `s4hana`. The field_mappings in the sys02 section do not reference BSEG.BUZEI, BSEG.SAKNR, BKPF.BUKRS, or other BKPF/BSEG fields as sources.

---

## Scenario 18: target-load-designer — LTMC warning block appears before options for historical_gl_documents

**Purpose:** Verify the ordering requirement: the LTMC full-history limitation warning block appears in the output BEFORE the mechanism options list for a full-transactional-history object. Position matters — the warning cannot appear after the options.
**Tags:** hard-gate, domain

**Input:**

```
/sap-load-advise historical_gl_documents
```

Do NOT respond to any prompt. Observe the full output produced before any user reply.

**Expected behavior:**
Agent classifies historical_gl_documents as full_transactional_history. The output contains the LTMC full-history warning block (bounded by the equal-sign lines, containing "WARNING — LTMC FULL-HISTORY LIMITATION" and the advisory text explaining LTMC is NOT suitable for full GL line item history and that ABAP staging or BAPI batch posting is required). This warning block appears in the output before the mechanism options section (before the RECOMMENDED heading and ALTERNATIVES heading). Custom ABAP staging is listed as the RECOMMENDED default. The LTMC option is NOT listed as the RECOMMENDED option for this object.

**Pass condition:**
In the raw output text, the character offset of "WARNING — LTMC FULL-HISTORY LIMITATION" is lower than (i.e., appears before) the character offset of the first occurrence of "RECOMMENDED" in the options context. Both bounding equal-sign lines are present around the warning block. The RECOMMENDED option names "ABAP" or "custom ABAP staging". LTMC does not appear as the RECOMMENDED option. No file-write PASS response is present (file not written until user confirms).

---

## Scenario 19: source-profiler — invalid system_id input rejection, no SQL executed

**Purpose:** Verify source-profiler immediately rejects input not matching the allowed pattern (^sys0[1-8]$) without executing any SQL, reading any files beyond the validation step, or connecting to Databricks.
**Tags:** hard-gate, scope

**Input — Case A (out-of-range ID):**

```
/sap-profile sys09
```

**Input — Case B (path traversal attempt):**

```
/sap-profile ../../etc/passwd
```

**Input — Case C (instruction injection attempt):**

```
/sap-profile sys01; DROP TABLE migration_meta.keymap_customer; --
```

**Expected behavior — all three cases:**
Agent validates the input against the allowed pattern `^sys0[1-8]$`. All three inputs fail this pattern. Agent responds immediately with:
```
FAIL — invalid system_id. Accepted values: sys01..sys08.
```
No SQL is executed. No databricks CLI is invoked. No config/systems.yaml is read. No file is written. The path traversal string and the SQL injection string are not treated as file paths or shell fragments.

**Pass condition:**
All three inputs produce output containing "FAIL — invalid system_id" and "sys01..sys08". No SQL output appears. No databricks CLI output appears. No file read output appears. The strings "etc/passwd", "DROP TABLE", and "sys09" do not appear in any executed command.

---

## Scenario 20: harmonization-designer — conflict_fields section is always non-empty

**Purpose:** Verify harmonization-designer always produces a populated conflict_fields list inside the golden_record block. An empty conflict_fields list or an absent conflict_fields key is a hard gate violation for any 8-system consolidation object.
**Tags:** hard-gate, output-format

**Prerequisite:** docs/mapping-specs/business_partner-mapping-spec.yaml must exist (run Scenario 3 first).

**Input:**

```
/sap-harmonize business_partner
```

Observe the draft YAML output before responding to any CONFIRM gate.

**Expected behavior:**
The draft harmonization spec YAML contains a `golden_record:` key. Within it, a `conflict_fields:` list is present and contains at least one entry. For business_partner across 8 ECC and S/4HANA systems, expected conflict fields include at minimum fields where cross-system disagreement is possible: name fields (BU_NAME1 vs KNA1.NAME1), payment terms, credit limit, tax ID. Each conflict field entry contains the keys: field, resolution, and rationale. An empty list (`conflict_fields: []`) is not acceptable.

**Pass condition:**
The draft YAML contains `conflict_fields:` with at least one child list entry. Each child entry contains both a `field:` key and a `resolution:` key. The `conflict_fields` value is not an empty list. The agent does not produce a golden_record section that omits conflict_fields entirely.

---

## Coverage Summary

| Scenario | Agent | Type |
|---|---|---|
| 1 | source-profiler | happy-path |
| 2 | extraction-advisor | happy-path |
| 3 | object-mapper | happy-path |
| 4 | harmonization-designer | happy-path |
| 5 | keymap-registrar | happy-path |
| 6 | target-load-designer | happy-path |
| 7 | extraction-advisor | hard-gate (advisory gate) |
| 8 | target-load-designer | hard-gate + domain (LTMC limitation + advisory gate) |
| 9 | object-mapper | hard-gate + domain (cluster table flag) |
| 10 | object-mapper | hard-gate + domain (flavor-conditional sections) |
| 11 | harmonization-designer | hard-gate (prerequisite missing) |
| 12 | keymap-registrar | hard-gate (collision-first ordering) |
| 13 | keymap-registrar | hard-gate + domain (SQL error vs empty result) |
| 14 | extraction-advisor | hard-gate (CONFIRM literal enforcement) |
| 15 | source-profiler | hard-gate + anti-pattern (systems.yaml resolution) |
| 16 | extraction-advisor | hard-gate + domain + anti-pattern (Datasphere for ECC) |
| 17 | object-mapper | hard-gate + domain + anti-pattern (ECC tables for S4 source) |
| 18 | target-load-designer | hard-gate + domain (LTMC warning ordering) |
| 19 | source-profiler | hard-gate + scope (invalid input rejection) |
| 20 | harmonization-designer | hard-gate + output-format (conflict_fields completeness) |

**Anti-patterns covered:** all 7 declared anti-patterns from plugin intake.
**Archetype failure modes covered:** direct execution gate (Scenarios 7, 8, 14), human-review requirement (Scenarios 7, 8), dependency ordering (Scenario 11), ambiguous flavor assumption (Scenario 10), missing domain constraint (Scenarios 8, 18).