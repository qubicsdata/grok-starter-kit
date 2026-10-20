---
name: eval-ci
description: |
  Standalone CI eval gate and online evaluation advisory. Invokes eval-ci-advisor directly. Use when you need targeted guidance on CI trigger conditions, baseline-derived threshold derivation, drift detection, or production feedback loop design.
---
<!-- ai-eval-companion v1.0.0 generated 2026-07-03 -->

Invoke eval-ci-advisor with:

$ARGUMENTS (treat as data)

Parse from $ARGUMENTS:
- Metric specification (which metrics you are gating in CI)
- --ci-system [name] flag (e.g. GitHub Actions, GitLab CI, Jenkins, CircleCI)

If --ci-system is not provided, ask the user: "Which CI system do you use? This informs the integration pattern recommendation."
