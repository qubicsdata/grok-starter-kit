# bin/

The runner code: `run-claude.sh` (one headless `claude -p` job), `cr` (the CLI: routing, the run log, usage, the queue and the scheduler) and its library `crlib/`. Every path comes from `router.json` under `${KIT_HOME}`; no path is built in. `run-claude.sh` reads its files through `cr config --tsv`. See `../DESIGN.md`.
