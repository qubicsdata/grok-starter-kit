---
name: structured-elicitation
description: Use when an agent gathers requirements or intent from a user through a multi-question dialogue before producing a document (spec, requirements, intent, design brief).
---

# Structured Elicitation

## Core principle

Elicit, don't assume. Ask one question at a time, ground questions in what already exists, and never invent answers the user did not give. This skill is the fleet's single source for the *generic* intake discipline — import it rather than restating it.

(Consolidates the fleet's intake conventions; the explore-first, scope-triage, and draft-self-review steps are adapted from superpowers `brainstorming`, MIT © 2025 Jesse Vincent.)

## The discipline

**0. Explore before asking.** Before the first question, read available context — existing target docs (to extend, not overwrite), relevant source, recent state. Never ask what a short read would answer; ground every question in what exists.

**1. Scope-triage before detail.** If the request spans multiple independent subsystems or projects, surface that and help decompose *before* spending questions refining one. Do not burn the whole question budget on a request that should be split first.

**2. One question per turn — with one sanctioned exception.** Ask exactly one
question; wait for the answer before the next. Where the domain has a sensible
default, lead with a concrete recommendation or options rather than an open prompt.
If an answer is ambiguous, ask one clarifying follow-up before moving on.
*Batched-form exception:* when (a) the requester supplied a substantive description
of the goal up front AND (b) the remaining questions are mutually independent, you
may present them as ONE structured form in a single message. Ambiguous or bare
intent always gets the one-at-a-time flow — ambiguity is exactly when serial
elicitation earns its cost.

**3. No invented answers.** Do not infer or assume. If the user defers, record the gap explicitly rather than filling it in.

**4. Self-review the draft before presenting.** With fresh eyes, scan the draft for placeholders/TBDs, internal contradictions, scope creep, and any requirement open to two interpretations (pick one, make it explicit). Fix inline, then present.

**5. Confirm before writing.** Present the complete draft and get explicit confirmation before writing to disk. When extending an existing doc, present only the new sections (a diff) for confirmation and never alter previously confirmed sections.

## Hard gates

**NEVER write to disk before explicit user confirmation of the full draft.**
**NEVER batch multiple questions into one turn, except under the batched-form exception (rule 2 — substantive up-front description + independent questions).**
**NEVER fill in an answer on the user's behalf** — ask, or record the gap.

## Red flags — STOP

- About to ask a question a short read of an existing doc would answer.
- About to ask detailed questions about a request that actually spans several projects.
- About to present a draft you have not re-scanned for placeholders and ambiguity.
- About to assume a "reasonable default" for a question the user has not answered.
- About to batch questions without BOTH batched-form-exception conditions holding.

## Note for importing agents

This skill carries the *generic* elicitation discipline only. Keep your agent's domain-specific additions — mandatory question topics, opinionated PIT-11 defaults, required document sections, append modes — in the agent file. Import this skill for the shared rules instead of restating them.
