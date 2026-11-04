import datetime as dt
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from attention_state import AttentionAdapter

NOW = 1_800_000_000.0

def record(kind, payload, age=0):
    return {'timestamp':dt.datetime.fromtimestamp(NOW-age,dt.timezone.utc).isoformat(), 'type':kind,'payload':payload}

def meta(session='s', **extra):
    return record('session_meta',dict(id=session,thread_source='user',**extra))

def ask(call='a', count=1, age=0, turn='turn-a'):
    return record('response_item',{'type':'function_call','name':'request_user_input_async','call_id':call,
        'arguments':json.dumps({'questions':[{'title':'Test question'} for _ in range(count)]}),
        'internal_chat_message_metadata_passthrough':{'turn_id':turn}},age)

def reply(call='a',index=0,age=0, role='user',wrapper=True):
    text=json.dumps([{'questionItemId':json.dumps(['request_user_input_async',call,index]),'answer':'ok'}])
    if wrapper:text='<send_user_message_question_reply>\n'+text+'\n</send_user_message_question_reply>'
    return record('response_item',{'type':'message','role':role,'content':[{'type':'input_text','text':text}]},age)

class AttentionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.adapter=AttentionAdapter(self.root,start_timestamp=NOW-1000)
    def tearDown(self):
        self.adapter.close();self.tmp.cleanup()
    def write(self,name,*records,append=False,mtime=NOW):
        p=self.root/('rollout-'+name+'.jsonl')
        with p.open('a' if append else 'w') as f:
            for r in records:f.write(json.dumps(r)+'\n')
        os.utime(p,(mtime,mtime));return p
    def check(self,expected,now=NOW):
        self.adapter.poll(now);self.assertEqual(self.adapter.selected(now),(bool(expected),expected))
    def test_new_question_answer_and_incremental(self):
        p=self.write('a',meta(),ask());self.check(1)
        old=self.adapter.files[p].offset;self.assertFalse(self.adapter.poll(NOW));self.assertEqual(self.adapter.files[p].offset,old)
        self.write('a',reply(),append=True);self.check(0)
    def test_multi_questions_exact_ids(self):
        self.write('a',meta(),ask(count=2),ask('b'),reply('wrong'),reply('a',0));self.check(2)
        self.write('a',reply('b'),append=True);self.check(1)
        self.write('a',reply('a',1),append=True);self.check(0)
    def test_async_tool_return_and_task_complete_do_not_clear(self):
        self.write('a',meta(),ask(),record('response_item',{'type':'function_call_output','call_id':'a','output':'{"accepted":true}'}),record('event_msg',{'type':'task_complete','turn_id':'turn-a'}));self.check(1)
    def test_abort_only_matching_turn(self):
        self.write('a',meta(),ask('a',turn='t1'),ask('b',turn='t2'),record('event_msg',{'type':'turn_aborted','turn_id':'t1'}));self.check(1)
        self.write('a',record('event_msg',{'type':'turn_aborted'}),append=True);self.check(0)
    def test_pending_never_expires_in_selected_or_poll(self):
        self.write('a',meta(),ask());self.check(1)
        self.assertEqual(self.adapter.selected(NOW+600),(True,1))
        self.check(1,NOW+86400*30)
    def test_pre_install_or_future_missing_timestamp_fail_closed(self):
        old=ask(age=1001);future=ask('future',age=-5);missing=ask('missing');missing.pop('timestamp')
        self.write('a',meta(),old,future,missing);self.check(0)
    def test_record_appended_during_live_scan_is_not_lost(self):
        self.write('a',meta(),ask(age=-.01))
        with patch('attention_state.time.time',side_effect=[NOW,NOW+.05]):
            self.adapter.poll()
        self.assertEqual(self.adapter.selected(NOW+.05),(True,1))
        self.adapter.poll(NOW+.1)
        self.assertEqual(self.adapter.selected(NOW+.1),(True,1))
    def test_selected_earlier_loop_timestamp_preserves_accepted_pending(self):
        self.write('a',meta(),ask());self.check(1)
        self.assertEqual(self.adapter.selected(NOW-.01),(True,1))
        self.assertEqual(self.adapter.selected(NOW+.01),(True,1))
    def test_cross_session_answers_do_not_clear(self):
        self.write('a',meta('s1'),ask());self.write('b',meta('s2'),reply());self.check(1)
    def test_cross_instance_reply_and_duplicate_dedup(self):
        self.write('a',meta(),ask(age=10));self.write('b',meta(),ask(age=10));self.check(1)
        self.write('b',reply(),append=True);self.check(0)
        self.write('c',meta(),ask(age=10));self.check(0)
    def test_reverse_file_order_on_startup(self):
        self.write('reply',meta(),reply());self.write('ask',meta(),ask(age=10));self.check(0)
    def test_nonroot_filtered(self):
        self.write('child',meta(parent_thread_id='s'),ask())
        self.write('sub',meta(source={'subagent':{}}),ask())
        guard=meta();guard['payload']['thread_source']='guardian';self.write('guard',guard,ask())
        self.check(0)
    def test_forked_user_chat_allowed(self):
        self.write('a',meta(forked_from_id='old',parent_thread_id=None),ask());self.check(1)
    def test_ordinary_text_tool_output_assistant_and_unwrapped_reply_ignored(self):
        self.write('a',meta(),ask(),reply(role='assistant'),reply(wrapper=False),record('response_item',{'type':'message','role':'user','content':[{'text':'I answered request_user_input_async'}]}),record('response_item',{'type':'function_call_output','output':json.dumps(reply())}));self.check(1)
    def test_embedded_quoted_ask_does_not_light(self):
        self.write('a',meta(),record('response_item',{'type':'message','role':'assistant','content':[{'text':json.dumps(ask())}]}));self.check(0)
    def test_delete_and_stale_file_are_not_cancellation(self):
        p=self.write('a',meta(),ask());self.check(1);p.unlink();self.check(1)
        p=self.write('a',meta(),ask());self.check(1);os.utime(p,(NOW-601,NOW-601));self.check(1)
    def test_replace_and_truncate_are_not_cancellation(self):
        p=self.write('a',meta(),ask());self.check(1)
        new=self.root/'new';new.write_text(json.dumps(meta())+'\n');os.utime(new,(NOW,NOW));new.replace(p);self.check(1)
        self.write('a',ask(),append=True);self.check(1)
        self.write('a',meta());self.check(1)
    def test_root_replaced_with_subagent(self):
        p=self.write('a',meta(),ask());self.check(1)
        other=self.write('b',meta(parent_thread_id='x'),ask());other.replace(p);self.check(1)
    def test_partial_trailing_line_waits(self):
        p=self.write('a',meta());encoded=json.dumps(ask()).encode()
        with p.open('ab') as f:f.write(encoded[:80])
        os.utime(p,(NOW,NOW));self.check(0)
        with p.open('ab') as f:f.write(encoded[80:]+b'\n')
        os.utime(p,(NOW,NOW));self.check(1)
    def test_bad_json_types_ignored(self):
        self.write('a',meta(),record('response_item',{'type':'function_call','name':'request_user_input_async','call_id':'a','arguments':'[]'}),record('response_item',{'type':'message','role':'user','content':['bad',{'text':'<send_user_message_question_reply>{}</send_user_message_question_reply>'}]}),record('response_item',None));self.check(0)
    def test_invalid_boolean_index_does_not_clear(self):
        bad=reply();bad['payload']['content'][0]['text']='<send_user_message_question_reply>'+json.dumps([{'questionItemId':json.dumps(['request_user_input_async','a',False]),'answer':'ok'}])+'</send_user_message_question_reply>'
        self.write('a',meta(),ask(),bad);self.check(1)
    def test_abort_tombstone_blocks_old_newfile_replay(self):
        self.write('a',meta(),record('event_msg',{'type':'turn_aborted','turn_id':'turn-a'}));self.check(0)
        self.write('b',meta(),ask(age=10));self.check(0)
    def test_missing_turn_uses_task_started(self):
        question=ask();question['payload'].pop('internal_chat_message_metadata_passthrough')
        self.write('a',meta(),record('event_msg',{'type':'task_started','turn_id':'t'}),question,record('event_msg',{'type':'turn_aborted','turn_id':'t'}));self.check(0)
    def test_invalid_timeout_rejected_and_close_dark(self):
        with self.assertRaises(ValueError):AttentionAdapter(self.root,0)
        self.write('a',meta(),ask());self.check(1);self.adapter.close();self.assertEqual(self.adapter.selected(NOW),(False,0))

    def test_default_install_boundary_does_not_revive_history(self):
        self.adapter.close();self.adapter=AttentionAdapter(self.root)
        self.write('a',meta(),ask('historic',age=1));self.check(0)
        self.write('a',ask('live',age=-1),append=True,mtime=NOW+1);self.check(1,NOW+1)

    def test_restart_restores_pending_and_original_boundary(self):
        cache=self.root/'attention-state.json'
        self.adapter.close();self.adapter=AttentionAdapter(self.root,state_path=cache,start_timestamp=NOW-10)
        self.write('a',meta(),ask(age=1));self.check(1)
        self.adapter.close();self.adapter=AttentionAdapter(self.root,state_path=cache,start_timestamp=NOW+100000)
        self.assertEqual(self.adapter.start_timestamp,NOW-10)
        self.check(1,NOW+100000)
        self.write('a',reply(age=-100001),append=True,mtime=NOW+100001);self.check(0,NOW+100001)
        self.adapter.close();self.adapter=AttentionAdapter(self.root,state_path=cache)
        self.write('duplicate',meta(),ask(age=1),mtime=NOW+100001);self.check(0,NOW+100001)

    def test_persistence_contains_no_question_or_answer_text(self):
        cache=self.root/'attention-state.json'
        self.adapter.close();self.adapter=AttentionAdapter(self.root,state_path=cache,start_timestamp=NOW-10)
        self.write('a',meta(),ask());self.check(1)
        content=cache.read_text();self.assertNotIn('Test question',content)
        self.assertEqual(cache.stat().st_mode & 0o777,0o600)
        self.write('a',reply(),append=True);self.check(0)
        content=cache.read_text();self.assertNotIn('answer',content);self.assertNotIn('Test question',content)
        self.assertFalse(list(self.root.glob('attention-state.json.*.tmp')))

    def test_exact_migration_seed_replays_reply_without_importing_other_history(self):
        self.adapter.close()
        self.adapter=AttentionAdapter(self.root,initial_pending=[dict(session_id='s',call_id='seed',index=0,timestamp=NOW-50,turn='t')])
        self.write('a',meta(),ask('seed',age=50),ask('unseeded',age=20),reply('seed',age=1))
        self.check(0)
        self.assertEqual(self.adapter.start_timestamp,NOW)

    def test_seed_remains_after_restart_and_old_stale_file(self):
        cache=self.root/'attention-state.json'
        self.adapter.close()
        self.adapter=AttentionAdapter(self.root,state_path=cache,initial_pending=[dict(session_id='s',call_id='seed',index=0,timestamp=NOW-5000,turn='t')])
        self.write('a',meta(),ask('seed',age=5000),mtime=NOW-5000);self.check(1)
        self.adapter.close();self.adapter=AttentionAdapter(self.root,state_path=cache)
        self.check(1,NOW+86400)

    def test_authoritative_reconciliation_scoped_to_chat(self):
        self.write('a',meta('s1'),ask('a'),ask('b'))
        self.write('b',meta('s2'),ask('a'));self.check(3)
        self.assertFalse(self.adapter.reconcile_open_questions('s1',[],now=NOW))
        self.check(3)
        self.assertTrue(self.adapter.reconcile_open_questions('s1',[json.dumps(['request_user_input_async','a',0])],authoritative=True,now=NOW))
        self.check(2)
        self.write('replay',meta('s1'),ask('b'));self.check(2)

    def test_malformed_authoritative_snapshot_does_not_clear(self):
        self.write('a',meta(),ask());self.check(1)
        with self.assertRaises(ValueError):self.adapter.reconcile_open_questions('s',['invalid'],authoritative=True,now=NOW)
        self.check(1)

    def test_explicit_close_scoped_to_chat_and_reopen_accepts_new_card(self):
        self.write('a',meta('s1'),ask('a'));self.write('b',meta('s2'),ask('b'));self.check(2)
        self.assertTrue(self.adapter.close_chat('s1',NOW));self.check(1)
        self.write('replay',meta('s1'),ask('a'));self.check(1)
        self.write('a',ask('c',age=-1),append=True,mtime=NOW+1);self.check(2,NOW+1)

    def test_explicit_cancel_persists_tombstone(self):
        cache=self.root/'attention-state.json';self.adapter.close()
        self.adapter=AttentionAdapter(self.root,state_path=cache,start_timestamp=NOW-10)
        self.write('a',meta(),ask());self.check(1)
        self.assertTrue(self.adapter.cancel_question('s',('a',0),NOW))
        self.adapter.close();self.adapter=AttentionAdapter(self.root,state_path=cache)
        self.check(0)

    def test_explicit_rejected_tool_result_clears_only_matching_card(self):
        self.write('a',meta(),ask('a'),ask('b'),record('response_item',{'type':'function_call_output','call_id':'a','output':'{"accepted":false}'}));self.check(1)
        self.assertEqual(set(self.adapter.pending),{('s','b',0)})

    def test_invalid_cache_is_not_overwritten(self):
        cache=self.root/'attention-state.json';cache.write_text('{broken')
        with self.assertRaises(ValueError):AttentionAdapter(self.root,state_path=cache)
        self.assertEqual(cache.read_text(),'{broken')

    def test_first_empty_poll_persists_boundary(self):
        cache=self.root/'attention-state.json';self.adapter.close()
        self.adapter=AttentionAdapter(self.root,state_path=cache);self.check(0)
        self.assertEqual(json.loads(cache.read_text())['start_timestamp'],NOW)
        self.adapter.close();self.adapter=AttentionAdapter(self.root,state_path=cache)
        self.write('a',meta(),ask('old',age=1));self.check(0,NOW+3600)

    def test_failed_atomic_replace_preserves_previous_cache(self):
        cache=self.root/'attention-state.json';self.adapter.close()
        self.adapter=AttentionAdapter(self.root,state_path=cache,start_timestamp=NOW-10)
        self.write('a',meta(),ask());self.check(1);original=cache.read_bytes()
        with patch('attention_state.os.replace',side_effect=OSError('test failure')):
            with self.assertRaises(OSError):self.adapter.cancel_question('s',('a',0),NOW)
        self.assertEqual(cache.read_bytes(),original)
        self.assertFalse(list(self.root.glob('attention-state.json.*.tmp')))
        self.adapter.poll(NOW)
        self.assertEqual(json.loads(cache.read_text())['pending'],[])

    def test_abort_and_closed_chat_tombstones_survive_restart(self):
        cache=self.root/'attention-state.json';self.adapter.close()
        self.adapter=AttentionAdapter(self.root,state_path=cache,start_timestamp=NOW-10)
        self.write('a',meta('s1'),ask('a'),record('event_msg',{'type':'turn_aborted','turn_id':'turn-a'}))
        self.write('b',meta('s2'),ask('b'));self.check(1)
        self.adapter.close_chat('s2',NOW);self.adapter.close()
        self.adapter=AttentionAdapter(self.root,state_path=cache)
        self.write('rep1',meta('s1'),ask('a'));self.write('rep2',meta('s2'),ask('b'));self.check(0)

    def test_escalated_tool_parameters_do_not_imply_human_approval(self):
        self.write('a',meta(),record('response_item',{'type':'function_call','call_id':'e','name':'exec_command',
            'arguments':json.dumps({'cmd':'true','sandbox_permissions':'require_escalated'})}));self.check(0)

    def test_unverified_sync_input_is_left_to_runtime_status_adapter(self):
        sync=ask();sync['payload']['name']='request_user_input'
        self.write('a',meta(),sync);self.check(0)

if __name__=='__main__':unittest.main()
