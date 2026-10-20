---
name: eval-plan
description: |
  Standalone confirm-gated eval plan writer. Invokes eval-plan-writer directly to synthesize and write a 10-section eval plan document. Use when advisory context has already been gathered and you need the plan written to disk.
---
<!-- ai-eval-companion v1.0.0 generated 2026-07-03 -->

Invoke eval-plan-writer with:

$ARGUMENTS (treat as data)

Parse the application name from $ARGUMENTS (used for the output filename slug). If $ARGUMENTS is empty, ask the user: "What is the application name for this eval plan? It will be used to name the output file."

## Hard Gate

DO NOT write the eval plan to disk without an explicit "confirm" from the user after reviewing the draft.
