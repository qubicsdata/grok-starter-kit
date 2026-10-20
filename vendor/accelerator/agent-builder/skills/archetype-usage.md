---
name: archetype-usage
description: Rules for incorporating a suggested archetype into generate-agent's output — scaffolds mandatory sections, hard gates, and output contract while domain brief takes precedence
---

## When to Use an Archetype

Read the `### Suggested Archetype` section at the end of the domain brief.

- **High or medium confidence:** Read the suggested archetype file from `archetypes/[name].md` before generating any agent files. Apply the rules below.
- **Low or none confidence:** Proceed without an archetype. Do not force an archetype on a plugin that doesn't match one.

## Rules

### 1. Mandatory Sections Checklist

Read `## Mandatory System Prompt Sections` in the archetype file. Every listed section must appear in the generated primary agent's system prompt. If a section is absent from your planned output, add it.

### 2. Hard Gates — Verbatim

Read `## Critical Hard Gates` in the archetype file. Copy every `DO NOT` and `STOP` rule into the generated primary agent's system prompt exactly as written. Do not paraphrase, condense, or reorder them.

### 3. Output Contract — Verbatim

Read `## Output Contract` in the archetype file. Use the declared output format exactly. Do not invent a different structure.

### 4. Fill Unique Content

Write the actual content of each mandatory section using the domain brief, user constraints, anti-patterns, and domain expertise. The archetype defines the skeleton; the domain brief and user inputs define the substance.

### 5. Domain Brief Overrides Archetype

If the domain brief contradicts an archetype pattern or hard gate, follow the domain brief. Add a note in the generated file:

```
# Note: archetype [name] recommends [X] but domain brief specifies [Y] — following domain brief.
```

## DO NOT

DO NOT copy the archetype's "What This Agent Must Do" section verbatim into the generated agent — it is a checklist for you, not output content. DO NOT apply archetype rules when confidence is low or none.
