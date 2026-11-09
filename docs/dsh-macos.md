# DeepSeek Harness 支持 · v0.7.0

[v0.7.0 安装包](https://github.com/dalaofei1154/rotating-flower/releases/download/v0.7.0/RotatingFlower-Mac-v0.7.0.zip)已包含 DSH 适配，同时支持 Codex 和 WorkBuddy。小花会跟着 DSH 的任务转动，等待你回答或授权时亮起提醒灯。

当前适配对象为 **DeepSeek Harness 0.2.1-rc.5**，运行于 **Apple 芯片 Mac、macOS 13+**。本版于 **2026 年 11 月 9 日**发布；[查看版本说明](open-release/RELEASE_NOTES.md)。

## 使用安装包

1. 先安装并打开一次 DSH，让它生成本机配置，然后退出应用。
2. 下载并解压 v0.7.0，连接已烧录旋转＋提醒灯固件的小花，双击 `安装小花.command`。安装器会自动识别已安装的应用并注册 DSH 插件，包内自带 Python。
3. 退出并重新打开 DSH，开始一个任务，检查工作时转动、等待问卡时停转亮灯、完成后停转灭灯。

升级、卸载、下载校验和常见退出码见[统一安装指南](open-release/INSTALL.md)。

## 从源码安装（可选）

本版源码在 [v0.7.0 标签的 m1 目录](https://github.com/dalaofei1154/rotating-flower/tree/v0.7.0/m1)。准备好已烧录[旋转＋提醒灯组合固件](../firmware/README.md)的小花和 USB 数据线。源码安装需要 Python 3.9 或更新版本；安装后仍需保留该 Python，因为后台使用同一个解释器运行。

1. 安装并至少打开一次 DeepSeek Harness，使其生成本机配置；随后退出应用。
2. 连接小花，在当前源码仓库根目录运行：

   ```sh
   python3 m1/integrated_setup.py install --source dsh
   ```

   统一安装器会同时安装后台并注册 DSH 本地插件。与已有应用一起使用时，用逗号组合：`--source codex,dsh`、`--source workbuddy,dsh`，或用 `--source all` 启用三者。所选应用需要已安装。

3. 重新打开 DeepSeek Harness，开始一个任务，检查转动、等待时的提醒灯以及任务结束后的停转。首次安装时若提示 DSH 尚未运行或初始化，请先完成这一步。

安装器只管理 `cordis.patch.yml` 中带有 `ROTATING-FLOWER DSH OBSERVER` 标记的小花区块，重复执行不会重复注册。改动前保留备份；安装失败时回滚本次写入，并保留安装期间发生的外部编辑。DSH 运行中更新插件后，需要重启应用才能加载新代码。

## 独立维护插件

统一安装已包含插件注册。需要单独检查、更新或移除插件时，可在源码目录使用：

```sh
python3 m1/dsh_setup.py status
python3 m1/dsh_setup.py install
python3 m1/dsh_setup.py uninstall
```

独立插件命令不安装小花后台服务。安装或卸载插件后，退出并重新打开 DSH。默认使用 `desktop` profile；其他 profile 的操作选项见 `python3 m1/dsh_setup.py --help`。

## 卸载

安装包用户双击 `卸载小花.command`。从源码安装的用户也可运行：

```sh
python3 m1/integrated_setup.py uninstall
```

统一卸载会移除小花后台服务与 DSH 插件注册，Codex、WorkBuddy、DSH 的小花联动一起停止。AI 应用、备份和日志保留；随后重启 DSH，使插件停止运行。如果只想停用 DSH 插件而保留其他来源，可以使用上面的独立插件卸载命令。

## 小花怎样响应

| DSH 推理等级 | 小花转速档位 |
| --- | --- |
| off / none / minimal | LOW |
| low / medium | MEDIUM |
| high | HIGH |
| xhigh | XHIGH |
| max | ULTRA |

- 工作时转动，完成或取消后停止。识别不了的等级按 HIGH 处理。
- 任务暂停等待回答或授权时，呼吸灯亮起；若没有其他任务在运行，小花同时停转。
- 有些问题允许工作继续，小花会一边转动、一边亮灯。
- Codex、WorkBuddy、DSH 可以一起使用。多任务同时工作时采用最高的活动档位，任一任务需要你处理时亮灯。
- 关闭 DSH 后，它的任务状态不再参与控制；其他应用继续联动。重新打开 DSH 后自动恢复。

<a id="本地数据与边界"></a>

## 本地数据

插件在本机处理 DSH 的事件和状态投影，从中提取任务状态、模型与推理等级，以及待处理问题和授权的数量。状态摘要保存在 `~/Library/Application Support/RotatingFlower/dsh/status.json`，由小花后台统一通过 USB 控制电机和灯。

摘要包含会话 ID、运行/阻塞标志、模型名、推理等级、待处理计数，以及心跳时间、进程标识等连接信息。插件不把提示词、问题正文、回答或账号凭据写入状态摘要，也不上传任务数据。你可以在 DSH 的 `cordis.patch.yml` 中查看插件注册区块。

## 当前边界与验证

- DSH 的插件与运行时接口可能随应用更新变化。接口持续不兼容时，后台会报告“任务状态无法验证”。
- 状态变化时立即写入，否则每 1 秒刷新心跳；心跳超过 3 秒没有更新就按“DSH 未运行”处理。
- 读取接口偶发失败会沿用上一次正常状态，连续 3 次失败才判定为不兼容；失败的事件会在恢复后重新读取。
- 该适配假设本机只运行一个 DSH 实例。
- 2026 年 11 月 9 日，在 Apple 芯片 Mac（arm64、macOS 26.6.2）上连接真实控制板验证了 DSH 链路。用户目视确认：工作时转动、等待问卡时停转亮灯、任务结束后停转灭灯；本次验证未观察到错误或断连。
- 自动化测试另覆盖状态判断、授权事件、安装回滚和打包内容。授权弹窗仍未做实机验证。
- 本版不包含 Windows 支持，也未做 Windows 实机验证。

[返回中文首页](../README.zh-CN.md) · [English home](../README.md)

## English

The [v0.7.0 installer](https://github.com/dalaofei1154/rotating-flower/releases/download/v0.7.0/RotatingFlower-Mac-v0.7.0.zip), released on **November 9, 2026**, includes DSH alongside Codex and WorkBuddy. The flower spins while a DSH task runs and lights up when a question or approval needs attention.

The adapter targets **DeepSeek Harness 0.2.1-rc.5**, **Apple silicon Macs and macOS 13+**, with one DSH instance per machine.

### Install the package

1. Install and open DSH at least once to create its local profile, then quit it.
2. Download and extract v0.7.0, connect a flower running the combined motor-and-light firmware, and double-click `安装小花.command`. The installer includes Python, detects installed apps and registers the local DSH plugin.
3. Quit and reopen DSH to load the plugin, then start a task and check rotation, attention lights and stopping.

See the [installation guide](open-release/INSTALL.md#en) for upgrades, removal, checksums and exit codes.

### Install from source (optional)

Use the [v0.7.0 source](https://github.com/dalaofei1154/rotating-flower/tree/v0.7.0/m1), a flower with the [combined motor-and-light firmware](../firmware/README.md) and a USB data cable. Python 3.9 or newer is required and must remain installed: the background service uses the same interpreter.

1. Install and open DSH at least once to create its local profile, then quit it.
2. Connect the flower and run this from the current source checkout:

   ```sh
   python3 m1/integrated_setup.py install --source dsh
   ```

   This installs the bridge and registers the local DSH plugin together. Use `--source codex,dsh`, `--source workbuddy,dsh` or `--source all` for multiple installed apps.

3. Reopen DSH and start a task. Check rotation, attention lights and stopping. If setup reports that DSH is not running or initialized, complete this step first.

The installer backs up changes and manages its marked block in `cordis.patch.yml`. Repeated installation does not duplicate the block. Failed installation rolls back its writes while preserving concurrent external edits. Restart DSH after updating the plugin.

### Maintain or remove

`python3 m1/dsh_setup.py status` checks plugin registration. Its `install` and `uninstall` actions maintain the plugin alone; they do not install the bridge. See `--help` for profile options.

Package users can double-click `卸载小花.command`. For a source installation, remove the bridge and plugin registration together with:

```sh
python3 m1/integrated_setup.py uninstall
```

This stops flower integration for all configured apps. Backups, logs and the AI apps remain. Restart DSH afterwards to unload the plugin.

### Behavior and local data

Reasoning effort maps to motor speed: off/none/minimal → LOW, low/medium → MEDIUM, high → HIGH, xhigh → XHIGH, max → ULTRA. Blocking questions and approvals pause that task's motor contribution. An asynchronous question can keep the light on while work continues; other active tasks also keep the flower moving.

The plugin processes local DSH events and projections and writes `~/Library/Application Support/RotatingFlower/dsh/status.json`. The summary contains session IDs, running/blocking flags, model, effort, pending counts and connection metadata. It does not store prompts, question bodies, answers or credentials, and the plugin does not upload task data.

Changed state is written immediately; otherwise a heartbeat is written once a second. A heartbeat older than three seconds is treated as DSH not running. Transient read failures retain the last good state; three consecutive failures report an unsupported interface, and failed events are retried on recovery.

On November 9, 2026, the DSH path was tested with a real controller on an Apple silicon Mac (arm64, macOS 26.6.2). The user visually confirmed rotation while working, stopping with the light on while a question card waited, and stopping with the light off after completion. No errors or disconnections were observed during this check.

Automated tests also cover state handling, approval events, installer rollback and package contents. Approval dialogs have not yet been tested with physical hardware. This release does not include Windows support or Windows hardware validation.
