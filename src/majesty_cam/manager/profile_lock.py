"""Exclusive lifetime lock for the fixed manager-generated Merge profile.

The lock file deliberately lives beside, rather than inside, the generated
profile directory.  Publishing replaces that directory atomically, so a lock
inside it would protect an obsolete inode/file object after the replacement.

On Windows the open handle uses ``dwShareMode == 0``.  The manager passes that
single handle to the runtime launcher with ``STARTUPINFOEX.handle_list``; the
launcher then keeps it open until Majesty exits.  The file is never deleted:
unlinking a lock pathname after close creates a race in which another process
can still own the old file while a third process locks a newly-created file.
"""

from __future__ import annotations

import ctypes
from ctypes import wintypes
import os
from pathlib import Path


PROFILE_LOCK_HANDLE_ENV_VAR = "MAJESTY_MOD_MANAGER_PROFILE_LOCK_HANDLE"

_GENERIC_READ = 0x80000000
_GENERIC_WRITE = 0x40000000
_OPEN_ALWAYS = 4
_FILE_ATTRIBUTE_NORMAL = 0x00000080
_HANDLE_FLAG_INHERIT = 0x00000001
_ERROR_SHARING_VIOLATION = 32
_ERROR_LOCK_VIOLATION = 33
_INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value


class ProfileLockError(RuntimeError):
    """Raised when the generated Merge profile cannot be locked safely."""


class ProfileLockBusyError(ProfileLockError):
    """Raised when another build or launched game owns the Merge profile."""


def merged_profile_lock_path(output_root: Path) -> Path:
    """Return the stable sibling lock path for a generated profile target."""

    output = Path(output_root)
    return output.parent / f".{output.name}.lock"


class ExclusiveProfileLock:
    """A close-only wrapper around a Windows exclusive file handle."""

    def __init__(self, path: Path, handle: int) -> None:
        self.path = path
        self._handle: int | None = handle

    @property
    def handle(self) -> int:
        if self._handle is None:
            raise ProfileLockError("The generated-profile lock is already closed.")
        return self._handle

    def set_inheritable(self, inheritable: bool) -> None:
        handle = self.handle
        kernel32 = _kernel32()
        flags = _HANDLE_FLAG_INHERIT if inheritable else 0
        if not kernel32.SetHandleInformation(
            wintypes.HANDLE(handle), _HANDLE_FLAG_INHERIT, flags
        ):
            error = ctypes.get_last_error()
            raise ProfileLockError(
                f"Could not prepare the generated-profile lock for the launcher "
                f"(Windows error {error})."
            )

    def close(self) -> None:
        handle = self._handle
        if handle is None:
            return
        self._handle = None
        if os.name == "nt":
            _kernel32().CloseHandle(wintypes.HANDLE(handle))

    def __enter__(self) -> "ExclusiveProfileLock":
        return self

    def __exit__(self, _exc_type, _exc, _traceback) -> None:
        self.close()


def acquire_merged_profile_lock(output_root: Path) -> ExclusiveProfileLock:
    """Acquire the one non-blocking lock shared by build and launch.

    Contention is reported immediately.  Waiting in the GUI would make a
    second build appear hung and could publish a profile the user no longer
    expects after the running game exits.
    """

    if os.name != "nt":
        raise ProfileLockError(
            "The Majesty generated-profile lock requires Windows."
        )
    lock_path = merged_profile_lock_path(output_root).resolve()
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    kernel32 = _kernel32()
    handle = kernel32.CreateFileW(
        str(lock_path),
        _GENERIC_READ | _GENERIC_WRITE,
        0,
        None,
        _OPEN_ALWAYS,
        _FILE_ATTRIBUTE_NORMAL,
        None,
    )
    raw_handle = ctypes.cast(handle, ctypes.c_void_p).value
    if raw_handle == _INVALID_HANDLE_VALUE:
        error = ctypes.get_last_error()
        if error in {_ERROR_SHARING_VIOLATION, _ERROR_LOCK_VIOLATION}:
            raise ProfileLockBusyError(
                "The generated Merge profile is in use by Majesty or another "
                "Mod Manager build. Close that game or wait for that build to "
                "finish, then try again."
            )
        raise ProfileLockError(
            f"Could not lock the generated Merge profile at {lock_path} "
            f"(Windows error {error})."
        )
    if raw_handle is None:
        raise ProfileLockError(
            f"Windows returned an invalid generated-profile lock for {lock_path}."
        )
    return ExclusiveProfileLock(lock_path, int(raw_handle))


def _kernel32():
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateFileW.argtypes = (
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.LPVOID,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    )
    kernel32.CreateFileW.restype = wintypes.HANDLE
    kernel32.SetHandleInformation.argtypes = (
        wintypes.HANDLE,
        wintypes.DWORD,
        wintypes.DWORD,
    )
    kernel32.SetHandleInformation.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
    kernel32.CloseHandle.restype = wintypes.BOOL
    return kernel32


__all__ = [
    "ExclusiveProfileLock",
    "PROFILE_LOCK_HANDLE_ENV_VAR",
    "ProfileLockBusyError",
    "ProfileLockError",
    "acquire_merged_profile_lock",
    "merged_profile_lock_path",
]
