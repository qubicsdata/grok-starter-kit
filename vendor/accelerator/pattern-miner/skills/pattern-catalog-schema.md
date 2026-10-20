---
name: pattern-catalog-schema
description: |
  Defines the catalog entry format for a mined pattern. Import before convention-extractor writes any entry, and before pattern-critic evaluates candidates.
---

# Pattern Catalog Schema

## File location

`mined-patterns/<project>.md` at the pattern-miner plugin root.

## Entry format

Each approved pattern is written as a level-3 heading block:

```
### <PATTERN_ID>

**Statement:** <One declarative sentence: what code always does in this project.>

**Scope:** <file | module | layer | project-wide>

**Confidence:** <high | medium>  (high = ≥3 independent evidence locations; medium = 2)

**Evidence:**
- `<relative/path/to/file.ext>:<line>` — <brief note>
- `<relative/path/to/file.ext>:<line>` — <brief note>
- `<relative/path/to/file.ext>:<line>` — <brief note>

**Category:** <naming | structure | architecture | testing | error-handling | dependency>
```

## Pattern ID format

`<PROJECT>-<CATEGORY_ABBREV>-<NNN>`

| Category | Abbreviation |
|---|---|
| naming | NM |
| structure | ST |
| architecture | AR |
| testing | TS |
| error-handling | EH |
| dependency | DP |

Example: `MYAPP-AR-001`

## Confidence rules

| Evidence locations | Confidence |
|---|---|
| ≥ 3 | high |
| 2 | medium |
| < 2 | REJECT — not enough evidence; do not write |

## Catalog file header

Every `mined-patterns/<project>.md` must begin with:

```
# Pattern Catalog — <project>

Mined: <ISO-8601 date>
Plugin: pattern-miner v1.0.0
Status: <active | stale>

---
```

## Hard Gates

**NEVER write an entry with fewer than 2 evidence locations.**
**NEVER omit Statement, Scope, Confidence, Evidence, or Category from any entry.**
**NEVER allow a critic-rejected pattern into the catalog file.**
