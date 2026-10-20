---
name: risk-tier-spec
description: |
  Canonical contract for risk-proportional review. Maps a cheap up-front risk score (fired enrichers + surfaces + security-sensitivity) to a review tier (light / standard / full) and prescribes per tier: review depth, model tiers, and fix policy. Read by the builder's review machinery and by any consumer review loop that wants to spend review tokens in proportion to risk. The static output-hygiene gate runs at EVERY tier.
contract_version: 1.0.0
---

# Risk-Tier Spec

A benchmark showed the accelerator's enforcement machinery ran at **fixed maximum
intensity regardless of risk** — full critic (Opus) + full panel on every build —
so ~50–60% of its tokens were the review/fix loop, and on the smallest build the
review found nothing at all. This contract makes review depth **proportional to
risk**: cheap builds get a light pass, risky builds get the full panel. Quality is
held by moving the mechanical defect class into a free static gate that runs at
every tier (see [[check-output-hygiene]] / `tools/check-output-hygiene.py`).

## The risk score (no extra LLM call)

Compute from signals already available — the enrichment result and a cheap spec scan:

| Symbol | Meaning | Source |
|--------|---------|--------|
| `F` | number of enrichers that FIRED | `.ai-baseline/enrich-result.json` `fired[]`, else 0 |
| `S` | number of distinct runtime surfaces (CLI, HTTP API, frontend/UI, datastore, queue/worker) | scan the spec |
| `Csec` | security-sensitive build | a security/auth/compliance enricher fired (primary); else keyword scan: `auth, login, password, token, payment, PII, innerHTML, eval, exec, subprocess, secret` |

```
risk = F + (2 * S) + (3 if Csec else 0)
```

Surfaces are weighted ×2 because integration across surfaces is where dropped
requirements hide (the benchmark's multi-surface build was where vanilla failed
hardest). Security adds ×3 and force-floors the tier. Use `F` (fired count), not the
total requirement count, so one chatty enricher cannot inflate the score.

## Tiers

| `risk` | Tier | Review depth | Models | Fix policy |
|-------:|------|--------------|--------|------------|
| 0–2 | **light** | static gate + PIT checks + critic Q1–4. **No panel.** | generate → haiku; critic → **sonnet** | controller applies all trivial fixes inline; **no fix subagent** |
| 3–6 | **standard** | light + critic Q5 + **security-reviewer** | generate/critic/security → sonnet | trivial inline; non-trivial → **ONE batched** fix dispatch |
| ≥7 | **full** | standard + **full panel** (security / ux / topology + test-agent) | critic → **opus**; panel per model-tier-guide | trivial inline; non-trivial → ONE batched fix dispatch |

## Force-floors (override the table)

- **`Csec == true` ⇒ tier ≥ standard.** A security-sensitive build always gets at
  least the LLM security-reviewer, even if the arithmetic says light.
- **Critic floor is sonnet.** Light tier runs the critic at sonnet, never haiku.
  Tiering may raise the critic to opus (full) but never drop it below sonnet.
- **The static output-hygiene gate runs at ALL tiers, unconditionally.** It is the
  safety net that makes a light LLM pass safe: mechanical defects (XSS, hardcoded
  config, missing error schema, zero tests) stay covered at zero token cost.

## Fix policy (all tiers)

- **Trivial / mechanical** findings (formatting, a `[$ARGUMENTS]` bracket, a missing
  import line, a one-line escape) — the controller applies them directly. Do NOT
  spawn a cold fix subagent for a one-line change; a fresh subagent re-pays full
  context cost to make a trivial edit.
- **Non-trivial** findings — batch ALL of them into **ONE** fix dispatch. Never one
  fixer per finding (each rebuilds context and re-runs suites).

## Tier without an enrichment run (consumer-side, SDD-only)

The superpowers review loop is external and cannot be modified; this tiering is a
**portable recommendation** an enriched spec carries (see the `## Review Plan` block
written by the enrich runner) — it is advisory, not enforced.

1. If `.ai-baseline/enrich-result.json` exists in the working directory → read its
   `tier`.
2. Otherwise compute a degraded score from the spec alone (`F = 0`):
   `risk = 2 * S + (3 if Csec_keyword else 0)`. A single-surface non-security spec
   ⇒ 2 ⇒ light; an auth-bearing frontend+API spec ⇒ `4 + 3 = 7` ⇒ full. The
   high-signal cheap inputs (surface count + security keywords) carry the decision,
   so it degrades gracefully with no enrichment dependency.

## Empirical notes (measured 2026-06-21)

These findings are why the tiers and fix policy are shaped the way they are. Evidence:
`benchmarks/2026-06-21-escalating/` (the S2-consumer and builder-panel re-benchmarks)
and the review-cost notes of the same day; neither is vendored in this kit.

- **More reviewers is often more noise, not more signal.** On a known-good plugin the two
  panel reviewers dropped at standard tier (ux, topology) produced 2 false-positive FAILs
  — both blind to a cross-plugin dependency that lives in ai-baseline; one misread a model
  ID the critic read correctly. The deep critic + the security reviewer carried the real
  findings. This is why standard keeps critic+security and drops the lower-signal members.
- **The unit of waste is the dispatch, not the token.** A trivial fix dispatched as a cold
  subagent cost ~21.7k tokens of context re-derivation; applied inline by the controller it
  cost ~0. This is the entire basis of the fix policy below — never pay a cold start for a
  one-line change.
- **The cheapest fix is upstream.** A requirement made explicit in the spec is built in and
  needs no downstream review/fix at all. Tiering reduces the cost of the backstop; tight
  enrichment reduces how often the backstop fires.

## Hard gates

- NEVER drop the critic below sonnet.
- NEVER skip the static output-hygiene gate to "save time" — it is the cheapest
  check and the one that makes the rest safe.
- NEVER auto-route a security-sensitive build (`Csec`) to light.
- NEVER spawn one fix subagent per finding; batch or apply inline.

See [[model-tier-guide]] for the model-per-role detail this contract references.
