"""First-use recovery with real temporary metadata; no desktop or USB access."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import time
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).parent))
from integrated_bridge import CodexSource, combine_sources
from workbuddy_adapter import WorkBuddyAdapter


CHAT = '11111111-1111-4111-8111-111111111111'


class ReadinessRecoveryTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='flower first use ')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.now = time.time()

    def codex(self):
        feed = Mock()
        feed.snapshot.return_value = self.offline('FileNotFoundError')
        with patch('integrated_bridge.DesktopRuntimeFeed', return_value=feed):
            source = CodexSource(self.root / 'codex/sessions', None)
        self.addCleanup(source.close)
        return source, feed

    @staticmethod
    def offline(error):
        return {'connected': False, 'error': error, 'last_message_at': None, 'threads': {}}

    def online(self, *, active=False, last_message_at=None):
        threads = {}
        if active:
            threads[CHAT] = {'host_id': 'local', 'owner_found': True,
                             'parent_thread_id': None, 'observed_at': self.now,
                             'runtime_status': {'type': 'active', 'activeFlags': []}}
        return {'connected': True, 'error': None, 'threads': threads,
                'last_message_at': self.now if last_message_at is None else last_message_at}

    def create_rollout(self, root):
        root.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.fromtimestamp(self.now, timezone.utc).isoformat()
        records = [
            {'type': 'session_meta', 'payload': {'id': CHAT, 'thread_source': 'user'}},
            {'type': 'turn_context', 'payload': {'turn_id': 'turn-one', 'effort': 'high'}},
            {'type': 'event_msg', 'payload': {'type': 'task_started', 'turn_id': 'turn-one'}},
        ]
        path = root / 'rollout-first.jsonl'
        path.write_text(''.join(json.dumps({'timestamp': timestamp, **record}) + '\n'
                                for record in records))
        os.utime(path, (self.now, self.now))

    def test_codex_missing_sessions_recovers_on_same_source_after_first_task(self):
        source, feed = self.codex()
        with patch('root_catalog.time.monotonic', return_value=100):
            first = source.poll(self.now)
        self.assertEqual(first['readiness'], 'not_initialized')
        self.assertIsNone(first['error'])
        self.assertFalse(first['healthy'])
        self.assertFalse(source.root.exists())
        self.assertEqual((first['motor'], first['light']), ('STOP', False))

        self.create_rollout(source.root)
        feed.snapshot.return_value = self.online(active=True)
        with patch('root_catalog.time.monotonic', return_value=106):
            recovered = source.poll(self.now)
        self.assertEqual(recovered['readiness'], 'ready')
        self.assertTrue(recovered['healthy'])
        self.assertEqual(recovered['motor'], 'RUN HIGH')
        self.assertIn(CHAT, source.catalog.ids)
        self.assertIn(CHAT, feed.set_targets.call_args.args[0])

    def test_codex_normal_disconnects_wait_and_reconnect_without_reinstallation(self):
        source, feed = self.codex()
        self.create_rollout(source.root)
        for error in ('not_started', 'FileNotFoundError', 'ConnectionRefusedError', 'EOFError',
                      'ConnectionResetError', 'ConnectionAbortedError', 'BrokenPipeError'):
            with self.subTest(error=error):
                feed.snapshot.return_value = self.offline(error)
                state = source.poll(self.now)
                self.assertEqual(state['readiness'], 'not_running')
                self.assertIsNone(state['error'])
                self.assertEqual((state['motor'], state['light']), ('STOP', False))
                self.assertEqual(combine_sources({'codex': state, 'workbuddy': {
                    'healthy': True, 'motor': 'RUN LOW', 'light': True}}), ('RUN LOW', True))
        feed.snapshot.return_value = self.online(active=True)
        state = source.poll(self.now)
        self.assertEqual((state['readiness'], state['motor']), ('ready', 'RUN HIGH'))

    def test_codex_permission_and_protocol_failures_are_errors_and_can_recover(self):
        source, feed = self.codex()
        source.root.mkdir(parents=True)
        for error in ('PermissionError', 'ValueError', 'KeyError', 'TypeError', 'IndexError'):
            with self.subTest(error=error):
                feed.snapshot.return_value = self.offline(error)
                state = source.poll(self.now)
                self.assertEqual(state['readiness'], 'error')
                self.assertEqual(state['error'], error)
                self.assertFalse(state['healthy'])
        feed.snapshot.return_value = self.online()
        self.assertEqual(source.poll(self.now)['readiness'], 'ready')

    def test_codex_stale_connection_is_first_use_only_without_known_chats(self):
        source, feed = self.codex()
        source.root.mkdir(parents=True)
        feed.snapshot.return_value = self.online(last_message_at=self.now - 7)
        state = source.poll(self.now)
        self.assertEqual(state['readiness'], 'not_initialized')
        self.assertIsNone(state['error'])
        self.create_rollout(source.root)
        state = source.poll(self.now)
        self.assertEqual(state['readiness'], 'error')
        self.assertTrue(state['error'])
        self.assertFalse(state['healthy'])

    def create_workbuddy(self, root):
        (root / 'sessions').mkdir(parents=True, exist_ok=True)
        (root / 'logs').mkdir(exist_ok=True)
        (root / 'logs/daemon.log').write_text('')
        db = sqlite3.connect(root / 'workbuddy.db')
        try:
            db.execute('CREATE TABLE sessions(id TEXT,status TEXT,updated_at INTEGER,'
                       'model TEXT,transport TEXT,deleted_at INTEGER)')
            db.execute('INSERT INTO sessions VALUES(?,?,?,?,?,NULL)',
                       (CHAT, 'working', int(self.now * 1000), 'balanced-model', 'local'))
            db.commit()
        finally:
            db.close()
        (root / 'sessions/123.json').write_text(json.dumps({
            'pid': 123, 'sessionId': CHAT, 'startedAt': int((self.now - 1) * 1000),
            'kind': 'interactive'}))

    def test_workbuddy_missing_metadata_recovers_on_same_adapter_after_first_task(self):
        root = self.root / 'workbuddy'
        adapter = WorkBuddyAdapter(root)
        first = adapter.poll(self.now)
        self.assertEqual(first['readiness'], 'not_initialized')
        self.assertIsNone(first['error'])
        self.assertEqual((first['motor'], first['light']), ('STOP', False))
        self.assertFalse(root.exists())

        self.create_workbuddy(root)
        with patch('workbuddy_adapter.os.kill'):
            recovered = adapter.poll(self.now)
        self.assertEqual(recovered['readiness'], 'ready')
        self.assertTrue(recovered['healthy'])
        self.assertEqual(recovered['motor'], 'RUN HIGH')

    def test_corrupt_workbuddy_database_is_error_and_recovers_after_repair(self):
        root = self.root / 'workbuddy'
        root.mkdir()
        path = root / 'workbuddy.db'
        path.write_bytes(b'not a sqlite database')
        adapter = WorkBuddyAdapter(root)
        state = adapter.poll(self.now)
        self.assertEqual(state['readiness'], 'error')
        self.assertTrue(state['error'])
        self.assertFalse(state['healthy'])
        self.assertEqual(path.read_bytes(), b'not a sqlite database')

        path.unlink()
        self.create_workbuddy(root)
        with patch('workbuddy_adapter.os.kill'):
            recovered = adapter.poll(self.now)
        self.assertEqual((recovered['readiness'], recovered['motor']), ('ready', 'RUN HIGH'))

    def test_existing_workbuddy_database_without_expected_schema_is_error(self):
        root = self.root / 'workbuddy'
        root.mkdir()
        db = sqlite3.connect(root / 'workbuddy.db')
        try:
            db.execute('CREATE TABLE unrelated(id TEXT)')
            db.commit()
        finally:
            db.close()
        state = WorkBuddyAdapter(root).poll(self.now)
        self.assertEqual(state['readiness'], 'error')
        self.assertTrue(state['error'])
        self.assertFalse(state['healthy'])


if __name__ == '__main__':
    unittest.main()
