#!/usr/bin/env python3
"""Run the overwrite-protection harness, optionally against another case
folder or another copy of the kit.

    python3 tests/overwrite/run_harness.py [--existing-dir DIR] [--kit DIR] [-v]

--existing-dir DIR  folder of `case-*.yaml` files (default: the kit's
                    tests/fixtures/existing-setup; env KIT_OVERWRITE_TARGET)
--kit DIR           the kit to test (default: this one; env KIT_OVERWRITE_KIT)

Every case still runs in its own temp folder; the override only chooses which
case files describe the existing setups. Exit code: unittest's.
"""

import argparse
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))


def main(argv=None):
    parser = argparse.ArgumentParser(prog="run_harness.py", description=__doc__.split("\n\n")[0])
    parser.add_argument("--existing-dir", metavar="DIR", help="folder of case-*.yaml files")
    parser.add_argument("--kit", metavar="DIR", help="another copy of the kit to test")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)
    if args.existing_dir:
        if not os.path.isdir(args.existing_dir):
            parser.error("--existing-dir is not a folder")
        os.environ["KIT_OVERWRITE_TARGET"] = os.path.abspath(args.existing_dir)
    if args.kit:
        if not os.path.isfile(os.path.join(args.kit, "AGENTS.md")):
            parser.error("--kit is not a kit folder (no AGENTS.md)")
        os.environ["KIT_OVERWRITE_KIT"] = os.path.abspath(args.kit)
    sys.dont_write_bytecode = True
    if HERE not in sys.path:
        sys.path.insert(0, HERE)
    suite = unittest.defaultTestLoader.discover(HERE, pattern="test_*.py", top_level_dir=HERE)
    result = unittest.TextTestRunner(verbosity=2 if args.verbose else 1).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
