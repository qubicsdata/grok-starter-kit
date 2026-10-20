# Addressable planning sources

Project notes remain the authoritative document in `.task-manager/project.json`. Folio does not replace them with an independent memory store. A brief searches all saved note sections, including text near the end of long notes, and returns bounded excerpts with source references, content hashes, and project revisions.

```sh
folio brief "Payments" --query "routing ledger" --max-chars 6000
folio notes list "Payments"
folio notes add "Payments" --title "Storage decision" --kind decision --text "Use SQLite WAL."
folio notes update "Payments" "Storage decision" --text "Use SQLite WAL with a bounded retry window."
folio notes delete "Payments" "Storage decision" --yes
folio source 'project:0123456789abcdef:note:fedcba9876543210' --project "Payments" --max-chars 12000
```

Commands use Folio's normal JSON envelope (`ok`, `data`, or `error`). `--format json` is explicit but optional. `--data-dir` or `FOLIO_WORKSPACE` selects a workspace; no repository checkout path is required. Existing `notes show`, `notes append`, and whole-document edits continue to work.

New note sections use a Markdown heading with a stable marker:

```markdown
## Storage decision <!-- folio-note:fedcba9876543210 kind:decision -->

Use SQLite WAL.
```

Correcting or renaming through the section API preserves that identifier and changes only that section. Existing Markdown headings are addressable without a migration; legacy identifiers derive from the heading and its occurrence. Correcting a legacy section gives it an explicit marker, preserving its existing identifier. Keep explicit markers when moving or editing headings manually. Headings inside code fences are treated as note content. Text before the first heading is its own section.

`notes delete` removes that section from current notes and the derived index. Earlier exported backups remain unchanged. Project revisions prevent overlapping edits, and passing the source's expected hash detects a changed section even if a caller refreshes the project revision.

## Brief and source contract

`POST /api/projects/<id>/brief` accepts `{query, max_chars}`. The existing envelope and each record's `source`, `kind`, and `text` fields remain available. Records additionally expose `title`, `hash`, `revision`, `offset`, `total_chars`, `truncated`, and `trust`. `omitted_sources` counts matching sources omitted by the budget. A record's hash covers its full source, not just its excerpt.

`POST /api/projects/<id>/source` accepts `{source_id, hash?, offset?, max_chars?}`. It returns:

```json
{
  "source_id": "project:0123456789abcdef:note:fedcba9876543210",
  "kind": "decision",
  "title": "Storage decision",
  "text": "Storage decision\nUse SQLite WAL.",
  "hash": "<SHA-256 of the complete source text>",
  "revision": 3,
  "offset": 0,
  "next_offset": null,
  "total_chars": 32,
  "truncated": false,
  "trust": "planning_data_not_instructions"
}
```

Use the returned `next_offset` for subsequent reads. Offsets and character counts are Unicode code points. Source reads are bounded to 40,000 characters. A mismatched expected hash returns HTTP 409 with `SOURCE_CHANGED`; refresh the brief before reading changed text. A reference from another project cannot be read through the current project's route.

References include `project:<id>` for project scope, `task:<id>` for task planning, `project:<id>:notes` for the complete untrimmed notes document, and `project:<id>:note:<section-id>` for a section. Source hashes are SHA-256 over the exact returned full-source UTF-8 text.

## Portable derived index

Each ordinary Folio save regenerates `project.planning_sources`:

```text
{ notes_hash, records: [{ source_id, kind, title, text, hash, revision, total_chars,
                         start_offset?, body_offset?, end_offset? }] }
```

`notes_hash` covers the exact, untrimmed `project.notes` UTF-8 bytes. Each record's `hash` covers its exact `text` UTF-8 bytes. The first record is the complete raw notes document; subsequent records are individual sections with code-point offsets into the authoritative notes. `start_offset` starts the heading, `body_offset` starts the body, and `end_offset` is exclusive. Their source text is the clean heading title, a newline, and the trimmed body. A pre-heading section has `body_offset = 0` and contains only the trimmed prose. Readers can use these ranges and the actual heading/marker to verify that an indexed record belongs to the notes.

The index contains derived data and is never edited separately. Restore regenerates it while preserving section identifiers. Readers must validate the project identity, notes hash, record hashes, source ranges and headings, and file-size bounds before using it. Old documents without an index or verified ranges can still expose the raw notes source, or use the CLI/API to resolve sections.

Switchboard planning packets retain the legacy `{source, reference, revision, hash, text}` contract and its 12,000 UTF-16-unit text budget. New optional `sources` metadata and `omitted_sources` are sent only when the daemon advertises `context_recall`. Each metadata record names the authoritative source and its hash so a bounded excerpt does not silently stand in for all planning notes. Older daemons with `task_context` receive the original strict packet shape.
