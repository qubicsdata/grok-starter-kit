# Second brain (template)

A folder of markdown notes plus `sb`, a read-only search tool with a channel filter and a `--doctor` check.

- Location: `${SB_HOME}` (default `${HOME}/second-brain`). If you already keep notes somewhere, point `SB_HOME` there instead and add only the folders you are missing.
- Channels: set in `kit.config.yaml` (`second_brain.channels`). Defaults: `dance-school`, `other-activities`.
- `bin/sb` is the search tool: Python 3 only (3.9 or newer, standard library). ripgrep is optional: `sb` uses `rg` only when it is already installed and gives the same results without it. See `bin/README.md`.
- Doctor rules: see `DOCTOR-SPEC.md`. Run `sb --doctor` after you add or move notes; it prints paths and check numbers only, never a note's content.

## Front matter (every note)

```yaml
---
title: "<short title>"
type: "note | template | schedule | plan | campaign | post | calendar | summary"
id: "N-YYYYMMDD-xxxxxx"
status: "idea | draft | active | template | archived"
owner: "<your-name>"
created: "YYYY-MM-DD"
channel: "<exactly one channel>"
tags: [<the same channel>, <topic tags>]
links: []        # only notes in the same channel
---
```

## Isolation rules

1. Every note has exactly one `channel`, and `tags` contains that channel and no other channel name.
2. The note's folder starts with its channel (`dance-school/...`). Folder and front matter must agree.
3. `links` and `[[...]]` links point only to notes in the same channel. A link is resolved as a path from the notes folder, a path from the note's own folder (`.md` optional) or a unique file name; `[[target|label]]` and `[[target#anchor]]` work too.
4. `sb --channel X` shows only notes tagged X; untagged or mixed notes are withheld and counted.
5. No personal data about students or parents, no bank details, no secrets. These are best-effort guardrails, not a security boundary.
