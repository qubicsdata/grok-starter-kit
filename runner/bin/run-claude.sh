#!/bin/bash
# usage: run-claude.sh [options] <label> <worktree>   (allow/deny lists: ../claude-run-flags.sh, doc: ../claude-run-flags.md)
# <label> names the job ([A-Za-z0-9._-]): the prompt <prompts_dir>/<label>.md, the logs claude-<label>.json/.err
# options (all optional; with none: CLI default model, --output-format json):
#   --task-type T       pick model from the routes table in router.json
#   --model M           override (wins over --task-type and CLAUDE_ROUTE_MODEL; logged as override)
#   --fallback-model M  passed to claude --fallback-model (default: per-model fallback from router.json when routed)
#   --allow-haiku       opt in to Haiku for trivial task types (format, log-triage, log-summary)
#   --effort E          override the route's --effort (low|medium|high|xhigh|max)
#   --experiment NAME   enable a router.json experiment for this run (autocompact, prompt_cache_ttl); repeatable
#   --run-id ID         id used in logs/runs.jsonl and logs/streams/ID.jsonl
#   --stream            stream-json capture (rate_limit_event -> logs/usage.jsonl) without changing the model
# Routed runs also get the route's --effort, --settings profile (plugins/skill listing) and --strict-mcp-config.
# env: CLAUDE_ROUTE_MODEL (override), CLAUDE_ROUTE_ALLOW_HAIKU=1, CLAUDE_ROUTE_SUBAGENT_MODEL, CLAUDE_ROUTE_EXPERIMENTS=a,b, CLAUDE_RUNNER_STREAM=1
# Every file comes from router.json (CR_CONFIG, else the runner dir of KIT_HOME), read through `cr config --tsv`:
#   runner.env_file (empty = none), runner.flags_file, runner.bash_env_file, runner.prompts_dir, paths.logs and
#   runner.mcp_cleanup_pattern (empty = no process cleanup). Example: KIT_HOME=/home/user/grok-kit
# CLAUDE_ROUTER_DIR (default: the runner dir above this script) and CLAUDE_RUN_LOG_DIR still override.
# Router docs: ../DESIGN.md
set -u
export DISABLE_TELEMETRY=1 DISABLE_ERROR_REPORTING=1 CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1
refuse() { echo "run-claude.sh: $1; not starting claude" >&2; exit "${2:-2}"; }
refuse_api_key() { if [ -n "${ANTHROPIC_API_KEY+x}" ]; then refuse "ANTHROPIC_API_KEY is set (subscription login only)" 99; fi; }
refuse_api_key
if [ "${CR_TEST_NO_REAL_CLAUDE:-0}" = 1 ] && [ -z "${CLAUDE_BIN:-}" ]; then refuse "CR_TEST_NO_REAL_CLAUDE=1 without a fake CLAUDE_BIN" 98; fi
ROUTER_DIR=${CLAUDE_ROUTER_DIR:-$(cd -P "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}
CR=(python3 -I -B "$ROUTER_DIR/bin/cr")  # -B: never write bytecode into the kit tree (-I ignores PYTHON* env)
CFG_TSV=$("${CR[@]}" config --tsv) || refuse "cannot read the runner config"
ENV_FILE=""; FLAGS_FILE=""; BASH_ENV_FILE=""; PROMPTS_DIR=""; CFG_LOGS=""; MCP_PATTERN=""
while IFS=$'\t' read -r key val; do
  case "$key" in
    runner.env_file) ENV_FILE=$val;;
    runner.flags_file) FLAGS_FILE=$val;;
    runner.bash_env_file) BASH_ENV_FILE=$val;;
    runner.prompts_dir) PROMPTS_DIR=$val;;
    paths.logs) CFG_LOGS=$val;;
    runner.mcp_cleanup_pattern) MCP_PATTERN=$val;;
  esac
done <<< "$CFG_TSV"
if [ -n "$ENV_FILE" ]; then
  [ -f "$ENV_FILE" ] || refuse "runner.env_file is set but the file does not exist"
  . "$ENV_FILE"
  refuse_api_key
fi
{ [ -n "$FLAGS_FILE" ] && [ -f "$FLAGS_FILE" ]; } || refuse "runner.flags_file is missing"
. "$FLAGS_FILE"
for arr in CLAUDE_ALLOWED CLAUDE_DISALLOWED CLAUDE_UNSET_ENV; do
  declare -p "$arr" >/dev/null 2>&1 || refuse "runner.flags_file does not define $arr"
done
if [ -n "$BASH_ENV_FILE" ] && [ ! -f "$BASH_ENV_FILE" ]; then refuse "runner.bash_env_file is set but the file does not exist"; fi
LOGS=${CLAUDE_RUN_LOG_DIR:-$CFG_LOGS}
[ -n "$LOGS" ] || refuse "paths.logs is empty"
mkdir -p "$LOGS" || refuse "cannot create paths.logs"
export CR_LOG_DIR="$LOGS"
CLAUDE_BIN=${CLAUDE_BIN:-claude}
if [ "$CLAUDE_BIN" = claude ] && ! command -v claude >/dev/null 2>&1 && command -v npm >/dev/null 2>&1; then
  PATH="$(npm prefix -g)/bin:$PATH"; export PATH  # claude installed with npm -g but not on PATH
fi
TASK_TYPE=""; MODEL=""; FALLBACK=""; EFFORT=""; EXPS=(); ALLOW_HAIKU=0; RUN_ID=""; STREAM=${CLAUDE_RUNNER_STREAM:-0}; ROUTED=0; POS=()
while [ $# -gt 0 ]; do
  case "$1" in
    --task-type) TASK_TYPE=${2:?--task-type needs a value}; ROUTED=1; shift 2;;
    --model) MODEL=${2:?--model needs a value}; ROUTED=1; shift 2;;
    --fallback-model) FALLBACK=${2:?--fallback-model needs a value}; ROUTED=1; shift 2;;
    --allow-haiku) ALLOW_HAIKU=1; ROUTED=1; shift;;
    --effort) EFFORT=${2:?--effort needs a value}; ROUTED=1; shift 2;;
    --experiment) EXPS+=(--experiment "${2:?--experiment needs a value}"); ROUTED=1; shift 2;;
    --run-id) RUN_ID=${2:?--run-id needs a value}; shift 2;;
    --stream) STREAM=1; shift;;
    --) shift; POS+=("$@"); break;;
    --*) echo "run-claude.sh: unknown option $1" >&2; exit 2;;
    *) POS+=("$1"); shift;;
  esac
done
[ "${#POS[@]}" -ge 2 ] || { echo "usage: run-claude.sh [options] <label> <worktree>" >&2; exit 2; }
[ -n "${CLAUDE_ROUTE_MODEL:-}" ] && ROUTED=1
[ -n "${CLAUDE_ROUTE_EXPERIMENTS:-}" ] && ROUTED=1
N=${POS[0]}; WT=${POS[1]}
case "$N" in *[!A-Za-z0-9._-]*|"") echo "run-claude.sh: bad label" >&2; exit 2;; esac
cd "$WT" || exit 1
if [ -n "${PROMPT_FILE:-}" ]; then PROMPT="$(cat "$PROMPT_FILE")"
else
  { [ -f "$PROMPTS_DIR/common.md" ] && [ -f "$PROMPTS_DIR/$N.md" ]; } || refuse "runner.prompts_dir has no common.md and $N.md (or set PROMPT_FILE)"
  PROMPT="$(cat "$PROMPTS_DIR/common.md"; echo; cat "$PROMPTS_DIR/$N.md")"
fi
UNSET=(); for v in ${CLAUDE_UNSET_ENV[@]+"${CLAUDE_UNSET_ENV[@]}"}; do UNSET+=(-u "$v"); done
CLAUDE_ENV=(-u CLAUDE_ENV_FILE); [ -n "$BASH_ENV_FILE" ] && CLAUDE_ENV=("CLAUDE_ENV_FILE=$BASH_ENV_FILE")
RUN_ID=${RUN_ID:-$N-$(date +%Y%m%d-%H%M%S)-$$}
case "$RUN_ID" in *[!A-Za-z0-9._-]*) echo "run-claude.sh: bad --run-id" >&2; exit 2;; esac
MODEL_ARGS=(); SETENV=(); ROUTE_JSON=""
if [ "$ROUTED" = 1 ]; then
  RARGS=(route --tsv); [ -n "$TASK_TYPE" ] && RARGS+=(--task-type "$TASK_TYPE"); [ -n "$MODEL" ] && RARGS+=(--model "$MODEL")
  [ -n "$FALLBACK" ] && RARGS+=(--fallback-model "$FALLBACK"); [ "$ALLOW_HAIKU" = 1 ] && RARGS+=(--allow-haiku)
  [ -n "$EFFORT" ] && RARGS+=(--effort "$EFFORT"); RARGS+=(${EXPS[@]+"${EXPS[@]}"})
  ROUTE_OUT=$("${CR[@]}" "${RARGS[@]}") || { echo "run-claude.sh: routing failed; not starting claude" >&2; exit 2; }
  ROUTE_JSON=""
  while IFS= read -r line; do
    if [ -z "$ROUTE_JSON" ]; then ROUTE_JSON=$line
    elif [ "${line%%$'\t'*}" = ARG ]; then MODEL_ARGS+=("${line#*$'\t'}")
    elif [ "${line%%$'\t'*}" = ENV ]; then
      case "${line#*$'\t'}" in CLAUDE_CODE_SUBAGENT_MODEL=*) SETENV+=("${line#*$'\t'}");; *) echo "run-claude.sh: refusing env from route" >&2; exit 2;; esac
    fi
  done <<< "$ROUTE_OUT"
  [ -n "$ROUTE_JSON" ] || { echo "run-claude.sh: empty route; not starting claude" >&2; exit 2; }
  STREAM=1
fi
if [ "$STREAM" = 1 ]; then
  mkdir -p "$LOGS/streams"; FMT=stream-json; OUT="$LOGS/streams/$RUN_ID.jsonl"; FMT_ARGS=(--output-format stream-json --verbose)
else
  FMT=json; OUT="$LOGS/claude-$N.json"; FMT_ARGS=(--output-format json)
fi
"${CR[@]}" log-start --run-id "$RUN_ID" --label "$N" --cwd "$PWD" --output-format "$FMT" --pid "$$" ${ROUTE_JSON:+--route-json "$ROUTE_JSON"} >/dev/null 2>>"$LOGS/router-errors.log" || true
env ${UNSET[@]+"${UNSET[@]}"} ${SETENV[@]+"${SETENV[@]}"} "${CLAUDE_ENV[@]}" "$CLAUDE_BIN" -p "$PROMPT" "${FMT_ARGS[@]}" --permission-mode acceptEdits \
  ${MODEL_ARGS[@]+"${MODEL_ARGS[@]}"} --allowedTools ${CLAUDE_ALLOWED[@]+"${CLAUDE_ALLOWED[@]}"} \
  --disallowedTools ${CLAUDE_DISALLOWED[@]+"${CLAUDE_DISALLOWED[@]}"} \
  < /dev/null > "$OUT" 2> "$LOGS/claude-$N.err"
RC=$?
"${CR[@]}" log-finish --run-id "$RUN_ID" --rc "$RC" --out "$OUT" --format "$FMT" --json-out "$LOGS/claude-$N.json" >/dev/null 2>>"$LOGS/router-errors.log" \
  || { [ "$FMT" = stream-json ] && grep '"type":"result"' "$OUT" | tail -n 1 > "$LOGS/claude-$N.json"; } || true
# Optional MCP process cleanup (runner.mcp_cleanup_pattern, off by default): only when no other `claude -p` runs.
if [ -n "$MCP_PATTERN" ]; then
  if ! pgrep -f 'claude -p' >/dev/null; then pkill -f "$MCP_PATTERN" || true; else echo "other claude running; MCP cleanup skipped"; fi
fi
echo "claude rc=$RC"
