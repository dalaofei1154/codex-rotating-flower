# Rotating Flower · 旋转花

[English](README.md) · **简体中文**

一朵跟随本地 AI 任务转动的桌面小花。Mac 桥接程序通过 USB 连接 **Codex、WorkBuddy** 和 ESP32 电机控制器。

项目原名 `codex-rotating-flower`。本次是一次小更新：新增 WorkBuddy 桥接支持和 Mac 下载包。新造型、灯光提醒等将在后续单独更新，**不包含在本次发布中**。

## WorkBuddy Mac 安装包 · v0.3.0

**[下载安装包](https://github.com/dalaofei1154/rotating-flower/releases/download/v0.3.0/rotating-flower-workbuddy-macos-v0.3.0.zip)** · [发布说明与校验文件](https://github.com/dalaofei1154/rotating-flower/releases/tag/v0.3.0) · [完整安装说明](docs/workbuddy-macos.md)

安装包面向**已经组装、烧录并试转通过的 USB 小花**。从零搭建请先完成[接线与固件教程](docs/从零搭建.md)。

1. 在 Apple 芯片 Mac 上安装并登录 WorkBuddy，用 USB **数据线**连接小花。
2. 解压安装包，将带版本号的 `.sh` 文件和 `INSTALL.md` 交给 WorkBuddy，再发送 `发给WorkBuddy的安装指令.txt` 中的文字；使用解压文件时，把“本次附上的 ZIP”改成对应脚本即可。
3. 让 WorkBuddy 执行安装，必要的系统授权由你确认。确认“后台服务运行正常”和“本次 USB 握手通过”，再观察任务期间转动、全部任务结束后停转。

包内含程序源码和说明，不联网下载程序、不需要 API Key；复用可用的 Python 3.9+，包括 WorkBuddy 自带运行时。安装后登录 Mac 自动启动，不需要每次重新安装。

## 当前联动规则

| 来源／选择 | 电机档位 |
| --- | --- |
| Codex | 根据所选推理强度映射五档 |
| WorkBuddy：快速 | LOW，慢转 |
| WorkBuddy：均衡 | HIGH，中转 |
| WorkBuddy：极致 | ULTRA，快转 |
| WorkBuddy：独立模型或未知的非空模型 | HIGH，统一中档 |
| WorkBuddy：旧记录缺少模型字段 | LOW |

WorkBuddy 等待用户回答或确认时暂停该任务的转动贡献，恢复工作后继续；完成或取消后移除贡献。多个任务取仍在工作的最高档，全部不再工作后才停转。安装 WorkBuddy 支持时会保留已有 Codex 联动。

这是**所选工作模式的映射**，不是云端算力、模型智力、token/s 或实测 RPM。WorkBuddy 工作中切换模式下一轮才生效；中途重启及采样限制见完整说明。

## 从源码运行

Mac 上准备 Python 3.9+，在仓库根目录执行：

```sh
# 只读查看状态，不连接 USB
python3 m1/global_bridge.py --source workbuddy --once

# 持续跟随 WorkBuddy，或同时跟随两种应用（只运行一个桥接进程）
python3 m1/global_bridge.py --source workbuddy
python3 m1/global_bridge.py --source both
```

默认来源仍为 Codex。登录自启、更新和卸载见[桥接程序说明](m1/README.md)。

## 验证范围与限制

- 本次仅支持 Mac 本地任务，不支持 Windows 或云端任务。
- WorkBuddy 5.9.3 的三档、并行降档、取消、等待及恢复已核对真实控制板回报；早期 5.8.3 起停已有目视确认。
- v0.3.0 已在维护者的 Apple 芯片 Mac + WorkBuddy 5.9.3 验证安装、新 USB 握手和结束 STOP；另一台 Mac 的独立安装和长期运行仍待验证。最新三档测试未测量实际 RPM 或噪声。
- 42 项自动测试覆盖桥接、安装与打包，使用临时数据和模拟硬件／服务控制。
- 适配依赖应用的本地数据格式，应用升级后需要复测。WorkBuddy 桥接只读任务及进程元数据，不读取聊天正文或凭据，不修改数据库；程序不向本项目的服务器发送数据。
- 连续 10 分钟无状态更新的任务不再贡献运行状态；原固件保留 30 秒无 `RUN` 指令自动停机。

```sh
python3 -m unittest discover -s m1 -p 'test_*.py' -v
```

## 开源范围

桥接程序、安装器及 ESP32 固件采用 [MIT](LICENSE)，教程文字采用 CC BY 4.0。**3D 模型及生产文件暂不公开。**你可以使用自己的装饰件，也可以先用裸电机验证联动。历史照片、视频的许可单独列于 [LICENSES.md](LICENSES.md)。

本次不增加图片或新硬件设计。[原 Codex 搭建教程](docs/从零搭建.md)继续作为硬件参考。本项目独立开发，与 OpenAI 或 WorkBuddy 无官方关联、赞助或背书。
