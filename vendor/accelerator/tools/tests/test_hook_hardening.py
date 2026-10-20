#!/usr/bin/env python3
"""Stdlib tests for hook-substrate hardening: repo-root resolution order,
Python 3.8 annotation compatibility, and atomic state writes.
Run: python3 tools/tests/test_hook_hardening.py"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
HOOK_DIRS = [REPO / "tools" / "hooks", REPO / "ai-baseline" / "hooks" / "scripts"]
sys.path.insert(0, str(REPO / "tools" / "hooks"))

from _hooklib import atomic_write_text, file_lock  # noqa: E402


def test_get_repo_root_prefers_claude_project_dir_over_cwd_git():
    # A hook whose process cwd sits in a DIFFERENT git repo than the session's
    # project dir must still resolve state to $CLAUDE_PROJECT_DIR — otherwise an
    # armed budget in the real project is silently bypassed (cost_gate) and
    # audit/budget writes land in the wrong repo (audit_append).
    base = Path(tempfile.mkdtemp(prefix="root-order-"))
    try:
        proj = base / "proj"
        other = base / "other"
        for d in (proj, other):
            d.mkdir()
            subprocess.run(["git", "init", "-q"], cwd=d, capture_output=True, check=True)
        env = dict(os.environ, CLAUDE_PROJECT_DIR=str(proj))
        r = subprocess.run(
            [sys.executable, "-c",
             "import sys; sys.path.insert(0, sys.argv[1]); "
             "from _hooklib import get_repo_root; print(get_repo_root())",
             str(REPO / "tools" / "hooks")],
            capture_output=True, text=True, cwd=str(other), env=env, timeout=15)
        assert r.returncode == 0, r.stderr
        assert Path(r.stdout.strip()).resolve() == proj.resolve(), r.stdout
    finally:
        shutil.rmtree(base, ignore_errors=True)


def test_cost_gate_denies_from_divergent_cwd():
    # End-to-end: exhausted budget in $CLAUDE_PROJECT_DIR must deny an Opus
    # dispatch even when the shell cwd is inside another git repo (worktree /
    # sibling checkout — README footgun #3 sends users there).
    base = Path(tempfile.mkdtemp(prefix="gate-divergent-"))
    try:
        proj = base / "proj"
        other = base / "other"
        for d in (proj, other):
            d.mkdir()
            subprocess.run(["git", "init", "-q"], cwd=d, capture_output=True, check=True)
        (proj / ".ai-baseline").mkdir()
        (proj / ".ai-baseline" / "budget.json").write_text(
            json.dumps({"limit_usd": 0.10, "spent_usd": 999}), encoding="utf-8")
        payload = json.dumps({"tool_name": "Task",
                              "tool_input": {"model": "opus", "subagent_type": "x"}})
        env = dict(os.environ, CLAUDE_PROJECT_DIR=str(proj))
        r = subprocess.run([sys.executable, str(REPO / "tools" / "hooks" / "cost_gate.py")],
                           input=payload, capture_output=True, text=True,
                           cwd=str(other), env=env, timeout=15)
        assert r.returncode == 0, r.stderr
        assert "deny" in r.stdout, (r.stdout, r.stderr)
    finally:
        shutil.rmtree(base, ignore_errors=True)


# PEP 585 built-in generics (tuple[...]/list[...]/dict[...]/set[...]) and PEP 604
# unions (X | None) in annotations raise at def time on Python 3.8 — the documented
# floor — unless the module has `from __future__ import annotations`.
_PEP585_604 = re.compile(
    r"(?:->\s*|:\s*)(?:tuple|list|dict|set)\[|->\s*[\w.\[\]]+\s*\|\s*|:\s*[\w.\[\]]+\s*\|\s*None")


def test_hooks_have_no_py38_breaking_annotations():
    offenders = []
    for d in HOOK_DIRS:
        for f in sorted(d.glob("*.py")):
            src = f.read_text(encoding="utf-8")
            if "from __future__ import annotations" in src:
                continue
            for i, line in enumerate(src.splitlines(), 1):
                stripped = line.strip()
                if stripped.startswith("#") or not stripped.startswith(("def ", "async def ")):
                    continue
                if _PEP585_604.search(line):
                    offenders.append(f"{f.relative_to(REPO)}:{i}")
    assert not offenders, f"PEP 585/604 annotations without future import (breaks Python 3.8): {offenders}"


def test_atomic_write_text_never_leaves_partial_file():
    tmp = Path(tempfile.mkdtemp(prefix="atomic-"))
    try:
        target = tmp / "budget.json"
        atomic_write_text(target, '{"a": 1}\n')
        assert target.read_text(encoding="utf-8") == '{"a": 1}\n'
        atomic_write_text(target, '{"a": 2}\n')  # overwrite path
        assert target.read_text(encoding="utf-8") == '{"a": 2}\n'
        leftovers = [p for p in tmp.iterdir() if p.name != "budget.json"]
        assert not leftovers, leftovers
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_file_lock_is_reentrant_across_processes():
    # Two sequential acquisitions must both succeed (lock released on exit),
    # and the lock context must not swallow the protected block's effects.
    tmp = Path(tempfile.mkdtemp(prefix="lock-"))
    try:
        lock = tmp / ".lock"
        results = []
        with file_lock(lock):
            results.append(1)
        with file_lock(lock):
            results.append(2)
        assert results == [1, 2]
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


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
