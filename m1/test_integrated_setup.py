from contextlib import redirect_stdout
import io
import json
import plistlib
import sqlite3
import subprocess
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent))
import integrated_setup as setup


# integrated_setup.py installs a launchctl LaunchAgent, so these need macOS.
@unittest.skipUnless(sys.platform == "darwin", "macOS integrated setup tests")
class IntegratedSetupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='小花 integrated with spaces ')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.support = self.root / 'support'
        self.plist = self.root / 'agents' / 'flower.plist'
        self.logs = self.root / 'logs'
        self.sources = self.root / 'sources'
        self.sources.mkdir()
        (self.sources / 'integrated_bridge.py').write_text('# new source\n')
        (self.sources / 'workbuddy_adapter.py').write_text('# new adapter\n')
        self.config = {'source': 'workbuddy', 'sessions_root': self.root / 'codex',
                       'workbuddy_root': self.root / 'workbuddy', 'port': 'auto'}
        for name, value in [('locations', (self.support, self.plist, self.logs)),
                            ('source_directory', self.sources), ('preflight', None), ('running', True),
                            ('detect_apps', {'workbuddy': {'path': '/Applications/WorkBuddy.app'}})]:
            p = patch.object(setup, name, return_value=value)
            p.start()
            self.addCleanup(p.stop)

    def prior(self, source=None, revision='software_adapt_20261103'):
        entry = self.support / revision / 'integrated_bridge.py'
        entry.parent.mkdir(parents=True, exist_ok=True)
        entry.write_text('# old source\n')
        args = ['/bin/bash', str(self.support / 'launch_bridge.sh'), '/python', str(entry),
                '--sessions-root', '/custom/codex', '--port', '/dev/cu.original']
        if source:
            args += ['--source', source]
        self.plist.parent.mkdir(parents=True, exist_ok=True)
        self.plist.write_bytes(plistlib.dumps({'Label': setup.LABEL, 'ProgramArguments': args}))
        return entry

    def test_detect_codex_integrated_service_and_keep_settings(self):
        self.prior()
        previous = setup.existing()
        with patch.object(setup, 'detect_apps', return_value={'codex': {}, 'workbuddy': {}}):
            config = setup.configuration(previous)
        self.assertEqual(config['source'], 'both')
        self.assertEqual(config['port'], '/dev/cu.original')
        self.assertEqual(config['sessions_root'], Path('/custom/codex'))
        self.assertEqual(setup.configuration(previous, 'workbuddy')['source'], 'workbuddy')

    def test_new_or_workbuddy_only_never_enables_codex(self):
        self.assertEqual(setup.configuration(None)['source'], 'workbuddy')
        self.prior(source='workbuddy', revision=setup.REVISION)
        self.assertEqual(setup.configuration(setup.existing())['source'], 'workbuddy')

    def test_v05_revision_is_supported_for_migration(self):
        entry = self.prior(source='workbuddy', revision='integrated-v0.5.0')
        self.assertEqual(setup.existing()['entry'], entry)

    def test_future_revision_is_not_downgraded(self):
        self.prior(revision='integrated-v1.0.0')
        before = self.plist.read_bytes()
        with self.assertRaisesRegex(RuntimeError, '不是本包可升级'):
            setup.existing()
        self.assertEqual(before, self.plist.read_bytes())

    def test_upgrade_migrates_cache_and_uses_stable_entry(self):
        entry = self.prior()
        cache = b'{"pending": [{"id":"identity-only"}]}\n'
        (entry.parent / 'attention-cache.json').write_bytes(cache)
        previous = setup.existing()
        with patch.object(setup, 'launchctl', return_value=True) as launch:
            receipt = setup.install(self.config, previous)
        payload = plistlib.loads(self.plist.read_bytes())
        args = payload['ProgramArguments']
        self.assertIn(str(self.support / setup.REVISION / 'integrated_bridge.py'), args)
        self.assertEqual(args[args.index('--source') + 1], 'workbuddy')
        self.assertEqual(args[args.index('--launch-id') + 1], receipt['launch_id'])
        self.assertEqual((self.support / setup.REVISION / 'attention-cache.json').read_bytes(), cache)
        self.assertEqual(launch.call_args_list[0].args[0], 'bootout')
        self.assertEqual(launch.call_args_list[-1].args[0], 'bootstrap')

    def test_failed_bootstrap_restores_same_revision_source_and_service(self):
        entry = self.prior(source='both', revision=setup.REVISION)
        before = self.plist.read_bytes()
        previous = setup.existing()
        calls = []
        def launch(*args, **kwargs):
            calls.append(args[0])
            if args[0] == 'bootstrap' and kwargs.get('check', True):
                raise RuntimeError('fixture bootstrap failure')
            return True
        with patch.object(setup, 'launchctl', side_effect=launch):
            with self.assertRaisesRegex(RuntimeError, 'fixture bootstrap'):
                setup.install(self.config, previous)
        self.assertEqual(self.plist.read_bytes(), before)
        self.assertEqual(entry.read_text(), '# old source\n')
        self.assertEqual(calls, ['bootout', 'bootstrap', 'bootout', 'bootstrap'])

    def test_new_install_failure_leaves_no_active_service(self):
        def launch(*args, **kwargs):
            if args[0] == 'bootstrap':
                raise RuntimeError('fixture failure')
            return True
        with patch.object(setup, 'launchctl', side_effect=launch):
            with self.assertRaises(RuntimeError):
                setup.install(self.config)
        self.assertFalse(self.plist.exists())
        self.assertFalse((self.support / setup.REVISION).exists())

    def test_fresh_handshake_requires_this_launch_and_both_capabilities(self):
        status = self.root / 'status.json'
        now = time.time()
        receipt = {'status_file': status, 'launch_id': 'current', 'started_at': now - 1}
        value = {'launch_id': 'previous', 'updated_at': now,
                 'device_connected': True, 'device_capabilities': ['motor', 'attention'],
                 'sources': {'workbuddy': {'healthy': True, 'readiness': 'ready'}}}
        status.write_text(json.dumps(value))
        self.assertEqual(setup.verify(receipt, 0), 3)
        value['launch_id'] = 'current'
        value['device_capabilities'] = ['motor']
        status.write_text(json.dumps(value))
        self.assertEqual(setup.verify(receipt, 0), 4)
        value['device_capabilities'].append('attention')
        status.write_text(json.dumps(value))
        self.assertEqual(setup.verify(receipt, 0), 0)
        value['sources']['workbuddy']['healthy'] = False
        status.write_text(json.dumps(value))
        self.assertEqual(setup.verify(receipt, 0), 3)
        value['sources']['workbuddy']['healthy'] = True
        value['updated_at'] = now - 100
        status.write_text(json.dumps(value))
        self.assertEqual(setup.verify(receipt, 0), 3)

    def test_uninstall_combined_removes_entire_service_and_keeps_backup(self):
        self.prior(source='both', revision=setup.REVISION)
        previous = setup.existing()
        with patch.object(setup, 'launchctl', return_value=True) as launch:
            self.assertEqual(setup.uninstall(previous), 0)
        self.assertEqual(launch.call_args.args[0], 'bootout')
        self.assertFalse(self.plist.exists())
        backups = list((self.support / 'backups').glob('uninstall-*/service.plist'))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_bytes(), previous['plist_bytes'])
        self.assertTrue(previous['entry'].exists())


    def test_combined_selfcheck_reports_codex_failure_instead_of_success(self):
        status = self.root / 'status.json'
        now = time.time()
        receipt = {'source': 'both', 'status_file': status,
                   'launch_id': 'current', 'started_at': now - 1}
        value = {'launch_id': 'current', 'updated_at': now,
                 'device_connected': True, 'device_capabilities': ['motor', 'attention'],
                 'sources': {'workbuddy': {'healthy': True, 'readiness': 'ready'},
                             'codex': {'healthy': False, 'readiness': 'error', 'error': 'Source initialization failed: ValueError'}}}
        status.write_text(json.dumps(value))
        output = io.StringIO()
        with redirect_stdout(output):
            self.assertEqual(setup.verify(receipt, 0), 3)
        self.assertIn('Codex 状态：Source initialization failed: ValueError', output.getvalue())
        self.assertIn('不要将该应用当作已就绪', output.getvalue())
        self.assertNotIn('安装自检通过', output.getvalue())
        self.assertEqual(json.loads(status.read_text()), value)

        value['sources']['codex'] = {'healthy': True, 'readiness': 'ready'}
        status.write_text(json.dumps(value))
        with redirect_stdout(io.StringIO()):
            self.assertEqual(setup.verify(receipt, 0), 0)

    def test_selfcheck_requires_only_enabled_sources_and_reports_offline_codex(self):
        status = self.root / 'status.json'
        now = time.time()
        receipt = {'source': 'codex', 'status_file': status,
                   'launch_id': 'current', 'started_at': now - 1}
        value = {'launch_id': 'current', 'updated_at': now,
                 'device_connected': True, 'device_capabilities': ['motor', 'attention'],
                 'sources': {'codex': {'healthy': False, 'readiness': 'not_running', 'error': None, 'detail': '应用尚未打开'}}}
        status.write_text(json.dumps(value))
        output = io.StringIO()
        with redirect_stdout(output):
            self.assertEqual(setup.verify(receipt, 0), 5)
        self.assertIn('等待应用：Codex — 应用尚未打开', output.getvalue())
        self.assertIn('不需要重新安装', output.getvalue())
        self.assertNotIn('WorkBuddy 状态', output.getvalue())

        value['sources']['codex']['healthy'] = True
        value['sources']['codex']['readiness'] = 'ready'
        status.write_text(json.dumps(value))
        with redirect_stdout(io.StringIO()):
            self.assertEqual(setup.verify(receipt, 0), 0)

        receipt['source'] = 'workbuddy'
        value['sources'] = {'workbuddy': {'healthy': True, 'readiness': 'ready'}, 'codex': {'healthy': False}}
        status.write_text(json.dumps(value))
        with redirect_stdout(io.StringIO()):
            self.assertEqual(setup.verify(receipt, 0), 0)


@unittest.skipUnless(sys.platform == "darwin", "macOS app bundle detection tests")
class SourceDetectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='小花 apps ')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def app(self, name, bundle_id, executable=True):
        root = self.root / name
        (root / 'Contents/MacOS').mkdir(parents=True)
        binary = root / 'Contents/MacOS/app'
        binary.write_text('fixture executable')
        binary.chmod(0o755 if executable else 0o644)
        (root / 'Contents/Info.plist').write_bytes(plistlib.dumps({
            'CFBundleIdentifier': bundle_id, 'CFBundleExecutable': 'app',
            'CFBundlePackageType': 'APPL', 'CFBundleShortVersionString': 'fixture',
        }))
        return root

    def test_codex_detected_by_id_even_when_named_chatgpt(self):
        codex = self.app('ChatGPT.app', 'com.openai.codex')
        wb = self.app('WorkBuddy.app', 'com.tencent.workbuddy.mac')
        with patch.object(setup, 'app_candidates', return_value=[codex, wb]):
            self.assertEqual(set(setup.detect_apps()), {'codex', 'workbuddy'})
            self.assertEqual(setup.configuration(None)['source'], 'both')

    def test_non_dictionary_plist_does_not_interrupt_app_discovery(self):
        malformed = self.app('Unrelated.app', 'unrelated.app')
        (malformed / 'Contents/Info.plist').write_bytes(plistlib.dumps(['valid plist', 'not a dictionary']))
        codex = self.app('ChatGPT.app', 'com.openai.codex')
        with patch.object(setup, 'app_candidates', return_value=[malformed, codex]):
            self.assertEqual(setup.detect_apps()['codex']['path'], str(codex.resolve()))

    def test_trashed_apps_and_symlinks_to_trash_are_not_installed(self):
        trashed = self.app('.Trash/ChatGPT.app', 'com.openai.codex')
        volume_trash = self.app('volume/.Trashes/501/WorkBuddy.app', 'com.tencent.workbuddy.mac')
        shortcut = self.root / 'Applications/ChatGPT.app'
        shortcut.parent.mkdir()
        shortcut.symlink_to(trashed, target_is_directory=True)
        with patch.object(setup, 'app_candidates', return_value=[trashed, volume_trash, shortcut]):
            self.assertEqual(setup.detect_apps(), {})

    def test_standard_application_has_priority_over_spotlight_copy(self):
        installed = self.app('Applications/ChatGPT.app', 'com.openai.codex')
        duplicate = self.app('Downloads/ChatGPT.app', 'com.openai.codex')
        responses = [subprocess.CompletedProcess(['mdfind'], 0, str(duplicate) + '\n', ''),
                     subprocess.CompletedProcess(['ps'], 0, '', '')]
        with patch.object(setup, 'application_roots', return_value=[self.root / 'Applications']), \
             patch.object(setup.subprocess, 'run', side_effect=responses):
            self.assertEqual(setup.detect_apps()['codex']['path'], str(installed.resolve()))

    def test_app_names_and_leftover_database_are_not_installation_evidence(self):
        fake = self.app('Codex.app', 'unrelated.app')
        missing_binary = self.app('WorkBuddy.app', 'com.tencent.workbuddy.mac', executable=False)
        data = self.root / '.workbuddy'
        data.mkdir()
        (data / 'workbuddy.db').write_bytes(b'leftover')
        with patch.object(setup, 'app_candidates', return_value=[fake, missing_binary]), \
             patch.object(setup.Path, 'home', return_value=self.root):
            self.assertEqual(setup.detect_apps(), {})
            with self.assertRaisesRegex(RuntimeError, '没有检测到已安装'):
                setup.configuration(None)

    def test_automatic_source_uses_current_apps_not_previous_source(self):
        previous = {'options': {'--source': 'workbuddy', '--port': '/dev/cu.saved'}}
        for apps, expected in (({'codex': {}}, 'codex'), ({'workbuddy': {}}, 'workbuddy'),
                               ({'codex': {}, 'workbuddy': {}}, 'both')):
            with patch.object(setup, 'detect_apps', return_value=apps):
                config = setup.configuration(previous)
                self.assertEqual(config['source'], expected)
                self.assertEqual(config['port'], '/dev/cu.saved')
        with patch.object(setup, 'detect_apps', return_value={'codex': {}, 'workbuddy': {}}):
            self.assertEqual(setup.configuration(previous, 'workbuddy')['source'], 'workbuddy')

    def test_nested_application_detected_when_spotlight_unavailable(self):
        app = self.app('Applications/Tools/ChatGPT.app', 'com.openai.codex')
        with patch.object(setup, 'application_roots', return_value=[self.root / 'Applications']), \
             patch.object(setup.subprocess, 'run', side_effect=OSError('no index/process permission')):
            self.assertIn(app, setup.app_candidates())
            self.assertEqual(setup.detect_apps()['codex']['path'], str(app.resolve()))

    def test_process_path_fallback_is_still_bundle_verified(self):
        app = self.app('elsewhere/ChatGPT.app', 'com.openai.codex')
        responses = [subprocess.CompletedProcess(['mdfind'], 1, '', ''),
                     subprocess.CompletedProcess(['ps'], 0, str(app / 'Contents/MacOS/app') + '\n', '')]
        with patch.object(setup, 'application_roots', return_value=[]), \
             patch.object(setup.subprocess, 'run', side_effect=responses):
            self.assertEqual(setup.detect_apps()['codex']['path'], str(app.resolve()))

    def test_uninitialized_apps_do_not_block_preflight(self):
        config = {'source': 'both', 'sessions_root': self.root / 'codex',
                  'workbuddy_root': self.root / 'workbuddy'}
        result = setup.preflight(config)
        self.assertEqual(result['codex']['readiness'], 'not_initialized')
        self.assertEqual(result['workbuddy']['readiness'], 'not_initialized')
        self.assertFalse(config['workbuddy_root'].exists())

    def test_corrupt_or_incompatible_database_is_error_not_initialization(self):
        config = {'source': 'workbuddy', 'workbuddy_root': self.root}
        db = self.root / 'workbuddy.db'
        db.write_bytes(b'not sqlite')
        self.assertEqual(setup.preflight(config)['workbuddy']['readiness'], 'error')
        db.unlink()
        with sqlite3.connect(db) as c:
            c.execute('CREATE TABLE sessions (id TEXT)')
        self.assertEqual(setup.preflight(config)['workbuddy']['readiness'], 'error')


@unittest.skipUnless(sys.platform == "darwin", "macOS readiness verification tests")
class ReadinessVerificationTests(unittest.TestCase):
    def test_waiting_requires_installed_service_fresh_hardware_and_explicit_states(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'status.json'
            now = time.time()
            receipt = {'source': 'both', 'status_file': path, 'launch_id': 'fixture', 'started_at': now - 1}
            value = {'launch_id': 'fixture', 'updated_at': now,
                     'device_connected': True, 'device_capabilities': ['motor', 'attention'],
                     'sources': {'codex': {'healthy': True, 'readiness': 'ready'},
                                 'workbuddy': {'healthy': False, 'readiness': 'not_initialized',
                                              'detail': '请打开并登录 WorkBuddy', 'error': None}}}
            with patch.object(setup, 'running', return_value=True), redirect_stdout(io.StringIO()):
                path.write_text(json.dumps(value))
                self.assertEqual(setup.verify(receipt, 0), 5)
                value['device_connected'] = False
                path.write_text(json.dumps(value))
                self.assertEqual(setup.verify(receipt, 0), 3)
                value['device_connected'] = True
                value['sources']['workbuddy'].pop('readiness')
                path.write_text(json.dumps(value))
                self.assertEqual(setup.verify(receipt, 0), 3)
                value['sources']['workbuddy'] = {'healthy': True}
                path.write_text(json.dumps(value))
                self.assertEqual(setup.verify(receipt, 0), 3)
                value['sources']['workbuddy'] = {'healthy': False, 'readiness': 'error', 'error': 'bad schema'}
                path.write_text(json.dumps(value))
                self.assertEqual(setup.verify(receipt, 0), 3)



if __name__ == '__main__':
    unittest.main()
