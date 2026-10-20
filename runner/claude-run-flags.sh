# Allow / deny lists and env scrub list for every claude run of the queue runner (sourced by bin/run-claude.sh).
# Generic template: edit it for your own projects, and keep claude-run-flags.md in step (the tests compare them).
# Deny rules win over allow rules. Backlog jobs stay local: no push, no GitHub, no commits (the runner commits).

CLAUDE_ALLOWED=(
  "Read"
  "Edit"
  "Write"
  "Glob"
  "Grep"
  "Bash(ls*)"
  "Bash(wc *)"
  "Bash(git status*)"
  "Bash(git diff*)"
  "Bash(git log*)"
  "Bash(git show*)"
  "Bash(python3 *)"
  "Bash(pnpm test*)"
  "Bash(pnpm check*)"
  "Bash(npm test*)"
)

CLAUDE_DISALLOWED=(
  "Bash(git push*)"
  "Bash(git commit*)"
  "Bash(git remote*)"
  "Bash(git reset*)"
  "Bash(git checkout*)"
  "Bash(git rebase*)"
  "Bash(gh *)"
  "Bash(curl *)"
  "Bash(wget *)"
  "Bash(sudo *)"
  "Bash(npm publish*)"
  "Bash(backlog browser*)"
  "Bash(env)"
  "Bash(printenv)"
  "Bash(printenv *)"
  "Bash(set)"
  "Bash(export -p*)"
  "Bash(declare)"
  "Bash(typeset*)"
  "Bash(compgen -v*)"
  "Bash(bash -c*)"
  "Bash(sh -c*)"
  "Bash(eval *)"
  "Bash(exec *)"
  "Read(//proc/**)"
  "Read(~/.claude/.credentials*)"
  "Read(~/.ssh/**)"
  "Read(~/.config/gh/**)"
  "Read(**/.env*)"
)

# Removed from claude's environment before it starts (names only; the runner also refuses ANTHROPIC_API_KEY).
CLAUDE_UNSET_ENV=(
  GH_TOKEN
  GITHUB_TOKEN
  NPM_TOKEN
  AWS_ACCESS_KEY_ID
  AWS_SECRET_ACCESS_KEY
  AWS_SESSION_TOKEN
  OPENAI_API_KEY
  ANTHROPIC_AUTH_TOKEN
  ANTHROPIC_API_KEY
)
