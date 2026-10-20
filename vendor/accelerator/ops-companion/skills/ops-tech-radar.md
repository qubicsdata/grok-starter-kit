---
name: ops-tech-radar
description: |
  Classifies ops tooling as Adopt / Trial / Assess / Hold using 5-factor criteria: maturity, ecosystem health, security posture, project fit, operational complexity. Hold-rated tools cannot be recommended as primary choices in generated configs. Used by pipeline-designer and monitoring-designer before referencing any tool.
---

# ops-tech-radar

Apply this rubric to every tool, action, or platform referenced in a generated config or recommended to the user. Assign a ring and include the classification in the output.

---

## Rings

| Ring | Meaning | Impact on generated output |
|---|---|---|
| **Adopt** | Proven, stable, widely used in production. Recommend confidently. | Use freely in generated configs. |
| **Trial** | Promising, growing adoption, some rough edges. Evaluate on a bounded scope. | Use with a note: "Trial-rated: validated in limited production use. Evaluate before broad rollout." |
| **Assess** | Interesting but not yet proven at scale. Explore in non-critical contexts. | Do not use as a primary tool. Mention as an alternative with "Assess-rated: not recommended for production primary use without evaluation." |
| **Hold** | Deprecated, has security concerns, or poor operational track record. | **Cannot be recommended as a primary choice.** If the user's existing config uses a Hold-rated tool, flag it as a finding and suggest a replacement. |

---

## 5-factor scoring rubric

Score each factor 1–4 (1=poor, 4=excellent). Sum the scores. Map to ring:

| Total score | Ring |
|---|---|
| 17–20 | Adopt |
| 12–16 | Trial |
| 7–11 | Assess |
| 4–6 | Hold |

### Factor 1: Maturity
- 4: GA for 3+ years, used in Fortune 500 / large-scale open-source projects
- 3: GA for 1–3 years, growing production adoption
- 2: GA < 1 year or beta with limited production track record
- 1: Alpha, experimental, or no longer actively developed

### Factor 2: Ecosystem health
- 4: Large active community, vendor-backed or CNCF-graduated, regular releases
- 3: Active community, regular releases, good documentation
- 2: Small community, irregular releases, or documentation gaps
- 1: Abandoned, CVE-heavy without patches, or vendor sunset announced

### Factor 3: Security posture
- 4: SOC 2 / ISO 27001 certified (if applicable), signed releases, public CVE process, no critical unpatched CVEs
- 3: Signed releases, public security contact, minor CVE history with prompt patches
- 2: No release signing or intermittent patch cadence
- 1: Known critical CVEs unpatched, or tool itself is a known supply-chain risk

### Factor 4: Project fit
- 4: Directly solves the stated requirement with minimal configuration
- 3: Solves the requirement with moderate configuration or a thin wrapper
- 2: Solves a related requirement; requires significant adaptation
- 1: Mismatch — solving the wrong problem, or adds complexity without clear benefit

### Factor 5: Operational complexity
- 4: Self-contained, minimal ops overhead, easy to upgrade
- 3: Moderate overhead, well-documented operational procedures
- 2: High overhead or requires deep expertise to operate correctly
- 1: Significant operational risk — hard to upgrade, debug, or monitor

---

## Pre-assessed tools (common ops tooling)

Apply these ratings without re-scoring unless the user provides context that changes the assessment.

| Tool | Ring | Notes |
|---|---|---|
| GitHub Actions | Adopt | Native to GitHub; broad ecosystem of actions |
| GitLab CI | Adopt | Native to GitLab; mature YAML pipeline model |
| CircleCI | Trial | Solid product; less dominant since GHA growth |
| Buildkite | Trial | Strong for large-scale pipelines; self-hosted agents |
| Jenkins | Hold | Operational complexity and plugin CVE surface; superseded by native CI for most use cases |
| Terraform | Adopt | IaC standard; large ecosystem |
| Pulumi | Trial | Strong multi-language IaC; smaller ecosystem than Terraform |
| AWS CDK | Trial | Good for AWS-native teams; TypeScript/Python first |
| CloudFormation | Adopt | Mature, native AWS; verbose but stable |
| Ansible | Trial | Strong for configuration management; less suited to cloud resource IaC |
| Prometheus + Grafana | Adopt | De-facto standard for self-hosted metrics and dashboards |
| OpenTelemetry (OTel) | Adopt | CNCF-graduated; vendor-neutral; growing fast |
| Datadog | Adopt | Strong commercial observability platform |
| CloudWatch | Adopt | Native AWS; acceptable for AWS-centric stacks |
| Semgrep | Adopt | SAST standard; fast, low false-positive rate |
| Trivy | Adopt | Container and IaC vulnerability scanner; fast and accurate |
| Snyk | Adopt | Developer-friendly SCA and SAST; commercial tiers available |
| cosign (Sigstore) | Trial | Container signing standard; growing adoption |
| Dependabot | Adopt | Native to GitHub; low-friction dependency updates |
| Renovate | Adopt | Cross-platform dependency updates; highly configurable |
| OWASP Dependency-Check | Trial | SCA tool; effective but slower than Snyk/Trivy |
| grype | Trial | Fast container/SBOM vulnerability scanner; growing adoption |
| pip-audit | Adopt | Standard Python dependency audit tool |
| npm audit | Adopt | Built into npm; baseline dependency scanning |

---

## Output format

When classifying a tool during config generation or review:

```
[tool name]: [Ring] — [one-sentence rationale]
```

When a Hold-rated tool appears in an existing config:

```
HOLD-RATED TOOL: [tool name] at [file:line]
Reason: [why it is Hold-rated]
Suggested replacement: [Adopt or Trial alternative]
```
