#!/usr/bin/env python3
"""Stdlib tests for tools/check-model-ids.py. Run: python3 tools/tests/test_model_ids.py"""
import importlib.util
import json
import shutil
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
_spec = importlib.util.spec_from_file_location("check_model_ids", REPO / "tools" / "check-model-ids.py")
cmi = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cmi)

FX = REPO / "tools" / "tests" / "model-ids-fixtures"
failures = []

def check(name, cond):
    print(("PASS " if cond else "FAIL ") + name)
    if not cond:
        failures.append(name)

canonical, allowed, deprecated = cmi.load_ids(FX / "clean" / "model-ids.json")
check("clean guide has 0 findings", cmi.check_guide(canonical, FX / "clean" / "model-tier-guide.md") == [])
check("clean frontmatter has 0 findings", cmi.check_frontmatter(allowed, deprecated, FX / "clean") == [])

canonical_d, allowed_d, deprecated_d = cmi.load_ids(FX / "dirty" / "model-ids.json")
check("dirty guide flags stale row", len(cmi.check_guide(canonical_d, FX / "dirty" / "model-tier-guide.md")) == 1)
check("dirty frontmatter flags deprecated id",
      any("DEPRECATED" in f for f in cmi.check_frontmatter(allowed_d, deprecated_d, FX / "dirty")))
check("body literal regex matches versioned ids", cmi.LITERAL_RE.search("use claude-sonnet-4-6 here") is not None)
check("body literal regex ignores tier names", cmi.LITERAL_RE.search("use the sonnet tier") is None)
check("body literal regex matches bare versioned ids", cmi.LITERAL_RE.search("use sonnet-4-6 here") is not None)

# Pricing data lockstep: the suite's pricing.json against the suite's tiers, then mutated copies.
real_canonical, _, _ = cmi.load_ids(cmi.MODEL_IDS_PATH)
check("suite pricing data covers the canonical tiers",
      cmi.check_pricing_tiers(real_canonical, cmi.PRICING_PATH) == [])
_pricing = json.loads(cmi.PRICING_PATH.read_text(encoding="utf-8"))
_tmp = Path(tempfile.mkdtemp(prefix="pricing-tiers-"))
try:
    def _findings(data):
        path = _tmp / "pricing.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        return cmi.check_pricing_tiers(real_canonical, path)
    _missing = dict(_pricing, tiers={k: v for k, v in _pricing["tiers"].items() if k != "haiku"})
    check("missing pricing tier flagged", any("tiers" in f for f in _findings(_missing)))
    _dangling = dict(_pricing, tiers=dict(_pricing["tiers"], opus="claude-example-unpriced"))
    check("tier pointing at an unpriced model flagged", any("unpriced" in f for f in _findings(_dangling)))
    check("unpriced default flagged",
          any("default" in f for f in _findings(dict(_pricing, default="claude-example-unpriced"))))
    check("unreadable pricing data flagged",
          cmi.check_pricing_tiers(real_canonical, _tmp / "absent.json") != [])
finally:
    shutil.rmtree(_tmp, ignore_errors=True)

sys.exit(1 if failures else 0)
