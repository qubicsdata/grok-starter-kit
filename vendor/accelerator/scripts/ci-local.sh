#!/usr/bin/env bash
# scripts/ci-local.sh: the accelerator fleet gate as one command, with a fixed log path.
# This repository has no GitHub Actions workflows; `tools/validate.sh` is the CI gate.
#
# Stages: trusted interpreter (/usr/bin/python3, root-owned, >= 3.9); tools/run-unit-tests.py;
#   tools/validate.sh (all fleet validators); generated files match HEAD (gen-registry.py + gen-readme.py,
#   then nothing may differ from HEAD); clean tree (the checkout must be clean before and after the run,
#   untracked files included, `git status` must succeed and HEAD must not move).
#   Every stage except the clean-tree check runs in a throwaway `git clone --no-hardlinks` of HEAD in a
#   private temp dir, because validate.sh and the generators rewrite README.md and registry.json in place:
#   the checkout under test is never written. Results therefore describe the HEAD commit.
# --quick skips tools/validate.sh (unit tests, generated files and clean tree still run).
# --root DIR: checkout to test (default: the repository containing this script). It must be the top of a
#   git work tree with the accelerator layout (tools/validate.sh, tools/gen-readme.py, ...); else exit 2.
# Log: $CI_LOCAL_LOG_DIR (default ~/.local/state/ci-local/accelerator)/<profile>-<sha12>.log, symlink
#   latest-<profile>.log, <profile>-<sha12>.summary.json. The log dir must be a real directory owned by you
#   and not writable by group/others (a new one is created 0700); files are 0600.
# Offline (stdlib Python only); never pushes or publishes.
# Exit 0 only if every stage passed; 1 if a stage failed; 2 on a usage or setup error.
set -uo pipefail
export PYTHONDONTWRITEBYTECODE=1 GIT_OPTIONAL_LOCKS=0
die() { echo "ci-local: $*" >&2; exit 2; }

here=$(cd "$(dirname "$0")/.." 2>/dev/null && pwd -P) || die "cannot resolve the repository containing $0"
root=$here profile=default
while [ $# -gt 0 ]; do
  case "$1" in
    --quick) profile=quick ;;
    --root) { [ $# -ge 2 ] && [ -n "$2" ]; } || die "--root needs a directory"; root=$2; shift ;;
    -h|--help) sed -n '2,19p' "$0"; exit 0 ;;
    *) die "unknown option $1" ;;
  esac; shift
done
[ -d "$root" ] || die "root $root is not a directory"
root=$(cd "$root" 2>/dev/null && pwd -P) || die "cannot enter root $root"
top=$(git -C "$root" rev-parse --show-toplevel 2>/dev/null) || top=""
[ -n "$top" ] && [ "$top" = "$root" ] || die "root $root is not the top of a git work tree"
for f in tools/validate.sh tools/run-unit-tests.py tools/gen-readme.py tools/gen-registry.py; do
  [ -f "$root/$f" ] || die "root $root does not have the accelerator layout (no $f)"
done
sha=$(git -C "$root" rev-parse --verify -q HEAD) || die "root $root has no HEAD commit"
py=/usr/bin/python3

# Log dir and files: no symlinked, foreign-owned or shared-writable dir (trailing slashes are stripped
# first, so "link/" cannot slip past the symlink test); files are created 0600 by mktemp and renamed into
# place, so a symlink planted at a predictable name is replaced, not followed.
logdir=${CI_LOCAL_LOG_DIR:-$HOME/.local/state/ci-local/accelerator}
while [ "${#logdir}" -gt 1 ] && [ "${logdir%/}" != "$logdir" ]; do logdir=${logdir%/}; done
[ -n "$logdir" ] || die "empty log dir"
[ -L "$logdir" ] && die "log dir $logdir is a symlink; refusing"
if [ ! -e "$logdir" ]; then
  mkdir -p "$(dirname "$logdir")" && mkdir -m 700 "$logdir" || die "cannot create log dir $logdir"
fi
{ [ -d "$logdir" ] && [ ! -L "$logdir" ]; } || die "log dir $logdir is not a directory"
[ "$(stat -c %u "$logdir")" = "$(id -u)" ] || die "log dir $logdir is not owned by $(id -un); refusing"
[ $(( 0$(stat -c %a "$logdir") & 022 )) -eq 0 ] || die "log dir $logdir is writable by group/others; refusing"
base="$profile-${sha:0:12}"; log="$logdir/$base.log"; summary="$logdir/$base.summary.json"
tmplog=$(mktemp "$logdir/.$base.log.XXXXXX") || die "cannot create a log file in $logdir"
exec 3>>"$tmplog" || die "cannot open $tmplog"
mv -fT "$tmplog" "$log" || die "cannot rename $tmplog to $log"
tmplink="$logdir/.latest-$profile.$$"
ln -s "$base.log" "$tmplink" && mv -fT "$tmplink" "$logdir/latest-$profile.log" || die "cannot update latest-$profile.log"
exec > >(tee -a /dev/fd/3) 2>&1

porcelain() { git -C "$root" status --porcelain --untracked-files=all 2>&1; }
echo "ci-local accelerator profile=$profile root=$root sha=$sha log=$log"
before=$(porcelain); before_rc=$?
if [ "$before_rc" -ne 0 ]; then echo "WARNING: git status failed before the gate; the clean tree stage will fail"
elif [ -n "$before" ]; then echo "WARNING: the tree is dirty before the gate; the clean tree stage will fail"; fi

# Throwaway clone of HEAD (private temp dir, own object store, push disabled) where every stage runs.
work=$(mktemp -d "${TMPDIR:-/tmp}/ci-local-accelerator.XXXXXX") || die "cannot create a temp dir"
trap 'rm -rf "$work"' EXIT
trap 'exit 130' INT TERM HUP
clone=$work/repo
{ git clone -q --no-hardlinks --no-checkout "$root" "$clone" \
  && git -C "$clone" remote set-url --push origin NO_PUSH_ci_local \
  && git -C "$clone" -c advice.detachedHead=false checkout -q --detach "$sha"; } >/dev/null 2>&1 \
  || die "cannot make a throwaway clone of $root at $sha"
mkdir "$work/bin" && ln -s "$py" "$work/bin/python3" || die "cannot pin python3 to $py"
export PATH="$work/bin:$PATH"

results=() failed=0
stage() { local name=$1; shift; local t0=$SECONDS; echo; echo "=== [$name] $(date '+%F %T %Z')"
  if ( cd "$clone" && "$@" ); then results+=("ok|$name|$((SECONDS-t0))|"); echo "=== [$name] ok"
  else local rc=$?; results+=("FAIL|$name|$((SECONDS-t0))|exit $rc"); failed=1; echo "=== [$name] FAILED (exit $rc)"; fi; }

interp() { [ -x "$py" ] && [ "$(stat -c %u "$(readlink -f "$py")")" = 0 ] \
  && "$py" -c 'import sys; print(sys.version); sys.exit(sys.version_info < (3, 9))'; }
generated() { local st
  "$py" tools/gen-registry.py > /dev/null && "$py" tools/gen-readme.py > /dev/null || return 1
  st=$(git status --porcelain --untracked-files=all 2>&1) || { echo "git status failed: $st"; return 1; }
  [ -z "$st" ] || { echo "generated output differs from HEAD (regenerate and commit):"; echo "$st"
    git --no-pager diff --stat; return 1; }; }
clean() { local after rc head bad=0
  if [ "$before_rc" -ne 0 ]; then echo "git status failed before the gate (exit $before_rc):"; echo "$before"; bad=1
  elif [ -n "$before" ]; then echo "the tree was dirty before the gate:"; echo "$before"; bad=1; fi
  after=$(porcelain); rc=$?
  if [ "$rc" -ne 0 ]; then echo "git status failed after the gate (exit $rc):"; echo "$after"; bad=1
  elif [ -n "$after" ]; then echo "the tree is dirty after the gate:"; echo "$after"; bad=1; fi
  head=$(git -C "$root" rev-parse --verify -q HEAD) || head="(none)"
  [ "$head" = "$sha" ] || { echo "HEAD moved during the gate: $sha -> $head"; bad=1; }
  return "$bad"; }

stage "trusted interpreter" interp
stage "unit tests (tools/run-unit-tests.py)" "$py" tools/run-unit-tests.py
[ "$profile" = quick ] || stage "fleet gate (tools/validate.sh)" bash tools/validate.sh
# validate.sh regenerates in the clone; reset it so this stage checks the generators from HEAD.
git -C "$clone" reset -q --hard "$sha" && git -C "$clone" clean -qfdx || die "cannot reset the throwaway clone"
stage "generated files match HEAD" generated
stage "clean tree" clean

echo; echo "ci-local summary (accelerator $profile, $sha)"
for r in "${results[@]}"; do IFS='|' read -r st name secs note <<<"$r"
  printf '  %-5s %-40s %5ss %s\n' "$st" "$name" "$secs" "$note"; done
result=$([ "$failed" = 0 ] && echo pass || echo fail)
tmpsum=$(mktemp "$logdir/.$base.summary.json.XXXXXX") || die "cannot create a summary file in $logdir"
"$py" -I -c '
import json, sys
repo, profile, sha, root, finished, result = sys.argv[1:7]
stages = []
for r in sys.argv[7:]:
    st, name, secs, note = r.split("|", 3)
    stages.append({"stage": name, "status": st, "seconds": int(secs), "note": note})
json.dump({"repo": repo, "profile": profile, "sha": sha, "root": root, "finished": finished,
           "stages": stages, "result": result}, sys.stdout)
sys.stdout.write("\n")
' accelerator "$profile" "$sha" "$root" "$(date -Iseconds)" "$result" "${results[@]}" > "$tmpsum" \
  && mv -fT "$tmpsum" "$summary" || die "cannot write summary $summary"
echo "summary=$summary"
[ "$failed" = 0 ] && { echo "ci-local PASSED"; exit 0; }; echo "ci-local FAILED"; exit 1
