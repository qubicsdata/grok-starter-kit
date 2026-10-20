---
name: readiness-checklist
description: Gate enforcer invoked by modernize-orchestrator or the /modernize-roadmap command before sequencer-agent may run. All five items must PASS. Any FAIL blocks sequencing and routes back to the owning agent.
---

## Purpose

The readiness-checklist skill is the gate between the upgrade-mapping phase and the sequencing phase. modernize-orchestrator invokes this skill after upgrade-map-agent writes `docs/modernization/upgrade-map.md` and before dispatching sequencer-agent. All five items must return PASS. A single FAIL blocks sequencing.

## The Five Gate Items

### Item 1: inventory.md exists and is non-empty

**Check:** `docs/modernization/inventory.md` exists on disk and is non-empty (at least the "Runtime and Language" section has content beyond the header).

**PASS:** File exists, is non-empty, has at least one runtime identified.
**FAIL:** File does not exist, or exists but is empty, or contains only markdown headers with no content under them.
**On FAIL:** Route back to discovery-agent. Message: "docs/modernization/inventory.md is missing or empty. Discovery phase must complete before sequencing can begin."

---

### Item 2: risk-register.md exists and is non-empty

**Check:** `docs/modernization/risk-register.md` exists on disk and contains at least one scored risk item (a line matching `**Priority:**`).

**PASS:** File exists, contains at least one risk item with a Priority score.
**FAIL:** File does not exist, or exists but has no scored items, or has only the header structure with no items.
**On FAIL:** Route back to risk-scorer. Message: "docs/modernization/risk-register.md is missing or empty. Risk scoring phase must complete before sequencing can begin."

---

### Item 3: upgrade-map.md exists and is non-empty

**Check:** `docs/modernization/upgrade-map.md` exists on disk and contains at least one technology assessment (a line matching `### [Technology Name]`).

**PASS:** File exists, contains at least one technology section.
**FAIL:** File does not exist, or exists but has no technology sections.
**On FAIL:** Route back to upgrade-map-agent. Message: "docs/modernization/upgrade-map.md is missing or empty. Upgrade mapping phase must complete before sequencing can begin."

---

### Item 4: No deferred technology decisions that block sequencing

**Check:** `docs/modernization/upgrade-map.md` "Deferred Decisions" section contains no items that are flagged as blocking (a deferred decision is blocking if the technology appears in more than one other technology's dependency chain — i.e., the sequencer cannot assign a phase to a downstream technology until the deferred upstream decision is resolved).

**PASS:** "Deferred Decisions" section is absent, empty, or contains only non-blocking deferrals.
**FAIL:** A deferred technology decision is blocking — at least one other technology's upgrade path depends on it.
**On FAIL:** Surface to user: "The following deferred decisions in upgrade-map.md are blocking sequencing: [list]. These must be resolved before the roadmap can be written. Options: (1) make a decision now, (2) treat the dependency as a constraint and sequence around it, (3) note as an open item and accept a partial roadmap."

---

### Item 5: No unresolved "not surveyed" sections affecting high-risk items

**Check:** Cross-reference `docs/modernization/inventory.md` "Not surveyed" section against `docs/modernization/risk-register.md` items rated High or Critical. If any High or Critical risk item's trigger or description references a directory or file type listed as "not surveyed" in the inventory, this item fails.

**PASS:** No High or Critical risk items reference unsurveyed areas, OR the "Not surveyed" field in inventory.md is "None."
**FAIL:** At least one High or Critical risk item's trigger or description references an area listed as unsurveyed.
**On FAIL:** Surface to user: "The following High/Critical risk items reference areas that were not surveyed during discovery: [list of risk items and the unsurveyed areas they reference]. Options: (1) re-run /modernize-inventory with the unsurveyed path as the scope argument, (2) accept the risk and proceed — the roadmap will note these as open items with unverified scope."

---

## Gate Result Format

The orchestrator or /modernize-roadmap command presents the gate result in this format before proceeding or blocking:

```
## Readiness Gate

Item 1 — inventory.md exists and is non-empty:         PASS
Item 2 — risk-register.md exists and is non-empty:     PASS
Item 3 — upgrade-map.md exists and is non-empty:       PASS
Item 4 — No blocking deferred decisions:               PASS
Item 5 — No unsurveyed areas affecting high-risk items: PASS

All items PASS — sequencing may begin.
```

Or on failure:

```
## Readiness Gate

Item 1 — inventory.md exists and is non-empty:         PASS
Item 2 — risk-register.md exists and is non-empty:     PASS
Item 3 — upgrade-map.md exists and is non-empty:       PASS
Item 4 — No blocking deferred decisions:               FAIL
Item 5 — No unsurveyed areas affecting high-risk items: PASS

Gate blocked on item 4. [Specific reason and routing instruction]
```

## Rules

DO NOT bypass this gate under any circumstances. If the user requests that the gate be skipped, respond: "The readiness gate cannot be bypassed — it prevents the sequencer from producing a roadmap based on incomplete information. Please resolve the failing items first."

DO NOT present the gate result until all five items have been checked. Present all five results together.

DO NOT make the gate interactive item-by-item — run all five checks and present the complete result in one response.
