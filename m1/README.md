# Mac bridge: link Codex to the motor

[简体中文](#中文说明)

The bridge watches your **local** Codex tasks on one Mac. When a task starts, it sends a speed command to the ESP32 over USB. When all tasks finish, it sends `STOP`. If several tasks are active, it uses the fastest setting. It can reconnect if the USB port name changes.

Upload [the ESP32 firmware](../m0/motor_control/motor_control.ino) and test `PING`, `RUN LOW`, and `STOP` in Arduino Serial Monitor before running the bridge. Close Serial Monitor afterward; it cannot share the port with the bridge.

## Try it in Terminal

From the repository root:

```sh
python3 m1/global_bridge.py --once
python3 m1/global_bridge.py
```

`--once` prints the task state it sees without opening USB. The second command keeps running and searches for an ESP32 that answers `PING`. If you have several serial devices, add `--port /dev/cu.usbmodemXXXX` using the **actual** port name. Press Ctrl+C to send `STOP` and exit.

## Start it automatically when you log in

Once the manual test works:

```sh
python3 m1/install_macos.py install
```

The installer copies the bridge to `~/Library/Application Support/RotatingFlower/` and creates a macOS LaunchAgent. Its log is `~/Library/Logs/RotatingFlower/bridge.log`. It uses your current Python executable, so keep that Python installation available.

To update or remove it:

```sh
python3 m1/install_macos.py install --replace
python3 m1/install_macos.py uninstall
```

Uninstalling keeps the logs. The bridge looks for sessions in your `CODEX_HOME` folder (default `~/.codex`). You can pass `--sessions-root` if yours is elsewhere.

## Check that it works

1. Start a local Codex task at LOW. The log should show `Codex active: 1` and `Motor: RUN LOW`.
2. While it is still running, start another local task at HIGH. The motor should switch to HIGH.
3. When HIGH ends, the motor should return to LOW. It should stop after both tasks finish.

The bridge reads Codex's local task files. That file format can change, so retest after Codex updates. It currently handles local and worktree tasks on a Mac; it does not handle cloud tasks or Windows. If a task record disappears, the bridge stops treating it as active after 10 minutes without updates. The ESP32 also stops the motor after 30 seconds without a `RUN` command.

## 中文说明

这个程序读取同一台 Mac 上的**本地** Codex 任务状态，通过 USB 向 ESP32 发送速度命令。多个任务同时运行时取最高档；全部结束后发送 `STOP`。USB 串口名称变化时，程序会尝试重新连接。

先上传[电机固件](../m0/motor_control/motor_control.ino)，在 Arduino 串口监视器里手动试通 `PING`、`RUN LOW` 和 `STOP`，然后**关闭串口监视器**。

在仓库根目录运行：

```sh
python3 m1/global_bridge.py --once
python3 m1/global_bridge.py
```

`--once` 只显示识别到的任务状态，不连接电机。第二条命令会持续运行。如果连了多个串口设备，可以用 `--port /dev/cu.usbmodemXXXX` 指定实际端口。按 Ctrl+C 会发送 `STOP` 并退出。

确认手动运行正常后，可以安装为 Mac 登录后自动运行的用户服务：

```sh
python3 m1/install_macos.py install
```

日志在 `~/Library/Logs/RotatingFlower/bridge.log`。更新代码用 `python3 m1/install_macos.py install --replace`；卸载用 `python3 m1/install_macos.py uninstall`，日志会保留。安装器会使用你当前的 Python 路径，之后不要移除该 Python 安装。

测试跨窗口时，可以先启动 LOW 任务，再启动 HIGH 任务：电机应切到 HIGH；HIGH 结束而 LOW 仍在运行时，应回到 LOW；全部结束后停转。

程序依赖 Codex 的本地任务文件格式，Codex 更新后可能需要调整。当前只支持 Mac 上的本地和 worktree 任务，不支持云端任务或 Windows。任务记录如果消失，10 分钟无更新后会失效；ESP32 收不到新的 `RUN` 命令满 30 秒也会停机。
