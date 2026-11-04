"""Metadata/state integrity tests; no sockets, desktop mutation or hardware."""
import threading
import unittest
from unittest.mock import patch as mock_patch

from runtime_feed import DesktopRuntimeFeed, apply_metadata_patches, normalize_metadata
from state_reducer import RuntimeSnapshot, reduce_state


A = "11111111-1111-4111-8111-111111111111"
B = "22222222-2222-4222-8222-222222222222"


def metadata(tid=A, **extra):
    return {"id": tid, "hostId": "local", "parentThreadId": None,
            "threadRuntimeStatus": {"type": "active", "activeFlags": []},
            "requests": [], **extra}


def observer():
    # Construct only the receiver state. Starting its worker would open IPC.
    feed = DesktopRuntimeFeed.__new__(DesktopRuntimeFeed)
    feed._lock = threading.Lock()
    feed._threads = {}
    feed._states = {}
    feed._revisions = {}
    feed._owners = {A: "owner-a", B: "owner-b"}
    feed._pending = {}
    feed._client = "observer-test"
    feed._last_message_at = None
    feed._connected = True
    feed._error = None
    feed.sent = []
    feed.follows = []
    feed._send = feed.sent.append
    feed._follow = lambda tid, owner, following: feed.follows.append((tid, owner, following))
    return feed


def snapshot(tid=A, **extra):
    return {"type": "broadcast", "method": "thread-stream-state-changed",
            "sourceClientId": "owner-a" if tid == A else "owner-b",
            "params": {"hostId": "local", "conversationId": tid,
                       "change": {"type": "snapshot", "revision": 1,
                                  "conversationState": metadata(tid, **extra)}}}


def patch(tid=A, patches=(), base=1, revision=2):
    return {"type": "broadcast", "method": "thread-stream-state-changed",
            "sourceClientId": "owner-a" if tid == A else "owner-b",
            "params": {"hostId": "local", "conversationId": tid,
                       "change": {"type": "patches", "baseRevision": base,
                                  "revision": revision, "patches": list(patches)}}}


class NormalizeTests(unittest.TestCase):
    def test_known_active_flags_are_preserved(self):
        result = normalize_metadata(A, metadata(threadRuntimeStatus={
            "type": "active", "activeFlags": ["waitingOnApproval", "waitingOnUserInput"]}), 100)
        self.assertEqual(result["runtime_status"], {"type": "active", "activeFlags": ["waitingOnApproval", "waitingOnUserInput"]})

    def test_missing_or_unknown_flags_never_become_work(self):
        for status in [{"type": "active"}, {"type": "active", "activeFlags": None},
                       {"type": "active", "activeFlags": "unknown"},
                       {"type": "active", "activeFlags": ["futureFlag"]},
                       {"type": "active", "activeFlags": [2]}]:
            with self.subTest(status=status):
                result = normalize_metadata(A, metadata(threadRuntimeStatus=status), 100)
                runtime = RuntimeSnapshot.from_status(A, result["runtime_status"], 100, is_root=True)
                state = reduce_state([], [runtime], now=100)
                self.assertEqual(state.motor_command, "STOP")
                self.assertIn(A, state.degraded_threads)

    def test_mixed_known_and_unknown_flag_stays_unknown(self):
        result = normalize_metadata(A, metadata(threadRuntimeStatus={
            "type": "active", "activeFlags": ["waitingOnApproval", "futureFlag"]}), 100)
        runtime = RuntimeSnapshot.from_status(A, result["runtime_status"], 100, is_root=True)
        state = reduce_state([], [runtime], now=100)
        self.assertIn(A, state.degraded_threads)

    def test_async_request_does_not_change_active_flags(self):
        result = normalize_metadata(A, metadata(requests=[{
            "id": "question-card", "type": "async-user-input", "params": {"threadId": A}}]), 100)
        self.assertEqual(result["runtime_status"], {"type": "active", "activeFlags": []})

    def test_request_projection_retains_only_identity_metadata(self):
        result = normalize_metadata(A, metadata(requests=[{
            "id": 12, "method": "item/commandExecution/requestApproval",
            "command": "PRIVATE-COMMAND", "prompt": "PRIVATE-PROMPT",
            "params": {"threadId": A, "turnId": "turn-a", "itemId": "item-a",
                       "questions": ["PRIVATE-QUESTION"], "command": "PRIVATE-NESTED"}}]), 100)
        text = repr(result)
        self.assertNotIn("PRIVATE", text)
        self.assertEqual(result["requests"][0]["threadId"], A)
        self.assertEqual(result["requests"][0]["id"], 12)

    def test_idle_is_not_an_async_question_resolution(self):
        result = normalize_metadata(A, metadata(threadRuntimeStatus={"type": "idle"},
                                               requests=[{"id": "still-pending"}]), 100)
        self.assertEqual(result["runtime_status"], {"type": "idle"})
        self.assertEqual(result["requests"], [{"id": "still-pending"}])


class ReceiverTests(unittest.TestCase):
    def test_snapshot_uses_thread_id_not_shared_session_tree_id(self):
        feed = observer()
        feed._handle(snapshot(sessionId=B), {A, B})
        self.assertEqual(set(feed._threads), {A})
        self.assertEqual(feed._threads[A]["thread_id"], A)

    def test_wrong_thread_in_snapshot_is_rejected(self):
        feed = observer()
        message = snapshot()
        message["params"]["change"]["conversationState"]["id"] = B
        feed._handle(message, {A, B})
        self.assertEqual(feed._threads, {})

    def test_remote_host_cannot_drive_local_flower(self):
        feed = observer()
        message = snapshot()
        message["params"]["hostId"] = "remote-host"
        feed._handle(message, {A})
        self.assertEqual(feed._threads, {})

    def test_wrong_owner_broadcast_ignored(self):
        feed = observer()
        message = snapshot()
        message["sourceClientId"] = "unrelated-owner"
        feed._handle(message, {A})
        self.assertEqual(feed._threads, {})

    def test_child_chat_does_not_become_root(self):
        feed = observer()
        feed._handle(snapshot(parentThreadId=B), {A})
        self.assertEqual(feed._threads, {})

    def test_two_chat_states_do_not_overwrite_each_other(self):
        feed = observer()
        feed._handle(snapshot(threadRuntimeStatus={"type": "active", "activeFlags": ["waitingOnApproval"]}), {A, B})
        feed._handle(snapshot(B), {A, B})
        self.assertEqual(feed._threads[A]["runtime_status"]["activeFlags"], ["waitingOnApproval"])
        self.assertEqual(feed._threads[B]["runtime_status"]["activeFlags"], [])

    def test_matching_patch_updates_wait_and_request_independently(self):
        feed = observer()
        feed._handle(snapshot(), {A})
        feed._handle(patch(patches=[
            {"op": "replace", "path": ["threadRuntimeStatus"], "value": {"type": "active", "activeFlags": ["waitingOnApproval"]}},
            {"op": "add", "path": ["requests", 0], "value": {"id": "approval-1"}},
        ]), {A})
        self.assertEqual(feed._threads[A]["runtime_status"]["activeFlags"], ["waitingOnApproval"])
        self.assertEqual(feed._threads[A]["requests"], [{"id": "approval-1"}])

    def test_missed_patch_revision_requests_full_snapshot(self):
        feed = observer()
        feed._handle(snapshot(threadRuntimeStatus={"type": "active", "activeFlags": ["waitingOnApproval"]}), {A})
        observed_at = feed._threads[A]["observed_at"]
        feed._handle(patch(base=100, revision=101, patches=[
            {"op": "replace", "path": ["threadRuntimeStatus"], "value": {"type": "active", "activeFlags": []}}]), {A})
        self.assertEqual(feed._threads[A]["runtime_status"]["activeFlags"], ["waitingOnApproval"])
        self.assertEqual(feed._threads[A]["observed_at"], observed_at)
        self.assertEqual(feed.follows, [(A, "owner-a", False), (A, "owner-a", True)])

    def test_patch_cannot_change_chat_identity(self):
        feed = observer()
        feed._handle(snapshot(), {A})
        observed_at = feed._threads[A]["observed_at"]
        feed._handle(patch(patches=[{"op": "replace", "path": ["id"], "value": B}]), {A, B})
        self.assertEqual(feed._threads[A]["observed_at"], observed_at)

    def test_patch_cannot_change_to_remote_host(self):
        feed = observer()
        feed._handle(snapshot(), {A})
        observed_at = feed._threads[A]["observed_at"]
        feed._handle(patch(patches=[{"op": "replace", "path": ["hostId"], "value": "remote-host"}]), {A})
        self.assertEqual(feed._threads[A]["observed_at"], observed_at)

    def test_owner_loss_does_not_refresh_last_good_wait_snapshot(self):
        feed = observer()
        feed._handle(snapshot(threadRuntimeStatus={"type": "active", "activeFlags": ["waitingOnApproval"]}), {A})
        observed_at = feed._threads[A]["observed_at"]
        feed._pending["request-1"] = ("thread-owner-discovery", A)
        feed._handle({"type": "response", "requestId": "request-1", "resultType": "error"}, {A})
        self.assertFalse(feed._threads[A]["owner_found"])
        self.assertEqual(feed._threads[A]["observed_at"], observed_at)
        # A delayed old-owner broadcast is no longer accepted as current.
        feed._handle(patch(patches=[{"op": "replace", "path": ["threadRuntimeStatus"],
                                    "value": {"type": "active", "activeFlags": []}}]), {A})
        self.assertEqual(feed._threads[A]["observed_at"], observed_at)

    def test_same_owner_heartbeat_revalidates_intact_subscription(self):
        feed = observer()
        with mock_patch("runtime_feed.time.time", return_value=100):
            feed._handle(snapshot(threadRuntimeStatus={"type": "active", "activeFlags": ["waitingOnApproval"]}), {A})
        feed._pending["request-1"] = ("thread-owner-discovery", A)
        with mock_patch("runtime_feed.time.time", return_value=110):
            feed._handle({"type": "response", "requestId": "request-1", "resultType": "success",
                          "handledByClientId": "owner-a"}, {A})
        self.assertEqual(feed._threads[A]["observed_at"], 110)
        self.assertEqual(feed._threads[A]["runtime_status"]["activeFlags"], ["waitingOnApproval"])
        self.assertEqual(feed.follows, [])

    def test_revision_gap_prevents_heartbeat_revalidating_stale_state(self):
        feed = observer()
        with mock_patch("runtime_feed.time.time", return_value=100):
            feed._handle(snapshot(), {A})
        feed._handle(patch(base=99, revision=100, patches=[]), {A})
        feed._pending["request-1"] = ("thread-owner-discovery", A)
        with mock_patch("runtime_feed.time.time", return_value=110):
            feed._handle({"type": "response", "requestId": "request-1", "resultType": "success",
                          "handledByClientId": "owner-a"}, {A})
        self.assertEqual(feed._threads[A]["observed_at"], 100)

    def test_new_owner_needs_snapshot_before_any_heartbeat_revalidation(self):
        feed = observer()
        with mock_patch("runtime_feed.time.time", return_value=100):
            feed._handle(snapshot(), {A})
        for index in range(2):
            request_id = "request-" + str(index)
            feed._pending[request_id] = ("thread-owner-discovery", A)
            with mock_patch("runtime_feed.time.time", return_value=110 + index):
                feed._handle({"type": "response", "requestId": request_id, "resultType": "success",
                              "handledByClientId": "new-owner"}, {A})
        self.assertEqual(feed._threads[A]["observed_at"], 100)

    def test_unrelated_client_cannot_archive_target(self):
        feed = observer()
        feed._handle(snapshot(), {A})
        feed._handle({"type": "broadcast", "method": "thread-archived",
                      "sourceClientId": "unrelated-owner",
                      "params": {"hostId": "local", "conversationId": A}}, {A})
        self.assertFalse(feed._threads[A]["archived"])

    def test_delayed_patch_cannot_unarchive_target(self):
        feed = observer()
        feed._handle(snapshot(), {A})
        feed._handle({"type": "broadcast", "method": "thread-archived",
                      "sourceClientId": "owner-a",
                      "params": {"hostId": "local", "conversationId": A}}, {A})
        self.assertTrue(feed._threads[A]["archived"])
        feed._handle(patch(patches=[{"op": "replace", "path": ["latestReasoningEffort"],
                                    "value": "ultra"}]), {A})
        self.assertTrue(feed._threads[A]["archived"])

    def test_snapshot_without_revision_cannot_authorize_later_patch(self):
        feed = observer()
        message = snapshot()
        del message["params"]["change"]["revision"]
        try:
            feed._handle(message, {A})
            feed._handle(patch(base=None, patches=[{"op": "replace", "path": ["latestReasoningEffort"],
                                                   "value": "ultra"}]), {A})
        except (ValueError, TypeError):
            pass  # Invalid frames may force transport reconnect instead.
        self.assertNotEqual(feed._threads.get(A, {}).get("latest_reasoning_effort"), "ultra")

    def test_null_requests_not_treated_as_authoritative_empty_list(self):
        feed = observer()
        feed._handle(snapshot(requests=[{"id": "still-pending"}]), {A})
        observed_at = feed._threads[A]["observed_at"]
        try:
            feed._handle(patch(patches=[{"op": "replace", "path": ["requests"], "value": None}]), {A})
        except (ValueError, TypeError):
            pass
        self.assertEqual(feed._threads[A]["observed_at"], observed_at)
        self.assertEqual(feed._threads[A]["requests"], [{"id": "still-pending"}])


class PatchTests(unittest.TestCase):
    def test_unwatched_message_content_is_not_copied(self):
        result = apply_metadata_patches(metadata(), [{"op": "add", "path": ["turns"], "value": ["PRIVATE"]}])
        self.assertNotIn("turns", result)
        self.assertNotIn("PRIVATE", repr(result))

    def test_request_remove_and_status_replace_are_independent(self):
        original = metadata(requests=[{"id": "one"}, {"id": "two"}])
        result = apply_metadata_patches(original, [{"op": "remove", "path": ["requests", 0]}])
        self.assertEqual(result["requests"], [{"id": "two"}])
        self.assertEqual(original["requests"], [{"id": "one"}, {"id": "two"}])
        self.assertEqual(result["threadRuntimeStatus"], original["threadRuntimeStatus"])


if __name__ == "__main__":
    unittest.main()
