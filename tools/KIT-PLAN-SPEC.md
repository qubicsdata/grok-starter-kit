# kit_plan.py: the reference planner (contract)

`tools/kit_plan.py` computes the proposal your Grok Bot shows at every checkpoint of `AGENTS.md` and, after your OK, applies the add-only-if-missing part of it. This file is its contract; the harness in `tests/overwrite/` tests exactly this. Stdlib-only Python 3.9+, no third-party packages.

## Inputs

| Flag | Default | Meaning |
|---|---|---|
| `--kit DIR` | `$KIT_HOME`, else the folder above `tools/` | the kit tree (templates, skills, routines, agent template) |
| `--config PATH` | `$KIT_CONFIG`, `$KIT_HOME/kit.config.yaml`, else the built-in defaults of `kit.config.example.yaml` | your `kit.config.yaml` |
| `--state PATH` | none (an empty setup) | the existing-setup description: a `tests/fixtures/existing-setup/case-*.yaml` file, or a discovered-state JSON with the same keys (`agents`, `skills`, `routines`, `memory`, `files`, `kit_facts`); an `expect` block is ignored. A path that does not exist is a usage error. |
| `--setup-dir DIR` | `$KIT_SETUP_DIR`, else `${HOME}/grok-setup` | where your Grok Bot's items are mirrored as files: `agents/<name>/AGENT.md`, `skills/<name>/SKILL.md`, `routines/<name>.md`, `memory/<slug>.md` |
| `--home DIR` | `$HOME` | the root of the `files:` entries of the state and of the relative keys of `second_brain.marketing_links` |

The second-brain home is `second_brain.home` of the config (`SB_HOME` overrides it, as for `sb`). The planner reads `kit.config.yaml`, the state, the setup dir, the home and the second-brain home. It never reads dot files, `*.env`, credential files or anything outside those places.

An item "exists" when the state names it or the file is present. `existing_setup.mode: fresh` is accepted only when nothing exists; otherwise the planner stops with a usage error.

## Modes

| Invocation | Writes | Exit |
|---|---|---|
| `--dry-run` (the default) | nothing | 0 |
| `--dry-run --json` | nothing; prints the plan as one JSON document | 0 |
| `--apply --approved <sha256>` | only the writing items (below) | 0 |
| `--apply` without `--approved` | nothing | 2 |
| `--apply --approved <other sha>` (the plan changed) | nothing | 3 |
| `--apply` when any planned target already exists | nothing | 4 (in practice a target that appeared turns its item into a `skip`, so the recomputed plan no longer matches and exit 3 comes first; 4 is the write-time guard behind it) |
| bad flags, `--dry-run --apply` together, unreadable config or state, `fresh` on a non-empty setup | nothing | 2 |

The text output (default) prints one `CHECKPOINT <id>: ...` block per checkpoint of `AGENTS.md`, in order, with one line per item, then `plan sha256: <hex>`. It names kit-relative and setup-relative targets only, never absolute paths. `--json` prints only the JSON document.

## The plan document

```json
{
  "kit_plan": 1,
  "mode": "dry-run",
  "checkpoints": ["1", "2", "3", "3b", "4", "5a", "5b", "6", "7", "8a", "8b", "9a", "9b", "10"],
  "items": [ ... ],
  "sha256": "<sha256 of the canonical items>"
}
```

`checkpoints` lists every checkpoint id of `AGENTS.md` once, in document order (the planner reads them from `AGENTS.md`). `sha256` is `sha256(json.dumps(items, sort_keys=True, separators=(",", ":"), ensure_ascii=False))`: the hash your Grok Bot quotes back with `--approved`. Two dry runs on the same state give the same items and hash; any change of the state changes the hash.

### Items

Every item has: `id` (unique, stable, e.g. `skill.add.sb-lookup-kit`), `type`, `kind`, `root`, `target`, `reason` (non-empty) and `checkpoint` (an id from `AGENTS.md`).

| Field | Values |
|---|---|
| `type` | `add` (new, only if missing), `extend` (hers stays, the kit's steps are proposed as additions), `merge` (the kit's sections into her routine), `link` (a link note pointing at her file), `skip` (nothing to do, with the reason), `report` (information for her: doctor findings, a contradiction) |
| `kind` | `folder`, `note`, `router`, `config`, `state_note`, `skill`, `routine`, `agent`, `memory`, `doctor`, `plugin`, `folio`, `runner` |
| `root` | `sb` (second-brain home), `setup` (the setup dir), `home` (her files), `kit` (the kit folder: `kit.config.yaml`, `runner.config`) |
| `target` | a path relative to the root; folders end with `/` |

Type-specific fields:

| Type / kind | Fields |
|---|---|
| `add` skill, routine, agent, note, router | `name`; `source` = the kit file it is created from (kit-relative) |
| `add` routine | `enabled: false` always; enabling is a separate `report` item at 5b / 8b |
| `add` memory | `fact`; target `memory/<slug>.md` (slug = lower case, non-alphanumerics to `-`) |
| `extend` skill | `name`, `additions` (the kit steps proposed, non-empty) |
| `extend` agent | `name`, `add_skills`, `add_routines` |
| `merge` routine | `into` (her routine), `sections` (non-empty) |
| `link` note | `links_to` = her file (home-relative); target `<campaigns folder>/<stem>.link.md` under `sb` |
| `skip` memory | `fact`, reason starts with `duplicate` |
| `report` memory | `fact` (the kit's), `contradicts` (hers), reason names the contradiction |
| `report` doctor | `findings: [{"path": "<her note>", "check": <n>}]`, checkpoint 3, always exactly one item: FAIL-level findings of `sb --doctor` (run in-process on the second-brain home with her `second_brain` settings) whose path is an existing note file; a missing router file or router path is not a finding on her notes and is left out. With `second_brain.name_hashes` entries the planner first reads her scan key as `sb` does (`read_scan_key`, `$XDG_CONFIG_HOME/grok-kit/scan.key` else `$HOME/.config/grok-kit/scan.key`) and passes it to the doctor only, never into the plan; a missing or unusable key fails closed: no findings, and the reason ends with `(sb --doctor could not run: ScanKeyError)`. Without `name_hashes` the key is never read |
| `link` note | also `channel`: the channel of the mapped kit folder (`second_brain.path_defaults`, else its first folder), written into the link note's front matter |

### Choices

When one decision has two options (a skill name clash: extend hers or add with `kit.collision_suffix`; a coding agent: extend it or create `dev-lead` under a free name) both items carry the same `choice` group name (e.g. `skill:sb-lookup`, `agent:dev-lead`) and so do the items that only make sense with one option (the skills a created agent needs, its sizing routine): those carry `option` = the id of the option they belong to. `--apply` never writes an item that carries `choice`; `--choose <group>=<item id>` selects one option (an unknown group or an id that is not an option of it is a usage error, exit 2), and only then are that option's writing items (the option itself and its `option` dependants) applied. The sizing routine of an extended agent and the skills it gains are part of the extend option (`add_routines`, `add_skills`) and are added by her Grok Bot, not by the planner. The skills of a created `dev-lead` are sourced from `agents/dev-lead/skills/<name>/SKILL.md` when the kit ships them; a skill she already has is a `skip`.

Memory facts are planned at checkpoint 4 (with the skills): the kit's facts are the `kit_facts` of the state (none by default); hers are the state's `memory` plus `memory/*.md` of the setup dir (first line). Nothing of the kit's own text is ever treated as a fact.

### Detection rules (what the state must say)

| Hers | The kit's item | Rule |
|---|---|---|
| a daily summary routine: the one `routines.morning_brief.merge_into` names, otherwise the first (by name) whose name or schedule holds a word starting with daily, morning, brief or summar; a routine named `*sizing*` or `*keep-alive*` never counts, and a bare `HH:MM` time is not enough | morning brief | `merge` into it; no `add` of `routines.morning_brief.name` |
| a routine named `dev-lead-sizing` | the sizing routine | `skip` at 8a; the 8b enable `report` names hers, never a suffixed name |
| a skill with the kit skill's name | that skill | a choice: `extend` hers / `add` as `<name><collision_suffix>` |
| an agent whose name or role mentions code, dev, website, site, repo or programming (or `agents.dev_lead.extend_existing` names it) | dev-lead | a choice: `extend` it (`add_skills` = the kit's review skills `pr-review`, `repo-health-check` that she lacks; `add_routines` = `dev-lead-sizing`) / `add` `agents.dev_lead.name` under a non-colliding name |
| a memory fact equal to a kit fact after folding (lower case, punctuation and extra spaces dropped) | that fact | `skip` (duplicate) |
| a memory fact that is the kit fact with the negation flipped (`never`, `not`, `no`, `don't`, `doesn't` added or removed) | that fact | `report` (contradiction), never added |
| a file under a `second_brain.marketing_links` key folder | a link note in the mapped kit folder | `link`, never a copy; the link note carries the folder's channel in its front matter and names her path |
| a note of hers that `sb --doctor` flags | nothing | `report` (doctor), her file is never edited |
| an existing folder, note, router, config file | the kit's | `skip` |

Optional phases (7, 8, 9) are planned too: the proposals exist so she can decline them at their checkpoint. Phase 1's note and phase 2's config are the Grok Bot's to write; the planner lists them as `report` or `skip`. Plugin installs, Folio, Backlog.md and the runner config (`root: kit`) are listed but never applied by the planner.

## `--apply`

1. Recompute the plan from the current inputs; stop with exit 3 if its hash differs from `--approved`.
2. Collect the writing items: `add` and `link` items with `root` `sb` or `setup` and no `choice` (or whose choice was made with `--choose`).
3. Check every target first; if any exists (file, folder or symlink), stop with exit 4 having written nothing.
4. Create exactly those files and folders (parents as needed), non-empty, from the kit templates. Nothing else is written; no existing file, agent, skill, routine or memory fact is modified, renamed, moved or deleted; nothing is written into the kit folder.
5. Print `{"mode": "apply", "written": [<item ids>]}` (with `--json`) and exit 0.

A second apply with the same hash refuses (the targets exist). A dry run after an apply lists the applied items as `skip` and has a different hash.

`extend`, `merge`, `report` and `skip` items are never applied by the planner: after the OK your Grok Bot performs the extension or merge itself, within what the proposal showed.
