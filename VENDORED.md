# Vendored components

Clean copies: files only, no history, no submodules, no link to any other repository. Each was scrubbed and parameterized before it was copied in.

| Component | Path | Source sha | License | Scrub and changes |
|---|---|---|---|---|
| Claude Code plugin suite ("accelerator") | `vendor/accelerator/` | `7ccfe80ebcf287b1acc35ed6ff5711496cfefa3d` | Apache-2.0 | author and homepage fields from `kit.config.yaml`; session logs, internal docs and benchmarks removed; builder plugin renamed `agent-builder` (`/build-agent`); hook pricing moved to `pricing.json` |
| Planning UI ("Folio") | `vendor/folio/` | `45a8d5934c102d9dd8a61f68f3ec70b8398862f8` | Apache-2.0 (LICENSE and NOTICE kept) | taken only from the cleaned, scanned tree (tracked files; no history); internal and release records, the plan and its reviews and build scripts left out; NOTICE wording per the owner decision; organisation and channel names replaced by generic placeholders (see `vendor/folio/KIT-README.md`); channel profiles optional and off |
| Second-brain search ("sb") and template | `second-brain/` | n/a (non-git source; sha256 7f3fde6211e998fe6123bbaea4b5b70a40f09738f845856ed43297737cd90f9a) | Apache-2.0 | roots, channels and path defaults from config; no built-in names |
| Dev-lead agent template | `agents/dev-lead/` | n/a (non-git source; 5 files, per-file sha256 kept by the maintainer) | Apache-2.0 | generic role; no names, repos or channels |
| Queue runner | `runner/` | `2280b6fd009b84032f80d74d71769809083be45a` | Apache-2.0 | all paths under `${KIT_HOME}`; synthetic fixtures only; screen-scrape path removed |
| Marketing starter | `second-brain/*/marketing/` | n/a (written for this kit; no upstream source) | Apache-2.0 | synthetic examples only |
| Onboarding | `onboarding/`, `AGENTS.md` | n/a (written for this kit; no upstream source) | Apache-2.0 | written for this kit |

## Kit changes to vendored files

Changes made in the kit on top of the scrub above. A re-vendor from the source must re-apply every one of them.

| File | Change |
|---|---|
| `vendor/accelerator/agent-builder/agents/domain-researcher.md` | neutral wording |
| `vendor/accelerator/agent-builder/skills/domain-research-searches.md` | renamed for neutral wording |
| `vendor/accelerator/agent-builder/skills/task-scoring.md` | neutral wording |
| `vendor/accelerator/ai-baseline/skills/model-tier-guide.md` | reference to removed internal notes dropped |
| `vendor/accelerator/ai-baseline/skills/risk-tier-spec.md` | reference to removed internal notes dropped |
| `vendor/accelerator/data-companion/skills/data-modeling-craft.md` | neutral wording |
| `vendor/accelerator/dev-companion/tests/behavioral-scenarios.md` | neutral wording |
| `vendor/accelerator/docs/learnings/2026-06-21-review-cost-learnings.md` | removed: internal notes |
| `vendor/accelerator/docs/learnings/2026-06-22-horizontal-layer-and-aliveness.md` | removed: internal notes |
| `vendor/accelerator/docs/learnings/2026-06-23-flawless-setup-implementation.md` | removed: internal notes |
| `vendor/accelerator/greenfield-project-initializer/skills/stack-selection-craft.md` | neutral wording |
| `vendor/accelerator/legacy-modernizer/skills/modernization-strategy-craft.md` | neutral wording |
| `vendor/accelerator/onboarding-guide/skills/stack-detection/SKILL.md` | neutral wording |
| `vendor/accelerator/onboarding-guide/tests/behavioral-scenarios.md` | sample key in a fake shape secret scanners do not match |
| `vendor/accelerator/ops-companion/agents/monitoring-designer.md` | neutral wording |
| `vendor/accelerator/ops-companion/tests/behavioral-scenarios.md` | sample key in a fake shape secret scanners do not match |
| `vendor/accelerator/performance-companion/agents/regression-gate-advisor.md` | neutral wording |
| `vendor/accelerator/performance-companion/tests/behavioral-scenarios.md` | neutral wording |
| `vendor/accelerator/product-companion/agents/backlog-agent.md` | neutral wording |
| `vendor/accelerator/release-manager/agents/release-orchestrator.md` | neutral wording |
| `vendor/accelerator/tools/check-stray-artifacts.py` | reference to removed internal notes dropped |
| `vendor/accelerator/tools/hooks/README.md` | reference to removed internal notes dropped |
| `vendor/accelerator/tools/validate-plugin.py` | neutral wording |
| vendor/accelerator (5 skill and agent docs) | local wording edits to 5 skill/agent docs after 7ccfe80e; see CHANGELOG |
| `vendor/folio/tests/test_wp8_ollama_url.py` | sample URL joined at run time (see `vendor/folio/KIT-README.md`) |
