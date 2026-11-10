import importlib.util
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))

spec = importlib.util.spec_from_file_location("process_probe", HERE / "process_probe.py")
process_probe = importlib.util.module_from_spec(spec)
sys.modules["process_probe"] = process_probe
spec.loader.exec_module(process_probe)


class ProcessProbeTests(unittest.TestCase):
    def test_current_process_is_alive(self):
        self.assertTrue(process_probe.process_alive(os.getpid()))

    def test_unused_pid_is_not_alive(self):
        # A very high PID is not in use on any supported platform.
        self.assertFalse(process_probe.process_alive(0x7FFFFFF0))

    def test_windows_backend_does_not_use_os_kill(self):
        """os.kill(pid, 0) terminates on Windows, so the backend must differ."""
        with patch.object(process_probe.sys, "platform", "win32"), \
             patch.object(process_probe, "_windows_process_alive",
                          return_value=True) as backend, \
             patch.object(process_probe.os, "kill") as kill:
            self.assertTrue(process_probe.process_alive(4242))
            backend.assert_called_once_with(4242)
            kill.assert_not_called()

    def test_posix_backend_propagates_permission_error(self):
        with patch.object(process_probe.sys, "platform", "darwin"), \
             patch.object(process_probe.os, "kill", side_effect=PermissionError):
            with self.assertRaises(PermissionError):
                process_probe.process_alive(4242)

    def test_posix_backend_reports_missing_process(self):
        with patch.object(process_probe.sys, "platform", "darwin"), \
             patch.object(process_probe.os, "kill", side_effect=ProcessLookupError):
            self.assertFalse(process_probe.process_alive(4242))


if __name__ == "__main__":
    unittest.main()
