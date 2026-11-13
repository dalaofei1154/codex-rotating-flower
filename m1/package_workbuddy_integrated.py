#!/usr/bin/env python3
"""Build an offline Apple Silicon installer, launched by Finder/Terminal."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import zipfile

VERSION = "0.7.0"
NAME = f"RotatingFlower-Mac-v{VERSION}"
PYTHON_SHA256 = "fdf98aad59d6fb99a0fc42a0392956bd7f246793003c1789b798f20e38b8ae75"
PYTHON_URL = "https://github.com/astral-sh/python-build-standalone/releases/download/20260211/cpython-3.13.12%2B20260211-aarch64-apple-darwin-install_only_stripped.tar.gz"
RUNTIME_FILES = ("integrated_setup.py", "integrated_install.sh", "dsh_setup.py",
                 "dsh/flower-observer.mjs")
BRIDGE_FILES = ("integrated_bridge.py", "attention_state.py", "motor_bridge_base.py",
                "runtime_feed.py", "state_reducer.py", "root_catalog.py", "workbuddy_adapter.py",
                "dsh_adapter.py", "qodercn_adapter.py", "source_config.py")

GUIDE = """小花 · Mac 统一安装

1. 用 USB 数据线连接已经烧录好的小花。
2. 解压后双击「安装小花.command」，弹出的窗口会自动安装，不用输入命令。
3. 按窗口提示打开你使用的 Codex、WorkBuddy、DeepSeek Harness 或 Qoder CN，登录后开始一次任务。
   DSH 需要先打开一次完成初始化；安装后退出并重新打开 DSH 以加载插件。
   Qoder CN 会按本机任务记录联动，不需要安装插件。

自动识别电脑上已安装的桌面应用：
支持 Codex、WorkBuddy、DeepSeek Harness 和 Qoder CN；检测到多个应用时同时联动。
Codex 或 WorkBuddy 还没打开时，后台会等待。DSH 插件需要已有的本地配置，
若提示找不到 DSH 配置，请先打开 DSH，再运行本安装器。
本包不包含这些应用本身；请先安装你要使用的应用。
以后新增另一个应用，再双击安装一次即可重新识别。平时登录 Mac 后自动运行。

任意一个应用工作，小花就转；同时工作取较高档位，全部结束才停。
需要回答或授权时亮呼吸灯；其他任务仍工作时，旋转和提醒灯可以同时运行。
回答或取消后清除对应提醒。首次请观察旋转、停转和提醒灯是否正常。

若 Mac 询问是否允许 USB 配件连接，请允许这次小花连接。
若 Mac 阻止打开安装文件：这是尚未经过 Apple 开发者签名和公证的个人试用包。
确认是赠送者发来的文件后，可按 macOS 提示在「系统设置 → 隐私与安全性」中为这次文件选择「仍要打开」。
Apple 官方说明：https://support.apple.com/zh-cn/102445

若提示未连接，请检查数据线后重新双击安装；异常时窗口会显示原因和日志位置。
不需要让 AI 帮忙安装，不需要额外安装 Python、Node、Arduino 或填写 API Key。
安装完成后可以删除此文件夹。若要卸载，重新解压后双击「卸载小花.command」。
卸载会移除全部后台联动及 DSH 插件配置，不卸载应用本身；备份和日志保留。
卸载后退出并重新打开 DSH。若其他 DSH profile 仍引用插件，会保留共享插件文件。

适用于 Apple 芯片 Mac（包含 M3），小花后台支持 macOS 12 及以上；DSH 适配需要 macOS 13 及以上。
安装到当前用户目录，无需管理员密码。
仅跟随本机任务。硬件由提供者预先烧录，本包不会烧录固件。
程序和独立 Python 均随包提供，安装时不下载程序，不包含赠送者的账户、聊天或配置。
"""


def launcher(action: str) -> str:
    title = "安装" if action == "install" else "卸载"
    confirm = '' if action == "install" else '''
printf '确认卸载小花的 Codex、WorkBuddy 和 DSH 全部联动？输入 y 后回车，其他输入取消：'
read -r flower_answer
if [[ "$flower_answer" != y && "$flower_answer" != Y ]]; then exit 0; fi
'''
    success = ("安装成功，旋转和提醒灯已连接。以后登录 Mac 会自动运行。\n现在可以关闭窗口，去已启用的应用中试一次工作转动、等待时亮灯和结束停转。"
               if action == "install" else "小花的全部后台联动已卸载。现在可以关闭窗口。")
    return f'''#!/bin/bash
flower_directory="$(cd -- "$(dirname -- "$0")" && pwd)"
printf '\\n小花 · Mac 统一{title}\\n\\n'
{confirm}
flower_log="$(/usr/bin/mktemp "${{TMPDIR:-/tmp}}/flower-{action}.XXXXXX")" || exit 1
echo '正在{title}，请稍候…'
/bin/bash "$flower_directory/安装资源/integrated_install.sh" {action} > "$flower_log" 2>&1
flower_result=$?
echo
/usr/bin/grep -E '^(已启用联动：|DSH )' "$flower_log" || true
case "$flower_result" in
  0) printf '%s\\n' '{success}' ;;
  5) echo '安装已完成。打开下方应用后，小花会自动联动。'
     /usr/bin/grep '^等待应用：' "$flower_log" || true ;;
  3) echo '后台已安装，但连接或应用状态自检尚未通过。'
     /usr/bin/tail -n 5 "$flower_log" ;;
  4) echo '控制板尚不支持提醒灯，请联系提供者更新硬件或固件。' ;;
  *) echo '{title}没有完成。请把下方提示发给小花的提供者：'
     /usr/bin/tail -n 8 "$flower_log" ;;
esac
printf '\\n详细记录：%s\\n' "$flower_log"
if [[ -t 0 ]]; then
  printf '\\n按回车结束，或直接关闭窗口…'
  read -r flower_reply
fi
exit "$flower_result"
'''


def build(output: Path, python_archive: Path) -> Path:
    digest = hashlib.sha256(python_archive.read_bytes()).hexdigest()
    if digest != PYTHON_SHA256:
        raise ValueError("Python archive differs from the pinned official SHA256")
    root = Path(__file__).parent
    missing = [name for name in BRIDGE_FILES if not (root / 'integrated' / name).is_file()]
    missing += [name for name in RUNTIME_FILES if not (root / name).is_file()]
    if missing:
        raise ValueError('Missing package sources: ' + ', '.join(missing))
    output.mkdir(parents=True, exist_ok=True)
    # Fresh staging prevents old caches, bytecode or obsolete source from leaking
    # into a rebuild. The package only includes an explicit source allowlist.
    with tempfile.TemporaryDirectory(prefix='.flower-package.', dir=output) as temp:
        folder = Path(temp) / NAME
        resources = folder / "安装资源"
        bridge = resources / 'integrated'
        bridge.mkdir(parents=True)
        for name in RUNTIME_FILES:
            (resources / name).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(root / name, resources / name)
        for name in BRIDGE_FILES:
            shutil.copy2(root / 'integrated' / name, bridge / name)
        shutil.copy2(python_archive, resources / "python-arm64.tar.gz")
        shutil.copy2(root.parent / "LICENSE", resources / "LICENSE")
        (resources / "Python来源.txt").write_text(
            f"Unmodified python-build-standalone CPython 3.13.12, Apple Silicon.\n{PYTHON_URL}\nSHA256: {digest}\n"
            "Python and bundled third-party license notices are included in the runtime archive.\n")
        checksums = {p.relative_to(resources).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                     for p in sorted(resources.rglob('*')) if p.is_file()}
        (resources / 'SHA256SUMS').write_text(''.join(f'{h}  {n}\n' for n, h in checksums.items()))
        for action, name in (("install", "安装小花.command"), ("uninstall", "卸载小花.command")):
            path = folder / name
            path.write_text(launcher(action))
            path.chmod(0o755)
        (folder / '先看这里.txt').write_text(GUIDE)
        archive = output / f'{NAME}.zip'
        with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as zipped:
            for path in sorted(folder.rglob('*')):
                if path.is_file():
                    zipped.write(path, str(Path(NAME) / path.relative_to(folder)))
        final_folder = output / NAME
        if final_folder.exists():
            if final_folder.is_symlink():
                raise ValueError('Refusing to replace a symlink output folder')
            shutil.rmtree(final_folder)
        shutil.copytree(folder, final_folder)
    (output / 'package_manifest.json').write_text(json.dumps({
        'version': VERSION, 'architecture': 'arm64', 'source_selection': 'installed-apps',
        'supported_sources': ['codex', 'workbuddy', 'dsh'], 'python_source': PYTHON_URL,
        'python_sha256': digest, 'resources': checksums,
        'zip_sha256': hashlib.sha256(archive.read_bytes()).hexdigest(),
        'apple_developer_signed': False, 'notarized': False,
        'installation_network_downloads': False,
    }, ensure_ascii=False, indent=2) + '\n')
    return archive


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--python-archive', type=Path, required=True)
    args = parser.parse_args()
    print(build(args.output, args.python_archive))
