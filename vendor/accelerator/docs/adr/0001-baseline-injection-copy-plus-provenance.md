# ADR-0001: Baseline injection — verbatim copy plus in-file provenance

**Status:** Accepted (2026-07-02)
**Format:** Nygard (single maintainer)
**Related:** the builder self-exemption design spec (WS5 implements this decision; design
notes not vendored in this kit)

## Context

agent-builder injects two ai-baseline files **verbatim** into every plugin it generates —
`skills/baseline-enforcer.md` and `agents/audit-trail-agent.md` — while *also* declaring
`requires: ai-baseline` in the generated README (`generate-agent.md`, baseline-injection steps
1–4). The 2026-07-02 builder audit (finding 5) questioned this: it is belt-and-suspenders that
becomes N stale forks the moment ai-baseline updates.

What already exists:

- **In-repo drift is gated.** `tools/check-baseline-drift.py` (validate.sh step 1) fails CI when
  any plugin copy inside this repo diverges byte-for-byte from the ai-baseline source. The fleet
  implicitly chose copy-plus-gate for in-repo plugins already.
- **Precedent.** Shipped hooks follow the same pattern deliberately: canonical sources in
  `tools/hooks/`, byte-identical copies in `ai-baseline/hooks/scripts/`, drift gated by
  `check-hooks-drift.py`, resync via `sync-shipped-hooks.py`.

What does not exist: any staleness signal for copies that **leave this repo** — plugins built in
consumer repos, or marketplace-installed plugins carrying the copies. Those forks drift silently
forever, and nothing in the file even records which ai-baseline version it came from.

The real question is therefore not "copy or not" (in-repo copying is settled and gated) but:
(a) is the copy+requires redundancy justified, and (b) how do out-of-repo copies become
staleness-detectable?

## Decision

**Keep the verbatim copies, keep `requires: ai-baseline`, and stamp every injected copy with an
in-file provenance line.**

1. Generate-agent injects each baseline copy with line 1:
   `<!-- baseline-provenance: ai-baseline v<version> <ISO-date> -->`
   (version from `ai-baseline/.claude-plugin/plugin.json`). The backfill checklist gains the same
   line.
2. `check-baseline-drift.py` becomes provenance-aware: it strips a leading provenance comment from
   the copy before the byte comparison. Source files stay headerless. An unstamped copy still
   passes (pre-ADR compatibility); a stamped copy with drifted content still fails.
3. Existing in-repo copies are stamped once with the current ai-baseline version.

The redundancy is justified and intentional: the **copy** guarantees a built plugin operates
standalone (audit trail and enforcer present even when ai-baseline is not installed); the
**requires:** declaration documents the richer runtime contract (cost-gate-agent, pii-scrub-agent,
enrich runner) that only the real dependency provides. They answer different failure modes, not the
same one.

## Alternatives considered

- **Reference-only** (drop the copies, rely solely on `requires:`): zero drift by construction and
  the cleanest model — rejected because a generated plugin installed without ai-baseline would
  silently lose its audit trail and enforcer, which is exactly the failure the injection exists to
  prevent. Marketplace outputs cannot assume the dependency resolves.
- **Copy + consumer resync command** (a `/baseline-sync` shipped with generated plugins that pulls
  current baseline files): the strongest freshness guarantee — deferred, not rejected. It adds new
  machinery and a write-into-consumer-repo surface that belongs to the sovereign-workbench
  portable-substrate program. Provenance stamping is its prerequisite either way: a resync tool
  needs to know what version a copy came from.
- **Provenance elsewhere** (a plugin.json field, or a sidecar file): rejected — a plugin.json field
  breaks the PIT-6 canonical-field whitelist, and a sidecar is a new artifact class for
  `check-stray-artifacts` to police. An in-file comment travels with the file, which is the point.

## Consequences

- **(+)** Out-of-repo staleness becomes detectable by inspection ("this copy is baseline v1.2.0,
  source is at v1.4.0") and machine-checkable by future tooling.
- **(+)** In-repo guarantees unchanged: byte-identity (modulo the stamp) still gated in CI.
- **(+)** Standalone operation of generated plugins preserved.
- **(−)** Out-of-repo copies still do not self-heal; they are stale until someone looks. Accepted
  for now; the resync command is the designated follow-up when the portable substrate lands.
- **(−)** `check-baseline-drift.py` gains a small parsing step (strip line 1 if provenance) — a
  unit test covers it.
- Builder generation gains one mechanical step; critic/PIT review is unaffected (the comment is not a
  structural field and appears in no gated schema).
