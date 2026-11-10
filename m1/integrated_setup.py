#!/usr/bin/env python3
"""Install/upgrade the combined flower service without losing existing sources."""
from __future__ import annotations

import argparse
from contextlib import closing
import datetime as dt
import json
import os
from pathlib import Path
import plistlib
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
import uuid

if sys.platform == "darwin":
    import fcntl
else:  # This installer drives launchctl and only exists for macOS.
    fcntl = None

from dsh_setup import DshPluginChange, dsh_home

sys.path.insert(0, str(Path(__file__).resolve().parent / 'integrated'))
from source_config import CHOICES, LABELS, enabled_sources, selection_for

VERSION = '0.7.0'
LABEL = 'com.rotatingflower.codex-motor'
REVISION = 'integrated-v' + VERSION
# Modules shared with the standalone bridge; imported by integrated_bridge.py.
SHARED_MODULES = ('serial_link.py', 'process_lock.py', 'process_probe.py')


def locations():
    home = Path.home()
    return (home / 'Library/Application Support/RotatingFlower',
            home / 'Library/LaunchAgents' / (LABEL + '.plist'),
            home / 'Library/Logs/RotatingFlower')


def launchctl(*args, check=True):
    try:
        result = subprocess.run(['launchctl', *args], capture_output=True, text=True, timeout=15)
    except subprocess.TimeoutExpired:
        if check:
            raise RuntimeError('系统服务操作超时，安装已停止。')
        return False
    if check and result.returncode:
        raise RuntimeError(f"系统服务操作失败：{result.stderr.strip() or result.stdout.strip()}")
    return result.returncode == 0


def running():
    try:
        result = subprocess.run(['launchctl', 'print', f'gui/{os.getuid()}/{LABEL}'],
                                capture_output=True, text=True, timeout=5)
        return result.returncode == 0 and 'state = running' in result.stdout
    except subprocess.SubprocessError:
        return False


def existing():
    support, plist, _ = locations()
    if not plist.exists():
        return None
    payload = plistlib.loads(plist.read_bytes())
    args = payload.get('ProgramArguments', [])
    entries = [Path(value) for value in args if isinstance(value, str) and value.endswith('.py')]
    if len(entries) != 1:
        raise RuntimeError('现有小花服务格式不识别，已保留原服务，请联系提供者。')
    entry = entries[0]
    valid = ((entry == support / 'global_bridge.py') or
             (entry.name == 'integrated_bridge.py' and entry.parent in (
                 support / 'software_adapt_20261103', support / 'integrated_20261103',
                 support / 'integrated-v0.5.0', support / 'integrated-v0.6.0', support / REVISION)))
    if not valid:
        raise RuntimeError(f'现有小花版本不是本包可升级的版本：{entry}。已停止，避免覆盖更新版本。')
    options = {}
    for key in ('--source', '--sessions-root', '--workbuddy-root', '--port', '--attention-cache'):
        if key in args:
            index = args.index(key)
            if index + 1 >= len(args):
                raise RuntimeError('现有服务参数不完整，未更改服务。')
            options[key] = args[index + 1]
    options.setdefault('--source', 'codex')
    if options['--source'] not in CHOICES:
        raise RuntimeError('现有服务来源不识别，未更改服务。')
    return {'payload': payload, 'options': options, 'entry': entry, 'plist_bytes': plist.read_bytes()}


# Match actual application identity, not data directories left after uninstall.
APP_IDS = {'codex': 'com.openai.codex', 'workbuddy': 'com.tencent.workbuddy.mac',
           'dsh': 'com.deepseek.dsh'}


def application_roots():
    return (Path('/Applications'), Path.home() / 'Applications')


def app_candidates():
    candidates = []
    for root in application_roots():
        try:
            candidates.extend(root.glob('*.app'))
            # Handle Applications/Utilities or another one-level app grouping.
            for child in root.iterdir() if root.is_dir() else ():
                if child.is_dir() and child.suffix != '.app':
                    candidates.extend(child.glob('*.app'))
        except OSError:
            continue
    query = ' || '.join(f'kMDItemCFBundleIdentifier == "{value}"' for value in APP_IDS.values())
    try:
        result = subprocess.run(['/usr/bin/mdfind', query], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            candidates.extend(Path(line) for line in result.stdout.splitlines() if line.endswith('.app'))
    except (OSError, subprocess.SubprocessError):
        pass
    # Spotlight can lag behind a new or relocated app. A running executable's
    # bundle is another candidate, still subject to the same plist validation.
    try:
        result = subprocess.run(['/bin/ps', '-axo', 'comm='], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            for line in result.stdout.splitlines():
                path, marker, _ = line.strip().partition('.app/Contents/MacOS/')
                if marker and path.startswith('/'):
                    candidates.append(Path(path + '.app'))
    except (OSError, subprocess.SubprocessError):
        pass
    return candidates


def detect_apps():
    found = {}
    for path in app_candidates():
        try:
            path = path.resolve()
            if any(part in ('.Trash', '.Trashes') for part in path.parts):
                continue
            info = plistlib.loads((path / 'Contents/Info.plist').read_bytes())
            if not isinstance(info, dict):
                continue
            bundle_id = info.get('CFBundleIdentifier')
            name = next((key for key, value in APP_IDS.items() if value == bundle_id), None)
            executable = info.get('CFBundleExecutable')
            if (name is None or name in found or info.get('CFBundlePackageType') != 'APPL'
                    or not isinstance(executable, str) or Path(executable).name != executable):
                continue
            binary = path / 'Contents/MacOS' / executable
            if not binary.is_file() or not os.access(binary, os.X_OK):
                continue
            found[name] = {'path': str(path), 'bundle_id': bundle_id,
                           'version': str(info.get('CFBundleShortVersionString', 'unknown'))}
        except (OSError, ValueError, plistlib.InvalidFileException):
            continue
    return found


def configuration(previous, requested_source=None, workbuddy_root=None):
    options = previous['options'] if previous else {}
    apps = detect_apps()
    if requested_source:
        source = requested_source
        enabled = enabled_sources(source)
        if any(name not in apps for name in enabled):
            raise RuntimeError('没有找到所选应用的有效安装，请先安装并打开所选应用。')
    else:
        if not apps:
            raise RuntimeError('没有检测到已安装的 Codex、WorkBuddy 或 DeepSeek Harness。'
                               '请先安装其中一个应用，再双击安装小花。')
        source = selection_for(apps)
    home = Path.home()
    roots = [home / '.workbuddy', home / '.workbuddy-ai']
    default_wb = next((p for p in roots if (p / 'workbuddy.db').is_file()), roots[0])
    return {'source': source, 'installed_apps': apps,
            'sessions_root': Path(options.get('--sessions-root', str(home / '.codex/sessions'))),
            'workbuddy_root': Path(workbuddy_root or options.get('--workbuddy-root', default_wb)),
            'port': options.get('--port', 'auto')}


def preflight(config):
    """Report data readiness without confusing uninitialized apps with damage.

    The background adapter retries as apps are opened. Neither missing initial
    data nor a bad source prevents the other configured source being installed;
    verify() must not report a broken source as ready.
    """
    enabled = enabled_sources(config['source'])
    result = {}
    if 'codex' in enabled:
        path = config['sessions_root']
        result['codex'] = {'readiness': 'ready' if path.is_dir() else 'not_initialized'}
        if path.exists() and not path.is_dir():
            result['codex'] = {'readiness': 'error', 'error': 'Codex 任务目录不是文件夹'}
    if 'workbuddy' in enabled:
        db = config['workbuddy_root'] / 'workbuddy.db'
        if not db.exists():
            result['workbuddy'] = {'readiness': 'not_initialized'}
        elif not db.is_file():
            result['workbuddy'] = {'readiness': 'error', 'error': 'WorkBuddy 数据库不是普通文件'}
        else:
            try:
                with closing(sqlite3.connect(db.resolve().as_uri() + '?mode=ro', uri=True, timeout=1)) as connection:
                    columns = {row[1] for row in connection.execute('PRAGMA table_info(sessions)')}
                    if not {'id', 'status', 'updated_at', 'transport', 'deleted_at'} <= columns:
                        raise ValueError('WorkBuddy 任务数据库格式尚未适配')
                result['workbuddy'] = {'readiness': 'ready'}
            except (OSError, sqlite3.Error, ValueError) as exc:
                result['workbuddy'] = {'readiness': 'error', 'error': str(exc)}
    if 'dsh' in enabled:
        status_file = Path.home() / 'Library/Application Support/RotatingFlower/dsh/status.json'
        result['dsh'] = {'readiness': 'ready'} if status_file.is_file() else {'readiness': 'not_initialized'}
    config['preflight'] = result
    for name, state in result.items():
        label = LABELS[name]
        if state['readiness'] == 'not_initialized' and name == 'dsh':
            print('DeepSeek Harness 尚未初始化；本次会安装插件，请在安装后退出并重新打开 DeepSeek Harness。')
        elif state['readiness'] == 'not_initialized':
            print(f'{label} 尚未初始化；小花服务将等待应用打开，随后自动连接。')
        elif state['readiness'] == 'error':
            print(f'{label} 数据检查异常：{state["error"]}；不会标记为已就绪。')
    return result


def source_directory():
    return Path(__file__).resolve().parent / 'integrated'


def install(config, previous=None):
    """Stage files, stop one serial owner, migrate caches, atomically replace service."""
    preflight(config)
    support, plist, logs = locations()
    source = source_directory()
    files = sorted(p for p in source.glob('*.py') if not p.name.startswith('test_'))
    # The shared modules live one level up; a fixture tree has no parent
    # copy, so only a real source tree is checked.
    shared = source.parent
    for name in SHARED_MODULES:
        candidate = shared / name
        if candidate.is_file():
            files.append(candidate)
        elif (shared / 'global_bridge.py').is_file():
            raise RuntimeError(f'安装文件不完整，缺少 {name}，请重新解压完整安装包。')
    if not (source / 'integrated_bridge.py').is_file() or not files:
        raise RuntimeError('安装文件不完整，请重新解压完整安装包。')
    support.mkdir(parents=True, exist_ok=True)
    logs.mkdir(parents=True, exist_ok=True)
    plist.parent.mkdir(parents=True, exist_ok=True)
    target = support / REVISION
    stamp = dt.datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    backup = support / 'backups' / ('integrated-' + stamp)
    backup.mkdir(parents=True)
    if previous:
        (backup / 'service.plist').write_bytes(previous['plist_bytes'])
    stage = Path(tempfile.mkdtemp(prefix='.integrated-stage.', dir=support))
    for file in files:
        shutil.copy2(file, stage / file.name)
    (stage / 'version.json').write_text(json.dumps({'version': VERSION, 'source': config['source'],
        'installed_apps': config.get('installed_apps', {})}, ensure_ascii=False) + '\n')
    launch_id = str(uuid.uuid4())
    args = [sys.executable, '-E', '-s', str(target / 'integrated_bridge.py'),
            '--source', config['source'], '--sessions-root', str(config['sessions_root']),
            '--workbuddy-root', str(config['workbuddy_root']), '--port', config['port'],
            '--status-file', str(target / 'status.json'), '--launch-id', launch_id]
    payload = {'Label': LABEL, 'ProgramArguments': args, 'RunAtLoad': True, 'KeepAlive': True,
               'ThrottleInterval': 5, 'StandardOutPath': str(logs / 'bridge-integrated.log'),
               'StandardErrorPath': str(logs / 'bridge-integrated-error.log')}
    domain = f'gui/{os.getuid()}'
    moved_target = False
    placed_target = False
    old_was_running = running()
    stopped_previous = False
    dsh_change = None
    try:
        if 'dsh' in enabled_sources(config['source']):
            dsh_change = DshPluginChange(dsh_home(), support / 'dsh',
                Path(__file__).parent / 'dsh' / 'flower-observer.mjs', backup=backup)
            dsh_change.apply()
            print('DSH 本地插件已注册；请退出并重新打开 DeepSeek Harness。')
        if previous:
            if not launchctl('bootout', domain, str(plist), check=False) and running():
                raise RuntimeError('旧服务仍在运行，已停止升级，避免两个程序同时控制小花。')
            stopped_previous = True
        if previous:
            caches = {'attention-cache.json': Path(previous['options'].get('--attention-cache',
                                                      previous['entry'].parent / 'attention-cache.json')),
                      'workbuddy-cache.json': previous['entry'].parent / 'workbuddy-cache.json'}
            for name, path in caches.items():
                if path.is_file():
                    shutil.copy2(path, stage / name)
                    shutil.copy2(path, backup / name)
        if target.exists():
            target.rename(backup / 'previous-runtime')
            moved_target = True
        stage.rename(target)
        placed_target = True
        temp = plist.with_suffix('.tmp')
        temp.write_bytes(plistlib.dumps(payload))
        temp.replace(plist)
        started_at = time.time()
        launchctl('bootstrap', domain, str(plist))
    except BaseException:
        if dsh_change:
            dsh_change.rollback()
        if placed_target:
            launchctl('bootout', domain, str(plist), check=False)
            shutil.rmtree(target)
        if moved_target:
            (backup / 'previous-runtime').rename(target)
        if previous:
            plist.write_bytes(previous['plist_bytes'])
            if old_was_running and stopped_previous:
                restored = launchctl('bootstrap', domain, str(plist), check=False)
                if not restored:
                    print('原配置已恢复，但原服务未能自动启动；请保留此日志联系提供者。', file=sys.stderr)
        else:
            plist.unlink(missing_ok=True)
        raise
    finally:
        if stage.exists():
            shutil.rmtree(stage)
    print(f'已设置登录自启；来源：{config["source"]}；备份：{backup}')
    print('已启用联动：' + ' + '.join(LABELS[name] for name in enabled_sources(config['source'])))
    return {'launch_id': launch_id, 'started_at': started_at, 'status_file': target / 'status.json',
            'source': config['source']}


def verify(receipt, seconds=12):
    deadline = time.monotonic() + seconds
    last = {}
    while True:
        try:
            last = json.loads(receipt['status_file'].read_text())
        except (OSError, ValueError):
            last = {}
        if not isinstance(last, dict):
            last = {}
        current = (last.get('launch_id') == receipt['launch_id'] and
                   type(last.get('updated_at')) in (int, float) and
                   receipt['started_at'] <= last['updated_at'] <= time.time() + 2 and
                   time.time() - last['updated_at'] < 5)
        sources = last.get('sources', {})
        if not isinstance(sources, dict):
            sources = {}
        source = receipt.get('source', 'workbuddy')
        enabled = enabled_sources(source)
        waiting, errors = {}, {}
        for name in enabled:
            state = sources.get(name)
            if not isinstance(state, dict):
                errors[name] = '尚未收到此应用的状态'
                continue
            readiness = state.get('readiness')
            if readiness == 'ready' and state.get('healthy') is True and not state.get('error'):
                continue
            if (readiness in ('not_running', 'not_initialized') and state.get('healthy') is False
                    and not state.get('error')):
                waiting[name] = state.get('detail') or ('尚未打开' if readiness == 'not_running' else '尚未初始化')
            else:
                errors[name] = state.get('error') or '任务状态无法验证或格式不兼容'
        capabilities = last.get('device_capabilities', [])
        valid_capabilities = isinstance(capabilities, list) and all(isinstance(v, str) for v in capabilities)
        connected = (current and running() and last.get('device_connected') is True)
        complete_device = connected and valid_capabilities and {'motor', 'attention'} <= set(capabilities)
        if complete_device and not waiting and not errors:
            print('安装自检通过：后台服务运行，已启用应用就绪，旋转与提醒灯控制板已连接。')
            return 0
        if connected and valid_capabilities and 'motor' in capabilities and 'attention' not in capabilities:
            print('这块控制板只有旋转功能，尚不支持提醒灯；请联系提供者升级硬件/固件。本安装包不会烧录固件。')
            return 4
        if time.monotonic() >= deadline:
            if complete_device and waiting and not errors:
                print('小花后台已安装，旋转和提醒灯已连接；以下应用待打开或初始化：')
                for name, detail in waiting.items():
                    label = LABELS.get(name, name)
                    print(f'等待应用：{label} — {detail}')
                print('打开相应应用并开始使用后会自动连接，不需要重新安装。')
                return 5
            if current and (errors or waiting):
                print('后台设置已保存，可用来源继续运行；尚未完成全部适配自检。')
                for name, reason in {**waiting, **errors}.items():
                    label = LABELS.get(name, name)
                    print(f'{label} 状态：{reason}')
                    if name in errors:
                        print('请保留此日志联系小花提供者，不要将该应用当作已就绪。')
                    else:
                        print(f'打开 {label} 后会自动重试连接，不需要重新安装。')
            if not complete_device:
                print('旋转与提醒灯连接检查未通过，请检查 USB 数据线、配件连接许可及控制板版本。')
            print('服务日志：' + str(locations()[2] / 'bridge-integrated-error.log'))
            return 3
        time.sleep(.4)


def uninstall(previous):
    support, plist, _ = locations()
    backup = support / 'backups' / ('uninstall-' + dt.datetime.now().strftime('%Y%m%d-%H%M%S-%f'))
    backup.mkdir(parents=True, exist_ok=True)
    if previous:
        (backup / 'service.plist').write_bytes(previous['plist_bytes'])
    was_running = running() if previous else False
    if previous and not launchctl('bootout', f'gui/{os.getuid()}', str(plist), check=False) and running():
        raise RuntimeError('服务仍在运行，卸载已停止。')
    change = DshPluginChange(dsh_home(), support / 'dsh', backup=backup)
    try:
        change.apply()
        plist.unlink(missing_ok=True)
    except BaseException:
        change.rollback()
        if previous and was_running:
            launchctl('bootstrap', f'gui/{os.getuid()}', str(plist), check=False)
        raise
    print('小花后台服务与登录自启已全部移除；Codex、WorkBuddy 和 DSH 均不再联动。备份和日志保留。')
    if change.removed:
        print('DSH 插件配置已移除，请退出并重新打开 DeepSeek Harness。')
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['install', 'uninstall', 'status'])
    parser.add_argument('--source', choices=CHOICES)
    parser.add_argument('--workbuddy-root', type=Path)
    parser.add_argument('--verify-seconds', type=float, default=12)
    args = parser.parse_args(argv)
    if sys.platform != 'darwin':
        parser.error('仅支持 macOS')
    if not 0 <= args.verify_seconds <= 30:
        parser.error('自检时间必须在 0 到 30 秒之间')
    support, _, _ = locations()
    support.mkdir(parents=True, exist_ok=True)
    # Separate from the bridge's serial lock. Prevent two installers racing.
    with (support / '.installer.lock').open('a+') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            previous = existing()
            if args.action == 'status':
                print(json.dumps({'installed': previous is not None, 'running': running(),
                                  'source': previous['options']['--source'] if previous else None}, ensure_ascii=False))
                return 0
            if args.action == 'uninstall':
                return uninstall(previous)
            receipt = install(configuration(previous, args.source, args.workbuddy_root), previous)
            return verify(receipt, args.verify_seconds)
        except BlockingIOError:
            print('另一个小花安装程序正在运行，请等待它完成。', file=sys.stderr)
            return 1
        except (OSError, ValueError, RuntimeError, sqlite3.Error, subprocess.SubprocessError) as exc:
            print(f'未完成：{exc}', file=sys.stderr)
            return 1


if __name__ == '__main__':
    sys.exit(main())
