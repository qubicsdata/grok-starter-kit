import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class PackageBoundaryTests(unittest.TestCase):
    def test_the_frozen_sync_package_is_neither_importable_nor_imported(self):
        # WP-7 (3/3): folio/switchboard/ is deleted; the core modules must not reach for it in any form.
        code = ("import importlib.util, sys, threading; import folio.core, folio.api, folio.web, folio.transport, folio.cli; "
                "print(importlib.util.find_spec('folio.switchboard') is None, "
                "any(name.startswith('folio.switchboard') for name in sys.modules), threading.active_count())")
        result = subprocess.run([sys.executable, "-c", code], cwd=str(ROOT), capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.split(), ["True", "False", "1"])


if __name__ == "__main__":
    unittest.main()
