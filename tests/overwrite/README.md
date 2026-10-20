# tests/overwrite: the overwrite-protection harness

Applies the kit's reference planner (`tools/kit_plan.py`, contract in `tools/KIT-PLAN-SPEC.md`) to every synthetic existing setup in `tests/fixtures/existing-setup/` and proves that nothing of hers is changed, renamed or deleted, that nothing is created before a checkpoint, and that the proposals are the ones the case expects.

```
python3 -m unittest discover -s tests/overwrite -p 'test_*.py'
python3 tests/overwrite/run_harness.py --existing-dir <folder of case-*.yaml> [--kit <kit copy>]
python3 tests/overwrite/harness_check.py        # dev check: the harness catches a misbehaving planner
```

The folder is not a package on purpose: `tools/ci_local.py` runs it as its own step (`overwrite-harness`), not inside `kit-tests`.

## What one case goes through

1. The case file is read with the harness's own YAML-subset reader (`caseyaml.py`).
2. A temp world is materialized: her files under `home/`, her Grok Bot's agents, skills, routines and memory facts as files under `setup/` (`agents/<n>/AGENT.md`, `skills/<n>/SKILL.md`, `routines/<n>.md`, `memory/<slug>.md`), a second-brain home (`home/` itself when the case holds notes with front matter, otherwise an empty `sb/`), a synthetic `kit.config.yaml` and the case file as `--state`. Every file gets a fixed past mtime.
3. Snapshot: sha256 and mtime of every file, every folder.
4. `--dry-run --json`: the plan must be well formed, match the case's `expect` block exactly, name no existing path as an add or link target, and the snapshot must be identical afterwards (folder mtimes included).
5. `--apply` without `--approved`: exit 2, snapshot identical. With a wrong hash: exit 3, snapshot identical. `--dry-run --apply` together: exit 2.
6. `--apply --approved <hash>`: exit 0; every pre-existing file keeps its bytes and mtime; the new files are exactly the planned add/link files; no new file repeats the bytes of one of hers; options of an undecided choice are not applied; `written` lists the applied item ids.
7. A second apply refuses; an apply after one planned target appeared refuses and writes nothing; a dry run after the apply proposes no further file writes.

| `expect` key | Assertion |
|---|---|
| `routines_created: N` | N `add` items of kind routine at checkpoint 5a |
| `proposals` | `merge/into` -> one routine merge with `sections`, no second routine; `extend/skill` and `add/skill` -> one choice group; `extend/agent` with `add_skills`, `add_routines` and `create/agent` -> one choice group at 8a |
| `unchanged` | every entry under the path identical after dry run and after apply, nothing added inside |
| `copies: 0` | no add item sources one of her files; no new file is a byte copy of hers |
| `link_notes` | exactly these `link` items, each with `links_to` one of her files |
| `added`, `duplicates_added` | memory facts added as `memory/<slug>.md`; duplicates are `skip` items |
| `agents_created_before_ok: 0` | nothing under `setup/agents/` after the dry run; agent creation is a choice |
| `doctor_findings` | one `report` item of kind doctor listing exactly these `(path, check)` pairs, all on her notes |

`test_contract.py` adds synthetic setups the fixtures do not hold: a contradicting memory fact (reported, never added), her own `dev-lead-sizing` on a timed schedule (skipped at 8a, named by the 8b report, never the morning-brief target), the morning-brief merge target (`merge_into` first, then a daily/morning/brief/summary name or schedule, never `*sizing*` or `*keep-alive*`, a bare time is not enough), an empty setup (every kit item is an add, the applied second brain passes `sb --doctor`), the discovered-state JSON input (same plan as the YAML case), `existing_setup.mode: fresh` on a non-empty setup (refused), the text output (every checkpoint and the hash), the help, and `--choose`: choosing the add option of case 03 writes `sb-lookup-kit` and nothing for her skill, choosing extend writes nothing for it, choosing create in case 05 writes the agent and its sizing routine (the items carrying `option` = that option's id), an unknown group or item is a usage error that writes nothing.

## Teeth: `harness_check.py`

`python3 tests/overwrite/harness_check.py` runs the harness against a copy of the kit whose planner was broken one way at a time and expects the named tests to go red: three stubs (`empty`, `toucher`, `creator`, see its docstring) and nine mutants of the real `tools/kit_plan.py`: `overwrite` (apply writes over an existing target), `no-sha` (apply skips the approval hash), `no-suffix` (the collision suffix is dropped), `dup-memory` (a duplicate memory fact is added), `sizing-report` (the 8b enable report names a suffixed sizing routine although she has hers), `bare-time` (any `HH:MM` schedule is a morning-brief target), `no-exclude` (`*sizing*` / `*keep-alive*` routines count as briefs), `no-brief-word` (a daily/morning/brief/summary word no longer counts), `merge-into-last` (a brief-like routine wins over `routines.morning_brief.merge_into`). It prints `KILLED <label>` or `SURVIVED <label>` and exits 0 only when every one is killed. It takes a few minutes and is not a CI step; run it after changing the planner or the harness.

## Target override

`--existing-dir DIR` (or `KIT_OVERWRITE_TARGET`) points the harness at another folder of `case-*.yaml` files; `--kit DIR` (or `KIT_OVERWRITE_KIT`) at another copy of the kit. The default is the fixtures and this kit, which is what `ci_local` runs. Each case still runs in its own temp folder; no test reads a path outside the kit, the case folder and its temp folder.

All data in the cases and in the worlds is synthetic (`example-*` names, placeholder content).
