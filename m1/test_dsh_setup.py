import os
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import dsh_setup

sys.path.insert(0, str(Path(__file__).parent))
from dsh_setup import (BEGIN, END, PLUGIN_ID, SetupError, apply_block, has_block,
                       install, managed_block, status, strip_block, uninstall, DshPluginChange)


class DshSetupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='dsh setup ')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.home = self.root / 'dsh home'
        self.profile = self.home / 'profiles' / 'desktop'
        self.profile.mkdir(parents=True)
        self.patch = self.profile / 'cordis.patch.yml'
        self.support = self.root / 'support'
        self.source = self.root / 'src' / 'flower-observer.mjs'
        self.source.parent.mkdir(parents=True)
        self.source.write_text('export default function () {}\n')

    def install(self):
        return install(self.home, 'desktop', self.support, self.source)

    def test_commented_empty_list_is_replaced_and_restored_byte_for_byte(self):
        for original in (b'# local settings\n[]\n', b'[]\n', b'\n- id: keep\n\n',
                         b'- id: keep', b'# comments\r\n[]\r\n', b'[] # inline comment\n',
                         b'---\n[ ] # inline\n'):
            with self.subTest(original=original):
                self.patch.write_bytes(original)
                self.install()
                self.assertNotIn('[]', self.patch.read_text())
                uninstall(self.home, 'desktop', self.support)
                self.assertEqual(self.patch.read_bytes(), original)

    def test_backups_never_overwrite_on_rapid_install_uninstall(self):
        original = b'- id: keep\n'
        self.patch.write_bytes(original)
        receipt = self.install()
        backup = receipt['backup']
        uninstall(self.home, 'desktop', self.support)
        self.assertEqual(backup.read_bytes(), original)
        self.assertGreaterEqual(len(list((self.support / 'backups').glob('cordis.patch.yml.*.bak'))), 2)

    def test_invalid_patch_does_not_replace_existing_observer(self):
        self.support.mkdir()
        observer = self.support / 'flower-observer.mjs'
        observer.write_bytes(b'old observer')
        self.patch.write_text(BEGIN + '\n- insert:\n')
        with self.assertRaises(SetupError):
            self.install()
        self.assertEqual(observer.read_bytes(), b'old observer')

    def test_failed_patch_write_rolls_back_observer_and_receipt(self):
        self.patch.write_bytes(b'[]\n')
        self.support.mkdir()
        observer = self.support / 'flower-observer.mjs'
        observer.write_bytes(b'old observer')
        original_write = dsh_setup._write_atomic
        def fail_patch(path, data, mode=0o600):
            if path == self.patch:
                raise OSError('fixture disk failure')
            return original_write(path, data, mode)
        with patch.object(dsh_setup, '_write_atomic', side_effect=fail_patch):
            with self.assertRaisesRegex(OSError, 'fixture disk failure'):
                self.install()
        self.assertEqual(observer.read_bytes(), b'old observer')
        self.assertEqual(self.patch.read_bytes(), b'[]\n')
        self.assertEqual(list(self.support.glob('install-state-*.json')), [])

    def test_unmanaged_duplicate_is_refused(self):
        original = '- insert:\n    - id: rotating-flower-observer\n      name: /custom.mjs\n'
        self.patch.write_text(original)
        with self.assertRaises(SetupError):
            self.install()
        self.assertEqual(self.patch.read_text(), original)
        self.assertFalse((self.support / 'flower-observer.mjs').exists())

    def test_reinstall_keeps_user_edits_when_uninstalled(self):
        self.patch.write_text('- id: keep\n')
        self.install()
        with self.patch.open('a') as handle:
            handle.write('\n# user note\n- id: added\n')
        self.install()
        uninstall(self.home, 'desktop', self.support)
        self.assertEqual(self.patch.read_text(), '- id: keep\n\n# user note\n- id: added\n')

    def test_rollback_does_not_overwrite_a_later_user_edit(self):
        self.patch.write_text('[]\n')
        change = DshPluginChange(self.home, self.support, self.source).apply()
        later = self.patch.read_bytes() + b'# later edit\n'
        self.patch.write_bytes(later)
        change.rollback()
        self.assertEqual(self.patch.read_bytes(), later)
        self.assertTrue(change.plugin.exists())

    def test_uninstall_preserves_observer_used_by_another_profile(self):
        self.patch.write_text('[]\n')
        other = self.home / 'profiles/other/cordis.patch.yml'
        other.parent.mkdir()
        other.write_text('[]\n')
        self.install()
        install(self.home, 'other', self.support, self.source)
        uninstall(self.home, 'desktop', self.support)
        self.assertTrue((self.support / 'flower-observer.mjs').exists())
        self.assertTrue(has_block(other.read_text()))
        uninstall(self.home, 'other', self.support)
        self.assertFalse((self.support / 'flower-observer.mjs').exists())
        self.assertEqual(other.read_text(), '[]\n')

    def test_legacy_manual_install_uninstalls_without_reinstating_block(self):
        self.patch.write_text('- id: keep\n' + managed_block('/old/observer.mjs') + '\n')
        self.install()
        uninstall(self.home, 'desktop', self.support)
        self.assertEqual(self.patch.read_text(), '- id: keep\n')

    def test_install_registers_the_plugin_and_the_observer(self):
        self.patch.write_text('- id: agent-default-model\n  name: "@deepseek-ai/dsh-agent-default-model"\n')
        result = self.install()
        self.assertTrue(result['changed'])
        text = self.patch.read_text()
        self.assertEqual(text.count(BEGIN), 1)
        self.assertEqual(text.count(END), 1)
        self.assertIn(PLUGIN_ID, text)
        self.assertIn(json.dumps(str(self.support / 'flower-observer.mjs')), text)
        self.assertIn('- id: agent-default-model', text)
        self.assertEqual(result['observer'].read_text(), self.source.read_text())
        if os.name != 'nt':
            # Windows has no POSIX permission bits; the file inherits the ACL.
            self.assertEqual(result['observer'].stat().st_mode & 0o777, 0o600)
            self.assertEqual(self.support.stat().st_mode & 0o777, 0o700)

    def test_installing_twice_changes_nothing(self):
        self.patch.write_text('- id: agent-default-model\n  name: "x"\n')
        first = self.install()
        before = self.patch.read_text()
        second = self.install()
        self.assertFalse(second['changed'])
        self.assertEqual(first['patch'], second['patch'])
        self.assertEqual(self.patch.read_text(), before)
        self.assertEqual(before.count(BEGIN), 1)

    def test_install_replaces_a_stale_observer_path(self):
        self.patch.write_text('- id: agent-default-model\n  name: "x"\n')
        self.install()
        moved = self.root / 'moved' / 'flower-observer.mjs'
        moved.parent.mkdir()
        moved.write_text('export default function () {}\n')
        install(self.home, 'desktop', self.root / 'moved', self.source)
        text = self.patch.read_text()
        self.assertEqual(text.count(BEGIN), 1)
        self.assertIn(json.dumps(str(moved)), text)
        self.assertNotIn(json.dumps(str(self.support / 'flower-observer.mjs')), text)

    def test_install_accepts_an_empty_flow_list_profile(self):
        self.patch.write_text('[]\n')
        self.install()
        text = self.patch.read_text()
        self.assertNotIn('[]', text)
        self.assertTrue(text.startswith(BEGIN))
        self.assertEqual(text.count(BEGIN), 1)

    def test_install_accepts_an_empty_file(self):
        self.patch.write_text('')
        self.install()
        self.assertTrue(has_block(self.patch.read_text()))

    def test_install_backs_up_the_original_once_per_change(self):
        self.patch.write_text('- id: agent-default-model\n  name: "x"\n')
        result = self.install()
        self.assertIsNotNone(result['backup'])
        self.assertEqual(result['backup'].read_text(), '- id: agent-default-model\n  name: "x"\n')
        self.assertIsNone(self.install()['backup'])

    def test_uninstall_restores_the_file_exactly(self):
        original = '- id: agent-default-model\n  name: "@deepseek-ai/dsh-agent-default-model"\n'
        self.patch.write_text(original)
        self.install()
        result = uninstall(self.home, 'desktop', self.support)
        self.assertEqual(self.patch.read_text(), original)
        self.assertIn(self.patch, result['removed'])
        self.assertFalse((self.support / 'flower-observer.mjs').exists())

    def test_uninstall_keeps_entries_added_after_the_block(self):
        self.patch.write_text('- id: agent-default-model\n  name: "x"\n')
        self.install()
        with self.patch.open('a') as handle:
            handle.write('\n- id: late-entry\n  name: "y"\n')
        uninstall(self.home, 'desktop', self.support)
        text = self.patch.read_text()
        self.assertFalse(has_block(text))
        self.assertIn('- id: agent-default-model', text)
        self.assertIn('- id: late-entry', text)

    def test_uninstall_without_an_install_is_harmless(self):
        self.patch.write_text('- id: agent-default-model\n  name: "x"\n')
        result = uninstall(self.home, 'desktop', self.support)
        self.assertEqual(result['removed'], [])
        self.assertEqual(self.patch.read_text(), '- id: agent-default-model\n  name: "x"\n')

    def test_uninstall_removes_the_dsh_status_file(self):
        self.support.mkdir(parents=True)
        (self.support / 'status.json').write_text('{}')
        self.patch.write_text('')
        uninstall(self.home, 'desktop', self.support)
        self.assertFalse((self.support / 'status.json').exists())

    def test_a_damaged_block_is_refused_instead_of_rewritten(self):
        self.patch.write_text(f'{BEGIN}\n- insert:\n')
        with self.assertRaises(SetupError):
            self.install()
        self.assertEqual(self.patch.read_text(), f'{BEGIN}\n- insert:\n')

    def test_a_missing_profile_is_reported_before_writing_anything(self):
        missing = self.root / 'no dsh'
        with self.assertRaises(SetupError) as error:
            install(missing, 'desktop', self.support, self.source)
        self.assertIn('cordis.patch.yml', str(error.exception))
        self.assertFalse(self.support.exists())

    def test_a_missing_observer_source_is_reported(self):
        self.patch.write_text('')
        with self.assertRaises(SetupError):
            install(self.home, 'desktop', self.support, self.root / 'nope.mjs')

    def test_status_reports_each_step(self):
        self.patch.write_text('- id: agent-default-model\n  name: "x"\n')
        before = status(self.home, 'desktop', self.support)
        self.assertEqual((before['profile_exists'], before['registered'], before['observer_exists']),
                         (True, False, False))
        self.install()
        after = status(self.home, 'desktop', self.support)
        self.assertEqual((after['profile_exists'], after['registered'], after['observer_exists']),
                         (True, True, True))

    def test_a_path_with_spaces_survives_the_round_trip(self):
        spaced = self.root / 'with space' / 'flower-observer.mjs'
        spaced.parent.mkdir()
        spaced.write_text('export default function () {}\n')
        self.patch.write_text('')
        install(self.home, 'desktop', spaced.parent, self.source)
        text = self.patch.read_text()
        # managed_block writes the path through json.dumps, which escapes
        # backslashes, so compare against the same encoding.
        self.assertIn(f'name: {json.dumps(str(spaced), ensure_ascii=False)}', text)
        self.assertTrue(has_block(text))


class BlockEditingTests(unittest.TestCase):
    def test_applying_a_block_is_idempotent(self):
        block = managed_block('/tmp/flower observer.mjs')
        once = apply_block('- id: a\n  name: "x"\n', block)
        self.assertEqual(apply_block(once, block), once)

    def test_stripping_an_absent_block_is_a_no_op(self):
        text = '- id: a\n  name: "x"\n'
        self.assertEqual(strip_block(text), text)

    def test_stripping_a_block_leaves_an_empty_file(self):
        block = managed_block('/tmp/x.mjs')
        self.assertEqual(strip_block(apply_block('', block)), '')


if __name__ == '__main__':
    unittest.main()
