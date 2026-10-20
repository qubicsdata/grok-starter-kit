"""Compare a JSON-serialisable value with a checked-in golden file next to these tests.

Set FOLIO_UPDATE_GOLDENS=1 to rewrite the files from the current behaviour (review the diff before keeping it).
`keep_*` goldens are never rewritten (tests/KEEP.md): update mode fails on them instead.
"""

import json
import os
from datetime import date
from pathlib import Path

GOLDENS = Path(__file__).resolve().with_name("goldens")
TODAY = "2026-10-17"


class FixedDate(date):
    """date.today() pinned to TODAY, so overdue/attention goldens never depend on the wall clock."""

    @classmethod
    def today(cls):
        return cls.fromisoformat(TODAY)


def render(value):
    return json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True) + "\n"


def assert_golden(test, name, value):
    path = GOLDENS / f"{name}.json"
    actual = render(value)
    if os.environ.get("FOLIO_UPDATE_GOLDENS") == "1":
        test.assertFalse(name.startswith("keep_"),
                         f"{path.name} is a keep_* golden (tests/KEEP.md): never rewritten, not even with FOLIO_UPDATE_GOLDENS=1")
        GOLDENS.mkdir(exist_ok=True)
        path.write_text(actual, encoding="utf-8")
        return
    test.assertTrue(path.exists(), f"Missing golden {path.name}; run with FOLIO_UPDATE_GOLDENS=1 to create it.")
    test.maxDiff = None
    test.assertEqual(json.loads(actual), json.loads(path.read_text(encoding="utf-8")), f"Behaviour drifted from golden {path.name}")
