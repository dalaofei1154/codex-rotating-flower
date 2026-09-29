import importlib.util
import json
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPT = Path(__file__).with_name("global_bridge.py")
spec = importlib.util.spec_from_file_location("global_bridge", SCRIPT)
bridge = importlib.util.module_from_spec(spec)
import sys
sys.modules[spec.name] = bridge
spec.loader.exec_module(bridge)


def write_records(path, records):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("ab") as file:
        for record in records:
            file.write(json.dumps(record, separators=(",", ":")).encode() + b"\n")


def meta(session_id, source="user", parent=None):
    return {"type": "session_meta", "payload": {
        "id": session_id, "source": "vscode", "thread_source": source,
        "parent_thread_id": parent}}


def event(kind, turn_id=None, effort=None):
    payload = {"type": kind}
    if turn_id:
        payload["turn_id"] = turn_id
    if kind == "thread_settings_applied":
        payload["thread_settings"] = {"reasoning_effort": effort}
    return {"type": "event_msg", "payload": payload}


def context(turn_id, effort):
    return {"type": "turn_context", "payload": {"turn_id": turn_id, "effort": effort}}


class GlobalBridgeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "sessions"
        self.root.mkdir()
        self.adapter = bridge.CodexRolloutAdapter(self.root, stale_seconds=600)

    def tearDown(self):
        self.adapter.close()
        self.temp.cleanup()

    def path(self, session_id):
        return self.root / "2026" / "09" / "23" / f"rollout-{session_id}.jsonl"

    def test_new_window_and_highest_active_effort(self):
        first = self.path("first")
        second = self.path("second")
        write_records(first, [meta("first"), event("task_started", "a"), context("a", "low")])
        self.adapter.poll()
        self.assertEqual(self.adapter.selected(), ("RUN LOW", "first", 1))

        # A different project/window appears after the bridge has already started.
        write_records(second, [meta("second"), event("task_started", "b"),
                               context("b", "xhigh")])
        self.adapter.poll()
        self.assertEqual(self.adapter.selected(), ("RUN XHIGH", "second", 2))

        write_records(second, [event("task_complete", "b")])
        self.adapter.poll()
        self.assertEqual(self.adapter.selected(), ("RUN LOW", "first", 1))
        write_records(first, [event("task_complete", "a")])
        self.adapter.poll()
        self.assertEqual(self.adapter.selected(), ("STOP", None, 0))

    def test_interrupt_and_subagent_copied_history(self):
        root = self.path("main")
        child = self.path("main_child")
        write_records(root, [meta("main"), event("task_started", "a"),
                             context("a", "medium")])
        write_records(child, [meta("child", source="subagent", parent="main"),
                              meta("main"), event("task_started", "b"),
                              context("b", "ultra")])
        self.adapter.poll()
        self.assertEqual(self.adapter.selected(), ("RUN MEDIUM", "main", 1))
        write_records(root, [event("turn_aborted", "a")])
        self.adapter.poll()
        self.assertEqual(self.adapter.selected(), ("STOP", None, 0))

    def test_new_turn_context_updates_effort_and_stale_active_expires(self):
        path = self.path("one")
        write_records(path, [meta("one"), event("task_started", "a"),
                             context("a", "medium"), event("task_complete", "a"),
                             event("task_started", "b"), context("b", "ultra")])
        self.adapter.poll()
        self.assertEqual(self.adapter.selected()[0], "RUN ULTRA")
        self.assertEqual(self.adapter.selected(time.time() + 601), ("STOP", None, 0))

    def test_context_before_start_and_serial_path_change(self):
        path = self.path("one")
        write_records(path, [meta("one"), context("a", "high"),
                             event("task_started", "a")])
        self.adapter.poll()
        self.assertEqual(self.adapter.selected()[0], "RUN HIGH")

        old = Path(self.temp.name) / "old-port"
        new = Path(self.temp.name) / "new-port"
        old.touch()
        new.touch()
        motor = bridge.MotorSerial()
        read_fd, write_fd = os.pipe()
        try:
            def fake_probe(candidate):
                motor.fd = os.dup(read_fd)
                motor.path = candidate
                return True

            with patch.object(bridge, "serial_candidates", side_effect=[[str(old)], [str(new)]]), \
                 patch.object(motor, "_probe", side_effect=fake_probe):
                self.assertTrue(motor.connect())
                self.assertEqual(motor.path, str(old))
                old.unlink()
                motor.last_probe_at = -float("inf")
                self.assertTrue(motor.connect())
                self.assertEqual(motor.path, str(new))
        finally:
            motor.close()
            os.close(read_fd)
            os.close(write_fd)

    def test_deleted_active_rollout_stops_motor(self):
        path = self.path("removed")
        write_records(path, [meta("removed"), event("task_started", "a"),
                             context("a", "high")])
        self.adapter.poll()
        self.assertEqual(self.adapter.selected()[0], "RUN HIGH")

        path.unlink()
        self.assertTrue(self.adapter.poll())
        self.assertEqual(self.adapter.selected(), ("STOP", None, 0))


if __name__ == "__main__":
    unittest.main()
