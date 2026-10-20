---
name: prompting-patterns
description: |
  Prompting patterns scoped to agentic work rather than general prompt engineering — output contracts, task decomposition, context budgeting, demanded verification, self-critique loops, and negative instruction. Consumed by workshop-companion agents when a session teaches prompting strategy. Each pattern states the failure it prevents.
---

# Prompting Patterns

Patterns are listed with the failure each one prevents, so they can be taught
against a concrete problem rather than as style advice.

## PP-1 — Output contract

State the shape of the answer before the agent produces it: format, length,
required fields, and what must be absent. Prevents rework caused by an answer
that is correct but unusable.

## PP-2 — Task decomposition

Split a request into steps the agent must complete in order, rather than one
compound instruction. Prevents FM-1 silent partial completion, because each step
has its own observable result.

## PP-3 — Context budgeting

Say what the agent should read and what it should not. Prevents both wasted
context on irrelevant files and confident answers based on nothing.

## PP-4 — Demanded verification

Ask for the evidence rather than the conclusion: the command output, the grep
result, the failing test. Prevents FM-6 unverified success claims.

## PP-5 — Self-critique loop

Ask the agent to argue against its own output before you accept it. Prevents the
first plausible answer from becoming the final answer.

## PP-6 — Negative instruction

State explicitly what must not change or must not happen. Prevents FM-3
over-eager scope, which unstated boundaries invite.
