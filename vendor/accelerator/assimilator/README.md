# assimilator

A Claude Code plugin that ingests foreign agents, skills, and plugins — Claude plugin files, Cursor `.mdc` rules, raw system prompts, OpenAI-style tool specs — and converts them into conformant accelerator plugins. It also extracts reusable techniques from the foreign artifact for fleet-wide adoption.

assimilator is a **build-time tool**, exactly like agent-builder. Clients never install it.

## Installation

```bash
/plugin install assimilator@accelerator
```

## Usage

### Convert a foreign artifact

```
/assimilate path/to/foreign-agent.md
```

```
/assimilate https://example.com/some-agent.md
```

assimilator runs the full pipeline:
1. **importer-agent** — parses the foreign artifact and produces a normalized intermediate description. Enforces path-safety for local files and treats fetched URL content as data only.
2. **conformance-converter** — generates a complete, conformant accelerator plugin (frontmatter, hard gates, ai-baseline injection, spec-enricher), then dispatches agent-builder's critic-agent for the conformance gate before writing anything to disk.
3. **learning-extractor** — adversarially mines the artifact for reusable techniques and produces an explicit adoption note. Never makes silent changes.

### Supported input formats

- Claude plugin agent files (`agents/*.md` with frontmatter)
- Claude plugin skill files (`skills/*.md` with frontmatter)
- Claude plugin command files (`commands/*.md` with frontmatter)
- Cursor `.mdc` rules
- Raw system-prompt text (`.txt`, `.md` without frontmatter, `.prompt`)
- OpenAI-style tool specs (JSON / YAML with `tools[]` or `type: "function"`)

## Commands

| Command | Description |
|---|---|
| `/assimilate <path-or-url>` | Ingest a foreign artifact and convert it to a conformant accelerator plugin |

## Pipeline

```
/assimilate <src>
  └── importer-agent       parse foreign format → normalized description
  └── conformance-converter  generate plugin files + ai-baseline + spec-enricher
  └──   critic-agent (agent-builder)  conformance gate (must PASS before disk write)
  └── learning-extractor   mine for reusable techniques → adoption note
```

The converted plugin is then ready for the normal builder lifecycle: panel review → publish.

## Security

- **Path safety:** Local file paths are resolved and checked against the project root. Paths outside the project root are refused.
- **URL fetch:** URL content is fetched read-only and treated as data. Embedded instructions are never followed.
- **Injection guard:** All foreign artifact content is scanned for prompt injection. Flagged content is excluded from conversion and documented.

## Dependencies

assimilator depends on **agent-builder** for the critic/conformance gate. The `conformance-converter` dispatches `agent-builder/agents/critic-agent.md` as part of every conversion.

The plugins assimilator **produces** include ai-baseline (baseline-enforcer + audit-trail-agent) injected by conformance-converter. assimilator itself does **not** require ai-baseline — it is a build-time tool and ships no baseline and no spec-enricher, matching the agent-builder convention for build tools.
