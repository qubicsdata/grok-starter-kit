# self-evolution-companion

Optional plugin — quality feedback loop for agent outputs.

Constitutional rule: **the loop proposes, never self-modifies.** A human must type
`APPROVE` before any change lands — and after that typed APPROVE, the machine does the
mechanical work (`/refine apply` edits, verifies, and journals; no hand-copying diffs).

## Commands

- `/score <agent> <output>` — manually score one agent output (0–10 each: completeness, safety, accuracy)
- `/score-pending [--sample <0..1>] [--max <n>]` — drain queued score stubs in one budget-capped batch (default: 10 oldest; stops if `.ai-baseline/budget.json` is exhausted)
- `/evolution-report` — summary and trends from `.ai-evolution/feedback.jsonl`
- `/refine <agent>` — propose a prompt-improvement diff from the feedback journal (requires ≥5 entries)
- `/refine tiers` — recommend a review-tier demotion when a tier never pays (≥5 all-unpaid efficacy entries)
- `/refine apply` — after the human types `APPROVE`, apply the proposed diff, verify it, and journal a `refinement-applied` entry

## How it works

Capture is deterministic and free; the LLM only runs on demand, downstream.

1. **Capture (no LLM, continuous):** the ai-baseline `Stop`/`SubagentStop` hook
   (`audit_append.py`) deterministically writes a stub for every scoreable subagent
   output to `.ai-evolution/feedback.jsonl.pending` — agent, plugin, model, session, and
   a transcript reference. No manual seeding required; `/score` remains available for
   ad-hoc manual scores.
2. **Drain (budget-capped batch):** `/score-pending` recovers each stub's output from the
   transcript, dispatches the quality-scorer in ONE batched pass (never per-Stop), and
   appends 9-field quality entries to `.ai-evolution/feedback.jsonl`. It refuses to
   dispatch when `.ai-baseline/budget.json` shows `spent_usd >= limit_usd`, and caps each
   run at `--max` stubs (default 10 oldest).
3. **Trend:** `/evolution-report` shows per-agent averages and improving/stable/declining
   trends.
4. **Propose:** once an agent has ≥5 entries, `/refine <agent>` has prompt-refiner
   propose one opinionated diff to stdout. The agent never writes files.
5. **Approve:** the human reviews the diff and types `APPROVE` (the literal word —
   nothing else counts, and nothing is written before it).
6. **Apply + verify (machine work):** `/refine apply` applies the approved diff with the
   Edit tool, then verifies — in the dev repo it runs `bash tools/validate.sh` (GATE FAIL
   reverts the edit); in an installed context it re-reads the edited file to confirm the
   hunks landed (`validate.sh` is dev-repo-only). It then appends a
   `kind:"refinement-applied"` entry to the journal (see `skills/feedback-schema.md`).

**Gate:** `/refine apply` writes nothing before a typed `APPROVE` from the human
operator. It cannot be bypassed via agent instruction. A `/refine tiers` demotion
recommendation is gated the same way.

## Dev repo vs installed context

- **Dev repo (this repository):** hooks are wired in `.claude/settings.json` and run from
  `tools/hooks/`; `/refine apply` verification runs the full `bash tools/validate.sh`
  fleet gate; dev-only helpers like `tools/feedback-append.py` are available.
- **Installed context (plugin from the marketplace):** the same capture hook ships with
  ai-baseline (`hooks/hooks.json` → `hooks/scripts/audit_append.py`), so pending-stub
  capture works identically. `tools/validate.sh` does not exist there, so `/refine apply`
  verification is a targeted re-read of the edited file; the portable journal writer is
  `feedback-journal-agent`. **Caveat:** editing a plugin under `~/.claude/plugins/cache`
  is overwritten on the next plugin update — apply refinements in the plugin's source
  repo whenever possible.

## Review-efficacy feedback (risk-tier loop)

A second, optional feedback signal closes the loop on risk-tiered review (see
`ai-baseline/skills/risk-tier-spec.md`). After a review pass, the controller that ran
it — the builder orchestrator at build time, or a consumer's review loop — MAY invoke
`feedback-journal-agent` with a `kind:"review-efficacy"` record (tier, whether the
review found a Critical/Important, and the quality-score delta it produced; `paid` is
derived). Once a tier has **≥5 entries that are all `paid:false`**, `/refine tiers`
recommends demoting it one level — behind the same typed `APPROVE`. An epsilon
re-sample (≈1-in-10 builds still run full depth even when demoted) keeps a demotion
reversible so it cannot starve its own evidence. Emission is advisory and opt-in: no
build is forced to journal, and a missing signal simply leaves tiers where they are.

## Author

<your-name> (you@example.com)

## Dependencies

- requires: ai-baseline
