# Mac v0.6.0 源码

本目录对应已发布的 [RotatingFlower-Mac-v0.6.0.zip](https://github.com/dalaofei1154/rotating-flower/releases/tag/v0.6.0)，支持 Codex 和 WorkBuddy 的旋转与提醒灯联动。运行文件来自该安装包，另附打包工具和测试；文件来源与校验值见 [SOURCE_MANIFEST.json](SOURCE_MANIFEST.json)。源码采用 [MIT](LICENSE)。

## 使用与开发

制作小花可从 [DIY 教程](../../docs/diy-guide/README.md) 开始，完成硬件和固件后安装 v0.6.0。这个目录保留 v0.6.0 的运行代码；仓库根目录的 `m1/` 则包含后续开发功能，例如多朵花的广播控制。

源码使用 Python 标准库，开发建议使用 Python 3.10 或更新版本。发布的双击安装包附带 Apple 芯片 CPython 3.13.12。

在本目录运行测试：

```sh
python3 -m unittest discover -s m1/integrated -p 'test_*.py' -v
python3 -m unittest discover -s m1 -p 'test_*.py' -v
```

查看本机应用状态：

```sh
python3 m1/integrated/integrated_bridge.py --source both --once
```

`--once` 输出一次状态快照，不连接 USB。

## 构建安装包

下载 [python-build-standalone 的 CPython 3.13.12 arm64 归档](https://github.com/astral-sh/python-build-standalone/releases/download/20260211/cpython-3.13.12%2B20260211-aarch64-apple-darwin-install_only_stripped.tar.gz)，其 SHA256 为：

```text
fdf98aad59d6fb99a0fc42a0392956bd7f246793003c1789b798f20e38b8ae75
```

在本目录执行，将示例路径换成归档和输出目录的实际位置：

```sh
python3 m1/package_workbuddy_integrated.py \
  --python-archive /path/to/python-arm64.tar.gz \
  --output /path/to/new-local-build
```

打包器会加入 Python 运行时并生成安装器需要的校验清单。构建完成后，从输出目录运行安装脚本。重建包包含新的生成时间等元数据，校验值会与原发布包不同。

分发新的安装包时，需保留 Python 及其打包依赖各自的许可和声明。上游的 [归档说明](https://github.com/astral-sh/python-build-standalone/blob/main/docs/distributions.rst) 和 [许可说明](https://github.com/astral-sh/python-build-standalone/blob/main/docs/running.rst#licensing) 提供了对应要求。

## 本地数据

WorkBuddy 适配读取本机任务、进程和通知元数据。Codex 适配读取本地运行状态及 rollout 记录，识别正在工作和等待回答的任务。桥接只保留状态、标识和时间，不保留问题与回答正文，也不向项目服务器上传任务数据。

应用升级后，本地记录格式可能变化；遇到联动问题可先用上面的状态快照命令检查。
