import importlib.util
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))


def load(name):
    spec = importlib.util.spec_from_file_location(name, HERE / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


serial_link = load("serial_link")
process_lock = load("process_lock")


class DevicePathTests(unittest.TestCase):
    def test_windows_device_path_prefix_is_added_once(self):
        self.assertEqual(serial_link.windows_device_path("COM3"), "\\\\.\\COM3")
        self.assertEqual(serial_link.windows_device_path("\\\\.\\COM12"), "\\\\.\\COM12")

    def test_port_sort_puts_com2_before_com10(self):
        ports = ["COM10", "COM2", "COM1"]
        self.assertEqual(sorted(ports, key=serial_link._port_sort_key),
                         ["COM1", "COM2", "COM10"])


class PortPresenceTests(unittest.TestCase):
    def test_existing_path_is_present(self):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "device")
            Path(path).touch()
            self.assertTrue(serial_link.port_still_present(path))

    def test_missing_posix_path_is_not_present(self):
        with tempfile.TemporaryDirectory() as folder:
            missing = os.path.join(folder, "missing")
            with patch.object(serial_link.sys, "platform", "linux"):
                self.assertFalse(serial_link.port_still_present(missing))


class ProcessLockTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.path = Path(self.folder.name) / "bridge.lock"

    def tearDown(self):
        self.folder.cleanup()

    def test_lock_path_is_per_user_and_filesystem_safe(self):
        path = process_lock.singleton_path("codex-motor-bridge")
        name = path.name
        self.assertIn("codex-motor-bridge", name)
        self.assertTrue(name.endswith(".lock"))
        self.assertNotIn("\\", name)
        self.assertNotIn("/", name)

    def test_second_acquire_fails_until_the_first_is_released(self):
        first = process_lock.acquire(self.path)
        self.assertIsNotNone(first)
        try:
            self.assertIsNone(process_lock.acquire(self.path))
        finally:
            first.close()
        second = process_lock.acquire(self.path)
        self.assertIsNotNone(second)
        second.close()


class SerialPortSelectionTests(unittest.TestCase):
    def test_open_port_picks_the_windows_implementation(self):
        with patch.object(serial_link.sys, "platform", "win32"), \
             patch.object(serial_link, "WindowsSerialPort") as windows_port:
            serial_link.open_port("COM7")
            windows_port.assert_called_once_with("COM7", serial_link.DEFAULT_BAUDRATE)

    def test_open_port_picks_the_posix_implementation(self):
        with patch.object(serial_link.sys, "platform", "darwin"), \
             patch.object(serial_link, "PosixSerialPort") as posix_port:
            serial_link.open_port("/dev/cu.usbmodem101")
            posix_port.assert_called_once_with("/dev/cu.usbmodem101",
                                               serial_link.DEFAULT_BAUDRATE)


class WindowsInstallerTests(unittest.TestCase):
    def setUp(self):
        sys.path.insert(0, str(HERE))
        import install_windows
        self.installer = install_windows
        self.folder = tempfile.TemporaryDirectory()
        self.support = Path(self.folder.name) / "RotatingFlower"

    def tearDown(self):
        self.folder.cleanup()

    def test_task_command_quotes_every_path(self):
        command = self.installer.task_command(
            self.support / "global_bridge.py", Path("C:/sessions"), "COM3",
            "codex", None)
        self.assertIn('--sessions-root "C:\\sessions"'.replace("\\\\", "\\"), command)
        self.assertIn('--port "COM3"', command)
        self.assertIn('--source codex', command)

    def test_uninstall_keeps_logs_and_removes_runtime(self):
        self.support.mkdir(parents=True)
        logs = self.support / "logs"
        logs.mkdir()
        (logs / "bridge.log").write_text("kept", encoding="utf-8")
        for name in self.installer.RUNTIME_FILES:
            (self.support / name).write_text("x", encoding="utf-8")

        with patch.object(self.installer, "locations",
                          return_value=(self.support, logs)), \
             patch.object(self.installer, "task_exists", return_value=False):
            self.installer.uninstall()

        for name in self.installer.RUNTIME_FILES:
            self.assertFalse((self.support / name).exists())
        self.assertTrue((logs / "bridge.log").exists())

    def test_install_refuses_missing_sessions_directory(self):
        with patch.object(self.installer, "locations",
                          return_value=(self.support, self.support / "logs")), \
             patch.object(self.installer, "task_exists", return_value=False):
            with self.assertRaises(RuntimeError):
                self.installer.install(False, Path(self.folder.name) / "nope", "auto")


if __name__ == "__main__":
    unittest.main()
