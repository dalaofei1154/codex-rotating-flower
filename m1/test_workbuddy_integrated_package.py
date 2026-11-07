import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

sys.path.insert(0, str(Path(__file__).parent))
import package_workbuddy_integrated as package


# The packager builds a /bin/bash launcher and records POSIX file modes.
@unittest.skipUnless(sys.platform == "darwin", "macOS package tests")
class IntegratedPackageTests(unittest.TestCase):
    def test_build_allowlist_excludes_private_and_stale_files_and_preserves_modes(self):
        with tempfile.TemporaryDirectory(prefix='小花 package ') as temp:
            root = Path(temp)
            source = root / 'm1'
            source.mkdir()
            integrated = source / 'integrated'
            integrated.mkdir()
            (root / 'LICENSE').write_text('fixture license')
            for name in package.BRIDGE_FILES:
                (integrated / name).write_text('# fixture ' + name)
            for name in ('attention-cache.json', 'status.json', 'test_private.py', 'obsolete.py'):
                (integrated / name).write_text('private fixture')
            for name in package.RUNTIME_FILES:
                (source / name).write_text('# fixture ' + name)
            runtime = root / 'python.tar.gz'
            runtime.write_bytes(b'fixture runtime')
            output = root / 'out'
            stale = output / package.NAME / '安装资源' / 'integrated'
            stale.mkdir(parents=True)
            (stale / 'old-private.py').write_text('private stale')
            with patch.object(package, '__file__', str(source / 'package.py')), \
                 patch.object(package, 'PYTHON_SHA256', hashlib.sha256(runtime.read_bytes()).hexdigest()):
                archive = package.build(output, runtime)
            manifest = json.loads((output / 'package_manifest.json').read_text())
            self.assertEqual(manifest['zip_sha256'], hashlib.sha256(archive.read_bytes()).hexdigest())
            with zipfile.ZipFile(archive) as zipped:
                contents = zipped.namelist()
                self.assertEqual({Path(n).name for n in contents if '/integrated/' in n}, set(package.BRIDGE_FILES))
                for n in contents:
                    self.assertNotIn(b'private', zipped.read(n))
                command = zipped.getinfo(package.NAME + '/安装小花.command')
                self.assertTrue((command.external_attr >> 16) & 0o111)
                for name, digest in manifest['resources'].items():
                    self.assertEqual(hashlib.sha256(zipped.read(package.NAME + '/安装资源/' + name)).hexdigest(), digest)
            self.assertFalse((stale / 'old-private.py').exists())

    def test_missing_adapter_stops_build(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'integrated').mkdir()
            archive = root / 'python.tar.gz'
            archive.write_bytes(b'fixture')
            with patch.object(package, '__file__', str(root / 'package.py')), \
                 patch.object(package, 'PYTHON_SHA256', hashlib.sha256(archive.read_bytes()).hexdigest()):
                with self.assertRaisesRegex(ValueError, 'workbuddy_adapter.py'):
                    package.build(root / 'out', archive)
            self.assertFalse((root / 'out').exists())

    def test_unverified_python_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            archive = Path(temp) / 'python.tar.gz'
            archive.write_bytes(b'not official')
            with self.assertRaisesRegex(ValueError, 'SHA256'):
                package.build(Path(temp) / 'out', archive)

    def test_legacy_motor_only_result_does_not_claim_full_install(self):
        with tempfile.TemporaryDirectory(prefix='小花 runner ') as temp:
            root = Path(temp)
            (root / '安装资源').mkdir()
            (root / '安装资源/integrated_install.sh').write_text('exit 4\n')
            command = root / '安装小花.command'
            command.write_text(package.launcher('install'))
            result = subprocess.run(['/bin/bash', str(command)], input='', capture_output=True, text=True, timeout=5)
            self.assertEqual(result.returncode, 4)
            self.assertIn('尚不支持提醒灯', result.stdout)
            self.assertNotIn('安装成功', result.stdout)
            log = next(line.removeprefix('详细记录：') for line in result.stdout.splitlines() if line.startswith('详细记录：'))
            Path(log).unlink()

    def test_waiting_app_is_installed_without_claiming_all_sources_ready(self):
        with tempfile.TemporaryDirectory(prefix='小花 unified runner ') as temp:
            root = Path(temp)
            (root / '安装资源').mkdir()
            (root / '安装资源/integrated_install.sh').write_text(
                "echo '已启用联动：Codex + WorkBuddy'\n"
                "echo '等待应用：Codex — 打开 Codex 后会自动联动。'\nexit 5\n")
            command = root / '安装小花.command'
            command.write_text(package.launcher('install'))
            result = subprocess.run(['/bin/bash', str(command)], input='', capture_output=True,
                                    text=True, timeout=5)
            self.assertEqual(result.returncode, 5)
            self.assertIn('已启用联动：Codex + WorkBuddy', result.stdout)
            self.assertIn('安装已完成', result.stdout)
            self.assertIn('等待应用：Codex', result.stdout)
            self.assertNotIn('安装成功，旋转和提醒灯已连接', result.stdout)
            self.assertNotIn('安装没有完成', result.stdout)
            log = next(line.removeprefix('详细记录：') for line in result.stdout.splitlines()
                       if line.startswith('详细记录：'))
            Path(log).unlink()


if __name__ == '__main__':
    unittest.main()
