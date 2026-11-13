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


class FakePort:
    """Records writes; optionally fails like a short serial write."""

    def __init__(self, short_write=False):
        self.writes=[]
        self.short_write=short_write
        self.closed=False

    def write(self,data):
        self.writes.append(data)
        if self.short_write:
            raise OSError('Short serial write')

    def read(self,limit=4096):
        return b''

    def close(self):
        self.closed=True


class TransportTests(unittest.TestCase):
    def ready(self, **kwargs):
        f=Flower(); f.serial=FakePort(**kwargs); f.path='test'
        f.capabilities=['motor','attention']; return f

    def test_motor_and_light_share_one_frame_and_heartbeat(self):
        f=self.ready()
        with patch('integrated_bridge.time.monotonic',return_value=10):
            self.assertTrue(f.send('RUN HIGH',False))
            self.assertTrue(f.send('RUN HIGH',False))
        self.assertEqual(len(f.serial.writes),1)
        self.assertEqual(f.serial.writes[0],b'RUN HIGH\nATTENTION OFF\n')
        with patch('integrated_bridge.time.monotonic',return_value=10.1):
            f.send('RUN HIGH',True)
        self.assertEqual(f.serial.writes[-1],b'RUN HIGH\nATTENTION ON\n')
        with patch('integrated_bridge.time.monotonic',return_value=12):
            f.send('RUN HIGH',True)
        self.assertEqual(len(f.serial.writes),3)

    def test_short_write_discards_connection_for_reprobe(self):
        f=self.ready(short_write=True)
        with patch.object(f,'close') as close:
            self.assertFalse(f.send('STOP',False));close.assert_called_once()

    def test_shutdown_sends_both_off(self):
        f=self.ready()
        with patch.object(f,'close') as close:
            f.stop()
        self.assertEqual(f.serial.writes,[b'STOP\nATTENTION OFF\n'])
        close.assert_called_once()

    def test_unrecognized_speed_never_written(self):
        f=self.ready()
        with self.assertRaises(ValueError):f.send('TEST FAST',True)
        self.assertEqual(f.serial.writes,[])
