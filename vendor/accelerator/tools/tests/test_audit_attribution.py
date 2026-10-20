#!/usr/bin/env python3
"""Stdlib tests for audit_append.py attribution fallback (git remote/branch)
and context.json precedence. Run: python3 tools/tests/test_audit_attribution.py"""
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO / "tools" / "hooks"))

from audit_append import apply_attribution, _repo_basename  # noqa: E402


def _git_fixture(remote="https://example.com/acme/acme-widgets.git", branch="feat/audit-fallback"):
    tmp = Path(tempfile.mkdtemp(prefix="attr-"))
    subprocess.run(["git", "init", "-q"], cwd=tmp, check=True)
    subprocess.run(["git", "checkout", "-q", "-b", branch], cwd=tmp, check=True)
    subprocess.run(["git", "remote", "add", "origin", remote], cwd=tmp, check=True)
    return tmp


def _null_record():
    return {"app": None, "feature": None, "plugin": None}


def test_fallback_fills_app_and_feature_from_git():
    tmp = _git_fixture()
    try:
        rec = apply_attribution(_null_record(), str(tmp))
        assert rec["app"] == "acme-widgets", rec
        assert rec["feature"] == "feat/audit-fallback", rec
        assert rec["plugin"] is None, rec  # plugin is transcript-owned, never git-filled
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_explicit_context_json_wins_over_git():
    tmp = _git_fixture()
    try:
        (tmp / ".ai-baseline").mkdir()
        (tmp / ".ai-baseline" / "context.json").write_text(
            json.dumps({"app": "billing", "feature": "user-auth"}), encoding="utf-8")
        rec = apply_attribution(_null_record(), str(tmp))
        assert rec["app"] == "billing" and rec["feature"] == "user-auth", rec
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_partial_context_json_mixes_with_git_fallback():
    tmp = _git_fixture()
    try:
        (tmp / ".ai-baseline").mkdir()
        (tmp / ".ai-baseline" / "context.json").write_text(json.dumps({"app": "billing"}), encoding="utf-8")
        rec = apply_attribution(_null_record(), str(tmp))
        assert rec["app"] == "billing", rec
        assert rec["feature"] == "feat/audit-fallback", rec  # only the null field falls back to git
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_non_null_fields_never_overwritten():
    tmp = _git_fixture()
    try:
        rec = apply_attribution({"app": "already-set", "feature": None, "plugin": None}, str(tmp))
        assert rec["app"] == "already-set", rec
        assert rec["feature"] == "feat/audit-fallback", rec
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_non_git_dir_fails_open_to_nulls():
    tmp = Path(tempfile.mkdtemp(prefix="attr-nogit-"))
    try:
        rec = apply_attribution(_null_record(), str(tmp))
        assert rec["app"] is None and rec["feature"] is None, rec
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_repo_basename_shapes():
    assert _repo_basename("https://github.com/acme/widgets.git") == "widgets"
    assert _repo_basename("git@example.com:acme/widgets.git") == "widgets"
    assert _repo_basename("git@example.com:widgets.git") == "widgets"
    assert _repo_basename("https://example.com/widgets/") == "widgets"


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
