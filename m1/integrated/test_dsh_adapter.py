import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent))
from dsh_adapter import DshAdapter, process_alive, speed_for_effort


class DshAdapterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='dsh adapter ')
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'status.json'
        self.adapter = DshAdapter(self.path)
        self.now = 1800000000
        self.alive = patch('dsh_adapter.process_alive', return_value=True).start()
        self.addCleanup(patch.stopall)

    def write(self, **overrides):
        payload = {'schema': 1, 'instance': 'instance-a', 'pid': 4242,
                   'updated_at': self.now, 'connected': True, 'error': None, 'tasks': []}
        payload.update(overrides)
        self.path.write_text(json.dumps(payload))
        return payload

    def task(self, **overrides):
        task = {'id': 'one', 'running': True, 'effort': 'max', 'model': 'deepseek-flash',
                'blocking': False, 'questions': 0, 'approvals': 0}
        task.update(overrides)
        return task

    def poll(self, delta=0):
        return self.adapter.poll(self.now + delta)

    # --- readiness -------------------------------------------------------

    def test_missing_file_waits_for_dsh_to_be_installed(self):
        result = self.poll()
        self.assertFalse(result['healthy'])
        self.assertEqual(result['readiness'], 'not_initialized')
        self.assertEqual(result['motor'], 'STOP')
        self.assertFalse(result['light'])

    def test_stale_heartbeat_means_dsh_is_gone(self):
        self.write()
        result = self.poll(delta=4)
        self.assertEqual(result['readiness'], 'not_running')
        self.assertFalse(result['healthy'])

    def test_a_small_future_skew_is_tolerated(self):
        self.write(updated_at=self.now + 1)
        self.assertTrue(self.poll()['healthy'])

    def test_a_far_future_heartbeat_is_not_trusted(self):
        self.write(updated_at=self.now + 30)
        self.assertEqual(self.poll()['readiness'], 'not_running')

    def test_a_disconnected_observer_stops_the_flower(self):
        self.write(connected=False)
        self.assertEqual(self.poll()['readiness'], 'not_running')

    def test_reported_incompatibility_is_an_error_not_a_silent_stop(self):
        self.write(error='unsupported_task_metadata')
        result = self.poll()
        self.assertEqual(result['readiness'], 'error')
        self.assertEqual(result['error'], 'DSH task metadata is incompatible')

    def test_a_reused_but_dead_pid_is_not_running(self):
        self.write()
        self.alive.return_value = False
        self.assertEqual(self.poll()['readiness'], 'not_running')

    def test_a_live_pid_keeps_the_snapshot_usable(self):
        self.write(tasks=[self.task()])
        self.assertTrue(self.poll()['healthy'])

    def test_a_permission_denied_probe_still_counts_as_alive(self):
        with patch('process_probe.process_alive', side_effect=PermissionError):
            self.assertTrue(process_alive(4242))

    def test_a_missing_process_is_reported_as_gone(self):
        with patch('process_probe.process_alive', return_value=False):
            self.assertFalse(process_alive(4242))

    def test_close_is_harmless(self):
        self.adapter.close()

    # --- effort mapping --------------------------------------------------

    def test_effort_tiers_map_to_motor_speeds(self):
        self.assertEqual(speed_for_effort(None), 'LOW')
        for effort, speed in [('off', 'LOW'), ('none', 'LOW'), ('minimal', 'LOW'),
                              ('low', 'MEDIUM'), ('medium', 'MEDIUM'),
                              ('high', 'HIGH'), ('xhigh', 'XHIGH'), ('max', 'ULTRA')]:
            self.assertEqual(speed_for_effort(effort), speed, effort)

    def test_unknown_effort_falls_back_to_high(self):
        self.assertEqual(speed_for_effort('turbo'), 'HIGH')

    def test_effort_is_case_insensitive(self):
        self.assertEqual(speed_for_effort('MAX'), 'ULTRA')

    def test_the_fastest_active_task_wins(self):
        self.write(tasks=[self.task(id='slow', effort='low'),
                          self.task(id='fast', effort='max')])
        result = self.poll()
        self.assertEqual(result['motor'], 'RUN ULTRA')
        self.assertEqual(sorted(result['working_threads']), ['fast', 'slow'])

    def test_an_idle_task_reports_stop(self):
        self.write(tasks=[self.task(running=False)])
        result = self.poll()
        self.assertEqual(result['motor'], 'STOP')
        self.assertEqual(result['working_threads'], [])

    # --- attention -------------------------------------------------------

    def test_a_blocking_question_pauses_and_lights(self):
        self.write(tasks=[self.task(blocking=True, questions=1)])
        result = self.poll()
        self.assertEqual(result['motor'], 'STOP')
        self.assertTrue(result['light'])
        self.assertEqual(result['waiting_threads'], ['one'])
        self.assertEqual(result['pending_questions'], 1)

    def test_an_approval_pauses_and_lights(self):
        self.write(tasks=[self.task(blocking=True, approvals=1)])
        result = self.poll()
        self.assertEqual(result['motor'], 'STOP')
        self.assertTrue(result['light'])
        self.assertEqual(result['pending_questions'], 1)

    def test_an_async_question_keeps_the_flower_turning_and_lit(self):
        # DSH can keep working while a question waits for an answer.
        self.write(tasks=[self.task(blocking=False, questions=1)])
        result = self.poll()
        self.assertEqual(result['motor'], 'RUN ULTRA')
        self.assertTrue(result['light'])
        self.assertEqual(result['working_threads'], ['one'])
        self.assertEqual(result['waiting_threads'], ['one'])

    def test_pending_counts_add_up_across_tasks(self):
        self.write(tasks=[self.task(id='a', blocking=True, questions=2),
                          self.task(id='b', blocking=True, approvals=1)])
        self.assertEqual(self.poll()['pending_questions'], 3)

    def test_nothing_waiting_means_the_light_is_off(self):
        self.write(tasks=[self.task()])
        self.assertFalse(self.poll()['light'])

    # --- malformed input -------------------------------------------------

    def test_an_unsupported_schema_is_an_error(self):
        self.write(schema=2)
        result = self.poll()
        self.assertEqual(result['readiness'], 'error')
        self.assertFalse(result['healthy'])

    def test_invalid_json_is_an_error(self):
        self.path.write_text('{not json')
        self.assertEqual(self.poll()['readiness'], 'error')

    def test_a_non_finite_heartbeat_is_an_error(self):
        self.path.write_text(json.dumps({'schema': 1, 'pid': 1, 'updated_at': float('nan'),
                                         'connected': True, 'tasks': []}))
        self.assertEqual(self.poll()['readiness'], 'error')

    def test_an_oversized_snapshot_is_rejected_before_parsing(self):
        self.path.write_text('x' * (DshAdapter.MAX_BYTES + 1))
        self.assertEqual(self.poll()['readiness'], 'error')

    def test_an_invalid_pid_is_an_error(self):
        self.write(pid='4242')
        self.assertEqual(self.poll()['readiness'], 'error')

    def test_tasks_must_be_a_list(self):
        self.write(tasks={'one': self.task()})
        self.assertEqual(self.poll()['readiness'], 'error')

    def test_duplicate_task_ids_are_rejected(self):
        self.write(tasks=[self.task(), self.task()])
        self.assertEqual(self.poll()['readiness'], 'error')

    def test_task_flags_must_be_booleans(self):
        self.write(tasks=[self.task(running=1)])
        self.assertEqual(self.poll()['readiness'], 'error')

    def test_attention_counts_must_be_non_negative_integers(self):
        self.write(tasks=[self.task(questions=-1)])
        self.assertEqual(self.poll()['readiness'], 'error')

    def test_an_unbounded_task_list_is_rejected(self):
        self.write(tasks=[self.task(id=f't{i}') for i in range(4097)])
        self.assertEqual(self.poll()['readiness'], 'error')

    def test_an_unknown_effort_type_is_an_error(self):
        self.write(tasks=[self.task(effort=2)])
        self.assertEqual(self.poll()['readiness'], 'error')


if __name__ == '__main__':
    unittest.main()
