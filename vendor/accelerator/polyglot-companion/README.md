# polyglot-companion

Language-specialist depth across 8 languages — Python, Java, Kotlin, Perl, SQL, Go, Rust, C# — so code reviews and spec requirements reflect each language's real idioms, security pitfalls, and conventions instead of generic advice.

## Installation

1. Copy `polyglot-companion/` into your accelerator plugin directory.
2. Ensure `ai-baseline` is installed and active (see Dependencies).
3. The `baseline-enforcer.md` and `audit-trail-agent.md` files are already included verbatim — no separate copy step needed.

## Usage

### Review a file

```
/polyglot-review src/main.py
```

The command detects the language from the file extension, loads the matching pack(s), and returns a structured review with every finding citing its pack rule ID.

### Review a project manifest

```
/polyglot-review go.mod
```

Detects Go from the manifest filename and applies `go-pack` rules.

### Mixed-language repo

```
/polyglot-review src/handler.go,db/schema.sql
```

Both `go-pack` and `sql-pack` are applied; findings are grouped by pack.

### Spec enrichment

When `ai-baseline`'s enrich runner processes a spec that names a covered language, `spec-enricher` automatically adds `[POLY-1]`, `[POLY-2]`, and `[POLY-3]` requirements to the enriched spec output.

## Commands

- `/polyglot-review <path>` — detect language(s) from path, apply matching pack(s), return structured review with rule citations.

## Dependencies

- requires: ai-baseline
