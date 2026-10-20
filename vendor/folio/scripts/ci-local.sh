#!/usr/bin/env bash
# scripts/ci-local.sh: Folio's local gate as one command (this repository has no GitHub Actions
# workflows; all verification is local, see README "Check" and docs/distribution.md).
#
# Stages (default): python version (requires-python >= 3.9), unit tests
#   (`python3 -m unittest discover -s tests -v`), JavaScript syntax (`node --check folio/static/app.js`).
# --full adds: browser smoke (`node tests/browser_smoke.mjs`, needs Chrome: CHROME_PATH or
#   /usr/bin/google-chrome). Releases are source only since WP-6: there is no wheel or bundle stage.
# --baseline FILE: a list of test ids (one per line, e.g. "test_x (tests.test_mod.Class.test_x)")
#   that already fail on the default branch. The unit stage then passes only if every failing or
#   erroring test is in FILE, and reports any new one. Without --baseline every failure fails.
# --root DIR: checkout to test (default: this repository).
# Log: $CI_LOCAL_LOG_DIR (default ~/.local/state/ci-local/folio)/<profile>-<sha12>.log, symlink
#   latest-<profile>.log, and <profile>-<sha12>.summary.json. Exit 0 only if every stage passed.
# Offline; never pushes or publishes.
set -uo pipefail
here=$(cd "$(dirname "$0")/.." && pwd)
root=$here profile=default baseline=""
while [ $# -gt 0 ]; do
  case "$1" in
    --full) profile=full ;;
    --root) root=$(cd "$2" && pwd); shift ;;
    --baseline) baseline=$(realpath "$2"); shift ;;
    -h|--help) sed -n '2,20p' "$0"; exit 0 ;;
    *) echo "ci-local: unknown option $1" >&2; exit 2 ;;
  esac; shift
done
py=${CI_LOCAL_PYTHON:-python3}
sha=$(git -C "$root" rev-parse HEAD 2>/dev/null || echo unknown)
logdir=${CI_LOCAL_LOG_DIR:-$HOME/.local/state/ci-local/folio}
mkdir -p "$logdir"
log="$logdir/$profile-${sha:0:12}.log"; summary="$logdir/$profile-${sha:0:12}.summary.json"
ln -sfn "$(basename "$log")" "$logdir/latest-$profile.log"
exec > >(tee "$log") 2>&1
tmp=$(mktemp -d "${TMPDIR:-/tmp}/folio-ci-local.XXXXXX"); trap 'rm -rf "$tmp"' EXIT
results=() failed=0
stage() { local name=$1; shift; local t0=$SECONDS; echo; echo "=== [$name] $(date '+%F %T %Z')"
  if ( cd "$root" && "$@" ); then results+=("ok|$name|$((SECONDS-t0))|"); echo "=== [$name] ok"
  else local rc=$?; results+=("FAIL|$name|$((SECONDS-t0))|exit $rc"); failed=1; echo "=== [$name] FAILED (exit $rc)"; fi; }
skip() { results+=("skip|$1|0|$2"); echo; echo "=== [$1] skipped: $2"; }
echo "ci-local folio profile=$profile root=$root sha=$sha log=$log"

pyver() { "$py" -c 'import sys; print(sys.version); sys.exit(sys.version_info < (3, 9))'; }
unit() {
  "$py" -m unittest discover -s tests -v 2>&1 | tee "$tmp/unit.txt"
  local rc=${PIPESTATUS[0]}
  grep -E '^Ran [0-9]+ tests|^(OK|FAILED)' "$tmp/unit.txt" | tail -2
  [ "$rc" = 0 ] && return 0
  sed -n 's/^\(ERROR\|FAIL\): \(.*\)$/\2/p' "$tmp/unit.txt" | sort -u > "$tmp/failing.txt"
  echo "failing tests:"; sed 's/^/  /' "$tmp/failing.txt"
  [ -n "$baseline" ] || return "$rc"
  local new; new=$(grep -vxF -f <(grep -v '^#' "$baseline" | sed '/^$/d') "$tmp/failing.txt")
  if [ -z "$new" ] && [ -s "$tmp/failing.txt" ]; then echo "all failures are in the baseline $baseline (no new failures)"; return 0; fi
  echo "NEW failures not in $baseline:"; echo "$new" | sed 's/^/  /'; return 1
}
jssyntax() { command -v node >/dev/null || { echo "node not on PATH"; return 1; }; node --check folio/static/app.js; }
browser() { CHROME_PATH=${CHROME_PATH:-/usr/bin/google-chrome} node tests/browser_smoke.mjs; }

stage "python >= 3.9" pyver
stage "unit tests" unit
stage "js syntax" jssyntax
if [ "$profile" = full ]; then
  if [ -n "${CHROME_PATH:-}" ] || [ -x /usr/bin/google-chrome ]; then stage "browser smoke" browser; else skip "browser smoke" "no Chrome"; fi
fi
echo; echo "ci-local summary (folio $profile, $sha)"
{ printf '{"repo":"folio","profile":"%s","sha":"%s","root":"%s","python":"%s","finished":"%s","stages":[' "$profile" "$sha" "$root" "$("$py" -c 'import platform;print(platform.python_version())')" "$(date -Iseconds)"
  sep=""; for r in "${results[@]}"; do IFS='|' read -r st name secs note <<<"$r"
    printf '%s{"stage":"%s","status":"%s","seconds":%s,"note":"%s"}' "$sep" "$name" "$st" "$secs" "$note"; sep=","
    printf '  %-5s %-32s %5ss %s\n' "$st" "$name" "$secs" "$note" >&2; done
  printf '],"result":"%s"}\n' "$([ "$failed" = 0 ] && echo pass || echo fail)"; } > "$summary"
echo "summary=$summary"
[ "$failed" = 0 ] && { echo "ci-local PASSED"; exit 0; }; echo "ci-local FAILED"; exit 1
