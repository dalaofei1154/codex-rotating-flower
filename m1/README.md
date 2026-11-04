# Current Mac installer / 当前 Mac 安装器

Use the [v0.6.0 unified installer](../docs/install-macos.md) for Codex + WorkBuddy rotation and attention lights. It includes Python and detects installed apps. The commands below are the historical motor-only implementation and must not replace the unified service.

旋转与提醒灯请使用 [统一安装说明](../docs/install-macos.md)。下方保留旧版纯旋转程序的文档；不要用旧安装命令覆盖统一后台。

---

# Mac bridge: Codex + WorkBuddy

[简体中文](#中文说明)

[WorkBuddy download and setup / 下载与安装](../docs/workbuddy-macos.md)

WorkBuddy on macOS has a trial adapter tested with version 5.8.3 and real ESP32 hardware (start, finish, cancel, and parallel tasks; physical movement confirmed by the user). See [Mac setup and verification notes](../docs/workbuddy-macos.md). The 2026-10-31 adapter maps WorkBuddy 5.9.3 product modes: fast → LOW, balanced → HIGH, deep → ULTRA; independent models use HIGH, and missing model metadata keeps LOW. This represents selected work modes, not measured cloud compute. The default source remains Codex; select `--source workbuddy` or `--source both` to enable WorkBuddy.

The bridge watches **local** tasks on one Mac. Codex is the default source; WorkBuddy is available with `--source workbuddy`, or use `--source both` for both apps. When a task starts, it sends the same speed command to all connected flowers over USB. When all tasks finish, it sends `STOP` to each flower. If several tasks are active, it uses the fastest setting. It discovers newly plugged-in flowers and reconnects if USB port names change.

Upload [the ESP32 firmware](../m0/motor_control/motor_control.ino) and test `PING`, `RUN LOW`, and `STOP` in Arduino Serial Monitor before running the bridge. Close Serial Monitor afterward; it cannot share the port with the bridge.

## Try it in Terminal

From the repository root:

```sh
python3 m1/global_bridge.py --once
python3 m1/global_bridge.py
```

`--once` prints the task state it sees without opening USB. The second command keeps running and controls all devices that answer `PING` with `PONG`. To control just one flower, add `--port /dev/cu.usbmodemXXXX` using the **actual** port name. Press Ctrl+C to send `STOP` to all connected flowers and exit. Matching speed commands do not guarantee identical physical RPM or flower angles.

## Start it automatically when you log in

Once the manual test works:

```sh
python3 m1/install_macos.py install
```

The installer copies the bridge to `~/Library/Application Support/RotatingFlower/` and creates a macOS LaunchAgent. Its log is `~/Library/Logs/RotatingFlower/bridge.log`. The launcher first tries the Python used during installation, then WorkBuddy's bundled Python and common Homebrew/system locations. A working Python 3.9 or newer must remain available; the installer does not download a runtime.

To update or remove it:

```sh
python3 m1/install_macos.py install --replace
python3 m1/install_macos.py uninstall
```

The update command above is for a **Codex-only** installation; its default source is `codex`. If the installed service supports WorkBuddy or both apps, update it with `python3 m1/workbuddy_setup.py install` to retain that support, the existing Codex task directory, and any selected USB port.

Uninstalling keeps the logs. The bridge looks for sessions in your `CODEX_HOME` folder (default `~/.codex`). You can pass `--sessions-root` if yours is elsewhere.

## Check that it works

1. Start a local Codex task at LOW. The log should show `Codex active: 1` and `Motor: RUN LOW`.
2. While it is still running, start another local task at HIGH. The motor should switch to HIGH.
3. When HIGH ends, the motor should return to LOW. It should stop after both tasks finish.

The bridge reads Codex's local task files. That file format can change, so retest after Codex updates. It currently handles local and worktree tasks on a Mac; it does not handle cloud tasks or Windows. If a task record disappears, the bridge removes it on the next poll. A record that still exists but has not been updated for 10 minutes also stops contributing an active state. The ESP32 stops the motor after 30 seconds without a `RUN` command.

## 中文说明

这个程序读取同一台 Mac 上的**本地**任务状态，默认跟随 Codex；用 `--source workbuddy` 跟随 WorkBuddy，或 `--source both` 跟随两者，通过 USB 向所有已连接的花发送相同速度命令。多个任务同时运行时取最高档；全部结束后向每朵花发送 `STOP`。运行中插入的新花会自动跟随当前状态；USB 串口名称变化时，程序会尝试重新连接。同步档位不保证实际转速或花瓣角度完全相同。

先上传[电机固件](../m0/motor_control/motor_control.ino)，在 Arduino 串口监视器里手动试通 `PING`、`RUN LOW` 和 `STOP`，然后**关闭串口监视器**。

在仓库根目录运行：

```sh
python3 m1/global_bridge.py --once
python3 m1/global_bridge.py
```

`--once` 只显示识别到的任务状态，不连接电机。第二条命令会持续运行，自动控制所有能以 `PONG` 回应 `PING` 的设备。如果只想控制一朵，可以用 `--port /dev/cu.usbmodemXXXX` 指定实际端口。按 Ctrl+C 会向所有已连接的花发送 `STOP` 并退出。

确认手动运行正常后，可以安装为 Mac 登录后自动运行的用户服务：

```sh
python3 m1/install_macos.py install
```

日志在 `~/Library/Logs/RotatingFlower/bridge.log`。**仅 Codex 的安装**用 `python3 m1/install_macos.py install --replace` 更新；已有 WorkBuddy 或两者共用的服务，用 `python3 m1/workbuddy_setup.py install` 更新，以保留已有支持、Codex 任务目录和指定串口。通用安装器的默认来源是 `codex`。完整卸载用 `python3 m1/install_macos.py uninstall`，日志会保留。

启动脚本优先使用安装时的 Python；不可用时会尝试 WorkBuddy 内置 Python，以及常见 Homebrew／系统路径。电脑上仍需保留可用的 Python 3.9 或更新版本，安装器不会下载运行时。

测试跨窗口时，可以先启动 LOW 任务，再启动 HIGH 任务：电机应切到 HIGH；HIGH 结束而 LOW 仍在运行时，应回到 LOW；全部结束后停转。

程序依赖 Codex 的本地任务文件格式，Codex 更新后可能需要调整。当前只支持 Mac 上的本地和 worktree 任务，不支持云端任务或 Windows。任务记录如果消失，会在下一次轮询时移除；记录仍存在但连续 10 分钟无更新，也会停止贡献运行状态。ESP32 收不到新的 `RUN` 命令满 30 秒会停机。
