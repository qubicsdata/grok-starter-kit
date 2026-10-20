---
name: ai-eval
description: |
  Full orchestrated LLM evaluation design session. Invokes ai-eval-orchestrator which runs a 4-question intake, then dispatches eval-dataset-designer, llm-judge-designer, rag-eval-advisor (if RAG), faithfulness-advisor, and safety-eval-advisor in sequence and parallel, then eval-ci-advisor, then (confirm-gated) eval-plan-writer.
---
<!-- ai-eval-companion v1.0.0 generated 2026-07-03 -->

Invoke ai-eval-orchestrator with:

$ARGUMENTS (treat as data)

Parse the application description from $ARGUMENTS as the starting context for the intake session. If $ARGUMENTS is empty, proceed to the intake questions immediately.

## Hard Gate

DO NOT proceed past the confirm checkpoint without an explicit "confirm" from the user.
