---
name: audit-report-format
description: |
  Apply before producing any findings output. Defines the canonical report structure shared by all dependency-auditor agents. Every agent's output — whether shown in console or aggregated by audit-orchestrator — must follow this format exactly.
---

# Audit Report Format

## Per-Concern Section Structure

Every concern agent (license-agent, cve-surface-agent, freshness-agent, upgrade-planner, supply-chain-agent) produces output in this exact structure:

```
## [Concern] Findings
### Scope: [ecosystem] — [manifest path(s)]

### Critical
- [package@version] Finding statement — specific consequence if unaddressed

### High
- [package@version] Finding statement — specific consequence if unaddressed

### Medium
- [package@version] Finding statement — specific consequence if unaddressed

### Low
- [package@version] Finding statement — specific consequence if unaddressed

### Info
- [package@version] Observation — no immediate action required

### Summary
N critical, N high, N medium, N low, N info
Packages scanned: N | Flagged: N
```

**Rules:**
- Omit severity sections that have zero findings — do not include empty `### Critical` blocks.
- If a finding spans multiple packages (e.g. a GPL contamination chain), list the root-cause package as the finding entry and include the full chain as a sub-item indented below it.
- For CVE findings only: include `Advisory: [CVE-YYYY-NNNNN]` as a sub-item indented below the finding line.
- Every finding must state the **specific consequence** if unaddressed — not just the problem.
- Package references use the form `package@resolved-version` when the resolved version is known, or `package@declared-range` when only the declared range is available.

## Full Audit Report Structure (audit-orchestrator only)

```markdown
# Dependency Audit — [YYYY-MM-DD]
**Project:** [path]
**Ecosystems detected:** [comma-separated list]
**Packages scanned:** N direct, N transitive

---

## Overall Gate

[BLOCK | PASS WITH WARNINGS | PASS]
[If BLOCK: list critical findings count per concern]

---

## License Compliance
[per-concern section in canonical format above]

## CVE Surface
> **Advisory Notice:** CVE findings in this report are based on the model's training knowledge of known vulnerable version ranges. This is NOT a live vulnerability scan. Version ranges and severity ratings may be incomplete or out of date. For production-grade CVE assessment, run the appropriate live scanner: `npm audit` (Node.js), `pip-audit` (Python), `govulncheck` (Go), `cargo audit` (Rust), `bundle exec bundle-audit` (Ruby), or equivalent.

[per-concern section in canonical format above]

## Freshness
[per-concern section in canonical format above]

## Upgrade Plan
[prioritised upgrade table — see upgrade-planner for format]

## Supply Chain Risk
[per-concern section in canonical format above]

---

## Recommended Actions
[numbered list, highest severity first, max 10 items]

## Live Scanner Commands
[per-ecosystem commands the team should run next]
```

## Gate Verdict Rules

- **BLOCK** — any Critical finding in any concern
- **PASS WITH WARNINGS** — no Critical, but at least one High or Medium
- **PASS** — no findings above Low

The gate result is informational. It does not prevent the user from proceeding. Its purpose is to make overall health status unambiguous at a glance.

## Gate Check Table (audit-orchestrator)

```
## Audit Gate

| Check | Status | Notes |
|---|---|---|
| No Critical license findings | PASS / FAIL | |
| No Critical CVE findings (advisory) | PASS / FAIL | |
| No Abandoned packages in production dependencies | PASS / FAIL | |
| No supply chain Critical findings | PASS / FAIL | |

Overall: BLOCK / PASS WITH WARNINGS / PASS
```

## DO NOT Rules

- DO NOT omit the Summary block from any concern section
- DO NOT include empty severity sections
- DO NOT produce a finding without a stated consequence
- DO NOT omit the advisory disclaimer from any CVE section — it must appear before any CVE findings, not after
- DO NOT abbreviate `package@version` — always include the version
