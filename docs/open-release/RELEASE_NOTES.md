# 旋转花雏菊版 DIY 资料更新

模型资料整理于 2026-11-05，2026-11-06 加入中英文配乐介绍片。硬件资料集为 `daisy-light-20261105`，配套软件源码为 `v0.6.0`，固件标识为 `FLOWER_COMBINED_V1`。

这次把做一朵雏菊小花所需的资料放到了一起：打印工程、分色 STL、可编辑网格、材料清单、接线和实拍装配教程，以及配套固件和软件源码。

## 本次内容

- 每套 10 个实体打印件。选择已有雏菊花盘、2 号 D16.95 连接件、Y1 D22.00 花心、L2 短根块灯盖和 P4 D6.2/H2.4 灯帽。
- 装配照片展示板卡、电机、灯板、传动和走线；成品展示图替换了背景。
- 中英文介绍片各 72 秒，配上原创音乐《小花慢慢转》，展示功能和零件组成。片中的 DSH 为 v0.7.0 本地试用版，目前公开下载的 v0.6.0 支持 Codex 和 WorkBuddy。
- 转动和输入提醒独立处理：一个任务等待、另一个任务工作时，可同时转动和亮灯。
- 代码 MIT、文字 CC BY 4.0；模型与本次新图片 CC BY-NC-SA 4.0。欢迎非商业复现与改进，商业合作另行联系。

## 还想改进的地方

花心、透明灯帽、枝干与盆盖的连接没有用胶，现在还有些松。后续会调整这几处配合；装配时留意松紧，搬动时托住花盆。

灯板用的是 KY-016，带预焊直角公排针和板载限流电阻。

## 目前试过哪些

我已装好 L2 灯盖＋P4 灯帽，旋转和亮灯正常。v0.6.0 在我的 Mac 上试过安装、应用识别、USB 连接、并行任务、等待回答和回答后恢复。

接下来还想收集不同打印机的配合情况、其他 Mac 的首次安装反馈，并继续测试权限审批和长时间运行。

Mac 安装包从公开 v0.6.0 Release 下载，包内带 Python。烧录工具按固件教程准备；打印文件请按自己的设备和耗材重新切片。

## English

The `daisy-light-20261105` DIY set brings together 10 printed parts, print projects, color-separated STL files, editable meshes, illustrated instructions, motor-and-light firmware and the v0.6.0 software source. Models and new images use CC BY-NC-SA 4.0; code uses MIT and written guides use CC BY 4.0.

The English and Chinese films were added on November 6, 2026. Each runs for 72 seconds with the original soundtrack “Little Things Turning” and shows the flower's behavior and parts. DSH appears in the local v0.7.0 preview; the public v0.6.0 download supports Codex and WorkBuddy.

My assembled L2 lid and P4 cap work for both rotation and lighting. I've checked v0.6.0 installation, app detection, USB communication, concurrent tasks, waiting for an answer and resuming on my Mac. Next, I'd like feedback on fits from other printers and first installations on other Macs, along with more testing of approval prompts and longer sessions.

The flower center, clear cap and stem-to-lid joint are unglued and still a little loose. I plan to improve these fits. Check them during assembly and hold the pot when moving the flower. The LED module is a KY-016 with pre-soldered right-angle male headers and onboard resistors.

Download the Mac installer, with Python included, from the public v0.6.0 Release. Follow the firmware guide for flashing tools, and slice the print files for your own printer and material.
