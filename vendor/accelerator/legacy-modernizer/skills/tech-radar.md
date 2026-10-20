---
name: tech-radar
description: Classifies technologies as Adopt, Trial, Assess, or Hold based on 5-factor criteria. Invoked by upgrade-map-agent for every technology in docs/modernization/inventory.md. Hold-rated technologies cannot be recommended target states.
---

## Purpose

The tech-radar skill provides upgrade-map-agent with a four-ring classification for every technology that appears in the codebase inventory — both existing technologies and candidate replacements. Classification is based on five factors: maturity, ecosystem health, security posture, project fit, and operational complexity. Never on trend or popularity alone.

## Classification Rings

| Ring | Meaning | In an upgrade map |
|------|---------|-------------------|
| **Adopt** | Proven in production at scale; strong ecosystem; low risk; actively maintained | Safe to recommend as a target state |
| **Trial** | Promising; growing adoption; some production use; API may not be fully stable | Acceptable as a target state; document the migration risk |
| **Assess** | Interesting; early stage; limited production use; higher uncertainty | Not recommended as a migration target for production systems |
| **Hold** | Declining; security concerns; deprecated; abandoned; or known critical issues | CANNOT be a recommended target state — see Hold-Rated Behaviour below |

## Classification Criteria (all five must be assessed)

1. **Maturity** — How long has the technology been in production use? Is the major version stable?
2. **Ecosystem health** — Active maintainers, recent releases, open issue response time, community size
3. **Security posture** — Known CVEs, patch cadence, supply-chain transparency
4. **Project fit** — Does it address the project's stated constraints (runtime, language, team expertise)? Is it compatible with the technologies that will remain after migration?
5. **Operational complexity** — What is the cost to run, monitor, and upgrade this technology in production?

## Classification Application Rules

When upgrade-map-agent names a technology (existing or candidate):

1. State the ring: `Adopt`, `Trial`, `Assess`, or `Hold`
2. Provide a one-line rationale citing which criteria drove the classification
3. If `Hold`, add: `HOLD — cannot be recommended as a target state. Included for reference only.`
4. If `Assess`, add: `ASSESS — not recommended as a migration target for a production system layer.`

## Hold-Rated Behaviour

DO NOT allow a Hold-rated technology to appear as a recommended target state in `docs/modernization/upgrade-map.md`. It may appear in the options table for transparency, but the recommendation column must be blank or explicitly marked "Not recommended — Hold."

If a technology currently in use is Hold-rated, the upgrade-map MUST recommend moving away from it. The recommended target state options must be Adopt or Trial ring technologies only.

If the user wishes to keep a Hold-rated technology in use, the orchestrator MUST:
1. Create a pending ADR for that decision
2. Flag the item in the upgrade map as a risk-acknowledged choice
3. Surface the following message before proceeding:

> WARNING: [Technology] is Hold-rated due to [reason]. Keeping it as the target state introduces significant risk. Do you wish to proceed with this choice and document the risk in an ADR? (yes / choose a different option)

## Output Format (within upgrade-map-agent tables)

```
| Technology | Current ring | Rationale |
|------------|-------------|-----------|
| React 18   | Adopt | Mature, actively maintained, strong ecosystem, stable API |
| Webpack 4  | Hold | Major version superseded; known performance issues; Webpack 5 is current; community migrating to Vite/esbuild — HOLD: cannot be recommended as a target state |
| Vite       | Adopt | Actively maintained; fast HMR; strong ecosystem fit for React projects |
| esbuild    | Trial | Excellent performance; production use growing; plugin ecosystem smaller than Vite |
```

## Rules

DO NOT rate a technology as Adopt solely because it is widely used or trending. Popularity is one signal, not the classification.

DO NOT rate a technology as Hold without citing at least one specific reason from the 5-factor criteria.

DO NOT omit tech-radar classification for any technology named by upgrade-map-agent — every named option must carry a ring rating.

DO NOT treat historical patterns or training-data knowledge as authoritative without verifying against current release notes and upstream documentation. Always apply the 5-factor criteria independently.

STOP and require explicit user acknowledgement before allowing a Hold-rated technology to remain as the recommended target state.
