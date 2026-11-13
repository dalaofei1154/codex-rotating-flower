"""Test the POSIX exclusive-ownership path with injected modules.

Windows has no fcntl/termios, so the POSIX branch cannot run there. These
tests inject stand-in modules into sys.modules so the real code path executes
on any platform, which is what the maintainer asked for: a test for the case
where TIOCEXCL fails.
"""

import errno
import importlib.util
import sys
import types
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


class FakeFcntl(types.ModuleType):
    def __init__(self, error=None):
        super().__init__("fcntl")
        self.error = error
        self.calls = []

    def ioctl(self, fd, request):
        self.calls.append((fd, request))
        if self.error is not None:
            raise self.error


class FakeTermios(types.ModuleType):
    TIOCEXCL = 0x2000740D
    TIOCNXCL = 0x2000740E

    def __init__(self):
        super().__init__("termios")


class PosixExclusiveOwnershipTests(unittest.TestCase):
    """A port that cannot be claimed exclusively must be rejected."""

    def _run(self, ioctl_error):
        fake_fcntl = FakeFcntl(ioctl_error)
        fake_termios = FakeTermios()
        opened = []
        closed = []

        def fake_open(path, flags):
            opened.append(path)
            return 4242

        # O_NOCTTY / O_NONBLOCK do not exist on Windows; the POSIX branch
        # reads them at call time, so create them for this test only.
        patches = [
            patch.dict(sys.modules, {"fcntl": fake_fcntl, "termios": fake_termios}),
            patch.object(serial_link.os, "O_RDWR", 2, create=True),
            patch.object(serial_link.os, "O_NOCTTY", 0o400, create=True),
            patch.object(serial_link.os, "O_NONBLOCK", 0o4000, create=True),
            patch.object(serial_link.subprocess, "run"),
            patch.object(serial_link.os, "open", side_effect=fake_open),
            patch.object(serial_link.os, "close", side_effect=closed.append),
        ]
        for entry in patches:
            entry.start()
        try:
            try:
                port = serial_link.PosixSerialPort("/dev/cu.test")
            except OSError as error:
                return "raised", error, opened, closed, fake_fcntl
            return "ok", port, opened, closed, fake_fcntl
        finally:
            for entry in reversed(patches):
                entry.stop()

    def test_tiocexcl_failure_raises_and_closes_the_descriptor(self):
        status, value, opened, closed, _ = self._run(
            OSError(errno.EIO, "Input/output error"))
        self.assertEqual(status, "raised", "TIOCEXCL failure must reject the port")
        self.assertEqual(opened, ["/dev/cu.test"])
        self.assertEqual(closed, [4242], "the descriptor must be closed on failure")

    def test_tiocexcl_failure_propagates_the_original_error(self):
        status, value, _, _, _ = self._run(OSError(errno.EIO, "Input/output error"))
        self.assertEqual(status, "raised")
        self.assertEqual(value.errno, errno.EIO)

    def test_tiocexcl_success_keeps_the_port_and_marks_it_exclusive(self):
        status, port, opened, closed, fake_fcntl = self._run(None)
        self.assertEqual(status, "ok")
        self.assertEqual(opened, ["/dev/cu.test"])
        self.assertEqual(closed, [])
        self.assertTrue(port.exclusive)
        self.assertEqual(fake_fcntl.calls, [(4242, FakeTermios.TIOCEXCL)])

    def test_close_releases_exclusive_ownership_then_closes(self):
        status, port, _, closed, fake_fcntl = self._run(None)
        self.assertEqual(status, "ok")
        fake_fcntl.calls.clear()
        closed.clear()
        # close() imports fcntl again, so keep the stand-in installed.
        with patch.dict(sys.modules, {"fcntl": fake_fcntl,
                                      "termios": FakeTermios()}), \
             patch.object(serial_link.os, "close", side_effect=closed.append):
            port.close()
        self.assertEqual(fake_fcntl.calls, [(4242, FakeTermios.TIOCNXCL)])
        self.assertEqual(closed, [4242])
        self.assertFalse(port.exclusive)


if __name__ == "__main__":
    unittest.main()
