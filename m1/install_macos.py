#!/usr/bin/env python3
"""Install the global bridge as one macOS user LaunchAgent.

Run: python3 m1/install_macos.py install
Update: python3 m1/install_macos.py install --replace
Remove: python3 m1/install_macos.py uninstall
"""

from __future__ import annotations

import argparse
import datetime as dt
import os
import plistlib
import shutil
import subprocess
import sys
from pathlib import Path


LABEL = "com.rotatingflower.codex-motor"
RUNTIME_FILES = ("global_bridge.py", "launch_bridge.sh", "serial_link.py", "process_lock.py")


def locations() -> tuple[Path, Path, Path]:
    home = Path.home()
    return (home / "Library" / "Application Support" / "RotatingFlower",
            home / "Library" / "LaunchAgents" / f"{LABEL}.plist",
            home / "Library" / "Logs" / "RotatingFlower")


def launchctl(*args: str, check: bool = True) -> None:
    subprocess.run(["launchctl", *args], check=check)


def install(replace: bool, sessions_root: Path, port: str,
            source: str = "codex", workbuddy_root: Path | None = None) -> int:
    support, plist_path, logs = locations()
    if plist_path.exists() and not replace:
        raise RuntimeError(f"Already installed: {plist_path}. Use install --replace to update.")
    if source in ("codex", "both") and not sessions_root.is_dir():
        raise RuntimeError(f"Codex sessions directory does not exist: {sessions_root}")
    if source in ("workbuddy", "both"):
        if workbuddy_root is None or not (workbuddy_root / "workbuddy.db").is_file():
            raise RuntimeError("Open WorkBuddy and complete one local task before installing")
    support.mkdir(parents=True, exist_ok=True)
    plist_path.parent.mkdir(parents=True, exist_ok=True)
    logs.mkdir(parents=True, exist_ok=True)
    previous = {path: path.read_bytes() if path.exists() else None
                for path in [plist_path] + [support / name for name in RUNTIME_FILES]}
    if replace and any(value is not None for value in previous.values()):
        stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        backup = support / "backups" / stamp
        backup.mkdir(parents=True)
        for path, contents in previous.items():
            if contents is not None:
                (backup / path.name).write_bytes(contents)
        print(f"Previous installation backed up: {backup}")
    target = support / "global_bridge.py"
    domain = f"gui/{os.getuid()}"
    arguments = ["/bin/bash", str(support / "launch_bridge.sh"), sys.executable,
                 str(target), "--sessions-root", str(sessions_root), "--port", port,
                 "--source", source]
    if workbuddy_root is not None:
        arguments += ["--workbuddy-root", str(workbuddy_root)]
    payload = {
        "Label": LABEL,
        "ProgramArguments": arguments,
        "RunAtLoad": True,
        "KeepAlive": True,
        "ThrottleInterval": 5,
        "StandardOutPath": str(logs / "bridge.log"),
        "StandardErrorPath": str(logs / "bridge-error.log"),
    }
    try:
        if replace:
            launchctl("bootout", domain, str(plist_path), check=False)
        for name in RUNTIME_FILES:
            shutil.copy2(Path(__file__).with_name(name), support / name)
        temporary = plist_path.with_suffix(".plist.tmp")
        with temporary.open("wb") as file:
            plistlib.dump(payload, file)
        temporary.replace(plist_path)
        # The old service has stopped. Only log lines after this point can
        # establish a fresh USB handshake from the service being installed.
        log_file = logs / "bridge.log"
        start_offset = log_file.stat().st_size if log_file.exists() else 0
        launchctl("bootstrap", domain, str(plist_path))
    except (OSError, subprocess.CalledProcessError):
        launchctl("bootout", domain, str(plist_path), check=False)
        for path, contents in previous.items():
            if contents is not None:
                path.write_bytes(contents)
            elif path.exists():
                path.unlink()
        if previous[plist_path] is not None:
            launchctl("bootstrap", domain, str(plist_path), check=False)
        raise
    print(f"Installed {LABEL}; source: {source}")
    print(f"Logs: {logs / 'bridge.log'}")
    return start_offset


def uninstall() -> None:
    support, plist_path, _ = locations()
    domain = f"gui/{os.getuid()}"
    if plist_path.exists():
        launchctl("bootout", domain, str(plist_path), check=False)
        plist_path.unlink()
    for name in RUNTIME_FILES:
        target = support / name
        if target.exists():
            target.unlink()
    print(f"Removed {LABEL}; log files were kept")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("install", "uninstall"))
    parser.add_argument("--replace", action="store_true")
    default_root = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))) / "sessions"
    parser.add_argument("--sessions-root", type=Path, default=default_root)
    parser.add_argument("--port", default="auto")
    parser.add_argument("--source", choices=("codex", "workbuddy", "both"), default="codex")
    workbuddy_roots = [Path.home() / ".workbuddy", Path.home() / ".workbuddy-ai"]
    default_workbuddy = next((root for root in workbuddy_roots
                              if (root / "workbuddy.db").is_file()), workbuddy_roots[0])
    parser.add_argument("--workbuddy-root", type=Path, default=default_workbuddy)
    args = parser.parse_args()
    if sys.platform != "darwin":
        parser.error("This installer supports macOS only")
    try:
        if args.action == "install":
            install(args.replace, args.sessions_root, args.port, args.source, args.workbuddy_root)
        else:
            uninstall()
    except (OSError, subprocess.CalledProcessError, RuntimeError) as exc:
        print(f"Install error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
