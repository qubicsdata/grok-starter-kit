---
name: dev-lead-sizing
description: >-
  Every few hours, size the open dev tasks and check the task worktrees and the
  runner; report only when something changed, is blocked or needs your decision.
enabled: false
starts_work: false
report: on-change
---
# Routine: dev-lead sizing and keep-alive (design)

- Name: `dev-lead-sizing`. Runs as `agents.dev_lead.name` (default `dev-lead`), or as your own coding agent if you chose **Extend** (`agents.dev_lead.extend_existing`).
- Off by default: creating the agent does not enable it. It runs only after a separate OK, which sets `agents.dev_lead.sizing_enabled: true`.
- Schedule: every `agents.dev_lead.sizing_interval_hours` (default 4) within `agents.dev_lead.sizing_hours` (default 08:00-20:00, your waking hours) in `kit.timezone`.
- Reads (read-only):
  1. the open dev tasks (from the lead, from you, and from the runner backlog if the runner is enabled) and their size: S (under 2 h), M (2-8 h), L (over 8 h), each estimate in hours marked ASSUMPTION;
  2. each active task worktree: does it still exist, its branch, uncommitted changes yes or no;
  3. the runner, only if `runner.enabled`: running or not, within its limits (concurrency, quiet hours, usage pacing), parked jobs.
- Compares with its previous report, a short snapshot kept in the agent's own memory (the only thing it writes).
- Reports only on change: a task added, closed or re-sized; a missing worktree; a blocked task; a runner limit reached or a parked job; a decision you need to make.
- Quiet rule: if nothing changed, stay quiet (send nothing).
- Output: at most 8 lines, to the lead (your primary Grok Bot) or to you, never to anyone else. Each line names its evidence (task, worktree, runner status line).
- Never starts work: it does not start, resume or retry a task, create or remove a worktree, start, stop or restart the runner, or change any config. Keep-alive means it checks that things are alive and tells you; it fixes nothing by itself.

## If you already have a sizing, stand-up or status routine
- Your Grok Bot proposes to merge these checks into yours (as added sections) instead of creating a second routine doing the same job, and waits for your OK.
- If a routine of yours is already named `dev-lead-sizing`, yours is reused as it is, even if it does another job: this one is not added, and no second copy is made under `kit.collision_suffix`.

ASSUMPTION: designed from the dev-lead role, not copied from an existing routine.
