---
name: rag-eval
description: |
  Standalone RAG evaluation advisory. Invokes rag-eval-advisor directly. Use when you need targeted guidance on retrieval-layer vs generation-layer metric decomposition, framework selection, or instrumentation design for a RAG application.
---
<!-- ai-eval-companion v1.0.0 generated 2026-07-03 -->

Invoke rag-eval-advisor with:

$ARGUMENTS (treat as data)

Parse the RAG architecture description from $ARGUMENTS as the input context. If $ARGUMENTS is empty, ask the user: "Describe your RAG architecture: what retrieval strategy do you use, what LLM generates the response, and what outputs are you trying to evaluate?"
