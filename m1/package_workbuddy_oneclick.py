#!/usr/bin/env python3
"""Build one self-extracting Mac installer and the exact prompt for WorkBuddy."""

from __future__ import annotations

import argparse
import base64
import hashlib
import io
import json
from pathlib import Path
import zipfile


VERSION = "0.3.0"
NAME = f"rotating-flower-workbuddy-macos-v{VERSION}"
RUNTIME_FILES = ("global_bridge.py", "install_macos.py", "workbuddy_setup.py", "launch_bridge.sh")

PROMPT = f"""请帮我安装 USB 小花，我已连接硬件。只使用本次附上的“{NAME}.zip”，不要搜索或使用桌面、下载目录里的其他同名或旧版安装包。解压后先确认 INSTALL.md 标题为 {VERSION}，再按说明直接执行同目录的“{NAME}.sh”，自动设置登录自启并验证本次启动的后台服务与 USB 握手。保留当前已启用的联动来源；不要根据历史备份恢复已停用的 Codex，也不要手改服务配置。请报告实际安装退出码及两项验证结果；需要系统授权时告诉我该点哪里。
"""

INSTRUCTIONS = f"""# USB 小花 · WorkBuddy Mac 一键安装 {VERSION}

这是已烧录 USB 小花的电脑端安装包，支持运行 macOS 12+、已正式安装并登录 WorkBuddy 的 Apple 芯片 Mac。用户无需安装 Arduino IDE、提供 API Key 或手动输入终端命令。

当前三档：快速 LOW、均衡 HIGH、极致 ULTRA；独立模型统一 HIGH。它表达所选工作模式，不测量实际云端算力。2026-10-31 已在提供者的 Apple 芯片 Mac + WorkBuddy 5.9.3 上通过真实控制板转停、三档、并行降档及等待确认/恢复测试；本轮未目视验收噪声与转速观感。其他电脑的实际系统、WorkBuddy 版本和 USB 连接仍需安装时自检。

## 给 WorkBuddy 的执行说明

1. 定位与本文件同目录的 `{NAME}.sh`。若只有 zip，先解压到本地临时目录。
2. 安装器会保留当前服务中的来源选项。只以当前配置为准，不查历史备份恢复已停用来源，不在运行安装器前手工修改 LaunchAgent。先检查并阅读安装脚本头部，运行 `/bin/bash "/实际路径/{NAME}.sh" inspect` 可只读查看内嵌说明和源码。所有运行文件都包含在包中，无需从网络下载程序。
3. 使用绝对路径运行以下命令（把路径替换为实际位置），不要要求用户手动编辑代码或打开终端：

   ```sh
   /bin/bash "/实际路径/{NAME}.sh"
   ```

   脚本自动解包，优先复用 WorkBuddy 自带 Python，安装或更新当前用户的后台服务，并等待最多 12 秒，验证服务运行及本次启动的 USB PING/PONG 握手。
4. 安装器不需要 Xcode；检测到未配置开发工具时跳过系统 Python。若 WorkBuddy 自带 Python 尚未就绪，先使用 WorkBuddy 自身的 Python 能力执行 `print(1+1)`，再重试。安装器不联网安装运行时或第三方包。
5. 如提示 WorkBuddy 未正式安装，请用户将官方 WorkBuddy.app 放入“应用程序”、打开并登录，再重试。本安装任务自身即可生成本地任务记录。
6. 如工具沙箱阻止用户 Library 写入、launchctl 或进程存活检查，使用 WorkBuddy 提供的正常权限申请流程。系统授权或必要的用户确认仍由用户完成。
7. 退出码 0 表示后台服务与 USB 握手都通过；退出码 3 表示安装已保存但连接自检未通过，按输出排查数据线、设备连接和串口占用后重试；其他非零退出码按错误排查，不能宣称安装成功。
8. 使用明确路径运行安装包，不搜索或上传聊天记录、密钥。当前任务完成后，提示用户目视确认小花停止；若另有 Codex/WorkBuddy 任务运行，小花会继续跟随它。

## 可选排查和卸载

```sh
/bin/bash "/实际路径/{NAME}.sh" status
/bin/bash "/实际路径/{NAME}.sh" uninstall
```

`status` 为只读诊断；它的退出码 0 不代表 USB 已握手。重新运行不带参数的安装入口会重新做完整自检。

重复安装会更新已有小花服务并备份旧版。已有 Codex 支持时保留原任务目录、指定串口及 Codex 支持；新用户只启用 WorkBuddy。程序安装后不依赖下载文件夹，登录 Mac 后自动运行。

## 限制

仅支持 Mac 本地任务；10 分钟没有状态更新时会停止跟随该任务。多个活动任务取最高档，全部结束后才停机。旧版缺少模型字段时回退 LOW。桥接在任务中途重启或错过任务结束边界时，可能无法准确还原本轮档位。依赖 WorkBuddy 内部元数据结构，其他版本/电脑需首次验证。只读任务及进程状态元数据，不读取聊天正文或凭据，不修改 WorkBuddy 数据库。

如连接后没有 USB 端口，先解锁 Mac，留意“允许配件连接”提示并允许本次小花连接；使用支持数据传输的 USB-C 线，必要时直接接到电脑。不要关闭系统安全功能，也不要要求用户授予完全磁盘访问权限。
"""


QUICKSTART_GUIDE = f"""Rotating Flower · WorkBuddy 安装三步

1. 用支持数据传输的 USB 线连接小花与 Mac，解锁电脑。若出现“允许配件连接”，允许这次连接。
2. 打开已登录的 WorkBuddy，把“{NAME}.zip”拖进去，并发送“发给WorkBuddy的安装指令.txt”中的整段话。若 ZIP 无法添加，先双击 ZIP 解压，再把里面的同名 .sh 文件拖进去。
3. 等 WorkBuddy 明确说“后台服务运行正常、USB 握手通过”，再发一句“请直接写一段约100字的周末祝福，不调用工具”。确认回答期间花转、全部任务结束后花停。系统授权由你亲自确认。

以后：登录 Mac 后自动运行，插上小花、正常使用 WorkBuddy 即可。

快速：慢转；均衡：中转；极致：快转；独立模型：中转。等待你确认时暂停。有其他任务同时工作时，花仍会继续转。

不用 Arduino，不用 API Key，不用自己打开终端，不用每次重新安装。
安装包只包含桥接程序、说明和许可，不含账户、聊天、用户配置或 3D 模型。

出问题时：让 WorkBuddy 按 INSTALL.md 运行 status 检查；提交问题前删去个人路径、设备编号和私密内容。
卸载时：把这份包交给 WorkBuddy，说“按包内说明卸载 WorkBuddy 小花支持；如有 Codex 小花支持请保留”。

版本：0.3.0 / 2026-10-31
"""


def payload_files() -> dict[str, bytes]:
    root = Path(__file__).parent
    return {**{name: (root / name).read_bytes() for name in RUNTIME_FILES},
            "INSTALL.md": INSTRUCTIONS.encode(),
            "LICENSE": (root.parent / "LICENSE").read_bytes()}


def make_script(files: dict[str, bytes]) -> bytes:
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, contents in sorted(files.items()):
            info = zipfile.ZipInfo(name, date_time=(2026, 10, 31, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, contents)
    data = stream.getvalue()
    digest = hashlib.sha256(data).hexdigest()
    header = f'''#!/bin/bash
# USB 小花 WorkBuddy Mac installer {VERSION}.
# Self-contained: base64 ZIP payload; no program downloads.
# Default: install + verify. Also supports status and uninstall.
set -euo pipefail
flower_stage="$(/usr/bin/mktemp -d "${{TMPDIR:-/tmp}}/rotating-flower-install.XXXXXX")"
trap '/bin/rm -rf -- "$flower_stage"' EXIT
/usr/bin/sed '1,/^__FLOWER_PAYLOAD_BEGIN__$/d' "$0" | /usr/bin/base64 -D > "$flower_stage/payload.zip"
flower_digest="$(/usr/bin/shasum -a 256 "$flower_stage/payload.zip")"
if [[ "${{flower_digest%% *}}" != "{digest}" ]]; then
  echo '安装文件校验失败，请重新获取完整文件。' >&2
  exit 1
fi
/usr/bin/unzip -q "$flower_stage/payload.zip" -d "$flower_stage/runtime"
if [[ $# -eq 0 ]]; then
  set -- install --verify-seconds 12
fi
if [[ "$1" == "inspect" ]]; then
  echo '=== INSTALL.md ==='
  /bin/cat "$flower_stage/runtime/INSTALL.md"
  for flower_source in global_bridge.py install_macos.py workbuddy_setup.py launch_bridge.sh; do
    echo "=== $flower_source ==="
    /bin/cat "$flower_stage/runtime/$flower_source"
  done
  exit 0
fi
echo '正在准备 USB 小花（Mac）…'
set +e
/bin/bash "$flower_stage/runtime/launch_bridge.sh" "" "$flower_stage/runtime/workbuddy_setup.py" "$@"
flower_result=$?
set -e
exit "$flower_result"
__FLOWER_PAYLOAD_BEGIN__
'''
    return header.encode() + base64.encodebytes(data)


def build(output: Path) -> Path:
    output.mkdir(parents=True, exist_ok=True)
    script = output / f"{NAME}.sh"
    sources = payload_files()
    script.write_bytes(make_script(sources))
    script.chmod(0o755)
    (output / "INSTALL.md").write_text(INSTRUCTIONS)
    (output / "发给WorkBuddy的安装指令.txt").write_text(PROMPT)
    (output / "LICENSE").write_bytes(sources["LICENSE"])
    (output / "先看这里.txt").write_text(QUICKSTART_GUIDE)
    selected = [script, output / "INSTALL.md", output / "发给WorkBuddy的安装指令.txt", output / "先看这里.txt", output / "LICENSE"]
    archive = output / f"{NAME}.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zipped:
        for path in selected:
            zipped.write(path, arcname=f"{NAME}/{path.name}")
    manifest = {
        "version": VERSION, "platform": "macOS", "network_downloads": False,
        "entrypoint": script.name, "default_action": "install_and_verify_service_and_usb",
        "hardware_baseline": "WorkBuddy 5.9.3 on provider Apple Silicon Mac: three tiers, independent model, parallel fallback, cancel, question wait/resume; board status verified; visual/noise acceptance pending",
        "mapping": {"fast-model": "LOW", "balanced-model": "HIGH", "deep-model": "ULTRA", "independent_or_unknown": "HIGH", "missing_model": "LOW"},
        "source_sha256": {name: hashlib.sha256(data).hexdigest() for name, data in sources.items()},
        "files_sha256": {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in selected},
        "zip_sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
    }
    (output / "package_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    return archive


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    print(build(parser.parse_args().output))
