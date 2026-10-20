---
name: migration-risk-scale
description: Probability × impact scoring rubric for migration risks. Invoked by risk-scorer on every item in docs/modernization/inventory.md. Defines four priority levels and DO NOT rules to prevent uniform scoring.
---

## Purpose

The migration-risk-scale skill provides risk-scorer with a two-axis scoring rubric for every item in the codebase inventory that warrants a risk assessment. The output is a risk register where every item carries a numeric priority score and a named priority level, and where items are differentiated — no flat registers where everything is "High."

## Axes

Every risk item is scored on two axes, each from 1 to 4:

### Probability (how likely is this risk to materialise during or after migration)

| Score | Label | Meaning |
|-------|-------|---------|
| 4 | Near-certain | This will cause a problem unless explicitly mitigated. Applies to EOL runtimes, known-CVE dependencies, frameworks with no upgrade path. |
| 3 | Likely | Has caused similar problems in comparable migrations; mitigation exists but requires effort. |
| 2 | Possible | Could cause a problem depending on implementation details not fully visible from static analysis. |
| 1 | Unlikely | Theoretical risk; no historical precedent in comparable codebases; low signal from inventory. |

### Impact (how severe is the consequence if this risk materialises)

| Score | Label | Meaning |
|-------|-------|---------|
| 4 | Critical | Data loss, security breach, prolonged production outage, or complete inability to deploy. |
| 3 | High | Significant rework (>1 sprint), partial feature loss, non-trivial recovery time. |
| 2 | Medium | Noticeable degradation, moderate rework (<1 sprint), recoverable quickly. |
| 1 | Low | Cosmetic or tooling issues; no user-facing impact; fixed in hours. |

## Priority Score

```
priority_score = probability × impact
```

Range: 1 (minimum) to 16 (maximum).

## Priority Levels

| Score range | Priority level |
|-------------|---------------|
| 12–16 | **Critical** |
| 8–11 | **High** |
| 4–7 | **Medium** |
| 1–3 | **Low** |

## Mandatory Scoring Triggers (Critical floor)

risk-scorer MUST produce at least one Critical-priority item if ANY of the following are present in the inventory:

1. A runtime that has passed its end-of-life date (probability 4 / impact 4 = score 16)
2. A dependency with a known CVE flagged in the inventory (probability 4 / impact ≥3 = score ≥12)
3. A framework version more than 2 major versions behind current stable (probability 3 / impact 4 = score 12)

If none of these three conditions apply, the register may contain no Critical items — but this absence must be stated explicitly:

> "No Critical-priority risks identified based on the current inventory. None of the three mandatory Critical triggers (EOL runtime, CVE-flagged dependency, framework >2 major versions behind) are present."

## DO NOT Rules (prevent uniform scoring)

DO NOT score all items at the same priority level. A risk register where every item is "High" provides no actionable differentiation. If you find all items converging on the same level, apply these checks before presenting:

1. **Check probability calibration:** Is every item truly "likely"? Distinguish between risks that will certainly occur (score 4) versus ones that might occur (score 2–3). If the distinction cannot be made from static analysis, record it in the risk item's description and default to a lower probability.

2. **Check impact calibration:** Is every consequence truly severe? A broken test suite during migration is not the same as a production security breach. Apply the impact labels literally.

3. **Check item granularity:** Are large multi-part risks being scored as one item? Split compound risks into their components — a single "upgrade Node.js runtime" item may contain a runtime compatibility risk (High), a native module rebuild risk (Medium), and a CI pipeline update risk (Low).

4. **Apply the 2× rule:** At least two priority levels must be represented across the register. A register with all Critical and one Low item satisfies this. A register with all High items does not.

DO NOT use vague consequence language. Consequences must name a specific outcome:
- Wrong: "things may break"
- Correct: "Express middleware using deprecated `req.param()` API will throw TypeError on first request after upgrade"

DO NOT omit the `Mitigation category` field. Even if mitigation is unknown, write: "Unknown — requires further investigation."

## Output Format

risk-scorer applies this skill to produce items in this exact format:

```markdown
### [Short title — specific, not generic]

**Priority:** [score 1–16] | **Probability:** [1–4] | **Impact:** [1–4]
**Category:** [Runtime / Dependency / Framework / Pattern / Infrastructure / Security]
**Description:** [what the risk is — specific, not generic]
**Trigger:** [what must be true for this risk to materialise]
**Consequence if triggered:** [specific, named outcome]
**Mitigation category:** [type of work that reduces this risk — no code, no file paths]
```

## Example (correctly scored)

```markdown
### Node.js 14 runtime is end-of-life

**Priority:** 16 | **Probability:** 4 | **Impact:** 4
**Category:** Runtime
**Description:** The project runs on Node.js 14, which reached end-of-life in April 2023. No security patches are issued for this version.
**Trigger:** Any new CVE discovered in the Node.js 14 runtime after April 2023 — no patch will be released.
**Consequence if triggered:** Production system exposed to unpatched runtime vulnerability with no upstream remediation path; may trigger compliance violation if the system handles regulated data.
**Mitigation category:** Runtime upgrade to an LTS version with active security support.
```
