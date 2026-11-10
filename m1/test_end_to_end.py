"""End-to-end checks that do not need a physical ESP32.

These complement the unit tests: they drive the real Win32 serial calls over a
loopback pipe and run the installed copy from its own directory, which is how
a missing runtime module would show up.
"""

import ctypes
import importlib.util
import os
import subprocess
import sys
import tempfile
import time
import unittest
from ctypes import wintypes
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
install_windows = load("install_windows")


@unittest.skipUnless(sys.platform == "win32", "drives the Win32 serial API")
class Win32LoopbackTests(unittest.TestCase):
    """Send the bridge's real frames through a Win32 duplex pipe."""

    def setUp(self):
        kernel32 = serial_link._kernel32()
        self.kernel32 = kernel32
        kernel32.CreateNamedPipeW.argtypes = [
            wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.DWORD,
            wintypes.DWORD, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID]
        kernel32.CreateNamedPipeW.restype = wintypes.HANDLE
        kernel32.ConnectNamedPipe.argtypes = [wintypes.HANDLE, wintypes.LPVOID]
        kernel32.ConnectNamedPipe.restype = wintypes.BOOL
        kernel32.DisconnectNamedPipe.argtypes = [wintypes.HANDLE]
        kernel32.DisconnectNamedPipe.restype = wintypes.BOOL
        kernel32.PeekNamedPipe.argtypes = [
            wintypes.HANDLE, wintypes.LPVOID, wintypes.DWORD,
            ctypes.POINTER(wintypes.DWORD), ctypes.POINTER(wintypes.DWORD),
            ctypes.POINTER(wintypes.DWORD)]
        kernel32.PeekNamedPipe.restype = wintypes.BOOL

        name = f"\\\\.\\pipe\\flower-test-{os.getpid()}-{id(self)}"
        self.device = kernel32.CreateNamedPipeW(
            name, 0x3, 0x0 | 0x0 | 0x0, 1, 4096, 4096, 0, None)
        self.assertFalse(
            not self.device or self.device == ctypes.c_void_p(-1).value,
            "CreateNamedPipeW failed")

        client = kernel32.CreateFileW(
            name, 0x80000000 | 0x40000000, 0, None, 3, 0x80, None)
        self.assertFalse(
            not client or client == ctypes.c_void_p(-1).value,
            "CreateFileW failed")
        kernel32.ConnectNamedPipe(self.device, None)

        # The production methods, pointed at the pipe handle.
        self.port = object.__new__(serial_link.WindowsSerialPort)
        self.port._ctypes = ctypes
        self.port._kernel32 = kernel32
        self.port.handle = client

    def tearDown(self):
        self.port.close()
        self.kernel32.DisconnectNamedPipe(self.device)
        self.kernel32.CloseHandle(self.device)

    def device_pending(self):
        available = wintypes.DWORD(0)
        self.kernel32.PeekNamedPipe(self.device, None, 0, None,
                                    ctypes.byref(available), None)
        return available.value

    def device_read(self):
        if not self.device_pending():
            return b""
        buffer = ctypes.create_string_buffer(4096)
        received = wintypes.DWORD(0)
        self.kernel32.ReadFile(self.device, buffer, 4096,
                               ctypes.byref(received), None)
        return buffer.raw[:received.value]

    def device_write(self, data):
        written = wintypes.DWORD(0)
        self.kernel32.WriteFile(self.device, data, len(data),
                                ctypes.byref(written), None)

    def test_ping_reaches_the_device(self):
        self.port.write(b"PING\n")
        self.assertEqual(self.device_read(), b"PING\n")

    def test_pong_is_read_back_by_the_bridge(self):
        self.device_write(b"PONG\n")
        deadline = time.monotonic() + 1.0
        reply = b""
        while time.monotonic() < deadline and b"PONG" not in reply:
            reply += self.port.read()
            time.sleep(0.02)
        self.assertIn(b"PONG", reply)

    def test_run_and_stop_frames_arrive_in_order(self):
        for command in (b"RUN LOW\n", b"RUN ULTRA\n", b"STOP\n"):
            self.port.write(command)
            self.assertEqual(self.device_read(), command)


class InstalledRuntimeTests(unittest.TestCase):
    """The installed copy must run with only its own directory on the path."""

    def test_install_then_run_the_installed_copy(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            sessions = root / "sessions"
            sessions.mkdir()
            support = root / "RotatingFlower"

            class Done:
                returncode = 0
                stdout = ""
                stderr = ""

            with patch.object(install_windows, "locations",
                              return_value=(support, support / "logs")), \
                 patch.object(install_windows, "task_exists", return_value=False), \
                 patch.object(install_windows, "schtasks",
                              return_value=Done()):
                install_windows.install(False, sessions, "auto", "codex", None)

            installed = support / "global_bridge.py"
            self.assertTrue(installed.exists())

            result = subprocess.run(
                [sys.executable, str(installed), "--once",
                 "--sessions-root", str(sessions)],
                capture_output=True, text=True, shell=False, timeout=60,
                cwd=str(support),
            )
            self.assertEqual(result.returncode, 0, result.stderr[:600])
            self.assertIn("motor: STOP", result.stdout)


if __name__ == "__main__":
    unittest.main()
