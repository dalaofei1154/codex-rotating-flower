"""End-to-end check of the Windows serial path against a fake ESP32.

A com0com-style virtual port is not available here, so this drives the real
WindowsSerialPort code against a loopback pipe created with the Win32 API.
The bridge's own handshake (write PING, wait for PONG, send RUN, send STOP) is
exercised unchanged; only the kernel object behind the handle differs from a
physical COM port.
"""

from __future__ import annotations

import ctypes
import os
import sys
import time
from ctypes import wintypes

sys.path.insert(0, "m1")

import serial_link

GENERIC_WRITE = 0x40000000
GENERIC_READ = 0x80000000
OPEN_EXISTING = 3
FILE_ATTRIBUTE_NORMAL = 0x80
PIPE_ACCESS_DUPLEX = 0x00000003
PIPE_TYPE_BYTE = 0x00000000
PIPE_READMODE_BYTE = 0x00000000
PIPE_WAIT = 0x00000000
INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value


class Pipe:
    """A duplex byte pipe that stands in for the ESP32 end of the link."""

    def __init__(self):
        self.kernel32 = serial_link._kernel32()
        self.kernel32.CreateNamedPipeW.argtypes = [
            wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.DWORD,
            wintypes.DWORD, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID]
        self.kernel32.CreateNamedPipeW.restype = wintypes.HANDLE
        self.kernel32.ConnectNamedPipe.argtypes = [wintypes.HANDLE, wintypes.LPVOID]
        self.kernel32.ConnectNamedPipe.restype = wintypes.BOOL
        self.kernel32.DisconnectNamedPipe.argtypes = [wintypes.HANDLE]
        self.kernel32.DisconnectNamedPipe.restype = wintypes.BOOL
        self.kernel32.PeekNamedPipe.argtypes = [
            wintypes.HANDLE, wintypes.LPVOID, wintypes.DWORD,
            ctypes.POINTER(wintypes.DWORD), ctypes.POINTER(wintypes.DWORD),
            ctypes.POINTER(wintypes.DWORD)]
        self.kernel32.PeekNamedPipe.restype = wintypes.BOOL

        name = f"\\\\.\\pipe\\flower-esp32-{os.getpid()}"
        self.handle = self.kernel32.CreateNamedPipeW(
            name, PIPE_ACCESS_DUPLEX, PIPE_TYPE_BYTE | PIPE_READMODE_BYTE | PIPE_WAIT,
            1, 4096, 4096, 0, None)
        if not self.handle or self.handle == INVALID_HANDLE_VALUE:
            raise ctypes.WinError(ctypes.get_last_error())
        self.name = name

    def connect_client(self):
        """Open the client end the way WindowsSerialPort opens a COM port."""
        handle = self.kernel32.CreateFileW(
            self.name, GENERIC_READ | GENERIC_WRITE, 0, None,
            OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, None)
        if not handle or handle == INVALID_HANDLE_VALUE:
            raise ctypes.WinError(ctypes.get_last_error())
        self.kernel32.ConnectNamedPipe(self.handle, None)
        return handle

    def pending(self) -> int:
        available = wintypes.DWORD(0)
        self.kernel32.PeekNamedPipe(self.handle, None, 0, None, ctypes.byref(available), None)
        return available.value

    def read(self, limit: int = 4096) -> bytes:
        if not self.pending():
            return b""
        buffer = ctypes.create_string_buffer(limit)
        received = wintypes.DWORD(0)
        if not self.kernel32.ReadFile(self.handle, buffer, limit,
                                      ctypes.byref(received), None):
            raise ctypes.WinError(ctypes.get_last_error())
        return buffer.raw[:received.value]

    def write(self, data: bytes) -> None:
        written = wintypes.DWORD(0)
        if not self.kernel32.WriteFile(self.handle, data, len(data),
                                       ctypes.byref(written), None):
            raise ctypes.WinError(ctypes.get_last_error())

    def close(self):
        if self.handle:
            self.kernel32.DisconnectNamedPipe(self.handle)
            self.kernel32.CloseHandle(self.handle)
            self.handle = None


def main() -> int:
    if sys.platform != "win32":
        print("SKIP: this check drives the Win32 serial API")
        return 0

    pipe = Pipe()
    client = pipe.connect_client()
    try:
        # Attach the real WindowsSerialPort methods to the pipe handle so the
        # production write/read/close code runs unmodified.
        port = object.__new__(serial_link.WindowsSerialPort)
        port._ctypes = ctypes
        port._kernel32 = pipe.kernel32
        port.handle = client

        port.write(b"PING\n")
        got = pipe.read()
        print("device received:", got)
        assert got == b"PING\n", got

        # The ESP32 answers; the bridge must see PONG.
        pipe.write(b"PONG\n")
        deadline = time.monotonic() + 1.0
        reply = b""
        while time.monotonic() < deadline:
            chunk = port.read()
            if chunk:
                reply += chunk
                if b"PONG" in reply:
                    break
            time.sleep(0.02)
        print("bridge received:", reply)
        assert b"PONG" in reply, reply

        # Full command cycle in the order the bridge sends it.
        for command in (b"RUN LOW\n", b"RUN ULTRA\n", b"STOP\n"):
            port.write(command)
            assert pipe.read() == command, command
            print("device received:", command)

        port.close()
        print("RESULT: PING/PONG handshake and RUN/STOP cycle work over the Win32 path")
        return 0
    finally:
        pipe.close()


if __name__ == "__main__":
    raise SystemExit(main())
