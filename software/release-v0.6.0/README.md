# Mac v0.6.0 源码快照

这里对应已发布的 [RotatingFlower-Mac-v0.6.0.zip](https://github.com/dalaofei1154/rotating-flower/releases/tag/v0.6.0)。九个运行源码文件直接从已校验 ZIP 提取，内容没有改写；逐文件来源及 SHA256 见 [SOURCE_MANIFEST.json](SOURCE_MANIFEST.json)。打包器和验证测试另从当前工作树选取，清单中已区分来源。

原安装包 SHA256：`a82b64865092d03672e4340752c0c574078149b9dbcfa028f9f3e3e995dd0c01`。软件源代码采用 [MIT](LICENSE)。

## 使用哪个版本

首次制作按 [DIY 教程](../../docs/diy-guide/README.md) 完成硬件与组合固件，再使用原 v0.6.0 双击安装包。它自动识别 Codex／WorkBuddy、统一控制旋转与提醒灯。

仓库根目录 `m1/integrated/integrated_bridge.py` 于 11 月 5 日增加 `FlowerGroup` 多花广播，已经不同于这个 v0.6.0 快照。不能把最新工作树当成已发布 ZIP 的逐字源码，也不能用它重新生成同名 v0.6.0 包覆盖固定哈希。新版本应另定版本、打包并验收。

## 开发和检查

源码只用 Python 标准库；建议使用 Python 3.10 或更新版本。原双击包附带 Apple 芯片 CPython 3.13.12，支持范围仍以 macOS 和本机任务为准。以下命令在**本目录**执行：

```sh
# 自动测试使用临时数据和模拟硬件，不安装服务、不连接小花
python3 -m unittest discover -s m1/integrated -p 'test_*.py' -v
python3 -m unittest discover -s m1 -p 'test_*.py' -v

# 只读检查本机应用状态，不打开 USB；输出仍可能包含本机任务标识
python3 m1/integrated/integrated_bridge.py --source both --once
```

2026-11-05 对此快照运行了 167 项集成测试和 27 项安装／打包测试，全部通过。这不是另一台 Mac 首次安装或硬件实测。

## 本地重建安装包

打包器固定使用 [python-build-standalone 20260211 的 CPython 3.13.12 arm64 归档](https://github.com/astral-sh/python-build-standalone/releases/download/20260211/cpython-3.13.12%2B20260211-aarch64-apple-darwin-install_only_stripped.tar.gz)，校验值为 `fdf98aad59d6fb99a0fc42a0392956bd7f246793003c1789b798f20e38b8ae75`。从该来源准备归档后，在本目录执行：

```sh
python3 m1/package_workbuddy_integrated.py \
  --python-archive /path/to/python-arm64.tar.gz \
  --output /path/to/new-local-build
```

`/path/to/` 必须替换成自己的路径。源码快照不内嵌 Python 二进制。输出仅用于本地重建核对：ZIP 包含生成时间等元数据，不保证与原发布 ZIP 字节相同；禁止以新 ZIP 冒充原固定 SHA256。`integrated_install.sh` 依赖打包后生成的校验清单及 Python 归档，不能直接在这个源码目录中双击安装。

Python 与其打包依赖各有许可，不能统一按本项目 MIT 重新授权。现有归档可见 CPython、pip 及部分 Tk 许可，但尚未完成所有编译依赖的 notice 核对；历史打包器中的“许可均在归档内”文案应在下一次二进制分发前更正并补齐。上游说明提供了 [完整归档与 install-only 的区别](https://github.com/astral-sh/python-build-standalone/blob/main/docs/distributions.rst) 和 [许可核查入口](https://github.com/astral-sh/python-build-standalone/blob/main/docs/running.rst#licensing)。

## 数据和验证边界

WorkBuddy 适配读取本机任务／worker／通知和 SDK 活动元数据，不读取聊天 JSONL 正文或修改数据库。Codex 适配读取本地运行状态及 rollout 记录来识别问题卡；只保留状态、标识和时间，问题和回答内容不保留。因此不应笼统宣传“所有来源完全不读取聊天文件”。桥接不向项目服务器传输这些数据。

应用内部格式可能变化。现有记录验证过 WorkBuddy 5.9.3、本机两应用并行、问题等待和回答后的控制板回执；朋友电脑首次安装、真实权限弹窗、长期运行仍需独立验收。本项目与 OpenAI、WorkBuddy 无官方关联。
