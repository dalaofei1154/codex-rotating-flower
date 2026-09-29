# Codex 全局电机桥接器（Mac 本地版）

这个进程监听当前用户在同一台 Mac 上的所有本地 Codex 主任务，跨窗口、跨项目工作。每个主任务独立记录「本轮是否正在运行」和推理强度；多个任务同时运行时取最高档，全部结束才发 `STOP`。新任务文件会自动发现，ESP32 的 `/dev/cu.usbmodem*` 串口变号后会重新寻找，并通过 `PING`/`PONG` 确认设备。

```text
各本地 Codex 任务 → CodexRolloutAdapter → 最高档仲裁 → MotorSerial → ESP32
```

ESP32 继续使用 `m0/motor_control/motor_control.ino`。协议不变：`RUN LOW`、`RUN MEDIUM`、`RUN HIGH`、`RUN XHIGH`、`RUN ULTRA`、`STOP`。`none/minimal/low` 映射 LOW，`max/ultra` 映射 ULTRA。某轮推理强度无法读取时暂按 MEDIUM 运行。中断事件也会关闭该任务的运行状态。

## 先在终端试运行

```sh
python3 m1/global_bridge.py --once
python3 m1/global_bridge.py
```

`--once` 只显示当前聚合结果，不打开串口。持续运行版自动搜索 ESP32；如果接了多个可响应 `PING` 的设备，可用 `--port /dev/cu.usbmodemXXXX` 明确指定。按 Ctrl+C 时会发送 `STOP`。

## 安装为 Mac 登录后的常驻服务

```sh
python3 m1/install_macos.py install
```

安装器把桥接脚本复制到 `~/Library/Application Support/RotatingFlower/`，在 `~/Library/LaunchAgents/` 安装一个用户服务；登录后自动运行，不依赖某一个 Codex 任务窗口。状态日志在 `~/Library/Logs/RotatingFlower/bridge.log`。更新代码后运行 `python3 m1/install_macos.py install --replace`。卸载命令是 `python3 m1/install_macos.py uninstall`，日志会保留。

朋友的 Mac 上，复制整个项目或至少 `m1` 与 ESP32 固件，先上传同一协议的固件，再在项目根目录执行安装命令。程序按该用户的 `CODEX_HOME`（或默认 `~/.codex`）找任务记录；可用 `--sessions-root` 覆盖。USB 端口通过 `PING`/`PONG` 自动识别，免去硬编码串口号。

## 验证跨窗口

1. 打开一个新 Codex 本地任务，选 LOW 后发起一轮，查看 `bridge.log` 中 `Codex active: 1` 与 `Motor: RUN LOW`。
2. 原任务仍运行时，在另一个本地任务选 HIGH 发起一轮，电机应切到 HIGH。
3. HIGH 结束，LOW 尚在运行时电机应回到 LOW；两个任务都结束后发出 `STOP`。

## 当前边界

- 这版面向同一台 Mac 上的 Codex 本地和 worktree 任务。云端任务在远端运行，本地 USB 电机收不到它们的任务记录；未来需加网络事件来源。
- 推理强度读取层使用本地 rollout 文件里的 `turn_context.effort`。这是当前 Codex 版本可用的内部格式，[官方 Hooks 文档](https://learn.chatgpt.com/docs/hooks)说明转录格式不是稳定接口，升级 Codex 后应复测。官方 Hook 有任务生命周期事件，但公开输入没有推理强度，因此本版把文件解析隔离在 `CodexRolloutAdapter`，便于将来替换。
- 如果任务突然消失而没有完成事件，最近 10 分钟没有更新的记录会失效；ESP32 本身也保留 30 秒没有 RUN 命令就关闭线圈的超时保护。
- Windows 尚未适配：它的串口枚举和连接方式与 Mac 不同。朋友若使用 Windows，需要实现 Windows 的 `MotorSerial` 后再安装。

官方环境说明：[本地、工作树与云端运行模式](https://learn.chatgpt.com/docs/environments/modes)。
