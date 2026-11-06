import unittest

from state_reducer import RolloutSnapshot as Rollout, RuntimeSnapshot as Runtime, reduce_state


NOW = 1_000.0


def task(thread="a", active=True, effort="high", age=0, **kwargs):
    return Rollout(thread, active, effort, NOW - age, **kwargs)


def live(thread="a", kind="active", flags=(), age=0, **kwargs):
    return Runtime(thread, kind, NOW - age, flags, **kwargs)


class StateReducerTests(unittest.TestCase):
    def reduce(self, rollouts=(), runtimes=(), questions=(), **kwargs):
        return reduce_state(rollouts, runtimes, questions, now=NOW, **kwargs)

    def test_only_task_blocked_on_approval_stops_and_lights(self):
        result = self.reduce([task()], [live(flags=("waitingOnApproval",))])
        self.assertEqual((result.motor_command, result.light, result.working_count), ("STOP", True, 0))
        self.assertEqual(result.waiting_threads, ("a",))
        self.assertEqual(result.degraded_threads, ())

    def test_only_task_blocked_on_input_stops_and_lights(self):
        result = self.reduce([task()], [live(flags=("waitingOnUserInput",))])
        self.assertEqual((result.motor_command, result.light), ("STOP", True))

    def test_async_question_and_continuing_work_rotate_and_light(self):
        result = self.reduce([task()], [live()], [("a", "call1", 0)])
        self.assertEqual((result.motor_command, result.light, result.waiting_threads), ("RUN HIGH", True, ()))

    def test_another_task_runs_while_highest_effort_task_waits(self):
        result = self.reduce(
            [task("a", effort="ultra"), task("b", effort="low"), task("c", effort="medium")],
            [live("a", flags=("waitingOnApproval",)), live("b"), live("c")])
        self.assertEqual((result.motor_command, result.selected_thread, result.light), ("RUN MEDIUM", "c", True))
        self.assertEqual(result.working_threads, ("b", "c"))

    def test_wait_resolves_without_changing_work_rule(self):
        result = self.reduce([task()], [live()])
        self.assertEqual((result.motor_command, result.light), ("RUN HIGH", False))

    def test_completed_reply_leaves_pending_async_card_lit(self):
        result = self.reduce([task(active=False)], [live(kind="idle")], [("a", "call1", 0)])
        self.assertEqual((result.motor_command, result.light), ("STOP", True))

    def test_all_idle_and_no_questions_stop_and_dark(self):
        result = self.reduce([task(active=False)], [live(kind="idle")])
        self.assertEqual((result.motor_command, result.light), ("STOP", False))

    def test_runtime_idle_overrides_unfinished_rollout(self):
        result = self.reduce([task()], [live(kind="idle", flags=None)])
        self.assertEqual((result.motor_command, result.degraded_threads), ("STOP", ()))

    def test_runtime_working_overrides_lagging_idle_rollout(self):
        result = self.reduce([task(active=False)], [live()])
        self.assertEqual(result.motor_command, "RUN HIGH")

    def test_multiple_sources_keep_light_until_all_resolve(self):
        result = self.reduce([task("a"), task("b", active=False)],
                             [live("a", flags=("waitingOnApproval", "waitingOnUserInput")), live("b", kind="idle")],
                             [("b", "call1", 0), ("b", "call1", 1), ("b", "call1", 0)])
        self.assertEqual((result.light, result.pending_question_count, result.waiting_threads), (True, 2, ("a",)))

    def test_missing_runtime_fails_quiet_by_default(self):
        result = self.reduce([task()])
        self.assertEqual((result.motor_command, result.light, result.degraded_threads), ("STOP", False, ("a",)))

    def test_missing_runtime_explicit_legacy_fallback_is_diagnosable(self):
        result = self.reduce([task()], fallback_policy="rollout")
        self.assertEqual((result.motor_command, result.light, result.degraded_threads), ("RUN HIGH", False, ("a",)))

    def test_unknown_or_missing_flags_never_mean_confirmed_work(self):
        for status in [None, {}, {"type": "active"}, {"type": "active", "activeFlags": "bad"},
                       {"type": "active", "activeFlags": ["newFlag"]},
                       {"type": "notLoaded"}, {"type": "systemError"}]:
            with self.subTest(status=status):
                runtime = Runtime.from_status("a", status, NOW)
                result = self.reduce([task(active=False)], [runtime])
                self.assertEqual((result.motor_command, result.light, result.degraded_threads), ("STOP", False, ("a",)))

    def test_unknown_runtime_can_fall_back_to_known_active_rollout(self):
        result = self.reduce([task()], [live(kind="notLoaded")], fallback_policy="rollout")
        self.assertEqual((result.motor_command, result.degraded_threads), ("RUN HIGH", ("a",)))

    def test_stale_runtime_wait_does_not_latch_forever(self):
        result = self.reduce([task(active=False)], [live(flags=("waitingOnApproval",), age=5)])
        self.assertEqual((result.motor_command, result.light, result.degraded_threads), ("STOP", False, ("a",)))

    def test_stale_runtime_wait_cannot_revive_motion_by_default(self):
        result = self.reduce([task()], [live(flags=("waitingOnApproval",), age=6)])
        self.assertEqual((result.motor_command, result.light), ("STOP", False))

    def test_stale_runtime_explicit_legacy_fallback_can_run(self):
        result = self.reduce([task()], [live(flags=("waitingOnApproval",), age=6)], fallback_policy="rollout")
        self.assertEqual((result.motor_command, result.light), ("RUN HIGH", False))

    def test_hold_wait_does_not_restart_blocked_thread_or_expire_light(self):
        result = self.reduce([task()], [live(flags=("waitingOnApproval",), age=3_600)], fallback_policy="hold_wait")
        self.assertEqual((result.motor_command, result.light, result.waiting_threads), ("STOP", True, ("a",)))
        self.assertEqual(result.sources, (("a", "fallback:held_wait"),))

    def test_hold_wait_allows_other_known_work_to_continue(self):
        result = self.reduce([task("a", effort="ultra"), task("b", effort="low")],
                             [live("a", flags=("waitingOnApproval",), age=3_600), live("b")],
                             fallback_policy="hold_wait")
        self.assertEqual((result.motor_command, result.light, result.selected_thread), ("RUN LOW", True, "b"))

    def test_hold_wait_resolves_with_new_fresh_runtime(self):
        result = self.reduce([task()], [live()], fallback_policy="hold_wait")
        self.assertEqual((result.motor_command, result.light), ("RUN HIGH", False))

    def test_unknown_fallback_policy_rejected(self):
        with self.assertRaises(ValueError):
            self.reduce(fallback_policy="guess")

    def test_stale_rollout_cannot_keep_motor_running(self):
        result = self.reduce([task(age=600)], fallback_policy="rollout")
        self.assertEqual(result.motor_command, "STOP")

    def test_live_runtime_can_keep_long_task_working(self):
        result = self.reduce([task(age=700)], [live()])
        self.assertEqual(result.motor_command, "RUN HIGH")

    def test_future_runtime_not_accepted(self):
        result = self.reduce([task(active=False)], [live(age=-3)])
        self.assertEqual((result.motor_command, result.degraded_threads), ("STOP", ("a",)))

    def test_two_seconds_clock_skew_is_tolerated(self):
        result = self.reduce([task()], [live(age=-2, flags=("waitingOnApproval",))])
        self.assertEqual((result.motor_command, result.light), ("STOP", True))

    def test_root_metadata_required_for_runtime_only_chat(self):
        ignored = self.reduce([], [live()])
        known = self.reduce([], [live(is_root=True)])
        self.assertEqual((ignored.motor_command, known.motor_command), ("STOP", "RUN MEDIUM"))

    def test_subagents_excluded(self):
        result = self.reduce([task(is_root=False)], [live(flags=("waitingOnApproval",))])
        self.assertEqual((result.motor_command, result.light), ("STOP", False))

    def test_duplicate_rollout_chat_counted_once_newest_wins(self):
        result = self.reduce([task(age=1), task(active=False)], [], [("a", "call1", 0)])
        self.assertEqual((result.motor_command, result.working_count, result.light), ("STOP", 0, True))

    def test_duplicate_runtime_newest_wins(self):
        result = self.reduce([task()], [live(flags=("waitingOnApproval",), age=1), live()])
        self.assertEqual((result.motor_command, result.light), ("RUN HIGH", False))

    def test_unknown_effort_retains_previous_bridge_default(self):
        result = self.reduce([task(effort="mystery")], [live()])
        self.assertEqual(result.motor_command, "RUN MEDIUM")

    def test_speed_mapping_keeps_existing_tiers(self):
        for effort, speed in [("none", "LOW"), ("minimal", "LOW"), ("low", "LOW"),
                              ("medium", "MEDIUM"), ("HIGH", "HIGH"), ("xhigh", "XHIGH"),
                              ("max", "ULTRA"), ("ultra", "ULTRA")]:
            with self.subTest(effort=effort):
                self.assertEqual(self.reduce([task(effort=effort)], [live()]).motor_command, "RUN " + speed)

    def test_speed_tie_prefers_latest_task_then_stable_id(self):
        result = self.reduce([task("a", started_at=2), task("b", started_at=3)], [live("a"), live("b")])
        self.assertEqual(result.selected_thread, "b")


if __name__ == "__main__":
    unittest.main()
