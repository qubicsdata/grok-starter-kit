# Behavioral Test Scenarios — greenfield-project-initializer
Generated: 2026-06-19T00:00:00Z
Coverage: 31 scenarios across 7 agents

---

## Happy-Path Scenarios (HP)

### HP-01: Full lifecycle from scratch
**Agent under test:** greenfield-orchestrator  
**Entry point:** `/greenfield "a B2B invoicing platform for small businesses"`  
**Preconditions:** No `.greenfield-state.json`, no `docs/` directory  
**Steps:**
1. Orchestrator checks for `.greenfield-state.json` — absent, starts phase 1
2. Passes project description to requirements-agent as context seed
3. requirements-agent asks all 8 questions one at a time
4. Orchestrator presents env promotion menu; user selects option 1 (dev → staging → prod)
5. requirements-agent appends env strategy to docs/requirements.md
6. security-baseline skill asks all 6 questions; requirements-agent appends answers
7. Orchestrator routes to sys-design-agent; agent presents 2 architecture shapes
8. User selects "Modular Monolith"; sys-design-agent writes docs/system-design.md
9. Orchestrator routes to tech-stack-agent; agent presents ≥2 options per layer with tech-radar ratings
10. User confirms all layer choices; tech-stack-agent writes docs/tech-stack.md
11. greenfield-checklist skill runs — all 6 items PASS
12. repo-scaffold-agent presents file manifest; user confirms; files written
13. ci-designer asks provider; user says "GitHub Actions"; pipeline written to .github/workflows/ci.yml
14. Orchestrator writes final .greenfield-state.json; presents completion summary  
**Expected outcome:** All 9 artifacts on disk; .greenfield-state.json shows phase-8 complete; completion summary lists all files with no open items

---

### HP-02: Resume interrupted session
**Agent under test:** greenfield-orchestrator  
**Entry point:** `/greenfield`  
**Preconditions:** `.greenfield-state.json` present with `last_checkpoint: "phase-5"`, `phases_complete: ["phase-1","phase-2","phase-3","phase-4","phase-5"]`; `docs/requirements.md` and `docs/system-design.md` on disk  
**Steps:**
1. Orchestrator reads `.greenfield-state.json`
2. Translates checkpoint IDs to human-readable labels using Phase Labels table
3. Presents resume summary: "Last completed step: System design complete. Steps completed: Requirements complete, Team constraints captured, Environment promotion strategy recorded, Security baseline complete, System design complete."
4. User selects "resume"
5. Orchestrator routes to tech-stack-agent (phase 6)
6. Session continues from phase 6 onward  
**Expected outcome:** Raw checkpoint IDs ("phase-5", []) never shown to user; resume continues from correct phase; no duplicate work

---

### HP-03: Standalone `/adr` without prior session
**Agent under test:** adr-agent  
**Entry point:** `/adr "Choice of primary database engine"`  
**Preconditions:** No `.greenfield-state.json`, no `docs/` directory (or any project state)  
**Steps:**
1. Command reads `$ARGUMENTS` — decision statement present
2. Routes to adr-agent
3. adr-agent cannot find docs/requirements.md — defaults to Nygard format
4. adr-agent checks docs/adr/ — absent, sequence number is 0001
5. Agent asks user to provide two options and rationale via dialogue
6. adr-template validation: ≥2 options present, rationale present, status "Proposed", date set
7. Draft presented as Markdown code block; user confirms
8. File written to docs/adr/0001-primary-database-engine.md  
**Expected outcome:** Well-formed Nygard ADR written; no prior session required; agent did not invent options or rationale

---

### HP-04: Standalone `/scaffold` with all prerequisite docs present
**Agent under test:** repo-scaffold-agent (via `/scaffold` command)  
**Entry point:** `/scaffold`  
**Preconditions:** `docs/requirements.md`, `docs/system-design.md`, `docs/tech-stack.md` all present and non-empty; env promotion and security baseline sections present in requirements  
**Steps:**
1. Command checks docs/tech-stack.md — present
2. greenfield-checklist runs — all 6 items PASS (files exist, sections verified)
3. No deferred security baseline answers
4. Routes to repo-scaffold-agent
5. Agent reads both docs, runs scaffold-spec validation internally
6. Presents file manifest as tree; user confirms
7. Scaffold files written; ci-designer invoked  
**Expected outcome:** Scaffold generated without re-running requirements/design/tech-stack phases; all 6 checklist items passed; ci-designer asked for CI provider

---

### HP-05: Tech-stack agent presents Hold-rated technology with warning
**Agent under test:** tech-stack-agent  
**Entry point:** `/tech-stack`  
**Preconditions:** `docs/system-design.md` present  
**Steps:**
1. tech-stack-agent presents options for Language/runtime layer
2. One option is a Node 14 (EOL) runtime — rated Hold
3. Agent includes it in the table with "HOLD — cannot be recommended as a primary choice. Included for reference."
4. User attempts to select the Hold-rated option
5. tech-radar skill surfaces warning and requires explicit acknowledgement
6. User acknowledges; pending ADR created for that risk decision  
**Expected outcome:** Hold-rated technology never silently accepted; warning displayed; ADR flagged as risk-acknowledged; session continues only after explicit user confirmation

---

### HP-06: Requirements agent extends existing document
**Agent under test:** requirements-agent  
**Entry point:** `/requirements`  
**Preconditions:** `docs/requirements.md` exists with Project Purpose, Scope, and Functional Requirements sections; missing Non-Functional Requirements and Definition of Done  
**Steps:**
1. Command detects existing docs/requirements.md
2. Informs user: "An existing requirements document was found. I will extend it with any missing sections."
3. requirements-agent reads existing doc, identifies missing topics (NFRs, timeline, integrations, DoD)
4. Asks only about missing topics
5. Presents diff (new sections only) for confirmation
6. Writes to disk — existing sections unmodified  
**Expected outcome:** Only missing sections asked; existing content unchanged; diff shown before write; user confirms before write

---

### HP-07: ADR agent selects MADR format for large team
**Agent under test:** adr-agent  
**Entry point:** `/adr "API style selection (REST vs GraphQL)"`  
**Preconditions:** `docs/requirements.md` present with "Size: 8 engineers" in Team Profile  
**Steps:**
1. adr-agent reads docs/requirements.md — team size 8 ≥ 5
2. Selects MADR format
3. Gathers options (REST, GraphQL) and rationale from user
4. Applies adr-template validation — all MADR required sections present
5. Presents full draft; user confirms; written to docs/adr/  
**Expected outcome:** MADR format used (not Nygard); all MADR sections present including Decision Drivers, Pros and Cons of Options; sequence number correct

---

## Hard-Gate Scenarios (HG)

### HG-01: Scaffold blocked when docs/requirements.md missing
**Agent under test:** greenfield-checklist skill (via `/scaffold`)  
**Entry point:** `/scaffold`  
**Preconditions:** `docs/tech-stack.md` present; `docs/requirements.md` absent  
**Expected behaviour:** greenfield-checklist item 1 FAILS; checklist result shows BLOCKED; user directed to run `/requirements`; no scaffold files written

---

### HG-02: Scaffold blocked when env promotion strategy missing
**Agent under test:** greenfield-checklist skill  
**Entry point:** `/scaffold`  
**Preconditions:** All docs present; `docs/requirements.md` has no `## Environment Promotion Strategy` section  
**Expected behaviour:** greenfield-checklist item 2 FAILS; checklist blocked; user directed to requirements-agent append mode; scaffold not generated

---

### HG-03: Scaffold blocked when security baseline has deferred answers
**Agent under test:** greenfield-checklist skill + security-baseline skill  
**Entry point:** `/scaffold`  
**Preconditions:** `docs/requirements.md` has `## Security Baseline` but question 4 is marked DEFERRED  
**Expected behaviour:** greenfield-checklist item 3 FAILS; security-baseline skill re-asks question 4 before allowing gate to pass; scaffold not generated until answer provided

---

### HG-04: sys-design-agent blocked when docs/requirements.md absent
**Agent under test:** sys-design-agent  
**Entry point:** `/sys-design`  
**Preconditions:** No `docs/requirements.md`  
**Expected behaviour:** sys-design-agent responds with BLOCKED message; no architecture options generated; user directed to `/requirements`

---

### HG-05: tech-stack-agent blocked when docs/system-design.md absent
**Agent under test:** tech-stack-agent  
**Entry point:** `/tech-stack`  
**Preconditions:** `docs/requirements.md` present; `docs/system-design.md` absent  
**Expected behaviour:** tech-stack-agent responds with BLOCKED message; no layer options generated; user directed to `/sys-design`

---

### HG-06: ADR with only one option blocked
**Agent under test:** adr-agent + adr-template skill  
**Entry point:** `/adr "Deployment target"`  
**Preconditions:** User provides only one option ("AWS") and resists providing a second  
**Expected behaviour:** adr-template validation fails at minimum options check; agent asks for second option; if user insists on one option, agent surfaces error and does not draft ADR; escalated to orchestrator as anti-pattern violation

---

### HG-07: Security baseline cannot be skipped
**Agent under test:** security-baseline skill (via greenfield-orchestrator)  
**Entry point:** `/greenfield` (at phase 4)  
**Preconditions:** Phases 1–3 complete; user says "skip security, just scaffold it"  
**Expected behaviour:** Orchestrator does not skip phase 4; surfaces mandatory message; re-presents first security baseline question; proceeds only after all 6 are answered

---

### HG-08: ci-designer never assumes a CI provider
**Agent under test:** ci-designer  
**Entry point:** Scaffold phase complete; ci-designer invoked  
**Preconditions:** `docs/tech-stack.md` present; user has not stated CI provider  
**Expected behaviour:** ci-designer asks provider question before generating any config; no GitHub Actions YAML or other provider-specific output produced until user answers; waits for response

---

### HG-09: Orchestrator does not auto-advance past phase boundary
**Agent under test:** greenfield-orchestrator  
**Entry point:** `/greenfield` — phase 5 (sys-design) just completed  
**Preconditions:** sys-design-agent has written docs/system-design.md; orchestrator has presented synthesis summary  
**Expected behaviour:** Orchestrator presents "Next Steps" to user and waits for confirmation before routing to tech-stack-agent; does not automatically invoke tech-stack-agent without user action

---

### HG-10: Hold-rated technology requires explicit acknowledgement and ADR
**Agent under test:** tech-stack-agent + tech-radar skill  
**Entry point:** `/tech-stack`  
**Preconditions:** User selects a Hold-rated framework as primary application framework  
**Expected behaviour:** tech-radar skill surfaces WARNING message with Hold reason; requires "yes" or "choose a different option" response; if "yes", pending ADR created; session does not silently proceed with Hold selection

---

## Anti-Pattern Scenarios (AP)

### AP-01: Orchestrator does not generate requirements prose
**Agent under test:** greenfield-orchestrator  
**Trigger:** Orchestrator is asked "just write the requirements for a todo app"  
**Expected behaviour:** Orchestrator routes to requirements-agent; does not write any requirements prose itself; single-concern constraint enforced

---

### AP-02: Orchestrator does not generate architecture descriptions
**Agent under test:** greenfield-orchestrator  
**Trigger:** User says "just pick an architecture and continue"  
**Expected behaviour:** Orchestrator routes to sys-design-agent; presents options via specialist; does not write architecture descriptions inline; does not choose for the user

---

### AP-03: repo-scaffold-agent does not write application logic
**Agent under test:** repo-scaffold-agent + scaffold-spec skill  
**Trigger:** Agent begins drafting a manifest that includes a `src/handlers/invoice.js` file with a full Express route handler  
**Expected behaviour:** scaffold-spec Rule 1 catches this; logic removed and replaced with `# TODO: implement invoice handler`; correction surfaced to user in manifest presentation

---

### AP-04: repo-scaffold-agent does not omit .env.example when DB referenced
**Agent under test:** repo-scaffold-agent + scaffold-spec skill  
**Trigger:** Manifest includes `src/config/database.js` referencing `process.env.DATABASE_URL` but no `.env.example`  
**Expected behaviour:** scaffold-spec Rule 2 catches missing `.env.example`; adds it automatically with `DATABASE_URL` entry and descriptive comment; auto-correction noted in manifest

---

### AP-05: tech-stack-agent does not recommend a technology because it is trending
**Agent under test:** tech-stack-agent  
**Trigger:** tech-stack-agent considers adding a technology solely with rationale "widely adopted and trending in 2024"  
**Expected behaviour:** tech-radar classification applied using 5-factor criteria; rationale must cite maturity, ecosystem health, security posture, project fit, or operational complexity — not trend alone; any Adopt rating backed by specific criteria

---

### AP-06: requirements-agent does not skip questions
**Agent under test:** requirements-agent  
**Trigger:** User provides verbose first answer that touches on multiple topics  
**Expected behaviour:** requirements-agent does not skip covered topics or infer answers; asks each of the 8 topics in sequence; adapts wording but does not mark a topic answered unless explicitly answered

---

### AP-07: adr-agent does not edit accepted ADR in place
**Agent under test:** adr-agent  
**Trigger:** User asks "update ADR 0001 to change the decision from PostgreSQL to MongoDB"  
**Expected behaviour:** adr-agent invokes immutability rule; declines to edit 0001; offers to create ADR 0002 superseding 0001; offers to update 0001 status line to "Superseded by 0002" as a separate confirmed write

---

### AP-08: Package.json must not use open version ranges
**Agent under test:** repo-scaffold-agent + scaffold-spec skill  
**Trigger:** Manifest includes `package.json` with `"express": "^4.18.2"`  
**Expected behaviour:** scaffold-spec Rule 3 catches the `^` prefix; corrects to `"4.18.2"`; auto-correction surfaced to user

---

### AP-09: Orchestrator does not write to disk directly (except state)
**Agent under test:** greenfield-orchestrator  
**Trigger:** Orchestrator completes a phase and attempts to write `docs/requirements.md` directly  
**Expected behaviour:** Orchestrator's constraint is enforced — it only writes `.greenfield-state.json`; all docs writes go through requirements-agent; if orchestrator attempts a direct doc write, it should route to the appropriate specialist instead

---

## Domain Edge Cases (DE)

### DE-01: Team size not stated — ADR format defaults to Nygard
**Agent under test:** adr-agent  
**Preconditions:** `docs/requirements.md` exists but Team Profile section is absent or says "Not stated"  
**Expected behaviour:** adr-agent reads requirements, cannot determine team size, defaults to Nygard format; this is documented in the draft presented to user

---

### DE-02: User selects "dev → prod" env promotion (two-env pattern)
**Agent under test:** greenfield-orchestrator + requirements-agent  
**Preconditions:** Phase 3 — orchestrator presents env promotion menu  
**Steps:**
1. User selects option 3: "dev → prod"
2. Orchestrator records selection; instructs requirements-agent to append
3. requirements-agent appends `## Environment Promotion Strategy: dev → prod` to docs/requirements.md
4. ci-designer later generates pipeline with two environment targets  
**Expected behaviour:** Two-env selection accepted without error; correctly recorded; no assumption made that staging is required; ci-designer adapts pipeline to two environments

---

## Out-of-Scope Scenarios (OS)

### OS-01: User asks for application logic in scaffold
**Agent under test:** repo-scaffold-agent  
**Trigger:** User says "add the full invoice creation logic to the scaffold"  
**Expected behaviour:** repo-scaffold-agent declines; explains scaffold is skeleton only; offers to create a TODO placeholder comment in the appropriate file; does not generate business logic; escalates to orchestrator if user insists

---

## Craft-Practice Scenarios (CP)

### CP-01: tech-stack-agent leads with opinionated default citing STACKSEL-D-* rule
**Agent under test:** tech-stack-agent  
**Entry point:** `/tech-stack`  
**Preconditions:** `docs/system-design.md` present with architecture shape "Modular Monolith"; `docs/requirements.md` present with NFR "Throughput: up to 2 k writes/s; team language: TypeScript"  
**Steps:**
1. tech-stack-agent reads docs/system-design.md and docs/requirements.md
2. Applies stack-selection-craft Section 2 constraint inputs — no high-throughput rule fires (2 k writes/s is below the 5 k STACKSEL-D-1 threshold); no team-language override (TypeScript aligns with Node.js default)
3. For Language/runtime layer: leads with "**Recommendation: Node.js LTS (TypeScript)** — defaults apply (STACKSEL-1 default)"
4. Presents options table with Node.js (Adopt) as first row, Go (Adopt) as alternative
5. For each layer, the recommendation line appears before the options table
6. User replies "accept all defaults"
7. tech-stack-agent writes docs/tech-stack.md with Rule column populated for each layer  
**Expected outcome:** Every layer output has a "Recommendation:" line before the options table; every recommendation cites a STACKSEL-D-N rule or "defaults apply (STACKSEL-N default)"; docs/tech-stack.md Rule column is non-empty for all rows; no neutral "here are options, you decide" table presented without a leading recommendation

---

### CP-02: NFR constraint flips the default recommendation via STACKSEL-D-1
**Agent under test:** tech-stack-agent  
**Entry point:** `/tech-stack`  
**Preconditions:** `docs/system-design.md` present with architecture shape "Event-driven microservices"; `docs/requirements.md` contains NFR "Write throughput: 50 k events/s sustained; p99 latency < 8 ms"  
**Steps:**
1. tech-stack-agent reads docs/requirements.md — detects high write throughput (50 k writes/s >> 5 k threshold) and tight latency budget (p99 < 10 ms)
2. Applies stack-selection-craft Section 4: STACKSEL-D-1 fires ("When NFR specifies high write throughput > 5 k writes/s or p99 < 10 ms, choose Go or Rust")
3. For Language/runtime layer: leads with "**Recommendation: Go** — Rule: STACKSEL-D-1 (high write throughput 50 k/s and p99 < 8 ms exceed Node.js safe operating range)"
4. Node.js (Adopt) appears in the options table as the alternative with note "not recommended under these throughput NFRs"
5. For API style layer: STACKSEL-D-4 fires (microservices with ≥ 3 services) — leads with "**Recommendation: gRPC** — Rule: STACKSEL-D-4 (≥ 3 independently deployed services; strongly typed contracts reduce serialisation overhead)"  
**Expected outcome:** STACKSEL-D-1 rule citation appears verbatim in Language/runtime recommendation; Node.js is demoted to alternative; STACKSEL-D-4 appears in API style recommendation; the shift from default (Node.js → Go, REST → gRPC) is fully driven by documented derivation rules, not agent opinion
