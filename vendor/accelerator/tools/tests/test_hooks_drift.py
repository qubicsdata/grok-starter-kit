#!/usr/bin/env python3
"""Stdlib tests for tools/check-hooks-drift.py run_checks(). Run: python3 tools/tests/test_hooks_drift.py"""
import importlib.util
import json
import shutil
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent

# check-hooks-drift.py has dashes in its name — load it via importlib.
_spec = importlib.util.spec_from_file_location("check_hooks_drift", REPO / "tools" / "check-hooks-drift.py")
check_hooks_drift = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(check_hooks_drift)
run_checks = check_hooks_drift.run_checks

VALID_HOOKS_JSON = {
    "hooks": {
        "SessionStart": [{"hooks": [{"type": "command", "command": "python3 x", "timeout": 10}]}],
        "Stop": [{"hooks": [{"type": "command", "command": "python3 x", "timeout": 10}]}],
        "SubagentStop": [{"hooks": [{"type": "command", "command": "python3 x", "timeout": 10}]}],
        "PreToolUse": [{"matcher": "Bash", "hooks": [{"type": "command", "command": "python3 x", "timeout": 10}]}],
    }
}


def _make_root(tmp: Path) -> Path:
    """Build a minimal fixture repo: canonical hooks + byte-identical shipped set + valid hooks.json."""
    canonical = tmp / "tools" / "hooks"
    shipped = tmp / "ai-baseline" / "hooks" / "scripts"
    canonical.mkdir(parents=True)
    shipped.mkdir(parents=True)
    for name, body in (("_hooklib.py", "# shared helpers\nX = 1\n"), ("secret_guard.py", "print('guard')\n")):
        (canonical / name).write_text(body, encoding="utf-8")
        (shipped / name).write_text(body, encoding="utf-8")
    (canonical / "README.md").write_text("# not shipped\n", encoding="utf-8")
    (tmp / "ai-baseline" / "hooks" / "hooks.json").write_text(json.dumps(VALID_HOOKS_JSON), encoding="utf-8")
    pricing = '{"unit": "usd_per_token", "models": {}}\n'
    (tmp / "pricing.json").write_text(pricing, encoding="utf-8")
    (shipped / "pricing.json").write_text(pricing, encoding="utf-8")
    return tmp


def _with_fixture(mutate):
    tmp = Path(tempfile.mkdtemp(prefix="hooks-drift-"))
    try:
        root = _make_root(tmp)
        mutate(root)
        return run_checks(root, quiet=True)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_identical_passes():
    findings = _with_fixture(lambda root: None)
    assert findings == [], findings


def test_one_byte_diff_fails():
    def mutate(root):
        p = root / "ai-baseline" / "hooks" / "scripts" / "secret_guard.py"
        p.write_text(p.read_text(encoding="utf-8") + " ", encoding="utf-8")
    findings = _with_fixture(mutate)
    assert any("secret_guard.py" in f and "DRIFT" in f for f in findings), findings


def test_missing_shipped_file_fails():
    def mutate(root):
        (root / "ai-baseline" / "hooks" / "scripts" / "_hooklib.py").unlink()
    findings = _with_fixture(mutate)
    assert any("_hooklib.py" in f and "MISSING" in f for f in findings), findings


def test_stray_shipped_file_fails():
    def mutate(root):
        (root / "ai-baseline" / "hooks" / "scripts" / "orphan.py").write_text("x = 1\n", encoding="utf-8")
    findings = _with_fixture(mutate)
    assert any("orphan.py" in f and "STRAY" in f for f in findings), findings


def test_missing_hooks_json_fails():
    def mutate(root):
        (root / "ai-baseline" / "hooks" / "hooks.json").unlink()
    findings = _with_fixture(mutate)
    assert any("hooks.json" in f and "MISSING" in f for f in findings), findings


def test_malformed_hooks_json_fails():
    def mutate(root):
        (root / "ai-baseline" / "hooks" / "hooks.json").write_text("{not json", encoding="utf-8")
    findings = _with_fixture(mutate)
    assert any("hooks.json" in f and "not valid JSON" in f for f in findings), findings


def test_hooks_json_missing_event_fails():
    def mutate(root):
        data = json.loads((root / "ai-baseline" / "hooks" / "hooks.json").read_text(encoding="utf-8"))
        del data["hooks"]["SubagentStop"]
        (root / "ai-baseline" / "hooks" / "hooks.json").write_text(json.dumps(data), encoding="utf-8")
    findings = _with_fixture(mutate)
    assert any("SubagentStop" in f for f in findings), findings


def test_pricing_data_drift_fails():
    def mutate(root):
        p = root / "ai-baseline" / "hooks" / "scripts" / "pricing.json"
        p.write_text(p.read_text(encoding="utf-8") + " ", encoding="utf-8")
    findings = _with_fixture(mutate)
    assert any("pricing.json" in f and "DRIFT" in f for f in findings), findings


def test_missing_shipped_pricing_data_fails():
    def mutate(root):
        (root / "ai-baseline" / "hooks" / "scripts" / "pricing.json").unlink()
    findings = _with_fixture(mutate)
    assert any("pricing.json" in f and "MISSING" in f for f in findings), findings


def test_missing_canonical_pricing_data_fails():
    def mutate(root):
        (root / "pricing.json").unlink()
    findings = _with_fixture(mutate)
    assert any("pricing.json" in f and "MISSING" in f for f in findings), findings


def test_readme_not_required_in_shipped_set():
    # README.md exists canonically but must not be demanded from (or flagged in) the shipped set.
    findings = _with_fixture(lambda root: None)
    assert not any("README.md" in f for f in findings), findings


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
