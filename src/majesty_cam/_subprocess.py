"""Cross-platform subprocess options for headless Windows helper programs."""

from __future__ import annotations

import os
import subprocess
from typing import Any


def no_console_window_options(*, force_hidden: bool = True) -> dict[str, Any]:
    """Return ``subprocess`` options that avoid a Windows console flash.

    ``CREATE_NO_WINDOW`` prevents console-subsystem helpers from receiving a
    console.  ``STARTF_USESHOWWINDOW`` with ``SW_HIDE`` also covers helper
    executables that pay attention to the startup show state.  Callers that
    intentionally open a graphical application can set ``force_hidden=False``
    and still suppress an accidental console without hiding the application.

    Non-Windows callers receive an empty mapping so the same process creation
    code retains its existing behavior on every other platform.
    """

    if os.name != "nt":
        return {}

    options: dict[str, Any] = {
        "creationflags": subprocess.CREATE_NO_WINDOW,
    }
    if force_hidden:
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = subprocess.SW_HIDE
        options["startupinfo"] = startupinfo
    return options


__all__ = ["no_console_window_options"]
