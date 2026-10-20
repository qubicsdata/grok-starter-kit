"""Golden: the planning brief and source-read JSON contract (folio/brief.py:46-107)."""

import threading
import unittest
from unittest.mock import patch

from folio.brief import brief_for_project, read_source
from folio.core import AppError
from folio.notes import digest

from .fixtures import PROJECT_ID, project
from .golden import FixedDate, assert_golden


class StubStore:
    """Just what project_brief/read_source touch: a lock and project()."""

    def __init__(self, value):
        self.lock = threading.RLock()
        self.value = value

    def project(self, project_id):
        if project_id != self.value["id"]:
            raise AppError("Project not found.", 404, "NOT_FOUND")
        return self.value


def failure(call):
    try:
        call()
    except AppError as error:
        return {"message": str(error), "status": error.status, "code": error.code}
    raise AssertionError("expected an AppError")


@patch("folio.brief.date", FixedDate)
class BriefSourceGoldenTests(unittest.TestCase):
    def test_brief_contract(self):
        cases = {
            "default": ("", 12000),
            "query_sqlite": ("SQLite ledger", 12000),
            "no_match": ("zzzz-unmatched", 12000),
            "tight_budget": ("", 500),
        }
        result = {name: brief_for_project(project(), query, budget) for name, (query, budget) in cases.items()}
        assert_golden(self, "brief_contract", result)

    def test_brief_rejects_bad_arguments(self):
        result = {
            "query_too_long": failure(lambda: brief_for_project(project(), "q" * 1001)),
            "query_not_string": failure(lambda: brief_for_project(project(), 7)),
            "budget_too_small": failure(lambda: brief_for_project(project(), "", 499)),
            "budget_too_large": failure(lambda: brief_for_project(project(), "", 40001)),
            "budget_bool": failure(lambda: brief_for_project(project(), "", True)),
        }
        assert_golden(self, "brief_errors", result)

    def test_source_reads_and_paging(self):
        store = StubStore(project())
        brief = brief_for_project(project(), "", 12000)
        decision = next(r for r in brief["records"] if r["kind"] == "decision")
        pages, offset = [], 0
        while offset is not None:
            page = read_source(store, PROJECT_ID, "task:0000000000000002", offset, 40, None)
            pages.append(page)
            offset = page["next_offset"]
        result = {
            "notes": read_source(store, PROJECT_ID, f"project:{PROJECT_ID}:notes"),
            "project": read_source(store, PROJECT_ID, f"project:{PROJECT_ID}", 0, 30),
            "decision_by_hash": read_source(store, PROJECT_ID, decision["source"], 0, 12000, decision["hash"]),
            "task_pages": pages,
        }
        self.assertEqual(digest("".join(p["text"] for p in pages)), pages[0]["hash"])
        assert_golden(self, "source_reads", result)

    def test_source_rejects_bad_arguments(self):
        store = StubStore(project())
        notes = f"project:{PROJECT_ID}:notes"
        result = {
            "unknown_source": failure(lambda: read_source(store, PROJECT_ID, "task:ffffffffffffffff")),
            "hash_mismatch": failure(lambda: read_source(store, PROJECT_ID, notes, 0, 100, "0" * 64)),
            "hash_malformed": failure(lambda: read_source(store, PROJECT_ID, notes, 0, 100, "XYZ")),
            "offset_beyond_end": failure(lambda: read_source(store, PROJECT_ID, notes, 10 ** 6)),
            "negative_offset": failure(lambda: read_source(store, PROJECT_ID, notes, -1)),
            "zero_budget": failure(lambda: read_source(store, PROJECT_ID, notes, 0, 0)),
            "source_not_string": failure(lambda: read_source(store, PROJECT_ID, None)),
        }
        assert_golden(self, "source_errors", result)


if __name__ == "__main__":
    unittest.main()
