# DeepSeek Harness 支持进展

DSH 适配已加入 **v0.7.0 本地试用版**，安装包与源码会在整理完成后发布。目前可下载的 [v0.6.0](https://github.com/dalaofei1154/rotating-flower/releases/tag/v0.6.0) 支持 Codex 和 WorkBuddy。

当前适配版本为 **DeepSeek Harness 0.2.1-rc.5**，运行于 **Apple 芯片 Mac、macOS 13+**。

## 小花怎样响应

| DSH 推理等级 | 小花转速档位 |
| --- | --- |
| Off | LOW |
| Low | MEDIUM |
| High | HIGH |
| Max | ULTRA |

- 工作时转动，完成或取消后停止。
- 任务暂停等待回答或授权时，呼吸灯亮起；处理后恢复对应状态。
- 有些问题允许工作继续，小花会一边转动、一边亮灯。
- Codex、WorkBuddy、DSH 可以一起使用。多任务同时工作时采用最高的活动档位，任一任务需要你处理时亮灯。
- 关闭 DSH 后，它的状态会清除；其他应用继续联动。重新打开 DSH 后自动恢复。

<a id="本地数据与边界"></a>

## 本地数据

适配通过 DSH 本地插件读取任务状态、模型与推理等级，以及待处理问题和授权的数量。状态摘要保存在本机 `~/Library/Application Support/RotatingFlower/dsh/status.json`，由小花后台统一通过 USB 控制电机和灯。

摘要不包含问题正文、回答或账号凭据，也不向项目服务器上传。DSH 的插件与运行时接口可能随应用更新变化，适配版本会在发布时注明。

[返回中文首页](../README.zh-CN.md) · [English home](../README.md)
