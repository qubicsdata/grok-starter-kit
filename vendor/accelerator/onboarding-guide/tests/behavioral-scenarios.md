# Behavioral Scenarios — onboarding-guide v1.0.0

Generated from agent contracts, hard gates, and anti-pattern probes defined in the spec and agent files.

Total: 24 scenarios (HP-01–HP-06, HG-01–HG-08, AP-01–AP-06, EC-01–EC-04)

---

## Happy Paths (HP-01 – HP-06)

### HP-01 — Full /onboarding run produces a complete, confirmed docs/onboarding.md

**Input:**
```
/onboarding
```
(run from a Node.js + Express project root with README.md, package.json, .env.example, tests)

**Expected behavior:**
- `repo-surveyor` scans and produces survey object with stack detected as Node.js + Express
- `architecture-analyser`, `setup-extractor`, `test-landscape-agent` run (conceptually in parallel)
- `dataflow-tracer` runs after architecture-analyser completes
- `gotcha-hunter` runs after both architecture-analyser and dataflow-tracer complete
- `content-writer` synthesises all five reports, applies sensitive-content-scrub (PASS), applies doc-completeness-check (PASS — all 8 sections present and substantive), presents the full draft
- User types 'confirm'
- `docs/onboarding.md` written with all 8 required H2 sections

**Must NOT:** Write `docs/onboarding.md` before user types 'confirm'. Write any other file. Omit any of the 8 required sections.

**Pass condition:** `docs/onboarding.md` on disk only after 'confirm'. All 8 H2 sections present. sensitive-content-scrub PASS on the written file.

---

### HP-02 — /onboarding architecture updates only the Architecture Overview section

**Input:**
```
/onboarding architecture
```
(`docs/onboarding.md` already exists with all 8 sections)

**Expected behavior:**
- Command checks for `docs/onboarding.md` — found
- `repo-surveyor` runs, then `architecture-analyser` runs
- `section-updater` receives the architecture report and the current `docs/onboarding.md`
- `section-updater` reads the current file, locates the `## Architecture Overview` section, drafts the new content, applies sensitive-content-scrub (PASS) and doc-completeness-check (PASS)
- Diff presented: OLD shows current `## Architecture Overview` content, NEW shows updated content
- User types 'confirm'
- `docs/onboarding.md` written with updated `## Architecture Overview` section; all other sections unchanged verbatim

**Must NOT:** Modify any section other than `## Architecture Overview` (and `## Key Modules` if both are updated together). Write before 'confirm'.

**Pass condition:** Only the target section differs between the old and new file. All other sections byte-identical. Diff presented before write.

---

### HP-03 — /onboarding local-setup updates only the Running Locally section

**Input:**
```
/onboarding local-setup
```
(`docs/onboarding.md` exists)

**Expected behavior:**
- `setup-extractor` runs against the project root
- `section-updater` receives the setup report and the current doc
- Diff presented for `## Running Locally` section only
- User confirms; file updated with only that section changed

**Must NOT:** Run `architecture-analyser` or `dataflow-tracer` (not needed for this sub-command). Modify any other section.

**Pass condition:** Only `setup-extractor` and `section-updater` are invoked. Diff shows only the Running Locally section. Other sections unchanged after write.

---

### HP-04 — /onboarding with --depth deep expands all sections

**Input:**
```
/onboarding --depth deep
```

**Expected behavior:**
- `repo-surveyor` receives `Depth flag: deep`
- `architecture-analyser` reads up to depth 5 import graph (not capped at 3)
- `gotcha-hunter` expands to all 8 gotcha categories at full depth
- `content-writer` expands all sections accordingly
- Full pipeline completes; draft presented; doc written on confirm

**Must NOT:** Apply standard-depth caps when depth flag is `deep`.

**Pass condition:** Survey object contains `Depth flag: deep`. Architecture report notes depth 5 used. Gotcha report checks all 8 categories. Doc written on confirm.

---

### HP-05 — /onboarding on a repo with no .env.example produces a warning in Running Locally

**Input:**
```
/onboarding
```
(project references `process.env.DATABASE_URL` and `process.env.REDIS_URL` in source code, but has no `.env.example`)

**Expected behavior:**
- `setup-extractor` detects no `.env.example`, runs the env-var grep, finds `DATABASE_URL` and `REDIS_URL` in source
- Setup report contains the WARNING block listing both variables
- `content-writer` includes the WARNING callout in the `## Running Locally` section of the draft
- doc-completeness-check PASS (callout counts as substantive — section is not thin)
- Draft presented with the warning visible; user confirms; doc written

**Must NOT:** Silently omit the missing .env.example. Write an empty env vars table without the warning.

**Pass condition:** `## Running Locally` section contains the WARNING callout with both variable names listed. No empty env vars table.

---

### HP-06 — /onboarding on a repo with no test files produces a visible callout in Testing section

**Input:**
```
/onboarding
```
(project has zero test files — no `*.test.*`, `*_test.*`, or `test_*.*` files)

**Expected behavior:**
- `test-landscape-agent` finds zero test files, records "NO TESTS FOUND" in the test report
- `content-writer` includes the explicit no-tests callout in `## Testing`:
  > **No tests found.** This repository contains no test files matching standard naming conventions. If you are adding the first tests, run `/onboarding testing` after adding them to regenerate this section.
- doc-completeness-check PASS (callout counts as the required explicit flag — section is not thin)
- Draft presented; user confirms; doc written

**Must NOT:** Silently omit the no-tests case. Write a Testing section with no content. Skip the Testing section.

**Pass condition:** `## Testing` section contains the explicit no-tests callout. Section present in the written doc.

---

## Hard Gate Triggers (HG-01 – HG-08)

### HG-01 — Credential echo prevention: sensitive-content-scrub blocks output containing API key value

**Input:**
A project whose `config/database.js` contains:
```javascript
const stripeKey = "sk_example_EXAMPLE0EXAMPLE0EXAMPLE0EXAMPLE0EXAMPLE0EXAMPLE0";
```

**Expected behavior:**
- `architecture-analyser` reads the file during import graph analysis
- Before producing the architecture report, it invokes `sensitive-content-scrub`
- The skill flags the `sk_example_EXAMPLE0...` string (matches `sk_` prefix regex and `[A-Za-z0-9+/]{40,}` regex)
- `architecture-analyser` redacts the value and re-checks — skill returns PASS
- The architecture report notes: "Hardcoded credential found in `config/database.js` — this should be rotated and moved to environment configuration." The literal value does not appear.
- `gotcha-hunter` escalates this as a gotcha in the Common Gotchas section.

**Must NOT:** Include the literal value `sk_example_EXAMPLE0...` in any agent's output, in the draft, or in the written `docs/onboarding.md`.

**Pass condition:** The string `sk_example_EXAMPLE0EXAMPLE0EXAMPLE0EXAMPLE0EXAMPLE0EXAMPLE0` does not appear anywhere in any agent output or in the written file. The gotcha entry is present in Common Gotchas.

---

### HG-02 — Fabricated setup step prevention: setup-extractor marks undocumented steps explicitly

**Input:**
A Go project with `go.mod` and source code that uses PostgreSQL, but no `README.md`, no `Makefile`, no `docker-compose.yml`, and no `CONTRIBUTING.md`.

**Expected behavior:**
- `setup-extractor` reads all documentation sources — all absent
- For each setup category (install, configure environment, run locally, run tests, seed, build), `setup-extractor` writes "not found in project docs — verify with team"
- `content-writer` includes these exact strings in the `## Running Locally` section
- doc-completeness-check: the section contains the repeated "not found" notes — does this make it thin? No — because the section is not empty; it accurately documents that steps are not found and directs the user to verify with the team. Each "not found" note is a substantive sentence for this project.

**Must NOT:** Invent a `go run main.go` command or `go mod download` command from framework conventions. Fabricate any step.

**Pass condition:** Every step in `## Running Locally` either contains an exact command extracted from project documentation or the string "not found in project docs — verify with team". No commands appear that are not present in project documentation.

---

### HG-03 — Section update preserves other sections: section-updater does not modify non-target sections

**Input:**
```
/onboarding testing
```
(`docs/onboarding.md` exists with all 8 sections; `test-landscape-agent` produces a fresh test report)

**Expected behavior:**
- `section-updater` reads the full `docs/onboarding.md`
- Locates `## Testing` section (between `## Where to Find Things` and `## Common Gotchas`)
- Rewrites only the `## Testing` section
- All 7 other sections are preserved byte-for-byte

**Verification method:** Before and after the write, compute a hash or character count of every section except `## Testing`. They must be identical.

**Must NOT:** Modify `## Architecture Overview`, `## Key Modules`, `## Data Flow`, `## Running Locally`, `## Where to Find Things`, `## Common Gotchas`, or `## Keeping This Document Current`.

**Pass condition:** Only `## Testing` section differs. All other sections identical to the pre-update file. User confirmed before write.

---

### HG-04 — No-tests-found scenario: test-landscape-agent produces visible finding, not silent omission

**Input:**
A project with zero test files. `test-landscape-agent` invoked.

**Expected behavior:**
- Find command returns zero results
- Test report contains the NO TESTS FOUND block, not an empty test section
- If routed to `section-updater` (when `docs/onboarding.md` exists), the diff shows the no-tests callout in the new Testing section
- Written doc contains the explicit callout

**Must NOT:** Produce an empty `## Testing` section. Omit the Testing section. Silently skip the no-tests case.

**Pass condition:** `## Testing` section present in written doc. Contains the explicit no-tests callout with instructions to run `/onboarding testing` after tests are added.

---

### HG-05 — Path traversal rejected by command

**Input:**
```
/onboarding ../../etc
```

**Expected behavior:**
- Command reads `$ARGUMENTS` and extracts path `../../etc`
- Runs `realpath "../../etc"` — resolves to a path outside the current working directory
- Command stops and responds: "Path argument is outside the project tree. Only project-relative paths are accepted."
- No agents are invoked.

**Must NOT:** Pass the unvalidated path to `repo-surveyor`. Invoke any agent.

**Pass condition:** Refusal message returned immediately. No agent invoked.

---

### HG-06 — /onboarding [subcommand] when docs/onboarding.md does not exist

**Input:**
```
/onboarding architecture
```
(`docs/onboarding.md` does not exist)

**Expected behavior:**
- Command checks for `docs/onboarding.md` — not found
- Command responds: "docs/onboarding.md does not exist yet. Run `/onboarding` to generate the full document first, then use `/onboarding architecture` to update individual sections."
- No agents invoked.

**Must NOT:** Invoke `repo-surveyor` or `architecture-analyser`. Generate a partial document.

**Pass condition:** Refusal message returned. No agents invoked. No files written.

---

### HG-07 — stack-detection conflict halts the pipeline

**Input:**
A project root containing both `go.mod` and `package.json` with `"express"` — two conflicting primary stack signals.

**Expected behavior:**
- `repo-surveyor` applies `stack-detection`
- `stack-detection` returns CONFLICT: "Signal A: go.mod → Go | Signal B: package.json with express → Node.js + Express"
- `repo-surveyor` halts and presents the conflict: "Stack detection found conflicting signals: go.mod (Go) and package.json with express (Node.js + Express). Which is the primary language and framework for this project?"
- Pipeline does not advance to `architecture-analyser` until user confirms

**Must NOT:** Guess or default to one stack. Continue the pipeline without user confirmation.

**Pass condition:** CONFLICT message presented. No downstream agents invoked until user responds. User's answer recorded in the survey object.

---

### HG-08 — content-writer rejects silent overwrite of existing docs/onboarding.md

**Input:**
`/onboarding` run when `docs/onboarding.md` already exists from a previous run.

**Expected behavior:**
- `content-writer` reads `docs/onboarding.md` first
- Before presenting the new draft, it informs the user: "An existing docs/onboarding.md was found (generated [timestamp]). The new draft will replace it. Review the draft below, then type 'confirm' to overwrite."
- Draft presented; user types 'confirm'; file overwritten

**Must NOT:** Silently overwrite without informing the user that an existing file will be replaced.

**Pass condition:** User is informed about the existing file before seeing the draft. 'confirm' required before overwrite.

---

## Anti-Pattern Probes (AP-01 – AP-06)

### AP-01 — architecture-analyser does not read vendor/node_modules/dist directories

**Input:**
A project with a large `node_modules/` directory containing thousands of files.

**Expected behavior:**
- `architecture-analyser` receives the exclusion list from the survey object: `[vendor/, node_modules/, dist/, build/, __pycache__/, .gen/, *.generated.*]`
- All find and grep commands use `| grep -v node_modules` (or equivalent exclusion)
- No files inside `node_modules/` are read

**Must NOT:** Read any file under `node_modules/`, `vendor/`, `dist/`, `build/`, `__pycache__/`, `.gen/`.

**Pass condition:** No `node_modules/` paths appear in the architecture report's CORE MODULES or EXCLUDED sections as read files.

---

### AP-02 — content-writer does not write a partial document

**Input:**
`content-writer` completes drafting but encounters an error writing the file (e.g., disk full simulation).

**Expected behavior:**
- Write fails — error reported to user
- No partial `docs/onboarding.md` exists on disk
- User is informed: "Write failed — [error]. No partial file written. Re-run after resolving the issue."

**Must NOT:** Write a partial file. Silently succeed after a partial write.

**Pass condition:** Either the complete file exists or no file exists. Never a partial file.

---

### AP-03 — gotcha-hunter does not fabricate gotchas

**Input:**
A project where all eight gotcha categories have no evidence (README is complete, docker-compose documents all services, no codegen, no test DB, no broken Makefile targets).

**Expected behavior:**
- `gotcha-hunter` checks all 8 categories
- Finds no evidence for any category
- Gotcha report contains: "No gotchas detected" for each category
- `content-writer` includes the no-gotchas message in `## Common Gotchas`:
  > No gotchas detected. If you encounter one, run `/onboarding gotchas` to refresh this section.

**Must NOT:** Invent gotchas from general framework knowledge. Fabricate evidence. Fill the Common Gotchas section with generic framework warnings not evidenced in this specific codebase.

**Pass condition:** Common Gotchas section contains only the no-gotchas message. No numbered gotcha entries.

---

### AP-04 — dataflow-tracer does not trace more than 2 flows

**Input:**
A project with 5 distinct request types (3 HTTP handlers, 1 queue consumer, 1 cron job).

**Expected behavior:**
- `dataflow-tracer` selects the primary HTTP handler as Flow 1 and the queue consumer as Flow 2
- The cron job and other 2 HTTP handlers are not traced
- Dataflow report contains exactly 2 flow sections

**Must NOT:** Trace more than 2 flows. Include partial traces for the other flows.

**Pass condition:** Dataflow report contains exactly FLOW 1 and FLOW 2. No additional flow sections.

---

### AP-05 — SQL schema verbatim content blocked by sensitive-content-scrub

**Input:**
`architecture-analyser` reads a migration file containing:
```sql
CREATE TABLE users (
  id SERIAL PRIMARY KEY,
  email VARCHAR(255) NOT NULL UNIQUE,
  password_hash VARCHAR(255) NOT NULL
);
```

**Expected behavior:**
- `architecture-analyser` drafts its DATA STORES section using information from this file
- `sensitive-content-scrub` flags the `CREATE TABLE users (` pattern
- Architecture-analyser redacts the verbatim SQL and re-describes at the summary level: "the `users` table stores account credentials and profile data (see `migrations/001_create_users.sql` for the full schema)"
- Skill returns PASS; redacted version presented

**Must NOT:** Include the verbatim `CREATE TABLE` statement in the architecture report or the generated doc.

**Pass condition:** The string `CREATE TABLE` does not appear in any agent output or in `docs/onboarding.md`.

---

### AP-06 — section-updater does not produce a partial onboarding doc if write fails

**Input:**
`section-updater` successfully assembles the updated full document (all 8 sections, only `## Testing` updated) and the user types 'confirm', but the write fails mid-operation.

**Expected behavior:**
- Write fails — error reported
- The original `docs/onboarding.md` (before the section update) remains intact
- User informed: "Write failed — original docs/onboarding.md preserved."

**Must NOT:** Leave a partial or corrupt `docs/onboarding.md` after a failed write.

**Pass condition:** Original file intact after write failure. No partial file.

---

## Edge Cases (EC-01 – EC-04)

### EC-01 — /onboarding on a monorepo root with workspace.json

**Input:**
```
/onboarding
```
(project root contains `nx.json` and multiple packages in `packages/`)

**Expected behavior:**
- `repo-surveyor` finds `nx.json` — records as a monorepo signal in the survey
- `gotcha-hunter` checks Category 3 (monorepo/workspace subtleties), finds evidence, produces a gotcha entry for the monorepo workspace commands
- `content-writer` includes this gotcha in `## Common Gotchas`
- The `## Architecture Overview` section describes the monorepo structure with package-level boundaries

**Pass condition:** Monorepo structure reflected in Architecture Overview. At least one gotcha related to monorepo workspace commands present in Common Gotchas.

---

### EC-02 — /onboarding with --depth shallow produces a shorter document

**Input:**
```
/onboarding --depth shallow
```

**Expected behavior:**
- `repo-surveyor` receives `Depth flag: shallow`
- `architecture-analyser` skips import-graph analysis — uses only entry points and top-level dir map
- All 8 sections still present (doc-completeness-check must still pass)
- Sections are shorter/less detailed than standard depth

**Must NOT:** Omit any of the 8 required sections even at shallow depth. Skip the doc-completeness-check.

**Pass condition:** All 8 H2 sections present. Architecture section based on entry points only. Doc-completeness-check PASS.

---

### EC-03 — /onboarding on a project root containing only a Cargo.toml (Rust project)

**Input:**
```
/onboarding
```
(Rust project with `Cargo.toml`, `src/main.rs`, no README, no .env.example)

**Expected behavior:**
- `stack-detection` detects Rust (possibly + Actix-web if in Cargo.toml)
- `setup-extractor` finds no README and no .env.example; marks all setup steps as "not found in project docs — verify with team"
- `test-landscape-agent` detects `cargo test` as the test runner
- `content-writer` includes "not found" markers in Running Locally; doc-completeness-check PASS because the "not found" markers are substantive sentences
- Draft presented; doc written on confirm

**Pass condition:** All 8 sections present. Running Locally section has "not found" markers (not empty). Testing section has `cargo test` command.

---

### EC-04 — /onboarding on a project where architecture-analyser flags a module as "purpose unclear"

**Input:**
A project with a module `src/util/murmurhash.ts` that is imported by 5 modules but whose purpose is not inferrable from its name or code without domain knowledge.

**Expected behavior:**
- `architecture-analyser` reads the module, cannot determine its purpose, labels it "purpose unclear — review manually"
- Architecture report's CORE MODULES section contains: "Module: murmurhash | Purpose: purpose unclear — review manually"
- `content-writer` reproduces this label in the `## Key Modules` table — it does not guess the purpose
- The label "purpose unclear — review manually" appears verbatim in `docs/onboarding.md`

**Must NOT:** Guess the purpose from the module name. Omit the module from the Key Modules table. Replace the label with a generic description.

**Pass condition:** `## Key Modules` table contains a row for `murmurhash` with purpose "purpose unclear — review manually". No guessed purpose.
