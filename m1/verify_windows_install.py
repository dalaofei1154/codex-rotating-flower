"""Install into a temp LOCALAPPDATA, then run the installed copy.

This catches the failure mode where the test suite passes but the installed
runtime is missing a module it imports.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import install_windows


def main() -> int:
    if sys.platform != "win32":
        print("SKIP: Windows installer")
        return 0

    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder)
        sessions = root / "sessions"
        sessions.mkdir()

        support = root / "RotatingFlower"
        logs = support / "logs"
        with _patched(install_windows, "locations", lambda: (support, logs)), \
             _patched(install_windows, "task_exists", lambda: False), \
             _patched(install_windows, "schtasks", lambda *a, **k: _Done()):
            install_windows.install(False, sessions, "auto", "codex", None)

        installed = support / "global_bridge.py"
        print("installed files:", sorted(p.name for p in support.glob("*.py")))
        if not installed.exists():
            print("FAIL: global_bridge.py was not installed")
            return 1

        # The installed copy must import and run with only its siblings present.
        result = subprocess.run(
            [sys.executable, str(installed), "--once",
             "--sessions-root", str(sessions)],
            capture_output=True, text=True, shell=False, timeout=60,
            cwd=str(support),
        )
        print("installed copy exit:", result.returncode)
        print("stdout:", result.stdout.strip()[:200])
        if result.returncode != 0:
            print("stderr:", result.stderr.strip()[:600])
            print("RESULT: FAIL - the installed runtime is incomplete")
            return 1

        print("RESULT: the installed copy runs from its own directory")
        return 0


class _Done:
    returncode = 0
    stdout = ""
    stderr = ""


class _patched:
    """Minimal patch context manager without importing unittest.mock."""

    def __init__(self, module, name, value):
        self.module = module
        self.name = name
        self.value = value
        self.saved = None

    def __enter__(self):
        self.saved = getattr(self.module, self.name)
        setattr(self.module, self.name, self.value)
        return self

    def __exit__(self, *exc):
        setattr(self.module, self.name, self.saved)
        return False


if __name__ == "__main__":
    raise SystemExit(main())
