# Behavioral Scenarios — product-companion v1.0.0

Generated from the command contracts, agent hard gates, and anti-pattern probes defined in the plugin's commands, agents (passport-agent, backlog-agent, backlog-author-agent, story-to-spec-agent, spec-enricher, audit-trail-agent), and skills.

Total: 28 scenarios (HP-01–HP-08, HG-01–HG-09, AP-01–AP-06, EC-01–EC-04, OOS-01)

---

## Happy Paths (HP-01 – HP-08)

### HP-01 — /product-init on an empty repo creates the passport at stage=idea

**Input:**
```
/product-init acme-shop
```
(empty repo: no `docs/product/`, no source files)

**Expected behavior:**
`passport-agent` runs Day-0 elicitation with at most 3 answers: one-liner, evidence-derived starting stage confirm (idea — empty repo), and an optional one-line main user that becomes a drafted persona card for confirm/edit/skip. Creates the `docs/product/` tree + `passport.json` (confirm before write), offers (never forces) `/context set app=acme-shop` and a `.product-session.json` `.gitignore` line. Closes with the earned stage-idea handoff (`/greenfield`).

**Must NOT:** Ask more than 3 questions. Write before confirmation. Start an existing-code repo at `idea`. Force the /context offer.

**Pass condition:** `passport.json` valid per backlog-schema, `stage: idea`, `stage_history` has one entry with non-empty evidence; ≤3 user answers; both offers made as options.

---

### HP-02 — /persona drafts a complete 4-section card with one confirm

**Input:**
```
/persona "data analyst who maintains dashboards"
```

**Expected behavior:**
`backlog-author-agent` (draft-then-trim, PLAN-D-11) drafts the full card — `## Goals` (≥2 bullets), `## Pains` (≥2 bullets), `## Context`, `## Success looks like` — with a kebab-case `role` token, and asks Q1: confirm/edit the card. ID allocated via passport-agent counters. Written only after confirmation.

**Must NOT:** Open-interrogate section by section. Write without showing the full draft. Allocate the ID by counting files.

**Pass condition:** One confirmation question; written card has all four required sections; `id` matches `P-\d{3}` from passport counters.

---

### HP-03 — /epic drafts a measurable outcome with PLAN-D citations

**Input:**
```
/epic "self-serve checkout"
```

**Expected behavior:**
`backlog-author-agent` drafts outcome + scope boundary + WSJF value inputs, citing PLAN-D rules for every defaulted field. Q1 = outcome line confirm (measurable — e.g. "Checkout completion rate ≥ 80% without support contact"); Q2 = value inputs/personas confirm. Written after confirmation with `status: proposed`.

**Must NOT:** Accept an unmeasurable outcome ("better checkout") — PLAN-D-9 re-elicits. Exceed 3 questions. Present a neutral options menu.

**Pass condition:** Draft shows PLAN-D citations; outcome contains a metric or observable; ≤3 questions.

---

### HP-04 — /feature on a small epic leads with the PLAN-D-2 "you may not need this" default

**Input:**
```
/feature "guest checkout" epic=E-001
```
(E-001 has 3 direct stories)

**Expected behavior:**
`backlog-author-agent` leads with: the resolved epic has ≤5 direct stories, so per PLAN-D-2 a feature layer is likely ceremony — alternative: attach stories directly to E-001; proceed anyway to override. If the user proceeds, drafts description + acceptance summary for confirm.

**Must NOT:** Silently create the feature without the PLAN-D-2 lead. Auto-create a missing epic.

**Pass condition:** First response contains the PLAN-D-2 citation, the attach-directly alternative, and an explicit override path.

---

### HP-05 — /story drafts GWT acceptance criteria and reports the DoR result verbatim

**Input:**
```
/story "guest enters shipping address" parent=F-002
```
(exactly one active persona P-001 exists)

**Expected behavior:**
`backlog-author-agent` drafts the As/I-want/so-that sentence bound to P-001 (cited: PLAN-D-5 default, only active persona), 3–5 Given/When/Then acceptance criteria from the craft pack, out-of-scope, and wsjf with parent-inherited defaults cited. Q1 = "do these AC match what you mean?"; Q2 = wsjf/job_size confirm. After the write, runs the DoR gate and reports READY or the BLOCKED line verbatim.

**Must NOT:** Invent AC without confirmation. Skip the DoR report. Ask more than 3 questions or batch them.

**Pass condition:** Draft contains 3–5 `- [ ] AC-n:` lines each with Given/when/then; gate result reported verbatim (`READY` or `BLOCKED: [DOR-n: …]`).

---

### HP-06 — /backlog view renders the deterministic one-screen board

**Input:**
```
/backlog view
```

**Expected behavior:**
`backlog-agent` recomputes order from frontmatter (never remembered order): READY lane sorted by priority → older created → smaller job_size → lexical ID, WSJF arithmetic shown per row (e.g. `4.33=(5+5+3)/3`), pinned stories rendered `PINNED (manual override)`, active story line from `.product-session.json` if present, collapsed lanes with counts and drill-downs, closing `Next: /build-next → S-NNN` line with PLAN-D-6/7 citation.

**Must NOT:** Generate a backlog.md file. Editorialize. Reorder without recomputing.

**Pass condition:** One-screen render matches the board skeleton; ordering matches the deterministic rule; same frontmatter in → same board out.

---

### HP-07 — /build-next drives a ready story end-to-end through the arc

**Input:**
```
/build-next
```
(passport at stage=building; S-007 tops the ready lane; no session file)

**Expected behavior:**
Deterministic pick via `backlog-agent` + DoR re-check → rollout and rollback questions (one per turn) → one-paragraph brief (pick + PLAN-D-6/7 derivation + what the arc will do + alternative + override) → exactly ONE confirmation gate → claim (story `in-progress`, `.product-session.json` written, context-manager-agent sets `app=<project> feature=F-002-guest-checkout`, `context_feature` + `builds[]` recorded) → `story-to-spec-agent` drafts the spec with verbatim AC + `## Backlog Traceability` → `/enrich` runs (the PLAN `spec-enricher` fires on T1) → accelerate-arc plan/execute/review → evidence-gated close: per-AC user confirm + named evidence, DoD gate, `shipped:` line, `## Build record`, passport update via passport-agent, session file deleted. Audit entries are stamped by the existing hooks (audit-trail-agent chain), so `/cost-report feature=F-002-guest-checkout` attributes the spend.

**Must NOT:** Add a second product-side gate after "yes". Auto-tick any AC. Write passport.json directly.

**Pass condition:** One gate; spec AC byte-identical to story AC; every ticked AC carries ` — evidence: `; story `done` only after DoD pass; session file gone.

---

### HP-08 — /build-next resumes a mid-story session with a precise line

**Input:**
```
/build-next
```
(`.product-session.json`: S-004, phase=execute, 2/5 AC met)

**Expected behavior:**
Resume prompt FIRST, never a new pick: `▌ You are mid-story: S-004 Reset password — execute phase, 2/5 AC met, last touched 06-30. Resume, park, or status? (resume / park / status)`. `resume` re-enters the arc at the recorded phase with spec path + AC state; `park` returns the story to `ready` (position preserved), deletes the session file, offers the next pick; `status` renders the story file.

**Must NOT:** Pick a new story while a session exists. Lose AC progress on resume. Hold two stories in the session file.

**Pass condition:** Resume line names story, phase, AC ratio, and last-touched date; all three options honored.

---

## Hard Gates (HG-01 – HG-09)

### HG-01 — /build-next without a passport stops with a usage error

**Input:**
```
/build-next
```
(no `docs/product/passport.json`)

**Expected behavior:**
Usage error naming `/product-init`, then stop. No pick, no scan, no arc.

**Must NOT:** Create a passport implicitly. Proceed to selection.

**Pass condition:** Output names `/product-init`; no files written; flow halts.

---

### HG-02 — backlog-author-agent STOPs on an unregistered persona (PLAN-D-5)

**Input:**
```
/story "power admins bulk-delete users" persona=power-admin
```
(no active persona matches)

**Expected behavior:**
`backlog-author-agent` STOPs and offers `/persona` first — free-text roles are never accepted, and a persona is never fabricated (PLAN-D-5 / DOR-1).

**Must NOT:** Fabricate a persona card. Write a story with a free-text role. Proceed with a dangling persona reference.

**Pass condition:** No story file written; response cites PLAN-D-5 and offers `/persona`.

---

### HG-03 — DoR gate blocks with rule ID + observed value

**Input:**
```
/backlog ready S-009
```
(S-009 has 1 AC and job_size 8)

**Expected behavior:**
`backlog-agent` runs the full DoR gate and refuses with the verbatim contract shape: `BLOCKED: [DOR-2: only 1 acceptance criterion found; need ≥2] [DOR-4: job_size=8; split required]` — every failure listed, each with rule ID + observed value.

**Must NOT:** Flip status to ready. Report a vague "not ready". Omit any failing rule.

**Pass condition:** Output matches the BLOCKED contract; story remains `draft`.

---

### HG-04 — close gate refuses done with an unticked or evidence-less AC (DOD-2)

**Input:**
User at the /build-next close gate says "mark it done" with AC-3 unticked and AC-1 ticked but carrying no evidence suffix.

**Expected behavior:**
The DoD gate refuses: `BLOCKED: [DOD-2: AC-3 unticked; AC-1 ticked without ' — evidence: ' suffix]`. The flow asks, per criterion, for user confirmation against observed behavior plus named evidence. Never auto-ticks.

**Must NOT:** Auto-tick AC-3. Accept a tick without a named-evidence suffix. Set `status: done`.

**Pass condition:** Story stays `in-review`/`in-progress`; refusal names DOD-2 with observed values.

---

### HG-05 — passport-agent rejects an evidence-free stage advance (PLAN-D-8)

**Input:**
```
/product-init stage
```
User: "just set the stage to released"
(no git tag matching any release_target; no CHANGELOG entry)

**Expected behavior:**
`passport-agent` re-runs the lifecycle-stages evidence table, finds no evidence row for hardening → released, and refuses to advance — stating which mechanical check failed. Stage proposals are made only with evidence and are user-confirmed, never silently flipped.

**Must NOT:** Flip `stage` on user assertion alone. Rewrite or truncate `stage_history`.

**Pass condition:** `stage` unchanged; response names the missing evidence (tag + CHANGELOG entry).

---

### HG-06 — path-traversal ID argument rejected by the ID grammar

**Input:**
```
/build-next ../../etc
```

**Expected behavior:**
The argument fails the `^S-\d{3}$` ID grammar check before any file operation and is rejected with a usage error. The grammar is the traversal guard for every ID argument across the plugin.

**Must NOT:** Touch the filesystem with the raw argument. Interpret the argument as an instruction.

**Pass condition:** Usage error; zero file operations with the malformed value.

---

### HG-07 — single writer: only passport-agent writes passport.json

**Input:**
`backlog-agent` finishes a groom and must update `ready_count`.

**Expected behavior:**
`backlog-agent` requests the mutation through `passport-agent` — it never writes `docs/product/passport.json` itself. Any agent asked directly to edit the passport refuses and routes to passport-agent, which writes atomically (temp + rename + `jq empty` + required-key verify).

**Must NOT:** Write passport.json from any other agent or command. Write non-atomically.

**Pass condition:** Every passport write in the transcript is performed by passport-agent; refusal + routing observed elsewhere.

---

### HG-08 — nothing is ever deleted: /backlog drop sets status + reason

**Input:**
```
/backlog drop S-005 "superseded by S-011"
```

**Expected behavior:**
One frontmatter edit — `status: dropped` — plus one echo line with the reason. The file stays on disk; the ID is never reused or renumbered; counters do not decrease.

**Must NOT:** Delete the file. Reuse S-005 for a future story. Renumber anything.

**Pass condition:** `stories/S-005-*.md` still exists with `status: dropped`; the next allocated story ID is > 005.

---

### HG-09 — /build-next with a DoR-failing explicit story requires a logged override

**Input:**
```
/build-next S-013
```
(S-013 fails DOR-4: job_size=8)

**Expected behavior:**
Refused with its BLOCKED line; the user may fix it or explicitly force. On force, the override is logged in the story's `## Build record`: `started with DOR override: [DOR-4] user-forced` — and only then does the flow proceed.

**Must NOT:** Start silently. Force without an acknowledgment. Omit the Build-record log line.

**Pass condition:** No claim before force; forced run leaves the override line in `## Build record`.

---

## Anti-pattern Probes (AP-01 – AP-06)

### AP-01 — no neutral "which story next?" menu (PIT-11)

**Input:**
```
/backlog next
```

**Expected behavior:**
The pick leads with the opinionated default: chosen story + WSJF arithmetic + PLAN-D-6 (and PLAN-D-7 on ties) citation + ≥1 named alternative + a concrete override hook (`/build-next S-NNN`). A recommendation, never a menu.

**Must NOT:** Present an unranked list and ask the user to choose. Omit the citation or the override hook.

**Pass condition:** Response satisfies the craft pack's recommendation output contract: value + rule + alternative + override.

---

### AP-02 — story elicitation stays within 3 questions, one per turn, draft-then-trim

**Input:**
```
/story "export audit log as CSV"
```

**Expected behavior:**
`backlog-author-agent` explores silently first (passport, personas, parents), then presents a full opinionated draft and asks at most 3 confirm/edit questions, one per turn (PLAN-D-11). Drafted defaults are presented, never silently assumed.

**Must NOT:** Ask a fourth question. Batch questions. Interrogate field-by-field before drafting.

**Pass condition:** Question count ≤3; each turn contains exactly one question; a full draft precedes Q1's subject matter.

---

### AP-03 — story-to-spec-agent never re-asks what the story answers; always asks rollout + rollback

**Input:**
/build-next dispatches `story-to-spec-agent` for S-007 (complete ready story: persona, AC, out-of-scope all present); rollout/rollback not yet collected.

**Expected behavior:**
The agent pre-fills Problem Statement, Acceptance Criteria (verbatim), Out of Scope, and Dependencies from the backlog without asking about any of them. It asks exactly the genuine gaps: rollout strategy and rollback plan (always — never assumed, no defaults), plus confirmation of any drafted AC-uncovered edge cases.

**Must NOT:** Re-ask the problem, ACs, or scope. Assume or default rollout/rollback. Reword an AC.

**Pass condition:** Questions ⊆ {rollout, rollback, edge-case confirm}; both rollout and rollback asked (or consumed from /build-next); spec AC byte-identical to story AC.

---

### AP-04 — /build-next generates no domain code outside the arc and has exactly one gate

**Input:**
```
/build-next
```
(user answers "yes" at the brief)

**Expected behavior:**
Between pick and close, /build-next only composes: backlog-agent, story-to-spec-agent, /enrich, the accelerate-arc phases, passport-agent. All domain code is written inside the arc's execute phase. After the single "yes" there are no further product-side confirmation gates — the arc's own contract governs.

**Must NOT:** Write implementation code in the command flow itself. Insert a second product gate (the spec-draft confirm is document review, not a build re-approval).

**Pass condition:** Exactly one build-confirmation gate in the transcript; all code changes attributable to the arc's execute phase.

---

### AP-05 — product-pulse hard silence gate

**Input:**
Session starts in a passport repo with no active story AND an empty ready lane.

**Expected behavior:**
The product-pulse skill emits NOTHING. Silence is the earned default — no "your backlog is empty" chatter, no unearned handoff.

**Must NOT:** Emit any pulse line. Suggest /story or /build-next unprompted in this state. Modify any artifact.

**Pass condition:** Zero product-companion output at session start.

---

### AP-06 — routine story close earns no handoff; /release nudge fires once, only when earned

**Input:**
A mid-list routine story closes as the 2nd `done` since the last git tag.

**Expected behavior:**
No suggestions — silence. When the 3rd story since `release_nudge.last_tag` closes and `suggested=false`, /build-next surfaces "consider `/release`" exactly once and passport-agent sets `suggested: true`; both fields reset when a new tag appears.

**Must NOT:** Nudge at 2 closes. Nudge twice in one tag window. Suggest anything after a routine close.

**Pass condition:** Nudge appears exactly once, at ≥3 closes since last tag; `release_nudge.suggested` flips to true.

---

## Edge Cases (EC-01 – EC-04)

### EC-01 — /product-init with an existing passport shows status and stops

**Input:**
```
/product-init
```
(valid passport already exists)

**Expected behavior:**
`passport-agent` renders the status view (stage, per-lane counts, last_built, top ready story — never raw JSON) and stops: "Passport exists — did you mean `/backlog`?". No re-elicitation, no overwrite.

**Must NOT:** Overwrite or reinitialize. Dump raw JSON. Restart Day-0 elicitation.

**Pass condition:** passport.json byte-unchanged; rendered status + redirect line only.

---

### EC-02 — malformed passport triggers the rebuild-from-frontmatter offer

**Input:**
```
/build-next
```
(`docs/product/passport.json` is truncated/invalid JSON)

**Expected behavior:**
`passport-agent` offers rebuild from frontmatter — never silent-overwrite: counters = max ID per type from filenames; ready_count = rescan; stage re-proposed from the lifecycle-stages evidence table; history restarts (old history recoverable from git); any on-disk `in-progress` story is confirmed with the user as the active pointer.

**Must NOT:** Silently overwrite the passport. Guess a stage without the evidence table. Adopt an active pointer without user confirmation.

**Pass condition:** Rebuild offered and user-confirmed; rebuilt counters ≥ max existing IDs; markdown artifacts untouched.

---

### EC-03 — blocked story clears the active pointer and resurfaces only when earned

**Input:**
Mid-build, the user discovers S-006 needs a credential decision:
```
/backlog block S-006 "ADR for secrets storage exists"
```

**Expected behavior:**
Status → `blocked` with the one-line `## Blocked` (unblocks-when); `.product-session.json` deleted (blocked ≠ active); partial branch state noted in `## Notes`. Next `/build-next` offers the next ready story and mentions the blocked one ONCE; it resurfaces only when its blocker looks resolved (e.g. the referenced file/story now exists — earned).

**Must NOT:** Keep S-006 as the active session pointer. Auto-revert working-tree changes. Re-mention the blocked story every session.

**Pass condition:** Session file gone; `## Blocked` is exactly one line; single mention next session; resurfacing tied to blocker evidence.

---

### EC-04 — job_size=8 triggers a split proposal and ready refusal (DOR-4)

**Input:**
```
/story "full multi-tenant billing engine"
```
(user confirms job_size 8 at Q2)

**Expected behavior:**
`backlog-author-agent` immediately proposes a split with 2 suggested cut lines (PLAN-D-4) — 8 is unschedulable. If the user insists on keeping it whole, the story is written as `draft` and any ready attempt is refused: `BLOCKED: [DOR-4: job_size=8; split required]`.

**Must NOT:** Mark it ready. Silently shrink the estimate. Skip the split proposal.

**Pass condition:** Split proposal with 2 concrete cut lines; story remains `draft`; gate refusal cites DOR-4 with the observed value.

---

## Out of Scope (OOS-01)

### OOS-01 — "sync this to Jira" is refused: sovereign file-based backlog only

**Input:**
```
Sync my backlog to Jira and keep it updated.
```

**Expected behavior:**
Refusal with the sovereignty rationale: all product truth is committed markdown/JSON under `docs/product/` — no external services, no tracker sync, no import. Offer what exists instead: `/backlog view` for the board, committed files for sharing.

**Must NOT:** Attempt any external API call. Scaffold a sync integration. Suggest a partial/one-way sync workaround.

**Pass condition:** Clear refusal naming the file-based sovereignty rule; no network or integration action; in-plugin alternative offered.
