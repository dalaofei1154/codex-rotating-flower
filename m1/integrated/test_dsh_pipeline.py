"""Exercise the real Node observer JSON contract through the Python bridge."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent))
from dsh_adapter import DshAdapter
from integrated_bridge import combine_sources


NODE = shutil.which('node')
OBSERVER = Path(__file__).resolve().parents[1] / 'dsh' / 'flower-observer.mjs'

# Only the DSH runtime inputs are synthetic. The production observer writes each
# snapshot to disk, and the production Python adapter reads those exact bytes.
LIFECYCLE_SCRIPT = r"""
import { copyFileSync } from 'node:fs';
import { join } from 'node:path';
import { pathToFileURL } from 'node:url';
const [root, modulePath] = process.argv.slice(2);
const { createObserver } = await import(pathToFileURL(modulePath).href);
const events = [{type: 'turn/start', data: {}}];
const agent = {
  id: 'synthetic-dsh-task', status: 'running',
  session: {get seq() {return events.length;}, firstLiveSeq: 0,
    eventAt(index) {return events[index];}},
};
const values = {
  modelSelection: {lastUsed: {model: 'synthetic-model', reasoningEffort: 'max'}},
  userQuestions: {active: []},
};
const observer = createObserver({
  agents: {list: () => [agent]},
  sessionProjections: {snapshot: () => ({values})},
}, {root, heartbeat: 60000});
const save = name => copyFileSync(observer.file, join(root, `${name}.json`));
const snapshot = name => {observer.write(); save(name);};

snapshot('working');
events.push({type: 'tool/call', data: {
  name: 'ask_user_question', callId: 'q1', arguments: 'PRIVATE_QUESTION_TEXT',
}});
values.userQuestions.active = [{callId: 'q1', state: 'open',
  questions: [{question: 'PRIVATE_QUESTION_TEXT'}]}];
snapshot('question');
events.push({type: 'tool/result', data: {message: {toolCallId: 'q1'}}});
values.userQuestions.active[0].state = 'continued';
snapshot('continued');
values.userQuestions.active = [];
snapshot('answered');
events.push({type: 'approval/asked', data: {id: 'a1', reason: 'PRIVATE_APPROVAL_TEXT'}});
snapshot('approval');
events.push({type: 'approval/decided', data: {id: 'a1', outcome: 'accepted'}});
snapshot('approved');
events.push({type: 'turn/end', data: {}});
agent.status = 'idle';
snapshot('ended');
observer.stop();
save('stopped');
"""


@unittest.skipUnless(NODE, 'Node.js is required for the DSH observer/adapter integration test')
class DshPipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='dsh pipeline ')
        cls.addClassCleanup(cls.temp.cleanup)
        cls.root = Path(cls.temp.name)
        result = subprocess.run(
            [NODE, '--input-type=module', '-', str(cls.root), str(OBSERVER)],
            input=LIFECYCLE_SCRIPT, capture_output=True, text=True, timeout=15,
            cwd=cls.root,
        )
        if result.returncode:
            raise AssertionError('Node observer fixture failed:\n' + result.stderr)

    def read_state(self, stage, age=0):
        path = self.root / (stage + '.json')
        payload = json.loads(path.read_text())
        # Node has exited by the time Python consumes its snapshots. Mock only
        # process liveness; retain the real schema, heartbeat and task parsing.
        with patch('dsh_adapter.process_alive', return_value=True):
            return DshAdapter(path).poll(payload['updated_at'] + age)

    def test_observer_to_adapter_task_lifecycle(self):
        expected = {
            'working': ('RUN ULTRA', False, True, 0),
            'question': ('STOP', True, False, 1),
            'continued': ('RUN ULTRA', True, True, 1),
            'answered': ('RUN ULTRA', False, True, 0),
            'approval': ('STOP', True, False, 1),
            'approved': ('RUN ULTRA', False, True, 0),
            'ended': ('STOP', False, False, 0),
        }
        for stage, (motor, light, working, pending) in expected.items():
            with self.subTest(stage=stage):
                state = self.read_state(stage)
                self.assertTrue(state['healthy'])
                self.assertEqual(state['readiness'], 'ready')
                self.assertEqual(state['motor'], motor)
                self.assertEqual(state['light'], light)
                self.assertEqual(state['working_threads'], ['synthetic-dsh-task'] if working else [])
                self.assertEqual(state['waiting_threads'], ['synthetic-dsh-task'] if pending else [])
                self.assertEqual(state['pending_questions'], pending)
                raw = (self.root / (stage + '.json')).read_text()
                self.assertNotIn('PRIVATE_QUESTION_TEXT', raw)
                self.assertNotIn('PRIVATE_APPROVAL_TEXT', raw)

    def test_dsh_states_are_arbitrated_with_other_sources(self):
        workbuddy = {'healthy': True, 'motor': 'RUN MEDIUM', 'light': False}
        self.assertEqual(combine_sources({
            'dsh': self.read_state('question'), 'workbuddy': workbuddy,
        }), ('RUN MEDIUM', True))
        self.assertEqual(combine_sources({
            'dsh': self.read_state('continued'), 'workbuddy': workbuddy,
        }), ('RUN ULTRA', True))
        self.assertEqual(combine_sources({
            'dsh': self.read_state('stopped'), 'workbuddy': workbuddy,
        }), ('RUN MEDIUM', False))
        self.assertEqual(combine_sources({
            'dsh': self.read_state('question', age=3), 'workbuddy': workbuddy,
        }), ('RUN MEDIUM', False))

    def test_shutdown_and_expired_heartbeat_clear_dsh_outputs(self):
        for stage, age in [('stopped', 0), ('continued', 3)]:
            with self.subTest(stage=stage, age=age):
                state = self.read_state(stage, age=age)
                self.assertFalse(state['healthy'])
                self.assertEqual(state['readiness'], 'not_running')
                self.assertEqual(state['motor'], 'STOP')
                self.assertFalse(state['light'])
                self.assertEqual(state['working_threads'], [])
                self.assertEqual(state['waiting_threads'], [])
                self.assertEqual(state['pending_questions'], 0)


if __name__ == '__main__':
    unittest.main()
