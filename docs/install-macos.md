# 安装小花联动 · v0.6.0

适用于 **Apple 芯片 Mac、macOS 12 或更新版本**，以及已接好、预先烧录旋转＋提醒灯固件的小花。电脑上应已安装 Codex、WorkBuddy 中的一个或两个。

给朋友或 AI 助手的一句话：

> 请按 https://github.com/dalaofei1154/rotating-flower/blob/v0.6.0/docs/install-macos.md 帮我安装小花联动，硬件已接好。

## 双击安装

1. 用 USB **数据线**连接小花，下载 [RotatingFlower-Mac-v0.6.0.zip](https://github.com/dalaofei1154/rotating-flower/releases/download/v0.6.0/RotatingFlower-Mac-v0.6.0.zip)。
2. 解压，双击 **安装小花.command**，按窗口提示操作。
3. 自行打开并登录 Codex 或 WorkBuddy，开始一个任务，观察小花转动与提醒灯。

安装器自动识别已安装的 Codex、WorkBuddy，启用其中一个或两个；新装和升级都重新识别。以后新增另一个应用，再双击安装一次。包内已带 Python，**不需要系统 Python、Homebrew 或 Node**；不会安装 AI 应用，也不会烧录控制板。

应用还没打开或初始化时可以先装。提示“已安装、等待应用”（退出码 **5**）时，打开相应应用、登录并开始一次任务即可，后台会自动重试，**无需重装**。以后登录 Mac 自动启动，可以删除解压文件夹。

这是尚未签名、公证的个人试用包，macOS 可能要求你确认打开文件或允许 USB 配件连接。通过系统正常提示完成授权。

## 让 AI 助手或终端安装

先将固定版本的[安装脚本](../m1/install_unified_release.sh)下载到临时目录，再执行保存的文件：

```sh
flower_install_dir="$(/usr/bin/mktemp -d "${TMPDIR:-/tmp}/rotating-flower-install.XXXXXX")" &&
/usr/bin/curl --fail --show-error --location \
  --proto '=https' --proto-redir '=https' \
  --output "$flower_install_dir/install_unified_release.sh" \
  'https://raw.githubusercontent.com/dalaofei1154/rotating-flower/v0.6.0/m1/install_unified_release.sh' &&
/bin/bash "$flower_install_dir/install_unified_release.sh"
```

如果浏览器能访问 GitHub 而命令行下载超时，AI 助手应先读取本机已配置的网络代理并沿用；不要改系统网络设置。安装脚本会沿用显式代理环境变量，或使用 macOS 已启用的静态 HTTPS 代理（不解析 PAC）。

脚本下载固定的 v0.6.0 ZIP，校验下面的 SHA256 后才解压、安装。它不把网络内容直接通过管道交给 shell。

```text
a82b64865092d03672e4340752c0c574078149b9dbcfa028f9f3e3e995dd0c01
```

| 退出码 | 含义与下一步 |
| --- | --- |
| `0` | 后台、已启用应用和旋转＋提醒灯控制板均通过自检。 |
| `5` | 已安装，等待打开或初始化应用；后台自动重试，无需重装。 |
| `3` | 已安装，但 USB 或应用状态检查未通过；按窗口错误处理，不能当作全部就绪。 |
| `4` | 控制板缺少提醒灯能力；联系提供者核对硬件与固件，本安装器不会烧录。 |
| 其他 | 安装未完成；保留窗口错误和日志提示。 |

数据损坏或版本不兼容会明确报错，不会当作“等待应用”跳过。若 AI 工具被拒绝操作串口或注册后台，走该工具的正常权限申请流程，或在系统“终端”运行已下载的脚本；不要反复执行 `launchctl` 修复，不要用 `sudo` 或关闭安全设置。

## 使用、更新与卸载

多个工作任务取最高转速档位；连接正常的来源有待回答或授权事项时亮提醒灯。Codex 异步问题允许同一任务继续工作并亮灯；来源断开时停止贡献输出，但保留提醒缓存。阻塞等待中的任务不参与选速，另一个任务仍在工作时，小花可以继续旋转并同时亮灯。回答后相应提醒清除；全部任务完成且没有等待事项时停转、灭灯。档位表示所选工作模式，不是实测算力或转速。

更新时运行新版本安装包。卸载时双击包内 **卸载小花.command**，它会移除整个小花后台，同时停止 Codex 和 WorkBuddy 联动，保留备份和日志。

本机已验证 Codex **26.1027.61615**、WorkBuddy **5.9.3**：双击安装、双应用并行选速、等待真实问题卡及回答后灭灯通过，用户亲眼确认灯在呼吸。当前包不支持 Intel Mac，也不代表全部应用版本或第二台 Mac 已通过验证；真实权限审批弹窗和长期连续使用仍待验证。桥接依赖应用本地状态格式，应用升级后需要复测。只支持本机任务。

## English

Use an **Apple silicon Mac running macOS 12+**, with Codex and/or WorkBuddy already installed. The assembled flower must already have combined firmware supporting both `motor` and `attention`. This installer does not flash firmware or install AI apps.

Download the [v0.6.0 ZIP](https://github.com/dalaofei1154/rotating-flower/releases/download/v0.6.0/RotatingFlower-Mac-v0.6.0.zip), extract it, and double-click **安装小花.command**. Alternatively, run the download-then-execute commands above; the pinned script verifies the ZIP's SHA256 before installation. Python is bundled; system Python, Homebrew and Node are not required. The package is unsigned and unnotarized, so macOS may require confirmation.

Installation and upgrade detect either app or both. If you add the other app later, run the installer again. Exit **5** means installation succeeded but an app is not ready: open it, sign in and start a task. The background service retries automatically; do not reinstall. Exit **0** means all checks passed, **3** means a USB/app check failed, and **4** means the board lacks attention-light support. Damaged or incompatible app data is an error, not a successful check.

Use the assistant's normal permission workflow or run the saved script in Terminal if access is denied. Do not repeatedly repair `launchctl`, use `sudo`, or disable security settings. The service starts at login. Multiple working tasks use the highest speed; reminders combine across tasks. One blocked task does not stop another task's rotation. An asynchronous question can leave the same Codex task working and the light on. Disconnected sources stop contributing outputs but retain pending-state caches. Double-click **卸载小花.command** to remove the entire flower service; backups and logs remain.

Tested on one Mac with Codex **26.1027.61615** and WorkBuddy **5.9.3**, including double-click installation, concurrent tasks, a real question card and clearing the light after answering. The user visually confirmed the breathing light. This package does not support Intel Macs. Every app version, installation on a second Mac, real permission prompts and long continuous use are not claimed as verified.

[English README](../README.md) · [中文首页](../README.zh-CN.md) · [许可](../LICENSES.md) · 历史纯旋转硬件参考：[English](build-guide-en.md) / [中文](从零搭建.md)
