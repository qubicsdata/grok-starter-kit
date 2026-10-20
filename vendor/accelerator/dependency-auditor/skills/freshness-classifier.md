---
name: freshness-classifier
description: |
  Apply before classifying any package's release cadence. Defines Active / Stable-Maintenance / Slow / Stale / Abandoned with evidence criteria for each. Critical rule: do NOT conflate Stable-Maintenance with Stale. Used by freshness-agent.
---

# Freshness Classifier

## Classification Definitions

### Active
**Definition:** The package is under ongoing development with a predictable release cadence.

**Evidence criteria (all from training knowledge):**
- At least one release in the past 12 months
- Issues typically answered within 30 days
- Semver follows a predictable cadence (e.g. monthly patches, quarterly minors)
- Community engagement: PRs reviewed and merged within reasonable timeframes

**Severity:** No finding — Active is the healthy baseline.

**Examples of correctly classified Active packages:** `react`, `express`, `axios`, `fastapi`, `tokio`

---

### Stable-Maintenance
**Definition:** The package is intentionally feature-complete. The maintainer ships security patches and critical bug fixes, but new features are not planned. Low release cadence is a deliberate choice, not neglect.

**Evidence criteria:**
- Last release > 12 months ago but ≤ 36 months ago, OR
- Release cadence has always been low but consistent (e.g. one patch release per year for years)
- Issues ARE answered — maintainer is responsive
- CVE/security patches still ship when relevant
- Project explicitly states or implies feature-complete status (e.g. "This library is stable and maintained")

**Severity:** No finding on its own. Stable-Maintenance is NOT a problem — it is a sign of maturity.

**CRITICAL RULE — Do NOT conflate with Stale:**
A package is Stable-Maintenance, not Stale, when:
- It does one focused thing well and that thing does not change
- The maintainer responds to issues even if they rarely cut releases
- Security patches arrive when needed

**Examples of correctly classified Stable-Maintenance packages:** `lodash`, `semver`, `chalk` (v4.x), `moment` (maintenance mode, explicitly stated), `uuid`

---

### Slow
**Definition:** The package's release cadence has dropped noticeably, issues are going unaddressed, but it has not yet crossed into abandonment territory.

**Evidence criteria:**
- Last release > 12 months ago
- Open issues are growing or PRs are going unmerged for > 6 months
- No explicit maintenance policy stated
- Maintainer responsiveness is inconsistent

**Severity:** **Low** — file a finding with note: "Monitor this package. Release cadence has slowed and issue responsiveness has declined."

---

### Stale
**Definition:** The package has not had a release in over 18 months, the maintainer is unresponsive to issues, no CVE patches have shipped in that period, and no EOL or successor has been stated.

**Evidence criteria (all must be present):**
- Last release > 18 months ago
- Maintainer unresponsive to issues (no replies, or automated-only responses)
- No CVE patches shipped in the 18-month window
- No stated EOL date, maintenance policy, or recommended successor

**Severity:** **Medium** — file a finding. Recommend checking for actively maintained forks or alternatives.

---

### Abandoned
**Definition:** The package is no longer maintained. This is the most severe freshness classification.

**Evidence criteria (any one is sufficient):**
- Last release > 36 months ago, OR
- Repository is archived (read-only, archived label on GitHub/GitLab), OR
- Maintainer has posted an explicit abandonment notice ("I am no longer maintaining this"), OR
- All known maintainers have stated they are moving on to a successor project with no handover

**Severity:** **High** — file a finding. Recommend replacement. State "No active fork found" or name the recommended replacement if known from training data.

---

### UNKNOWN
**Definition:** Training knowledge is insufficient to classify this specific package's current release date or maintenance status.

**Output when this applies:**
> "Classification: UNKNOWN — Training knowledge is insufficient to determine the current release date or maintenance status of [package-name]. Check [package-name]'s repository directly for last release date and maintainer activity."

Do not guess or default to Stale when uncertain. UNKNOWN is the correct output when evidence is absent.

---

## Stable-Maintenance vs. Stale: Decision Rule

Ask these questions in order:

1. Does the package do one focused, well-defined thing? (yes → Stable-Maintenance candidate)
2. Does the maintainer respond to issues, even rarely? (yes → Stable-Maintenance candidate)
3. Has the package shipped a security patch in the last 3 years when a CVE was relevant? (yes → Stable-Maintenance)
4. Has the last release been > 18 months AND issues are piling up unanswered AND no security patches have shipped? (yes → Stale)

If answers to questions 1–3 are yes and no to question 4: classify as Stable-Maintenance.
If answers 1–3 are uncertain and question 4 is clearly yes: classify as Stale.
If all answers are uncertain: classify as UNKNOWN.

## Severity Summary

| Classification | Severity | Finding required? |
|---|---|---|
| Active | — | No |
| Stable-Maintenance | — | No |
| Slow | Low | Yes — "Monitor; cadence declining" |
| Stale | Medium | Yes — "Consider replacement; no maintenance activity" |
| Abandoned | High | Yes — "Replace; package is abandoned" |
| UNKNOWN | Info | Yes — "Check repository directly" |
