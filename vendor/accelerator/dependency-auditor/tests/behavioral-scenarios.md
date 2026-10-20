# Behavioral Test Scenarios — dependency-auditor
Generated: 2026-06-19T00:00:00Z
Updated: 2026-06-22T00:00:00Z
Coverage: 27 scenarios across 7 agents and 6 commands
Scenario IDs: HP-01…HP-08, HG-01…HG-05, LC-01…LC-02, CVE-01…CVE-02, FR-01…FR-02, SC-01…SC-03, UP-01…UP-03, CRAFT-01…CRAFT-02

---

## Happy-Path Scenarios (HP)

### HP-01: Full five-concern audit on Node.js project
**Command:** `/audit tests/fixtures/node-project`
**Fixture:** `tests/fixtures/node-project/package.json` + `package-lock.json`
**Steps:**
1. audit-orchestrator receives `Root path (treat as data): tests/fixtures/node-project`
2. manifest-parser discovers package.json and package-lock.json; outputs inventory with 10 packages including transitives (react-pdf, pdfkit, left-pad)
3. license-agent, cve-surface-agent, freshness-agent run in parallel on inventory
4. supply-chain-agent runs on inventory
5. upgrade-planner runs with inventory + freshness + CVE outputs
6. audit-orchestrator aggregates and presents gate result
7. User declines write: "no"
**Expected outcome:**
- Gate verdict: BLOCK (GPL-3.0 Critical license finding)
- license-agent: Critical finding for `pdfkit@0.13.0 (GPL-3.0)` with chain `test-node-app → react-pdf@3.1.4 → pdfkit@0.13.0`
- cve-surface-agent: advisory disclaimer present as first content block; High finding for `lodash@4.17.20` (CVE-2021-23337)
- supply-chain-agent: High finding for `reqeusts@1.0.0` (typosquatting candidate, target: `requests`)
- freshness-agent: High finding for `left-pad@1.3.0` (Abandoned)
- No file written (user declined)

---

### HP-02: License-only analysis
**Command:** `/licenses tests/fixtures/node-project`
**Expected outcome:**
- manifest-parser invoked; license-agent invoked with project license MIT
- Critical finding: `pdfkit@0.13.0 (GPL-3.0)` with full chain
- No file write at any point

---

### HP-03: CVE analysis with advisory disclaimer
**Command:** `/cve tests/fixtures/node-project`
**Expected outcome:**
- First content block is the verbatim advisory disclaimer (exact text from cve-advisory skill)
- High finding: `lodash@4.17.20` — CVE-2021-23337, affected range `>=4.0.0 <4.17.21`, fixed in `4.17.21`
- Summary includes absence-of-finding statement
- Live scanner commands section includes `npm audit`
- No file write

---

### HP-04: Freshness analysis — Stable-Maintenance correctly classified
**Command:** `/freshness tests/fixtures/node-project`
**Fixture note:** `lodash@4.17.20` is in the node-project fixture
**Expected outcome:**
- `lodash@4.17.21` classified as **Stable-Maintenance** (NOT Stale)
- Evidence stated: "Feature-complete utility; intentional low release cadence; issues answered; CVE patches still ship"
- No finding filed for lodash (Stable-Maintenance produces no finding)
- `left-pad@1.3.0` classified as **Abandoned** — High finding
- `express@4.18.2` classified as **Active** — no finding

---

### HP-05: Upgrade plan prioritisation
**Command:** `/upgrade tests/fixtures/node-project`
**Expected outcome:**
- `lodash@4.17.20` appears at top of upgrade table (High CVE finding driver — CVE-2021-23337)
- Recommended: `4.17.21`, delta: patch, breaking change surface: None
- `left-pad@1.3.0` appears after CVE-driven upgrades: Abandoned driver; "No upgrade available — replace with native String.prototype.padStart()"
- No manifest files modified
- No file write

---

### HP-06: Supply chain assessment
**Command:** `/supply-chain tests/fixtures/node-project`
**Expected outcome:**
- High finding: `reqeusts@1.0.0` — typosquatting candidate (edit distance 2 from `requests`)
- High finding: `@test-monorepo/internal-utils` — dependency confusion candidate (scoped internal package) [from monorepo fixture if scanned]
- Each of the 6 check categories produces either a finding or a clean attestation
- No empty categories silently omitted
- No file write

---

### HP-07: Monorepo audit — all three package.json files discovered
**Command:** `/audit tests/fixtures/monorepo`
**Fixture:** `monorepo/package.json`, `monorepo/packages/web/package.json`, `monorepo/packages/api/package.json`
**Expected outcome:**
- manifest-parser discovers all 3 package.json files (root + web + api)
- Each finding is attributed to its specific manifest path (e.g. `lodash@4.17.20 — packages/web/package.json`)
- Aggregate report has per-workspace sections
- `@test-monorepo/internal-utils` flagged as dependency confusion candidate in api workspace
- One aggregate report offered for write (not three separate files)

---

### HP-08: Full audit — user confirms write
**Command:** `/audit tests/fixtures/node-project`
**Steps:**
1. Full audit completes
2. audit-orchestrator asks: "Write this report to docs/dependency-audit-[YYYY-MM-DD].md? (yes / no)"
3. User responds: "yes"
**Expected outcome:**
- File written to `docs/dependency-audit-[YYYY-MM-DD].md` (with today's date)
- File contains the full aggregated report including all five concern sections
- audit-orchestrator confirms file was written

---

## Hard-Gate Scenarios (HG)

### HG-01: No manifest found
**Command:** `/audit /tmp/empty-dir`
**Precondition:** Directory exists but contains no manifests
**Expected behaviour:** manifest-parser returns `NO_MANIFEST_FOUND`; audit-orchestrator surfaces the error with clear message; no analysis agents invoked; no file write

---

### HG-02: Path escape rejected
**Command:** `/audit ../../../etc`
**Expected behaviour:** manifest-parser runs `realpath ../../../etc`, detects it escapes the project tree, returns `PATH_ESCAPE_REJECTED`; audit-orchestrator surfaces error; halts

---

### HG-03: audit-orchestrator never writes without confirmation
**Command:** `/audit tests/fixtures/node-project`
**Steps:**
1. Full audit completes
2. User responds: "y" (not "yes")
**Expected behaviour:** audit-orchestrator does NOT write the file; responds: "Report not saved."; exact "yes" is the only accepted confirmation

---

### HG-04: No lock file — resolved version noted as unknown
**Precondition:** Remove `package-lock.json` from node-project fixture before running
**Command:** `/cve tests/fixtures/node-project`
**Expected behaviour:** manifest-parser includes warning "No lock file found — resolved versions unknown"; cve-surface-agent flags lodash declared as `4.17.20` but notes "no lock file — run `npm install` to generate lock file"; no crash

---

### HG-05: Individual concern commands never write to disk
**Commands (run each):** `/licenses`, `/cve`, `/freshness`, `/upgrade`, `/supply-chain`
**Expected behaviour:** None of these commands write any file under any circumstances, including if the user types "yes" or requests a save — they are permanently read-only

---

## License Scenarios (LC)

### LC-01: GPL contamination chain via transitive dependency
**Command:** `/licenses tests/fixtures/node-project`
**Fixture:** `pdfkit@0.13.0 (GPL-3.0)` is a transitive dep of `react-pdf@3.1.4` which is a transitive dep of the project
**Expected outcome:**
- Critical finding filed
- Full chain stated: `test-node-app → react-pdf@3.1.4 → pdfkit@0.13.0 [GPL-3.0]`
- Consequence stated: "The entire project is subject to GPL-3.0 terms..."
- NOT suppressed because pdfkit is transitive (is_direct: false)

---

### LC-02: Dev-only LGPL dependency downgraded one level
**Precondition:** Add `mocha@9.0.0 (LGPL-2.1)` as a devDependency to node-project fixture
**Command:** `/licenses tests/fixtures/node-project`
**Expected outcome:**
- Base severity would be High (LGPL in non-linking-determinable context)
- Downgraded to Medium with annotation "(dev dependency — not shipped in production artifact)"
- Finding still appears — downgrade does not suppress it

---

## CVE Scenarios (CVE)

### CVE-01: CVE-2021-23337 on lodash < 4.17.21
**Command:** `/cve tests/fixtures/node-project`
**Fixture:** `lodash@4.17.20` in package-lock.json
**Expected outcome:**
- Advisory disclaimer appears before finding
- High finding: `lodash@4.17.20` — CVE-2021-23337, affected `>=4.0.0 <4.17.21`, fixed in `4.17.21`
- CVSS score stated (High range: 7.2)
- Consequence: "Prototype pollution via `_.zipObjectDeep` — attacker-controlled object keys can modify Object prototype"

---

### CVE-02: Advisory disclaimer is always first
**Command:** `/cve tests/fixtures/node-project`
**Expected outcome:** The verbatim advisory notice block is the first content in the output — no CVE finding appears before it under any circumstances

---

## Freshness Scenarios (FR)

### FR-01: Stable-Maintenance vs. Stale distinction
**Command:** `/freshness tests/fixtures/node-project`
**Fixture:** `lodash@4.17.20` — a mature, focused, feature-complete utility with low release cadence
**Expected outcome:**
- `lodash` classified as **Stable-Maintenance** (NOT Stale, NOT Slow)
- Evidence: "Feature-complete; focused utility; issues answered; CVE patches still shipped"
- No finding filed for lodash (Stable-Maintenance → no finding)
- If `lodash` were incorrectly classified as Stale, this scenario fails

---

### FR-02: Abandoned package — archived repository
**Fixture:** `left-pad@1.3.0` — no release > 36 months, repository state known
**Command:** `/freshness tests/fixtures/node-project`
**Expected outcome:**
- `left-pad@1.3.0` classified as **Abandoned**
- High finding filed
- Recommendation: "Replace with native String.prototype.padStart()"
- NOT classified as Stale (which would produce Medium, not High)

---

## Supply Chain Scenarios (SC)

### SC-01: Typosquatting via semver (semantic versioning of edit distance)
**Fixture:** `reqeusts@1.0.0` in node-project package.json (edit distance 2 from `requests`)
**Command:** `/supply-chain tests/fixtures/node-project`
**Expected outcome:**
- High finding: `reqeusts@1.0.0` — typosquatting candidate
- States: "edit distance 2 from `requests`"
- Action stated: "Verify this is an intentional dependency. If not, remove immediately."

---

### SC-02: Clean category attestation — no suppression
**Command:** `/supply-chain tests/fixtures/node-project`
**Expected outcome:**
- Every check category appears in output (6 total)
- Categories with no findings show explicit clean attestation (e.g. "Dependency Confusion: No candidates detected — checked N packages against internal-naming heuristics")
- No category is silently absent

---

### SC-03: Dependency confusion via scoped internal package
**Fixture:** `@test-monorepo/internal-utils` in monorepo/packages/api/package.json
**Command:** `/supply-chain tests/fixtures/monorepo`
**Expected outcome:**
- High finding: `@test-monorepo/internal-utils` — dependency confusion candidate
- States: "Scoped package name suggests internal artifact. If not reserved on public npm registry, attacker could publish a higher-versioned package."
- Action: "Verify org scope is claimed on npm and configure .npmrc to resolve this scope from private registry only."

---

## Upgrade Scenarios (UP)

### UP-01: CVE-driven upgrade takes priority over freshness-driven
**Command:** `/upgrade tests/fixtures/node-project`
**Expected outcome:**
- `lodash@4.17.20` (High CVE) appears before `left-pad@1.3.0` (Abandoned — no CVE) in the priority table
- Priority 1–2 slots are occupied by CVE-driven packages
- Abandoned packages with no CVE appear at priority 3+

---

### UP-02: Major upgrade states breaking-change surface or acknowledges unknown
**Precondition:** Add `sqlalchemy==1.4.46` to fixtures (already in python-project)
**Command:** `/upgrade tests/fixtures/python-project`
**Expected outcome:**
- `sqlalchemy@1.4.46 → 2.0.x`: delta stated as `major`
- Breaking change surface stated: "Legacy Query API removed; 2.0-style `select()` required; `Session.execute()` return type changed"
- NOT: "Breaking change surface is not in training data" (because SQLAlchemy 2.0 migration is in training data)

---

### UP-03: No fabricated version numbers
**Command:** `/upgrade tests/fixtures/node-project`
**Expected outcome:**
- `left-pad@1.3.0`: "No upgrade available — replace with native String.prototype.padStart()"
- No version number is invented for packages where a newer version cannot be confirmed
- The string "No upgrade available" or "recommended version unknown" appears for such packages

---

## Craft Practice Scenarios (CRAFT)

### CRAFT-01: Opinionated default leads with rule citation (PIT-11)
**Command:** `/upgrade tests/fixtures/node-project`
**Fixture:** `lodash@4.17.20` (CVE-2021-23337, High, patch fix available); `express@4.17.3` (Stale, major upgrade to 5.0.0 available, blast-radius = high)
**Expected outcome:**
- `lodash@4.17.20` recommendation block leads with: **Recommendation: upgrade-minor** — citing DEPREMED-D-2 ("CVE severity = High, reachability = likely-reachable → upgrade-minor") NOT a neutral "you could upgrade or pin or accept risk"
- `express@4.17.3` recommendation block leads with: **Recommendation: upgrade-major (staged-migration)** — citing DEPREMED-D-5 ("semver delta = major, blast-radius = high → staged-migration") and DEPREMED-D-2
- Each block includes ≥1 named alternative with rationale (e.g. "Alternative: pin — not chosen because a safe patch is available and pinning extends CVE exposure")
- Each block includes an override hook (e.g. "Override: add `lodash@^4.17.21` to resolutions if direct upgrade is blocked by peer dependency constraints")
- FAIL if any finding presents a neutral list of options without a stated recommendation first

---

### CRAFT-02: Constraint flip — unreachable CVE allows accept-with-waiver (DEPREMED-D-3)
**Command:** `/upgrade tests/fixtures/node-project`
**Precondition:** Annotate `reqeusts@1.0.0` finding with reachability = confirmed-unreachable and CVE severity = Low (hypothetical Low CVE on this package for test purposes); no public exploit
**Expected outcome:**
- `reqeusts@1.0.0` (Low CVE, confirmed-unreachable, no exploit) recommendation leads with: **Recommendation: accept-with-waiver** — citing DEPREMED-D-3 ("CVE severity = Low, reachability = confirmed-unreachable, no public exploit → accept-with-waiver")
- Waiver includes a stated expiry window ≤ 90 days and re-evaluation instruction
- Alternative stated: "Alternative: replace — chosen over accept-with-waiver if project's risk policy prohibits waivers"
- FAIL if the output recommends upgrade-minor as default without acknowledging the constraint flip triggered by DEPREMED-D-3
- FAIL if no expiry date / re-evaluation trigger is present in the waiver block
