#!/usr/bin/env python3
"""Stdlib smoke tests for the installed-runtime proof chain.

Run: python3 tools/tests/test_installed_runtime.py

Asserts, against the current tree:
  1. tools/check-installed-runtime.py (the CI-grade consumer simulation) exits 0.
  2. The canonical hook self-check (tools/hooks/self_check.py) exits 0.
  3. The shipped self_check copy is byte-identical to the canonical one
     (cheap pre-flight for the drift gate — a diverged self_check would make
     /baseline-init lie to installed consumers).
"""
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent


def _run(script: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(script), *args],
        capture_output=True, text=True, timeout=180, cwd=str(REPO),
    )


def test_checker_passes_against_current_tree():
    script = REPO / "tools" / "check-installed-runtime.py"
    assert script.is_file(), f"missing {script}"
    r = _run(script)
    assert r.returncode == 0, (
        f"check-installed-runtime failed (exit {r.returncode})\n"
        f"stdout:\n{r.stdout[-2000:]}\nstderr:\n{r.stderr[-800:]}"
    )
    assert "PASS" in r.stdout, f"no PASS in output:\n{r.stdout[-2000:]}"


def test_canonical_self_check_passes():
    script = REPO / "tools" / "hooks" / "self_check.py"
    assert script.is_file(), f"missing {script}"
    r = _run(script)
    assert r.returncode == 0, (
        f"self_check failed (exit {r.returncode})\n"
        f"stdout:\n{r.stdout[-2000:]}\nstderr:\n{r.stderr[-800:]}"
    )


def test_shipped_self_check_is_byte_identical():
    canonical = REPO / "tools" / "hooks" / "self_check.py"
    shipped = REPO / "ai-baseline" / "hooks" / "scripts" / "self_check.py"
    assert canonical.is_file(), f"missing {canonical}"
    assert shipped.is_file(), f"missing {shipped}"
    assert canonical.read_bytes() == shipped.read_bytes(), (
        "shipped self_check.py drifted from tools/hooks/self_check.py — "
        "run 'python3 tools/sync-shipped-hooks.py'"
    )


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"PASS {t.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"FAIL {t.__name__}: {e}")
        except Exception as e:
            failed += 1
            print(f"ERROR {t.__name__}: {type(e).__name__}: {e}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    sys.exit(1 if failed else 0)
