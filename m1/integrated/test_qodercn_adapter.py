import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import time
import unittest

sys.path.insert(0, str(Path(__file__).parent))
from qodercn_adapter import ModelEffortCatalog, QoderCnSource, speed_for_effort
from source_config import CHOICES, NAMES, enabled_sources, selection_for


def assistant(*blocks, stop=None, message_id='as-1', model='magpie/group/safely-deepseek'):
    content = []
    for block in blocks:
        if block == 'thinking':
            content.append({'type': 'thinking', 'thinking': 'considering'})
        elif block == 'text':
            content.append({'type': 'text', 'text': 'done'})
        else:
            content.append({'type': 'tool_use', 'id': 'call-' + block, 'name': block, 'input': {}})
    return json.dumps({'type': 'assistant', 'isSidechain': False,
                       'message': {'id': message_id, 'role': 'assistant', 'model': model,
                                   'stop_reason': stop, 'content': content}})


def user_tool_result():
    return json.dumps({'type': 'user', 'isSidechain': False,
                       'message': {'role': 'user', 'content': [
                           {'type': 'tool_result', 'tool_use_id': 'call-Bash', 'content': 'ok'}]}})


def user_prompt(text='do the task'):
    return json.dumps({'type': 'user', 'isSidechain': False,
                       'message': {'role': 'user', 'content': [{'type': 'text', 'text': text}]}})


def runtime_config(model='magpie/group/safely-deepseek', effort=None):
    return json.dumps({'type': 'runtime-config', 'model': model, 'reasoningEffort': effort})


class QoderCnSourceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='qoder source ')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / '.qoder-cn'
        (self.root / 'projects').mkdir(parents=True)
        self.app_data = Path(self.temp.name) / 'appdata'
        self.app_data.mkdir()
        self.now = time.time()

    def preferences(self, rows):
        connection = sqlite3.connect(self.app_data / 'main.sqlite')
        try:
            connection.execute('CREATE TABLE chat_model_preferences '
                               '(model_key TEXT PRIMARY KEY, reasoning_effort TEXT)')
            connection.executemany('INSERT INTO chat_model_preferences VALUES (?, ?)', rows)
            connection.commit()
        finally:
            connection.close()

    def write(self, lines, project='workspace', session='s1'):
        directory = self.root / 'projects' / project
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / (session + '.jsonl')
        path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
        return path

    def append(self, path, lines):
        with path.open('a', encoding='utf-8') as file:
            file.write('\n'.join(lines) + '\n')

    def poll(self, source=None, now=None):
        source = source or QoderCnSource(self.root, self.app_data)
        return source.poll(self.now if now is None else now)

    # --- readiness -------------------------------------------------------

    def test_a_missing_qoder_root_waits_for_first_use(self):
        result = QoderCnSource(Path(self.temp.name) / 'missing', self.app_data).poll(self.now)
        self.assertFalse(result['healthy'])
        self.assertEqual(result['readiness'], 'not_initialized')
        self.assertEqual(result['motor'], 'STOP')

    def test_a_root_without_task_records_is_not_initialized(self):
        root = Path(self.temp.name) / 'empty-root'
        root.mkdir()
        result = QoderCnSource(root, self.app_data).poll(self.now)
        self.assertEqual(result['readiness'], 'not_initialized')
        self.assertFalse(result['healthy'])

    def test_a_task_directory_file_is_an_error(self):
        (self.root / 'projects').rmdir()
        (self.root / 'projects').write_text('not a directory')
        result = self.poll()
        self.assertEqual(result['readiness'], 'error')

    def test_ready_when_the_projects_directory_is_readable(self):
        self.write([user_prompt(), assistant('text', stop='end_turn')])
        result = self.poll()
        self.assertTrue(result['healthy'])
        self.assertEqual(result['readiness'], 'ready')

    # --- work and attention ----------------------------------------------

    def test_a_pending_tool_marks_the_task_working(self):
        self.write([user_prompt(), assistant('thinking'),
                    assistant('Bash', stop='tool_use')])
        result = self.poll()
        self.assertEqual(result['motor'], 'RUN MEDIUM')
        self.assertFalse(result['light'])
        self.assertEqual(result['working_threads'], ['s1'])
        self.assertEqual(result['waiting_threads'], [])

    def test_a_pending_question_pauses_and_lights(self):
        self.write([user_prompt(),
                    assistant('AskUserQuestion', stop='tool_use')])
        result = self.poll()
        self.assertEqual(result['motor'], 'STOP')
        self.assertTrue(result['light'])
        self.assertEqual(result['waiting_threads'], ['s1'])
        self.assertEqual(result['pending_questions'], 1)

    def test_an_answered_question_resumes_work(self):
        path = self.write([user_prompt(), assistant('AskUserQuestion', stop='tool_use')])
        self.poll()
        self.append(path, [user_tool_result()])
        result = self.poll()
        self.assertEqual(result['motor'], 'RUN MEDIUM')
        self.assertFalse(result['light'])
        self.assertEqual(result['working_threads'], ['s1'])

    def test_a_parallel_response_with_a_question_still_waits(self):
        self.write([user_prompt(),
                    assistant('AskUserQuestion', stop=None),
                    assistant('Bash', stop='tool_use')])
        self.assertEqual(self.poll()['waiting_threads'], ['s1'])

    def test_a_finished_turn_stops_without_a_light(self):
        self.write([user_prompt(), assistant('thinking'),
                    assistant('text', stop='end_turn')])
        result = self.poll()
        self.assertEqual(result['motor'], 'STOP')
        self.assertFalse(result['light'])
        self.assertEqual(result['working_threads'], [])

    def test_an_interrupted_turn_is_idle(self):
        self.write([user_prompt(), assistant('Bash', stop='tool_use'),
                    user_prompt('[Request interrupted by user]')])
        self.assertEqual(self.poll()['motor'], 'STOP')

    def test_parallel_sessions_take_the_fastest_active_speed(self):
        self.write([runtime_config(effort='xhigh'), user_prompt(),
                    assistant('Bash', stop='tool_use')], session='fast')
        self.write([user_prompt(), assistant('AskUserQuestion', stop='tool_use')],
                   session='waiting')
        result = self.poll()
        self.assertEqual(result['motor'], 'RUN XHIGH')
        self.assertTrue(result['light'])
        self.assertEqual(result['working_threads'], ['fast'])
        self.assertEqual(result['waiting_threads'], ['waiting'])

    # --- speed mapping ---------------------------------------------------

    def test_effort_tiers_map_to_motor_speeds(self):
        for effort, speed in [('minimal', 'LOW'), ('low', 'LOW'), ('medium', 'MEDIUM'),
                              ('high', 'HIGH'), ('xhigh', 'XHIGH'), ('max', 'ULTRA')]:
            self.assertEqual(speed_for_effort(effort), speed, effort)
        self.assertIsNone(speed_for_effort(None))
        self.assertIsNone(speed_for_effort('turbo'))

    def test_runtime_effort_wins_over_the_model_catalog(self):
        self.preferences([('byok:magpie/group%2Fsafely-deepseek', 'max')])
        self.write([runtime_config(effort='low'), user_prompt(),
                    assistant('Bash', stop='tool_use')])
        self.assertEqual(self.poll()['motor'], 'RUN LOW')

    def test_the_model_catalog_supplies_a_missing_effort(self):
        self.preferences([('byok:magpie/group%2Fsafely-deepseek', 'max'),
                          ('fast', 'low')])
        self.write([user_prompt(), assistant('Bash', stop='tool_use')])
        self.assertEqual(self.poll()['motor'], 'RUN ULTRA')

    def test_an_unconfigured_model_stays_neutral(self):
        self.write([runtime_config(model='qmodel_latest'), user_prompt(),
                    assistant('Bash', stop='tool_use')])
        self.assertEqual(self.poll()['motor'], 'RUN MEDIUM')

    def test_a_missing_catalog_fails_quiet(self):
        catalog = ModelEffortCatalog(self.app_data / 'missing')
        self.assertIsNone(catalog.effort('magpie/group/safely-deepseek'))

    # --- file lifecycle --------------------------------------------------

    def test_a_stale_transcript_is_not_working(self):
        path = self.write([user_prompt(), assistant('Bash', stop='tool_use')])
        old = self.now - 3600
        os.utime(path, (old, old))
        self.assertEqual(self.poll()['motor'], 'STOP')

    def test_appended_records_are_read_incrementally(self):
        path = self.write([user_prompt(), assistant('text', stop='end_turn')])
        source = QoderCnSource(self.root, self.app_data)
        self.assertEqual(source.poll(self.now)['motor'], 'STOP')
        self.append(path, [user_prompt('again'), assistant('Bash', stop='tool_use')])
        result = source.poll(time.time() + 1)
        self.assertEqual(result['motor'], 'RUN MEDIUM')
        self.assertEqual(result['working_threads'], ['s1'])

    def test_a_rewritten_transcript_rebuilds_state(self):
        path = self.write([user_prompt(), assistant('Bash', stop='tool_use')])
        source = QoderCnSource(self.root, self.app_data)
        self.assertEqual(source.poll(self.now)['motor'], 'RUN MEDIUM')
        path.write_text('\n'.join([user_prompt(), assistant('text', stop='end_turn')]) + '\n',
                        encoding='utf-8')
        self.assertEqual(source.poll(time.time() + 1)['motor'], 'STOP')

    def test_malformed_and_bookkeeping_records_are_ignored(self):
        self.write(['{"type":"system","subtype":"compact_boundary"}', 'not json',
                    json.dumps({'type': 'active-leaf', 'leafUuid': 'x'}),
                    json.dumps({'type': 'file-history-snapshot'}),
                    user_prompt(), assistant('Bash', stop='tool_use')])
        result = self.poll()
        self.assertEqual(result['motor'], 'RUN MEDIUM')
        self.assertEqual(result['working_threads'], ['s1'])

    def test_close_is_harmless(self):
        source = QoderCnSource(self.root, self.app_data)
        source.close()
        source.close()


class SourceSelectionTests(unittest.TestCase):
    def test_qoder_combinations_are_enabled(self):
        self.assertIn('qodercn', NAMES)
        self.assertIn('qodercn', CHOICES)
        self.assertEqual(enabled_sources('qodercn'), ('qodercn',))
        self.assertEqual(enabled_sources('codex,qodercn'), ('codex', 'qodercn'))
        self.assertEqual(enabled_sources('qodercn,dsh'), ('qodercn', 'dsh'))

    def test_legacy_aliases_still_work(self):
        self.assertEqual(enabled_sources('both'), ('codex', 'workbuddy'))
        # Upgrading an existing 'all' install must not add an uninitialized source.
        self.assertEqual(enabled_sources('all'), ('codex', 'workbuddy', 'dsh'))

    def test_selection_prefers_canonical_names(self):
        self.assertEqual(selection_for({'qodercn'}), 'qodercn')
        self.assertEqual(selection_for({'codex', 'qodercn'}), 'codex,qodercn')
        self.assertEqual(selection_for({'codex', 'workbuddy'}), 'both')
        self.assertEqual(selection_for({'codex', 'workbuddy', 'dsh'}), 'all')
        self.assertEqual(selection_for(set(NAMES)), 'codex,workbuddy,dsh,qodercn')

    def test_unknown_or_duplicate_sources_are_rejected(self):
        for value in ('nope', 'qodercn,nope', 'qodercn,qodercn', ''):
            with self.assertRaises(ValueError):
                enabled_sources(value)


if __name__ == '__main__':
    unittest.main()