# 旋转花雏菊版公开资料

**[▶ 中文配乐介绍片](https://github.com/user-attachments/assets/a38f9855-469f-46ad-a9b5-1f78d493e84b)** · [▶ English film](https://github.com/user-attachments/assets/debc0f6c-ad6e-49d3-a212-e0ad689b4f36)

72 秒看看小花怎么工作、由哪些零件组成，配上原创音乐《小花慢慢转》。视频也展示了 DSH 的 v0.7.0 本地试用版；目前可下载的 v0.6.0 支持 Codex 和 WorkBuddy。

[模型下载图与3D组成动画 / Visual download guide and 3D animation](../../hardware/daisy-light/VISUAL_GUIDE.md)

[English](README.en.md)

旋转花是一朵通过 USB 连接 Mac 的桌面小花：AI 工作时转动，需要你回答时亮起呼吸灯。不同推理档位对应不同转速。

这里整理了雏菊带灯版的整套制作资料：10 个打印件、模型、图解教程、旋转＋灯光固件，以及 v0.6.0 软件源码。

我现在装的是 L2 灯盖和 P4 灯帽，转动、亮灯都正常。花心、透明灯帽、枝干与盆盖的连接没有用胶，配合还有些松，后续会继续改模型。试装时留意这几处，搬动时托住花盆。

## 从这里开始

1. 阅读[材料、打印与装配教程](../diy-guide/README.md)，先核对材料再下单。
2. 按[模型说明](../../hardware/README.md)选择一套零件，使用 3MF 保留双色对齐，或按 STL 清单导入。每套 10 件；L2、P4 参考盘分别排了 2 件、4 件，切片时只保留所需数量。
3. 断电接线并检查，再烧录[旋转和提醒灯组合固件](../../firmware/README.md)。
4. 安装[公开 v0.6.0 Mac 软件](https://github.com/dalaofei1154/rotating-flower/releases/tag/v0.6.0)。已装好软件的人不必再次安装。
5. 依照[验收表](../diy-guide/CHECKLIST.md)检查起停、灯光、并行任务和合盖后运行。

## 文件与版本

| 内容 | 入口 | 说明 |
| --- | --- | --- |
| 打印模型与可编辑网格 | [hardware](../../hardware/README.md) | 雏菊版打印文件与可编辑 Blender 网格 |
| 图解制作教程 | [中文](../diy-guide/README.md) / [English](../diy-guide/README.en.md) | 过程实拍；封面替换过背景 |
| 固件 | [firmware](../../firmware/README.md) | `FLOWER_COMBINED_V1`；USB 控制旋转和呼吸灯 |
| 软件源码 | [release-v0.6.0](../../software/release-v0.6.0/README.md) | 与公开 v0.6.0 安装包对应 |
| 更新记录 | [RELEASE_NOTES](RELEASE_NOTES.md) | 本次内容、试装情况和待改进之处 |
| 许可与署名 | [LICENSES](../../LICENSES.md) / [ATTRIBUTION](ATTRIBUTION.md) | 软件 MIT；文字 CC BY；模型和新图片 CC BY-NC-SA |

安装包适用于 Apple 芯片 Mac。我在自己的 Mac 上做了联动测试，也想看看它在大家的设备上用起来怎么样。Codex、WorkBuddy 更新后，如果出现联动问题，欢迎反馈应用版本。

## 复现与改进

欢迎在[项目 Issues](https://github.com/dalaofei1154/rotating-flower/issues)晒出你做的小花，聊聊打印机、耗材和组装过程，也可以反馈问题。贴日志或截图前，记得遮住私人信息。商业合作也可以在这里联系。

这批模型与新图片采用 CC BY-NC-SA 4.0，允许署名后的非商业分享、改编，分享改编作品时沿用相同许可。商业使用需另行取得许可。软件的 MIT 许可保持不变。

我是 Flynn。这朵小花的起点是一个手动盆栽摆件，后来我借助 AI 工具，一点点做出了自己的雏菊造型、电动结构和应用联动。
