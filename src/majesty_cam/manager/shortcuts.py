"""Windows shortcut support for the packaged Majesty Mod Manager."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
from typing import Callable

from .._subprocess import no_console_window_options
from .paths import default_desktop_root


SHORTCUT_NAME = "Majesty Mod Manager.lnk"

_CREATE_SHORTCUT_SCRIPT = r"""
$ErrorActionPreference = 'Stop'
$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($env:MMM_SHORTCUT_PATH)
$shortcut.TargetPath = $env:MMM_EXECUTABLE_PATH
$shortcut.WorkingDirectory = $env:MMM_WORKING_DIRECTORY
$shortcut.IconLocation = $env:MMM_ICON_LOCATION
$shortcut.Description = 'Launch Majesty Mod Manager'
$shortcut.Save()
""".strip()


class ShortcutError(RuntimeError):
    """Raised when Windows cannot create the requested manager shortcut."""


ShortcutRunner = Callable[..., subprocess.CompletedProcess[str]]


def create_manager_desktop_shortcut(
    *,
    application_executable: Path | None = None,
    desktop_root: Path | None = None,
    runner: ShortcutRunner = subprocess.run,
) -> Path:
    """Create or replace a Desktop shortcut without moving the application.

    The packaged manager is an onedir application whose ``_internal`` folder
    must remain beside its executable.  A shortcut preserves that layout and
    continues pointing at Steam's stable Workshop item directory after item
    updates.
    """

    executable = Path(application_executable or sys.executable).resolve(strict=False)
    if not executable.is_file():
        raise ShortcutError(f"Manager executable was not found: {executable}")

    desktop = Path(desktop_root or default_desktop_root()).resolve(strict=False)
    if not desktop.is_dir():
        raise ShortcutError(f"Windows Desktop folder was not found: {desktop}")

    shortcut = desktop / SHORTCUT_NAME
    environment = os.environ.copy()
    environment.update(
        {
            "MMM_SHORTCUT_PATH": str(shortcut),
            "MMM_EXECUTABLE_PATH": str(executable),
            "MMM_WORKING_DIRECTORY": str(executable.parent),
            "MMM_ICON_LOCATION": f"{executable},0",
        }
    )
    command = (
        "powershell.exe",
        "-NoLogo",
        "-NoProfile",
        "-NonInteractive",
        "-ExecutionPolicy",
        "Bypass",
        "-Command",
        _CREATE_SHORTCUT_SCRIPT,
    )
    try:
        completed = runner(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=20,
            env=environment,
            **no_console_window_options(),
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise ShortcutError(f"Windows could not create the shortcut: {exc}") from exc

    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "unknown error").strip()
        raise ShortcutError(f"Windows could not create the shortcut: {detail}")
    if not shortcut.is_file():
        raise ShortcutError(f"Windows did not create the shortcut: {shortcut}")
    return shortcut


__all__ = [
    "SHORTCUT_NAME",
    "ShortcutError",
    "create_manager_desktop_shortcut",
]
