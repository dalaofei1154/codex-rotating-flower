# Mac 安装与升级 · Installation and upgrades

[中文](#zh) · [English](#en) · [返回首页 / Project home](../../README.md)

<a id="zh"></a>

## 中文

### 下载

**[下载 v0.7.0 安装包](https://github.com/dalaofei1154/rotating-flower/releases/download/v0.7.0/RotatingFlower-Mac-v0.7.0.zip)** · [版本说明](https://github.com/dalaofei1154/rotating-flower/releases/tag/v0.7.0)

v0.7.0 支持 Codex、WorkBuddy 和 DeepSeek Harness（DSH），会自动启用电脑上已安装的应用。DSH 的适配版本与实测范围见[适配说明](../dsh-macos.md)。本版不包含 Windows 支持。

### 安装前准备

- Apple 芯片 Mac，macOS 12 或以上；使用 DSH 时需要 macOS 13 或以上。
- 已安装 Codex、WorkBuddy 或 DSH，使用自己的账号登录应用。DSH 需要先打开至少一次，生成本机配置后再安装小花。
- 已装好并烧录[旋转＋提醒灯组合固件](../../firmware/README.md)的小花，以及 USB 数据线。

安装包自带 Python，不需要另外安装运行环境或填写 API Key。包还没有签名、公证，macOS 可能会要求确认打开文件或允许 USB 配件连接，按系统提示操作即可。

### 三步安装

1. 用 USB 数据线连接小花，下载并解压 ZIP。
2. 双击 `安装小花.command`，按窗口提示安装。
3. 打开并登录所用应用，开始一个任务，看看小花的转动、停转和提醒灯。DSH 需要在安装后退出并重新打开，以加载插件。

安装器自动识别 Codex、WorkBuddy 和 DSH，并为 DSH 注册本地插件。安装后后台会在登录 Mac 时启动，解压文件夹可以删除。

### 安装结果与退出码

安装器会检查后台服务、应用状态和控制板连接。

| 退出码 | 含义 | 下一步 |
| --- | --- | --- |
| `0` | 后台运行、应用就绪，旋转与提醒灯控制板已连接 | 开始任务，检查小花的动作 |
| `5` | 已安装且控制板连接通过，应用尚未打开或初始化 | 打开、登录应用并开始任务；后台会自动连接，不必重装 |
| `4` | 控制板缺少提醒灯固件支持 | 按[组合固件说明](../../firmware/README.md)检查和烧录 |
| `3` | 后台设置已保存，但应用状态或 USB 连接检查未通过 | 根据日志检查应用、数据线、USB 连接许可和固件 |
| `1` | 安装未完成，或另一安装程序仍在运行 | 查看终端中的具体错误；若是并发安装，等前一个结束 |

如果提示找不到 DSH 配置，先打开一次 DSH，然后重新运行安装器。应用数据损坏或版本不兼容时，窗口会显示具体错误。反馈问题时请附上错误提示和应用版本，分享日志前删去私人信息。

### 升级、增加应用与卸载

从 v0.6.0 升级时，运行 v0.7.0 安装包即可。如果之后又安装了 Codex、WorkBuddy 或 DSH，重新运行安装器即可识别并启用它；新装的 DSH 仍需先打开一次。安装过程会保留备份和日志，安装失败时回滚本次配置改动。

双击 `卸载小花.command` 可移除小花后台服务、登录自启和 DSH 插件注册，三个应用的小花联动会一起停止。备份、日志和 AI 应用会保留。卸载后退出并重新打开 DSH，使插件停止运行。

### 校验下载与查看源码

文件名：`RotatingFlower-Mac-v0.7.0.zip`

SHA256：

```text
ede5370522558ab2a2bc49f4c9c4afded89d20d04c55a48263457e13923dbf3b
```

在终端输入 `shasum -a 256 `，将下载的 ZIP 拖入终端补全路径，按回车后与上面的值核对。

安装包对应的运行代码在 [v0.7.0 源码目录](https://github.com/dalaofei1154/rotating-flower/tree/v0.7.0/m1)。需要通过终端安装时，可以使用[固定版本安装脚本](https://github.com/dalaofei1154/rotating-flower/blob/v0.7.0/m1/install_unified_release.sh)，脚本会下载并校验同一个 ZIP。

<a id="data"></a>

### 本地数据

小花软件读取本机任务状态，通过 USB 控制小花，不向项目服务器上传任务记录。

- **WorkBuddy：** 读取任务与进程元数据，包括状态和模式信息。
- **Codex：** 读取本地运行状态和 rollout 记录来识别问题卡，保留状态与标识，不保存问题正文。
- **DSH：** 本地插件处理事件和状态投影，将运行/阻塞标志、推理等级与待处理计数等元数据写入摘要，不保存提示词、问题正文、回答或凭据。[详细说明](../dsh-macos.md#本地数据与边界)

应用更新可能改变本地数据格式。如果更新后联动出现问题，请反馈应用版本和现象。

<a id="en"></a>

## English

### Download

**[Download v0.7.0](https://github.com/dalaofei1154/rotating-flower/releases/download/v0.7.0/RotatingFlower-Mac-v0.7.0.zip)** · [Release notes](https://github.com/dalaofei1154/rotating-flower/releases/tag/v0.7.0)

v0.7.0 supports Codex, WorkBuddy and DeepSeek Harness (DSH), automatically enabling the installed apps. See the [DSH notes](../dsh-macos.md#english) for its supported version and validation scope. This release does not include Windows support.

### Before installing

- An Apple silicon Mac running macOS 12 or later; DSH support requires macOS 13 or later.
- Codex, WorkBuddy or DSH installed, using your own account. Open DSH at least once before installing the flower so it can create its local profile.
- An assembled flower with the [combined motor-and-light firmware](../../firmware/README.md), plus a USB data cable.

Python is included, and no separate runtime or API key is needed. The package is unsigned and unnotarized, so macOS may ask you to confirm opening a file or allow the USB accessory. Follow the system prompts.

### Install

1. Connect the flower, download the ZIP and extract it.
2. Double-click `安装小花.command` and follow the prompts.
3. Open and sign in to your app, start a task, and check rotation, stopping and the attention light. Quit and reopen DSH after installation to load its plugin.

The installer detects Codex, WorkBuddy and DSH and registers the local DSH plugin. The service starts when you log in to your Mac. You can delete the extracted download folder after installation.

### Exit codes

The installer checks the background service, app status and controller connection.

| Code | Meaning | What to do |
| --- | --- | --- |
| `0` | Service running, apps ready, motor-and-light controller connected | Start a task and check the flower |
| `5` | Installed and controller connected; an app is not open or initialized | Open and sign in to the app, then start a task; the service connects automatically |
| `4` | The controller lacks attention-light firmware support | Check and flash the [combined firmware](../../firmware/README.md) |
| `3` | Settings saved, but an app or USB check failed | Read the log and check the app, data cable, USB permission and firmware |
| `1` | Installation failed, or another installer is running | Read the specific error; wait if another installation is in progress |

If setup reports a missing DSH profile, open DSH once and rerun the installer. Damaged app data or an incompatible version produces a specific error. Include that message and your app version when reporting a problem, and remove private information from logs before sharing them.

### Upgrade, add an app or uninstall

Run the v0.7.0 installer to upgrade from v0.6.0. If you later install Codex, WorkBuddy or DSH, run the installer again to detect and enable it; open a newly installed DSH at least once first. Backups and logs are retained, and a failed installation rolls back its configuration changes.

Double-click `卸载小花.command` to remove the flower's background service, login startup and DSH plugin registration. This stops flower integration for all three apps. Backups, logs and the AI apps remain. Quit and reopen DSH afterwards to unload the plugin.

### Checksum and source

File: `RotatingFlower-Mac-v0.7.0.zip`

SHA256:

```text
ede5370522558ab2a2bc49f4c9c4afded89d20d04c55a48263457e13923dbf3b
```

Type `shasum -a 256 ` in Terminal, drag in the downloaded ZIP to insert its path, then press Return and compare the result with the value above.

The runtime code for this installer is in the [v0.7.0 source directory](https://github.com/dalaofei1154/rotating-flower/tree/v0.7.0/m1). For Terminal installation, use the [versioned installation script](https://github.com/dalaofei1154/rotating-flower/blob/v0.7.0/m1/install_unified_release.sh), which downloads and verifies the same ZIP.

### Local data

The bridge reads local task status and sends control commands over USB. It does not upload task records to a project server.

- **WorkBuddy:** reads task and process metadata, including status and mode settings.
- **Codex:** reads local runtime and rollout records to recognize questions, retaining state and identifiers without saving question text.
- **DSH:** a local plugin processes events and projections, retaining metadata such as running/blocking flags, reasoning effort and pending counts. The summary does not store prompts, question bodies, answers or credentials. [Details](../dsh-macos.md#english).

App updates may change local data formats. If the connection stops working after an update, report the app version and what happened.
