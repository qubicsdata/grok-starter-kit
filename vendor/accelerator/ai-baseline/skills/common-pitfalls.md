---
name: common-pitfalls
description: |
  Hard-won lessons from every post-mortem and review cycle in this fleet. Read before authoring any agent, skill, or command file. Each rule has an ID (PIT-1..N) and a one-line detection criterion — apply them in generate-agent output and critic-agent reviews.
contract_version: 1.0.0
---

# Common Pitfalls Gate

Every rule below was derived from a real defect found in this fleet. Apply them during authoring (generate-agent) and verify them during review (critic-agent).

---

## PIT-1 — Baseline import scope

**Rule:** Every authored agent MUST import `baseline-enforcer` at session start — EXCEPT: (a) the generated `spec-enricher.md`, and (b) verbatim ai-baseline copies such as `audit-trail-agent.md`.

**Detection:** Check every agent file with `name:` frontmatter. If the system prompt lacks "Import the baseline-enforcer skill" and the file is not a spec-enricher or a verbatim baseline copy → VIOLATION.

---

## PIT-2 — $ARGUMENTS passed without brackets

**Rule:** Every command invocation that forwards user input MUST use `$ARGUMENTS` (bare, no brackets). Using `[$ARGUMENTS]` treats it as a literal string.

**Detection:** `grep -F '[$ARGUMENTS]'` in any command or agent file → VIOLATION.

---

## PIT-3 — Path-safety guard for file-reading agents

**Rule:** Any agent that reads files from paths provided by the user MUST validate the resolved path stays within the git root. Pattern: resolve via `realpath`, confirm it is a prefix of `git rev-parse --show-toplevel`.

**Detection:** Agent reads user-supplied paths AND lacks a git-root containment check → VIOLATION.

---

## PIT-4 — Tools section required for disk-touching agents

**Rule:** Any agent whose system prompt instructs it to read, write, or run shell commands MUST include a `## Tools` section listing the permitted tool names.

**Detection:** Agent prompt contains "read", "write", "run", "execute", or "shell" AND the file has no `## Tools` section → VIOLATION.

---

## PIT-5 — Build tools ship no baseline or enricher

**Rule:** Plugins classified as `build-tool` (currently: `agent-builder`, `assimilator`) MUST NOT ship `skills/baseline-enforcer.md` or `agents/spec-enricher.md`.

**Detection:** `find <build-tool-dir> -name baseline-enforcer.md -o -name spec-enricher.md` returns results → VIOLATION.

---

## PIT-6 — Canonical plugin.json field set

**Rule:** `plugin.json` MUST contain exactly these fields (and no others unless whitelisted in validate-fleet.py): `name`, `version`, `description`, `category`, `author`, `keywords`. Adding phantom fields (e.g. `tags`, `type`, `extra`) causes fleet validation failure.

**Detection:** Any field in `plugin.json` outside the allowed set → VIOLATION.

---

## PIT-7 — grep -F for user-supplied values

**Rule:** When an agent uses shell `grep` to search for a value derived from user input, it MUST use `grep -F` (fixed-string) not `grep` (regex). User values containing `.`, `*`, `[`, etc. silently match wrong strings under regex mode.

**Detection:** Agent prompt instructs `grep <user-value>` without `-F` flag → VIOLATION.

---

## PIT-8 — Behavioral-scenarios header count matches actual count

**Rule:** Every `tests/behavioral-scenarios.md` that declares a total count in its header (e.g. "Total: 39 scenarios") MUST match the actual number of scenario headings in the file. Accepting both `### ` and `## Scenario ` heading styles.

**Detection:** Parse declared count from header; count actual headings (both styles); if they differ → VIOLATION.

---

## PIT-9 — Current model IDs only

**Rule:** All `model:` frontmatter values MUST be one of the three current IDs: `claude-sonnet-4-6`, `claude-haiku-4-5-20251001`, `claude-opus-4-8`. Deprecated aliases (e.g. `claude-opus-4`, `claude-sonnet-4-5`, any `us.anthropic.*` ARN) are forbidden.

**Detection:** `grep -r "^model:" <plugin>/agents/ <plugin>/skills/` finds a value not in the approved set → VIOLATION.

---

## PIT-10 — Spec-enrichers must never apply to every spec

**Rule:** A `spec-enricher.md` MUST declare concrete relevance triggers. An enricher that returns APPLIES_BECAUSE for every spec regardless of content is a defect — it bloats every enrichment run and dilutes signal.

**Detection:** Enricher body lacks at least one specific named trigger (e.g. "spec defines financial operations", "spec includes auth or user roles") → VIOLATION.

---

## PIT-11 — Decision agents must encode opinionated, traceable craft

**Rule:** Any agent whose role includes recommending, selecting, choosing, or advising on domain options (e.g. palette, typography, layout, tech stack, data schema, API style, incident severity, content tone) MUST: (a) lead with an opinionated default recommendation; (b) expose the constraint-derivation behind it — cite the rule or design-brief input that drove the choice; and (c) keep the recommendation overridable and distinct from hard requirements (never `MUST`). It MUST NOT present a neutral menu of options with no recommendation, nor rely on un-encoded model taste ("it depends", "present trade-offs and wait", "do not choose"). Where a craft pack (`*-craft.md`, per `craft-pack-schema`) exists for the domain, the agent MUST consume it.

**Scope:** Applies ONLY to decision/recommendation/advisory agents. Mechanical and infra agents (audit-trail, pii-scrub, cost-gate, formatters, extractors that make no choice) are out of scope — do not flag them.

**Detection:** The agent's stated purpose includes recommend/select/choose/advise on domain options AND any of: (i) it instructs presenting options without a recommendation ("present trade-offs and wait", "list pros and cons", "do not choose"); (ii) it makes domain recommendations without citing a derivation rule or brief input; (iii) a `*-craft.md` pack covers the domain but the agent does not import it → VIOLATION.

---

## PIT-12 — Skill description states triggers, not workflow

**Rule:** A skill `description` MUST state WHEN to reach for the skill (triggering symptoms, situations, keywords) and MUST NOT restate the skill's workflow or process steps. A description that summarizes the procedure becomes a shortcut a cold agent follows *instead of* reading the body — collapsing a multi-step skill to a single step. Applies to paraphrases and implications of the process, not just a literal step list. (Adapted from superpowers `writing-skills`, MIT © 2025 Jesse Vincent.)

**Scope:** Skill (`skills/`) `description` frontmatter only. Agent and command descriptions are used for routing/dispatch and legitimately summarize what the unit does — out of scope.

**Detection:** A skill `description` enumerates ordered steps, names internal phases, or paraphrases the body's procedure rather than triggering conditions → VIOLATION. Judgment call — not statically decidable; enforced by the LLM critic, not check-plugin-static.py.

---

## PIT-13 — No @-link force-loads in authored bodies

**Rule:** Agent, skill, and command bodies MUST NOT reference other fleet files with `@`-prefixed force-load links (e.g. `@skills/<name>/SKILL.md`, `@agents/<name>.md`). The `@` syntax force-loads the target immediately, burning context before it is needed. Reference a skill by name with an explicit import line ("Import the `<name>` skill …"); reference an agent by dispatch.

**Detection:** `@(skills|agents|commands)/…` appears in any `agents/`, `skills/`, or `commands/` body → VIOLATION. Statically decidable — enforced by `tools/check-plugin-static.py` and backstopped by the critic.

---

## Hard Gate

**STOP before emitting any generated agent, skill, or command file until you have checked every PIT-1..PIT-13 rule against that file.**

DO NOT skip this gate because the file "looks simple." Each pitfall was introduced in a file that looked simple.
