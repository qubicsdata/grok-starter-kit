---
name: claude-code-dev-task
description: >-
  Use this when asked to run a development task with the Claude Code CLI
  on your own box and deliver a branch, PR, and diff summary.
---
# Steps
1. If `agents.dev_lead.claude_bin_dir` is set, put it first on PATH: `export PATH="<claude_bin_dir>:$PATH"` (empty = `claude` is already on your PATH); verify `claude --version` (it is signed in with your own Claude subscription, not an API key).
2. In the target repo: `git fetch`, then create a dedicated worktree and branch per task: `git worktree add ../wt-<slug> -b task/<slug> origin/<default>`.
3. cd into the worktree and run `claude -p "<task>" < /dev/null` with conservative permissions: never read .env, key, or credential files; no unsandboxed or dangerous commands; restrict allowed tools to the worktree.
4. Review the changes; run the project's tests and linters; fix or report failures.
5. Commit on the task branch, push the task branch only, open a PR (draft if tests fail).
6. Deliver: branch name, PR link, diff summary (files, key changes, test results).
7. Never merge, push to main/default, force-push, or delete branches/worktrees/files without explicit user approval.
