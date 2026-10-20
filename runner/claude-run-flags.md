# Runner flags: allow and deny lists

`bin/run-claude.sh` sources `runner.flags_file` (default `claude-run-flags.sh`, next to this file) and passes the lists verbatim to every `claude -p` run: `--allowedTools` and `--disallowedTools`. It also starts claude without the variables in `CLAUDE_UNSET_ENV`, and points `CLAUDE_ENV_FILE` at `runner.bash_env_file` (`claude-bash-env.sh`), which Claude Code sources before each Bash command.

Edit the lists for your own projects. Keep this page in step with the template: `runner/tests/test_runner.py` compares both lists with the bullets below. Deny rules win over allow rules.

## Disallowed
- `Bash(git push*)`
- `Bash(git commit*)`
- `Bash(git remote*)`
- `Bash(git reset*)`
- `Bash(git checkout*)`
- `Bash(git rebase*)`
- `Bash(gh *)`
- `Bash(curl *)`
- `Bash(wget *)`
- `Bash(sudo *)`
- `Bash(npm publish*)`
- `Bash(backlog browser*)`
- `Bash(env)`
- `Bash(printenv)`
- `Bash(printenv *)`
- `Bash(set)`
- `Bash(export -p*)`
- `Bash(declare)`
- `Bash(typeset*)`
- `Bash(compgen -v*)`
- `Bash(bash -c*)`
- `Bash(sh -c*)`
- `Bash(eval *)`
- `Bash(exec *)`
- `Read(//proc/**)`
- `Read(~/.claude/.credentials*)`
- `Read(~/.ssh/**)`
- `Read(~/.config/gh/**)`
- `Read(**/.env*)`

## Allowed
- `Read`
- `Edit`
- `Write`
- `Glob`
- `Grep`
- `Bash(ls*)`
- `Bash(wc *)`
- `Bash(git status*)`
- `Bash(git diff*)`
- `Bash(git log*)`
- `Bash(git show*)`
- `Bash(python3 *)`
- `Bash(pnpm test*)`
- `Bash(pnpm check*)`
- `Bash(npm test*)`

## Changes
Write a line here when you change a list (date, what, why). The runner makes the job's local commit itself, so `git commit` stays denied inside a job.
