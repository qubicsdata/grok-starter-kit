---
name: cutover-gate-spec
description: |
  Import when assembling or evaluating go/no-go evidence for a wave cutover decision.
  Triggers on: "go/no-go", "cutover approval", "cutover runbook", "dress rehearsal",
  "rollback plan", "wave advance", "evidence table", "cutover_approved signoff".
  Read before querying migration_meta for cutover evidence or authoring a cutover runbook.
contract_version: 1.0.0
---

# Cutover Gate Specification

Defines the complete evidence set required for a wave's go/no-go decision.
All evidence comes from migration_meta — never from memory, verbal assurance, or conversation context.

---

## Required Evidence Set (per wave)

For a wave to be eligible for cutover approval, ALL of the following must be present and PASS
in migration_meta:

1. **recon_results completeness:** Every object × source_system_id × layer_from × layer_to
   combination defined in the wave plan must have a recon_results entry with `result = 'PASS'`.
   No missing entries. No FAIL entries.

2. **DQ gate signoffs:** migration_meta.signoffs must contain at least one `wave_advance` or
   `gate_pass` entry for this wave_id, written by dq-gatekeeper.

3. **No unresolved gate_override entries:** If any `gate_override` signoff exists for this wave,
   the `notes` field must contain a human acknowledgement (not an automated message, not a blank).

---

## Go/No-Go Evidence Table Format

Populate this table ONLY from migration_meta.recon_results query results.
NEVER fill it from memory, conversation context, or verbal assurance.

```
| Object | System | Layer Transition | Result | Run At | Mismatch Detail |
|--------|--------|-----------------|--------|--------|-----------------|
| <from query> | <from query> | <from query> | <from query> | <from query> | <from query> |
```

A blank `Mismatch Detail` is only acceptable when `Result = PASS`.

---

## Completeness Check Query

Run before assembling the evidence table:

```sql
WITH wave_objects AS (
  SELECT object_name, source_system_id, layer_from, layer_to
  FROM (VALUES
    ('<object>', '<sys>', '<layer_from>', '<layer_to>')
    -- one row per expected combination from wave plan document
  ) AS t(object_name, source_system_id, layer_from, layer_to)
)
SELECT wo.object_name, wo.source_system_id, wo.layer_from, wo.layer_to
FROM wave_objects wo
LEFT JOIN migration_meta.recon_results rr
  ON  rr.object_name      = wo.object_name
  AND rr.source_system_id = wo.source_system_id
  AND rr.wave_id          = '<wave-id>'
  AND rr.layer_from       = wo.layer_from
  AND rr.layer_to         = wo.layer_to
WHERE rr.object_name IS NULL;
```

Any row returned = BLOCKED. List all missing combinations in the BLOCKED message.

---

## Rollback Checklist Items (per object)

For every object in the wave, include in Section 3 of the cutover runbook:

1. **Rollback SQL — target layer tables:**
   ```sql
   DELETE FROM <target_layer_schema>.<object_table>
   WHERE source_system_id = '<sys>';
   ```
   Each DELETE requires a separate user CONFIRM before execution.

2. **Rollback SQL — keymap entries:**
   ```sql
   DELETE FROM migration_meta.keymap_<object>
   WHERE source_system_id = '<sys>';
   ```

3. **Downstream dependency check:**
   List all objects that reference this object's keymaps. Any downstream object may need
   its own rollback if this object is rolled back. Surface this dependency chain explicitly
   in the runbook — do not assume rollback is isolated.

---

## Cutover Runbook Sections (required)

| Section | Contents |
|---------|----------|
| 1 — Dress-Rehearsal Checklist | Pre-cutover checks, system freeze steps, recon re-run confirmation, rollback SQL verification on staging |
| 2 — Go/No-Go Evidence Table | Populated from migration_meta.recon_results — never from memory |
| 3 — Rollback Plan | Per-object rollback SQL, keymap revert, downstream dependency chain |

---

## Hard Gates

**NEVER approve cutover with a missing recon_results entry — absence = BLOCKED.**
**NEVER accept verbal assurance as evidence — query migration_meta.**
**NEVER write a cutover_approved signoff without displaying the complete evidence table.**
**NEVER roll back without explicit user CONFIRM for each object affected.**
**NEVER populate the evidence table from memory — it must come from migration_meta queries.**
