# Unreleased · DeepSeek Harness 适配

以下为当前源码的变更，尚未发布 v0.7.0。可下载的 [v0.6.0 安装包](https://github.com/dalaofei1154/rotating-flower/releases/tag/v0.6.0)仍只支持 Codex 和 WorkBuddy。

- **新增 DeepSeek Harness 适配**：推理等级映射为转速档位（off/none/minimal → LOW，low/medium → MEDIUM，high → HIGH，xhigh → XHIGH，max → ULTRA），待回答和待授权时亮起提醒灯。Codex、WorkBuddy、DSH 可以同时使用，多任务取最高活动档位。
- 本地插件处理 DSH 事件和状态投影，将会话 ID、运行/阻塞标志、模型、推理等级和待处理数量写入 `~/Library/Application Support/RotatingFlower/dsh/status.json`。摘要不保存提示词、问题正文、回答或凭据，也不上传任务数据。
- 修正异步提问被误判为阻塞的情况：任务继续工作时，小花可同时转动和亮灯。读取事件失败后保留游标，恢复时重新处理该事件。
- 状态变化时立即写入，否则每秒刷新心跳；偶发读取失败沿用上一次正常状态，连续 3 次失败才报告接口不兼容。
- 统一安装器自动注册或移除 DSH 插件，安装失败时回滚本次配置改动。`m1/dsh_setup.py` 也提供独立安装、卸载和状态检查。
- 打包工具纳入插件及安装模块，可从源码构建包含 DSH 的安装包；本次未发布新的下载包。
- `--source` 接受 `dsh`、`codex,dsh`、`workbuddy,dsh`、`all` 等组合，并允许从 v0.6.0 升级。
- 补充 observer、适配器、安装回滚及安装包内容的自动化测试，CI 增加 Node observer 检查。自动化测试不代替实机 USB 验收。

**安装与边界**：见 [DSH 源码安装说明](../dsh-macos.md)。本次面向 Apple 芯片 Mac、macOS 13+ 和 DSH 0.2.1-rc.5，假设本机只运行一个 DSH 实例；未包含 Windows 支持。

## English

These changes are in the current source. **v0.7.0 has not been released.** The downloadable [v0.6.0 installer](https://github.com/dalaofei1154/rotating-flower/releases/tag/v0.6.0) still supports Codex and WorkBuddy only.

- **DeepSeek Harness support**: reasoning effort maps to motor speed (off/none/minimal → LOW, low/medium → MEDIUM, high → HIGH, xhigh → XHIGH, max → ULTRA); questions and approvals light the reminder LED. Codex, WorkBuddy and DSH can run together and the fastest active preset wins.
- A local plugin processes DSH events and projections, writing session IDs, running/blocking flags, model, effort and pending counts to `~/Library/Application Support/RotatingFlower/dsh/status.json`. The summary does not store prompts, question bodies, answers or credentials, and the plugin does not upload task data.
- Asynchronous questions no longer pause the flower after work has continued. A failed event read retains its cursor so that the event can be retried on recovery.
- Changed state is written immediately; unchanged state gets a one-second heartbeat. Transient read failures retain the last good snapshot, with an incompatibility reported after three consecutive failures.
- The integrated installer registers or removes the DSH plugin and rolls back its configuration changes if installation fails. `m1/dsh_setup.py` remains available for standalone installation, removal and status checks.
- The package builder includes the plugin and its setup module. No new downloadable installer is published with this change.
- `--source` accepts `dsh`, `codex,dsh`, `workbuddy,dsh` and `all`; upgrading from v0.6.0 is supported.
- Automated tests cover the observer, adapter, installer rollback and packaged files; CI adds the Node observer checks. These checks do not replace physical USB acceptance testing.

**Setup and scope**: see the [DSH source installation notes](../dsh-macos.md#english). This change targets DSH 0.2.1-rc.5 on Apple silicon Macs with macOS 13+, assumes one DSH instance per machine, and does not include Windows support.

# 雏菊版制作资料更新

## 2026-11-06

- 首页更新为 46 秒实拍成片（英文旁白、中英字幕）；3D 功能与组成介绍片移至[模型展示页](../../hardware/daisy-light/VISUAL_GUIDE.md#animation)。
- 加入作者提供的[材料参考价格](../diy-guide/BOM.md#costs)，所列项目合计 53.92 元，并在制作教程前提供入口。

- 提供一套 10 件的打印模型：9 个 3MF 工程、13 份分色 STL 和 10 份可编辑 Blender 网格。
- 加入材料清单、打印说明、实拍装配教程、接线表和装配检查表。
- 配套提供旋转＋提醒灯固件，以及 v0.6.0 软件源码。安装包支持 Codex 和 WorkBuddy，DSH 支持正在开发中。

## 装配时留意

- 本套采用 L2 带灯盆盖和 P4 透明灯帽；灯板为 KY-016，带直角公排针和板载限流电阻。
- 花心、透明灯帽、枝干与盆盖的连接没有用胶，目前还有些松。试装时检查松紧，搬动时托住花盆。
- 部分 3MF 打印盘包含备用件，一盆只需要 10 个打印件，按清单调整数量。

[制作教程](../diy-guide/README.md) · [模型清单](../../hardware/daisy-light/VISUAL_GUIDE.md) · [安装软件](INSTALL.md)

## English

### November 6, 2026

- The homepage now features the approved 46-second live-action demo with English narration and bilingual subtitles. The 3D explainer is on the [model guide](../../hardware/daisy-light/VISUAL_GUIDE.md#animation).
- Added the author’s [reference material costs](../diy-guide/BOM.md#costs), totaling CNY 53.92 for the listed items, with links before the build steps.

- A complete set of 10 printed parts: 9 print projects, 13 color-separated STL files and 10 editable Blender meshes.
- Materials list, printing instructions, illustrated assembly guide, wiring table and build checklist.
- Motor-and-light firmware and v0.6.0 software source. The installer supports Codex and WorkBuddy; DSH support is in development.

### Assembly notes

- This set uses the L2 lid and P4 clear cap, with a KY-016 LED module fitted with right-angle male headers and onboard resistors.
- The flower center, clear cap and stem-to-lid joint are unglued and still a little loose. Check these fits during assembly and hold the pot when moving the flower.
- Some 3MF plates include spares. Use the parts list to select the 10 parts needed for one flower.

[Build guide](../diy-guide/README.en.md) · [Parts list](../../hardware/daisy-light/VISUAL_GUIDE.md) · [Install the software](INSTALL.md#en)
