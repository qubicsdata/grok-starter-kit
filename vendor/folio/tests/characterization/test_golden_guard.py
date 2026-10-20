"""KEEP.md rule: `keep_*` goldens are never rewritten, even with FOLIO_UPDATE_GOLDENS=1 (review r1 L-2)."""

import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from . import golden


class KeepGoldenGuardTests(unittest.TestCase):
    def setUp(self):
        # Work on a temp copy so a red run can never touch the checked-in goldens.
        tmp = Path(tempfile.mkdtemp(prefix="folio-golden-guard-"))
        self.addCleanup(shutil.rmtree, str(tmp), True)
        shutil.copy(golden.GOLDENS / "keep_sec12_headers.json", tmp / "keep_sec12_headers.json")
        self.goldens = tmp

    def test_update_mode_refuses_keep_goldens_and_leaves_them_unchanged(self):
        path = self.goldens / "keep_sec12_headers.json"
        before = path.read_bytes()
        with mock.patch.dict(os.environ, {"FOLIO_UPDATE_GOLDENS": "1"}), \
                mock.patch.object(golden, "GOLDENS", self.goldens):
            with self.assertRaises(AssertionError) as raised:
                golden.assert_golden(self, "keep_sec12_headers", {"changed": True})
        self.assertIn("keep_", str(raised.exception))
        self.assertEqual(path.read_bytes(), before)

    def test_update_mode_still_rewrites_other_goldens(self):
        with mock.patch.dict(os.environ, {"FOLIO_UPDATE_GOLDENS": "1"}), \
                mock.patch.object(golden, "GOLDENS", self.goldens):
            golden.assert_golden(self, "plain_example", {"v": 1})
        self.assertTrue((self.goldens / "plain_example.json").is_file())


if __name__ == "__main__":
    unittest.main()
