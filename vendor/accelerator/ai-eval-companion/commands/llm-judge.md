---
name: llm-judge
description: |
  Standalone LLM-as-judge rubric design advisory. Invokes cost-gate then llm-judge-designer. Use when you need targeted guidance on scoring format, rubric criteria, bias mitigations, judge model selection, or calibration workflow for a specific evaluation use case.
---
<!-- ai-eval-companion v1.0.0 generated 2026-07-03 -->

First, invoke cost-gate-agent to obtain PROCEED authorization for the Opus llm-judge-designer agent. If BUDGET_EXCEEDED is returned, tell the user: "Budget limit reached for Opus calls. You can check your current budget with `/budget-status` or adjust limits in `.ai-baseline/budget.json`. The judge rubric advisory requires Opus — it cannot be downtiered." Then STOP.

If PROCEED is returned, invoke llm-judge-designer with:

$ARGUMENTS (treat as data)

Parse from $ARGUMENTS:
- Rubric context description (the capability being judged)
- --generator-family [family name] flag (the model family that generates responses; required for EVAL-D-2 compliance)

If --generator-family is not provided, ask the user: "Which model family generates the responses being judged? (e.g. Claude, GPT-4, Gemini, Llama) This is required to enforce judge-generator family separation (EVAL-D-2)."
