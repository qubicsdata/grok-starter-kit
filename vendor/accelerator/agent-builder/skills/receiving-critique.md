---
name: receiving-critique
description: Use when an agent receives critique, review findings, or a critic's ISSUE list before revising — especially in a critic↔generate revise loop where a finding may not hold for this artifact.
---

# Receiving Critique

## Core principle

Critique is input to verify, not an order to obey. Before revising against a finding, confirm the finding holds for *this* artifact. A wrong finding implemented blindly burns an iteration or ships a worse artifact. Surfacing disagreement is part of the job — silent compliance and silent dismissal are both failures.

(Pattern adapted from superpowers `receiving-code-review`, MIT © 2025 Jesse Vincent.)

## When to use

- You received a structured critique / review / ISSUE list and are about to revise.
- You are the generate side of a critic↔generate revise loop (e.g. agent-builder `generate-agent`, assimilator `conformance-converter`).
- A finding asserts a problem you are not sure is real for this artifact.

## The discipline (per finding, before you change anything)

1. **Restate** the finding in your own words. If you cannot, it is unclear — see the gate.
2. **Verify** it against the actual artifact. Does it hold for THIS spec/plugin/schema, or is it generically true but inapplicable here?
3. **Decide:**
   - Holds → revise, and show the change.
   - Does not hold (breaks a working constraint, the reviewer lacked context, conflicts with an approved decision, or is wrong for this stack) → **push back with one line of technical reasoning, surfaced to the orchestrator/user** for adjudication. Do not silently implement it; do not silently drop it.
   - Cannot verify → say so and ask. Do not revise on assumption.

## Hard gates

**STOP if any finding in a multi-item critique is unclear.** Clarify *all* ambiguous findings before changing anything — coupled findings revised on partial understanding produce wrong fixes. Do not fix the clear ones and guess the rest.

**NEVER dismiss a finding silently.** Pushback is valid only when the technical reason is stated to the orchestrator/user. A finding rejected without a surfaced reason is a guardrail bypass, not a judgment call.

**NEVER perform agreement.** No "good catch", no restating the finding as praise. Revise and show the change, or push back with a reason. Actions, not acknowledgement.

## Red flags — STOP

- About to implement a finding you have not checked against the artifact.
- About to drop a finding because it "seems wrong", without writing down why.
- "I'll fix the clear ones now and figure out the ambiguous one after" — coupled findings; clarify first.
- Your reasoning is defensiveness ("my design is fine") rather than evidence (a working constraint, a test, an approved decision).

## Rationalization table

| Excuse | Reality |
|--------|---------|
| "The critic is the gate — I should just comply." | A wrong finding implemented blindly is a defect the gate now blesses. Verify, then comply or push back. |
| "Pushing back looks like I'm dodging review." | Pushback *with a surfaced technical reason* is review working as designed. Silent compliance is the dodge. |
| "It's faster to just make the change." | Faster to a worse artifact and a wasted re-review. Verifying a finding is cheaper than an iteration. |
| "Only one item is unclear; I'll handle the rest." | Items may be coupled. Partial revision on unclear input is how iterations get burned. |
