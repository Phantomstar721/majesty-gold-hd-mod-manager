"""Narrow Windows elevation helpers for protected game-file mutations."""

from __future__ import annotations

import ctypes
from ctypes import wintypes
import os
from pathlib import Path
import subprocess
import tempfile
from typing import Sequence


_ERROR_ACCESS_DENIED = 5
_ERROR_CANCELLED = 1223
_SEE_MASK_NOCLOSEPROCESS = 0x00000040
_SEE_MASK_NO_CONSOLE = 0x00008000
_SW_HIDE = 0
_WAIT_OBJECT_0 = 0x00000000
_WAIT_TIMEOUT = 0x00000102
_INFINITE = 0xFFFFFFFF


class _ShellExecuteInfoW(ctypes.Structure):
    _fields_ = (
        ("cbSize", wintypes.DWORD),
        ("fMask", wintypes.ULONG),
        ("hwnd", wintypes.HWND),
        ("lpVerb", wintypes.LPCWSTR),
        ("lpFile", wintypes.LPCWSTR),
        ("lpParameters", wintypes.LPCWSTR),
        ("lpDirectory", wintypes.LPCWSTR),
        ("nShow", ctypes.c_int),
        ("hInstApp", wintypes.HINSTANCE),
        ("lpIDList", wintypes.LPVOID),
        ("lpClass", wintypes.LPCWSTR),
        ("hkeyClass", wintypes.HKEY),
        ("dwHotKey", wintypes.DWORD),
        ("hIconOrMonitor", wintypes.HANDLE),
        ("hProcess", wintypes.HANDLE),
    )


def directory_requires_elevation(directory: Path) -> bool:
    """Return whether creating a temporary file is denied in ``directory``.

    Windows ACL checks such as ``os.access`` do not reliably model the token
    used for a real create operation. This reversible probe asks the filesystem
    directly and removes its empty file immediately.
    """

    if os.name != "nt":
        return False
    probe_path: str | None = None
    descriptor: int | None = None
    try:
        descriptor, probe_path = tempfile.mkstemp(
            prefix=".MajestyModManager-write-probe-",
            dir=str(directory),
        )
        return False
    except PermissionError:
        return True
    except OSError as exc:
        return getattr(exc, "winerror", None) == _ERROR_ACCESS_DENIED
    finally:
        if descriptor is not None:
            os.close(descriptor)
        if probe_path is not None:
            try:
                Path(probe_path).unlink()
            except OSError:
                pass


def run_elevated_hidden(
    command: Sequence[str],
    *,
    timeout_seconds: int | None = 300,
) -> subprocess.CompletedProcess[str]:
    """Run one command through Windows UAC without elevating the Manager.

    Only the exact child command crosses the elevation boundary. Its arguments
    are supplied explicitly by the unelevated process, so per-user Manager
    paths never need to be rediscovered under a different administrator token.
    """

    arguments = tuple(str(item) for item in command)
    if not arguments:
        raise ValueError("an elevated command requires an executable")
    if os.name != "nt":
        raise OSError("Windows elevation is unavailable on this platform")

    shell32 = ctypes.WinDLL("shell32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    shell_execute = shell32.ShellExecuteExW
    shell_execute.argtypes = (ctypes.POINTER(_ShellExecuteInfoW),)
    shell_execute.restype = wintypes.BOOL
    wait_for_single_object = kernel32.WaitForSingleObject
    wait_for_single_object.argtypes = (wintypes.HANDLE, wintypes.DWORD)
    wait_for_single_object.restype = wintypes.DWORD
    get_exit_code = kernel32.GetExitCodeProcess
    get_exit_code.argtypes = (wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD))
    get_exit_code.restype = wintypes.BOOL
    close_handle = kernel32.CloseHandle
    close_handle.argtypes = (wintypes.HANDLE,)
    close_handle.restype = wintypes.BOOL

    info = _ShellExecuteInfoW()
    info.cbSize = ctypes.sizeof(info)
    info.fMask = _SEE_MASK_NOCLOSEPROCESS | _SEE_MASK_NO_CONSOLE
    info.lpVerb = "runas"
    info.lpFile = arguments[0]
    info.lpParameters = subprocess.list2cmdline(list(arguments[1:]))
    info.nShow = _SW_HIDE
    ctypes.set_last_error(0)
    if not shell_execute(ctypes.byref(info)):
        error = ctypes.get_last_error()
        if error == _ERROR_CANCELLED:
            raise OSError(error, "Administrator approval was cancelled")
        raise ctypes.WinError(error)
    if not info.hProcess:
        raise OSError("Windows did not return the elevated process handle")

    try:
        timeout_ms = (
            _INFINITE
            if timeout_seconds is None
            else max(0, int(timeout_seconds * 1000))
        )
        wait_result = wait_for_single_object(info.hProcess, timeout_ms)
        if wait_result == _WAIT_TIMEOUT:
            raise subprocess.TimeoutExpired(arguments, timeout_seconds)
        if wait_result != _WAIT_OBJECT_0:
            raise ctypes.WinError(ctypes.get_last_error())
        exit_code = wintypes.DWORD()
        if not get_exit_code(info.hProcess, ctypes.byref(exit_code)):
            raise ctypes.WinError(ctypes.get_last_error())
        return subprocess.CompletedProcess(
            arguments,
            int(exit_code.value),
            stdout="",
            stderr="",
        )
    finally:
        close_handle(info.hProcess)


__all__ = ["directory_requires_elevation", "run_elevated_hidden"]
