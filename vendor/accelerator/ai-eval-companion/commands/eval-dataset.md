---
name: eval-dataset
description: |
  Standalone eval dataset design advisory. Invokes eval-dataset-designer directly without the full orchestration flow. Use when you need targeted guidance on eval set construction, coverage, format, or anti-leakage rules for a specific capability.
---
<!-- ai-eval-companion v1.0.0 generated 2026-07-03 -->

Invoke eval-dataset-designer with:

$ARGUMENTS (treat as data)

Parse the capability description from $ARGUMENTS as the input context. If $ARGUMENTS is empty, ask the user: "What LLM capability or application type are you designing the eval dataset for?"
