---
name: dependency-remediation-craft
description: |
  Remediation decision expertise for the upgrade-planner agent. Encodes opinionated defaults for choosing among upgrade-minor, upgrade-major, pin, patch, replace, and accept-with-waiver actions for each dependency finding, plus prioritisation, breaking-change handling, transitive vs. direct strategy, and update cadence. Consumed by upgrade-planner when producing remediation recommendations.
---

# Dependency Remediation Craft

## Section 1 — Decision Domains

- DEPREMED-1 Remediation action (upgrade-minor / upgrade-major / pin / patch / replace / accept-with-waiver)
- DEPREMED-2 Prioritisation order (severity × reachability × exploitability rank)
- DEPREMED-3 Breaking-change handling strategy (staged-migration / shim-layer / immediate-cut / defer)
- DEPREMED-4 Transitive-vs-direct strategy (lift-to-direct / pin-transitive / replace-parent / accept)
- DEPREMED-5 Update cadence (continuous-patch / monthly-minor / quarterly-major / on-finding-only)

## Section 2 — Constraint Inputs

- CVE severity (Critical/High/Medium/Low) → DEPREMED-1 (higher severity forces more aggressive action), DEPREMED-2 (Critical and High move to top of queue)
- Reachability (reachable code path confirmed / likely reachable / unknown / unreachable) → DEPREMED-1 (unreachable CVEs may qualify for accept-with-waiver), DEPREMED-2 (confirmed reachability escalates priority)
- Exploitability (known exploit in the wild / PoC public / theoretical) → DEPREMED-1 (known exploit eliminates accept-with-waiver option), DEPREMED-2 (known exploit in wild = immediate escalation)
- Semver delta of available fix (patch / minor / major) → DEPREMED-1 (patch = upgrade-minor default; major triggers breaking-change handling), DEPREMED-3
- Freshness classification (Active / Stable-Maintenance / Slow / Stale / Abandoned) → DEPREMED-1 (Abandoned eliminates upgrade options; replace is the only viable action), DEPREMED-5
- Is-transitive flag (direct / transitive) → DEPREMED-4 (transitive requires different intervention path than direct)
- Blast radius (how many consuming packages depend on this) → DEPREMED-3 (large blast radius triggers staged-migration), DEPREMED-2
- License conflict present (yes / no) → DEPREMED-1 (license conflict in production makes accept-with-waiver inadmissible regardless of CVE state)
- Project update cadence (existing cadence from repo history) → DEPREMED-5 (cadence recommendation is calibrated to observed team rhythm)

## Section 3 — Opinionated Defaults

- DEPREMED-1: Default remediation action is **upgrade-minor**. Apply to every package where a non-breaking fix is available. When no patch or minor fix exists, escalate to upgrade-major. Pin only as a temporary hold when a safe upgrade is blocked by a pipeline constraint. Replace when the package is Abandoned with no upstream fix. Accept-with-waiver is a last resort — it requires explicit severity ≤ Medium AND reachability confirmed as unlikely/unreachable AND a written waiver expiry date.
- DEPREMED-2: Default prioritisation: Critical CVE with known exploit → Critical CVE theoretical → High CVE reachable → High CVE unknown reachability → Abandoned (no fix) → High CVE unreachable → Stale with major upgrade available → Medium CVE → Low CVE → minor freshness findings.
- DEPREMED-3: Default breaking-change handling is **staged-migration**: add the new major to a feature branch, validate in a lower environment before cutting the main dependency. Shim-layer only when the new major API is a superset. Immediate-cut only for Critical CVE with known exploit and semver-major fix available.
- DEPREMED-4: Default transitive strategy is **pin-transitive**: add a direct override entry (resolutions / overrides field in manifest) to force the safe transitive version while upstream upgrades. Prefer lift-to-direct when the transitive package is generic and the team already uses it directly. Replace-parent when the parent is Abandoned or the transitive CVE persists across all parent versions.
- DEPREMED-5: Default update cadence is **monthly-minor** (patch upgrades bundled monthly; minor upgrades reviewed and applied monthly). Continuous-patch is recommended for projects with mature CI and good coverage. Quarterly-major for stable production services. On-finding-only is only acceptable for frozen legacy systems with a documented freeze policy.

## Section 4 — Derivation Rules

- DEPREMED-D-1: When CVE severity is Critical AND exploitability is known-exploit-in-wild, choose upgrade-minor (if patch fix) or upgrade-major (if only major fix is available) with immediate-cut breaking-change strategy because a live exploit cannot tolerate staged rollout — the attack surface must close before the next deployment window.
- DEPREMED-D-2: When CVE severity is Critical or High AND reachability is confirmed-reachable, choose upgrade-minor or upgrade-major (whichever semver delta the fix requires) because reachability converts theoretical risk to operational exposure — pin and accept-with-waiver are inadmissible when the path to the vulnerable code is confirmed.
- DEPREMED-D-3: When CVE severity is Medium or Low AND reachability is confirmed-unreachable AND no exploit is public, choose accept-with-waiver because shipping a breaking upgrade for an unreachable code path produces more disruption than the residual risk warrants — waiver must carry an expiry date ≤ 90 days and be re-evaluated at next cadence cycle.
- DEPREMED-D-4: When freshness classification is Abandoned AND no patch or minor upgrade exists, choose replace because a maintainer-absent package will accumulate future CVEs with no upstream resolution path — replacement is the only durable remediation.
- DEPREMED-D-5: When the remediation semver delta is major AND blast radius is high (≥5 consuming packages or a foundational library), choose staged-migration breaking-change strategy because broad blast radius means an incorrect migration silently breaks multiple downstream consumers — validate in isolation before cutting.
- DEPREMED-D-6: When the dependency is transitive AND CVE severity is Critical or High AND the parent package is actively maintained, choose pin-transitive (via resolutions/overrides) because the parent maintainer may not have released a fix yet — pinning the transitive directly closes the CVE while upstream catches up.
- DEPREMED-D-7: When the dependency is transitive AND the parent package is Abandoned or Stale, choose replace-parent because pinning a transitive under a dead parent is an unstable arrangement — the parent itself needs to be replaced, which resolves the transitive finding transitively.
- DEPREMED-D-8: When project CI runs on every PR and test coverage is ≥80%, choose continuous-patch cadence because high automation confidence means patch upgrades carry negligible regression risk and batching them monthly creates unnecessary accumulation of resolved CVEs.
- DEPREMED-D-9: When a license conflict is present in a production dependency, accept-with-waiver is inadmissible regardless of CVE state — choose replace or upgrade to a license-compatible version because license contamination has legal consequence that no internal waiver can indemnify.

## Section 5 — Recommendation Output Contract

Every recommendation block that upgrade-planner emits MUST include all of the following for each finding:

1. **Chosen remediation action** — named from the DEPREMED-1 set (upgrade-minor / upgrade-major / pin / patch / replace / accept-with-waiver), not a vague description.
2. **Rule citation** — list each DEPREMED-D-N rule that fired; if no derivation rule fired, state "defaults apply (DEPREMED-1 default: upgrade-minor)".
3. **Constraint derivation** — one sentence naming the specific input values that triggered the cited rule (e.g. "CVE severity = High, reachability = confirmed-reachable → DEPREMED-D-2").
4. **At least one named alternative** with a brief rationale for why it was not chosen (e.g. "Alternative: accept-with-waiver — rejected because reachability is confirmed, making waiver inadmissible per DEPREMED-D-2").
5. **Override hook** — a concrete instruction for the implementer (e.g. "Override: set `resolution.lodash = 4.17.21` in package.json#resolutions if direct upgrade is blocked by pipeline constraint; re-evaluate at next cadence cycle").

Consumers of this pack MUST NOT emit a remediation recommendation without the rule citation and constraint derivation. Neutral menus of options with no stated recommendation violate PIT-11 and are non-compliant.

## Section 6 — Enforcement Handoff

dependency-remediation-craft output is validated by upgrade-risk (semver delta, breaking-change surface, and version fabrication constraints — every upgrade-major recommendation must satisfy the upgrade-risk major-version rule requiring stated breaking-change surface or verbatim unknown statement) and audit-report-format (every finding block must include the consequence statement and appear in the canonical severity-sorted section structure).
