"""R-b (review r1 M-1): characterization tests and goldens hold no `/home/<name>` or `/Users/<name>`.

The WP-0a local_path rule flags such paths (they would block WP-0b); fixtures use
`/nonexistent/fixture-home` or a temp-dir value instead. Patterns are built from fragments.
"""

import re
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
LOCAL = re.compile(re.escape("/" + "home" + "/") + r"(?!linuxbrew\b)[A-Za-z0-9._-]+|" + re.escape("/" + "Users" + "/") + r"[A-Za-z0-9._-]+")


class NoLocalPathTests(unittest.TestCase):
    def test_characterization_files_hold_no_home_paths(self):
        hits = []
        for path in sorted(HERE.rglob("*")):
            if path.is_file() and path.suffix in (".py", ".json", ".md"):
                for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                    if LOCAL.search(line):
                        hits.append("%s:%d" % (path.relative_to(HERE), number))
        self.assertEqual(hits, [])


if __name__ == "__main__":
    unittest.main()
