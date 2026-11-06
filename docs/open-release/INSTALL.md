# Mac 安装与升级 · Installation and upgrades

[中文](#zh) · [English](#en) · [返回首页 / Project home](../../README.md)

<a id="zh"></a>

## 中文

### 选哪个版本

| 版本 | 支持应用 | 获取方式 |
| --- | --- | --- |
| 公开 v0.6.0 | Codex、WorkBuddy，可启用其中一个或两个 | [下载 ZIP](https://github.com/dalaofei1154/rotating-flower/releases/download/v0.6.0/RotatingFlower-Mac-v0.6.0.zip) · [Release](https://github.com/dalaofei1154/rotating-flower/releases/tag/v0.6.0) |
| 本地试用 v0.7.0 | Codex、WorkBuddy、DSH | 尚未公开发布；见 [DSH 适配说明](../dsh-macos.md) |

下面的双击安装、退出码和校验值对应公开 **v0.6.0**，该版本不包含 DSH。小花软件 v0.7.0 与 DSH 应用自身版本是两个不同编号。

### 安装前准备

- Apple 芯片 Mac，macOS 12 或以上。DSH 试用适配另要求 DSH 自身支持的 macOS 13+。
- 已安装 Codex 和／或 WorkBuddy，使用自己的账号登录应用。
- 已装好、接线检查完毕并烧录[旋转＋提醒灯组合固件](../../firmware/README.md)的小花，以及 USB 数据线。

安装包内带 Python，不需要另装 Python、Homebrew 或填写 API Key。包尚未签名、公证；必要的系统确认由使用者完成。Mac 安装器不代装 AI 应用，也不烧录控制板。

### 三步安装

1. 用 USB 数据线连接小花，下载并解压 ZIP。
2. 双击 `安装小花.command`，按提示完成安装和系统确认。
3. 打开并登录要使用的应用，开始一个任务，检查小花的转动、停转和提醒灯。

安装器根据已安装的应用识别 Codex、WorkBuddy，启用其中一个或两者。Codex 以应用 bundle ID 识别，不依赖应用文件名。

### 安装结果与退出码

以下为公开 v0.6.0 安装自检的返回值。自检覆盖后台服务、启用来源就绪状态，以及本次安装后的旋转＋提醒灯控制板连接；通信通过仍需自行观察实物动作。

| 退出码 | 含义 | 下一步 |
| --- | --- | --- |
| `0` | 后台运行、启用应用就绪，旋转与提醒灯控制板已连接 | 开始任务，检查实物动作 |
| `5` | 已安装且控制板连接通过，应用尚未打开或初始化 | 打开、登录应用并开始使用；后台会自动连接，不必重装 |
| `4` | 已连接的控制板只提供旋转能力，没有提醒灯能力 | 核对硬件和固件，按组合固件教程处理；Mac 安装器不负责烧录 |
| `3` | 后台设置已保存，但应用状态或设备连接自检未全部通过 | 根据日志核对应用、USB 数据线、连接许可和固件；此时尚未完成安装验收 |
| `1` | 安装未完成，或另一安装程序仍在运行 | 查看终端中的具体原因；若是并发安装，等前一个结束 |

损坏或不兼容的应用数据会报告错误，不会被当成普通“等待应用”。可用的来源可以继续运行；需保留错误信息以便核对。分享日志前删去私人路径、任务标识、聊天内容和凭据。

### 升级、增加应用与卸载

新装和升级都会重新识别已安装的 Codex／WorkBuddy。之后新增另一款应用，再运行一次安装器即可。安装过程保留备份和日志；请使用旋转＋提醒灯版本，历史纯旋转安装包只适合对应的旧配置。

双击 `卸载小花.command` 会移除 Codex、WorkBuddy 共用的小花后台服务与登录自启，保留备份和日志，不卸载 AI 应用。该操作会同时移除两个来源的联动。

v0.7.0 的 DSH 接入还涉及本地插件配置的备份、安装和移除；以 [DSH 说明](../dsh-macos.md)为准。

### 校验下载与源码对应

文件名：`RotatingFlower-Mac-v0.6.0.zip`

SHA256：

```text
a82b64865092d03672e4340752c0c574078149b9dbcfa028f9f3e3e995dd0c01
```

可在终端输入 `shasum -a 256 `，将实际下载的 ZIP 拖入终端补全路径，然后按回车，与上面的值核对。此校验值仅对应原公开 v0.6.0 ZIP。

[固定 v0.6.0 源码快照](../../software/release-v0.6.0/README.md)对应公开 ZIP 的运行文件。根目录 `m1/` 后续开发已包含不同功能，不能视为同一个发布包的逐字源码；本地重新打包也会得到不同的 ZIP 校验值。

<a id="data"></a>

### 本地数据与验证范围

桥接只跟随本机任务，通过 USB 控制小花，不向本项目服务器上传任务记录。WorkBuddy 适配读取任务与进程元数据；Codex 适配读取本地运行状态和 rollout 记录来识别问题卡，保留状态与标识而不保留问题正文。DSH 本地试用适配通过观察插件提供状态摘要，细节见 [DSH 数据说明](../dsh-macos.md#本地数据与边界)。

现有 v0.6.0 记录覆盖维护者 Mac 上的安装、USB、两应用并行、问题等待与回答恢复；作者已目视确认呼吸灯。其他 Mac 首次完整安装和长期运行仍需独立验证。应用内部格式可能变化，升级后应复测。DSH 的本地适配有独立验证记录，各版本的验证范围分别记录。

<a id="en"></a>

## English

### Choose a version

| Version | Apps | Availability |
| --- | --- | --- |
| Public v0.6.0 | Codex, WorkBuddy, or both | [Download ZIP](https://github.com/dalaofei1154/rotating-flower/releases/download/v0.6.0/RotatingFlower-Mac-v0.6.0.zip) · [Release](https://github.com/dalaofei1154/rotating-flower/releases/tag/v0.6.0) |
| Local v0.7.0 preview | Codex, WorkBuddy and DSH | Not publicly released; see the [DSH adaptation notes](../dsh-macos.md) |

The instructions, exit codes and checksum below refer to **public v0.6.0**, which does not include DSH. Rotating Flower v0.7.0 and the DSH application's own version are separate identifiers.

### Before installing

Use an Apple silicon Mac with macOS 12+, Codex and/or WorkBuddy, and an assembled flower flashed with the [combined rotation and attention-light firmware](../../firmware/README.md). Connect it with a USB data cable. The DSH preview additionally requires macOS 13+ for the DSH app.

Python is included; no separate Python, Homebrew or API key is needed. The installer does not install or sign in to AI apps, and does not flash the control board. The package is unsigned and unnotarized; complete required system confirmations yourself.

### Install

1. Connect the flower, download the ZIP and extract it.
2. Double-click `安装小花.command` and follow the installation prompts.
3. Open and sign in to your AI app, start a task, and check physical rotation, stopping and the attention light.

The installer detects the installed Codex and WorkBuddy apps and enables either or both. Codex is identified by its bundle ID, not its application filename.

### Exit codes

These codes describe the v0.6.0 installation self-check: background service, enabled app readiness, and a fresh connection to a board with both motor and attention capabilities. Successful communication is not a measurement of physical motion.

| Code | Meaning | What to do |
| --- | --- | --- |
| `0` | Service running, enabled apps ready, motor/light board connected | Start a task and check the flower |
| `5` | Installed and board connected; an app is not open or initialized | Open and sign in to the app; connection retries automatically, without reinstalling |
| `4` | The connected board supports rotation but lacks the light capability | Check hardware and combined firmware; the Mac installer does not flash it |
| `3` | Settings saved, but app or device checks did not all pass | Read the log and check app state, USB cable, connection permission and firmware |
| `1` | Installation failed, or another installer is running | Read the specific terminal error; wait if another installation is in progress |

Damaged or incompatible app data is reported as an error, not normal waiting. Healthy sources may continue operating. Remove private paths, task identifiers, conversation text and credentials before sharing logs.

### Upgrade, add an app or uninstall

New installations and upgrades detect the installed apps again. Run the installer again if you later add Codex or WorkBuddy. Backups and logs are retained. Use the current motor-and-light package; historical motor-only packages belong to older configurations.

`卸载小花.command` removes the shared Rotating Flower background service and login startup for both apps, keeping backups and logs. It does not uninstall the AI apps. Both sources stop following tasks after removal.

The local v0.7.0 DSH adaptation also manages a local observer-plugin configuration. Its backup, installation and removal behavior is documented in the [DSH notes](../dsh-macos.md).

### Checksum and source

File: `RotatingFlower-Mac-v0.6.0.zip`

```text
a82b64865092d03672e4340752c0c574078149b9dbcfa028f9f3e3e995dd0c01
```

To check it, type `shasum -a 256 ` in Terminal, drag in the actual downloaded ZIP to insert its path, then press Return. This checksum identifies the original public v0.6.0 ZIP only.

The [pinned v0.6.0 source](../../software/release-v0.6.0/README.md) matches runtime files from that release. Later code in the root `m1/` development tree differs; a locally rebuilt archive also has a different checksum.

### Local data and validation

The bridge follows local tasks and sends control commands over USB. It does not upload task records to a project server. WorkBuddy uses task/process metadata. Codex reads local runtime and rollout records to recognize questions, retaining state and identifiers rather than question text. The DSH preview uses a local observer plugin to provide state summaries.

Existing v0.6.0 checks cover the maintainer's Mac installation, USB communication, concurrent apps, waiting questions and resumption; the author visually confirmed the breathing light. Another Mac's full first installation and long-running use still need independent validation. App data formats may change, so app upgrades require retesting. DSH has separate adaptation records, with validation scope recorded for each version.
