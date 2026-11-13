"""Open and poll an ESP32 serial port on macOS, Linux, and Windows.

The bridge keeps using only the standard library. POSIX systems configure the
port with ``stty`` and poll it with ``select``; Windows talks to the Win32
serial API through ``ctypes``, so ``global_bridge.py`` no longer needs
``fcntl``, ``stty``, or a ``select``-able file descriptor.
"""

from __future__ import annotations

import glob
import os
import subprocess
import sys

DEFAULT_BAUDRATE = 115200

POSIX_PATTERNS = (
    "/dev/cu.usbmodem*",
    "/dev/cu.usbserial*",
    "/dev/serial/by-id/*",
    "/dev/ttyACM*",
    "/dev/ttyUSB*",
)

_WINDOWS_PREFIX = "\\\\.\\"


def list_serial_ports() -> list[str]:
    """Return the serial ports that currently exist on this computer."""
    if sys.platform == "win32":
        return _windows_serial_ports()
    return sorted({path for pattern in POSIX_PATTERNS for path in glob.glob(pattern)})


def port_still_present(path: str) -> bool:
    """Report whether ``path`` can still be used without reopening it."""
    if os.path.exists(path):
        return True
    if sys.platform == "win32":
        # A caller may pass either "COM12" or the "\\\\.\\COM12" form that
        # Win32 needs; the registry only reports the bare name.
        wanted = _bare_port_name(path).upper()
        return any(port.upper() == wanted for port in _windows_serial_ports())
    return False


def _bare_port_name(port: str) -> str:
    """Strip the ``\\\\.\\`` prefix so a device path compares with the registry."""
    if port.startswith(_WINDOWS_PREFIX):
        return port[len(_WINDOWS_PREFIX):]
    return port


def windows_device_path(port: str) -> str:
    """Return the ``\\\\.\\COMx`` form Win32 needs for ports above COM9."""
    if port.startswith(_WINDOWS_PREFIX):
        return port
    return _WINDOWS_PREFIX + port


def open_port(path: str, baudrate: int = DEFAULT_BAUDRATE) -> "SerialPort":
    """Open ``path`` as a non-blocking serial port."""
    if sys.platform == "win32":
        return WindowsSerialPort(path, baudrate)
    return PosixSerialPort(path, baudrate)


class SerialPort:
    """The small serial interface the motor link relies on."""

    def write(self, data: bytes) -> None:
        raise NotImplementedError

    def read(self, limit: int = 4096) -> bytes:
        """Return whatever bytes are already waiting, without blocking."""
        raise NotImplementedError

    def close(self) -> None:
        raise NotImplementedError


class PosixSerialPort(SerialPort):
    def __init__(self, path: str, baudrate: int = DEFAULT_BAUDRATE):
        stty_flag = "-f" if sys.platform == "darwin" else "-F"
        try:
            subprocess.run(["stty", stty_flag, path, str(baudrate), "raw", "-echo"],
                           check=True, capture_output=True, timeout=2)
        except (subprocess.SubprocessError, OSError) as error:
            raise OSError(f"could not configure {path}: {error}") from error
        self.fd = os.open(path, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
        self.exclusive = False
        try:
            import fcntl
            import termios
        except ImportError:
            # Not a POSIX build: there is no ioctl to take.
            return
        try:
            # Exclusive ownership: refuse to share the port with another owner
            # such as a serial monitor. A failure here (EIO when the device
            # cannot be claimed) must reject the connection, not continue on a
            # port someone else may own.
            fcntl.ioctl(self.fd, termios.TIOCEXCL)
            self.exclusive = True
        except OSError:
            os.close(self.fd)
            raise

    def write(self, data: bytes) -> None:
        written = os.write(self.fd, data)
        if written != len(data):
            raise OSError(f"serial write sent {written} of {len(data)} bytes")

    def read(self, limit: int = 4096) -> bytes:
        import select
        ready, _, _ = select.select([self.fd], [], [], 0)
        if not ready:
            return b""
        return os.read(self.fd, limit)

    def close(self) -> None:
        if self.exclusive:
            try:
                import fcntl
                import termios
                fcntl.ioctl(self.fd, termios.TIOCNXCL)
            except (ImportError, OSError):
                pass
            self.exclusive = False
        os.close(self.fd)


def _windows_serial_ports() -> list[str]:
    try:
        import winreg
    except ImportError:
        return []
    try:
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                             r"HARDWARE\DEVICEMAP\SERIALCOMM")
    except OSError:
        return []
    ports: list[str] = []
    with key:
        index = 0
        while True:
            try:
                _, value, _ = winreg.EnumValue(key, index)
            except OSError:
                break
            if isinstance(value, str) and value:
                ports.append(value)
            index += 1
    return sorted(set(ports), key=_port_sort_key)


def _port_sort_key(port: str) -> tuple[str, int, str]:
    """Sort COM2 before COM10, which plain string ordering gets wrong."""
    index = 0
    while index < len(port) and not port[index].isdigit():
        index += 1
    digits = port[index:]
    if digits.isdigit():
        return (port[:index].upper(), int(digits), port)
    return (port[:index].upper(), -1, port)


if sys.platform == "win32":
    import ctypes
    from ctypes import wintypes

    _INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value
    _GENERIC_READ_WRITE = 0x80000000 | 0x40000000
    _OPEN_EXISTING = 3
    _FILE_ATTRIBUTE_NORMAL = 0x80
    _PURGE_TXCLEAR_RXCLEAR = 0x0004 | 0x0008

    class _DCB(ctypes.Structure):
        _fields_ = [
            ("DCBlength", wintypes.DWORD),
            ("BaudRate", wintypes.DWORD),
            ("fBinary", wintypes.DWORD, 1),
            ("fParity", wintypes.DWORD, 1),
            ("fOutxCtsFlow", wintypes.DWORD, 1),
            ("fOutxDsrFlow", wintypes.DWORD, 1),
            ("fDtrControl", wintypes.DWORD, 2),
            ("fDsrSensitivity", wintypes.DWORD, 1),
            ("fTXContinueOnXoff", wintypes.DWORD, 1),
            ("fOutX", wintypes.DWORD, 1),
            ("fInX", wintypes.DWORD, 1),
            ("fErrorChar", wintypes.DWORD, 1),
            ("fNull", wintypes.DWORD, 1),
            ("fRtsControl", wintypes.DWORD, 2),
            ("fAbortOnError", wintypes.DWORD, 1),
            ("fDummy2", wintypes.DWORD, 17),
            ("wReserved", wintypes.WORD),
            ("XonLim", wintypes.WORD),
            ("XoffLim", wintypes.WORD),
            ("ByteSize", wintypes.BYTE),
            ("Parity", wintypes.BYTE),
            ("StopBits", wintypes.BYTE),
            ("XonChar", ctypes.c_char),
            ("XoffChar", ctypes.c_char),
            ("ErrorChar", ctypes.c_char),
            ("EofChar", ctypes.c_char),
            ("EvtChar", ctypes.c_char),
            ("wReserved1", wintypes.WORD),
        ]

    class _COMMTIMEOUTS(ctypes.Structure):
        _fields_ = [
            ("ReadIntervalTimeout", wintypes.DWORD),
            ("ReadTotalTimeoutMultiplier", wintypes.DWORD),
            ("ReadTotalTimeoutConstant", wintypes.DWORD),
            ("WriteTotalTimeoutMultiplier", wintypes.DWORD),
            ("WriteTotalTimeoutConstant", wintypes.DWORD),
        ]

    _KERNEL32 = None

    def _kernel32():
        global _KERNEL32
        if _KERNEL32 is None:
            library = ctypes.WinDLL("kernel32", use_last_error=True)
            library.CreateFileW.argtypes = [
                wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD,
                wintypes.HANDLE]
            library.CreateFileW.restype = wintypes.HANDLE
            library.CloseHandle.argtypes = [wintypes.HANDLE]
            library.CloseHandle.restype = wintypes.BOOL
            library.SetupComm.argtypes = [wintypes.HANDLE, wintypes.DWORD,
                                          wintypes.DWORD]
            library.SetupComm.restype = wintypes.BOOL
            library.GetCommState.argtypes = [wintypes.HANDLE,
                                             ctypes.POINTER(_DCB)]
            library.GetCommState.restype = wintypes.BOOL
            library.SetCommState.argtypes = [wintypes.HANDLE,
                                             ctypes.POINTER(_DCB)]
            library.SetCommState.restype = wintypes.BOOL
            library.SetCommTimeouts.argtypes = [wintypes.HANDLE,
                                                ctypes.POINTER(_COMMTIMEOUTS)]
            library.SetCommTimeouts.restype = wintypes.BOOL
            library.PurgeComm.argtypes = [wintypes.HANDLE, wintypes.DWORD]
            library.PurgeComm.restype = wintypes.BOOL
            library.ReadFile.argtypes = [
                wintypes.HANDLE, wintypes.LPVOID, wintypes.DWORD,
                ctypes.POINTER(wintypes.DWORD), wintypes.LPVOID]
            library.ReadFile.restype = wintypes.BOOL
            library.WriteFile.argtypes = [
                wintypes.HANDLE, wintypes.LPCVOID, wintypes.DWORD,
                ctypes.POINTER(wintypes.DWORD), wintypes.LPVOID]
            library.WriteFile.restype = wintypes.BOOL
            _KERNEL32 = library
        return _KERNEL32

    class WindowsSerialPort(SerialPort):
        """A Win32 serial handle that behaves like a non-blocking POSIX port."""

        def __init__(self, path: str, baudrate: int = DEFAULT_BAUDRATE):
            self._ctypes = ctypes
            self._kernel32 = _kernel32()
            handle = self._kernel32.CreateFileW(
                windows_device_path(path), _GENERIC_READ_WRITE, 0, None,
                _OPEN_EXISTING, _FILE_ATTRIBUTE_NORMAL, None)
            if not handle or handle == _INVALID_HANDLE_VALUE:
                raise ctypes.WinError(ctypes.get_last_error())
            self.handle = handle
            try:
                self._configure(baudrate)
            except OSError:
                self.close()
                raise

        def _configure(self, baudrate: int) -> None:
            ctypes = self._ctypes
            kernel32 = self._kernel32
            if not kernel32.SetupComm(self.handle, 4096, 4096):
                raise ctypes.WinError(ctypes.get_last_error())
            dcb = _DCB()
            dcb.DCBlength = ctypes.sizeof(_DCB)
            if not kernel32.GetCommState(self.handle, ctypes.byref(dcb)):
                raise ctypes.WinError(ctypes.get_last_error())
            dcb.BaudRate = baudrate
            dcb.fBinary = 1
            dcb.fParity = 0
            dcb.fOutxCtsFlow = 0
            dcb.fOutxDsrFlow = 0
            dcb.fDtrControl = 0
            dcb.fDsrSensitivity = 0
            dcb.fTXContinueOnXoff = 1
            dcb.fOutX = 0
            dcb.fInX = 0
            dcb.fErrorChar = 0
            dcb.fNull = 0
            dcb.fRtsControl = 0
            dcb.fAbortOnError = 0
            dcb.ByteSize = 8
            dcb.Parity = 0
            dcb.StopBits = 0
            if not kernel32.SetCommState(self.handle, ctypes.byref(dcb)):
                raise ctypes.WinError(ctypes.get_last_error())
            timeouts = _COMMTIMEOUTS()
            timeouts.ReadIntervalTimeout = 0xFFFFFFFF
            timeouts.ReadTotalTimeoutMultiplier = 0
            timeouts.ReadTotalTimeoutConstant = 0
            timeouts.WriteTotalTimeoutMultiplier = 0
            timeouts.WriteTotalTimeoutConstant = 1000
            if not kernel32.SetCommTimeouts(self.handle, ctypes.byref(timeouts)):
                raise ctypes.WinError(ctypes.get_last_error())
            kernel32.PurgeComm(self.handle, _PURGE_TXCLEAR_RXCLEAR)

        def write(self, data: bytes) -> None:
            ctypes = self._ctypes
            written = wintypes.DWORD(0)
            if not self._kernel32.WriteFile(self.handle, data, len(data),
                                            ctypes.byref(written), None):
                raise ctypes.WinError(ctypes.get_last_error())
            if written.value != len(data):
                raise OSError(f"serial write sent {written.value} of {len(data)} bytes")

        def read(self, limit: int = 4096) -> bytes:
            ctypes = self._ctypes
            buffer = ctypes.create_string_buffer(limit)
            received = wintypes.DWORD(0)
            if not self._kernel32.ReadFile(self.handle, buffer, limit,
                                           ctypes.byref(received), None):
                raise ctypes.WinError(ctypes.get_last_error())
            return buffer.raw[:received.value]

        def close(self) -> None:
            if self.handle:
                self._kernel32.CloseHandle(self.handle)
                self.handle = None
else:
    class WindowsSerialPort(SerialPort):
        def __init__(self, path: str, baudrate: int = DEFAULT_BAUDRATE):
            raise OSError("Windows serial support is unavailable on this platform")
