import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).parent))
from workbuddy_adapter import WorkBuddyAdapter, NotifierEvents, SdkActivity


class WorkBuddyAdapterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='workbuddy test ')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'sessions').mkdir()
        (self.root / 'logs').mkdir()
        self.db = self.root / 'workbuddy.db'
        self.log = self.root / 'logs/daemon.log'
        self.log.write_text('')
        connection = sqlite3.connect(self.db)
        try:
            connection.execute('CREATE TABLE sessions(id TEXT,status TEXT,updated_at INTEGER,model TEXT,transport TEXT,deleted_at INTEGER)')
            connection.commit()
        finally:
            connection.close()
        self.adapter = WorkBuddyAdapter(self.root)
        self.now = 1800000000
        self.kill = patch('process_probe.process_alive', return_value=True).start()
        self.addCleanup(patch.stopall)

    def task(self, sid='one', status='working', model='fast-model', at=None, pid=123, started=1):
        at = self.now if at is None else at
        connection = sqlite3.connect(self.db)
        try:
            connection.execute('DELETE FROM sessions WHERE id=?', (sid,))
            connection.execute('INSERT INTO sessions VALUES(?,?,?,?,?,?)', (sid,status,int(at*1000),model,'local',None))
            connection.commit()
        finally:
            connection.close()
        (self.root / f'sessions/{pid}.json').write_text(json.dumps({'pid':pid,'sessionId':sid,'startedAt':started}))

    def event(self, sid='one', status='pending', kind='question', at=None, partial=False, scope='daemon-server:task-notify'):
        at = self.now if at is None else at
        line = json.dumps({'timestamp':datetime.fromtimestamp(at,timezone.utc).isoformat(), 'level':'info', 'scope':scope,
                          'message':[f'[TaskStatusNotifier] upsert received: session={sid} prev=working new={status} kind={kind}']})
        with self.log.open('a') as f: f.write(line + ('' if partial else '\n'))

    def poll(self, delta=0):
        return self.adapter.poll(self.now+delta)

    def sdk(self, event, at=None, sid='one', instance='ci-test', **fields):
        at=self.now if at is None else at
        day=datetime.fromtimestamp(at,timezone.utc).strftime('%Y-%m-%d')
        path=self.root/'logs'/day/'sdk/conversations'/f'{sid}.log'
        path.parent.mkdir(parents=True,exist_ok=True)
        data={'conversationId':sid,'instanceId':instance,**fields}
        with path.open('a') as f:f.write(datetime.fromtimestamp(at,timezone.utc).isoformat()+' '+event+' '+json.dumps(data)+'\n')

    def long_task(self, heartbeat=None, sdk_age=10, worker_start=None):
        start=self.now-1000 if worker_start is None else worker_start
        self.task(at=self.now-900,started=int(start*1000))
        path=self.root/'sessions/123.json'
        data=json.loads(path.read_text())
        data.update(kind='interactive',lastHeartbeat=int((self.now-5 if heartbeat is None else heartbeat)*1000))
        path.write_text(json.dumps(data))
        self.sdk('state-machine:transition',at=self.now-900,input='PROMPT_SENT',valid=True,to='working')
        self.sdk('event-machine:dispatch',at=self.now-sdk_age,input='session_info_update',requestId='current-turn')

    def test_product_tiers_and_unknown_model(self):
        for model, speed in [('fast-model','LOW'),('balanced-model','HIGH'),('deep-model','ULTRA'),('new-model','HIGH'),(None,'LOW')]:
            self.adapter = WorkBuddyAdapter(self.root)
            self.task(model=model)
            self.assertEqual(self.poll()['motor'], 'RUN '+speed)

    def test_idle_pending_does_not_light(self):
        self.task(status='pending')
        self.assertFalse(self.poll()['light'])
        self.assertEqual(self.poll()['motor'],'STOP')

    def test_question_and_permission_need_matching_current_transition(self):
        for kind in ('question','permission','user_input'):
            self.adapter=WorkBuddyAdapter(self.root)
            self.task(status='pending')
            self.event(kind=kind)
            state=self.poll()
            self.assertTrue(state['light'])
            self.assertEqual(state['motor'],'STOP')
            self.assertEqual(state['waiting_threads'],['one'])

    def test_old_pending_from_previous_turn_does_not_light(self):
        self.task(status='pending')
        self.event(at=self.now-100)
        self.assertFalse(self.poll()['light'])

    def test_long_wait_survives_restart_without_six_hundred_second_timeout(self):
        self.task(status='pending',at=self.now-86400)
        self.event(at=self.now-86400)
        self.assertTrue(self.poll()['light'])
        self.adapter=WorkBuddyAdapter(self.root)
        self.assertTrue(self.poll(1000)['light'])

    def test_answer_clears_light_and_preserves_turn_speed(self):
        self.task(model='deep-model')
        self.assertEqual(self.poll()['motor'],'RUN ULTRA')
        self.task(status='pending',model='fast-model',at=self.now+1)
        self.event(at=self.now+1)
        self.assertTrue(self.poll(1)['light'])
        self.task(model='fast-model',at=self.now+2)
        state=self.poll(2)
        self.assertFalse(state['light'])
        self.assertEqual(state['motor'],'RUN ULTRA')

    def test_cancellation_and_error_clear_wait(self):
        for status in ('completed','terminated','failed','error','archived'):
            self.task(status='pending')
            self.event()
            self.assertTrue(self.poll()['light'])
            self.task(status=status,at=self.now+1)
            state=self.poll(1)
            self.assertFalse(state['light'])
            self.assertEqual(state['motor'],'STOP')

    def test_parallel_wait_cannot_select_speed(self):
        self.task(status='pending',model='deep-model')
        self.event()
        self.task(sid='two',pid=124,model='fast-model')
        state=self.poll()
        self.assertTrue(state['light'])
        self.assertEqual(state['motor'],'RUN LOW')
        self.assertEqual(state['working_threads'],['two'])

    def test_worker_death_and_new_worker_reset(self):
        self.task(status='pending')
        self.event()
        self.kill.side_effect=ProcessLookupError
        self.assertFalse(self.poll()['light'])
        self.kill.side_effect=None
        self.task(model='deep-model')
        self.assertEqual(self.poll()['motor'],'RUN ULTRA')
        self.task(model='fast-model',started=2,at=self.now+1)
        self.assertEqual(self.poll(1)['motor'],'RUN LOW')

    def test_denied_worker_probe_reports_error(self):
        self.task()
        self.kill.side_effect=PermissionError
        state=self.poll()
        self.assertEqual(state['motor'],'STOP')
        self.assertIn('denied',state['error'])
        self.assertFalse(state['healthy'])

    def test_missing_notifier_log_is_not_reported_as_fully_supported(self):
        self.task()
        self.log.unlink()
        state=self.poll()
        self.assertFalse(state['healthy'])
        self.assertIn('log is missing',state['error'])
        self.assertEqual(state['motor'],'STOP')

    def test_notifier_read_failure_is_not_reported_as_healthy(self):
        self.task()
        with patch.object(self.adapter.events, 'poll'):
            self.adapter.events.error='WorkBuddy task notification metadata is not readable'
            state=self.poll()
        self.assertFalse(state['healthy'])
        self.assertEqual(state['motor'],'STOP')

    def test_missing_database_fails_quiet(self):
        self.db.unlink()
        state=self.poll()
        self.assertFalse(state['healthy'])
        self.assertFalse(state['light'])
        self.assertEqual(state['motor'],'STOP')

    def test_prewarms_are_excluded(self):
        self.task()
        (self.root/'sessions/123.json').write_text(json.dumps({'pid':123,'sessionId':'one','kind':'prewarm'}))
        self.assertEqual(self.poll()['motor'],'STOP')

    def test_partial_line_rotation_and_duplicate_events(self):
        self.task(status='pending')
        self.event(partial=True)
        self.assertFalse(self.poll()['light'])
        with self.log.open('a') as f:f.write('\n')
        self.assertTrue(self.poll()['light'])
        self.log.rename(self.root/'logs/daemon.old.log')
        self.event()
        self.assertTrue(self.poll()['light'])
        self.assertEqual(self.poll()['pending_questions'],1)

    def test_late_event_cannot_revive_completed_state(self):
        self.task(status='pending')
        self.event(status='completed',kind='<none>',at=self.now+1)
        self.event(at=self.now)
        self.assertFalse(self.poll(1)['light'])

    def test_invalid_and_future_events_do_not_light(self):
        self.task(status='pending')
        self.log.write_text('malformed\n')
        self.event(at=self.now+30)
        self.event(scope='other-app')
        self.assertFalse(self.poll()['light'])

    def test_completed_event_between_polls_resets_model_tier(self):
        self.task(model='deep-model')
        self.assertEqual(self.poll()['motor'],'RUN ULTRA')
        self.event(status='completed',kind='<none>',at=self.now+1)
        self.task(model='fast-model',at=self.now+2)
        self.assertEqual(self.poll(2)['motor'],'RUN LOW')

    def test_newer_notifier_terminal_overrides_stale_working_database(self):
        self.task()
        self.event(status='completed',kind='<none>',at=self.now+1)
        self.assertEqual(self.poll(1)['motor'],'STOP')

    def test_previous_notifier_terminal_does_not_stop_new_turn(self):
        self.task()
        self.event(status='completed',kind='<none>',at=self.now-.001)
        self.assertEqual(self.poll()['motor'],'RUN LOW')

    def test_silent_long_work_and_stale_heartbeat_do_not_run_forever(self):
        self.task(at=self.now-601)
        path=self.root/'sessions/123.json'
        data=json.loads(path.read_text());data['lastHeartbeat']=int(self.now*1000);path.write_text(json.dumps(data))
        state=self.poll()
        self.assertEqual(state['motor'],'STOP')
        self.assertEqual(state['degraded_threads'],['one'])

    def test_notifier_recent_work_metadata_can_refresh_stale_db(self):
        self.task(at=self.now-601)
        self.event(status='working',kind='<none>',at=self.now)
        self.assertEqual(self.poll()['motor'],'RUN LOW')

    def test_long_work_needs_fresh_sdk_request_and_matching_live_worker(self):
        self.long_task()
        self.assertEqual(self.poll()['motor'],'RUN LOW')
        # Reconstructing the bridge can validate the same active turn.
        self.adapter=WorkBuddyAdapter(self.root)
        self.assertEqual(self.poll()['motor'],'RUN LOW')

    def test_long_work_stops_when_sdk_activity_is_stale(self):
        self.long_task(sdk_age=91)
        self.assertEqual(self.poll()['motor'],'STOP')

    def test_static_registration_heartbeat_does_not_stop_live_sdk_work(self):
        self.long_task(heartbeat=self.now-1000)
        self.assertEqual(self.poll()['motor'],'RUN LOW')
        # WorkBuddy 5.9.3 can leave this field at worker startup indefinitely.
        self.adapter=WorkBuddyAdapter(self.root)
        self.assertEqual(self.poll()['motor'],'RUN LOW')

    def test_future_registration_heartbeat_cannot_replace_sdk_activity(self):
        self.long_task(heartbeat=self.now+10,sdk_age=91)
        self.assertEqual(self.poll()['motor'],'STOP')

    def test_interactive_heartbeat_alone_cannot_extend_stale_work(self):
        self.long_task()
        for p in (self.root/'logs').glob('*/sdk/conversations/*.log'):p.unlink()
        self.assertEqual(self.poll()['motor'],'STOP')

    def test_new_worker_cannot_reuse_previous_worker_sdk_turn(self):
        self.long_task(worker_start=self.now-30)
        self.assertEqual(self.poll()['motor'],'STOP')

    def test_late_different_request_cannot_refresh_long_task(self):
        self.long_task(sdk_age=120)
        self.sdk('event-machine:dispatch',input='session_info_update',requestId='previous-turn')
        self.assertEqual(self.poll()['motor'],'STOP')

    def test_new_sdk_instance_cannot_inherit_old_active_turn(self):
        self.long_task(sdk_age=120)
        self.sdk('event-machine:dispatch',instance='new-instance',input='session_info_update',requestId='current-turn')
        self.assertEqual(self.poll()['motor'],'STOP')

    def test_sdk_explicit_stop_cannot_be_extended_by_alive_worker(self):
        for status in ('completed','failed','error','terminated','pending','idle'):
            for p in (self.root/'logs').glob('*/sdk/conversations/*.log'):p.unlink()
            self.adapter=WorkBuddyAdapter(self.root)
            self.long_task()
            self.sdk('runtime-status:persisted',at=self.now+1,status=status)
            self.assertEqual(self.poll(1)['motor'],'STOP')

    def test_fresh_database_cannot_override_newer_sdk_terminal_state(self):
        self.long_task()
        self.task(at=self.now-2,started=int((self.now-1000)*1000))
        p=self.root/'sessions/123.json';data=json.loads(p.read_text());data.update(kind='interactive',lastHeartbeat=int(self.now*1000));p.write_text(json.dumps(data))
        self.sdk('runtime-status:persisted',status='completed')
        self.assertEqual(self.poll()['motor'],'STOP')

    def test_old_sdk_terminal_does_not_stop_a_new_database_turn(self):
        self.long_task()
        self.sdk('runtime-status:persisted',at=self.now-.001,status='completed')
        connection = sqlite3.connect(self.db)
        try:
            connection.execute('UPDATE sessions SET updated_at=?',(int(self.now*1000),))
            connection.commit()
        finally:
            connection.close()
        # The new SDK PROMPT_SENT may not have been flushed yet.
        self.assertEqual(self.poll()['motor'],'RUN LOW')

    def test_new_prompt_resets_previous_request_and_can_extend_new_turn(self):
        self.long_task(sdk_age=120)
        self.assertEqual(self.poll()['motor'],'STOP')
        self.sdk('runtime-status:persisted',at=self.now-110,status='completed')
        connection = sqlite3.connect(self.db)
        try:
            connection.execute('UPDATE sessions SET updated_at=?',(int((self.now-100)*1000),))
            connection.commit()
        finally:
            connection.close()
        self.sdk('state-machine:transition',at=self.now-100,input='PROMPT_SENT',valid=True,to='working')
        self.sdk('event-machine:dispatch',at=self.now-10,input='session_info_update',requestId='new-turn')
        self.adapter.stale_seconds=1
        self.assertEqual(self.poll()['motor'],'RUN LOW')
        self.assertEqual(self.adapter.sdk.turns['one'].request,'new-turn')

    def test_other_dispatch_payloads_are_rejected_before_json_decoding(self):
        reader=SdkActivity(self.root)
        line=b'2027-01-15T08:00:00Z event-machine:dispatch {"input":"text_delta","output":"ignored"}'
        with patch('workbuddy_adapter.json.loads') as decode:
            reader._line(line,'one',self.now)
        decode.assert_not_called()

    def test_fresh_sdk_activity_never_clears_a_database_wait(self):
        self.long_task()
        self.task(status='pending',at=self.now,started=int((self.now-1000)*1000))
        self.event()
        state=self.poll()
        self.assertEqual(state['motor'],'STOP')
        self.assertTrue(state['light'])

    def test_fresh_sdk_activity_never_revives_database_terminal_task(self):
        self.long_task()
        self.task(status='completed',started=int((self.now-1000)*1000))
        self.assertEqual(self.poll()['motor'],'STOP')

    def test_long_work_connection_loss_stops_after_grace(self):
        self.long_task()
        self.assertEqual(self.poll()['motor'],'RUN LOW')
        self.assertEqual(self.poll(91)['motor'],'STOP')

    def test_legacy_schema_without_model(self):
        connection = sqlite3.connect(self.db)
        try:
            connection.execute('DROP TABLE sessions')
            connection.execute('CREATE TABLE sessions(id TEXT,status TEXT,updated_at INTEGER,transport TEXT,deleted_at INTEGER)')
            connection.execute('INSERT INTO sessions VALUES(?,?,?,?,NULL)',('one','working',int(self.now*1000),'local'))
            connection.commit()
        finally:
            connection.close()
        (self.root/'sessions/123.json').write_text(json.dumps({'pid':123,'sessionId':'one'}))
        self.assertEqual(self.poll()['motor'],'RUN LOW')


if __name__ == '__main__':unittest.main()
