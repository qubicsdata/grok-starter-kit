---
name: accelerate-arc
description: Use when starting any multi-step task in a repo that has the Accelerator fleet installed — walks the route → enrich → plan → execute → review arc, pulling in the right domain plugin at each phase. Trigger on a non-trivial goal, or when the user runs /accelerate.
---

# Accelerate Arc

The Accelerator fleet's horizontal process spine. It does not own domain logic — it
**sequences** existing fleet capabilities so any task flows through a disciplined arc:
`route → enrich → plan → execute → review`, with governance (audit-trail, cost-gate, `/enrich`)
woven through.

## When this fires

A non-trivial, multi-step goal, OR the user runs `/accelerate <goal>`. For a one-line lookup or a
single trivial edit, skip the arc — it is for work with more than one step.

## Behaviour contract (adaptive & opinionated)

- Announce the arc once, then state which phase you are in with a single "**▸ <phase>**" line.
- Walk forward by default, but **silently skip** any phase whose condition is false.
- **Yield immediately** if the user redirects — never insist on the next phase.
- **Never hard-block.** Discipline by default, not by force. No approval gates.
- This is a flexible skill: adapt the arc to the task; do not perform empty phases for ceremony.

## The five phases

| ▸ Phase | Mechanism (existing fleet capability) | Skip condition |
|---|---|---|
| **route** | Dispatch `router-agent` with the goal → 1–3 candidate commands. If `docs/product/passport.json` exists (one existence check + one read), pass its `stage` and top ready story to router-agent as goal context — a goal like "ship checkout" routes toward `/build-next` at stage=building, `/greenfield` at stage=idea (see [[lifecycle-stages]]). | never (always orient first) |
| **enrich** | Run `/enrich <spec>` (the `enrich-spec` skill). | no spec / requirements doc is in play |
| **plan** | Plan the work inline; defer to a planning skill if one is present. | never |
| **execute** | Invoke the routed domain command(s). | never |
| **review** | Invoke the domain-appropriate reviewer (e.g. `/review`, `/security`, `/polyglot-review`). | nothing was changed / produced |

Governance is **woven through, not a phase**: the existing audit-trail and cost-gate hooks run as
configured; you do not invoke them manually.

## Recording review efficacy (required, non-silent)

When the **review** phase runs a reviewer, you MUST record one `review-efficacy` data point so the
risk-tier loop can learn which tiers earn their cost (see [[risk-tier-spec]]). This is the wire that
was previously "best-effort / skip silently" — and it is why the journal stayed empty. Emit it:

- `tier` = the review tier that ran; `found_critical` / `found_important` = whether the reviewer
  raised a real Critical / Important finding; `score_delta` = 0 (no re-score here).
- **How:** inside the accelerator repo, run the deterministic writer —
  `python3 tools/feedback-append.py efficacy --tier <t> --found-critical <bool> --found-important <bool> --score-delta 0`;
  in an installed context, dispatch `self-evolution-companion`'s `feedback-journal-agent` with the
  same `kind:"review-efficacy"` record.
- If **no** writer exists (installed context without self-evolution-companion), do NOT skip
  silently — surface one line, `review-efficacy not recorded: no feedback writer installed`, so the
  gap is visible. Emission never blocks the arc, but its absence is always stated, never swallowed.

## Earned arc-close suggestions (utility plugins)

At the **close** of the arc, surface a passive utility plugin ONLY when the run earned it —
never unconditionally (blanket prompts *reduce* aliveness). Each is a peer suggestion, never a gate:

- If the run was **expensive** — many dispatches or high cost in the audit log
  (`.ai-baseline/audit.*.jsonl`; roll up with `tools/cost-units.py`) — suggest a cost check.
  <!-- handoff: expensive run → consider `/cost-report` -->
- If the work added an **observable surface** (an HTTP API, worker, or datastore — the same `S`
  signal the [[risk-tier-spec]] computes), suggest a health/metrics check.
  <!-- handoff: new observable surface → consider `/observe` then `/slo-status` -->
- If the task produced **durable cross-session state** (a decision, roadmap, or config worth
  keeping), suggest persisting it — and **name the payload**: the one-line durable decision this
  arc made (e.g. "chose event-sourcing over CRUD for the ledger"), never a vague "save your work".
  <!-- handoff: durable decision → consider `/remember` -->
- If the arc was **maintenance-heavy** — it dispatched >=5 subagents, or the session-start
  gateway surfaced a Maintenance line — suggest the self-maintenance arc so the debt gets drained.
  <!-- handoff: heavy arc or surfaced debt → consider `/steward` -->
- If the executed work completed a backlog story's acceptance criteria, or was feature-shaped
  work in a passport repo with no linked story — suggest closing it via `/build-next`, or
  capturing it with `/story`. Earned only: a repo without `docs/product/passport.json` gets nothing.
  <!-- handoff: passport story touched → consider `/build-next` or `/story` -->

A one-line edit or a throwaway task earns none of these — stay silent. The cost trigger reads the
real audit data (now populated by the enriched Stop hook), so the prompt is proportional to actual spend.

## Degradation rules

- **router returns `NOT_FOUND`** → drop the route phase and run the plain `plan → execute → review`
  arc. Say so: "No matching command; proceeding without routing."
- **A routed plugin is not installed** → name the gap, offer the closest installed alternative,
  and continue. Do not stall.
- **Any phase fails** → surface the failure plainly (per the report-faithfully norm) and ask:
  retry, skip, or stop. Never silently swallow a failure.

## Relationship to other layers

- The session gateway makes the fleet *present*; this skill is what it points multi-step work at.
- Cross-plugin handoffs ("Next: run `/api-review`") are peer suggestions that reinforce — but never
  replace — this top-down arc.
- Process discipline (TDD, systematic debugging) belongs to whatever process toolkit the user has;
  this arc sequences *domain* capability and governance, and defers discipline to that toolkit.
