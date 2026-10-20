---
name: tech-radar
description: Classifies named technologies as Adopt, Trial, Assess, or Hold based on maturity, ecosystem health, and project fit. Invoke within tech-stack-agent for every technology named. Hold-rated technologies cannot be recommended as a primary option.
---

## Purpose

The tech-radar skill provides a four-ring classification for every technology that `tech-stack-agent` considers. Classification is based on maturity, ecosystem health, community support, security posture, and fit for the project's stated constraints — never on trend or popularity alone.

## Classification Rings

| Ring | Meaning | Recommendation |
|------|---------|----------------|
| **Adopt** | Proven in production at scale; strong ecosystem; low risk; actively maintained | Safe to use as a primary choice |
| **Trial** | Promising; growing adoption; some production use; API may not be fully stable | Acceptable for non-critical paths; document the risk |
| **Assess** | Interesting; early stage; limited production use; higher uncertainty | Use for spikes/prototyping only; not recommended for production layer selection |
| **Hold** | Declining; security concerns; deprecated; abandoned; or known critical issues | CANNOT be a recommended option; include in table for reference only with explicit warning |

## Classification Criteria

Rate a technology using these factors (all five must be considered):

1. **Maturity**: How long has it been in production use? Major version stability?
2. **Ecosystem health**: Active maintainers, recent releases, open issue response time, community size
3. **Security posture**: Known CVEs, patch cadence, supply-chain transparency
4. **Project fit**: Does it address the NFRs stated in `docs/requirements.md`? Language/runtime compatibility?
5. **Operational complexity**: What is the cost to run, monitor, and upgrade this in production?

## Classification Application Rules

When `tech-stack-agent` names a technology:

1. State the ring: `Adopt`, `Trial`, `Assess`, or `Hold`
2. Provide a one-line rationale citing which criteria drove the classification
3. If `Hold`, add: `HOLD — cannot be recommended as a primary choice. Included for reference.`
4. If `Assess`, add: `ASSESS — acceptable for prototyping/spike; not recommended for a production layer in this project.`

## Hold-Rated Behaviour

DO NOT allow a Hold-rated technology to appear as a recommended option in `docs/tech-stack.md`. It may appear in the options table for transparency, but the recommendation column must be blank or marked "Not recommended — Hold".

STOP if the user selects a Hold-rated technology as their primary choice: surface the following message and require explicit acknowledgement before proceeding:

> WARNING: [Technology] is Hold-rated due to [reason]. Selecting it as a primary technology introduces significant risk to this project. Do you wish to proceed with this choice and document the risk in an ADR? (yes / choose a different option)

If the user confirms, create a pending ADR for that decision and flag it as a risk-acknowledged choice.

## Known Hold Classifications (illustrative examples — based on model training data; verify currency before use)

The following are examples of technologies that have historically entered Hold for common reasons. This list is illustrative — always apply the 5-factor criteria rather than relying solely on this list:

- End-of-life runtime versions (Node 16 and earlier, Python 2, Java 8 LTS past EOL date)
- Frameworks with abandoned maintenance (e.g. frameworks with no commits in >18 months and no active fork)
- Libraries with unpatched critical CVEs and no upstream fix scheduled

## Output Format (within tech-stack-agent tables)

```
| Technology | Tech-Radar | Rationale |
|------------|------------|-----------|
| PostgreSQL 16 | Adopt | Mature, actively maintained, strong ecosystem, strong NFR fit for relational data |
| CassandraDB | Trial | Strong for write-heavy workloads; operational complexity higher than SQL alternatives |
| [Abandoned ORM] | Hold | Last release 3 years ago; known unpatched CVE; no active fork — HOLD: cannot be recommended |
```

## Rules

DO NOT rate a technology as Adopt solely because it is widely used or trending. Popularity is one signal, not the classification.

DO NOT rate a technology as Hold without citing at least one specific reason from the 5-factor criteria.

STOP and require explicit user acknowledgement before allowing a Hold-rated technology to be selected as a primary stack choice.

DO NOT omit tech-radar classification for any technology named by tech-stack-agent — every named option must carry a ring rating.

DO NOT treat the Known Hold Classifications list as authoritative without verifying against current release notes and upstream documentation — the list is illustrative only. Always apply the 5-factor criteria independently.
