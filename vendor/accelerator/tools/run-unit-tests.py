#!/usr/bin/env python3
"""
run-unit-tests.py — discover and run every stdlib unit test under tools/tests/ (test_*.py).

These guard the fleet's Python tooling (transcript parsing, audit enrichment, cost roll-up,
feedback writer). Each test file is self-contained (no pytest dependency) and exits non-zero
on failure. This runner aggregates them for the fleet gate.

Exit non-zero if any test file fails.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    tests = sorted((REPO_ROOT / "tools" / "tests").glob("test_*.py"))
    if not tests:
        print("run-unit-tests: no test files found")
        return 0
    fails = []
    for t in tests:
        r = subprocess.run([sys.executable, str(t)], capture_output=True, text=True)
        print(f"  {'PASS' if r.returncode == 0 else 'FAIL'}: {t.name}")
        if r.returncode != 0:
            fails.append(t.name)
            sys.stdout.write(r.stdout[-800:])
            sys.stderr.write(r.stderr[-800:])
    print(f"run-unit-tests: {len(tests) - len(fails)}/{len(tests)} test file(s) passed")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
