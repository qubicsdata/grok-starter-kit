# product-companion

Product planning layer for the accelerator fleet. Personas, epics, features, user stories, a prioritized WSJF-lite backlog, and a project passport that tracks lifecycle stage — all as committed files under `docs/product/` in your own repository. `/build-next` drives the highest-priority ready story through the accelerate arc: spec → enrich → plan → execute → review → evidence-gated close.

---

## Installation

```bash
# From your project root, install the plugin:
claude plugin install product-companion

# Or reference locally during development:
claude plugin install /path/to/product-companion
```

Ensure `ai-baseline` is installed and active (see Dependencies). The `baseline-enforcer.md` and `audit-trail-agent.md` files are already included verbatim — no separate copy step needed.

---

## Commands

| Command | Description | Example |
|---|---|---|
| `/product-init [project-name] \| show \| stage` | Create or show the project passport — lifecycle stage, backlog root, ID counters. | `/product-init acme-shop` |
| `/persona "name or role"` | Create a user persona card (goals, pains, context, success criteria). | `/persona "Maya the Maintainer"` |
| `/epic "title"` | Create an epic with a measurable outcome and WSJF value inputs. | `/epic "Self-serve checkout"` |
| `/feature "title" [epic=E-NNN]` | Create a feature under an epic. Optional layer — earned only past 5 direct stories (PLAN-D-2). | `/feature "Guest checkout" epic=E-001` |
| `/story "title" [parent=F-NNN\|E-NNN] [persona=P-NNN]` | Create a user story with drafted Given/When/Then acceptance criteria; reports the DoR result verbatim. | `/story "Guest enters shipping address"` |
| `/backlog [view\|next\|groom\|set\|block\|unblock\|drop\|ready\|<lane>\|<ID>]` | View, groom, or mutate the prioritized backlog (WSJF-lite). | `/backlog view` |
| `/build-next [S-NNN]` | Take the highest-priority ready story into the accelerate arc — spec, enrich, plan, execute, review, evidence-gated close. | `/build-next` |

---

## Agents

### passport-agent

Sole reader-writer of `docs/product/passport.json`. Initializes the passport, renders status, allocates IDs from monotonic counters, runs the stage evidence table and proposes lifecycle transitions, and offers rebuild-from-frontmatter recovery when the passport is malformed. Writes atomically (temp file + rename + parse verify). Never advances a stage without matching evidence and user confirmation.

Use when: creating or inspecting the project passport, advancing the lifecycle stage, recovering a corrupted passport.

### backlog-agent

All mechanical backlog operations: frontmatter scan, WSJF-lite recompute, the deterministic ready-lane order, DoR/DoD gate runs with the `BLOCKED: [DOR-n: …]` output contract, one-line mutations, groom (demote rot, re-derive parent statuses, maintain `## Children`), and the one-screen terminal board render. Never flips a story to `ready`/`done` without running the full gate. Never deletes a file.

Use when: viewing the board, grooming, blocking/unblocking/dropping stories, checking what `/build-next` will pick.

### backlog-author-agent

Elicits and writes one backlog artifact (persona, epic, feature, or story) via draft-then-trim: it drafts the full artifact from the product-planning craft rules, then asks at most 3 confirm/edit questions, one per turn. Rejects unmeasurable epic outcomes, proposes splits for `job_size: 8` stories, and stops to offer `/persona` when the beneficiary is not a registered active persona — never fabricates one. Confirms before every write.

Use when: capturing a new persona, epic, feature, or story.

### story-to-spec-agent

The bridge from backlog to build. Reads one ready story plus its parent and persona, then drafts `docs/specs/NNNN-<slug>.md` in dev-companion's exact spec shape plus a `## Backlog Traceability` section. Acceptance criteria are copied verbatim — never reworded. Asks only the genuine gaps: rollout strategy, rollback plan, and edge cases the ACs don't cover. Never re-asks what the story already answers.

Use when: turning a ready story into a build-ready spec (normally invoked by `/build-next`).

### spec-enricher

The `PLAN` enricher for the fleet's `/enrich` runner. When a spec carries backlog traceability, backlog IDs, or an unbound user-type dimension, it injects `PLAN-*` production requirements (verbatim ACs, scope boundary, cost-attribution label, persona binding) into the spec's production requirements. Emits `NOT_APPLICABLE` with a reason for specs with no backlog or user-type dimension.

Use when: running `/enrich` on any spec (fires automatically as part of the enrich runner).

### audit-trail-agent

Byte-identical copy of the fleet baseline audit-trail agent from `ai-baseline` (drift-checked). Records every agent invocation into the audit log.

---

## Skills

| Skill | Purpose |
|---|---|
| `backlog-schema` | Canonical schemas — ID grammar, status lifecycles, WSJF-lite ordering, DoR/DoD gate predicates, write-safety protocol. |
| `lifecycle-stages` | The passport's stage enum, the evidence table each transition requires, and the stage → earned-handoff map. |
| `product-planning-craft` | The craft pack — PLAN-D derivation rules behind every planning decision the agents make. |
| `product-pulse` | Self-activating session pulse: surfaces the lifecycle stage, active story, and earned next step in at most one line. Hard silence gate — no active story and an empty ready lane emits nothing. |
| `baseline-enforcer` | Verbatim fleet baseline copy (drift-checked). |

---

## Day-0 example

```
/product-init acme-shop
# → passport created at the earned stage, docs/product/ tree scaffolded (≤3 questions)

/persona "Maya the Maintainer"
# → P-001 persona card drafted (goals, pains, context, success), one confirm, written

/epic "Self-serve checkout"
# → E-001 with a measurable outcome and WSJF value inputs, PLAN-D citations in the draft

/story "Guest enters shipping address"
# → S-001 under E-001, bound to P-001, 3–5 drafted Given/When/Then acceptance criteria,
#   wsjf with cited defaults; DoR result reported verbatim (READY or BLOCKED: [DOR-n: …])

/build-next
# → picks S-001 (WSJF arithmetic + rule citations shown), asks rollout + rollback,
#   one confirmation gate, then: spec with verbatim ACs → /enrich → plan → execute →
#   risk-tiered review → evidence-ticked close → passport updated
```

---

## Artifacts produced

| Artifact | Location |
|---|---|
| Project passport | `docs/product/passport.json` |
| Personas | `docs/product/personas/P-NNN-<slug>.md` |
| Epics | `docs/product/epics/E-NNN-<slug>.md` |
| Features (optional layer) | `docs/product/features/F-NNN-<slug>.md` |
| Stories | `docs/product/stories/S-NNN-<slug>.md` |
| Feature specs (via `/build-next`) | `docs/specs/NNNN-<slug>.md` |

Nothing is ever deleted: `dropped` is a status, IDs are never reused, and stage history is append-only.

---

## Sovereignty

All product truth lives as committed markdown/JSON under `docs/product/` in your own repository. There is no external service, no Jira/Linear sync, and no import/export bridge — requests to sync or import from an external tracker are refused by design. Your backlog is versioned, diffable, greppable, and yours.

## Dependencies

- requires: ai-baseline
