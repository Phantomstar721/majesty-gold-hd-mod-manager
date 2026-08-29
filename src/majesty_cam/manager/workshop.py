"""Safe, player-facing links to Steam Workshop items."""

from __future__ import annotations

from enum import Enum
import os
from pathlib import Path
import re
import subprocess
from typing import Optional
import webbrowser

from .._subprocess import no_console_window_options


_MAX_PUBLISHED_FILE_ID = 2**64 - 1


class WorkshopOpenMethod(str, Enum):
    """Where a Workshop page was opened."""

    STEAM = "steam"
    BROWSER = "browser"


def normalize_workshop_item_id(value: object) -> str:
    """Validate and canonicalize a Steam PublishedFileId.

    Accepting ASCII digits only, and passing Steam a subprocess argument list,
    keeps paths and URLs from becoming a command-shell boundary.
    """

    if not isinstance(value, str):
        raise ValueError("Workshop item ID must be a decimal string")
    candidate = value.strip()
    if re.fullmatch(r"[1-9][0-9]{0,19}", candidate) is None:
        raise ValueError("Workshop item ID must be a nonzero unsigned 64-bit integer")
    if int(candidate) > _MAX_PUBLISHED_FILE_ID:
        raise ValueError("Workshop item ID exceeds Steam's unsigned 64-bit range")
    return candidate


def workshop_page_url(item_id: str) -> str:
    """Return the public HTTPS details page for a validated Workshop item."""

    canonical = normalize_workshop_item_id(item_id)
    return f"https://steamcommunity.com/sharedfiles/filedetails/?id={canonical}"


def workshop_steam_uri(item_id: str) -> str:
    """Return Steam's client URI for a validated Workshop item."""

    canonical = normalize_workshop_item_id(item_id)
    return f"steam://url/CommunityFilePage/{canonical}"


def find_steam_executable() -> Optional[Path]:
    """Find an installed Steam client without invoking PATH or a shell."""

    candidates: list[Path] = []
    if os.name == "nt":
        try:
            import winreg

            registry_locations = (
                (winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam"),
                (winreg.HKEY_LOCAL_MACHINE, r"Software\WOW6432Node\Valve\Steam"),
                (winreg.HKEY_LOCAL_MACHINE, r"Software\Valve\Steam"),
            )
            for hive, key_name in registry_locations:
                try:
                    with winreg.OpenKey(hive, key_name) as key:
                        for value_name in ("SteamExe", "InstallPath", "SteamPath"):
                            try:
                                raw_value = winreg.QueryValueEx(key, value_name)[0]
                            except OSError:
                                continue
                            path = Path(str(raw_value).replace("/", "\\"))
                            candidates.append(
                                path if path.name.casefold() == "steam.exe" else path / "steam.exe"
                            )
                except OSError:
                    continue
        except (ImportError, OSError):
            pass

    program_files_x86 = os.environ.get("PROGRAMFILES(X86)")
    if program_files_x86:
        candidates.append(Path(program_files_x86) / "Steam" / "steam.exe")
    candidates.append(Path(r"C:\Program Files (x86)\Steam\steam.exe"))

    seen: set[str] = set()
    for candidate in candidates:
        key = str(candidate.resolve(strict=False)).casefold()
        if key in seen:
            continue
        seen.add(key)
        if candidate.is_file():
            return candidate.resolve()
    return None


def open_workshop_item(item_id: str) -> WorkshopOpenMethod:
    """Open an item in Steam when installed, otherwise in the web browser.

    Steam is launched directly with an argv list and ``shell=False``.  If an
    installed client cannot be started, the HTTPS page is used as a graceful
    fallback.
    """

    canonical = normalize_workshop_item_id(item_id)
    steam_executable = find_steam_executable()
    if steam_executable is not None:
        try:
            subprocess.Popen(
                [str(steam_executable), workshop_steam_uri(canonical)],
                shell=False,
                close_fds=True,
                **no_console_window_options(force_hidden=False),
            )
            return WorkshopOpenMethod.STEAM
        except OSError:
            # An installed-but-unlaunchable client should not strand the user.
            pass

    opened = webbrowser.open_new_tab(workshop_page_url(canonical))
    if opened is False:
        raise OSError("Windows could not open the Steam Workshop page")
    return WorkshopOpenMethod.BROWSER


__all__ = [
    "WorkshopOpenMethod",
    "find_steam_executable",
    "normalize_workshop_item_id",
    "open_workshop_item",
    "workshop_page_url",
    "workshop_steam_uri",
]
