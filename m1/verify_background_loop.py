"""Run the integrated bridge's background path briefly and check the status file.

This is the code path that raised AttributeError on macOS: the loop writes a
status dict containing device_connected, and --once never reaches it.
"""

import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main() -> int:
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder)
        sessions = root / "sessions"
        sessions.mkdir()
        workbuddy = root / "workbuddy"
        workbuddy.mkdir()
        status = root / "status.json"
        cache = root / "cache.json"

        command = [
            sys.executable,
            str(HERE / "integrated" / "integrated_bridge.py"),
            "--source", "codex",
            "--sessions-root", str(sessions),
            "--workbuddy-root", str(workbuddy),
            "--port", "auto",
            "--status-file", str(status),
            "--attention-cache", str(cache),
        ]

        process = subprocess.Popen(
            command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, cwd=str(HERE),
        )
        try:
            # The loop writes status once per second; give it a few cycles.
            deadline = time.monotonic() + 12
            while time.monotonic() < deadline and not status.exists():
                time.sleep(0.5)
        finally:
            process.terminate()
            try:
                stdout, stderr = process.communicate(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                stdout, stderr = process.communicate()

        print("--- stdout ---")
        print(stdout.strip()[:800])
        print("--- stderr ---")
        print(stderr.strip()[:1200])

        if "AttributeError" in stderr:
            print("RESULT: FAIL - the background loop raised AttributeError")
            return 1
        if not status.exists():
            print("RESULT: FAIL - the loop never wrote a status file")
            return 1

        payload = json.loads(status.read_text())
        print("--- status ---")
        print(json.dumps(payload, indent=2, ensure_ascii=False)[:600])
        if "device_connected" not in payload:
            print("RESULT: FAIL - status has no device_connected")
            return 1

        print("RESULT: the background loop wrote a status file without raising")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
