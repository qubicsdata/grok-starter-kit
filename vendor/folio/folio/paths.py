"""User data locations, independent of the installation and working directory."""
import os
import sys
from pathlib import Path


def default_workspace(env=None, platform=None):
    env = os.environ if env is None else env
    platform = sys.platform if platform is None else platform
    home = Path.home()
    if platform == "win32":
        return Path(env.get("LOCALAPPDATA") or home / "AppData" / "Local") / "Folio" / "workspace"
    if platform == "darwin":
        return home / "Library" / "Application Support" / "Folio" / "workspace"
    return Path(env.get("XDG_DATA_HOME") or home / ".local" / "share") / "folio" / "workspace"


def path_identity(value):
    """Match roots using the platform's filesystem case semantics."""
    return os.path.normcase(os.path.realpath(value))
