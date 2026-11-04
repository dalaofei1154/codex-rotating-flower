# Rotating Flower · 旋转花

[English](README.md) · **简体中文**

一朵跟随本地 **Codex、WorkBuddy** 任务转动的 USB 桌面小花，需要你回答时亮起呼吸灯。项目原名 `codex-rotating-flower`。

## 安装 v0.6.0

**[下载 Mac 安装包](https://github.com/dalaofei1154/rotating-flower/releases/download/v0.6.0/RotatingFlower-Mac-v0.6.0.zip)** · [安装说明](docs/install-macos.md) · [发布页](https://github.com/dalaofei1154/rotating-flower/releases/tag/v0.6.0)

需要 **Apple 芯片 Mac、macOS 12 或更新版本**，已安装 Codex、WorkBuddy 中的一个或两个，以及已组装、预先烧录旋转＋提醒灯固件的小花。

1. 用 USB **数据线**连接小花。
2. 解压安装包，双击 **安装小花.command**。
3. 自行打开并登录 AI 应用，开始一个任务。

也可以直接把这句话发给朋友或 AI 助手：

> 请按 https://github.com/dalaofei1154/rotating-flower/blob/v0.6.0/docs/install-macos.md 帮我安装小花联动，硬件已接好。

新装和升级都会自动识别 Codex、WorkBuddy，启用其中一个或两个。以后新增另一应用，再双击安装一次。包内带有 Python，**不需要系统 Python、Homebrew 或 Node**；不会安装 AI 应用或烧录硬件。安装后登录 Mac 自动运行。

应用尚未打开或初始化时可以先安装。退出码 **5** 表示“已安装，等待应用”；打开应用、登录并开始任务后，后台会自动重试，**无需重装**。数据损坏或版本不兼容会明确报错。本包尚未签名、公证，macOS 可能要求确认打开。

[安装说明](docs/install-macos.md)提供固定版本的网络安装入口：先下载脚本再执行，并校验安装包 SHA256：

```text
a82b64865092d03672e4340752c0c574078149b9dbcfa028f9f3e3e995dd0c01
```

## 联动规则

| 状态 | 小花表现 |
| --- | --- |
| 正在工作 | 按所选模式旋转 |
| 阻塞等待回答或授权 | 呼吸灯提醒，该任务不参与选速 |
| 一个任务等待，另一个仍工作 | 可以同时旋转、亮灯 |
| 全部完成且没有待处理事项 | 停转、灭灯 |

两个应用的工作任务取最高档位；连接正常的来源仍有待处理事项时，提醒就保留。Codex 异步问题可让同一任务继续工作并亮灯；来源断开时停止贡献输出，但保留提醒缓存。WorkBuddy 快速／均衡／极致对应 LOW／HIGH／ULTRA，独立或未知模型用 HIGH，缺少模式记录用 LOW；Codex 保留五档推理强度映射。这是所选工作模式的映射，不是实测算力或 RPM。

卸载时双击 **卸载小花.command**，会移除整个小花后台，同时停止两个应用的联动，保留备份和日志。

## 验证范围

已在一台 Mac 上验证 **Codex 26.1027.61615、WorkBuddy 5.9.3**：双击安装、双应用并行选速、真实问题卡等待及回答后灭灯通过，用户亲眼确认灯在呼吸。

当前包不支持 Intel Mac；所有应用版本或第二台 Mac 独立安装尚未全部验证；真实权限审批弹窗与长期连续使用仍待验证。只跟随本机任务，适配依赖应用本地数据格式，应用升级后需要复测。不需要 API Key，桥接程序不向本项目的服务器发送数据。

## 源码与硬件参考

桥接程序、安装器与 ESP32 固件采用 [MIT](LICENSE)，教程文字采用 CC BY 4.0；媒体等单独条款见 [LICENSES.md](LICENSES.md)。当前 3D 模型和生产文件不公开。

历史纯旋转搭建教程：[中文](docs/从零搭建.md) / [English](docs/build-guide-en.md)。其中的旧固件与安装命令不等于本版所需的旋转＋提醒灯配置。

本项目独立开发，与 OpenAI 或 WorkBuddy 无官方关联、赞助或背书。
