#!/usr/bin/env python3
"""A local, project-folder-backed workspace for solution architects."""

from folio.core import AppError, Store  # noqa: F401 - re-exported for existing imports
from folio.web import main, make_server  # noqa: F401

if __name__ == "__main__":
    main()
