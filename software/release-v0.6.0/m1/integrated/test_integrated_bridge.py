import unittest
from unittest.mock import patch
from integrated_bridge import Flower
from integrated_bridge import select_outputs
from state_reducer import RolloutSnapshot


class IntegrationStateTests(unittest.TestCase):
    def snapshot(self, states, now=100):
        return {'connected': True, 'last_message_at': now, 'threads': {
            tid: {'host_id':'local','owner_found':True,'parent_thread_id':None,
                  'observed_at':now,'runtime_status':status}
            for tid,status in states.items()}}

    def roots(self):
        return {t:RolloutSnapshot(t,True,e,100) for t,e in [('one','ultra'),('two','high')]}

    def test_blocking_approval_stops_only_that_chat(self):
        snap=self.snapshot({'one':{'type':'active','activeFlags':['waitingOnApproval']},
                            'two':{'type':'active','activeFlags':[]}})
        state,healthy=select_outputs(self.roots(),snap,[],100)
        self.assertTrue(healthy);self.assertEqual(state.motor_command,'RUN HIGH')
        self.assertTrue(state.light);self.assertEqual(state.waiting_threads,('one',))

    def test_single_blocking_input_stops_and_lights(self):
        snap=self.snapshot({'one':{'type':'active','activeFlags':['waitingOnUserInput']}})
        state,_=select_outputs(self.roots(),snap,[],100)
        self.assertEqual(state.motor_command,'STOP');self.assertTrue(state.light)

    def test_async_question_does_not_suppress_active_work(self):
        snap=self.snapshot({'one':{'type':'active','activeFlags':[]}})
        state,_=select_outputs(self.roots(),snap,[('one','call1',0)],100)
        self.assertEqual(state.motor_command,'RUN ULTRA');self.assertTrue(state.light)

    def test_idle_keeps_async_question_light(self):
        snap=self.snapshot({'one':{'type':'idle'}})
        state,_=select_outputs(self.roots(),snap,[('one','call1',0)],100)
        self.assertEqual(state.motor_command,'STOP');self.assertTrue(state.light)

    def test_stale_wait_cannot_restart_from_rollout(self):
        snap=self.snapshot({'one':{'type':'active','activeFlags':['waitingOnApproval']}})
        snap['last_message_at']=110
        state,_=select_outputs(self.roots(),snap,[],110)
        self.assertEqual(state.motor_command,'STOP')

    def test_missing_owner_does_not_reuse_previous_active_status(self):
        snap=self.snapshot({'one':{'type':'active','activeFlags':[]}})
        snap['threads']['one'].update(owner_found=False,owner_checked_at=100)
        state,_=select_outputs(self.roots(),snap,[],100)
        self.assertEqual(state.motor_command,'STOP')

    def test_disconnected_feed_fails_quiet_without_mutating_pending(self):
        snap=self.snapshot({'one':{'type':'active','activeFlags':[]}})
        snap['connected']=False
        pending=[('one','call1',0)]
        state,healthy=select_outputs(self.roots(),snap,pending,100)
        self.assertFalse(healthy);self.assertEqual(state.motor_command,'STOP')
        self.assertFalse(state.light);self.assertEqual(len(pending),1)

    def test_archived_and_unloaded_are_not_work(self):
        snap=self.snapshot({'one':{'type':'active','activeFlags':[]},'two':{'type':'notLoaded'}})
        snap['threads']['one']['archived']=True
        state,_=select_outputs(self.roots(),snap,[],100)
        self.assertEqual(state.motor_command,'STOP')


class TransportTests(unittest.TestCase):
    def ready(self):
        f=Flower(); f.fd=42; f.path='test'; return f

    @patch('integrated_bridge.select.select',return_value=([],[],[]))
    def test_motor_and_light_share_one_frame_and_heartbeat(self,_):
        f=self.ready()
        with patch('integrated_bridge.os.write',side_effect=lambda fd,data:len(data)) as write:
            with patch('integrated_bridge.time.monotonic',return_value=10):
                self.assertTrue(f.send('RUN HIGH',False))
                self.assertTrue(f.send('RUN HIGH',False))
            self.assertEqual(write.call_count,1)
            self.assertEqual(write.call_args.args,(42,b'RUN HIGH\nATTENTION OFF\n'))
            with patch('integrated_bridge.time.monotonic',return_value=10.1):
                f.send('RUN HIGH',True)
            self.assertEqual(write.call_args.args[1],b'RUN HIGH\nATTENTION ON\n')
            with patch('integrated_bridge.time.monotonic',return_value=12):
                f.send('RUN HIGH',True)
            self.assertEqual(write.call_count,3)

    def test_short_write_discards_connection_for_reprobe(self):
        f=self.ready()
        with patch('integrated_bridge.os.write',return_value=2),patch.object(f,'close') as close:
            self.assertFalse(f.send('STOP',False));close.assert_called_once()

    def test_shutdown_sends_both_off(self):
        f=self.ready()
        with patch('integrated_bridge.os.write') as write,patch.object(f,'close') as close:
            f.stop();write.assert_called_once_with(42,b'STOP\nATTENTION OFF\n');close.assert_called_once()

    def test_unrecognized_speed_never_written(self):
        f=self.ready()
        with patch('integrated_bridge.os.write') as write:
            with self.assertRaises(ValueError):f.send('TEST FAST',True)
            write.assert_not_called()

if __name__=='__main__':unittest.main()
