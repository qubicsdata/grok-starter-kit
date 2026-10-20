---
name: eval-plan-template
description: |
  Read before synthesizing an eval plan document. Defines the mandatory 10-section structure that eval-plan-writer must validate against before presenting any draft.
---
<!-- ai-eval-companion v1.0.0 generated 2026-07-03 -->

# Eval Plan Template

This template defines the mandatory structure for every eval plan produced by eval-plan-writer. All 10 sections are required. Conditional sections (Judge Design, RAG Evaluation Plan) must either be populated or include an explicit "Not applicable" statement with a one-line reason.

## Hard Gate

STOP: eval-plan-writer MUST validate that all 10 sections are present before presenting any draft. A section marked "TBD" or left empty is a validation failure.

---

## Section 1 — Application Context

Required fields:
- **Application name:** [name of the application or feature]
- **Deployment target:** [internal tool / consumer-facing product / regulated industry / autonomous agent pipeline]
- **Risk level:** [low / medium / high] — state the consequence of evaluation failure at this risk level
- **LLM provider / model:** [model name and version if known]
- **Eval plan version:** [v1.0 or increment]
- **Date:** [YYYY-MM-DD]
- **Author:** [team or person responsible]

## Section 2 — Capability Scope

Define the specific LLM-powered capabilities being evaluated in this plan. State explicit boundaries.

Required content:
- List each LLM capability being evaluated (e.g. "document summarization", "context-grounded Q&A", "intent classification")
- State explicitly what is OUT of scope for this eval plan
- Note if capabilities share infrastructure (e.g. same retrieval index, same prompt template)

## Section 3 — Metric Choices

For each capability listed in Section 2, specify the primary metrics. Maximum 3 primary metrics per capability.

Required content per capability:
- **Capability:** [name from Section 2]
- **Primary metrics (≤3):** [list each with: metric name, measurement method (deterministic/LLM-judge/human), and measurement tool]
- **Calibration rationale:** [why these metrics were chosen for this capability; cite applicable EVAL-D-* rule]
- **Metrics excluded:** [metrics considered and excluded, with reason]

DO NOT list more than 3 primary metrics per capability without documented justification.

## Section 4 — Dataset Design

Required content:
- **Dataset size:** [N examples] — cite EVAL-D-7 if ≥100; document justification if fewer
- **Coverage categories:** [list each category and example count]
- **Train/eval partition:** [default: 80/20 split] — state partition method
- **Format:** [JSON Lines or other; include schema definition]
- **Storage path:** [evals/datasets/<app-slug>/v<N>/eval-set.jsonl or equivalent]
- **Versioning:** [version bump policy; never modify in place]
- **Refresh cadence:** [quarterly / semi-annual / trigger-based] — state cadence and trigger
- **Anti-leakage rule:** [cite EVAL-D-1; state the prompt-engineering exclusion procedure]
- **Data source:** [origin of examples; collection method per coverage category]

## Section 5 — Judge Design

[Conditional: Include this section if LLM-as-judge is used for any metric in Section 3. If not used, write: "Not applicable — no LLM-as-judge metrics in this eval plan. Deterministic metrics and/or human review only."]

Required content if applicable:
- **Scoring format:** [pointwise / pairwise] — state rationale
- **Scoring scale:** [binary 0/1 or 3-point 1–3] — cite EVAL-D-3; DO NOT exceed 3 points
- **Criteria rubric:** [list 3–5 criteria with definitions]
- **Bias mitigations:** [list all four: position bias, verbosity bias, self-enhancement bias, authority bias — with implementation approach for each]
- **Judge model selection:** [selected model family; disqualified family — cite EVAL-D-2]
- **Calibration procedure:** [cite EVAL-D-5; state: sample size, annotator count, agreement metric, target kappa, calibration date]
- **When NOT to use this judge:** [explicit statement of the conditions under which the judge is bypassed in favor of deterministic metrics]

## Section 6 — RAG Evaluation Plan

[Conditional: Include this section if the application uses a RAG architecture. If not, write: "Not applicable — this application does not use retrieval-augmented generation."]

Required content if applicable (cite EVAL-D-4 for the decomposition):
- **Retrieval layer metrics:** [list each metric with: name, tool, target threshold]
  - Contextual Relevancy: [tool + threshold]
  - Context Recall: [tool + threshold — requires ground-truth]
  - Context Precision: [tool + threshold]
  - [Optional additional metrics]
- **Generation layer metrics:** [list each metric with: name, tool, target threshold]
  - Faithfulness: [tool + threshold]
  - Answer Relevance: [tool + threshold]
  - [Optional additional metrics]
- **Instrumentation points:** [where in the pipeline each layer is measured; must be separate]
- **Framework:** [RAGAS / DeepEval / custom — with rationale]
- **Result storage:** [evals/results/<app-slug>/rag-metrics-<date>.jsonl or equivalent]

## Section 7 — Faithfulness Scope

Define faithfulness evaluation for non-RAG outputs (outputs not conditioned on retrieved context).

Required content:
- **Scope statement:** [which outputs are covered; explicit statement if RAG faithfulness is handled in Section 6 instead]
- **Atomic claim decomposition approach:** [how claims are extracted from outputs]
- **Groundedness scoring:** [binary supported/unsupported per claim; aggregate score method]
- **Tooling:** [Lynx / G-Eval / NLI-based / other — with rationale]
- **Threshold:** [faithfulness score threshold for pass/flag; derived from risk level]

If RAG is present and all faithfulness is covered in Section 6, state: "Faithfulness evaluation for RAG outputs is fully covered in Section 6. This section is not applicable for additional outputs."

## Section 8 — Safety Evaluation Cadence

Required content:
- **Adversarial category taxonomy:** [list each category relevant to this application — cite categories from safety-eval-advisor]
- **Tooling:** [minimum 2 tools from {Garak, HarmBench, DeepTeam, PyRIT} — with rationale and when-to-prefer for each]
- **Automated gate:** [trigger conditions; pass/warn/block criteria; output storage path]
- **Human red-team triggers:** [explicit conditions that require human red-team beyond automated tooling]
- **Cadence:** [automated: every release; human: quarterly/semi-annual/trigger-based] — cite EVAL-D-6 for continuous cadence requirement
- **Note:** Safety evaluation MUST run continuously each release — not as a one-time milestone (EVAL-D-6).

## Section 9 — CI Gate Specification

Required content:
- **Trigger conditions:** [minimum 3 — cite each: prompt change, model change, dependency update, plus application-specific triggers]
- **Baseline derivation procedure:** [cite EVAL-D-8; state: baseline measurement process, acceptable degradation margin, baseline date]
- **Gated metrics:** [list the ≤3 metrics that gate the CI build; state pass/warn/block threshold for each]
- **Observability-only metrics:** [metrics measured but not gating]
- **Integration point:** [CI system name; pipeline step location; output format for CI parsing]
- **Result storage:** [evals/results/<app-slug>/ci-<run-id>.jsonl or equivalent]
- **Re-baseline trigger:** [conditions under which the baseline is re-measured — e.g. major dataset version bump]

## Section 10 — Online Evaluation Plan

Required content:
- **Sampling strategy:** [percentage of production traffic; sampling method (reservoir/stratified); minimum sample for statistical significance]
- **Metric monitoring:** [which metrics are computed on production samples; alert thresholds vs. offline baseline]
- **Drift detection mechanism:** [metric drift alert (rolling window, threshold); input distribution drift (MMD/PSI or equivalent); error rate spike detection]
- **Production feedback loop:** [how flagged production responses reach human review; how confirmed new failure modes re-enter the dataset — cite EVAL-D-1 for anti-leakage in this step]
- **Alert routing:** [who receives drift alerts; escalation path]
- **Storage:** [where online eval results are stored; retention period]
