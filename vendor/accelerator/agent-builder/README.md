# agent-builder

A Claude Code plugin that builds, audits, and publishes other Claude Code agents and skills. Run `/build-agent` to generate a publication-ready plugin from a description, or audit an existing one with a full cognitive review cycle.

## Installation

```bash
/plugin install agent-builder@accelerator
```

## Usage

### Generate a new plugin

```
/build-agent
```

agent-builder interviews you about what you want to build, designs the agent topology, generates all plugin files, runs a self-critique + specialist panel review, and writes the output to disk — publication-ready.

Provide a description up front — `/build-agent` then answer one batched intake form — for
the fastest path: a light-tier build needs ~3 confirmations total (intake form,
scoring, design). Vague or bare invocations fall back to one-question-at-a-time.

### Audit an existing plugin

```
/build-agent path/to/my-plugin
```

Runs the full specialist panel (security, UX, topology) against your existing plugin and produces a scored audit report with prioritised fixes.

### Workshop mode

Choose both generate and audit during the intake interview. agent-builder builds your plugin, then immediately audits the output before writing to disk.

## How it works

```
/build-agent
  └── intake-agent         interview + 3-axis task scoring
  └── knowledge fetch      live Claude API + SDK docs
  └── domain-researcher    web-sourced domain brief (depth scales with stakes)
  └── design-agent         topology, skills, hierarchy
  └── [Gate 1]             structured pre-generation reflection
  └── generate-agent       all plugin files (in context)
  └── critic-agent         RED/GREEN self-critique (risk-tiered: sonnet floor, opus at full)
  └── specialist panel     scaled to review tier (security / + ux + topology at full)
  └── [Gate 2]             pre-publish reflection + block check
  └── publisher-agent      static PIT gate + version check + write to disk
```

## Model routing and review tiers

agent-builder scores your task on scope, ambiguity, and stakes, then derives both the
per-agent model routing and a **review tier** (light / standard / full — see
`ai-baseline/skills/risk-tier-spec.md`). You review and can override both before
anything runs. The critic runs at the tier's model — sonnet at light/standard, opus
at full — and never below sonnet. Mechanical PIT rules are enforced statically at
publish by `tools/check-plugin-static.py` at every tier, so correctness never rests
on an LLM reviewer noticing them. Security-sensitive builds are force-floored to at
least standard tier.

## Self-update

agent-builder checks for a newer version of itself on every `/build-agent` invocation. If an update is available, it surfaces a non-blocking banner. It also fetches the latest Claude API docs and SDK changelog before generating anything, so your plugins are never built on stale knowledge.
