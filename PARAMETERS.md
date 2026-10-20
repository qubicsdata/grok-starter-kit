# Parameters

Source = the kit file that defines the setting. Existing-setup aware: **detect** (read from your setup first), **reuse-or-extend** (use or extend what you have), **add-only-if-missing** (create only when absent).

| Key | Default | Source | Existing-setup aware | Note |
|---|---|---|---|---|
| `kit.home` (KIT_HOME) | `${HOME}/grok-kit` | `kit.config.example.yaml` | detect | reuse an existing kit folder if found |
| `kit.timezone` (KIT_TZ) | `UTC` | `kit.config.example.yaml` | detect | taken from your Grok Bot's settings |
| `kit.author_name` / `author_email` | `<your-name>` / `you@example.com` | `kit.config.example.yaml` | detect | fills plugin manifests and docs |
| `kit.homepage` | empty | `kit.config.example.yaml` | add-only-if-missing | plugin manifests |
| `kit.collision_suffix` | `-kit` | `kit.config.example.yaml` | detect | applied only on a name clash |
| `existing_setup.mode` | `integrate` | `kit.config.example.yaml` | detect | never overwrite |
| `second_brain.home` (SB_HOME) | `${HOME}/second-brain` | `second-brain/README.md` | reuse-or-extend | point at your existing notes folder |
| `second_brain.router_file` | `ROUTER.md` | `kit.config.example.yaml` | detect | relative to `SB_HOME`; your existing index file if you have one |
| `second_brain.channels` | `dance-school`, `other-activities` | `second-brain/README.md` | detect | your own channel names win |
| `second_brain.roots` / `raw_roots` | `.` / none | `second-brain/bin/` (sb) | reuse-or-extend | add your existing note folders |
| `second_brain.path_defaults` | channel folder -> channel | `second-brain/bin/` (sb) | detect | follows your folder layout |
| `second_brain.name_hashes` | empty | `second-brain/bin/` (sb) | add-only-if-missing | optional; keyed with your local scan key (`~/.config/grok-kit/scan.key`, never in a repo): `sb --init-key`, then `sb --hash-name`; older unkeyed entries must be re-hashed |
| `second_brain.boost_paths` | empty | `second-brain/bin/` (sb) | add-only-if-missing | optional ranking bonus for a few folders |
| `second_brain.doctor.*` | all `true` | `second-brain/DOCTOR-SPEC.md` | add-only-if-missing | strict tag isolation |
| `second_brain.marketing_links` | empty | `kit.config.example.yaml` | detect | links to existing campaigns, never copies |
| `agents.lead.name` | your primary Grok Bot | `AGENTS.md` | detect | never recreated |
| `agents.dev_lead.name` | `dev-lead` | `agents/dev-lead/AGENT.md` | reuse-or-extend | extend your coding agent or add under a free name |
| `agents.dev_lead.enabled` | `false` | `agents/dev-lead/AGENT.md` | add-only-if-missing | created only after your OK |
| `agents.dev_lead.sizing_interval_hours` | `4` | `agents/dev-lead/AGENT.md` | reuse-or-extend | off until enabled |
| `agents.dev_lead.extend_existing` | empty | `agents/dev-lead/AGENT.md` | detect | your coding agent to extend instead of creating one (phase 8) |
| `agents.dev_lead.sizing_enabled` | `false` | `agents/dev-lead/routines/dev-lead-sizing.md` | reuse-or-extend | separate OK to enable; merges into your status routine if you have one |
| `agents.dev_lead.sizing_hours` | `08:00-20:00` | `agents/dev-lead/routines/dev-lead-sizing.md` | detect | your waking hours, in `kit.timezone` |
| `agents.dev_lead.claude_bin_dir` | empty (`claude` already on PATH) | `agents/dev-lead/skills/claude-code-dev-task/SKILL.md` | detect | folder holding `claude`, put first on PATH; no built-in path |
| `skills.*` | `sb-lookup`, `content-calendar-planner`, `comms-template-writer` | `grok-skills/` | reuse-or-extend | extend yours if similar |
| `routines.morning_brief.*` | off, 07:30, quiet when unchanged | `routines/morning-brief.md` | reuse-or-extend | merges into an existing daily summary |
| `accelerator.marketplace_path` | `${KIT_HOME}/vendor/accelerator` | `vendor/accelerator/KIT-README.md` | detect | skip plugins you already have |
| `accelerator.plugins` | `ai-baseline`, `content-companion` | `vendor/accelerator/KIT-README.md` | add-only-if-missing | |
| `accelerator.pricing_table_file` / `model_ids_file` | files in the vendored copy | `vendor/accelerator/` | add-only-if-missing | updatable without code edits |
| `folio.enabled` / `source` / `data_dir` | off / `vendor/folio` / Folio default | `vendor/folio/README.md` | detect | keep an existing Folio install and data |
| `folio.task_sync` | `false` | `vendor/folio/README.md` | add-only-if-missing | |
| `folio.machine_profile` | `none` | `vendor/folio/README.md` | add-only-if-missing | optional channel profile, off |
| `folio.migration_allow_list` | empty (off) | `vendor/folio/README.md` | add-only-if-missing | optional |
| `folio.backlog_version` | `1.53.0` | `EXTERNAL-DEPENDENCIES.md` | detect | keep a newer one only after review |
| `folio.about.attribution` / `website` / `help_url` | empty (not shown) | `vendor/folio/KIT-README.md` | add-only-if-missing | Folio's local config `about` object, written only when set |
| `runner.enabled` | `false` | `runner/DESIGN.md` | add-only-if-missing | separate explicit OK to start |
| `runner.*` paths, `paths.*`, `backlog.queue/state_file/prompt_dir`, `usage.probe_dir` | under `${KIT_HOME}/runner/` | `runner/runner.config.example.json` | detect | no built-in paths |
| `runner.env_file` | empty | `runner/runner.config.example.json` | add-only-if-missing | keep outside the kit |
| `runner.flags_file` / `bash_env_file` | `${KIT_HOME}/runner/...` | `runner/runner.config.example.json` | add-only-if-missing | templates; allow and deny lists |
| `runner.commit_identity` | `<your-name> <you@example.com>` | `runner/runner.config.example.json` | detect | from your git config |
| `runner.mcp_cleanup_pattern` | empty (off) | `runner/runner.config.example.json` | add-only-if-missing | |
| `backlog.max_concurrent` / `fable.max_concurrent` | 3 / 2 | `runner/DESIGN.md` | add-only-if-missing | |
| `policy.total_cap` / `opus_cap` | 4 / 3 | `runner/DESIGN.md` | add-only-if-missing | |
| `backlog.quiet_hours` | 01:00-07:00, `${KIT_TZ}` | `runner/DESIGN.md` | detect | timezone from your settings |
| `backlog.weekly_pacing` | 70% at reset-18h, 75% at reset; Fable 75%, park 80% | `runner/DESIGN.md` | add-only-if-missing | |
| `policy.session.pause_noncritical_pct` | 80 | `runner/DESIGN.md` | add-only-if-missing | |
| `usage.primary_source` / `poll_interval_minutes` / `probe_fallback` | `rate_limit_event` / 30 / `none` | `runner/DESIGN.md` | add-only-if-missing | no screen scraping |
| `policy.overage` / `rate_limit_park_statuses` | disabled / `rejected` | `runner/DESIGN.md` | add-only-if-missing | |
| `backlog.group_limits` | empty | `runner/runner.config.example.json` | add-only-if-missing | |
| `existing_setup.current_state_note` | `${KIT_HOME}/onboarding/current-state.md` | `onboarding/current-state.md` | detect | saved only after checkpoint 1 (`AGENTS.md`) |
| `accelerator.enabled` | `false` | `vendor/accelerator/KIT-README.md` | add-only-if-missing | set after checkpoint 6 |
| `runner.config` | `${KIT_HOME}/runner/router.json` | `runner/runner.config.example.json` | detect | written after checkpoint 9a, with `runner.enabled: false` |
| `runner.refuse_api_key` | `true` | `runner/runner.config.example.json` | add-only-if-missing | the runner never uses an API key; `ANTHROPIC_API_KEY` is refused whatever this says |
| `policy.session.stop_new_pct` | 90 | `runner/DESIGN.md` | add-only-if-missing | session pause 80 / stop new 90 |
| `policy.weekly.*` | 68 / 3, 75 / 1, 80 | `runner/DESIGN.md` | add-only-if-missing | weekly guard: restricted, critical-only, stop new |
| `policy.count_external_claude` | `true` | `runner/runner.config.example.json` | add-only-if-missing | sessions you start by hand count against the caps |
| `usage.probe_method` / `min_probe_spacing_minutes` / `projects_dir` | `print` / 30 / Claude Code's projects folder | `runner/runner.config.example.json` | add-only-if-missing | `claude -p /usage` at most every 30 minutes |
| `backlog.enabled` | `false` | `runner/runner.config.example.json` | add-only-if-missing | the backlog queue starts only with the runner (checkpoint 9b) |
| `backlog.session_max_pct` / `weekly_max_pct` | 80 / 75 | `runner/DESIGN.md` | add-only-if-missing | backlog holds |
| `backlog.guard_preamble` | generic, names `<your-name>` | `runner/runner.config.example.json` | add-only-if-missing | prepended to every backlog job; names you as the approver; empty or missing holds the backlog |
| `models.*` / `routes.*` | empty | `runner/runner.config.example.json` | add-only-if-missing | task type -> model tables, filled at build time |
| `runner.*` `${KIT_HOME}` / `${KIT_TZ}` in `router.json` | env `KIT_HOME` / `KIT_TZ`, else `kit.home` / `kit.timezone`, else tz `UTC` | `runner/DESIGN.md` | detect | unresolved or unknown placeholder = error, never a built-in path |
| `routes` / `models` / `task_type_aliases` / `profiles` | Opus for security, architecture and core work; Sonnet for routine edits and docs; Haiku opt-in; `fable-*` optional | `runner/DESIGN.md` | add-only-if-missing | keep your own routes if you have them |
| `experiments` | `{}` | `runner/runner.config.example.json` | add-only-if-missing | |
| `backlog.reserve_slots` / `reserve_opus` | 1 / 1 | `runner/DESIGN.md` | add-only-if-missing | kept free from backlog jobs |
| `usage.probe_unset_env` | empty | `runner/DESIGN.md` | add-only-if-missing | names only, never values |
| `backlog.weekly_pacing.fable.fresh_minutes` / `stale_near_cap_minutes` / `stale_block_minutes` | 30 / 45 / 90 | `runner/runner.config.example.json` | add-only-if-missing | Fable reading age: normal caps / one Fable job at most / no new Fable starts |
| `backlog.weekly_pacing.fable.near_park_pct` / `usage.near_park_min_probe_spacing_minutes` | 75 / 5 | `runner/runner.config.example.json` | add-only-if-missing | re-probe before each Fable launch from 75%; 5 min is a floor |
| `usage.min_probe_spacing_minutes` | 30 | `runner/runner.config.example.json` | add-only-if-missing | a floor: `/usage` is never probed closer than 30 min, whatever the value |
| `policy.session.stop_new_pct` / `policy.weekly.restricted_pct` / `critical_only_pct` / `stop_new_pct` | 90 / 68 / 75 / 80 | `runner/DESIGN.md` | add-only-if-missing | session stop; weekly guard |
| `policy.heavy_after_reset_minutes` | 60 | `runner/runner.config.example.json` | add-only-if-missing | a non-critical job marked `heavy` starts only in the first 60 min after a reset |
| `policy.early_block_fraction` | 0.4 | `runner/runner.config.example.json` | add-only-if-missing | in the first 40% of the five-hour window Opus jobs go first in the queue, after that the lighter ones do |
| `policy.resume_grace_seconds` | 60 | `runner/runner.config.example.json` | add-only-if-missing | a rate-limit park ends this long after the reset |
| `policy.external_default_family` | `opus` | `runner/runner.config.example.json` | add-only-if-missing | a session you started by hand whose model is unknown counts as Opus |
| `usage.stale_minutes` | 20 | `runner/DESIGN.md` | add-only-if-missing | a `rate_limit_event` younger than this wins over a newer `/usage` reading |
| `usage.window_hours` / `weekly_days` | 5 / 7 | `runner/runner.config.example.json` | add-only-if-missing | the session window and the weekly window |
| `usage.budgets_estimate.five_hour_weighted` / `weekly_weighted` | 60000000 / 600000000 | `runner/DESIGN.md` | add-only-if-missing | weighted-token budgets behind the estimated %; `cr usage calibrate` replaces them |
| `usage.token_weights.*` | input 1.0, output 5.0, cache_read 0.1, cache_creation 1.25 | `runner/DESIGN.md` | add-only-if-missing | weights per token kind for the estimate |
| `usage.model_weights.*` | opus 1.0, sonnet 0.6, haiku 0.2, other 1.0 | `runner/DESIGN.md` | add-only-if-missing | weights per model for the estimate |
| `backlog.priorities` | `P0`, `P1`, `P2` | `runner/DESIGN.md` | add-only-if-missing | only jobs with a listed priority start |
| `backlog.max_attempts` | 2 | `runner/DESIGN.md` | add-only-if-missing | a crashed job is retried while its attempts stay below this; limit hits and errors are not |
| `backlog.require_soak_window` / `soak_reset_within_hours` / `soak_projected_max_pct` | `false` / 24 / 75 | `runner/DESIGN.md` | add-only-if-missing | off by default; when on, backlog jobs start only within 24 h of the weekly reset and while the projected weekly % at the reset stays below 75 |
| `backlog.burn_lookback_hours` | 3 | `runner/runner.config.example.json` | add-only-if-missing | hours of recent use behind the weekly burn rate of the soak projection |
| `default_model` | `opus` | `runner/runner.config.example.json` | add-only-if-missing | used when a route names no model |
| `haiku_opt_in_default` | `false` | `runner/DESIGN.md` | add-only-if-missing | Haiku routes run only with `--allow-haiku` or this set to `true` |
| `subagent_model.default` | `null` | `runner/DESIGN.md` | add-only-if-missing | subagents inherit the session model |
| `profiles_enabled` | `true` | `runner/runner.config.example.json` | add-only-if-missing | routed runs apply their route's `profile` |
| `policy.total_cap` / `opus_cap` / `overage` / `rate_limit_park_statuses` / `session.*`, `policy.weekly.restricted_pct` / `critical_only_pct` / `stop_new_pct`, `usage.primary_source` / `probe_method` / `probe_fallback` / `poll_interval_minutes` / `min_probe_spacing_minutes` / `near_park_min_probe_spacing_minutes`, `backlog.max_concurrent` / `reserve_slots` / `reserve_opus` / `session_max_pct` / `weekly_max_pct` / `quiet_hours.*` / `weekly_pacing.*` / `fable.max_concurrent` (code defaults) | as in the rows above; `backlog.quiet_hours.tz` falls back to `UTC` | `runner/bin/crlib/policy.py` | add-only-if-missing | filled into `router.json` at load time where a key is missing; your values win |
