# Claude Code queue runner (design)

Optional. **Off by default** (`runner.enabled: false`). It runs queued headless `claude -p` jobs for the dev-lead agent on your own box, with your own Claude login, and paces them so your subscription stays an individual's tool with room for your own interactive use. Read `TERMS-NOTICE.md` first.

## What it does
- Routes a task type to a model (`routes` in the config), queues jobs, and drains them under the caps below.
- Reads usage from the `rate_limit_event` records that every headless run streams (primary), plus `claude -p "/usage"` at most every 30 minutes, run by the scheduler itself. There is no screen scraping and no tmux path (`probe_fallback: none`).
- Refuses to run if `ANTHROPIC_API_KEY` is set, even to an empty value (it is for your own subscription login only). `cr sched` and `bin/run-claude.sh` both check, and the script checks again after sourcing your `env_file`.
- Each job runs in its own git worktree with allow and deny tool lists from `claude-run-flags.sh` (listed in `claude-run-flags.md`). Claude Code sources `claude-bash-env.sh` before each Bash command of a job.
- Backlog jobs start only with a guard preamble (`backlog.guard_preamble`, naming `<your-name>`); an empty one holds the backlog.
- After a finished job with `commit: yes`, it makes one local commit (never a push) as `runner.commit_identity`, else as the repo's own git user. With neither, it skips the commit and logs `commit_skipped` in `logs/scheduler.jsonl`.
- Keeps the safe limits below even in a partial config: `bin/crlib/policy.py` holds them as code defaults, and the loader fills in any key your `router.json` lacks (add-only: a value you set is never changed). The one floor is the `/usage` probe spacing: a config can space probes further apart, never closer than 30 minutes (5 minutes for the Fable near-park re-probe).

## Default policy
| Setting | Default |
|---|---|
| Runner's own sessions (`backlog.max_concurrent`) | 3, of which at most 2 Fable |
| All `claude -p` on the box (`policy.total_cap` / `opus_cap`) | 4 / 3 |
| Kept free from backlog jobs (`backlog.reserve_slots` / `reserve_opus`) | 1 slot / 1 Opus |
| Quiet hours (no new starts; running jobs finish) | 01:00-07:00 in `${KIT_TZ}` |
| Weekly pacing, all models | 70% at reset-18h, 75% at the reset |
| Weekly pacing, Fable | 75% at the reset, park at 80% |
| Session pause (non-critical) | 80% |
| Session stop (nothing new until the reset) | 90% |
| Weekly guard (`policy.weekly`) | 68% cap 3; 75% critical only; 80% nothing new |
| Backlog holds (`backlog.session_max_pct` / `weekly_max_pct`) | session 80% / weekly 75% |
| Fable reading age (`fresh_minutes` / `stale_near_cap_minutes` / `stale_block_minutes`) | 30 / 45 / 90 min |
| Near the Fable park (`near_park_pct`; re-probe spacing) | from 75%; 5 min apart at least |
| Usage source | `rate_limit_event` primary; `/usage` every 30 min at most; no fallback |
| Overage | disabled |
| On a `rejected` status | park until the reset |

## Config keys (all under `${KIT_HOME}`)
See `runner.config.example.json`. It is a complete config: every key the runner reads is there, with the defaults above. Every path the runner uses (logs, queue, pidfile, stop file, output, prompts, probe dir, backlog queue, state and prompt dir, the runner script, the flags file and the bash env file) is a key. The optional `env_file` is empty by default; if you set it, keep it outside the kit and never commit it. If you set it and the file is missing, the runner refuses to start a job.

The config is `CR_CONFIG`, else `${KIT_HOME}/runner/router.json`. The runner fills in the placeholders when it reads the config:
- `${KIT_HOME}` comes from the `KIT_HOME` environment variable, else from `kit.home` in `${KIT_HOME}/kit.config.yaml` (the file next to `runner/`; `${HOME}` and `~` are expanded there). It must be an absolute path.
- `${KIT_TZ}` comes from `KIT_TZ`, else from `kit.timezone`, else `UTC`. An empty `backlog.quiet_hours.tz` also means UTC.

An unknown placeholder, or `${KIT_HOME}` with no value, stops the runner with an error that names the key. It never falls back to a built-in path. The `CR_*` environment overrides still win over the config.

`runner.mcp_cleanup_pattern` is empty by default. If you set it, `run-claude.sh` runs `pkill -f <pattern>` after a job, but only when no other `claude -p` is running. `backlog.group_limits` is `{}` (no limits per group); set e.g. `{"my-repo": 2}` to cap jobs that carry `group: my-repo`. `usage.probe_unset_env` is `[]`: list extra variable names your shell sets (tokens for other tools) that the `/usage` probe should not see; `ANTHROPIC_API_KEY` and `ANTHROPIC_AUTH_TOKEN` are always removed.

## Turning it on (needs your explicit OK)
1. Your Grok Bot shows you the filled config and the terms notice.
2. You reply OK; it sets `runner.enabled: true` and starts the runner.
3. To stop: create the stop file or ask your Grok Bot to stop it.

`cr sched loop` and `cr sched tick` check `runner.enabled` first, before the pidfile, the scheduler log, any `/usage` probe or any start. Only the JSON value `true` turns the runner on; `false`, a missing key, `"true"` or `1` all refuse. `cr sched status` (a dry run without a probe) and `cr sched stop` still work while the runner is off. The scheduler's own `loop()` and the job launcher check it again, so no job process starts while the runner is off, whatever called them.

## One job: `bin/run-claude.sh`
```
run-claude.sh <label> <worktree>                          # CLI default model, --output-format json
run-claude.sh --task-type rebase <label> <worktree>       # routed: --model sonnet --fallback-model opus, stream-json capture
run-claude.sh --task-type security --model sonnet ...     # --model always wins, logged as model_source=override-flag
CLAUDE_ROUTE_MODEL=opus run-claude.sh --task-type docs ...  # env override (override-env); --model beats it
run-claude.sh --task-type log-triage --allow-haiku ...    # Haiku only when opted in (or CLAUDE_ROUTE_ALLOW_HAIKU=1)
CLAUDE_ROUTE_SUBAGENT_MODEL=sonnet run-claude.sh ...      # sets CLAUDE_CODE_SUBAGENT_MODEL for that run
```
`<label>` names the job (letters, digits, `.`, `_`, `-`). The prompt is `PROMPT_FILE`, else `<prompts_dir>/common.md` followed by `<prompts_dir>/<label>.md`. Output goes to `logs/claude-<label>.json` (and `.err`); routed runs also write `logs/streams/<run_id>.jsonl`. An unknown task type exits 2 without starting claude. `bin/cr route --task-type X` shows what a run would get.

## Routing (`routes`, `models`, `task_type_aliases`)
| Model | Effort | Task types |
|---|---|---|
| opus | high | security, implement, review-fix, hard-debug (profile `lean`: the TDD skill stays on) |
| opus | high | architecture, plan, test, test-hardening (`lean_no_superpowers`); pre-review, review (`lean_no_superpowers_keep_review`) |
| opus | CLI default | default |
| opusplan | medium | medium |
| sonnet | medium | refactor, test-hardening-nonsecurity, rebase, rebase-fallout, rename, pr-body, mechanical, docs |
| sonnet (Haiku opt-in) | low | format, log-triage, log-summary (Haiku only with `--allow-haiku` or `haiku_opt_in_default: true`) |
| fable (optional) | high | fable-pre-review (report only), fable-implement, fable-security, fable-refactor |

Aliases for other spellings of a task type: `analysis/docs` -> docs, `feature+tests` -> implement, `test-infra` -> test-hardening-nonsecurity, `metrics` -> log-summary. `--effort` overrides a route's effort. Edit the table to suit your work; `run-claude.sh` reads it on every launch. Use the `fable-*` routes only if your plan includes Fable.

**Fallback** (`--fallback-model`, used when the primary model is overloaded or unavailable, not to save capacity): opus and opusplan -> sonnet, sonnet -> opus, haiku -> sonnet, fable -> opus. With no routing options, no `--model` or `--fallback-model` is passed.

**opusplan when headless:** with `--permission-mode acceptEdits`, opusplan runs on Sonnet; Opus is used only in plan mode. So "medium -> opusplan" means Sonnet for queued jobs. If medium work should get Opus, change that route to `opus`.

**Subagents:** `subagent_model.default` is `null`, so `CLAUDE_CODE_SUBAGENT_MODEL` is not set and subagents without a `model:` field inherit the session model (Opus routes get Opus subagents, Sonnet routes Sonnet ones). An Agent-tool `model` parameter or an agent's own `model:` field still wins. A route may set `subagent_model`.

## Profiles (routed runs only)
A route's profile is passed as `claude --settings '<json>'`, plus `--strict-mcp-config` (no MCP servers in queued jobs):
- `lean`: the `frontend-design` and `playwright` plugins off; `skillListingMaxDescChars: 80`.
- `lean_no_superpowers`: lean, plus the `superpowers` (TDD skill) and `pr-review-toolkit` plugins off.
- `lean_no_superpowers_keep_review`: lean, plus `superpowers` off (`pr-review-toolkit` kept for its reviewer agent).

Turning off a plugin you do not have is harmless; add your own plugins to a profile the same way. Only `enabledPlugins`, `skillListingMaxDescChars`, `promptCacheTtl`, `bashOutputMaxChars` and `autoCompactWindow` may appear in profile settings; `permissions`, `hooks` and `env` are refused. The only extra flags allowed are `--strict-mcp-config` and `--autocompact`.

## Experiments (`experiments`, empty by default)
An experiment adds settings or flags to some routes, e.g. `{"autocompact": {"enabled": false, "flags": ["--autocompact", "200k"], "apply_to": ["implement"]}}`. Turn one on with `enabled: true`, for one run with `--experiment NAME`, or with `CLAUDE_ROUTE_EXPERIMENTS=a,b`. Each run logs its `experiments` in `runs.jsonl`.

## Usage signals
| Signal | Status | Notes |
|---|---|---|
| stream-json `rate_limit_event` | observed, exact; primary | Every routed run streams it: `status` (allowed, allowed_warning, rejected), `resetsAt`, `rateLimitType`, the five-hour and seven-day utilization. The scheduler also reads the live streams of running jobs. A fresh event (< `usage.stale_minutes`) wins over a newer `/usage` reading. |
| `claude -p "/usage"` | observed, to the minute; secondary | A local slash command (no model turn, no cost). The only source of the Fable-only weekly %. Run by the scheduler at most every 30 minutes. A reply that carries model usage is never taken as a reading. |
| result JSON | observed per run | Model usage per model, `is_error`, `api_error_status` and the error text on a limit. No window fields. |
| local session JSONL | inferred | Token counts from `usage.projects_dir`, deduplicated; five-hour blocks never cross an observed reset. Covers this machine only. |
| budgets / estimated % | estimate | `usage.budgets_estimate` in weighted tokens (`token_weights` x `model_weights`); `cr usage calibrate` replaces them from a fresh observed % or a limit hit. |

The reset time is observable (exact from `rate_limit_event`, to the minute from `/usage`); the window start is not, and is taken as reset - 5 h. The weekly window is fixed by its reset, not rolling.

## Scheduler (`cr sched`)
```
bin/cr queue add --task-type implement --cwd <worktree> --prompt-file <prompt.md> [--priority N] [--critical] [--heavy] [--model M] [--label L]
bin/cr queue list
bin/cr sched status            # dry run: what would start and why (never probes)
bin/cr sched tick              # one pass
bin/cr sched loop --interval 60   # the queue runner (single instance via runner.pidfile)
bin/cr sched stop              # stop file + SIGTERM to the runner only; running jobs keep running
bin/cr backlog status          # queue depth, runner pid, running jobs, failures
bin/cr usage status            # observed vs inferred usage (--json for everything)
bin/cr usage poll              # one manual /usage reading
```
Each tick reaps finished jobs (from the `runs.jsonl` finish records), refreshes usage, counts running sessions (its own jobs plus every other `claude -p` on the machine, from a read-only `/proc` scan; an unknown model counts as Opus), then applies `policy`:
- caps: `total_cap` 4 and `opus_cap` 3 over all `claude -p` sessions;
- session: below 80% normal; 80-90% non-critical paused; from 90% nothing new until the reset;
- weekly: below 68% normal; 68-75% cap 3 and non-critical only in the first 60 minutes after a reset; 75-80% critical only, cap 1; from 80% nothing new;
- a `rejected` event (or a limit-error result) parks everything until the reset plus a 60 s grace, then it re-probes and resumes;
- `--heavy` non-critical jobs start only in the first 60 minutes of a window;
- order: critical first, then priority, then window position (early in a window Opus jobs first, late in a window lighter ones), then age.

Parking never kills or signals anything; running jobs finish. A job that ends with a limit hit goes to `queue/failed/` and is not retried (it may have done partial work). The loop reads `router.json` once at start: restart it (`cr sched stop`, then start it again) after a policy change.

## Backlog (`backlog.queue`)
After the main queue (`cr queue add`), each tick reads the backlog queue file (read-only, a small YAML subset) and keeps status in `backlog.state_file` (queued -> running -> done | failed | retry). A backlog job starts only when all of these hold:
- no main-queue job is waiting; one slot and one Opus stay free (`reserve_slots`, `reserve_opus`); at most `max_concurrent` backlog jobs run, at most `fable.max_concurrent` of them on Fable;
- not inside quiet hours; session below `session_max_pct`, weekly below `weekly_max_pct`, no park, and the weekly pacing line allows it;
- the soak window, only if `require_soak_window` is true (off by default): the weekly reset is at most `soak_reset_within_hours` away and the projected weekly % at the reset stays below `soak_projected_max_pct`;
- the job has `status: queued`, a priority listed in `priorities`, `channel: direct`, a `model` other than `none` (no `model:` means: route by task type), every `depends_on` id done, an existing worktree and a prompt at `<prompt_dir>/<id>.md` (or `prompt_file:`).

Before each launch the runner re-reads usage and stops launching on a threshold or a park. A crash (pid gone, no finish record) is retried while `attempts < max_attempts`; limit hits and errors are not. `stack_on: <branch>` fast-forwards the job's worktree onto that branch first (`git merge --ff-only`, local only); if it cannot, the job fails with the reason.

## Weekly pacing and Fable
- **Pacing line** (`backlog.weekly_pacing`): from the week start (reset - 7 d) to `target_pct` at reset - `target_hours_before_reset`, then to `final_pct` at the reset. Ahead of the line by `slack_pct` or more: no new backlog starts; ahead by less: `near_cap`; behind it: full caps. With no usage reading at all, the backlog runs under `near_cap`.
- **Fable reading age:** the Fable-only % comes only from `/usage`. A reading up to 30 minutes old: normal Fable caps; older than 45 minutes: one Fable job at most; older than 90 minutes, a failed probe or no reading: no new Fable starts. Other jobs are not affected.
- **Near the Fable park:** at Fable 75% or more (`near_park_pct`) the runner re-probes `/usage` before each Fable launch, at most every 5 minutes (`usage.near_park_min_probe_spacing_minutes`); a failed re-probe, a stale reading or 80% (`park_pct`) skips that launch.

## Logs (under `paths.logs`)
- `runs.jsonl`: one `start` record (run id, label, task type, model, model source, reason, fallback, effort, profile, experiments) and one `finish` record (rc, is_error, models reported, model usage, last rate-limit status, limit hit) per run.
- `usage.jsonl`: one record per observation (`usage_screen`, `rate_limit_event`, `limit_hit`, `probe_failed`).
- `scheduler.jsonl` (decisions, logged on change), `streams/<run_id>.jsonl`, `usage-calibration.json`.

## Known limits
- Percentages are server-side and true token caps are unknown, so budgets are rough estimates that cover this machine only.
- The `/usage` parser depends on the current output layout. A layout change shows up as `probe_failed`; the runner then uses rate-limit events and estimates, and the Fable % goes stale (no new Fable starts).
- Unrouted runs keep `--output-format json`, so they produce no `rate_limit_event`; use `--stream` or any routing option to capture it.
- Other `claude -p` sessions without `--model` count as Opus.

## Tests that ship with it
Policy defaults, quiet hours blocking new starts, the tmux path disabled even if the config says otherwise, park on `rejected`, the 30-minute probe spacing. `tests/test_policy.py` is the policy contract: the example config and the code defaults equal the table above, a config missing any of them still runs under it, quiet hours follow the configured zone through daylight-saving changes (new starts blocked, running jobs finish and are reaped), no code path can start tmux, `loop()` and the launcher refuse while the runner is off, probes keep their floors, and the terms notice is linked from the setup phases. `tests/k5/` covers the parameterization: placeholders, the `runner.enabled` gate, the `ANTHROPIC_API_KEY` refusal, commit identity, the guard preamble, the config-driven `run-claude.sh`, the routes table and the generic-text rules. All tests use synthetic fixtures (`fixtures/`) and run in a temp `KIT_HOME` with a fake `claude` (`tests/README.md`).
