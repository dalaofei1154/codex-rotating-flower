# WorkBuddy Mac setup / WorkBuddy Mac 安装

[English README](../README.md) · [中文首页](../README.zh-CN.md)

## Download and install

Download [v0.3.0](https://github.com/dalaofei1154/rotating-flower/releases/download/v0.3.0/rotating-flower-workbuddy-macos-v0.3.0.zip). The release includes `SHA256SUMS.txt` for the ZIP. This installs the Mac bridge only; it does not flash firmware.

Use an Apple Silicon Mac with WorkBuddy installed and signed in, an assembled ESP32 flower already flashed with the [existing firmware](../m0/motor_control/motor_control.ino), and a USB data cable. Complete one local WorkBuddy task to initialize its records. The launcher needs Python 3.9+ and can reuse WorkBuddy's bundled Python; it does not install a runtime or third-party packages.

Extract the ZIP, then either ask WorkBuddy to follow `INSTALL.md` using the included versioned script, or run it yourself:

```sh
/bin/bash "/path/to/rotating-flower-workbuddy-macos-v0.3.0.sh"
```

Use the actual extracted path. The script installs a user background service and checks both the service and a fresh USB handshake. Approve required macOS or application prompts yourself. Exit code `0` means both checks passed; `3` means installation was saved but connection verification did not pass. Other nonzero codes indicate an error. Check physical start/stop after installation; successful communication alone does not measure motor movement or noise.

The package supports source inspection, diagnostics and removal:

```sh
/bin/bash "/path/to/rotating-flower-workbuddy-macos-v0.3.0.sh" inspect
/bin/bash "/path/to/rotating-flower-workbuddy-macos-v0.3.0.sh" status
/bin/bash "/path/to/rotating-flower-workbuddy-macos-v0.3.0.sh" uninstall
```

`inspect` prints the bundled source without installing it. `status` is read-only; its exit code does not prove a USB handshake. Removing WorkBuddy support preserves Codex if both were enabled. Reinstalling backs up the previous service and keeps the currently enabled sources, Codex session path and selected USB port. The service runs after Mac login; the download folder is not needed afterward.

## 中文安装步骤

1. 下载上面的 ZIP 并解压；接好已烧录的小花，在 WorkBuddy 完成一次本地任务。
2. 把 `rotating-flower-workbuddy-macos-v0.3.0.sh` 和 `INSTALL.md` 添加到 WorkBuddy，发送：

   > 请按本次附件 INSTALL.md 安装 Rotating Flower。只使用本次附上的 v0.3.0 脚本，先 inspect 检查源码，再执行同一脚本。保留当前已启用来源，不根据历史备份恢复停用来源，不手改服务配置。报告实际退出码、后台服务状态和本次 USB 握手结果；需要系统授权时告诉我该点哪里。

3. 系统授权由你确认。两项自检通过后发起一个普通任务，目视确认转动；其他 Codex/WorkBuddy 任务全部结束后确认停转。

首次连接先解锁 Mac，如出现 USB 配件提示，允许本次连接。若无端口，检查线缆是否支持数据、设备是否连接，关闭占用串口的 Arduino 串口监视器或额外桥接进程。若缺少 Python，可先让 WorkBuddy 用自身 Python 执行 `print(1+1)`，再安装；不需要因此安装 Xcode。

安装包会复用可用运行时。退出码 `0` 表示服务和 USB 两项通过，`3` 表示已保存服务但连接验证失败，不能算全部成功。`status` 是只读诊断，不能用它的退出码替代 USB 自检。

## Mapping and task behavior / 映射

| WorkBuddy selection | Command |
| --- | --- |
| Fast / 快速 (`fast-model`) | `RUN LOW` |
| Balanced / 均衡 (`balanced-model`) | `RUN HIGH` |
| Deep / 极致 (`deep-model`) | `RUN ULTRA` |
| Independent / unknown nonempty model | `RUN HIGH` |
| Missing / blank model metadata | `RUN LOW` |

These presets express the selected product mode, not measured compute, intelligence or token throughput. WorkBuddy's mode switch during a turn applies to the next turn. The bridge remembers the tier observed at task start; pause/resume keeps that tier. Multiple active tasks use the highest tier, including Codex when `--source both` is enabled. Waiting tasks do not contribute; all inactive means `STOP`. Completion and cancellation may use the same database status, so the bridge does not invent distinct success/error animations.

快速、均衡、极致对应慢、中、快三档。它们是体验映射，不按独立模型的品牌排名。任务中途切选项下一轮生效；等待确认暂停、恢复继续。并行任务取最高档，有其他任务仍在工作时不会停花。

## Run and build from source

```sh
python3 m1/global_bridge.py --source workbuddy --once
python3 m1/global_bridge.py --source workbuddy --no-motor
python3 m1/workbuddy_setup.py install --verify-seconds 12
python3 m1/workbuddy_setup.py status
python3 m1/workbuddy_setup.py uninstall
```

The first two commands only observe state. Only run one motor-controlling bridge at a time. The setup entry point adds WorkBuddy to an existing Codex service, or creates a WorkBuddy-only service for a new user. To build the same installer from the repository:

```sh
python3 m1/package_workbuddy_oneclick.py --output dist/workbuddy-v0.3.0
python3 -m unittest discover -s m1 -p 'test_*.py' -v
```

The package explicitly includes four runtime files, setup instructions and the MIT license. The generated manifest records source hashes; no 3D models, application databases, credentials or user configuration are bundled. ZIP timestamps can vary between builds; compare the manifest's source hashes when checking a rebuild.

## Validation, privacy and limits

WorkBuddy 5.9.3 on the maintainer's Apple Silicon Mac was checked for all three presets, independent-model fallback, parallel fallback, cancellation, waiting and resumption against a real ESP32 controller. v0.3.0 installation passed with a fresh USB handshake and final STOP. There are 42 automated tests. Other Macs, actual reboot behavior and long-running use have not been independently verified; latest preset tests did not verify noise or measured RPM.

The adapter opens the WorkBuddy database read-only and reads task IDs, statuses, timestamps, mode metadata and worker-process records. It does not read conversation titles, prompts, message bodies or credentials, change WorkBuddy settings, or upload data. Codex retains its existing local task-log adapter.

Internal data formats may change. Only local workers are supported. A task with no state update for 10 minutes stops contributing; firmware stops after 30 seconds without `RUN`. On restart, metadata recovery or missed task boundaries, the current selected configuration may not identify the exact in-flight turn. Treat the displayed tier as a best-effort selected-mode mapping.

Logs are in `~/Library/Logs/RotatingFlower/`. When reporting a problem, share only a short redacted excerpt with application/version details. Do not upload WorkBuddy databases, worker records, Codex sessions or private files.

当前仅验证维护者本机，其他电脑和长期运行仍需确认。桥接依赖内部数据结构；中途重启、元数据恢复或漏采任务边界时，档位只能按当前配置推断，不承诺逐请求完全准确。报错时只提供脱敏片段，勿上传数据库、会话文件或私人资料。
