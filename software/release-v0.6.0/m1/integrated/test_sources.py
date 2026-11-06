import unittest
from integrated_bridge import combine_sources, RecoveringSource
from unittest.mock import Mock


def source(motor='STOP', light=False, healthy=True):
    return dict(motor=motor, light=light, healthy=healthy)


class SourceFusionTests(unittest.TestCase):
    def test_codex_disconnected_does_not_stop_workbuddy(self):
        self.assertEqual(combine_sources({'codex':source(healthy=False),
                                          'workbuddy':source('RUN HIGH')}),('RUN HIGH',False))

    def test_workbuddy_wait_does_not_stop_other_work(self):
        self.assertEqual(combine_sources({'codex':source('RUN ULTRA'),
                                          'workbuddy':source(light=True)}),('RUN ULTRA',True))

    def test_failed_source_cannot_leave_stale_light_or_speed(self):
        self.assertEqual(combine_sources({'codex':source('RUN ULTRA',True,False),
                                          'workbuddy':source('RUN LOW')}),('RUN LOW',False))

    def test_highest_active_speed_and_any_wait(self):
        self.assertEqual(combine_sources({'codex':source('RUN MEDIUM',True),
                                          'workbuddy':source('RUN HIGH')}),('RUN HIGH',True))

    def test_one_source_initialization_error_is_isolated_and_retried(self):
        recovered=Mock()
        recovered.poll.return_value=source('RUN HIGH')
        factory=Mock(side_effect=[ValueError('invalid cache'),recovered])
        wrapper=RecoveringSource(factory)
        broken=wrapper.poll(100)
        self.assertFalse(broken['healthy'])
        self.assertEqual(combine_sources({'codex':broken,'workbuddy':source('RUN LOW')}),('RUN LOW',False))
        wrapper.poll(101)
        self.assertEqual(factory.call_count,1)
        self.assertEqual(wrapper.poll(106)['motor'],'RUN HIGH')
        wrapper.close();recovered.close.assert_called_once()

    def test_disabled_sources_are_absent(self):
        self.assertEqual(combine_sources({'workbuddy':source()}),('STOP',False))


if __name__=='__main__':unittest.main()
