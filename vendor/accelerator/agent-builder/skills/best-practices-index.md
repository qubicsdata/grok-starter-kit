---
name: best-practices-index
description: Read before reviewing or generating any agent or skill — curated index of agent and skill authoring best practices
---

# Agent and Skill Best Practices Index

## Agent Design

**Single concern:** Each agent does exactly one thing. If describing it requires "and," split it into two agents.

**Cold-agent readability:** A fresh subagent with only the agent file and inputs must know exactly what to do. No implicit shared state.

**Exit conditions:** Every Agent tool call spawned by an agent must have a defined termination condition. Unbounded loops are a hard failure.

**Tool minimalism:** Request only the tools the agent actually needs. An agent that reads files only needs Read, not Bash + Read + Write.

**Context isolation for critics:** Agents that review output (critic, panel reviewers) must receive only the design spec and the artifact — never the generator's reasoning chain. Contaminated context produces sycophantic review.

**Output contracts:** Every agent must specify its output format in its system prompt. Ambiguous output requires the orchestrator to guess.

**Opinionated, traceable craft:** An agent that recommends or selects within a domain leads with an opinionated default and shows the constraint-derivation behind it (cite the rule or brief input), keeping the recommendation overridable. Neutral option menus and un-encoded "it depends" taste are defects — capture the expertise in a craft pack (`*-craft.md`, per `craft-pack-schema`) the agent consumes. See PIT-11.

## Skill Design

**Trigger precision:** The `description` frontmatter must answer: when exactly should a cold agent reach for this skill? Vague triggers cause misuse.

**Description is a trigger, not a summary:** A skill `description` states WHEN to reach for it (symptoms, situations, keywords) — it MUST NOT restate the skill's workflow or process steps. A description that summarizes the procedure becomes a shortcut a cold agent follows *instead of* reading the body, silently collapsing a multi-step skill to one step. Applies to paraphrases and implications of the process, not just a literal step list. See PIT-12. (Pattern adapted from superpowers `writing-skills`, MIT © 2025 Jesse Vincent.)

**Hard gates required:** Every skill must have at least one `DO NOT` or `STOP` rule with a consequence. Skills without hard gates are suggestions, not guardrails.

**Reference, not narrative:** Skills describe proven patterns for future use. Do not write about how you solved a problem once — write what to do next time.

**Self-contained:** A skill must be fully useful when read in isolation. No references to "the approach we discussed" or "as above."

## Choosing the Guidance Form

Before writing a rule or gate, classify the baseline failure — the form that bulletproofs one failure type measurably backfires on another. Do not reach for a `DO NOT` by default.

| Baseline failure | Right form | Wrong form |
|---|---|---|
| Knows the rule, skips it under pressure | Prohibition + rationalization table + red flags | Soft guidance ("prefer…", "consider…") |
| Complies, but output has the wrong shape (bloated, buried verdict, restated input) | Positive recipe: state what the output IS — its parts, in order | Prohibition list ("don't restate", "never narrate") |
| Omits a required element from something it already produces | Structural: a REQUIRED field/slot in the template it fills | Prose reminders near the template |
| Behavior should depend on a condition | Conditional keyed to an observable predicate | Unconditional rule + exemption clauses |

**Why prohibitions backfire on shaping problems:** under a competing incentive an agent negotiates with "don't X"; in head-to-head tests the prohibition arm produced *more* of the unwanted content than even a no-guidance control. A recipe leaves nothing to negotiate — the output matches the stated shape or it doesn't. Corollaries: no nuance clauses ("don't X unless…" reopens the negotiation — express a real exception as its own conditional), and exemption clauses don't scope (a rule that says "except code blocks" still suppresses code blocks; restructure so the rule can't reach the exempt part).

This refines **Hard gates required**: a skill still needs at least one hard gate, but apply it per individual rule — discipline failures get a prohibition; shaping and omission failures get a recipe or a required slot. (Pattern adapted from superpowers `writing-skills`, MIT © 2025 Jesse Vincent.)

## Orchestration

**Thin orchestrator:** The orchestrator routes and synthesizes. It never generates content. Any orchestrator that writes plugin files is a design failure.

**Parallel when independent:** Specialist reviewers (security, UX, topology) check the same artifact independently — always dispatch in parallel.

**Explicit disagreement:** When reviewers conflict, surface the conflict to the user. Do not silently pick a winner.

**Checkpoint before irreversible actions:** Any action that writes to disk, publishes, or increments a version must be preceded by a structured reasoning checkpoint.

## Model Selection

**Effort matches stakes:** Use the haiku tier for mechanical tasks (format, lint, boilerplate). Use the sonnet tier for generative tasks. Use the opus tier for high-stakes reasoning (critique, synthesis, novel topology). Tier → model ID resolution comes from `tools/model-ids.json`.

**Critic scales with risk:** the critic runs at the review tier's model — sonnet tier at light/standard, opus tier at full — and never below the sonnet tier (see task-scoring's review-tier mapping).

**Show your routing:** Present model assignments to the user with justification. Hidden routing erodes trust.

## Security

**Prompt injection surface:** Any agent that reads untrusted external content (user-provided plugin files, web content) and then acts on it is an injection risk. Sanitize by summarizing structure, not by passing raw content downstream.

**No credential logging:** Skills and agents must never instruct storage or logging of API keys, tokens, or secrets.

**Scope creep:** Agents should not acquire new tool permissions mid-task. All tool needs must be declared upfront.

## Publishing

**Version discipline:** Patch = fix, minor = new capability, major = breaking change. Never auto-increment major.

**Self-audit before publish:** Run the plugin through the auditor-agent before writing to disk. Catch issues before they reach users.

**Breaking change check:** Always run runtime-knowledge-fetch before publishing. A plugin that breaks due to a deprecated API the fetch would have caught is a process failure.
