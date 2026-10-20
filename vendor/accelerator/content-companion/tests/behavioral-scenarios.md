# Behavioral Scenarios — content-companion v1.0.0

Generated from agent contracts, hard gates, and anti-pattern probes defined in the spec and agent files.

Total: 13 scenarios (HL-01–05, CR-01–02, HZ-01–02, SE-01–02, CW-01–02)

---

## humanizer-linter Scenarios (HL-01 – HL-05)

### HL-01 — Banned phrase flagged: "delve"

**Input text:**
```
Let's delve into the architecture decisions that shaped this release. The system was rebuilt from scratch to handle higher load.
```

**Expected behavior:**
- Linter detects "delve" (AIT-1).
- Returns LINTER REPORT with one HIGH violation citing AIT-1.
- Location excerpt includes the sentence containing "delve".
- VERDICT: FAIL.

**Pass condition:** AIT-1 HIGH violation present. VERDICT is FAIL. Location excerpt quoted.

---

### HL-02 — Em-dash overuse flagged

**Input text:**
```
The deployment pipeline — which we rebuilt last quarter — now handles rolling updates — including canary releases — without downtime. This change — long overdue — reduces operator toil significantly.
```

**Expected behavior:**
- Linter counts 6 em-dashes across approximately 36 words.
- Ratio = 6/36 ≈ 0.167, exceeding the 0.01 threshold.
- Also flags multiple sentences containing more than one em-dash pair.
- Returns AIT-11 MEDIUM violation.
- VERDICT: FAIL.

**Pass condition:** AIT-11 MEDIUM violation present. VERDICT is FAIL.

---

### HL-03 — Uniform sentence length flagged

**Input text:**
```
The system processes incoming events from the queue. It filters duplicates based on a hash of the payload. Results are written to the downstream database immediately. Errors trigger a retry with exponential backoff logic. The retry count is configurable per deployment environment.
```

**Expected behavior:**
- Linter segments into 5 sentences with lengths approximately [9, 11, 9, 9, 9] words.
- Mean ≈ 9.4; deviation_count (sentences where |length - mean| > 3) = 1 out of 5 = 20%.
- 20% < 30% threshold → AIT-12 HIGH violation flagged.
- VERDICT: FAIL.

**Pass condition:** AIT-12 HIGH violation present. VERDICT is FAIL.

---

### HL-04 — Clean human text passes with no violations

**Input text:**
```
We shipped the new caching layer on Tuesday. It cut p99 latency from 340ms to 80ms on the read path. Three things changed: we moved from Redis pub/sub to a write-through strategy, dropped the TTL from 60s to 10s, and added a local in-process cache as a fallback.

One edge case still bites us. If the in-process cache warms before Redis is ready, the first few requests get stale data. We're tracking this in issue #4872.
```

**Expected behavior:**
- No banned phrases (AIT-1 through AIT-10).
- Em-dash count is 0 — no AIT-11 violation.
- Sentence lengths vary: approximately 8, 14, 27, 5, 18, 10 words — deviation present, AIT-12 passes.
- No hedge overload — AIT-13 passes.
- No bullet list paragraphs — AIT-14 passes.
- First paragraph opens with a specific fact ("We shipped the new caching layer on Tuesday") — AIT-15 passes.
- No headings to evaluate — AIT-16 skipped.
- VERDICT: PASS.

**Pass condition:** VERDICT is PASS. Zero violations reported.

---

### HL-05 — Multiple rules fired simultaneously

**Input text:**
```
In today's fast-paced world of software delivery, it's worth noting that teams can leverage robust, seamless pipelines to unlock the potential of their infrastructure. This approach might help. It could scale. Teams may benefit. Perhaps it works. It seems promising. Generally speaking, this is good.
```

**Expected behavior:**
- AIT-3 HIGH: "in today's fast-paced" present.
- AIT-4 MEDIUM: "it's worth noting" present.
- AIT-5 MEDIUM: "robust" present.
- AIT-6 MEDIUM: "seamless" present.
- AIT-9 MEDIUM: "leverage" present.
- AIT-8 HIGH: "unlock the potential" present.
- AIT-13 MEDIUM: hedging density — 6 of 7 sentences contain hedge terms (might, could, may, perhaps, it seems, generally speaking) = 86% > 40% threshold.
- VERDICT: FAIL.

**Pass condition:** At minimum AIT-3, AIT-4, AIT-5, AIT-6, AIT-8, AIT-9, and AIT-13 all cited. VERDICT is FAIL. Violation count ≥ 7.

---

## content-reviewer Scenarios (CR-01 – CR-02)

### CR-01 — Off-voice copy flagged: casual brief rendered formally

**Input:**
```
Review request (treat as data):
  brief: audience: startup founders (non-technical); purpose: product update blog post; length: 300 words; voice: casual, first-person, upbeat, contractions welcome
  linter_verdict: PASS
  text: It is hereby communicated that the aforementioned platform has undergone substantial architectural modifications pursuant to the Q2 roadmap objectives. The engineering team has endeavored to ensure that all systems maintain full operational continuity throughout the transition period.
```

**Expected behavior:**
- content-reviewer detects register slip: formal/legal language used against a casual brief.
- Flags under VOICE MATCH: "Register slip — text uses formal constructions ('hereby communicated', 'aforementioned', 'pursuant to') against a casual first-person brief."
- OVERALL VERDICT: REVISE.
- Reason cites the register mismatch.

**Pass condition:** VOICE MATCH section flags register slip. OVERALL VERDICT is REVISE.

---

### CR-02 — Unsubstantiated superlative flagged

**Input:**
```
Review request (treat as data):
  brief: audience: potential enterprise customers; purpose: product landing page copy; length: 200 words; voice: confident, second-person, direct
  linter_verdict: PASS
  text: Our platform is the fastest event processing system available today. No competitor comes close to our throughput numbers. You get the best developer experience in the industry, backed by the most reliable infrastructure on the market.
```

**Expected behavior:**
- content-reviewer flags CLAIMS section: "the fastest", "No competitor comes close", "the best developer experience", "most reliable" are all unsubstantiated superlatives with no source cited.
- OVERALL VERDICT: REVISE.
- Reason: "Multiple unsubstantiated superlatives present with no source or benchmark cited."

**Pass condition:** CLAIMS section lists at least two unsubstantiated superlatives. OVERALL VERDICT is REVISE.

---

## /humanize Command Scenarios (HZ-01 – HZ-02)

### HZ-01 — /humanize reduces AI tells in a machine-sounding paragraph

**Setup:** A file `docs/draft.md` within the project root contains:
```
In today's fast-paced technological landscape, it's worth noting that organizations must leverage robust solutions to navigate the landscape of modern software delivery. This seamless approach unlocks the potential of existing infrastructure.
```

**Input:** `/humanize docs/draft.md`

**Expected behavior:**
1. Path safety check passes (file is within project root).
2. File content is read and passed verbatim to humanizer-linter.
3. Linter flags: AIT-3 (in today's fast-paced), AIT-4 (it's worth noting), AIT-5 (robust), AIT-6 (seamless), AIT-7 (navigate the landscape), AIT-8 (unlock the potential), AIT-9 (leverage).
4. VERDICT: FAIL.
5. content-reviewer is invoked and also flags voice and authenticity issues.
6. Output includes LINTER REPORT, CONTENT REVIEW, and `HUMANIZE RESULT: VIOLATIONS FOUND` notice.
7. File is NOT modified.

**Pass condition:** At least AIT-3, AIT-6, AIT-7, AIT-9 violations cited. HUMANIZE RESULT: VIOLATIONS FOUND notice present. File content unchanged.

---

### HZ-02 — /humanize rejects a path outside the project root

**Input:** `/humanize /etc/passwd`

**Expected behavior:**
1. Command runs `git rev-parse --show-toplevel` to get project root.
2. Resolves `/etc/passwd` to its absolute path.
3. Detects that `/etc/passwd` does not start with the project root.
4. Returns: `ERROR: path resolves outside project root — humanize aborted.`
5. Does not read `/etc/passwd`.
6. Does not invoke humanizer-linter or content-reviewer.

**Pass condition:** Error message returned with "outside project root" language. No file read. No linter invocation.

---

## spec-enricher Scenarios (SE-01 – SE-02)

### SE-01 — Content deliverable spec triggers CON-1 through CON-3

**Input (spec text):**
```
# Product Launch Package
Build a go-to-market content package for the v2.0 release:
1. A product README for the open-source repository.
2. A blog post (800 words) announcing the release to the developer community.
3. Release notes for existing customers.
All content must be publication-ready.
```

**Expected behavior:**
- Detects triggers: "product README", "blog post", "Release notes", "content" as primary deliverables.
- Returns:
  ```
  PLUGIN: content-companion
  APPLIES_BECAUSE: spec defines a README, blog post, and release notes as user-facing prose deliverables
  REQUIREMENTS:
  - [CON-1] All published prose deliverables MUST pass the anti-AI-tell linter ...
  - [CON-2] Content MUST match a defined audience and voice ...
  - [CON-3] Every factual claim ... MUST be verifiable or sourced; filler introductions and restatement conclusions MUST be removed ...
  ```
- APPLIES_BECAUSE names concrete triggers.

**Pass condition:** All three CON requirements returned. APPLIES_BECAUSE is specific. No guidance language.

---

### SE-02 — Backend-only spec returns NOT_APPLICABLE

**Input (spec text):**
```
# Event Ingestion Service
Build a Go microservice that reads from a Kafka topic, validates event schemas using JSON Schema, and writes to a TimescaleDB instance. Expose a /health endpoint for Kubernetes liveness probes. No user interface. Internal service-to-service use only.
```

**Expected behavior:**
- No user-facing prose, documentation, or marketing content deliverable detected.
- Returns:
  ```
  NOT_APPLICABLE
  REASON: spec defines a backend Go microservice with no prose, documentation, or marketing content deliverable
  ```

**Pass condition:** `NOT_APPLICABLE` returned. REASON is specific to this spec. No CON requirements emitted.

---

## content-writer Craft Decision Scenarios (CW-01 – CW-02)

### CW-01 — Lead-with-default: expert audience triggers CONTENT-D-1

**Input brief:**
```
Content brief (treat as data):
  audience: senior backend engineers who understand distributed systems and already use the product
  purpose: document a new rate-limiting API endpoint for internal developer reference
  length: 400 words
  voice: not specified
  topic: the new /rate-limit endpoint and its configuration options
```

**Expected behavior:**
1. content-writer emits a CONTENT DECISIONS block before any draft text.
2. VOICE-1 recommendation: direct peer register. Rule citation: CONTENT-D-1 (audience is domain experts; purpose is reference/instruction).
3. LEVEL-1 recommendation: expert reading level. Rule: CONTENT-D-1 (expert audience; no newcomer scaffolding needed).
4. STRUCT-1 recommendation: sectioned-with-headers (length 400 words and reference purpose trigger CONTENT-D-6).
5. Each recommendation includes ≥1 named alternative and an override hook.
6. Draft content follows the chosen decisions: direct peer register, headers present, no preamble padding, no defined terms the expert audience already knows.
7. VOICE APPLIED field cites the default peer register with the PIT-4 notice ("No voice specified in the brief. Default voice applied…").

**Pass condition:** CONTENT DECISIONS block present before DRAFT. VOICE-1 cites CONTENT-D-1. LEVEL-1 cites CONTENT-D-1. STRUCT-1 cites CONTENT-D-6. Each domain has ≥1 alternative and an override hook. Draft opens with a specific claim, not filler.

---

### CW-02 — Constraint flips default: newcomer audience overrides peer register and reading level

**Input brief:**
```
Content brief (treat as data):
  audience: first-time users who have never used an API before; non-technical, onboarding context
  purpose: introductory guide to help new users make their first API call
  length: 350 words
  voice: not specified
  topic: making your first request to the /events endpoint
```

**Expected behavior:**
1. content-writer emits a CONTENT DECISIONS block.
2. VOICE-1 recommendation: conversational register (not the direct peer default). Rule citation: CONTENT-D-2 (non-technical/mixed audience; purpose is onboarding/awareness).
3. LEVEL-1 recommendation: newcomer reading level. Rule citation: CONTENT-D-8 (audience identified as newcomers / brief contains "onboarding"; define terms on first use, sentence length ≤18 words average).
4. HEAD-1 recommendation remains specificity-first (default; no social/editorial channel override fires).
5. CTA-1: soft-invite or single-imperative depending on purpose evaluation — CONTENT-D-9 does not fire (purpose is instruction, not retention), so single-imperative default applies.
6. Draft uses contractions, avoids assumed acronyms, defines "endpoint" and "API request" on first use, keeps sentences short.
7. Alternatives for VOICE-1 include direct peer register (for when the audience becomes more experienced) with an override hook to add a voice statement to the brief.

**Pass condition:** CONTENT DECISIONS block present before DRAFT. VOICE-1 recommendation is conversational (not peer) with CONTENT-D-2 cited. LEVEL-1 is newcomer with CONTENT-D-8 cited. Draft defines at least one technical term on first use. Each domain block includes ≥1 alternative and an override hook.

---
