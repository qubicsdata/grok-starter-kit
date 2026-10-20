# Runner parameterization tests

They are the contract for parameterizing the runner: every row of the parameterization table (the 19 router paths, identity, guard, time zone, MCP cleanup, group limits), the `runner.enabled` gate, the `ANTHROPIC_API_KEY` refusal, the routes table and the generic-text rules. `test_k5_rows.py` maps each row to its tests.

Run from the kit root: `python3 -B -m unittest discover -s runner/tests/k5 -t runner/tests/k5`. The CI step `runner-k5` runs this suite; a red suite fails the step.

This folder has no `__init__.py`, so the `runner-tests` step (`runner/tests`) does not collect it. Every test uses the runner test sandbox (`../helpers.py`): a temp `KIT_HOME`, the fake `claude`, and the audit hook. `bin/cr` runs in-process, and its start paths are replaced by recorders. `run-claude.sh` runs as a process inside the sandbox, with fake `pgrep` / `pkill` first on `PATH`. Failures are FAILs, never ERRORs.

## The contract, in short
- **Loader** (`crlib/common.load_config`)
  - `${KIT_HOME}` comes from env `KIT_HOME`, else from `kit.home` in `<KIT_HOME>/kit.config.yaml` (next to `runner/router.json`). `${HOME}` and `~` are expanded. The path must be absolute and is normalized.
  - `${KIT_TZ}` comes from env `KIT_TZ`, else `kit.timezone`, else `UTC`.
  - An unknown placeholder, or a `${KIT_HOME}` with no value, raises a `ValueError` that names the key.
  - Without `CR_CONFIG`, the config is `${KIT_HOME}/runner/router.json`.
  - `CR_*` overrides still win.
- **`cr sched loop` / `tick`** refuse before any start (no pidfile, log, probe or launch) in two cases:
  - `runner.enabled` is anything but JSON `true`;
  - `ANTHROPIC_API_KEY` is set, even to an empty value.
  - `status` and `stop` still work.
- **Commit identity**
  - `runner.commit_identity` (`Name <address>`) wins.
  - If it is unset or still the `<your-name>` template, the repo's git config is used.
  - If there is neither, or the value is malformed, no commit is made and `scheduler.jsonl` gets a `commit_skipped` record naming `runner.commit_identity`.
- **Backlog**
  - An empty or missing `guard_preamble` holds the backlog.
  - `group_limits` `{}` caps nothing.
  - A missing or empty `quiet_hours.tz` means UTC.
- **`run-claude.sh`** takes all of these from the config:
  - `env_file`: empty means nothing is sourced; set but missing means refuse;
  - `flags_file`: missing means refuse;
  - `bash_env_file` becomes `CLAUDE_ENV_FILE`;
  - `prompts_dir`;
  - `paths.logs`;
  - `mcp_cleanup_pattern`: empty means no `pkill` at all.

  The router dir defaults to the script's own runner dir. `ANTHROPIC_API_KEY`, including one set by the env file, exits 99 before `claude` starts.
- **Static rules**
  - The runner code holds no absolute paths: only `/home/user` examples in comments, `/dev/null`, `/proc` and `/usage`.
  - No leftovers from the source, no addresses, no built-in git identity, no city time zones.
  - Doc references resolve inside the kit.
  - Generic templates `runner/claude-run-flags.sh` and `runner/claude-bash-env.sh` exist.
- **Generic runner** (`test_k5_generic.py`)
  - The example config holds the routes table: Opus for security, architecture and core work, Sonnet for routine edits and docs, Haiku only when opted in, the `fable-*` routes optional; reasons hold no names, dates or approval notes; `experiments` is `{}`; profiles turn off only public plugins.
  - The example is complete: the scheduler runs on it alone, and the test overlay adds only synthetic experiments.
  - Comments, docstrings and docs hold no approval or rule-change notes, setup dates, work-package words or build job ids; no host-specific env names and no leftover names from the source (checked by digest).
  - The `/usage` probe removes `ANTHROPIC_API_KEY`, `ANTHROPIC_AUTH_TOKEN` and the names in `usage.probe_unset_env`, nothing built in.
