---
name: keymap-spec
description: |
  Import when designing, querying, or validating migration_meta keymap tables, new-key issuance
  strategies, or collision-detection queries for any migration object that spans multiple source
  systems.
---

# Keymap Specification

Reference for `migration_meta` keymap table design, collision detection, and key issuance strategies.

---

## migration_meta.keymap_<object> Schema

```sql
CREATE TABLE IF NOT EXISTS migration_meta.keymap_<object> (
  source_system_id  VARCHAR(10)  NOT NULL,   -- e.g. 'sys01' — always from config/systems.yaml
  source_key        VARCHAR(255) NOT NULL,   -- original key from source system (VARCHAR preserves leading zeros)
  target_key        VARCHAR(255) NOT NULL,   -- assigned target key after consolidation
  object_type       VARCHAR(100) NOT NULL,   -- migration object slug (e.g. 'customer', 'gl_document')
  created_at        TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (source_system_id, source_key, object_type)
);
```

Field notes:
- `source_system_id`: always one of sys01..sys08 (from `config/systems.yaml`); never a hardcoded name
- `source_key`: VARCHAR — never INTEGER; SAP document numbers have leading zeros that must be preserved
- `target_key`: the assigned key in the target S/4HANA system after consolidation
- `object_type`: the migration object slug — same value as the $ARGUMENTS object name

---

## Collision Detection Queries

Run BEFORE any new-key issuance — this is unconditional.

```sql
-- Step 1: Existing mapping state per system
SELECT
  source_system_id,
  COUNT(*)           AS mapped_keys,
  MIN(created_at)    AS earliest,
  MAX(created_at)    AS latest
FROM migration_meta.keymap_<object>
GROUP BY source_system_id
ORDER BY source_system_id;

-- Step 2: Cross-system key collisions
SELECT
  source_key,
  COUNT(DISTINCT source_system_id) AS system_count,
  COLLECT_LIST(source_system_id)   AS systems
FROM migration_meta.keymap_<object>
GROUP BY source_key
HAVING system_count > 1
ORDER BY system_count DESC
LIMIT 50;
```

If the table does not yet exist, record: "0 existing mappings — table not yet created."

---

## New-Key Issuance Strategies

### Strategy 1: Source System ID Prefix (RECOMMENDED DEFAULT)
- **Format:** `<SYSID_UPPER>-<source_key>` — e.g. `SYS01-100001`
- **Uniqueness guarantee:** zero collision risk across up to 99 systems
- **Provenance:** always traceable to the originating system
- **Derivation:** simplest approach; no number range coordination; no SAP Basis change required
- **Override condition:** only override when business data governance requires prefix-free sequential keys

### Strategy 2: New Number Range
- **Format:** Reserve a dedicated numeric range (e.g. 9000000001+ for customer numbers)
- **Requirements:** SAP Basis must configure and activate the reserved number range on tgt01
- **Pros:** cleaner for production use (no prefix); sequential
- **Cons:** requires coordination; loses source provenance; risk of range exhaustion

### Strategy 3: Explicit Manual Mapping
- **Format:** CSV-based mapping table, manually authored
- **Suitable for:** objects with fewer than 10,000 total keys and business-mandated per-key approval
- **Risk:** HIGH for large objects — any gap causes FK violations at load time
- **Do NOT use for:** customer, vendor, or material masters at typical 8-system scale

---

## Referential Consistency Rule

All foreign keys within a document must reference a keymap entry for the same object type.

**Example:** An open GL document mapped from sys03 references customer number `100001`. That customer's
`target_key` MUST exist in `migration_meta.keymap_customer` before the GL document record is loaded.

**Load order for keymaps:**
1. All master data keymaps (customer, vendor, material, GL account)
2. All open item keymaps
3. All historical document keymaps

Never load document keymaps before all referenced master data keymaps are populated.

---

## Point Lookup Pattern

```sql
-- Resolve source_key to target_key (use fixed-string comparison, not regex)
SELECT target_key
FROM migration_meta.keymap_<object>
WHERE source_system_id = 'sysNN'
  AND source_key        = '100001'
  AND object_type       = 'customer';
```

When using shell `grep` to locate a value from user input, always use `grep -F` (fixed-string) to
prevent regex interpretation of special characters in key values.

---

## Hard Gates

**NEVER issue a new target_key without first running the collision-detection queries above.**
**NEVER allow duplicate (source_system_id, source_key, object_type) entries — the PRIMARY KEY enforces this; never bypass it.**
**NEVER load document keymap entries before all referenced master data keymap entries exist.**
**NEVER store SAP document numbers or material numbers as integers — always VARCHAR to preserve leading zeros.**
**NEVER use grep without the -F flag when searching for user-supplied key values.**