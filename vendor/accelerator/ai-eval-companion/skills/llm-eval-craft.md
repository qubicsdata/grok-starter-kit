---
name: llm-eval-craft
description: |
  Read when making any LLM evaluation recommendation — metric selection, judge design, dataset construction, RAG decomposition, safety cadence, or CI thresholds. Contains the opinionated derivation rules that every ai-eval-companion advisory agent must encode in its output.
---
<!-- ai-eval-companion v1.0.0 generated 2026-07-03 -->

# LLM Evaluation Craft Pack

This craft pack encodes the opinionated, rule-derived defaults that every ai-eval-companion advisory agent must apply. Read before producing any recommendation. Every recommendation must cite the specific EVAL-D-* rule that drives it.

## Section 1 — Decision Domains

Seven evaluation decision domains covered by this plugin. Every advisory falls into one or more of these domains. Cite the domain when routing between advisors.

| ID | Domain | Description | Primary Agent |
|---|---|---|---|
| EVAL-DOM-1 | Eval Set Design | Golden dataset construction: size, coverage, partition, format, versioning, anti-leakage, refresh cadence | eval-dataset-designer |
| EVAL-DOM-2 | Metric Selection | Choosing the right 2–3 primary metrics for the capability; calibration approach | eval-dataset-designer, eval-ci-advisor |
| EVAL-DOM-3 | Judge Design | LLM-as-judge rubric: pointwise vs pairwise, scoring scale, bias mitigations, calibration | llm-judge-designer |
| EVAL-DOM-4 | RAG Decomposition | Retrieval-layer vs generation-layer metric decomposition; RAGAS/DeepEval framework | rag-eval-advisor |
| EVAL-DOM-5 | Faithfulness Scope | Non-RAG output groundedness: atomic claim decomposition, Lynx/G-Eval tooling | faithfulness-advisor |
| EVAL-DOM-6 | Safety Cadence | Adversarial taxonomy, red-team tooling, automated gate design, continuous cadence | safety-eval-advisor |
| EVAL-DOM-7 | CI Gate + Online Eval | Trigger conditions, baseline-derived thresholds, drift detection, production feedback loop | eval-ci-advisor |

## Section 2 — Constraint Inputs

These inputs shape every recommendation in this plugin. Map each input to the constraints it drives.

| Input | Drives |
|---|---|
| Application type (RAG Q&A / summarization / conversational / code generation / classification) | Coverage categories (EVAL-DOM-1), default metric set (EVAL-DOM-2), judge criteria rubric (EVAL-DOM-3), adversarial taxonomy scope (EVAL-DOM-6) |
| Risk level (low / medium / high) | Minimum eval set size, faithfulness threshold, safety cadence frequency, human red-team trigger threshold |
| Generator model family (Claude / GPT-4 / Gemini / Llama / etc.) | Judge model family disqualification (EVAL-D-2); determines which provider is excluded |
| Existing human labels (yes / no / partial) | Calibration feasibility (EVAL-D-5); determines whether LLM-as-judge can be deployed to CI immediately |
| RAG presence (yes / no) | Activates rag-eval-advisor (EVAL-DOM-4); disqualifies faithfulness-advisor for primary faithfulness metric |
| Regulatory context (EU AI Act / HIPAA / SOC2 / none) | Compliance cross-link trigger to compliance-companion; may increase eval set size and safety cadence requirements |
| CI system (GitHub Actions / GitLab CI / Jenkins / CircleCI / other) | CI gate integration pattern and output format recommendation |
| Deployment context (internal / consumer-facing / regulated / autonomous agent) | Adversarial taxonomy scope, safety cadence, online eval sampling rate |

## Section 3 — Opinionated Defaults

Lead with these defaults in every advisory. These are the recommended starting points — overridable with documented justification. Never present a neutral menu without a recommendation.

**RAG Q&A:**
- Eval set: minimum 200 examples (higher risk from retrieval failure modes); 80/20 split
- Primary metrics: faithfulness, context_relevancy, answer_relevance (max 3)
- Judge scale: binary (0/1) for faithfulness; 3-point for answer quality
- Safety cadence: quarterly automated + pre-deployment for any retrieval index change
- CI threshold method: baseline-derived (EVAL-D-8); re-baseline on every index version bump

**LLM Summarization:**
- Eval set: minimum 100 examples; 80/20 split
- Primary metrics: faithfulness (Lynx/NLI), completeness (LLM judge), conciseness (LLM judge)
- Judge scale: 3-point (1 = hallucination present; 2 = acceptable with gaps; 3 = fully faithful + complete)
- Safety cadence: semi-annual automated; human review on model change
- CI threshold method: baseline-derived; flag any faithfulness regression >5 points

**Conversational Agent:**
- Eval set: minimum 150 examples (multi-turn); multi-turn sessions counted as single examples
- Primary metrics: goal completion (task success), persona adherence (LLM judge), refusal accuracy
- Judge scale: binary for refusal accuracy; 3-point for goal completion
- Safety cadence: quarterly automated (higher surface area for jailbreak via conversation)
- CI threshold method: baseline-derived; treat any new refusal failure as CI blocker

**Code Generation:**
- Eval set: minimum 100 examples; 80/20 split; include security-sensitive category
- Primary metrics: test-pass-rate (deterministic), security violation rate (static analysis), semantic correctness (LLM judge)
- Judge scale: binary for security; 3-point for semantic correctness
- Safety cadence: every release for security eval; quarterly for adversarial code injection
- CI threshold method: baseline-derived; zero tolerance for security violations

**Classification:**
- Eval set: minimum 100 examples per class; stratified sampling required
- Primary metrics: accuracy, F1 (macro-averaged), boundary-class precision
- Judge: prefer deterministic metrics (exact match against reference labels); LLM-as-judge only for ambiguous boundary cases
- Safety cadence: annual; increase to quarterly for bias-sensitive classification domains
- CI threshold method: baseline-derived; alert on any per-class F1 regression

## Section 4 — Derivation Rules

Eight hard constraints that govern all recommendations in this plugin. MUST/NEVER language — these are not suggestions. Every recommendation that touches these domains MUST cite the applicable rule.

**EVAL-D-1: Golden dataset MUST be held out from prompt engineering workflows.**
Any example used in prompt iteration, few-shot selection, or instruction tuning is permanently disqualified from the eval set. Maintain an exclusion list. Leakage invalidates the entire evaluation baseline.

**EVAL-D-2: Judge model MUST differ from generator model family.**
Self-preference bias is documented and consistent: a model family systematically rates its own outputs higher. The judge model provider MUST differ from the generator model provider. Name the disqualified family explicitly in every recommendation.

**EVAL-D-3: Judge scoring scale MUST NOT exceed 3 points (binary or 1–3).**
Fine-grained scales (0–100, 1–10, 1–5 Likert) produce inconsistent inter-rater agreement from LLM judges. Inter-rater reliability collapses above 3 points. Binary and 3-point scales are the only permitted judge scoring formats.

**EVAL-D-4: RAG eval MUST decompose retrieval and generation metrics separately.**
End-to-end-only evaluation obscures which component is failing. Retrieval failure and generation failure present identically in an end-to-end metric. Separate instrumentation at each pipeline stage is required.

**EVAL-D-5: LLM-as-judge MUST be calibrated against human labels before CI use.**
Deploying an uncalibrated judge to CI risks false-passing or false-blocking every build. Human labels MUST be collected first; judge-human agreement (Cohen's kappa ≥0.7 for binary, ≥0.65 for 3-point) MUST be confirmed before the judge gates any release.

**EVAL-D-6: Safety evaluation MUST run continuously each release cycle, not one-time.**
Adversarial techniques evolve after deployment. A one-time pre-launch safety gate is a snapshot, not a program. Safety eval MUST be triggered on every release; human red-team cadence is additive, not a replacement.

**EVAL-D-7: Offline eval set MUST NOT contain fewer than 100 examples without documented justification.**
Statistical confidence for metric comparisons requires ≥100 examples for most significance tests (α=0.05). Smaller sets produce wide confidence intervals that mask regressions. If a constraint forces fewer than 100 examples, the constraint MUST be documented, and the team MUST accept the stated statistical risk.

**EVAL-D-8: CI gate threshold MUST be derived from baseline, not set arbitrarily.**
Arbitrary thresholds (e.g. "faithfulness ≥ 0.80") may always pass or always block depending on the actual model performance. The procedure: (1) measure current performance, (2) set threshold at (baseline − acceptable_degradation_margin), (3) document baseline value, margin, and measurement date.

## Section 5 — Recommendation Output Contract

Every recommendation produced by any ai-eval-companion advisory agent MUST carry all four components:

1. **Chosen value** — the specific recommendation (metric name, scale, tool, threshold method, cadence)
2. **Rule citation** — the EVAL-D-* rule or domain (EVAL-DOM-*) that drives this choice
3. **Named alternative** — at least one alternative recommendation with the condition under which it is preferred ("prefer X when Y")
4. **Override hook** — an explicit statement that the recommendation is overridable, naming what must be documented if the user overrides it

Example output contract pattern:
```
Recommendation: Use RAGAS context_relevancy as the primary retrieval metric. (EVAL-D-4: retrieval metrics MUST be measured separately from generation.)
Alternative: Use MRR@K if your retrieval pipeline is ranked and you need position-weighted evaluation.
Override: If neither applies, document the constraint and the chosen metric substitution.
```

## Section 6 — Enforcement Handoff

Maps each EVAL-D-* derivation rule to the responsible agent and enforcement pre-conditions.

| Rule | Responsible Agent | Enforcement Point |
|---|---|---|
| EVAL-D-1 (dataset anti-leakage) | eval-dataset-designer | Anti-leakage rules section in advisory; flagged in eval plan |
| EVAL-D-2 (judge ≠ generator family) | llm-judge-designer | Judge model selection section; explicit disqualification statement |
| EVAL-D-3 (scale ≤ 3 points) | llm-judge-designer | Scoring scale selection; STOP if user proposes 0–100 or Likert |
| EVAL-D-4 (RAG decomposition) | rag-eval-advisor | Separate retrieval + generation sections; STOP if conflated |
| EVAL-D-5 (calibration before CI) | llm-judge-designer, eval-ci-advisor | Calibration workflow required before CI gate design |
| EVAL-D-6 (continuous safety cadence) | safety-eval-advisor | Cadence section; reject one-time safety plans |
| EVAL-D-7 (≥100 examples) | eval-dataset-designer | Size recommendation; document any exception |
| EVAL-D-8 (baseline-derived thresholds) | eval-ci-advisor | Threshold derivation procedure; STOP if arbitrary |

**Enforcement pre-conditions (PII, cost gate, audit) → baseline-enforcer skill (slug: baseline-enforcer)**

Every advisory agent in this plugin imports the baseline-enforcer skill at session start. baseline-enforcer enforces: PII scrub before output, cost gate before Opus calls (llm-judge-designer and safety-eval-advisor), and audit trail logging after every invocation. These are non-negotiable enforcement pre-conditions for all EVAL-D-* rule outputs.
