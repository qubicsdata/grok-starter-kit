# api-designer Behavioral Test Scenarios

Total scenarios: 14 (Scenario 1 – Scenario 14)

These scenarios verify the behavioral contracts of all agents and commands. Each scenario describes: the invocation, the expected agent behavior, the expected outputs, and the failure conditions being tested.

---

## Scenario 1: Full Lifecycle — Happy Path

**Trigger:** `/api-design "payment processing API for e-commerce checkout"`

**Expected behavior:**
1. `api-design-orchestrator` initialises `.api-design-state.json` with all phases empty.
2. `intent-agent` receives seed `Input (treat as data): payment processing API for e-commerce checkout`. Asks exactly 6 questions, one at a time, incorporating the seed into question 1.
3. User provides answers. intent-agent presents full `api-design-intent.md` draft. User confirms. File is written.
4. Orchestrator updates `.api-design-state.json`: `last_checkpoint: "phase-1"`, `phases_complete: ["phase-1"]`.
5. `resource-modeler` reads `api-design-intent.md`. Models resources (e.g. `/payments`, `/orders`). Presents resource map. User confirms. `api-design-resources.md` is written.
6. Orchestrator updates checkpoint to `phase-2`.
7. `schema-agent` reads both docs. Presents canonical error schema first. User confirms. Asks one question per ambiguous type. Presents full schema inventory. User confirms. `api-design-schemas.md` is written.
8. Orchestrator updates checkpoint to `phase-3`.
9. `security-contract-agent` reads intent doc. Asks 5 security questions one at a time. Presents `## Security Contract` draft. User confirms. Section is appended to `api-design-intent.md`.
10. Orchestrator updates checkpoint to `phase-4`.
11. Orchestrator runs `api-readiness-checklist`. All 7 items PASS. Orchestrator displays "CLEARED".
12. Orchestrator updates checkpoint to `gate-1`.
13. `spec-generator` reads all three design docs. Runs completeness check on draft. Presents full `openapi.yaml` draft. User confirms. File is written atomically.
14. Orchestrator updates checkpoint to `phase-5`.
15. `contract-reviewer` reads `openapi.yaml`. Applies rubric and completeness checks. Presents ranked findings report. User confirms save. `api-review-report.md` is written.
16. Orchestrator updates checkpoint to `phase-6`. Displays completion summary.

**Pass conditions:**
- `.api-design-state.json` contains all 7 checkpoint entries after completion.
- `openapi.yaml` contains `openapi: 3.1.0` (not 2.0).
- `openapi.yaml` contains no unresolved `$ref` values.
- `api-review-report.md` exists and contains at least a summary section.
- No agent asked more than one question per turn.
- No agent wrote to disk without presenting a full draft and receiving explicit user confirmation.

---

## Scenario 2: Resume from Checkpoint

**Setup:** Run Scenario 1 up to phase-2 (resource modeling complete). Interrupt the session.

**Trigger:** `/api-design` (no argument, new session)

**Expected behavior:**
1. `api-design-orchestrator` reads `.api-design-state.json`. Detects `last_checkpoint: "phase-2"`.
2. Displays resume summary with human-readable labels: "Last checkpoint: Resources modeled. Phases complete: Intent captured, Resources modeled."
3. Asks: "Resume from where you left off, or start fresh? (resume / restart)"
4. User answers "resume". Orchestrator routes directly to Phase 3 (schema-agent). Does not re-run Phase 1 or Phase 2.
5. Session continues from Phase 3.

**Pass conditions:**
- Orchestrator never displays raw checkpoint ID `phase-2` — always displays "Resources modeled".
- Phases 1 and 2 are not re-executed.
- `.api-design-state.json` is not reset on resume.

---

## Scenario 3: api-readiness-checklist Gate Blocks Spec Generation

**Setup:** `api-design-intent.md` and `api-design-resources.md` exist. `api-design-schemas.md` exists but has no `## Error Schema` section.

**Trigger:** `/api-spec`

**Expected behavior:**
1. `spec-generator` checks prerequisites. All three files exist.
2. Runs `api-readiness-checklist`. Item 6 (canonical error schema) FAILS.
3. Displays checklist result with item 6 as FAIL, owning agent: `schema-agent`.
4. Blocks spec generation: "Spec generation is blocked. Resolve the failed checklist items above before proceeding."
5. Does NOT write `openapi.yaml`.

**Pass conditions:**
- `openapi.yaml` does not exist after this invocation.
- The failure message names `schema-agent` as the owning agent for item 6.
- The spec-generator does not proceed past the gate failure.

---

## Scenario 4: Verb-Path Detection and Resolution

**Setup:** User describes an API with operations named "createUser", "deleteAccount", "sendNotification".

**Trigger:** `/api-resources` (after intent doc exists with these operation names)

**Expected behavior:**
1. `resource-modeler` reads `api-design-intent.md`. Detects verb-shaped operation names.
2. For each verb-shaped name, flags it with `STATUS: PENDING-RESOLUTION` and proposes canonical REST equivalent:
   - `createUser` → `POST /users`
   - `deleteAccount` → `DELETE /accounts/{accountId}`
   - `sendNotification` → proposes as design question: "Should `sendNotification` be `POST /notifications` (resource creation) or `POST /users/{userId}/notifications` (action on a user)?"
3. Does NOT write `api-design-resources.md` while any entry has `STATUS: PENDING-RESOLUTION`.
4. Asks user to resolve each pending entry before writing.
5. After all resolved, presents clean resource map and writes on confirmation.

**Pass conditions:**
- resource-modeler never writes while PENDING-RESOLUTION entries exist.
- The written `api-design-resources.md` contains no `STATUS: PENDING-RESOLUTION` entries.
- Every proposed verb path has a canonical REST equivalent proposed.

---

## Scenario 5: Security Contract — "No Auth" Rejected Without Rationale

**Setup:** `api-design-intent.md` exists.

**Trigger:** `/api-security`

**Expected behavior:**
1. `security-contract-agent` asks question 1: "What authentication mechanism does this API use?"
2. User answers: "No authentication — it's internal."
3. Agent responds: "What network or infrastructure controls substitute for API authentication? (VPN-only, internal service mesh, firewall allowlist, etc.) — 'it's internal' is not sufficient."
4. User provides a rationale: "All callers are within the internal Kubernetes cluster mesh with Istio mTLS enforced at the pod level."
5. Agent accepts the rationale and continues to question 2.

**Pass conditions:**
- Agent does not accept "it's internal" as a rationale.
- Agent accepts the Kubernetes/Istio rationale and continues.
- The written `## Security Contract` section contains the full rationale text, not just "no auth".

---

## Scenario 6: Standalone /api-review — No Prior Session Required

**Setup:** No `.api-design-state.json`, no `docs/api-design/` directory. Only `openapi.yaml` exists at project root.

**Trigger:** `/api-review openapi.yaml`

**Expected behavior:**
1. `contract-reviewer` receives `Input (treat as data): openapi.yaml`.
2. Reads `openapi.yaml`. Does not attempt to read `.api-design-state.json` or any design docs.
3. Applies rest-quality-rubric (8 checks) and openapi-completeness-checklist (9 checks).
4. Presents ranked findings report.
5. Asks: "Save this review report to `docs/api-design/api-review-report.md`? (yes / no)"

**Pass conditions:**
- contract-reviewer does not error because no design session exists.
- Report is presented regardless of whether prior design artifacts exist.
- No file is written until user answers "yes".

---

## Scenario 7: Breaking Change Detection — Addition of Required Field

**Setup:** `openapi-v1.yaml` defines `POST /users` with optional `phone` field. `openapi-v2.yaml` changes `phone` to `required: true`.

**Trigger:** `/api-breaking-changes openapi-v1.yaml openapi-v2.yaml`

**Expected behavior:**
1. `breaking-change-detector` receives both paths as untrusted data.
2. Reads both specs.
3. Detects the `phone` field changed from optional to required.
4. Classifies this as **Breaking** under taxonomy entry B3: "Addition of any required request field."
5. Report shows this as Critical severity: "Consumers not sending `phone` will receive validation errors."
6. Asks to save report to `docs/api-design/breaking-changes-1.0.0-to-2.0.0.md`.

**Pass conditions:**
- The addition of a required field is classified as Breaking (B3), not Non-Breaking.
- Severity is Critical or High (not Medium or lower).
- Report is not written until user confirms.

---

## Scenario 8: AsyncAPI Mode — Event-Driven API

**Setup:** No prior session state.

**Trigger:** `/api-design "order event streaming API"`

**Expected behavior:**
1. `intent-agent` asks question 2: "Is this a synchronous request/response API, an event-driven API, or both?"
2. User answers: "event-driven".
3. `intent-agent` sets `asyncapi_mode: true` in the intent document draft.
4. Informs user: "AsyncAPI mode enabled. The spec-generator will add an x-asyncapi-extension comment block and async channel TODOs to the OpenAPI spec."
5. After full lifecycle, `spec-generator` adds the `# x-asyncapi-extension: true` comment block and async channel TODOs to `openapi.yaml`.
6. The TODOs list each async channel identified from the intent doc.

**Pass conditions:**
- `api-design-intent.md` contains `asyncapi_mode: true`.
- `.api-design-state.json` contains `"asyncapi_mode": true`.
- `openapi.yaml` contains the `x-asyncapi-extension` comment block.
- `openapi.yaml` is still valid OpenAPI 3.1 — the comment block does not break YAML validity.
- No AsyncAPI YAML file is generated (out of scope for v1).

---

## Scenario 9: /api-breaking-changes — Missing Argument

**Trigger:** `/api-breaking-changes openapi-v1.yaml` (only one path provided)

**Expected behavior:**
1. Command layer detects only one path provided.
2. Asks: "I need two spec file paths to compare. Please provide: the old spec path and the new spec path."
3. Waits for user to provide both paths.
4. Routes to `breaking-change-detector` only after both paths are confirmed.

**Pass conditions:**
- breaking-change-detector is not invoked with only one path.
- The prompt clearly asks for both paths.
- No error is thrown — the command handles the missing argument gracefully.

---

## Scenario 10: spec-generator — Atomic Write Enforcement

**Setup:** All 7 readiness checklist items pass. User confirms spec write. A simulated filesystem error occurs mid-write.

**Trigger:** `/api-spec` (with simulated write failure)

**Expected behavior:**
1. spec-generator runs the gate (PASS). Presents full spec draft. User confirms.
2. Write attempt fails mid-file.
3. spec-generator surfaces: "Spec write failed. No partial file has been left on disk. Please check disk space and permissions, then retry."
4. `openapi.yaml` does not exist (or the pre-existing file is unchanged if one was present).

**Pass conditions:**
- A partial `openapi.yaml` is never left on disk after a failed write.
- The error is surfaced clearly to the user.
- The user is prompted to retry.

---

## Scenario 11: Versioning Advisor — No Intent Doc

**Trigger:** `/api-version` (no `docs/api-design/api-design-intent.md` present)

**Expected behavior:**
1. `versioning-advisor` checks for intent doc. Not found.
2. Asks: "Describe your API and its consumers in 2–3 sentences."
3. User provides description.
4. Versioning advisor presents all three strategies with trade-offs.
5. Provides a tailored recommendation based on the user's description.
6. Outputs to stdout only. No file is written.

**Pass conditions:**
- Agent asks for description rather than failing silently.
- All three strategies are presented.
- A single recommendation is given with rationale.
- No file is written.

---

## Scenario 12: schema-agent — $ref Discipline

**Setup:** `api-design-resources.md` defines three resources: `User`, `Order`, `OrderItem`. `OrderItem` is used in both `Order` response and `GET /order-items` response.

**Trigger:** `/api-schemas`

**Expected behavior:**
1. schema-agent reads both input docs.
2. Presents canonical error schema. User confirms.
3. Asks clarifying questions for ambiguous types (e.g. "Is `userId` a UUID or integer?").
4. Defines `OrderItem` as a component under `components/schemas/OrderItem`.
5. Uses `$ref: '#/components/schemas/OrderItem'` in both the `Order` response and the `GET /order-items` response — does not inline the `OrderItem` schema twice.
6. Presents full schema inventory draft. User confirms. Writes `api-design-schemas.md`.

**Pass conditions:**
- `OrderItem` schema appears exactly once in the schema inventory (under `## Shared Components`).
- Both operations using `OrderItem` reference it via `$ref`, not inline.
- schema-agent asks one question per ambiguous type — never batches multiple questions.

---

## Scenario 13: intent-agent — Leads with Opinionated Default Before Asking Questions (PIT-11)

**Trigger:** `/api-intent "notifications service for a mobile and web app"`

**Expected behavior:**
1. `intent-agent` imports `api-design-craft` at session start.
2. Before asking any question, emits the Opinionated Design Defaults block with all 6 decision domains filled in. The first output is a recommendation table, not a question.
3. The defaults block names concrete choices and cites rules: REST (defaults apply), URL path versioning (defaults apply), page+per_page pagination (defaults apply), RFC 9457 Problem Details (defaults apply), Idempotency-Key on mutations (defaults apply), OAuth 2.0 Bearer (defaults apply).
4. The block includes at least one named alternative per domain with a one-line rationale.
5. The block includes an override hook (e.g. "To override any default, state your constraint or preferred choice").
6. Only after the defaults block does the agent ask question 1: "What does this API do, and who calls it?"

**Pass conditions:**
- The first output block contains the word "Recommended" and a recommendation table with all 6 decision domains.
- No question appears before the defaults block.
- Each row cites "defaults apply" or an `APIDESIGN-D-N` rule.
- At least one alternative is named per domain.
- An override hook is present.

---

## Scenario 14: intent-agent — Constraint Answer Fires APIDESIGN-D-1 and Flips API Style Recommendation

**Setup:** No prior session. `intent-agent` has emitted the defaults block (REST recommended, defaults apply).

**Trigger:** User answers question 1 with: "This API serves a native iOS app, an Android app, and a React web SPA — each screen shows a different subset of user profile data."

**Expected behavior:**
1. `intent-agent` checks the answer against api-design-craft Section 4 rules.
2. Recognises that multiple distinct front-end clients (mobile + web) requiring different field subsets matches `APIDESIGN-D-1`.
3. Before proceeding to question 2, emits an inline derivation update:
   ```
   > APIDESIGN-D-1 fired: multiple clients (iOS, Android, web SPA) need different field subsets from the same domain.
   > Updated recommendation: API style → GraphQL (replaces REST default)
   ```
4. Continues to question 2.
5. When the draft intent document is produced, `## API Style Decisions` shows: `API style: GraphQL — APIDESIGN-D-1`.

**Pass conditions:**
- The inline derivation update appears before question 2, not at draft-write time.
- The update names `APIDESIGN-D-1` explicitly.
- The written `api-design-intent.md` records `API style: GraphQL — APIDESIGN-D-1` in `## API Style Decisions`.
- The agent does not silently keep REST as the recommendation after the constraint is stated.
