---
name: backlog-schema
description: Canonical schemas for the product passport, personas, epics, features, and stories — ID grammar, status lifecycles, WSJF-lite ordering, DoR/DoD gate predicates, and write-safety protocol. Import when reading or writing any docs/product/ artifact.
---

# Backlog Schema

All product truth is committed markdown/JSON under `docs/product/` in the target project. File-based and sovereign: no external services, no tracker sync. Nothing is ever deleted — `dropped` is a status; IDs are never reused or renumbered; `stage_history` is append-only.

## Layout & ID scheme

```
docs/product/
├── passport.json                 # machine-readable durable state — passport-agent only
├── personas/P-001-<slug>.md
├── epics/E-001-<slug>.md
├── features/F-001-<slug>.md      # OPTIONAL layer — created only when earned (PLAN-D-2)
└── stories/S-001-<slug>.md
```

- ID grammar: `^[EFSP]-\d{3}$` (`E-` epic, `F-` feature, `S-` story, `P-` persona). Zero-padded, monotonic per type, allocated from `passport.counters` via passport-agent (**never** `find | wc -l` — counters survive drops). Filename = `<ID>-<kebab-slug>.md`.
- IDs are never reused or renumbered. Deleting a file is forbidden; use `status: dropped`.
- The grammar doubles as (a) the path-traversal guard on every ID argument and (b) the `/context` feature-label vocabulary.
- There is **no generated backlog.md file**. The frontmatter *is* the board; `/backlog` renders terminal-only views. Nothing can go stale.

## Persona — `docs/product/personas/P-001-<slug>.md`

```yaml
---
schema_version: "1.0.0"
id: P-001
type: persona
name: "Maya the Maintainer"
role: data-analyst              # kebab-case role token used in story sentences
status: active                  # active | retired
created: 2026-07-02
---
```

Body sections, all REQUIRED (omission = schema violation caught by the author agent's pre-write checklist and check-passport.py):
`## Goals` (≥2 bullets) · `## Pains` (≥2 bullets) · `## Context` (proficiency, environment, constraints) · `## Success looks like` (observable outcomes). One screen max.

Personas are the unit of "who": every `ready` story must bind to an `active` persona (DOR-1). Free-text roles are never accepted.

## Epic — `docs/product/epics/E-001-<slug>.md`

```yaml
---
schema_version: "1.0.0"
id: E-001
type: epic
title: "Self-serve checkout"
status: proposed                # proposed | committed | in-progress | done | dropped
outcome: "Checkout completion rate ≥ 80% without support contact"   # REQUIRED, measurable (PLAN-D-9)
personas: [P-001]
wsjf: { business_value: 8, time_criticality: 3, risk_reduction: 2 } # value inputs; inherited defaults for children
release_target: null            # "v1.0" ties epic to a release; drives hardening evidence
created: 2026-07-02
updated: 2026-07-02
---
```

Body: `## Outcome hypothesis` (why it exists, how we'll know it worked) · `## Scope boundary` (explicit non-goals) · `## Children` (list of F-*/S-* links, maintained by backlog-agent at groom — a maintained section, not a separate file).

Epic status is **derived where possible**: `in-progress` when any child story is in-progress/in-review, OR when ≥1 non-dropped child is done but not yet all (shipped work keeps the parent in-progress — it never sits at `proposed` with delivered children); `done` only when all non-dropped children are done (checked mechanically at groom; never declared).

## Feature — `docs/product/features/F-001-<slug>.md` (optional layer)

```yaml
---
schema_version: "1.0.0"
id: F-001
type: feature
epic: E-001                     # REQUIRED parent, must resolve to a non-dropped epic
title: "Guest checkout"
status: proposed                # proposed | in-progress | done | dropped
personas: [P-001]
wsjf: { business_value: 5, time_criticality: 3, risk_reduction: 1 }
created: 2026-07-02
updated: 2026-07-02
---
```

Body: `## Description` · `## Acceptance summary` (3–5 bullets) · `## Children` (maintained S-* list) · `## Delivery record` (appended at feature completion: `/cost-report feature=<label>` summary line — spend-per-feature becomes a committed product fact).

**The feature layer is optional.** Stories may parent directly to epics. Opinionated default (PLAN-D-2): introduce features only when an epic exceeds 5 direct stories. There is no `E-000 unsorted` epic and no mandatory feature link — a day-0 solo project runs epic→story. Features are **real files** (never sections inside epic files) so cross-links stay deterministically checkable and cost labels stay addressable.

## Story — `docs/product/stories/S-001-<slug>.md` (the workhorse)

```yaml
---
schema_version: "1.0.0"
id: S-001
type: story
parent: F-002                   # REQUIRED — resolves to a feature OR directly to an epic (E-NNN)
title: "Guest enters shipping address"
status: ready                   # draft | ready | in-progress | in-review | blocked | done | dropped
persona: P-001                  # REQUIRED — must resolve to an active persona
wsjf:
  business_value: 5             # ∈ {1,2,3,5,8}
  time_criticality: 3           # ∈ {1,2,3,5,8}
  risk_reduction: 1             # ∈ {1,2,3,5,8}
  job_size: 3                   # ∈ {1,2,3,5,8}; 8 = must split before ready (DOR-4)
priority: 3.0                   # DERIVED cache: (bv+tc+rr)/job_size, written at last groom — never truth
pin: null                       # integer n pins into top-n of the ready lane; rendered "PINNED (manual override)"
blocked_by: []                  # [S-004, ...] — DOR-6 requires all done
spec: null                      # docs/specs/NNNN-<slug>.md — set by /build-next
context_feature: null           # the /context feature label used during builds (cost linkage)
builds: []                      # appended by /build-next: [{session_id, correlation_id, started, ended, outcome}]
created: 2026-07-02
updated: 2026-07-02
closed: null
shipped: null                   # one "what shipped" line, set at close
---
# S-001 — Guest enters shipping address

## Story
As **Maya the Maintainer** (P-001), I want <capability>, so that <benefit>.

## Acceptance criteria
- [ ] AC-1: Given <context>, when <action>, then <observable outcome>.
- [ ] AC-2: Given <edge/error context>, when <action>, then <handled outcome>.

## Out of scope
- <explicit non-goals for this story>

## Notes
<!-- optional: decisions, links, discovered-scope → new-story pointers -->

## Blocked
<!-- present only when status: blocked — exactly one line: what unblocks it -->

## Build record
<!-- appended by /build-next at close: spec path, commit range (<sha>..<sha>, hex SHAs), review tier + verdict, date -->
```

**AC tick format (canonical, greppable):** a met criterion becomes
`- [x] AC-1: Given …, then …. — evidence: test_reset_link_expiry` — the ` — evidence: ` suffix names a test, `file:line`, command output, or `verified manually by user`. A ticked AC without an evidence suffix is a DOD-2 violation.

**Status lifecycle** (one-way except explicit demotion):
`draft → ready` (DoR pass only) `→ in-progress` (/build-next claims) `→ in-review` (arc review phase) `→ done` (DoD pass only). `blocked` reachable from ready/in-progress (with a one-line `## Blocked` reason); `unblock` returns it to `ready` (re-gated). `dropped` reachable from any state. A `ready` story whose DoR rots (e.g. persona retired) is demoted to `draft` at the next groom, naming the failed DOR-n.

## Estimation & priority scheme (WSJF-lite, one scheme)

`priority = (business_value + time_criticality + risk_reduction) / job_size`, all inputs ∈ {1, 2, 3, 5, 8}. `job_size` is relative Fibonacci, **never hours**, and is acted on three ways: WSJF denominator; split trigger (`8` blocks ready — PLAN-D-4/DOR-4); review-depth risk hint (`job_size ≥ 5` → nudge the arc's review tier up one — PLAN-D-12).

**Deterministic total order for the ready lane:** higher `priority` → older `created` → smaller `job_size` → lexical ID. `pin: n` forces a story into the top n positions, rendered `PINNED (manual override)`. This exact ordering rule is shared verbatim by backlog-agent (board) and /build-next (picker) so they can never disagree.

**Named alternative (PLAN-D-6):** stack-rank (`pin` on everything) is acceptable only for backlogs <8 items; the passport records `backlog_scheme`. No P1–P3 bands, no S/M/L sizes exist anywhere.

## Definition of Ready / Definition of Done

Machine-checkable; the SAME predicates live in backlog-agent's procedure and in tools/check-passport.py — they may never disagree.

**DoR — `draft → ready` requires ALL of:**

| Rule | Predicate (exact) | INVEST |
|---|---|---|
| DOR-1 | `persona:` resolves to an existing `personas/P-\d{3}-*.md` with `status: active` | V |
| DOR-2 | ≥2 lines matching `^- \[ \] AC-\d+:` each containing `Given` and `when` and `then` (case-insensitive) | T |
| DOR-3 | `wsjf` block complete; all four fields ∈ {1,2,3,5,8} | E |
| DOR-4 | `job_size ≤ 5` | S |
| DOR-5 | `parent:` resolves to an existing epic/feature file whose `status` ≠ `dropped` | I |
| DOR-6 | `blocked_by` empty OR every referenced story has `status: done`; own status ≠ `blocked` | I |
| DOR-7 | `## Story` section contains "As ", "I want", "so that" and the persona's ID | V/N |

(N is additionally covered by `## Out of scope` present and non-empty.)

**DoD — `→ done` requires ALL of:**

| Rule | Predicate (exact) |
|---|---|
| DOD-1 | `spec:` points to an existing `docs/specs/*.md` file |
| DOD-2 | every AC line is `- [x]` AND carries an ` — evidence: ` suffix; every tick was user-confirmed (never auto-ticked) |
| DOD-3 | `## Build record` contains a review verdict line (`review: <tier> — <verdict>`) and a commit range in SHA form (`<sha>..<sha>`, each 7–40 hex chars — never symbolic refs like `v1.0..HEAD`) |
| DOD-4 | *(advisory, never blocking)* audit log contains entries for the build's correlation_id |

**Output contract for every gate run** (backlog-agent, verbatim shape):
`READY` / `DONE` on pass, otherwise `BLOCKED: [DOR-2: only 1 acceptance criterion found; need ≥2] [DOR-4: job_size=8; split required]` — always rule ID + observed value, all failures listed.

## The passport — `docs/product/passport.json`

Durable, committed, machine-readable. **State split (fleet state convention):** durable truth (stage, history, counters, denormalized ready_count, last_built) lives in the committed passport; the **in-flight build pointer lives in a root dotfile `.product-session.json`** (like `.release-session.json`) so a mid-build session never dirties a committed file.

### passport.json schema v1.0.0 (verbatim)

```json
{
  "schema_version": "1.0.0",
  "project": "acme-shop",
  "one_liner": "Usage-based billing for small SaaS teams",
  "stage": "building",
  "stage_history": [
    {"stage": "idea", "ts": "2026-07-01T09:00:00Z", "by": "/product-init", "evidence": "empty repo; passport created"},
    {"stage": "building", "ts": "2026-07-02T10:00:00Z", "by": "/build-next", "evidence": "first story S-001 passed DoD"}
  ],
  "backlog_root": "docs/product",
  "backlog_scheme": "wsjf-lite",
  "counters": {"epic": 1, "feature": 3, "story": 12, "persona": 2},
  "ready_count": 4,
  "last_built": {"story": "S-006", "ts": "2026-07-01T18:12:00Z", "outcome": "done"},
  "release_nudge": {"last_tag": "v0.3.0", "suggested": false},
  "created": "2026-07-01",
  "updated": "2026-07-02"
}
```

- `stage` enum: `idea | scaffolded | building | hardening | released | operating`.
- `stage_history` append-only; timestamps monotonic; `evidence` non-empty.
- `counters` are the ID allocators (monotonic; `counters.X ≥` max existing ID of type X — checked).
- `ready_count` is denormalized by backlog-agent on every backlog write so the session gateway can surface it with **one JSON read, zero directory scans**.
- `backlog_scheme`: `wsjf-lite` (default) or `stack-rank` (<8 items).
- `release_nudge` implements the earned `/release` suggestion: when ≥3 stories reached `done` since the git tag recorded in `last_tag`, suggest `/release` ONCE, set `suggested: true`; reset both fields when a new tag appears. Never nags.

Stage transitions advance ONLY on the machine-checkable evidence table in the lifecycle-stages skill (PLAN-D-8) — proposed with evidence, user-confirmed, never silently flipped.

**What reads the passport:** `/build-next` (precondition), `/backlog` (header line), the product-pulse skill, the accelerate arc (read-only), the session gateway, and the stage-keyed earned handoffs in the lifecycle-stages skill.

### `.product-session.json` (root dotfile — runtime state, safe to delete, never committed; `/product-init` offers a `.gitignore` line)

```json
{
  "story": "S-007",
  "phase": "execute",
  "spec_path": "docs/specs/0008-email-verification.md",
  "ac_total": 5,
  "ac_met": 2,
  "started": "2026-07-02T14:02:00Z",
  "correlation_id": "…",
  "context_feature": "F-002-guest-checkout",
  "last_error": null
}
```

Written/updated by the /build-next flow at each phase boundary; deleted at story close or park. Fully rebuildable knowledge? No — it IS the resume pointer; if deleted, `/build-next` falls back to scanning for an `in-progress` story and asks the user to confirm resume.

### Passport recovery

If passport.json is malformed/missing, passport-agent offers **rebuild from frontmatter**: counters = max ID per type from filenames; ready_count = rescan; stage re-proposed from the lifecycle-stages evidence table; history restarts (old history recoverable from git); any on-disk `in-progress` story is confirmed with the user as the active pointer. Never silent-overwrite.

## Write-safety protocol

1. **Single writer for the passport.** Only passport-agent writes `docs/product/passport.json`. All other agents and commands request passport mutations through passport-agent.
2. **Atomic write + jq verify.** Write to a temp file, then rename over the target. After the rename, verify with `jq empty` (parse check) and confirm every required key of the schema above is present. Never leave a temp file behind on failure.
3. **Realpath guard.** Every write realpath-resolves its target and must stay under `docs/product/` (or `docs/specs/` for story-to-spec-agent). A resolved path outside the allowed root is refused before any file operation.
4. **ID grammar guard.** `^[EFSP]-\d{3}$` validates every ID argument before any file operation (kills traversal).
5. **Project-relative paths.** All paths resolve from `git rev-parse --show-toplevel`.
6. **Confirm before write.** No agent writes an artifact without showing the full draft and getting explicit confirmation.

## Hard Gates

**NEVER delete or renumber an artifact.**
**NEVER reuse an ID.**
**NEVER write passport.json from any agent but passport-agent.**
**NEVER mark a story ready/done without the gate.**
**NEVER tick an AC without named evidence.**
**NEVER store secrets or PII in backlog artifacts.**

## Enforcement

Every invariant in this schema is deterministically enforced by `tools/check-passport.py` (fleet dev repo) and mirrored in backlog-agent's gate procedure (installed contexts). The `PLAN-` requirement family (spec-enricher) and `PLAN-D-` rule family (craft) bind builds to these schemas.
