import unittest
import test_attention_state as fixtures
from test_attention_state import NOW, meta, ask, reply, record


def direct(text='继续', kind='user.text', image=False):
    return record('response_item',{'type':'message','role':'user',
        'content':[{'type':'input_image','image_url':'test'}] if image else [{'type':'input_text','text':text}],
        'internal_chat_message_metadata_passthrough':{'content_item_kinds':[kind]}})


class DirectReplyTests(unittest.TestCase):
    setUp = fixtures.AttentionTests.setUp
    tearDown = fixtures.AttentionTests.tearDown
    write = fixtures.AttentionTests.write
    check = fixtures.AttentionTests.check
    def test_direct_text_clears_prior_questions_only_in_same_chat(self):
        self.write('a',meta('s1'),ask('old',age=3),ask('another',age=2),direct(),ask('new',age=-1))
        self.write('b',meta('s2'),ask('other',age=3))
        self.check(2,NOW+1)
        self.assertEqual(set(self.adapter.pending),{('s1','new',0),('s2','other',0)})

    def test_image_acknowledges(self):
        self.write('a',meta(),ask(age=1),direct(kind='user.image',image=True));self.check(0)

    def test_injected_context_never_acknowledges(self):
        self.write('a',meta(),ask(age=1),direct('<environment_context/>',kind='environments.environment_context'),
                   direct('page',kind='additional_content.codex_apps_open_page'));self.check(1)

    def test_card_submission_still_matches_one_id(self):
        r=reply('a');r['payload']['internal_chat_message_metadata_passthrough']={'content_item_kinds':['user.text']}
        self.write('a',meta(),ask('a',age=2),ask('b',age=1),r);self.check(1)

    def test_ack_persists_across_restart_and_duplicate_history(self):
        from attention_state import AttentionAdapter
        cache=self.root/'cache.json'
        self.adapter.close();self.adapter=AttentionAdapter(self.root,state_path=cache,start_timestamp=NOW-100)
        self.write('a',meta(),ask(age=2),direct());self.check(0)
        self.adapter.close();self.adapter=AttentionAdapter(self.root,state_path=cache)
        self.write('b',meta(),ask(age=2));self.check(0)


if __name__=='__main__':unittest.main()
