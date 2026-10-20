---
name: wave-planning-craft
description: |
  Import when sequencing SAP migration objects into waves or evaluating wave plan correctness.
  Triggers on: "wave plan", "tier ordering", "pilot system", "wave sizing", "dependency order",
  "blackout window", "migration sequence", "wave-1 foundation", "Tier 1 master data".
  Read before producing or validating any docs/waves/ document.
contract_version: 1.0.0
---

# Wave Planning Craft

Generative expertise for sequencing SAP migration objects × source systems into ordered waves.
Consumed by wave-planner when producing a wave plan, and by cutover-orchestrator when validating
that prerequisites were respected. Every recommendation leads with a default and carries the
derivation rule that produced it.

## Section 1 — Decision Domains

| ID prefix | Decision domain | The decision being made |
|-----------|-----------------|-------------------------|
| `WAVE-TIER` | Tier placement | Which dependency tier an object belongs to, and therefore which waves may carry it |
| `WAVE-PILOT` | Pilot system selection | Which single source system runs end-to-end first |
| `WAVE-SIZE` | Wave composition | How many objects and how many systems a single wave carries |
| `WAVE-SCHED` | Schedule shaping | How cutover dates, blackout windows, and parallel-operation buffers move wave boundaries |
| `WAVE-DOC` | Plan artifact shape | What the emitted `docs/waves/` document must contain to be reviewable |

## Section 2 — Constraint Inputs

Mapping from brief dimension → the decision(s) it drives.

| Brief dimension | Drives | How |
|-----------------|--------|-----|
| Source system inventory (`config/systems.yaml`) | `WAVE-PILOT`, `WAVE-SIZE` | Row counts and config complexity rank pilot candidates; system count sets fan-out after pilot |
| Migration object set | `WAVE-TIER` | Each object resolves to a tier via the migration-object-catalog |
| Estimated row volumes | `WAVE-SIZE`, `WAVE-SCHED` | High-volume Tier 4 objects force sub-wave isolation and longer durations |
| `cutover-date=<YYYY-MM-DD>` | `WAVE-SCHED` | Work backward from the date to set wave start boundaries |
| `blackout=<YYYY-MM>` | `WAVE-SCHED` | No production load scheduled inside a month-end close |
| `parallel-operation=<weeks>` | `WAVE-SCHED` | Buffer weeks where source and target run simultaneously |
| `pilot=<system-id>` | `WAVE-PILOT` | Explicit override of automatic pilot ranking |
| `wave-size=<n>` | `WAVE-SIZE` | Explicit override of the default object cap |
| Risk tolerance | `WAVE-SIZE` | Lower tolerance narrows waves and delays parallel fan-out |

## Section 3 — Opinionated Defaults

When constraints are silent, these are the defaults.

**Tier placement (`WAVE-TIER`).** Tiers are hard ordering constraints, not guidelines — violating
them causes referential integrity failures in the target system.

| Tier | Objects | Prerequisite |
|------|---------|--------------|
| **Tier 1 — Foundation** | Company codes (`T001`), GL account master (`SKA1`, `SKAT`), currency/fiscal-year config | None — loads first in any plan |
| **Tier 2 — Master Data** | Business partners (`BUT000`, `BUT020`), materials (`MARA`, `MARC`), customers (`KNA1`, `KNB1`), vendors (`LFA1`, `LFB1`) | Tier 1 loaded AND reconciled |
| **Tier 3 — Open Items** | AR open items, AP open items, partial deliveries | Tier 1 + Tier 2 loaded AND reconciled per system |
| **Tier 4 — Full Transactional History** | Complete GL posting history, full material documents, full sales/purchase orders | Tier 1 + Tier 2 loaded AND reconciled; never co-scheduled with Tier 3 |

**Pilot selection (`WAVE-PILOT`).** One source system runs end-to-end through all tiers before any
fan-out. Rank candidates from `config/systems.yaml` by, in priority order: (1) smallest estimated
row count across all objects, (2) simplest SAP configuration — fewest company codes and custom
programs, (3) non-production-critical — a subsidiary or regional entity, never the parent.

**Wave sizing (`WAVE-SIZE`).**

| Default | Value | Rationale |
|---------|-------|-----------|
| Max migration objects per wave | 3 | Limits blast radius; keeps reconciliation reviewable |
| Tier 4 isolation | One source system per sub-wave | GL history volume and risk require isolation |
| Pilot system in Wave 1 | Required | Contains risk before fleet-wide expansion |
| Concurrent system loads (Tier 2+) | All systems, only after pilot passes | Parallelism is earned by a green pilot, not assumed |

**Schedule shaping (`WAVE-SCHED`).** Default to no parallel-operation buffer and no blackout unless
named. When a stated constraint cannot be satisfied, surface the conflict and present alternatives
rather than silently relaxing it.

## Section 4 — Derivation Rules

- `WAVE-D-1`: When an object appears in the migration-object-catalog, choose its catalog tier because tier membership is a referential-integrity property of the object, not a scheduling preference.
- `WAVE-D-2`: When any Tier 3 or Tier 4 object is proposed, choose to place it only after its Tier 1 and Tier 2 prerequisites are both loaded and reconciled, because open items and history post against master data that must already exist.
- `WAVE-D-3`: When Tier 3 and Tier 4 objects are both in scope for one system, choose separate waves because co-scheduling them makes a failed reconciliation ambiguous between the two loads.
- `WAVE-D-4`: When no `pilot=` constraint is given, choose the system ranking highest on row count, then config simplicity, then business criticality, because pilot cost should be low and pilot failure should be survivable.
- `WAVE-D-5`: When a `pilot=` constraint is given, choose the named system but validate it exists in `config/systems.yaml`, because an unvalidated pilot ID silently produces an unrunnable plan.
- `WAVE-D-6`: When no `wave-size=` constraint is given, choose a cap of 3 objects per wave because reconciliation review effort grows faster than object count.
- `WAVE-D-7`: When a Tier 4 object is scheduled, choose one source system per sub-wave because full-history volume dominates the wave's runtime and failure surface.
- `WAVE-D-8`: When the pilot system has not passed its reconciliation gates, choose to keep remaining systems unscheduled because fan-out before a green pilot multiplies an unfixed defect across the estate.
- `WAVE-D-9`: When a `blackout=<YYYY-MM>` is declared, choose to move any production load out of that month because month-end close contends for the same source systems.
- `WAVE-D-10`: When a `cutover-date=` is declared, choose wave boundaries derived backward from that date because a forward-derived plan hides the slack that has already been consumed.
- `WAVE-D-11`: When a constraint set is unsatisfiable, choose to surface the conflict with at least one compliant alternative because silently dropping a constraint destroys the plan's evidence value.

## Section 5 — Recommendation Output Contract

Every wave-plan recommendation MUST surface: the chosen value, the `WAVE-D-*` rule ID(s) that
produced it, at least one named alternative, and an override hook.

The emitted `docs/waves/<wave-slug>.md` carries this frontmatter followed by a narrative:

```markdown
---
wave_id: wave-1-foundation
objects:
  - name: company_codes
    tier: 1
    system_ids: [sys01, sys02, sys03, sys04, sys05, sys06, sys07, sys08]
    estimated_rows: 48
    dependency_rationale: "No upstream dependencies. Must load first."
  - name: gl_account_master
    tier: 1
    system_ids: [sys01, sys02, sys03, sys04, sys05, sys06, sys07, sys08]
    estimated_rows: 96000
    dependency_rationale: "No upstream dependencies. Enables all GL postings."
dependencies: []
business_constraints:
  - "pilot_system: sys01 (smallest, simplest)"
  - "blackout: 2026-03 (month-end close)"
estimated_duration: "3 weeks"
prerequisites_confirmed: false
---

## Wave 1 — Foundation

Narrative: object selection rationale, pilot strategy, expected recon gates.
```

Every object MUST carry `dependency_rationale` naming why it sits in this tier, which prerequisites
must be loaded and reconciled before the wave starts, and which downstream objects depend on it.
That field is the evidence the cutover completeness check reads.

**Override hook.** A user may override any default by naming the constraint (`pilot=`, `wave-size=`,
`blackout=`, `cutover-date=`, `parallel-operation=`). Tier ordering is the one exception: it is
never overridable. When a request would violate `WAVE-D-2` or `WAVE-D-3`, refuse the ordering,
state the violated rule, and present a compliant alternative.

## Section 6 — Enforcement Handoff

wave-planning-craft output is validated by cutover-gate-spec (prerequisite evidence must exist for
every object before a wave advances) and recorded through migration-state-spec (wave status and
reconciliation results are read back from migration_meta, never from memory). Any wave placement
that deviates from its cited `WAVE-D-*` rule without an explicit user override is a finding.
