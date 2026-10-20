# Overwrite-protection fixtures (synthetic)

Each case describes an invented "existing setup" and what the kit must do. The build's harness applies the kit to each case in a temp folder and checks that no existing file, agent, skill, routine or memory fact was changed, renamed or deleted, and that every proposed change stopped at a checkpoint.

| Case | Existing setup | Expected |
|---|---|---|
| `case-01-has-morning-brief.yaml` | a daily summary routine at 08:00 | no second routine; a merge proposal; nothing changed before OK |
| `case-02-has-campaign-folder.yaml` | campaigns in `my-marketing/campaigns/` | link notes only; no copies; folder untouched |
| `case-03-skill-name-clash.yaml` | a skill named `sb-lookup` | kit skill proposed as `sb-lookup-kit` or as an extension |
| `case-04-duplicate-memory.yaml` | memory fact "never post on Sundays" | fact not duplicated; a contradiction is flagged, not overwritten |
| `case-05-has-coding-agent.yaml` | an agent `example-coder` doing code work | extend-or-create proposal; no new agent before OK; `example-coder` unchanged |
| `case-06-untagged-notes.yaml` | notes without channel tags in `SB_HOME` | doctor reports them; files untouched |

## How your Grok Bot uses the plan at each checkpoint

The same planner that the harness tests, `tools/kit_plan.py`, runs on your box. A case file here has the shape of the current-state description your Grok Bot discovers in phase 1 of `AGENTS.md` (`agents`, `skills`, `routines`, `memory`, `files`, `kit_facts`); the `expect` block is only for the harness.

1. Before a checkpoint: `python3 tools/kit_plan.py --dry-run --state <current-state> --config <kit.config.yaml>` prints one `CHECKPOINT <id>` block per checkpoint and a `plan sha256` line, writing nothing. Your Grok Bot shows you the block of the checkpoint at hand: `add` (new, only if missing), `extend` (yours stays, the kit's steps are proposed as additions), `merge` (the kit's sections into your routine), `link` (a note pointing at your file), `skip` (nothing to do) or `report` (something for you to decide, such as a doctor finding or a contradicting memory fact).
2. A decision with two options (case 03: extend your `sb-lookup` or add `sb-lookup-kit`; case 05: extend your coding agent or create `dev-lead`) shows both items under one choice group. You pick one; nothing of a choice is applied without your pick.
3. After your OK: `python3 tools/kit_plan.py --apply --approved <that sha256> [--choose <group>=<item id>]` creates only the `add` and `link` items of that plan, only where nothing exists yet. It refuses, writing nothing, if the plan changed since you approved it (your setup changed) or if a planned target appeared in the meantime. Extensions, merges and enabling a routine are done by your Grok Bot itself after the OK, within what the proposal showed; the planner never edits, renames, moves or deletes anything of yours.
