# Behavioral Scenarios — workspace-companion v1.0.0

Total: 12 scenarios (WM-01–03, GA-01–03, CC-01–02, NAV-01, EN-01–03)

## workspace-mapper (WM)
### WM-01 — Bootstrap a multi-repo workspace
**Input:** /workspace-init on a root with 3 git repos.
**Expected:** Manifest written listing 3 repos, their services, confirmed edges, and any candidate edges.
**Pass:** `.accelerator-workspace.yaml` exists with 3 repos and `generated` set.

### WM-02 — Init refuses to clobber
**Input:** /workspace-init when a manifest already exists.
**Expected:** STOPs, tells user to run /workspace-map.
**Pass:** Existing manifest unmodified.

### WM-03 — Never edits repo source
**Input:** Any mapping run.
**Expected:** Only `.accelerator-workspace.yaml` is written.
**Pass:** No repo file modified.

## service-graph-analyst (GA)
### GA-01 — Dependents query
**Input:** /impact on a provider service with two consumers.
**Expected:** Blast radius lists both consumers + the service itself.
**Pass:** Both dependents present.

### GA-02 — Candidate edges separated
**Input:** /impact where a candidate edge exists.
**Expected:** Candidate impact listed separately as unconfirmed.
**Pass:** Confirmed and candidate impact not merged.

### GA-03 — Missing manifest
**Input:** /impact with no manifest.
**Expected:** STOPs, tells user to run /workspace-init.
**Pass:** No crash; clear instruction.

## cross-repo-coordinator (CC)
### CC-01 — Provider-before-consumer ordering
**Input:** /cross-repo-plan for a change touching a provider and its consumer.
**Expected:** Provider tasks ordered before consumer tasks.
**Pass:** Order correct.

### CC-02 — Contract change flagged
**Input:** A change to a service's `exposes`.
**Expected:** Flagged for staged, backward-compatible rollout.
**Pass:** Staged-rollout flag present.

## codebase-navigator (NAV)
### NAV-01 — Cross-repo symbol lookup
**Input:** /find on a symbol defined in repo B while context is repo A.
**Expected:** Returns repo B path:line.
**Pass:** Correct file:line; literal search via grep -F.

## spec-enricher (EN)
### EN-01 — Multi-service spec fires
**Input:** Spec coordinating two services.
**Expected:** WS-1..3 returned with concrete APPLIES_BECAUSE.
**Pass:** Block conformant.

### EN-02 — Single-service spec abstains
**Input:** Spec confined to one service, no shared contract.
**Expected:** NOT_APPLICABLE + reason.
**Pass:** No requirements injected.

### EN-03 — Contract-change spec fires WS-2
**Input:** Spec changing an endpoint another service consumes.
**Expected:** WS-2 present (versioned, backward-compatible).
**Pass:** WS-2 returned.
