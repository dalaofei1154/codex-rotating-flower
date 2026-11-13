import importlib.util
import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPT = Path(__file__).with_name("global_bridge.py")
sys.path.insert(0, str(SCRIPT.parent))
spec = importlib.util.spec_from_file_location("global_bridge", SCRIPT)
bridge = importlib.util.module_from_spec(spec)
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


class FakeMotorSerial:
    def __init__(self, path):
        self.path = path
        self.port = None
        self.last_probe_at = -float("inf")
        self.commands = []
        self.available = True
        self.probes = 0
        self.closed = False

    @property
    def connected(self):
        return self.port is not None

    def send(self, command):
        if self.port is None:
            self.probes += 1
            self.last_probe_at = time.monotonic()
            if not self.available:
                return False
            self.port = object()
        self.commands.append(command)
        return True

    def close(self):
        self.closed = True
        self.port = None


class MotorGroupTests(unittest.TestCase):
    def setUp(self):
        self.serial_patch = patch.object(bridge, "MotorSerial", FakeMotorSerial)
        self.serial_patch.start()
        self.addCleanup(self.serial_patch.stop)
        self.group = bridge.MotorGroup()
        self.addCleanup(self.group.close)

    def test_two_flowers_receive_speed_changes_and_stop(self):
        with patch.object(bridge, "serial_candidates", return_value=["one", "two"]):
            self.group.send("RUN LOW")
            self.group.send("RUN LOW")
            self.group.send("RUN ULTRA")
            self.group.send("STOP")
        for motor in self.group.motors.values():
            self.assertEqual(motor.commands[-3:], ["RUN LOW", "RUN ULTRA", "STOP"])
            self.assertEqual(motor.probes, 1)

    def test_hotplug_gets_current_command_and_unplug_keeps_other_running(self):
        with patch.object(bridge, "serial_candidates", return_value=["one"]):
            self.group.send("RUN HIGH")
        first = self.group.motors["one"]
        with patch.object(bridge, "serial_candidates", return_value=["one", "two"]):
            self.group.send("RUN ULTRA")
        second = self.group.motors["two"]
        self.assertEqual(second.commands, ["RUN ULTRA"])
        with patch.object(bridge, "serial_candidates", return_value=["two"]):
            self.group.send("RUN LOW")
        self.assertTrue(first.closed)
        self.assertEqual(second.commands[-1], "RUN LOW")
        self.assertNotIn("one", self.group.motors)

    def test_unresponsive_ports_do_not_block_heartbeats_or_later_flowers(self):
        first = FakeMotorSerial("one")
        first.port = object()
        bad = FakeMotorSerial("bad")
        bad.available = False
        self.group.motors = {"one": first, "bad": bad}
        with patch.object(bridge, "serial_candidates", return_value=["one", "bad", "two"]):
            self.group.send("RUN HIGH")
            self.assertEqual(first.commands, ["RUN HIGH"])
            self.assertIsNone(self.group.motors["two"].port)
            self.group.send("RUN LOW")
        self.assertEqual(first.commands, ["RUN HIGH", "RUN LOW"])
        self.assertEqual(self.group.motors["two"].commands, ["RUN LOW"])
        self.assertEqual(bad.probes, 1)

    def test_explicit_port_only_controls_requested_flower(self):
        self.group = bridge.MotorGroup("two")
        with patch.object(bridge, "serial_candidates") as candidates:
            self.group.send("RUN MEDIUM")
        candidates.assert_not_called()
        self.assertEqual(list(self.group.motors), ["two"])

    def test_close_stops_all_connected_flowers_without_opening_pending_port(self):
        with patch.object(bridge, "serial_candidates", return_value=["one", "two", "three"]):
            self.group.send("RUN HIGH")
            self.group.send("RUN HIGH")
        motors = list(self.group.motors.values())
        self.group.close()
        for motor in motors[:2]:
            self.assertEqual(motor.commands[-1], "STOP")
            self.assertTrue(motor.closed)
        self.assertEqual(motors[2].probes, 0)
        self.assertFalse(self.group.motors)


if __name__ == "__main__":
    unittest.main()
