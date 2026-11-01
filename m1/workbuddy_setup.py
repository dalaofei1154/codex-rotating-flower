#!/usr/bin/env python3
"""Small macOS setup/diagnostic entry point for a pre-flashed flower."""

from __future__ import annotations

import argparse
import os
import plistlib
import re
import subprocess
import sys
import time
from pathlib import Path

import global_bridge as bridge
import install_macos as installer


def existing_options() -> dict[str, str]:
    _, plist_path, _ = installer.locations()
    if not plist_path.exists():
        return {}
    with plist_path.open("rb") as file:
        payload = plistlib.load(file)
    arguments = payload.get("ProgramArguments", [])
    options = {"--source": "codex"}  # Original installations have no source option.
    for key in ("--source", "--sessions-root", "--port", "--workbuddy-root"):
        if key in arguments:
            index = arguments.index(key)
            if index + 1 < len(arguments):
                options[key] = arguments[index + 1]
    return options


def app_version() -> str | None:
    for directory in (Path("/Applications"), Path.home() / "Applications"):
        app = directory / "WorkBuddy.app" / "Contents" / "Info.plist"
        if app.is_file():
            with app.open("rb") as file:
                return str(plistlib.load(file).get("CFBundleShortVersionString", "unknown"))
    return None


def service_running() -> bool:
    result = subprocess.run(["launchctl", "print", f"gui/{os.getuid()}/{installer.LABEL}"],
                            capture_output=True, text=True, timeout=5)
    return result.returncode == 0 and "state = running" in result.stdout


def verify_installation(log_offset: int, seconds: float) -> bool:
    """Use this launch's PING/PONG result, without opening a competing USB handle."""
    deadline = time.monotonic() + seconds
    log = installer.locations()[2] / "bridge.log"
    running = False
    while True:
        running = service_running()
        recent = ""
        if log.is_file():
            with log.open("rb") as file:
                file.seek(log_offset)
                recent = file.read().decode("utf-8", errors="replace")
        present = set(bridge.serial_candidates())
        connected = set(re.findall(r"^Motor connected: (.+)$", recent, flags=re.MULTILINE)) & present
        if running and connected:
            print("安装自检通过：登录自启服务正在运行，USB 开发板已通过 PING/PONG 握手。")
            print("已连接：" + ", ".join(sorted(connected)))
            print("本轮 WorkBuddy 任务完成后，小花应停转；请目视确认一次。")
            return True
        if time.monotonic() >= deadline:
            break
        time.sleep(0.5)
    if running:
        print("后台服务已安装并运行；USB 握手尚未通过，尚不能报告全部安装成功。", file=sys.stderr)
        print("请检查 USB 数据线、连接与串口占用，然后重新运行此安装文件。", file=sys.stderr)
    else:
        print("后台服务自检未通过，请检查 bridge-error.log 中的新错误。", file=sys.stderr)
    return False


def status(root: Path) -> bridge.WorkBuddyDatabaseAdapter:
    adapter = bridge.WorkBuddyDatabaseAdapter(root)
    adapter.poll()
    print(f"WorkBuddy 版本：{app_version() or '未在应用程序文件夹找到'}")
    print(f"状态目录：{root}")
    print(f"任务状态统计：{adapter.status_counts}；匹配的运行进程：{adapter.live_workers}")
    if adapter.last_error:
        print(f"状态读取：{adapter.last_error}")
    print(f"当前 WorkBuddy 电机指令：{adapter.selected()[0]}")
    print(f"USB 候选端口：{', '.join(bridge.serial_candidates()) or '未发现，请检查数据线'}")
    options = existing_options()
    if options:
        print(f"已安装桥接服务，来源：{options['--source']}")
        running = service_running()
        print(f"服务状态：{'运行中' if running else '未运行'}")
    else:
        print("尚未安装小花后台服务")
    print(f"日志位置：{installer.locations()[2] / 'bridge.log'}")
    return adapter


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("install", "status", "uninstall"))
    parser.add_argument("--workbuddy-root", type=Path, default=bridge.default_workbuddy_root())
    parser.add_argument("--verify-seconds", type=float, default=0,
                        help="After installation, wait for service + fresh USB handshake (0 disables)")
    args = parser.parse_args(argv)
    if not 0 <= args.verify_seconds <= 30:
        parser.error("--verify-seconds 必须在 0 到 30 秒之间")
    if sys.platform != "darwin":
        parser.error("此安装入口仅支持 Mac")
    try:
        if args.action == "status":
            adapter = status(args.workbuddy_root)
            return 1 if adapter.last_error else 0
        previous = existing_options()
        sessions_root = Path(previous.get("--sessions-root", str(
            Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))) / "sessions")))
        port = previous.get("--port", "auto")
        if args.action == "uninstall":
            if previous.get("--source") == "both":
                installer.install(True, sessions_root, port, source="codex")
                print("已移除 WorkBuddy 支持，保留 Codex 桥接。")
            elif previous.get("--source") == "workbuddy":
                installer.uninstall()
            else:
                print("当前未安装 WorkBuddy 桥接，无需卸载。")
            return 0
        if app_version() is None:
            raise RuntimeError("请先将 WorkBuddy 拖入“应用程序”，打开并登录。")
        adapter = status(args.workbuddy_root)
        if adapter.last_error or not adapter.status_counts:
            raise RuntimeError("请先在 WorkBuddy 桌面端发一条普通消息，等回复完成后重新安装。")
        source = "both" if previous.get("--source") in ("codex", "both") else "workbuddy"
        log_offset = installer.install(bool(previous), sessions_root, port, source, args.workbuddy_root)
        if args.verify_seconds and not verify_installation(log_offset, args.verify_seconds):
            return 3
        print("安装完成。请插入小花，在 WorkBuddy 发起一个本地任务，观察开始转动和结束停转。")
        print("WorkBuddy 映射：快速慢转、均衡中转、极致快转；独立模型统一中转。首次使用请观察本机转停。")
        return 0
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        print(f"未完成：{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
