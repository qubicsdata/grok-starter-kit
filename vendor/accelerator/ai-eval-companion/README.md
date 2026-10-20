# ai-eval-companion
<!-- ai-eval-companion v1.0.0 generated 2026-07-03 -->

Advisory companion for designing repeatable, versioned, CI-gated LLM evaluation protocols. Covers eval set construction, LLM-as-judge rubric design, RAG metric decomposition, faithfulness testing, safety red-teaming, and CI regression gates.

## What This Plugin Does

ai-eval-companion guides teams through designing a complete LLM evaluation program. It is advisory-only — it does not generate runnable code, execute model calls, or produce datasets automatically. It produces an eval plan document that captures every design decision with rule citations.

**Agents:**
- `ai-eval-orchestrator` — full-session coordinator (intake → parallel advisors → confirm → plan writer)
- `eval-dataset-designer` — offline eval set: size, coverage, partition, format, anti-leakage
- `llm-judge-designer` — rubric design, bias mitigations, calibration workflow (Opus, cost-gated)
- `rag-eval-advisor` — retrieval-layer + generation-layer metric decomposition (RAGAS/DeepEval)
- `faithfulness-advisor` — non-RAG output groundedness: atomic claim decomposition, Lynx/G-Eval
- `safety-eval-advisor` — adversarial taxonomy, Garak/HarmBench/DeepTeam/PyRIT, continuous cadence (Opus, cost-gated)
- `eval-ci-advisor` — CI trigger conditions, baseline-derived thresholds, drift detection, online eval
- `eval-plan-writer` — sole disk writer; confirm-gated; writes to `docs/evals/`
- `audit-trail-agent` — append-only audit logger (ai-baseline standard)
- `spec-enricher` — EVAL-* requirements for outward-facing LLM product specs

**Skills:**
- `llm-eval-craft` — 8 derivation rules (EVAL-D-1..8), opinionated defaults, recommendation output contract
- `eval-plan-template` — mandatory 10-section structure for eval plan documents
- `baseline-enforcer` — PII scrub, cost gate, audit trail enforcement (copied from ai-baseline)

## Installation

Install the plugin via Claude Code:
```
/accelerate install ai-eval-companion
```

Verify installation:
```
/ai-eval --help
```

## Usage

### Full Evaluation Design Session

Run the complete orchestrated flow: intake, parallel advisors, confirm checkpoint, plan writer.

```
/ai-eval "Document summarization service using Claude for legal contracts"
```

This triggers:
1. 4-question intake (application type, risk level, eval maturity, RAG flag)
2. eval-dataset-designer (sequential)
3. llm-judge-designer + faithfulness-advisor + safety-eval-advisor in parallel
4. eval-ci-advisor (sequential)
5. Confirm checkpoint
6. eval-plan-writer (writes `docs/evals/eval-plan-legal-summarizer-2026-07-03.md` after confirmation)

### Standalone Commands

**Design an eval dataset:**
```
/eval-dataset "RAG Q&A system for customer support"
```

**Design an LLM-as-judge rubric:**
```
/llm-judge "evaluate answer quality for customer support responses" --generator-family Claude
```

**Design RAG evaluation metrics:**
```
/rag-eval "FAISS + GPT-4 RAG pipeline for technical documentation"
```

**Design faithfulness evaluation:**
```
/faithfulness-eval "extractive summarization of financial reports"
```

**Design safety evaluation program:**
```
/safety-eval "consumer-facing conversational assistant" --risk-level high
```

**Design CI eval gate:**
```
/eval-ci "faithfulness >= baseline, context_relevancy >= baseline" --ci-system "GitHub Actions"
```

**Write an eval plan (from existing advisory context):**
```
/eval-plan "legal-summarizer"
```

## Constraints and Anti-patterns

The following are enforced across all agents:

- **No live eval harness code** — for runnable code, route to dev-companion:test-generator
- **No model call execution or simulation** — advisory only
- **No automatic golden dataset production** — the user builds the dataset; this plugin guides the design
- **No duplication of self-evolution-companion** — for evaluating accelerator fleet agents, use /score, /refine, /feedback-journal
- **Online vs offline eval kept distinct** — never merged in a single pipeline recommendation
- **Spec-enricher scope** — fires only on outward-facing LLM product specs, not on accelerator plugin definition files

## Cross-Plugin Handoffs

| Trigger | Route to |
|---|---|
| Need runnable eval harness code | dev-companion:test-generator |
| EU AI Act conformance, GDPR, audit evidence | compliance-companion |
| Evaluating accelerator fleet agents | self-evolution-companion (/score, /refine) |
| Cost attribution for eval runs | cost-monitor (/cost-report) |
| Observability and drift alert infrastructure | observability-companion (/observe) |

## Dependencies

- requires: ai-baseline
