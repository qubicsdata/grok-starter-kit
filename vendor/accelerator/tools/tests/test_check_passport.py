#!/usr/bin/env python3
"""Stdlib tests for tools/check-passport.py — the deterministic mirror of
product-companion's backlog-schema DoR/DoD predicates.
Run: python3 tools/tests/test_check_passport.py"""
import importlib.util
import json
import shutil
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent

# check-passport.py has dashes in its name — load it via importlib.
_spec = importlib.util.spec_from_file_location("check_passport", REPO / "tools" / "check-passport.py")
check_passport = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(check_passport)

FIXTURES = REPO / "tools" / "tests" / "fixtures" / "passport"
VALID = FIXTURES / "valid"


# ---------------------------------------------------------------- helpers

def _with_tree(mutate):
    """Copy the valid fixture tree, apply `mutate(root)`, run check_tree, clean up."""
    tmp = Path(tempfile.mkdtemp(prefix="check-passport-"))
    try:
        root = tmp / "tree"
        shutil.copytree(VALID, root)
        mutate(root)
        return check_passport.check_tree(root)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _rules(findings):
    return {f.rule for f in findings}


def _edit(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    assert old in text, f"fixture drift: {old!r} not found in {path.name}"
    path.write_text(text.replace(old, new), encoding="utf-8")


def _edit_passport(root: Path, mutate) -> None:
    p = root / "docs" / "product" / "passport.json"
    data = json.loads(p.read_text(encoding="utf-8"))
    mutate(data)
    p.write_text(json.dumps(data), encoding="utf-8")


READY_STORY = Path("docs/product/stories/S-001-guest-enters-shipping-address.md")
DONE_STORY = Path("docs/product/stories/S-002-rate-limiting-on-checkout-api.md")
PERSONA = Path("docs/product/personas/P-001-maya-the-maintainer.md")


# ---------------------------------------------------------------- fixtures pass/fail

def test_valid_tree_is_clean():
    findings = check_passport.check_tree(VALID)
    assert findings == [], [str(f) for f in findings]


def test_every_violation_fixture_fires_its_tag():
    for dirname, tag in check_passport.EXPECTED_VIOLATIONS.items():
        findings = check_passport.check_tree(FIXTURES / dirname)
        assert findings, f"{dirname}: expected findings, got none"
        assert tag in _rules(findings), f"{dirname}: expected [{tag}], got {_rules(findings)}"


def test_selftest_passes():
    assert check_passport.selftest() == 0


def test_no_product_dir_is_clean():
    tmp = Path(tempfile.mkdtemp(prefix="check-passport-empty-"))
    try:
        assert check_passport.check_tree(tmp) == []
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ---------------------------------------------------------------- passport document

def test_unknown_schema_version_flagged():
    findings = _with_tree(lambda root: _edit_passport(
        root, lambda d: d.update(schema_version="9.9.9")))
    assert "PASSPORT" in _rules(findings), _rules(findings)


def test_missing_required_key_flagged():
    findings = _with_tree(lambda root: _edit_passport(
        root, lambda d: d.pop("backlog_scheme")))
    assert "PASSPORT" in _rules(findings), _rules(findings)


def test_bad_stage_enum_flagged():
    findings = _with_tree(lambda root: _edit_passport(
        root, lambda d: d.update(stage="shipping")))
    assert "PASSPORT" in _rules(findings), _rules(findings)


def test_empty_evidence_flagged_as_history():
    def mutate(d):
        d["stage_history"][1]["evidence"] = ""
    findings = _with_tree(lambda root: _edit_passport(root, mutate))
    assert "HISTORY" in _rules(findings), _rules(findings)


def test_stage_regression_without_user_declared_flagged():
    def mutate(d):
        d["stage_history"].append(
            {"stage": "idea", "ts": "2026-07-03T09:00:00Z", "by": "/product-init",
             "evidence": "starting over"})
    findings = _with_tree(lambda root: _edit_passport(root, mutate))
    assert "HISTORY" in _rules(findings), _rules(findings)


def test_stage_regression_with_user_declared_passes():
    def mutate(d):
        d["stage_history"].append(
            {"stage": "idea", "ts": "2026-07-03T09:00:00Z", "by": "/product-init",
             "evidence": "user-declared regression: pivot to new market"})
    findings = _with_tree(lambda root: _edit_passport(root, mutate))
    assert "HISTORY" not in _rules(findings), [str(f) for f in findings]


# ---------------------------------------------------------------- grammar + identity

def test_frontmatter_id_mismatch_flagged():
    findings = _with_tree(lambda root: _edit(root / READY_STORY, "id: S-001", "id: S-009"))
    assert "ID-GRAMMAR" in _rules(findings), _rules(findings)


def test_duplicate_id_flagged():
    def mutate(root):
        src = root / READY_STORY
        shutil.copyfile(src, src.parent / "S-001-duplicate-slug.md")
    findings = _with_tree(mutate)
    assert "DUP-ID" in _rules(findings), _rules(findings)


# ---------------------------------------------------------------- DoR mirror

def test_retired_persona_fails_dor1():
    findings = _with_tree(lambda root: _edit(
        root / PERSONA, "status: active", "status: retired"))
    assert _rules(findings) == {"DOR-1"}, [str(f) for f in findings]


def test_job_size_8_fails_dor4():
    findings = _with_tree(lambda root: _edit(
        root / READY_STORY, "  job_size: 3", "  job_size: 8"))
    assert "DOR-4" in _rules(findings), _rules(findings)


def test_blocked_by_done_story_passes_dor6():
    findings = _with_tree(lambda root: _edit(
        root / READY_STORY, "blocked_by: []", "blocked_by: [S-002]"))
    assert findings == [], [str(f) for f in findings]


def test_blocked_by_missing_story_fails():
    findings = _with_tree(lambda root: _edit(
        root / READY_STORY, "blocked_by: []", "blocked_by: [S-099]"))
    assert "DOR-6" in _rules(findings) and "XLINK" in _rules(findings), _rules(findings)


def test_missing_so_that_fails_dor7():
    findings = _with_tree(lambda root: _edit(
        root / READY_STORY,
        "so that I can complete checkout in one sitting",
        "and checkout completes in one sitting"))
    assert "DOR-7" in _rules(findings), _rules(findings)


def test_dor_not_applied_to_draft_stories():
    def mutate(root):
        _edit(root / READY_STORY, "status: ready", "status: draft")
        _edit_passport(root, lambda d: d.update(ready_count=0))
    findings = _with_tree(mutate)
    assert findings == [], [str(f) for f in findings]


# ---------------------------------------------------------------- DoD mirror

def test_missing_spec_file_fails_dod1():
    findings = _with_tree(
        lambda root: (root / "docs" / "specs" / "0001-rate-limiting.md").unlink())
    assert "DOD-1" in _rules(findings), _rules(findings)


def test_missing_review_verdict_fails_dod3():
    findings = _with_tree(lambda root: _edit(
        root / DONE_STORY, "- review: standard — approved\n", ""))
    assert "DOD-3" in _rules(findings), _rules(findings)


def test_missing_commit_range_fails_dod3():
    findings = _with_tree(lambda root: _edit(
        root / DONE_STORY, "- commits: 1a2b3c4..5d6e7f8\n", ""))
    assert "DOD-3" in _rules(findings), _rules(findings)


def test_unticked_ac_on_done_story_fails_dod2():
    findings = _with_tree(lambda root: _edit(
        root / DONE_STORY,
        "- [x] AC-1: Given 10 requests within a minute, when an 11th arrives, then it receives HTTP 429. — evidence: test_rate_limit_429",
        "- [ ] AC-1: Given 10 requests within a minute, when an 11th arrives, then it receives HTTP 429."))
    assert "DOD-2" in _rules(findings), _rules(findings)


# ---------------------------------------------------------------- enums + caches

def test_wsjf_value_outside_fibonacci_flagged():
    findings = _with_tree(lambda root: _edit(
        root / READY_STORY, "  business_value: 5", "  business_value: 4"))
    assert "ENUM" in _rules(findings), _rules(findings)


def test_priority_cache_mismatch_flagged():
    findings = _with_tree(lambda root: _edit(
        root / READY_STORY, "priority: 3.0", "priority: 2.5"))
    assert "ENUM" in _rules(findings), _rules(findings)


def test_invalid_status_flagged():
    def mutate(root):
        _edit(root / READY_STORY, "status: ready", "status: reviewing")
        _edit_passport(root, lambda d: d.update(ready_count=0))
    findings = _with_tree(mutate)
    assert "ENUM" in _rules(findings), _rules(findings)


# ---------------------------------------------------------------- frontmatter parser

def test_parser_handles_schema_shapes():
    text = "\n".join([
        "---",
        'schema_version: "1.0.0"',
        "id: S-001",
        "role: data-analyst              # kebab-case role token",
        "personas: [P-001, P-002]",
        "inline: { business_value: 8, time_criticality: 3 }",
        "wsjf:",
        "  business_value: 5             # comment",
        "  job_size: 3",
        "pin: null",
        "priority: 3.0",
        'shipped: "one line — with a dash"',
        "---",
        "# Body",
        "## Story",
        "content",
    ])
    fm, body = check_passport.parse_frontmatter(text)
    assert fm is not None
    assert fm["schema_version"] == "1.0.0"
    assert fm["id"] == "S-001"
    assert fm["role"] == "data-analyst", fm["role"]
    assert fm["personas"] == ["P-001", "P-002"]
    assert fm["inline"] == {"business_value": 8, "time_criticality": 3}
    assert fm["wsjf"] == {"business_value": 5, "job_size": 3}
    assert fm["pin"] is None
    assert fm["priority"] == 3.0
    assert fm["shipped"] == "one line — with a dash"
    assert "## Story" in body


def test_parser_returns_none_without_frontmatter():
    fm, _ = check_passport.parse_frontmatter("# Just a doc\n\nNo frontmatter here.\n")
    assert fm is None


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
