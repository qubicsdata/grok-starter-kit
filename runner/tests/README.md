# Runner tests

Run from the kit root: `python3 -B -m unittest discover -s runner/tests -t runner/tests` (CI step `runner-tests`).

## Sandbox (`helpers.py`, fail closed)
- Every `TempEnv` is a fresh temp `KIT_HOME`. Its `runner/router.json` is `runner/runner.config.example.json` plus `fixtures/router_test_overlay.json`. The example is complete; the overlay only adds two synthetic `experiments` (the example ships `{}`). An override is an error, so every test checks the example's own values. `${KIT_HOME}` becomes the temp dir and `${KIT_TZ}` becomes `Etc/GMT-3`. The kit's `claude-run-flags.sh` and `claude-bash-env.sh` are copied to its `runner/` dir.
- Every config path (logs, queue, runner script, pidfile, stop file, out, env/flags/bash-env files, prompts, probe dir, projects dir, backlog queue/state/prompts), every other path-like value and every `CR_*` path override must resolve inside that dir. If one does not, the run aborts (exit 70), on entry and again on exit. The message names the key, never the value. The one exception: `paths.runner`, `runner.script` and `CR_RUNNER` may name the kit's own `bin/run-claude.sh` (compared by real path).
- Process-wide settings: `CR_TEST_NO_REAL_CLAUDE=1`, `CLAUDE_BIN` = `fakebin/claude` (also first on `PATH`), `HOME` inside the sandbox, `TZ=Etc/GMT-3`, git's global and system config ignored, `GIT_*` cleared.
- An audit hook refuses to start any `claude` other than the fake, tmux or kill tools, and git outside a sandbox dir. The kit's own `bin/cr` and `bin/run-claude.sh` (by real path; a copy elsewhere is refused) start only with a sandbox environment:
  - `CR_TEST_NO_REAL_CLAUDE=1` and the fake `CLAUDE_BIN`;
  - `CR_CONFIG` (or, without it, `KIT_HOME`) inside a sandbox dir;
  - every `CR_*` / `CLAUDE_RUN_LOG_DIR` path inside one too.

  Signals are refused, except to the test process's own children.

## Fixtures
Every fixture is generated: `python3 runner/tests/make_synthetic_fixtures.py` (or `--check`). Never add a capture by hand.

## Tests that start the runner
These tests execute `run-claude.sh` or `bin/cr` as a process, inside the sandbox:
- `test_runner.py` (whole module)
- `test_sched.TickTests.test_end_to_end_with_runner_and_fake_claude`
- `test_operating_limits.ProbeCadenceTests.test_usage_loop_cli_retired`
- `test_queue_runner.LoopLifecycleTests` (5 tests; their temp config sets `runner.enabled: true`)
- `test_policy.EnabledGateTests.test_cr_sched_loop_refuses_as_a_process` (the example's `runner.enabled: false`: refused before any start)

None is skipped. `test_sandbox.RunnerScriptTests` checks that, and that `run-claude.sh` refuses `ANTHROPIC_API_KEY` before it reads the config or sources anything.

## Policy suite (`test_policy.py`)
The safe-limits contract: the example config and the code defaults (`bin/crlib/policy.py`) equal the table in `../DESIGN.md`; a config stripped of every policy key still runs under it; quiet hours in non-default `${KIT_TZ}` values (Pacific/Auckland, America/Los_Angeles, both daylight-saving edges) block new starts while running jobs finish and are reaped; no runner code path names tmux and a config saying `tmux` starts no process; `loop()`, the launcher and `cr sched loop` refuse while `runner.enabled` is not `true`; `/usage` probes keep the 30-minute floor (5 minutes for the Fable near-park re-probe) whatever the config says; the terms notice is present and linked; the policy files hold synthetic data only. Timestamps are inline; no fixture file is added.

## Parameterization suite (`k5/`)
`k5/` holds the parameterization tests: the `${KIT_HOME}` / `${KIT_TZ}` loader, the `runner.enabled` gate, commit identity, the guard preamble, MCP cleanup, the config-driven `run-claude.sh`, the routes table and the generic-text rules. It has no `__init__.py`, so this suite does not collect it. It runs as its own CI step, `runner-k5`. See `k5/README.md`. The CI step `runner` also runs the kit's clean-data scan on `runner/` alone.
