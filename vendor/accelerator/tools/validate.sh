#!/usr/bin/env bash
# validate.sh — Fleet CI gate.
#
# Runs all hardening validators in sequence:
#   1. check-baseline-drift.py    — baseline file drift
#   2. check-baseline-coverage.py — baseline import coverage
#   3. gen-registry.py (regen)    — regenerate registry.json
#   4. git diff --exit-code registry.json — fail if registry would change
#   5. validate-fleet.py          — all fleet invariants (includes command-name collision check)
#   6. check-scenario-coverage.py — per-plugin scenario counts (≥1 required)
#   7. check-calibration.py       — reviewer calibration (0 false-positives, ≥1 true-positive)
#   8. check-output-hygiene.py    — static pre-review gate self-test (clean:0, buggy:≥4)
#   9. README.md idempotency check — regen + git diff --exit-code README.md
#  10. check-craft-packs.py        — craft packs conform to craft-pack-schema
#  11. check-skill-refs.py         — promoted skills trigger-faced + no stale refs + handoffs resolve
#  20. check-marketplace-parity.py — every plugin dir is exposed in the marketplace manifest
#  12. check-stray-artifacts.py    — plugin dirs contain only legit structure (no leaked build artifacts)
#  13. run-unit-tests.py           — stdlib unit tests for fleet Python tooling (transcript/audit/cost/feedback)
#  14. check-hooks-drift.py        — shipped plugin hooks (ai-baseline/hooks/) byte-identical to tools/hooks/ + hooks.json valid
#  15. check-installed-runtime.py  — shipped ai-baseline hooks exercised end-to-end in a fake consumer repo (installed-runtime proof)
#  16. check-passport.py           — product-companion backlog invariants: DoR/DoD predicates mirror backlog-schema (fixture selftest)
#  17. check-model-ids.py         — model-ids.json ↔ guide ↔ frontmatter ↔ builder-prose lockstep
#  18. check-loop-alive.py        — self-evolution loop theater detector (write-path + publish gate + wire enforced)
#  19. run-scenarios.py --all      — behavioral-scenario static-assertion gate (parses all; MANUAL = needs a live run)
#
# Exits non-zero if any step fails.
#
# Usage:
#   bash tools/validate.sh
#   # or from repo root:
#   ./tools/validate.sh

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

PASS=0
FAIL=0

run_check() {
    local label="$1"
    shift
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  STEP: $label"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    if "$@"; then
        echo "  → PASS: $label"
        PASS=$((PASS + 1))
    else
        echo "  → FAIL: $label"
        FAIL=$((FAIL + 1))
    fi
}

echo "════════════════════════════════════════════════════════════════"
echo "  Fleet CI Gate — $(date -u '+%Y-%m-%dT%H:%M:%SZ')"
echo "════════════════════════════════════════════════════════════════"

# 1. Baseline drift
run_check "check-baseline-drift" python3 tools/check-baseline-drift.py

# 2. Baseline coverage
run_check "check-baseline-coverage" python3 tools/check-baseline-coverage.py

# 3. Regenerate registry.json
run_check "gen-registry (regen)" python3 tools/gen-registry.py

# 4. Registry staleness check
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  STEP: registry.json staleness check"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if git diff --exit-code registry.json > /dev/null 2>&1; then
    echo "  → PASS: registry.json is up-to-date"
    PASS=$((PASS + 1))
else
    echo "  → FAIL: registry.json is stale (commit the regenerated version)"
    git diff --stat registry.json
    FAIL=$((FAIL + 1))
fi

# 5. Fleet validator
run_check "validate-fleet" python3 tools/validate-fleet.py

# 6. Scenario coverage checker
run_check "check-scenario-coverage" python3 tools/check-scenario-coverage.py

# 7. Reviewer calibration checker
run_check "check-calibration" python3 tools/check-calibration.py

# 8. Output-hygiene static gate self-test (calibration)
run_check "check-output-hygiene" python3 tools/check-output-hygiene.py --calibrate

# 9. README.md idempotency check
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  STEP: README.md idempotency check"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
python3 tools/gen-readme.py > /dev/null
if git diff --exit-code README.md > /dev/null 2>&1; then
    echo "  → PASS: README.md is up-to-date (idempotent)"
    PASS=$((PASS + 1))
else
    echo "  → FAIL: README.md is stale — run 'python3 tools/gen-readme.py' and commit"
    git diff --stat README.md
    FAIL=$((FAIL + 1))
fi

# 10. Craft-pack schema conformance
run_check "check-craft-packs" python3 tools/check-craft-packs.py

# 11. Skill-promotion + handoff reference integrity
run_check "check-skill-refs" python3 tools/check-skill-refs.py

# 12. Stray-artifact hygiene (plugin dirs contain only legit structure)
run_check "check-stray-artifacts" python3 tools/check-stray-artifacts.py

# 13. Stdlib unit tests for fleet Python tooling
run_check "run-unit-tests" python3 tools/run-unit-tests.py

# 14. Shipped-hooks drift gate (ai-baseline plugin ships byte-identical copies of tools/hooks/)
run_check "check-hooks-drift" python3 tools/check-hooks-drift.py

# 15. Installed-runtime proof (shipped ai-baseline hooks exercised end-to-end in a fake consumer repo)
run_check "check-installed-runtime" python3 tools/check-installed-runtime.py

# 16. Product-passport invariants checker (deterministic DoR/DoD mirror of backlog-schema, fixture selftest)
run_check "check-passport" python3 tools/check-passport.py --selftest

# 17. Model-ID single source of truth
run_check "check-model-ids" python3 tools/check-model-ids.py

# 18. Self-evolution loop theater detector (write-path works, publish gate enforces, wire present + required)
run_check "check-loop-alive" python3 tools/check-loop-alive.py

# 19. Behavioral-scenario static-assertion gate (the dormant scenario runner, now enforced)
run_check "run-scenarios (static)" python3 tools/run-scenarios.py --all

# 20. Marketplace parity (hand-maintained manifest vs plugin dirs on disk)
run_check "check-marketplace-parity" python3 tools/check-marketplace-parity.py

echo ""
echo "════════════════════════════════════════════════════════════════"
echo "  RESULTS: PASS=$PASS  FAIL=$FAIL"
echo "════════════════════════════════════════════════════════════════"

if [ "$FAIL" -gt 0 ]; then
    echo "  GATE: FAIL"
    exit 1
fi

echo "  GATE: PASS"
exit 0
