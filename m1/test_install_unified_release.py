"""Exercise the release entry without network access or touching a real service."""
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import unittest
import zipfile


SCRIPT = Path(__file__).with_name('install_unified_release.sh')
PINNED_SHA = 'a82b64865092d03672e4340752c0c574078149b9dbcfa028f9f3e3e995dd0c01'
RELEASE_URL = 'https://github.com/dalaofei1154/rotating-flower/releases/download/v0.6.0/RotatingFlower-Mac-v0.6.0.zip'
PROXY_VARIABLES = ('HTTPS_PROXY', 'https_proxy', 'ALL_PROXY', 'all_proxy')


# This exercises a /bin/bash release script, so it only runs on macOS.
@unittest.skipUnless(sys.platform == "darwin", "macOS release installer tests")
class ReleaseInstallerTests(unittest.TestCase):
    def run_installer(self, *, result=0, output='', corrupt=False, download_error=False,
                      missing_entry=False, platform='Darwin', architecture='arm64', uid='501', args=(),
                      proxy_settings='', proxy_error=False, proxy_environment=None):
        with tempfile.TemporaryDirectory(prefix='小花 release test ') as temp:
            root = Path(temp)
            home = root / 'home'
            home.mkdir()
            temporary = root / 'temporary'
            temporary.mkdir()
            archive = root / 'release.zip'
            installed = root / 'installed.txt'
            extracted = root / 'extracted.txt'
            curl_args = root / 'curl-args.json'
            curl_env = root / 'curl-environment.json'
            scutil_called = root / 'scutil-called.txt'
            payload = ("printf '%s\\n' \"$*\" >> " + shlex.quote(str(installed)) + '\n'
                       + 'printf %s ' + shlex.quote(output) + '\n'
                       + 'exit ' + str(result) + '\n')
            with zipfile.ZipFile(archive, 'w') as zipped:
                name = ('unexpected.txt' if missing_entry else
                        'RotatingFlower-Mac-v0.6.0/安装资源/integrated_install.sh')
                zipped.writestr(name, payload)
            expected = hashlib.sha256(archive.read_bytes()).hexdigest()
            if corrupt:
                with archive.open('ab') as stream:
                    stream.write(b'changed after release')

            # Replace OS/network boundaries only in this isolated script copy.
            # Production has no environment override for its URL or SHA256.
            source = SCRIPT.read_text()
            self.assertIn("flower_expected_sha='" + PINNED_SHA + "'", source)
            source = source.replace(PINNED_SHA, expected)
            programs = {
                'uname': 'import sys\nprint(' + repr(platform) + ' if sys.argv[1] == "-s" else '
                         + repr(architecture) + ')\n',
                'id': 'print(' + repr(uid) + ')\n',
                'curl': 'import json, os, pathlib, shutil, sys\n'
                        + 'pathlib.Path(' + repr(str(curl_args)) + ').write_text(json.dumps(sys.argv[1:]))\n'
                        + 'pathlib.Path(' + repr(str(curl_env)) + ').write_text(json.dumps({key: os.environ[key] '
                        + 'for key in ' + repr(PROXY_VARIABLES) + ' if key in os.environ}))\n'
                        + ('sys.exit(22)\n' if download_error else
                           'shutil.copyfile(' + repr(str(archive)) + ', sys.argv[sys.argv.index("--output") + 1])\n'),
                'scutil': 'import pathlib, sys\n'
                          + 'pathlib.Path(' + repr(str(scutil_called)) + ').write_text("called")\n'
                          + ('sys.exit(1)\n' if proxy_error else 'print(' + repr(proxy_settings) + ')\n'),
                'ditto': 'import pathlib, sys, zipfile\n'
                         + 'pathlib.Path(' + repr(str(extracted)) + ').write_text("extracted")\n'
                         + 'with zipfile.ZipFile(sys.argv[-2]) as zipped:\n    zipped.extractall(sys.argv[-1])\n',
            }
            for name, code in programs.items():
                program = root / ('fake-' + name)
                program.write_text('#!' + sys.executable + '\n' + code)
                program.chmod(0o755)
                system_path = ('/usr/sbin/' if name == 'scutil' else '/usr/bin/') + name
                self.assertIn(system_path, source)
                source = source.replace(system_path, shlex.quote(str(program)))
            copied_script = root / 'install.sh'
            copied_script.write_text(source)
            environment = dict(os.environ, HOME=str(home), TMPDIR=str(temporary))
            for key in PROXY_VARIABLES:
                environment.pop(key, None)
            environment.update(proxy_environment or {})
            completed = subprocess.run(['/bin/bash', str(copied_script), *args], env=environment,
                                       input='', capture_output=True, text=True, timeout=10)
            logs = list((home / 'Library/Logs/RotatingFlower').glob('install-release-*'))
            return {'returncode': completed.returncode, 'output': completed.stdout + completed.stderr,
                    'installed': installed.read_text().splitlines() if installed.exists() else [],
                    'extracted': extracted.exists(),
                    'curl_args': json.loads(curl_args.read_text()) if curl_args.exists() else None,
                    'curl_environment': json.loads(curl_env.read_text()) if curl_env.exists() else None,
                    'scutil_called': scutil_called.exists(),
                    'logs': [p.read_text() for p in logs], 'temporary': list(temporary.iterdir())}

    def test_verified_release_calls_real_entry_once_noninteractively(self):
        result = self.run_installer(output='已启用联动：Codex + WorkBuddy\n')
        self.assertEqual(result['returncode'], 0)
        self.assertEqual(result['installed'], ['install'])
        self.assertIn('安装成功', result['output'])
        self.assertIn('Codex + WorkBuddy', result['output'])
        self.assertEqual(result['logs'], ['已启用联动：Codex + WorkBuddy\n'])
        self.assertEqual(result['temporary'], [])
        arguments = result['curl_args']
        self.assertEqual(arguments[-1], RELEASE_URL)
        for flag, value in (('--proto', '=https'), ('--proto-redir', '=https'),
                            ('--connect-timeout', '30'), ('--max-time', '600')):
            self.assertEqual(arguments[arguments.index(flag) + 1], value)
        self.assertIn('--fail', arguments)
        self.assertIn('--location', arguments)

    def test_changed_archive_is_never_extracted_or_executed(self):
        result = self.run_installer(corrupt=True)
        self.assertEqual(result['returncode'], 1)
        self.assertIn('SHA256 校验失败', result['output'])
        self.assertFalse(result['extracted'])
        self.assertEqual(result['installed'], [])
        self.assertEqual(result['temporary'], [])

    def test_failed_download_never_executes_package(self):
        result = self.run_installer(download_error=True)
        self.assertEqual(result['returncode'], 1)
        self.assertFalse(result['extracted'])
        self.assertEqual(result['installed'], [])
        self.assertIn('下载未完成', result['output'])
        self.assertEqual(result['temporary'], [])

    def test_wrong_archive_layout_is_not_executed(self):
        result = self.run_installer(missing_entry=True)
        self.assertEqual(result['returncode'], 1)
        self.assertEqual(result['installed'], [])
        self.assertIn('缺少预期的安装入口', result['output'])

    def test_exit_five_means_installed_waiting_not_failure_or_ready(self):
        result = self.run_installer(result=5, output='等待应用：WorkBuddy — 请打开并登录。\n')
        self.assertEqual(result['returncode'], 5)
        self.assertEqual(result['installed'], ['install'])
        self.assertIn('安装已完成，等待应用', result['output'])
        self.assertIn('无需重新安装', result['output'])
        self.assertIn('等待应用：WorkBuddy', result['output'])
        self.assertNotIn('安装成功', result['output'])
        self.assertNotIn('安装未完成', result['output'])

    def test_launchctl_permission_error_is_preserved_without_retry(self):
        result = self.run_installer(result=1, output='launchctl: Operation not permitted\n')
        self.assertEqual(result['returncode'], 1)
        self.assertEqual(result['installed'], ['install'])
        self.assertIn('Operation not permitted', result['output'])
        self.assertIn('停止在相同受限环境反复尝试', result['output'])
        self.assertIn('正常权限申请流程', result['output'])
        self.assertNotIn('安装成功', result['output'])
        self.assertEqual(result['logs'], ['launchctl: Operation not permitted\n'])

    def test_unverified_device_and_old_board_keep_distinct_exit_codes(self):
        for code, message in ((3, '自检未通过'), (4, '控制板尚不支持提醒灯')):
            with self.subTest(code=code):
                result = self.run_installer(result=code)
                self.assertEqual(result['returncode'], code)
                self.assertIn(message, result['output'])
                self.assertNotIn('安装成功', result['output'])
                self.assertEqual(result['installed'], ['install'])

    def test_platform_root_and_argument_checks_do_not_download(self):
        for overrides, code in (({'platform': 'Linux'}, 1), ({'architecture': 'x86_64'}, 1),
                                ({'uid': '0'}, 1), ({'args': ('--unexpected',)}, 2),
                                ({'args': ('--help',)}, 0)):
            with self.subTest(overrides=overrides):
                result = self.run_installer(**overrides)
                self.assertEqual(result['returncode'], code)
                self.assertIsNone(result['curl_args'])
                self.assertEqual(result['installed'], [])

    def test_static_https_proxy_uses_existing_system_configuration(self):
        settings = ('<dictionary> {\n  HTTPEnable : 1\n  HTTPProxy : wrong.example\n'
                    '  HTTPPort : 8000\n  HTTPSEnable : 1\n'
                    '  HTTPSProxy : 127.0.0.1\n  HTTPSPort : 7897\n}\n')
        result = self.run_installer(proxy_settings=settings)
        self.assertEqual(result['returncode'], 0)
        self.assertTrue(result['scutil_called'])
        args = result['curl_args']
        self.assertEqual(args[args.index('--proxy') + 1], 'http://127.0.0.1:7897')
        self.assertIn('沿用 macOS 已配置', result['output'])
        self.assertEqual(result['curl_environment'], {})

    def test_explicit_proxy_environment_takes_priority_including_empty_value(self):
        settings = 'HTTPSEnable : 1\nHTTPSProxy : 127.0.0.1\nHTTPSPort : 7897\n'
        for key in PROXY_VARIABLES:
            for value in ('http://explicit.example:8080', ''):
                with self.subTest(key=key, value=value):
                    result = self.run_installer(proxy_settings=settings, proxy_environment={key: value})
                    self.assertEqual(result['returncode'], 0)
                    self.assertFalse(result['scutil_called'])
                    self.assertNotIn('--proxy', result['curl_args'])
                    self.assertEqual(result['curl_environment'], {key: value})

    def test_no_static_proxy_does_not_change_normal_curl_path(self):
        cases = ({'proxy_settings': '<dictionary> {\n}\n'}, {'proxy_error': True},
                 {'proxy_settings': 'HTTPSEnable : 0\nHTTPSProxy : 127.0.0.1\nHTTPSPort : 7897\n'},
                 {'proxy_settings': 'ProxyAutoConfigEnable : 1\nProxyAutoConfigURLString : https://example.test/proxy.pac\n'})
        for settings in cases:
            with self.subTest(settings=settings):
                result = self.run_installer(**settings)
                self.assertEqual(result['returncode'], 0)
                self.assertNotIn('--proxy', result['curl_args'])

    def test_supported_dns_and_ipv6_proxy_hosts_are_single_arguments(self):
        for host, authority in (('proxy.example.test', 'proxy.example.test'),
                                ('::1', '[::1]'), ('[2001:db8::1]', '[2001:db8::1]')):
            with self.subTest(host=host):
                settings = 'HTTPSEnable : 1\nHTTPSProxy : ' + host + '\nHTTPSPort : 8080\n'
                result = self.run_installer(proxy_settings=settings)
                self.assertEqual(result['returncode'], 0)
                args = result['curl_args']
                self.assertEqual(args[args.index('--proxy') + 1], 'http://' + authority + ':8080')

    def test_invalid_system_proxy_never_reaches_network_or_installer(self):
        pairs = (('user:secret@proxy.example', '8080'), ('https://proxy.example', '8080'),
                 ('$(touch /tmp/should-not-exist)', '8080'), ('127.0.0.1;echo_bad', '8080'),
                 ('999.1.2.3', '8080'), ('bad..example', '8080'), ('[localhost]', '8080'),
                 ('2001:::1', '8080'), ('127.0.0.1', '0'), ('127.0.0.1', '65536'),
                 ('127.0.0.1', 'not-a-port'))
        for host, port in pairs:
            with self.subTest(host=host, port=port):
                settings = 'HTTPSEnable : 1\nHTTPSProxy : ' + host + '\nHTTPSPort : ' + port + '\n'
                result = self.run_installer(proxy_settings=settings)
                self.assertEqual(result['returncode'], 1)
                self.assertIsNone(result['curl_args'])
                self.assertEqual(result['installed'], [])
                self.assertIn('代理的地址或端口格式不受支持', result['output'])

    def test_duplicate_proxy_fields_are_rejected(self):
        result = self.run_installer(proxy_settings='HTTPSEnable : 1\nHTTPSProxy : localhost\n'
                                   'HTTPSPort : 8080\nHTTPSPort : 9000\n')
        self.assertEqual(result['returncode'], 1)
        self.assertIsNone(result['curl_args'])


if __name__ == '__main__':
    unittest.main()
