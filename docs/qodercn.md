# Qoder CN 支持

小花可以直接跟随 **Qoder CN** 的本机任务转动，等待你回答问题（AskUserQuestion）时亮起提醒灯，回答或结束后停转/灭灯。不需要给 Qoder CN 安装插件，也不需要 API Key 或联网。

适配基于 Qoder CN **1.1.79** 的本地会话记录（2026 年 11 月 13 日在 Windows 版验证）。这是应用内部格式，Qoder 更新后可能需要重新适配。

## 工作原理

Qoder CN 在任务运行期间，把每个本地会话追加写入一个 JSONL 记录：

```
~/.qoder-cn/projects/<工作区>/<会话 UUID>.jsonl
```

小花后台只读取该文件的最新部分，并只保留以下状态，不保存或输出提示词、工具参数、工具输出、对话正文：

| 记录 | 判定 |
| --- | --- |
| 助手正在生成（`stop_reason` 为空） | 工作中 |
| 助手请求工具（`stop_reason: tool_use`） | 工作中 |
| 助手请求 `AskUserQuestion` 且尚未返回结果 | 等待你回答（亮灯） |
| 助手结束回复（`end_turn` / `stop_sequence` / `max_tokens`） | 空闲 |
| 用户消息（新提示、工具结果或 `[Request interrupted by user]`） | 工作中 / 打断后空闲 |

转速档位来自会话里记录的推理强度 `reasoningEffort`；若会话未记录，则读取 Qoder CN 应用数据库
`%APPDATA%\com.qodercn.app.stable\main.sqlite`（macOS 为 `~/Library/Application Support/com.qodercn.app.stable/main.sqlite`）
中 `chat_model_preferences` 表的该模型配置档位；仍无配置时用中速 `MEDIUM`。

**已知限制**：命令执行的权限确认不会写入会话记录，因此“等待你批准某条命令”只表现为普通工作中，不会亮灯。只有提问（AskUserQuestion）会亮灯。

## 启用

### Windows 试用包

只用 Qoder CN：

```
03-install-qodercn.cmd          # 软件检查模式，不连接 USB
04-enable-usb-qodercn.cmd       # 连接 USB，自动寻找串口
```

与 Codex、WorkBuddy 一起：`01-install-both.cmd`（三者软件检查模式），再用 `02-enable-usb.cmd` 开启 USB。
详见包内《先看这里.txt》与《Windows详细说明.txt》。

### macOS 源码安装

```sh
python3 m1/integrated_setup.py install --source qodercn
python3 m1/integrated_setup.py install --source codex,qodercn
```

`--source all` 仍表示原来的 Codex + WorkBuddy + DSH 三者，不包含 Qoder CN；需要 Qoder CN 时显式写出。
任务目录不在默认位置时，用 `--qoder-root` 指向实际的 `.qoder-cn` 目录。

### 只检查状态（不连接 USB）

```sh
python3 m1/integrated/integrated_bridge.py --once --source qodercn
```

## 只读与隐私

- 会话记录以只读方式打开；Windows 上使用共享读取，不阻塞 Qoder CN 自己写日志。
- 只解析 `type`、`message.stop_reason`、工具名、模型名和 `reasoningEffort`，其余字段丢弃。
- 应用数据库以 `mode=ro` 打开，只读取模型档位表；格式变化时静默降级为中性档位，不会误驱动。
- 不写入 Qoder CN 的任何目录，不修改其数据。

## 排查

| 现象 | 检查 |
| --- | --- |
| `readiness: not_initialized` | 先打开并登录 Qoder CN，开始一次任务 |
| `readiness: error` | 数据目录不可读或不是文件夹；检查 `--qoder-root` |
| 转动但提问不亮灯 | 确认是提问（选择项）而非命令授权；授权确认不亮灯 |
| 状态不更新 | Qoder CN 版本更新可能改变记录格式；保留 `check.cmd` 输出用于重新适配 |
