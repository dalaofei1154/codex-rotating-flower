"""Check whether a PID is alive without touching it.

``os.kill(pid, 0)`` is the POSIX idiom for probing a process, but on Windows
``os.kill`` maps to ``TerminateProcess`` and would actually kill the target.
Windows therefore opens the process with query-only access instead.

``PermissionError`` is propagated rather than swallowed: a sandbox can deny the
probe even when the process exists, and callers differ on whether that should
count as alive (the Codex adapter skips, the WorkBuddy adapter reports it).
"""

from __future__ import annotations

import os
import sys


def process_alive(pid: int) -> bool:
    """Return True when ``pid`` is running; raise PermissionError if denied."""
    if sys.platform == "win32":
        return _windows_process_alive(pid)
    try:
        os.kill(pid, 0)
    except PermissionError:
        raise
    except OSError:
        return False
    return True


def _windows_process_alive(pid: int) -> bool:
    import ctypes
    from ctypes import wintypes

    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    ERROR_ACCESS_DENIED = 5
    ERROR_INVALID_PARAMETER = 87
    STILL_ACTIVE = 259

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL
    kernel32.GetExitCodeProcess.argtypes = [wintypes.HANDLE,
                                            ctypes.POINTER(wintypes.DWORD)]
    kernel32.GetExitCodeProcess.restype = wintypes.BOOL

    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        error = ctypes.get_last_error()
        if error == ERROR_ACCESS_DENIED:
            raise PermissionError(f"access denied probing pid {pid}")
        if error == ERROR_INVALID_PARAMETER:
            return False
        return False
    try:
        code = wintypes.DWORD(0)
        if not kernel32.GetExitCodeProcess(handle, ctypes.byref(code)):
            return True
        return code.value == STILL_ACTIVE
    finally:
        kernel32.CloseHandle(handle)
