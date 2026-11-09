"""Register the local DSH observer with reversible, byte-preserving changes."""
from __future__ import annotations
import argparse
import base64
import hashlib
import json
import os
import re
import sys
import tempfile
from pathlib import Path

BEGIN = '# BEGIN ROTATING-FLOWER DSH OBSERVER'
END = '# END ROTATING-FLOWER DSH OBSERVER'
PLUGIN_ID = 'rotating-flower-observer'
OBSERVER_NAME = 'flower-observer.mjs'


class SetupError(RuntimeError):
    pass


def dsh_home():
    return Path(os.environ.get('DSH_HOME') or Path.home() / '.dsh')


def support_root():
    return Path.home() / 'Library' / 'Application Support' / 'RotatingFlower' / 'dsh'


def profile_patch(home, profile='desktop'):
    if not profile or Path(profile).name != profile or profile in ('.', '..'):
        raise SetupError('DSH profile 必须是一个目录名。')
    return Path(home) / 'profiles' / profile / 'cordis.patch.yml'


def managed_block(observer):
    return '\n'.join([BEGIN, '- insert:', f'    - id: {PLUGIN_ID}',
                      f'      name: {json.dumps(str(observer), ensure_ascii=False)}', END])


def _locate_block(text):
    lines = text.splitlines(keepends=True)
    begins = [i for i, line in enumerate(lines) if line.strip() == BEGIN]
    ends = [i for i, line in enumerate(lines) if line.strip() == END]
    if not begins and not ends:
        if PLUGIN_ID in text:
            raise SetupError('DSH 中已有非标准小花插件配置，请先核对；未修改原配置。')
        return None
    if len(begins) != 1 or len(ends) != 1 or ends[0] < begins[0]:
        raise SetupError('cordis.patch.yml 里的小花区块不完整，请手工修好后再试。')
    return sum(map(len, lines[:begins[0]])), sum(map(len, lines[:ends[0] + 1]))


def has_block(text):
    return _locate_block(text) is not None


def _content_lines(text):
    return [value for line in text.splitlines()
            if (value := line.split('#', 1)[0].strip()) and value != '---']


def _ensure_list(text):
    if not _content_lines(text):
        return text + ('' if not text or text.endswith('\n') else '\n') + '[]\n'
    return text


def apply_block(text, block):
    found = _locate_block(text)
    if found:
        start, end = found
        return text[:start] + block + '\n' + text[end:]
    lines = text.splitlines(keepends=True)
    content = _content_lines(text)
    if len(content) == 1 and re.fullmatch(r'\[\s*\]', content[0]):
        # Preserve inline comments as well as comments on their own lines.
        text = ''.join((re.sub(r'^\s*\[\s*\][ \t]*', '', line) if '#' in line else '')
                       if re.fullmatch(r'\s*\[\s*\][ \t]*(?:#[^\r\n]*)?[\r\n]*', line)
                       else line for line in lines)
    return text + ('' if not text or text.endswith(('\n', '\r')) else '\n') + block + '\n'


def strip_block(text):
    found = _locate_block(text)
    if found is None:
        return text
    start, end = found
    return text[:start] + text[end:]


def _write_atomic(path, data, mode=0o600):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, name = tempfile.mkstemp(prefix='.' + path.name + '.', dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(fd, 'wb') as handle:
            handle.write(data)
        temporary.chmod(mode)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


class DshPluginChange:
    """A transaction retained until the enclosing bridge operation succeeds.

    rollback only restores bytes this instance wrote, never a later user edit.
    A private receipt preserves the pre-install patch for an exact uninstall
    when the installed patch is unchanged. Later user edits are kept verbatim.
    """
    def __init__(self, home, root, source=None, profile='desktop', backup=None):
        self.home = Path(home).resolve()
        self.root = Path(root).resolve()
        self.patch = profile_patch(self.home, profile)
        self.plugin = self.root / OBSERVER_NAME
        digest = hashlib.sha256(str(self.patch).encode()).hexdigest()[:16]
        self.receipt = self.root / ('install-state-' + digest + '.json')
        self.source = Path(source) if source else None
        self.profile = profile
        self.backup_root = Path(backup) if backup else self.root / 'backups'
        self.original = {}
        self.written = {}
        self.backup = None
        self.changed = False
        self.removed = []

    def _remember(self, path):
        if path not in self.original:
            self.original[path] = (path.read_bytes() if path.exists() else None,
                                   path.stat().st_mode & 0o777 if path.exists() else 0o600)
        return self.original[path][0]

    def _change(self, path, data):
        original = self._remember(path)
        if original == data:
            return
        current = path.read_bytes() if path.exists() else None
        if current != original:
            raise SetupError('DSH 配置在安装过程中改变，已停止以避免覆盖。')
        if original is not None:
            self.backup_root.mkdir(parents=True, exist_ok=True, mode=0o700)
            fd, name = tempfile.mkstemp(prefix=path.name + '.', suffix='.bak', dir=self.backup_root)
            with os.fdopen(fd, 'wb') as handle:
                handle.write(original)
            if path == self.patch:
                self.backup = Path(name)
        if data is None:
            path.unlink(missing_ok=True)
            self.removed.append(path)
        else:
            _write_atomic(path, data, self.original[path][1])
        self.written[path] = data

    def apply(self):
        try:
            return self._apply()
        except BaseException:
            self.rollback()
            raise

    def _apply(self):
        before = self._remember(self.patch)
        receipt_bytes = self._remember(self.receipt)
        saved = None
        if receipt_bytes:
            try:
                saved = json.loads(receipt_bytes)
                if (not isinstance(saved, dict) or saved.get('patch') != str(self.patch)
                        or not isinstance(saved.get('before'), str) or not isinstance(saved.get('after'), str)):
                    raise ValueError('invalid receipt')
                saved['before_bytes'] = base64.b64decode(saved['before'], validate=True)
                saved['after_bytes'] = base64.b64decode(saved['after'], validate=True)
            except (ValueError, TypeError) as exc:
                raise SetupError('小花安装记录损坏，未修改 DSH 配置。') from exc
        text = (before or b'').decode('utf-8')
        found = _locate_block(text)  # Validate before touching the existing plugin.
        if self.source:
            if not self.source.is_file():
                raise SetupError(f'找不到插件文件：{self.source}')
            if before is None:
                raise SetupError(f'找不到 DeepSeek Harness 配置：{self.patch}\n请先打开一次 DeepSeek Harness。')
            after = apply_block(text, managed_block(self.plugin)).encode('utf-8')
            # Preserve the first receipt across idempotent installs and upgrades.
            if saved and before == saved['after_bytes']:
                baseline = saved['before_bytes']
            elif found:
                baseline = _ensure_list(strip_block(text)).encode('utf-8')
            else:
                baseline = before
            receipt = json.dumps({'patch': str(self.patch),
                                  'before': base64.b64encode(baseline).decode('ascii'),
                                  'after': base64.b64encode(after).decode('ascii')}).encode() + b'\n'
            self._remember(self.plugin)
            # Recheck the patch after reading sources and before committing.
            data = self.source.read_bytes()
            if self.patch.read_bytes() != before:
                raise SetupError('DSH 配置在安装过程中改变，已停止以避免覆盖。')
            self._change(self.plugin, data)
            self._change(self.patch, after)
            self._change(self.receipt, receipt)
            self.changed = after != before
        else:
            if found:
                if saved and before == saved['after_bytes']:
                    after = saved['before_bytes']
                else:
                    # Legacy/manual installs have no receipt; keep a valid YAML list.
                    after = _ensure_list(strip_block(text)).encode('utf-8')
                self._change(self.patch, after)
                self.removed.append(self.patch)
            self._change(self.receipt, None)
            # A second profile may share the observer. Keep it while referenced.
            others = list((self.home / 'profiles').glob('*/cordis.patch.yml'))
            shared = any(p != self.patch and PLUGIN_ID in p.read_text(encoding='utf-8') for p in others)
            if not shared:
                self._change(self.plugin, None)
                self._change(self.root / 'status.json', None)
        return self

    def rollback(self):
        patch_now = self.patch.read_bytes() if self.patch.exists() else None
        preserve_plugin = (self.patch in self.written and patch_now != self.written[self.patch]
                           and patch_now is not None and PLUGIN_ID.encode() in patch_now)
        for path, written in reversed(list(self.written.items())):
            if preserve_plugin and path in (self.plugin, self.receipt):
                continue
            current = path.read_bytes() if path.exists() else None
            if current != written:
                continue
            original, mode = self.original[path]
            if original is None:
                path.unlink(missing_ok=True)
            else:
                _write_atomic(path, original, mode)
        self.written.clear()


def install(home=None, profile='desktop', root=None, observer_source=None):
    source = Path(observer_source) if observer_source else Path(__file__).parent / 'dsh' / OBSERVER_NAME
    change = DshPluginChange(home or dsh_home(), root or support_root(), source, profile).apply()
    return {'patch': change.patch, 'observer': change.plugin, 'backup': change.backup,
            'changed': change.changed, 'profile': profile}


def uninstall(home=None, profile='desktop', root=None):
    change = DshPluginChange(home or dsh_home(), root or support_root(), profile=profile).apply()
    return {'removed': change.removed}


def status(home=None, profile='desktop', root=None):
    root = Path(root) if root else support_root()
    patch = profile_patch(home or dsh_home(), profile)
    return {'profile': str(patch), 'profile_exists': patch.is_file(),
            'registered': patch.is_file() and has_block(patch.read_text(encoding='utf-8')),
            'observer': str(root / OBSERVER_NAME), 'observer_exists': (root / OBSERVER_NAME).is_file(),
            'status_file_exists': (root / 'status.json').is_file()}


def main(argv=None):
    parser = argparse.ArgumentParser(description='小花 × DeepSeek Harness 本地插件安装器')
    parser.add_argument('action', choices=('install', 'uninstall', 'status'))
    parser.add_argument('--profile', default='desktop')
    parser.add_argument('--dsh-home', type=Path, default=None)
    parser.add_argument('--support-root', type=Path, default=None)
    parser.add_argument('--observer', type=Path, default=None)
    args = parser.parse_args(argv)
    try:
        if args.action == 'install':
            result = install(args.dsh_home, args.profile, args.support_root, args.observer)
            print(f"已注册插件：{result['patch']}")
            print(f"插件文件：{result['observer']}")
            if result['backup']:
                print(f"原配置备份：{result['backup']}")
            print('请退出并重新打开 DeepSeek Harness，小花才会开始联动。')
        elif args.action == 'uninstall':
            result = uninstall(args.dsh_home, args.profile, args.support_root)
            if not result['removed']:
                print('没有找到已安装的小花插件。')
            for path in result['removed']:
                print(f'已移除：{path}')
            print('请重新打开 DeepSeek Harness 使其生效。')
        else:
            print(json.dumps(status(args.dsh_home, args.profile, args.support_root), indent=2, ensure_ascii=False))
    except (SetupError, OSError, UnicodeError) as exc:
        print(f'安装失败：{exc}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
