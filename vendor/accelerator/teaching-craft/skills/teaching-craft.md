---
name: teaching-craft
description: |
  Opinionated pedagogy decision expertise for technical workshops — delivery mode, concept sequencing, cognitive load, practice structure, planned failure, mixed-audience handling, assessment shape, and substrate assumption. Consumed by workshop-companion agents when shaping a session for a specific cohort. Every recommendation leads with a named default derived from constraints, cites the rule that produced it, and includes at least one alternative plus an override hook.
---

# Teaching Craft

## Section 1 — Decision Domains

- MODE-1 Delivery mode (demo-first / concept-first / discovery-first)
- SEQ-1 Concept sequencing (spiral / linear / problem-first)
- LOAD-1 Cognitive load per segment (single-concept / paired-concept / integrative)
- PRAC-1 Practice structure (guided / faded / independent)
- FAIL-1 Planned failure (experienced / narrated / avoided)
- MIX-1 Mixed-audience handling (common-core-plus-variants / parallel-tracks / buddy-pairing)
- ASSESS-1 Assessment shape (process-rubric / artifact-review / peer-critique / before-after)
- SUBSTRATE-1 Substrate assumption (goal-shaped / step-shaped)

## Section 2 — Constraint Inputs

- `audience_composition` → MIX-1, LOAD-1 (a room spanning engineers to non-technical staff cannot share one cognitive-load budget)
- `cohort_continuity` (same group across sessions / fresh group per session) → SEQ-1, MIX-1 (a continuing cohort can carry vocabulary forward; a fresh one cannot)
- `substrate_source` (instructor-supplied / learner-supplied) → SUBSTRATE-1, ASSESS-1 (learner-supplied substrate removes any single correct answer)
- `concept_type` (capability / failure mode / judgement call / integrative) → MODE-1, FAIL-1, LOAD-1 (failure modes are learned by collision, capabilities by demonstration, and integrative concepts overload a segment unless the load is deliberately split)
- `session_length` → LOAD-1, PRAC-1 (practice time is what gets squeezed; protect it explicitly)
- `session_index` (position in the series) → PRAC-1 (early sessions guide, later sessions fade support)
- `prior_exposure` (has the cohort used agents before) → MODE-1, SEQ-1 (naive rooms need demo-first; experienced rooms resent it)
- `assessment_purpose` (formative / summative) → ASSESS-1 (formative assessment tolerates ambiguity; summative does not)

## Section 3 — Opinionated Defaults

- MODE-1: Demo-first. Show the capability working before naming it. Agentic tooling has a credibility problem that abstract description makes worse, not better.
- SEQ-1: Spiral. Revisit each concept at increasing depth across sessions rather than exhausting it once. Agentic practice compounds; single-pass coverage does not stick.
- LOAD-1: Single-concept per segment, maximum 20 minutes before hands-on. One new idea, then immediate application.
- PRAC-1: Guided in sessions 1–2, faded in 3–4, independent thereafter. Support is withdrawn on a schedule, not improvised.
- FAIL-1: Experienced. Learners hit the failure themselves under supervision.
- MIX-1: Common core plus track variants. One shared exercise premise, three substrate-specific paths.
- ASSESS-1: Process rubric. Score prompt quality, decomposition, and verification behaviour.
- SUBSTRATE-1: Goal-shaped. State the outcome and the verification, never the directory path or the command.

## Section 4 — Derivation Rules

- TEACH-D-1: When the cohort has no prior exposure to agentic tooling and the concept is a capability, choose demo-first (MODE-1) because a working demonstration establishes that the capability is real before the learner is asked to invest effort in it; concept-first framing reads as marketing to a sceptical room.
- TEACH-D-2: When the cohort is mixed-expertise and progresses through the series together, choose common-core-plus-variants (MIX-1) over parallel tracks, because parallel tracks fracture the shared vocabulary that later sessions depend on; a room that cannot discuss the same exercise loses the cross-discipline conversation that is the main reason to mix the room at all.
- TEACH-D-3: When the concept being taught is itself a failure mode, choose experienced failure (FAIL-1) because narrated failure produces recognition without caution; learners who have only heard about over-eager scope will not slow down when they meet it, whereas learners who have lost work to it will.
- TEACH-D-4: When the substrate is learner-supplied, choose goal-shaped instructions (SUBSTRATE-1) because step-shaped instructions encode assumptions about directory layout, framework, and test runner that will not hold across an unknown set of repositories.
- TEACH-D-5: When the substrate is learner-supplied, choose a process rubric (ASSESS-1) because no single correct output exists across differing codebases; scoring output correctness in that setting rewards whoever brought the easiest problem.
- TEACH-D-6: When session length is under 90 minutes and the concept is integrative, reduce to single-concept load (LOAD-1) and defer the integration to a later session, because integrative segments consume practice time first and a session that demonstrates without practising produces no transfer.
- TEACH-D-7: When each session draws a fresh group rather than a continuing cohort, choose linear sequencing (SEQ-1) over spiral because spiral revisiting depends on learners recalling an earlier pass through the same concept from a prior session; a fresh room has no earlier pass to recall, so revisiting only re-teaches from zero and spends practice time the session cannot afford twice.
- TEACH-D-8: When the cohort has substantial prior exposure to agentic tooling and continues together across the series, choose problem-first sequencing (SEQ-1) over spiral because experienced learners already hold the vocabulary that spiral revisiting exists to build; opening on a realistic problem lets them retrieve and apply what they already know instead of sitting through scaffolding they no longer need.
- TEACH-D-9: When the session length is too short to leave room for recovery from a stalled attempt, choose guided practice (PRAC-1) even in a session the series schedule would otherwise fade or hand off, because independent struggle that runs out of time before resolving teaches learners to give up rather than to debug; a compressed session cannot absorb that risk the way a full-length one can.
- TEACH-D-10: When the assessment purpose is summative and the substrate is instructor-supplied, choose artifact-review (ASSESS-1) over a process rubric because a controlled, instructor-supplied substrate makes the resulting artifacts comparable across learners, and that comparability is what lets a summative judgement stay defensible after the session ends; a submitted artifact is the only evidence that persists for an evaluator who was not there to watch.

## Section 5 — Recommendation Output Contract

Every recommendation emitted by a consuming agent must carry four parts:

1. **Decision** — the chosen option, named using its domain code, for example `MODE-1: demo-first`.
2. **Derivation** — the `TEACH-D-*` rule that produced it, or the literal phrase `defaults apply` when no rule fired.
3. **Alternative** — at least one named option not chosen, with the condition under which it would win.
4. **Override hook** — the exact input the instructor can change to force a different outcome, for example `set prior_exposure: experienced`.

A recommendation missing any of the four parts is incomplete and must not be emitted.

## Section 6 — Enforcement Handoff

- Prose quality in any authored handout, deck, or lab narrative hands off to `anti-ai-tell-rules` and `voice-guide` from content-companion. Teaching material that reads as machine-generated undermines the credibility of the session.
- Severity language in any review or critique of workshop material hands off to the promoted `severity-scale` skill, so findings rank consistently.
- Assessment rubric construction hands off to `scoring-rubric` from self-evolution-companion for rubric shape, then diverges: teaching-craft scores learner process, not agent output.
