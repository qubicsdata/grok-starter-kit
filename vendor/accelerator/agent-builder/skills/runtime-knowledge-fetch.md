---
name: runtime-knowledge-fetch
description: Use once per session before design-agent is invoked — fetches the latest Claude API docs, plugin spec, SDK changelog, and superpowers release notes, then produces a knowledge patch injected into all downstream agents
---

# Runtime Knowledge Fetch

Fetch current documentation before any generation begins. Training data is always stale. The knowledge patch produced here is injected into design-agent, generate-agent, and critic-agent to prevent generating deprecated patterns.

## Sources to Fetch

Use WebFetch for each URL. If a fetch fails, log the failure and continue — do not abort the session.

| Source | URL | What to extract |
|---|---|---|
| Anthropic API docs | https://docs.anthropic.com/en/api/models-overview | Current model IDs, any deprecated model IDs |
| Claude Code plugin spec | https://docs.claude.ai/en/claude-code/plugins | Plugin structure changes, new manifest fields |
| Agent SDK changelog | https://docs.claude.ai/en/api/agent-sdk/overview | Breaking changes in Python/TS SDK |
| Superpowers releases | https://github.com/obra/superpowers/releases/latest | New skills, deprecated skill names |

## Knowledge Patch Format

After fetching, produce a structured patch in this format:

```markdown
## Knowledge Patch — [ISO timestamp]

### Model IDs (current)
- Latest Opus: [id]
- Latest Sonnet: [id]
- Latest Haiku: [id]
- Deprecated since training: [list any deprecated IDs found]

### Model-ID Drift
[present only when the fetch disagrees with tools/model-ids.json]

### Plugin Spec Changes
[List any structural changes, new required fields, or deprecated fields]
[Write "No changes detected" if none found]

### Agent SDK Breaking Changes
[List any breaking changes relevant to Claude Code plugin authors]
[Write "No breaking changes detected" if none found]

### Superpowers Changes
[New skills or deprecated skill names since the installed superpowers version]
[Write "No changes detected" if none found]

### Fetch Failures
[List any URLs that failed to load]
[Write "None" if all fetches succeeded]
```

## Injection Instructions

After producing the patch:
1. Write the patch to the session plan file (`.builder-session.md`) under `## Knowledge Patch`
2. Prepend the patch to the context given to design-agent, generate-agent, and critic-agent
3. Compare the fetched current model IDs against `tools/model-ids.json`. On any
   mismatch, add a `### Model-ID Drift` block to the knowledge patch:
   "tools/model-ids.json is STALE — [newer/deprecated ID list]. Update the file in a
   reviewed commit before building with new IDs." The JSON file is the ONLY routing
   authority; this fetch detects its staleness and NEVER overrides routing.

## STOP

DO NOT skip this step even if the session is a quick audit. Stale API knowledge in the generate or critic step is a guardrail failure. If all fetches fail, note this prominently in the session plan file and warn the user before proceeding.
