#!/usr/bin/env python3
"""Install the global bridge as one Windows sign-in task.

Run: python m1\\install_windows.py install
Update: python m1\\install_windows.py install --replace
Remove: python m1\\install_windows.py uninstall

This mirrors install_macos.py: it copies the runtime next to itself, registers
one per-user task that starts at sign-in, and keeps logs in the same layout.
"""

from __future__ import annotations

import argparse
import datetime as dt
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


TASK_NAME = "RotatingFlowerCodexMotor"
RUNTIME_FILES = ("global_bridge.py", "serial_link.py", "process_lock.py",
                 "process_probe.py")


def locations() -> tuple[Path, Path]:
    local = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    support = Path(local) / "RotatingFlower"
    return support, support / "logs"


def schtasks(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(["schtasks", *args], check=check, capture_output=True,
                          text=True, timeout=30)


def task_exists() -> bool:
    try:
        result = schtasks("/Query", "/TN", TASK_NAME, check=False)
    except (OSError, subprocess.SubprocessError):
        return False
    return result.returncode == 0


def task_command(target: Path, sessions_root: Path, port: str, source: str,
                 workbuddy_root: Path | None) -> str:
    parts = [f'"{sys.executable}"', f'"{target}"',
             "--sessions-root", f'"{sessions_root}"',
             "--port", f'"{port}"',
             "--source", source]
    if workbuddy_root is not None:
        parts += ["--workbuddy-root", f'"{workbuddy_root}"']
    return " ".join(parts)


def task_definition() -> str | None:
    """Return the registered task's XML so a failed replace can restore it."""
    if not task_exists():
        return None
    try:
        result = schtasks("/Query", "/TN", TASK_NAME, "/XML", check=False)
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0 or not result.stdout.strip():
        return None
    return result.stdout


def restore_task(definition: str | None) -> None:
    """Put the previous task back, or remove the one this run created."""
    if definition is None:
        schtasks("/Delete", "/TN", TASK_NAME, "/F", check=False)
        return
    handle = None
    try:
        handle = tempfile.NamedTemporaryFile(
            mode="w", suffix=".xml", delete=False, encoding="utf-16")
        handle.write(definition)
        handle.close()
        schtasks("/Create", "/TN", TASK_NAME, "/XML", handle.name, "/F", check=False)
    except (OSError, subprocess.SubprocessError):
        pass
    finally:
        if handle is not None:
            try:
                os.unlink(handle.name)
            except OSError:
                pass


def install(replace: bool, sessions_root: Path, port: str,
            source: str = "codex", workbuddy_root: Path | None = None) -> int:
    support, logs = locations()
    if task_exists() and not replace:
        raise RuntimeError(f"Already installed as {TASK_NAME}. Use install --replace to update.")
    if source in ("codex", "both") and not sessions_root.is_dir():
        raise RuntimeError(f"Codex sessions directory does not exist: {sessions_root}")
    if source in ("workbuddy", "both"):
        if workbuddy_root is None or not (workbuddy_root / "workbuddy.db").is_file():
            raise RuntimeError("Open WorkBuddy and complete one local task before installing")

    support.mkdir(parents=True, exist_ok=True)
    logs.mkdir(parents=True, exist_ok=True)

    previous = {support / name: ((support / name).read_bytes()
                                 if (support / name).exists() else None)
                for name in RUNTIME_FILES}
    previous_task = task_definition()
    if replace and (any(value is not None for value in previous.values())
                    or previous_task is not None):
        stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        backup = support / "backups" / stamp
        backup.mkdir(parents=True)
        for path, contents in previous.items():
            if contents is not None:
                (backup / path.name).write_bytes(contents)
        if previous_task is not None:
            (backup / f"{TASK_NAME}.xml").write_text(previous_task, encoding="utf-16")
        print(f"Previous installation backed up: {backup}")

    target = support / "global_bridge.py"
    try:
        for name in RUNTIME_FILES:
            shutil.copy2(Path(__file__).with_name(name), support / name)
        command = task_command(target, sessions_root, port, source, workbuddy_root)
        # /RL LIMITED keeps it in the normal user context, like a LaunchAgent.
        schtasks("/Create", "/TN", TASK_NAME, "/TR", command, "/SC", "ONLOGON",
                 "/RL", "LIMITED", "/F")
    except (OSError, subprocess.SubprocessError):
        # A timeout is a SubprocessError but not a CalledProcessError, and it
        # can leave the old task deleted, so roll back on both.
        restore_task(previous_task)
        for path, contents in previous.items():
            if contents is not None:
                path.write_bytes(contents)
            elif path.exists():
                path.unlink()
        raise

    print(f"Installed {TASK_NAME}; source: {source}")
    print(f"Logs: {logs}")
    print(f"Start it now with: schtasks /Run /TN {TASK_NAME}")
    return 0


def uninstall() -> None:
    support, _ = locations()
    if task_exists():
        schtasks("/Delete", "/TN", TASK_NAME, "/F", check=False)
    for name in RUNTIME_FILES:
        target = support / name
        if target.exists():
            target.unlink()
    print(f"Removed {TASK_NAME}; log files were kept")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("install", "uninstall"))
    parser.add_argument("--replace", action="store_true")
    default_root = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))) / "sessions"
    parser.add_argument("--sessions-root", type=Path, default=default_root)
    parser.add_argument("--port", default="auto", help="COM port such as COM3, or auto")
    parser.add_argument("--source", choices=("codex", "workbuddy", "both"), default="codex")
    workbuddy_roots = [Path.home() / ".workbuddy", Path.home() / ".workbuddy-ai"]
    default_workbuddy = next((root for root in workbuddy_roots
                              if (root / "workbuddy.db").is_file()), workbuddy_roots[0])
    parser.add_argument("--workbuddy-root", type=Path, default=default_workbuddy)
    args = parser.parse_args()
    if sys.platform != "win32":
        parser.error("This installer supports Windows only")
    try:
        if args.action == "install":
            install(args.replace, args.sessions_root, args.port,
                    args.source, args.workbuddy_root)
        else:
            uninstall()
    except (OSError, subprocess.CalledProcessError, RuntimeError) as exc:
        print(f"Install error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
