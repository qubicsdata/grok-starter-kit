# Sourced by Claude Code before each Bash tool command of a runner job (CLAUDE_ENV_FILE = runner.bash_env_file).
# Generic template: no secrets here, ever. It keeps commands non-interactive and drops credentials from the shell.
export GIT_TERMINAL_PROMPT=0
export GIT_PAGER=cat
export PAGER=cat
unset GH_TOKEN GITHUB_TOKEN NPM_TOKEN AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_SESSION_TOKEN OPENAI_API_KEY
unset ANTHROPIC_AUTH_TOKEN ANTHROPIC_API_KEY
