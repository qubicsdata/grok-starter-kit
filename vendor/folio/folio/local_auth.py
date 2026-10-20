"""Private, per-server discovery credentials for the local owner account."""

import json
import os
import re
import stat
from pathlib import Path

CREDENTIAL = re.compile(r"[a-f0-9]{64}")


def read_server_info(workspace):
    """Read only a regular owner-only file; never follow a discovery symlink."""
    path = Path(workspace) / ".server.json"
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0))
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or info.st_size > 65536:
            raise ValueError("Invalid Folio discovery file.")
        if os.name != "nt" and (info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o600):
            raise ValueError("Folio discovery must be owned by this account with mode 0600.")
        with os.fdopen(descriptor, encoding="utf-8") as handle:
            descriptor = None
            value = json.load(handle)
        if not isinstance(value, dict):
            raise ValueError("Invalid Folio discovery file.")
        return value
    finally:
        if descriptor is not None:
            os.close(descriptor)


def owner_credential(workspace, base_url):
    info = read_server_info(workspace)
    if base_url != f"http://127.0.0.1:{info.get('port')}" or not CREDENTIAL.fullmatch(str(info.get("owner_token", ""))):
        raise ValueError("Invalid Folio owner discovery.")
    return info["owner_token"]


def browser_url(workspace, base_url):
    info = read_server_info(workspace)
    if base_url != f"http://127.0.0.1:{info.get('port')}" or not CREDENTIAL.fullmatch(str(info.get("browser_token", ""))):
        raise ValueError("Invalid Folio browser discovery.")
    return base_url + "/#folio-launch=" + info["browser_token"]
