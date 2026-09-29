# 旋转花（Rotating Flower）

一个桌面实体状态指示器：Mac 上的本地 Codex 任务运行时，ESP32-C3 控制步进电机旋转；推理强度映射为五档速度，任务结束后停止。多个任务同时运行时，桥接器选用最高档。

**这是个人、非商业的 DIY 原型，与 OpenAI 没有合作、赞助或官方关联。** 演示视频中的 OpenAI 标志属于 OpenAI，装饰花件为购买的成品；本仓库不提供该标志或花件的 3D 模型，也不授权他人使用该标志。项目目前验证了电子与软件联动，尚无可直接打印的完整花朵模型。

[![旋转花随 Codex 工作的 10 秒预览](publish-assets/demo-preview.gif)](https://raw.githubusercontent.com/dalaofei1154/codex-rotating-flower/main/publish-assets/rotating-flower-demo-en-60s.mp4)

**[▶ 查看或下载完整 60 秒英文视频](https://raw.githubusercontent.com/dalaofei1154/codex-rotating-flower/main/publish-assets/rotating-flower-demo-en-60s.mp4)** · [English guide](README.en.md) · [中文从零搭建教程](docs/从零搭建.md)

演示视频展示了实际原型；教程聚焦于如何通过电脑、ESP32 和步进电机让自己的旋转装置跟随 Codex 任务状态变化。视频和第三方标志的使用范围见[许可说明](LICENSES.md)。

```text
本地 Codex 任务记录 → Mac 桥接器 → USB 串口 → ESP32-C3 → ULN2003 → 28BYJ-48
```

## 已验证范围

- ESP32-C3 SuperMini、ULN2003 和 5 V 28BYJ-48 可通过 USB 串口接收 `RUN LOW` 至 `RUN ULTRA`、`STOP`、`PING` 命令。
- `m1/global_bridge.py` 可在同一台 Mac 上发现多个本地 Codex 主任务，选择最高推理强度，任务结束时回退或停止，并在串口变号后重新连接。
- 现有 1:16 电机与手动模型在五档自动联动下完成短时实物观察。档位对应的是**固件的步进间隔**，不是独立测速得到的转速；长期连续运行、不同电机和负载仍需各自验证。
- 视频中的花朵外形不是本仓库提供的可制造结构；读者可以用自己的装饰件复现联动方法。

## 硬件与环境

| 项目 | 当前原型 |
| --- | --- |
| 电脑 | macOS，运行本地 Codex 任务 |
| 开发板 | ESP32-C3 SuperMini |
| 电机和驱动 | 5 V 28BYJ-48、ULN2003 驱动板 |
| 连接 | USB 数据线、母对母杜邦线 |
| 固件工具 | Arduino IDE 与 ESP32 Arduino Core；已在 3.3.11 上验证 |
| 桥接器 | Python 3.9 或更新版本，仅用标准库；测试已在 3.9.6 通过 |

当前原型的接线：

| ESP32-C3 | ULN2003 |
| --- | --- |
| 5V | 电源 `+` |
| G / GND | 电源 `-` |
| GPIO4 | IN1 |
| GPIO5 | IN2 |
| GPIO6 | IN3 |
| GPIO7 | IN4 |

电机的五针插头接到驱动板对应插座，ESP32-C3 通过 USB 数据线连接 Mac。**断电后接线**，并核对实际开发板和驱动板的引脚标识、电机铭牌电压与电源极性。当前 USB 供电方式只在这套原型上短时验证；换电机、增加负载或改用独立电源时，应重新核对供电能力并保持控制器与驱动板共地。旋转件与固定花瓣之间要留间隙，首次启动时从低速开始。

## 快速开始

第一次购买和接线，建议先看[从零搭建教程](docs/从零搭建.md)：它列出材料数量、六根杜邦线的连接方式、固件上传、Codex 联动步骤和可复用范围。

1. 用 Arduino IDE 打开并上传 [`m0/motor_control/motor_control.ino`](m0/motor_control/motor_control.ino)。选择与实际 ESP32-C3 开发板相符的目标板和串口。
2. 在 115200 波特率的串口监视器中发送 `PING`，应收到 `PONG`。再发送 `RUN LOW` 短时检查转动，发送 `STOP` 确认停止。运行桥接器前先关闭串口监视器，避免两个程序同时占用端口。
3. 在项目根目录运行：

   ```sh
   python3 m1/global_bridge.py --once
   python3 m1/global_bridge.py
   ```

   `--once` 只显示当前汇总状态，不连接电机。持续运行时自动查找可回应 `PING` 的串口；如果有多个候选设备，可以加 `--port /dev/cu.usbmodemXXXX`。按 Ctrl+C 会发送 `STOP`。

4. 确认手动运行正常后，可选装为 macOS 用户服务：

   ```sh
   python3 m1/install_macos.py install
   ```

   更新用 `python3 m1/install_macos.py install --replace`；卸载用 `python3 m1/install_macos.py uninstall`。安装位置、日志路径和跨窗口验证步骤见 [`m1/README.md`](m1/README.md)。安装脚本会把当前 Python 解释器路径写入 LaunchAgent，请使用日后仍会保留的 Python 安装。

## 档位与文件

| 推理强度 | 串口命令 | 目标步进间隔 |
| --- | --- | --- |
| `none` / `minimal` / `low` | `RUN LOW` | 32 ms |
| `medium` | `RUN MEDIUM` | 16 ms |
| `high` | `RUN HIGH` | 8 ms |
| `xhigh` | `RUN XHIGH` | 4 ms |
| `max` / `ultra` | `RUN ULTRA` | 2 ms |

未知档位在 M1 桥接器中暂按 `MEDIUM` 处理。固件在 `STOP`、启动和连续 30 秒未收到 `RUN` 命令时关闭线圈。`TEST` 命令用于限时调试，不是日常档位。

- `m0/`：ESP32 固件和 USB／电机短测程序。
- `m1/`：当前跨任务桥接器、macOS 安装器和测试。
- [`debug_log.md`](debug_log.md)：原型测试记录，包含观察条件与未验证项。
- `publish-assets/`：用于 GitHub 展示的 60 秒英文演示视频；原始剪辑素材和花件模型不在仓库中。

## 测试与限制

在项目根目录运行桥接器的纯软件测试：

```sh
python3 -m unittest discover -s m1 -p 'test_*.py' -v
```

桥接器读取本机 Codex 任务转录文件中的状态事件，不向网络发送内容。它依赖当前 Codex 的**内部转录格式**；[官方 Hooks 文档](https://learn.chatgpt.com/docs/hooks)也说明转录格式可能变化，因此升级 Codex 后需重新验证。当前安装流程只针对 macOS 和本地运行的 Codex 任务；云端任务、Windows 和正式机械结构尚未适配或完成。

## 参与和许可

提交问题或改动前请阅读 [`CONTRIBUTING.md`](CONTRIBUTING.md)。程序代码采用 [MIT](LICENSE)，文档文字采用 [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/legalcode)；演示视频及第三方标志的范围见 [`LICENSES.md`](LICENSES.md)。
