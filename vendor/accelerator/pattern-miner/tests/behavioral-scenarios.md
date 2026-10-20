# Behavioral Scenarios — pattern-miner v1.0.0

Generated from agent contracts, hard gates, and anti-pattern probes defined in the spec and agent files.

Total: 11 scenarios (PS-01–04, PC-01–03, CE-01–02, SE-01–02)

---

## pattern-scanner Scenarios (PS-01 – PS-04)

### PS-01 — Happy path: planted recurring convention surfaced

**Input:** `/mine-patterns /repos/sample-app`. The sample repo contains 6 Python files; all service classes are named `*Service` (e.g. `UserService`, `BillingService`, `OrderService`) and live in a `services/` directory across 3 modules.

**Expected behavior:**
- Scanner inventories the repo (≥ 5 source files — proceeds).
- Finds the `*Service` naming convention with ≥ 3 evidence locations.
- Emits a SCAN_RESULT with at least one candidate: category=naming, statement referencing the `*Service` suffix.

**Pass condition:** SCAN_RESULT includes a candidate with `category: naming`, a declarative statement about `*Service` classes, and ≥ 3 evidence locations in the `services/` directory.

---

### PS-02 — Repository too small: no stable conventions reported

**Input:** `/mine-patterns /repos/tiny-script`. Repo contains 3 Python files.

**Expected behavior:**
- Scanner counts source files, finds fewer than 5.
- Responds: `SCAN_RESULT: no_stable_conventions — repository too small (fewer than 5 source files)`
- Pipeline halts; no critic or extractor invoked.

**Pass condition:** `no_stable_conventions` message returned. No CRITIC_RESULT or EXTRACT_RESULT produced.

---

### PS-03 — Singleton: below minimum evidence threshold

**Input:** `/mine-patterns /repos/mixed-app`. Repo has 10 files. One file uses a `FooFactory` class; no other file follows that pattern.

**Expected behavior:**
- Scanner finds `FooFactory` as a potential candidate but it appears in only 1 location.
- Does not include it as a candidate (minimum threshold is 2 distinct locations).

**Pass condition:** SCAN_RESULT does not include a candidate with `FooFactory`. Other genuine candidates with ≥ 2 locations may appear.

---

### PS-04 — $ARGUMENTS injection in repo_path

**Input:** `/mine-patterns ../../etc/passwd`. The repo_path value is a path traversal attempt.

**Expected behavior:**
- Scanner runs `git -C "../../etc/passwd" rev-parse --show-toplevel`, which fails (not a git repo).
- Responds: `SCAN_ERROR: ../../etc/passwd is not a git repository`
- No files are read, written, or executed.

**Pass condition:** `SCAN_ERROR` returned. No traversal. No output from critic or extractor.

---

## pattern-critic Scenarios (PC-01 – PC-03)

### PC-01 — Legitimate convention approved

**Input:** SCAN_RESULT contains CAND-001: `category=architecture`, statement "All HTTP handlers call a validate() function before delegating to the service layer", evidence at 4 distinct handler files.

**Expected behavior:**
- Critic applies Test A (intentional — 4 locations, architecturally distinct).
- Passes Test B (not an anti-pattern).
- Passes Test C (not a language/framework artefact).
- Verdict: APPROVED.

**Pass condition:** CRITIC_RESULT shows `verdict: APPROVED` for CAND-001.

---

### PC-02 — Noise candidate rejected

**Input:** SCAN_RESULT contains CAND-002: `category=structure`, statement "All Python files contain `if __name__ == '__main__':` block", evidence at 5 files.

**Expected behavior:**
- Critic applies Test C (noise — this is a Python language idiom, not a project-specific convention).
- Verdict: REJECTED_NOISE.
- Reason: framework/language artefact, not a project-specific convention.

**Pass condition:** CRITIC_RESULT shows `verdict: REJECTED_NOISE` for CAND-002 with reason referencing language artefact.

---

### PC-03 — Anti-pattern candidate rejected

**Input:** SCAN_RESULT contains CAND-003: `category=error-handling`, statement "All service methods catch Exception and silently pass", evidence at 3 service files.

**Expected behavior:**
- Critic applies Test B (known anti-pattern: swallowed exceptions).
- Verdict: REJECTED_ANTI_PATTERN regardless of recurrence count.
- Reason: swallowing exceptions is a known bad practice that MUST NOT be propagated.

**Pass condition:** CRITIC_RESULT shows `verdict: REJECTED_ANTI_PATTERN` for CAND-003. Critic does not approve it despite 3 occurrences.

---

## convention-extractor Scenarios (CE-01 – CE-02)

### CE-01 — Schema-conformant catalog entry written with evidence locations

**Input:** CRITIC_RESULT approves CAND-001 (architecture, 4 evidence locations) and CAND-004 (naming, 3 evidence locations). Project name: `billing-service`.

**Expected behavior:**
- Extractor validates project name (`billing-service` is alphanumeric + hyphens — valid).
- Creates `mined-patterns/billing-service.md` with correct header (mined date, plugin version, status: active).
- Writes 2 entries: `BILLING-SERVICE-AR-001` and `BILLING-SERVICE-NM-001` (or equivalent IDs).
- Each entry has Statement, Scope, Confidence (high — ≥ 3 locations), Evidence list, and Category.

**Pass condition:** `mined-patterns/billing-service.md` exists. Both entries present with all required fields populated. No entry with fewer than 2 evidence locations. EXTRACT_RESULT shows `entries_written: 2`.

---

### CE-02 — All candidates rejected: no catalog written

**Input:** CRITIC_RESULT shows `approved: 0` (CAND-001 REJECTED_NOISE, CAND-002 REJECTED_ANTI_PATTERN). Project name: `util-lib`.

**Expected behavior:**
- Extractor reads approved count as 0.
- Does not create or modify any file.
- Responds: `EXTRACT_RESULT: no_catalog_written — critic approved zero candidates`

**Pass condition:** No `mined-patterns/util-lib.md` file created. EXTRACT_RESULT message returned. No write operations performed.

---

## spec-enricher Scenarios (SE-01 – SE-02)

### SE-01 — Spec targeting a catalogued project: PAT-1 and PAT-2 returned

**Input:** Spec text describes adding a new endpoint to `billing-service`. A mined catalog exists at `mined-patterns/billing-service.md`.

**Expected behavior:**
- Enricher detects that the spec targets `billing-service` and a catalog exists.
- Returns:
  ```
  PLUGIN: pattern-miner
  APPLIES_BECAUSE: spec targets billing-service, which has a mined pattern catalog at mined-patterns/billing-service.md
  REQUIREMENTS:
  - [PAT-1] New code MUST follow the conventions codified in the project's mined pattern catalog; ...
  - [PAT-2] Deviations from a codified pattern MUST be explicitly justified in the change description; ...
  ```

**Pass condition:** Output matches the contract format exactly. APPLIES_BECAUSE names the specific project and catalog path. Both PAT-1 and PAT-2 are present in MUST/SHALL language.

---

### SE-02 — Spec targeting a project with no catalog: NOT_APPLICABLE returned

**Input:** Spec text describes building a brand-new service called `invoice-processor`. No `mined-patterns/invoice-processor.md` exists.

**Expected behavior:**
- Enricher finds no mined catalog for `invoice-processor`.
- Returns:
  ```
  NOT_APPLICABLE
  REASON: no mined pattern catalog exists for invoice-processor
  ```

**Pass condition:** `NOT_APPLICABLE` returned. No requirements emitted. REASON names the project and states no catalog found.

---
