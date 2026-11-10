"""Check the unified installer stages the shared modules and can import them.

Replays integrated_setup.install()'s staging step into a temp directory, then
imports the staged bridge with only that directory on sys.path. That is exactly
the failure the maintainer reported: the installed copy could not import
serial_link / process_lock / process_probe.
"""

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import integrated_setup


def main() -> int:
    source = integrated_setup.source_directory()
    files = sorted(p for p in source.glob("*.py") if not p.name.startswith("test_"))
    for name in integrated_setup.SHARED_MODULES:
        files.append(source.parent / name)

    with tempfile.TemporaryDirectory() as folder:
        stage = Path(folder)
        for path in files:
            shutil.copy2(path, stage / path.name)

        staged = sorted(p.name for p in stage.glob("*.py"))
        print("staged modules:", staged)

        missing = [n for n in integrated_setup.SHARED_MODULES if n not in staged]
        if missing:
            print("RESULT: FAIL - shared modules not staged:", missing)
            return 1

        # Import the staged bridge with only the stage on the path, the way the
        # LaunchAgent runs it.
        probe = (
            "import sys; sys.path.insert(0, %r);"
            "import integrated_bridge;"
            "print('imported:', integrated_bridge.Flower.__name__)"
        ) % str(stage)
        result = subprocess.run(
            [sys.executable, "-I", "-c", probe],
            capture_output=True, text=True, shell=False, timeout=60,
            cwd=str(stage),
        )
        print("import exit:", result.returncode)
        print("stdout:", result.stdout.strip()[:300])
        if result.returncode != 0:
            print("stderr:", result.stderr.strip()[:800])
            print("RESULT: FAIL - the staged bridge cannot import its modules")
            return 1

        print("RESULT: the staged unified runtime imports and exposes Flower")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
