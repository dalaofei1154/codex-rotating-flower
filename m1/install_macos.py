#!/usr/bin/env python3
"""Install the global bridge as one macOS user LaunchAgent.

Run: python3 m1/install_macos.py install
Update: python3 m1/install_macos.py install --replace
Remove: python3 m1/install_macos.py uninstall
"""

from __future__ import annotations

import argparse
import os
import plistlib
import shutil
import subprocess
import sys
from pathlib import Path


LABEL = "com.rotatingflower.codex-motor"


def locations() -> tuple[Path, Path, Path]:
    home = Path.home()
    return (home / "Library" / "Application Support" / "RotatingFlower",
            home / "Library" / "LaunchAgents" / f"{LABEL}.plist",
            home / "Library" / "Logs" / "RotatingFlower")


def launchctl(*args: str, check: bool = True) -> None:
    subprocess.run(["launchctl", *args], check=check)


def install(replace: bool, sessions_root: Path, port: str) -> None:
    support, plist_path, logs = locations()
    if plist_path.exists() and not replace:
        raise RuntimeError(f"Already installed: {plist_path}. Use install --replace to update.")
    if not sessions_root.is_dir():
        raise RuntimeError(f"Codex sessions directory does not exist: {sessions_root}")
    support.mkdir(parents=True, exist_ok=True)
    plist_path.parent.mkdir(parents=True, exist_ok=True)
    logs.mkdir(parents=True, exist_ok=True)
    target = support / "global_bridge.py"
    shutil.copy2(Path(__file__).with_name("global_bridge.py"), target)
    domain = f"gui/{os.getuid()}"
    if replace:
        launchctl("bootout", domain, str(plist_path), check=False)
    payload = {
        "Label": LABEL,
        "ProgramArguments": [sys.executable, str(target), "--sessions-root",
                             str(sessions_root), "--port", port],
        "RunAtLoad": True,
        "KeepAlive": True,
        "ThrottleInterval": 5,
        "StandardOutPath": str(logs / "bridge.log"),
        "StandardErrorPath": str(logs / "bridge-error.log"),
    }
    temporary = plist_path.with_suffix(".plist.tmp")
    with temporary.open("wb") as file:
        plistlib.dump(payload, file)
    temporary.replace(plist_path)
    launchctl("bootstrap", domain, str(plist_path))
    print(f"Installed {LABEL}")
    print(f"Logs: {logs / 'bridge.log'}")


def uninstall() -> None:
    support, plist_path, _ = locations()
    domain = f"gui/{os.getuid()}"
    if plist_path.exists():
        launchctl("bootout", domain, str(plist_path), check=False)
        plist_path.unlink()
    target = support / "global_bridge.py"
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
    args = parser.parse_args()
    if sys.platform != "darwin":
        parser.error("This installer supports macOS only")
    try:
        if args.action == "install":
            install(args.replace, args.sessions_root, args.port)
        else:
            uninstall()
    except (OSError, subprocess.CalledProcessError, RuntimeError) as exc:
        print(f"Install error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
