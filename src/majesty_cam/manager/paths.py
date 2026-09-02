from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import re
import sys
import tempfile
from typing import Iterable

from .profile import canonical_remembered_path, default_profile_path


STEAM_APP_ID = "73230"
GAME_DIRECTORY_NAME = "Majesty HD"
GAME_EXECUTABLE_NAME = "MajestyHD.exe"
GAME_SELECTION_FILENAME = "game-executable.txt"


@dataclass(frozen=True)
class ManagerPaths:
    repo_root: Path
    game_path: Path
    local_mods_root: Path
    local_quests_root: Path
    workshop_roots: tuple[Path, ...]
    runtime_root: Path
    generic_visitor_installer: Path
    remember_mods_installer: Path
    remembered_path: Path
    profile_path: Path
    merged_output_root: Path

    @property
    def game_executable(self) -> Path:
        return self.game_path / GAME_EXECUTABLE_NAME

    @property
    def runtime_launcher(self) -> Path:
        return self.runtime_root / "MajestyBuildingRuntimeLauncher.exe"

    @property
    def runtime_dll(self) -> Path:
        return self.runtime_root / "MajestyBuildingRuntime.dll"

    @property
    def empty_runtime_capability_manifest(self) -> Path:
        return self.profile_path.parent / "empty-runtime-capabilities.mmcp"

    @property
    def empty_runtime_feature_registry(self) -> Path:
        return self.profile_path.parent / "empty-runtime-features.mmfr"

    @property
    def empty_controller_registry(self) -> Path:
        return self.profile_path.parent / "empty-stock-controllers.mmcr"

    @property
    def startup_cache_path(self) -> Path:
        return self.profile_path.parent / "startup-cache.json"


def detect_manager_paths(
    *,
    repo_root: Path | None = None,
    game_path: Path | None = None,
    documents_root: Path | None = None,
    local_appdata: Path | None = None,
) -> ManagerPaths:
    """Discover the current Windows install without writing outside the app."""

    if repo_root is None:
        repo_root = application_root()
    repo_root = repo_root.resolve(strict=True)
    workspace_root = repo_root.parent
    frozen = is_frozen_application()

    steam_roots = _steam_library_roots()
    if game_path is None:
        saved_executable = read_game_executable_selection(
            game_executable_selection_path(local_appdata)
        )
        game_candidates = [
            *((saved_executable.parent,) if saved_executable is not None else ()),
            Path(r"C:\Program Files (x86)\Steam\steamapps\common\Majesty HD"),
            *(root / "steamapps" / "common" / GAME_DIRECTORY_NAME for root in steam_roots),
        ]
        game_path = (
            _first_with_file(game_candidates, GAME_EXECUTABLE_NAME)
            or game_candidates[0]
        )
    game_path = game_path.resolve(strict=False)

    if documents_root is None:
        documents_root = default_documents_root()
    majesty_documents = documents_root / "My Games" / "MajestyHD"
    local_mods = majesty_documents / "Mods"
    local_quests = majesty_documents / "Quests"

    workshop_candidates = [
        Path(r"C:\Program Files (x86)\Steam\steamapps\workshop\content\73230"),
        *(root / "steamapps" / "workshop" / "content" / STEAM_APP_ID for root in steam_roots),
    ]
    workshop_roots = tuple(
        path.resolve()
        for path in _unique_paths(workshop_candidates)
        if path.is_dir()
    )

    runtime_candidates = [repo_root / "payload" / "runtime"]
    if not frozen:
        runtime_candidates.append(
            repo_root / "local" / "manager-runtime-release"
        )
    runtime_root = (
        _first_with_file(runtime_candidates, "MajestyBuildingRuntimeLauncher.exe")
        or runtime_candidates[0]
    )
    visitor_candidates = [
        repo_root
        / "payload"
        / "qol"
        / "generic-visitor-lists"
        / "Install-GenericVisitorLists.ps1"
    ]
    if not frozen:
        visitor_candidates.append(
            workspace_root
            / "majesty-gold-hd-generic-visitor-lists"
            / "scripts"
            / "Install-GenericVisitorLists.ps1"
        )
    visitor_installer = next(
        (candidate for candidate in visitor_candidates if candidate.is_file()),
        visitor_candidates[0],
    )
    remember_candidates = [
        repo_root
        / "payload"
        / "qol"
        / "remember-active-mods"
        / "Install-ModPersistence.ps1"
    ]
    if not frozen:
        remember_candidates.append(
            workspace_root
            / "majesty-gold-hd-remember-active-mods"
            / "scripts"
            / "Install-ModPersistence.ps1"
        )
    remember_installer = next(
        (candidate for candidate in remember_candidates if candidate.is_file()),
        remember_candidates[0],
    )

    return ManagerPaths(
        repo_root=repo_root,
        game_path=game_path,
        local_mods_root=local_mods,
        local_quests_root=local_quests,
        workshop_roots=workshop_roots,
        runtime_root=runtime_root.resolve(strict=False),
        generic_visitor_installer=visitor_installer.resolve(strict=False),
        remember_mods_installer=remember_installer.resolve(strict=False),
        remembered_path=canonical_remembered_path(local_appdata),
        profile_path=default_profile_path(local_appdata),
        merged_output_root=local_mods / "Majesty Mod Manager - Merged",
    )


def application_root() -> Path:
    """Return the source checkout or PyInstaller resource root.

    A packaged manager runs with code and payloads extracted under
    ``sys._MEIPASS``.  Keeping this boundary in one place lets the same manager
    services run from source without assuming a terminal or repository exists
    on a player's machine.
    """

    if is_frozen_application():
        bundled = getattr(sys, "_MEIPASS", None)
        return Path(bundled).resolve(strict=True)
    return Path(__file__).resolve().parents[3]


def default_documents_root() -> Path:
    """Return the Documents folder Windows exposes as ``shell:Personal``.

    ``Path.home() / "Documents"`` is not necessarily Majesty's Documents
    folder.  Windows Known Folder Move and similar redirection can place it
    under OneDrive or another location while leaving that legacy directory in
    place.  Majesty follows the shell folder, so the manager must do the same.
    """

    redirected = _windows_documents_root()
    if redirected is not None:
        return redirected
    return Path.home() / "Documents"


def default_desktop_root() -> Path:
    """Return the player's redirected Windows Desktop when available."""

    redirected = _windows_user_shell_folder("Desktop")
    if redirected is not None:
        return redirected
    return Path.home() / "Desktop"


def _windows_documents_root() -> Path | None:
    return _windows_user_shell_folder("Personal")


def _windows_user_shell_folder(value_name: str) -> Path | None:
    if os.name != "nt":
        return None
    try:
        import winreg

        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders",
        ) as key:
            value = winreg.QueryValueEx(key, value_name)[0]
    except (ImportError, OSError, TypeError):
        return None
    if not isinstance(value, str) or not value.strip():
        return None
    return Path(os.path.expandvars(value)).resolve(strict=False)


def is_frozen_application() -> bool:
    """Return true only for a PyInstaller process with an extraction root."""

    return bool(getattr(sys, "frozen", False) and getattr(sys, "_MEIPASS", None))


def _steam_library_roots() -> tuple[Path, ...]:
    roots: list[Path] = [Path(r"C:\Program Files (x86)\Steam")]
    if os.name == "nt":
        try:
            import winreg

            keys = (
                (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\Steam"),
                (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Valve\Steam"),
                (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Valve\Steam"),
            )
            for hive, name in keys:
                try:
                    with winreg.OpenKey(hive, name) as key:
                        roots.append(Path(winreg.QueryValueEx(key, "InstallPath")[0]))
                except OSError:
                    continue
        except (ImportError, OSError):
            pass

    expanded: list[Path] = []
    for root in _unique_paths(roots):
        expanded.append(root)
        library_file = root / "steamapps" / "libraryfolders.vdf"
        if not library_file.is_file():
            continue
        try:
            text = library_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for match in re.finditer(r'"path"\s+"([^"]+)"', text):
            expanded.append(Path(match.group(1).replace(r"\\", "\\")))
    return tuple(_unique_paths(expanded))


def _first_with_file(candidates: Iterable[Path], filename: str) -> Path | None:
    for candidate in _unique_paths(candidates):
        if (candidate / filename).is_file():
            return candidate
    return None


def game_executable_selection_path(local_appdata: Path | None = None) -> Path:
    """Return the manager-owned location for the player's chosen executable."""

    return default_profile_path(local_appdata).parent / GAME_SELECTION_FILENAME


def read_game_executable_selection(path: Path) -> Path | None:
    """Read one remembered Majesty executable without trusting stale entries."""

    if not path.is_file():
        return None
    try:
        value = path.read_text(encoding="utf-8").strip()
    except (OSError, UnicodeError):
        return None
    if not value:
        return None
    executable = Path(value).resolve(strict=False)
    if (
        executable.name.casefold() != GAME_EXECUTABLE_NAME.casefold()
        or not executable.is_file()
    ):
        return None
    return executable


def save_game_executable_selection(path: Path, executable: Path) -> Path:
    """Atomically remember a validated Majesty executable selection."""

    selected = executable.resolve(strict=True)
    if selected.name.casefold() != GAME_EXECUTABLE_NAME.casefold():
        raise ValueError(f"Choose {GAME_EXECUTABLE_NAME}, not {selected.name}.")
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent)
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(str(selected))
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()
    return selected


def _unique_paths(paths: Iterable[Path]) -> list[Path]:
    result: list[Path] = []
    seen: set[str] = set()
    for path in paths:
        key = str(path.resolve(strict=False)).casefold()
        if key in seen:
            continue
        seen.add(key)
        result.append(path)
    return result


__all__ = [
    "ManagerPaths",
    "GAME_EXECUTABLE_NAME",
    "application_root",
    "default_desktop_root",
    "default_documents_root",
    "detect_manager_paths",
    "game_executable_selection_path",
    "is_frozen_application",
    "read_game_executable_selection",
    "save_game_executable_selection",
]
