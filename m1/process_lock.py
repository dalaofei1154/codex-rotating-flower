"""Keep one bridge instance per user on macOS, Linux, and Windows.

``fcntl`` does not exist on Windows, so the lock is taken with ``msvcrt``
there and with ``fcntl`` everywhere else. Both release the lock when the
returned file object is closed, which lets the caller keep the existing
``lock_file.close()`` cleanup path.
"""

from __future__ import annotations

import getpass
import os
import sys
import tempfile
from pathlib import Path


def _user_token() -> str:
    try:
        user = getpass.getuser()
    except (OSError, KeyError):
        user = ""
    if not user:
        user = os.environ.get("USERNAME") or os.environ.get("USER") or "user"
    safe = "".join(character for character in user if character.isalnum())
    return safe or "user"


def singleton_path(name: str) -> Path:
    """Return a per-user lock path that Windows file names also accept."""
    return Path(tempfile.gettempdir()) / f"{name}-{_user_token()}.lock"


def acquire(path: Path):
    """Lock ``path`` or return None when another process already holds it."""
    handle = path.open("a+b")
    try:
        if sys.platform == "win32":
            import msvcrt
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        handle.close()
        return None
    return handle
