"""Catalog and guarded orchestration for standalone Majesty QOL utilities.

The manager owns no executable patch bytes here.  Every mutation is delegated
to the canonical, independently reversible PowerShell installer or restorer
shipped by the corresponding standalone repository.  This module contributes
only discovery, stock-build identification, status inspection, and idempotent
apply/remove orchestration.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
import struct
import subprocess
from typing import Callable, Sequence
import xml.etree.ElementTree as ET

from .._subprocess import no_console_window_options
from .elevation import directory_requires_elevation, run_elevated_hidden
from .paths import default_documents_root


class QolServiceError(RuntimeError):
    """Raised when a guarded utility action cannot be completed safely."""


class QolUtilityState(str, Enum):
    MISSING = "missing"
    UNSUPPORTED = "unsupported"
    AVAILABLE = "available"
    INSTALLED = "installed"
    ERROR = "error"


@dataclass(frozen=True)
class StockSectionSignature:
    name: str
    virtual_size: int
    rva: int
    raw_size: int
    raw_offset: int
    characteristics: int


@dataclass(frozen=True)
class MajestyBranch:
    key: str
    display_name: str
    version: str
    coff_timestamp: int
    stock_sections: tuple[StockSectionSignature, ...]


PUBLIC_BRANCH = MajestyBranch(
    key="public",
    display_name="Default Public Version",
    version="1.5.2.24",
    coff_timestamp=0x5897B72F,
    stock_sections=(
        StockSectionSignature(
            ".text", 0x333E7D, 0x001000, 0x334000, 0x000400, 0x60000020
        ),
        StockSectionSignature(
            ".rdata", 0x07E88C, 0x335000, 0x07EA00, 0x334400, 0x40000040
        ),
        StockSectionSignature(
            ".data", 0x05826C, 0x3B4000, 0x00C800, 0x3B2E00, 0xC0000040
        ),
        StockSectionSignature(
            ".rsrc", 0x000F34, 0x40D000, 0x001000, 0x3BF600, 0x40000040
        ),
    ),
)

BETA2_BRANCH = MajestyBranch(
    key="beta2",
    display_name="beta2 / Steam Multiplayer Support",
    version="1.5.2.28",
    coff_timestamp=0x5A8A11D5,
    stock_sections=(
        StockSectionSignature(
            ".text", 0x34C20D, 0x001000, 0x34C400, 0x000400, 0x60000020
        ),
        StockSectionSignature(
            ".rdata", 0x08395C, 0x34E000, 0x083A00, 0x34C800, 0x40000040
        ),
        StockSectionSignature(
            ".data", 0x058DF4, 0x3D2000, 0x00D200, 0x3D0200, 0xC0000040
        ),
        StockSectionSignature(
            ".rsrc", 0x000F34, 0x42B000, 0x001000, 0x3DD400, 0x40000040
        ),
    ),
)

SUPPORTED_BRANCHES = (PUBLIC_BRANCH, BETA2_BRANCH)

# Change this if status interpretation changes independently of the shipped
# scripts/specs. UI/runtime rebuilds do not change canonical patch evidence.
QOL_INSPECTION_CACHE_VERSION = 2


@dataclass(frozen=True)
class QolPatchSpec:
    key: str
    name: str
    description: str
    repository: str
    bundle_directory: str
    payload_slug: str
    install_script_name: str
    remove_script_name: str
    installed_phrase: str = ""
    preference_only: bool = False
    required_by_manager: bool = False
    license_identifier: str = "MIT"


QOL_PATCHES = (
    QolPatchSpec(
        "skip-intro",
        "Skip Intro Videos",
        "Starts Majesty at the main menu instead of playing the opening movies.",
        "majesty-gold-hd-skip-intro-videos",
        "Skip Intro Videos",
        "skip-intro-videos",
        "Install-NoIntro.ps1",
        "Uninstall-NoIntro.ps1",
        preference_only=True,
    ),
    QolPatchSpec(
        "quests-shortcut",
        "Downloadable Quests Shortcut",
        "Makes the compass icon a fixed shortcut to downloadable and custom quests.",
        "majesty-gold-hd-downloadable-quests-shortcut",
        "Downloadable Quests Shortcut",
        "downloadable-quests-shortcut",
        "Install-DownloadableQuestShortcut.ps1",
        "Restore-CustomQuestButton.ps1",
        "AlreadyPatched",
    ),
    QolPatchSpec(
        "map-drag",
        "Quest Map Drag",
        "Adds left-click drag panning to the quest map.",
        "majesty-gold-hd-quest-map-drag",
        "Quest Map Drag",
        "quest-map-drag",
        "Install-QuestMapDragPan.ps1",
        "Restore-QuestMapDragPan.ps1",
        "already installed",
    ),
    QolPatchSpec(
        "unlock-quests",
        "Unlock All Quests",
        "Makes every stock quest selectable for the current session.",
        "majesty-gold-hd-unlock-all-quests",
        "Unlock All Quests",
        "unlock-all-quests",
        "Install-UnlockAllQuests.ps1",
        "Restore-UnlockAllQuests.ps1",
        "would leave installed",
    ),
    QolPatchSpec(
        "suppress-flags",
        "Suppress All Message Flags",
        "Hides scripted message banners, sound, and forced mini-camera focus.",
        "majesty-gold-hd-suppress-all-message-flags",
        "Suppress All Message Flags",
        "suppress-all-message-flags",
        "Install-SuppressAllMessageFlags.ps1",
        "Restore-SuppressAllMessageFlags.ps1",
        "already suppressed",
    ),
    QolPatchSpec(
        "remember-mods",
        "Remember Active Mods",
        "Restores the Mods > Active list automatically on future launches.",
        "majesty-gold-hd-remember-active-mods",
        "Remember Active Mods",
        "remember-active-mods",
        "Install-ModPersistence.ps1",
        "Restore-ModPersistence.ps1",
        "already installed",
        required_by_manager=True,
    ),
    QolPatchSpec(
        "remember-speed",
        "Remember Game Speed",
        "Saves and restores the in-quest game-speed setting.",
        "majesty-gold-hd-remember-game-speed",
        "Remember Game Speed",
        "remember-game-speed",
        "Install-RememberGameSpeed.ps1",
        "Restore-RememberGameSpeed.ps1",
        "already installed",
    ),
    QolPatchSpec(
        "remember-zoom",
        "Remember Camera Zoom",
        "Saves and restores the in-quest camera zoom setting.",
        "majesty-gold-hd-remember-camera-zoom",
        "Remember Camera Zoom",
        "remember-camera-zoom",
        "Install-RememberCameraZoom.ps1",
        "Restore-RememberCameraZoom.ps1",
        "already installed",
    ),
    QolPatchSpec(
        "generic-visitors",
        "Generic Visitor Lists",
        "Lets added guilds display nonhero visitors with Majesty's normal icons "
        "and Threat Ranks.",
        "majesty-gold-hd-generic-visitor-lists",
        "Generic Visitor Lists",
        "generic-visitor-lists",
        "Install-GenericVisitorLists.ps1",
        "Restore-GenericVisitorLists.ps1",
        "Threat Ranks are already installed",
        required_by_manager=True,
    ),
    QolPatchSpec(
        "lower-tracking",
        "Lower Tracking Window",
        "Changes lower Autoscan into a Track Selected control.",
        "majesty-gold-hd-lower-tracking-window",
        "Lower Tracking Window",
        "lower-tracking-window",
        "Install-LowerTrackingWindow.ps1",
        "Restore-LowerTrackingWindow.ps1",
        "Lower Tracking Window is already installed",
    ),
)


@dataclass(frozen=True)
class ResolvedQolPatch:
    spec: QolPatchSpec
    source_kind: str
    source_root: Path | None
    install_script: Path | None
    remove_script: Path | None
    license_path: Path | None

    @property
    def apply_available(self) -> bool:
        return self.install_script is not None and self.install_script.is_file()

    @property
    def remove_available(self) -> bool:
        return self.remove_script is not None and self.remove_script.is_file()

    @property
    def license_available(self) -> bool:
        return self.license_path is not None and self.license_path.is_file()


@dataclass(frozen=True)
class QolUtilityStatus:
    patch: ResolvedQolPatch
    state: QolUtilityState
    supported: bool
    applicable: bool
    installed: bool | None
    detail: str

    @property
    def key(self) -> str:
        return self.patch.spec.key

    @property
    def name(self) -> str:
        return self.patch.spec.name

    @property
    def description(self) -> str:
        return self.patch.spec.description

    @property
    def required_for_manager(self) -> bool:
        return self.patch.spec.required_by_manager

    @property
    def can_install(self) -> bool:
        return (
            self.applicable
            and self.installed is False
            and self.patch.apply_available
        )

    @property
    def can_remove(self) -> bool:
        return (
            self.applicable
            and self.installed is True
            and self.patch.remove_available
            and not self.required_for_manager
        )

    @property
    def status(self) -> str:
        return self.state.value


@dataclass(frozen=True)
class QolCatalogSnapshot:
    game_executable: Path
    branch: MajestyBranch | None
    utilities: tuple[QolUtilityStatus, ...]

    def get(self, key: str) -> QolUtilityStatus:
        try:
            return next(item for item in self.utilities if item.key == key)
        except StopIteration as exc:
            raise KeyError(key) from exc


Runner = Callable[[Sequence[str]], subprocess.CompletedProcess[str]]
ElevationProbe = Callable[[Path], bool]


class QolService:
    """Expose and mutate independent QOL utilities through canonical scripts."""

    def __init__(
        self,
        *,
        repo_root: Path,
        game_executable: Path,
        prefs_path: Path | None = None,
        specs: Sequence[QolPatchSpec] = QOL_PATCHES,
        powershell_executable: str = "powershell.exe",
        runner: Runner | None = None,
        elevated_runner: Runner | None = None,
        elevation_probe: ElevationProbe | None = None,
    ) -> None:
        self.repo_root = repo_root.resolve(strict=False)
        self.game_executable = game_executable.resolve(strict=False)
        self.prefs_path = (prefs_path or default_prefs_path()).resolve(strict=False)
        self.specs = tuple(specs)
        self.powershell_executable = powershell_executable
        self._runner = runner or self._run_command
        self._elevated_runner = elevated_runner or run_elevated_hidden
        self._elevation_probe = elevation_probe or directory_requires_elevation

    def inspect(self) -> QolCatalogSnapshot:
        branch = detect_majesty_branch(self.game_executable)
        patches = tuple(resolve_qol_patch(self.repo_root, spec) for spec in self.specs)
        # Canonical dry-runs are independent and read-only. Bound the cold
        # inspection to three processes; retain separate PowerShell scopes and
        # each command's timeout rather than sharing script globals/runspaces.
        if branch is not None and len(patches) > 1:
            with ThreadPoolExecutor(max_workers=3) as executor:
                utilities = tuple(executor.map(lambda patch: self._inspect_resolved(patch, branch), patches))
        else:
            utilities = tuple(self._inspect_resolved(patch, branch) for patch in patches)
        return QolCatalogSnapshot(self.game_executable, branch, utilities)

    def refresh_preferences(self, snapshot: QolCatalogSnapshot) -> QolCatalogSnapshot:
        """Refresh cheap per-user settings without invalidating binary checks."""
        return QolCatalogSnapshot(snapshot.game_executable, snapshot.branch, tuple(
            self._inspect_resolved(status.patch, snapshot.branch)
            if status.patch.spec.preference_only else status
            for status in snapshot.utilities
        ))

    def inspect_patch(self, key: str) -> QolUtilityStatus:
        spec = self._spec(key)
        return self._inspect_resolved(
            resolve_qol_patch(self.repo_root, spec),
            detect_majesty_branch(self.game_executable),
        )

    def apply(
        self,
        key: str,
        *,
        current: QolUtilityStatus | None = None,
    ) -> QolUtilityStatus:
        return self._change(key, install=True, current=current)

    def remove(
        self,
        key: str,
        *,
        current: QolUtilityStatus | None = None,
    ) -> QolUtilityStatus:
        return self._change(key, install=False, current=current)

    def ensure_required(self) -> tuple[QolUtilityStatus, ...]:
        """Verify and install every helper declared as a Manager requirement."""

        results: list[QolUtilityStatus] = []
        for spec in self.specs:
            if not spec.required_by_manager:
                continue
            current = self.inspect_patch(spec.key)
            results.append(
                current
                if current.installed is True
                else self.apply(spec.key, current=current)
            )
        return tuple(results)

    def _change(
        self,
        key: str,
        *,
        install: bool,
        current: QolUtilityStatus | None = None,
    ) -> QolUtilityStatus:
        spec = self._spec(key)
        if current is None:
            current = self.inspect_patch(key)
        elif current.key != key or current.patch.spec.key != spec.key:
            raise QolServiceError(
                f"Cached QOL status does not describe {spec.name}."
            )
        if not install and current.required_for_manager:
            raise QolServiceError(
                f"{current.name} is required by Majesty Mod Manager and cannot be removed."
            )
        desired = install
        if current.installed is desired:
            return current
        if not current.applicable or current.installed is None:
            raise QolServiceError(
                f"{current.patch.spec.name} is not safely applicable: {current.detail}"
            )
        # Resolve the canonical pair again before mutation so a cached status
        # can skip its expensive dry-run without pinning the action to stale or
        # removed script paths.  The script remains the authority for branch,
        # byte-layout, ownership, and conflict checks.
        patch = resolve_qol_patch(self.repo_root, spec)
        script = patch.install_script if install else patch.remove_script
        if script is None or not script.is_file():
            verb = "installer" if install else "restorer"
            raise QolServiceError(
                f"{spec.name} canonical {verb} is unavailable."
            )

        command = self._command(spec, script)
        try:
            if (
                not spec.preference_only
                and self._elevation_probe(self.game_executable.parent)
            ):
                completed = self._elevated_runner(command)
            else:
                completed = self._runner(command)
        except (OSError, subprocess.SubprocessError) as exc:
            action = "install" if install else "remove"
            raise QolServiceError(
                f"Could not {action} {spec.name}: {exc}"
            ) from exc
        output = _combined_output(completed)
        if completed.returncode != 0:
            action = "apply" if install else "remove"
            raise QolServiceError(
                f"Could not {action} {spec.name}: "
                f"{output or f'exit code {completed.returncode}'}"
            )
        # Canonical scripts fail closed: they validate their complete target
        # set, verify locks, perform the mutation, and return nonzero on any
        # failure.  A second dry-run merely repeats their expensive parsing.
        return QolUtilityStatus(
            patch=patch,
            state=(
                QolUtilityState.INSTALLED
                if desired
                else QolUtilityState.AVAILABLE
            ),
            supported=True,
            applicable=True,
            installed=desired,
            detail="Installed." if desired else "Available.",
        )

    def _inspect_resolved(
        self,
        patch: ResolvedQolPatch,
        branch: MajestyBranch | None,
    ) -> QolUtilityStatus:
        spec = patch.spec
        if not patch.apply_available:
            return QolUtilityStatus(
                patch,
                QolUtilityState.MISSING,
                supported=spec.preference_only or branch is not None,
                applicable=False,
                installed=None,
                detail="Canonical installer is not available.",
            )

        if spec.preference_only:
            installed = intro_videos_disabled(self.prefs_path)
            return QolUtilityStatus(
                patch,
                QolUtilityState.INSTALLED if installed else QolUtilityState.AVAILABLE,
                supported=True,
                applicable=True,
                installed=installed,
                detail="Installed" if installed else "Available",
            )

        if branch is None:
            return QolUtilityStatus(
                patch,
                QolUtilityState.UNSUPPORTED,
                supported=False,
                applicable=False,
                installed=None,
                detail=(
                    "MajestyHD.exe is not the supported public 1.5.2.24 or "
                    "beta2 1.5.2.28 layout."
                ),
            )

        try:
            completed = self._runner(self._command(spec, patch.install_script, dry_run=True))
        except (OSError, subprocess.SubprocessError, QolServiceError) as exc:
            return QolUtilityStatus(
                patch,
                QolUtilityState.ERROR,
                supported=True,
                applicable=False,
                installed=None,
                detail=str(exc),
            )
        output = _combined_output(completed)
        if completed.returncode != 0:
            return QolUtilityStatus(
                patch,
                QolUtilityState.ERROR,
                supported=True,
                applicable=False,
                installed=None,
                detail=output or f"Inspection exited with code {completed.returncode}.",
            )
        lowered = output.casefold()
        installed = (
            spec.installed_phrase.casefold() in lowered
            and "wouldpatch" not in lowered
        )
        return QolUtilityStatus(
            patch,
            QolUtilityState.INSTALLED if installed else QolUtilityState.AVAILABLE,
            supported=True,
            applicable=True,
            installed=installed,
            detail=output or ("Installed" if installed else "Available"),
        )

    def _command(
        self,
        spec: QolPatchSpec,
        script: Path,
        *,
        dry_run: bool = False,
    ) -> list[str]:
        command = [
            self.powershell_executable,
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(script),
        ]
        if spec.preference_only:
            command.extend(("-PrefsPath", str(self.prefs_path)))
        else:
            command.extend(("-GamePath", str(self.game_executable.parent)))
            if dry_run:
                command.append("-DryRun")
        return command

    def _run_command(
        self, command: Sequence[str]
    ) -> subprocess.CompletedProcess[str]:
        try:
            return subprocess.run(
                list(command),
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=60,
                **no_console_window_options(),
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise QolServiceError(f"Could not run QOL script: {exc}") from exc

    def _spec(self, key: str) -> QolPatchSpec:
        try:
            return next(spec for spec in self.specs if spec.key == key)
        except StopIteration as exc:
            raise KeyError(key) from exc


def resolve_qol_patch(repo_root: Path, spec: QolPatchSpec) -> ResolvedQolPatch:
    """Prefer the complete frozen QOL suite, then the standalone canonical repo.

    During development the aggregate QOL bundle is a final fallback.  A partial
    payload is retained only when no complete apply/remove pair exists, making
    the missing restorer explicit instead of mixing scripts from revisions.
    """

    repo_root = repo_root.resolve(strict=False)
    workspace_root = repo_root.parent
    candidates = (
        (
            repo_root
            / "payload"
            / "qol"
            / "utilities"
            / spec.bundle_directory,
            "manager-payload-qol-suite",
        ),
        (repo_root / "payload" / "qol" / spec.payload_slug, "manager-payload"),
        (workspace_root / spec.repository, "standalone-repository"),
        (
            workspace_root
            / "majesty-gold-hd-qol-utilities"
            / "utilities"
            / spec.bundle_directory,
            "qol-utilities-bundle",
        ),
    )
    found: list[ResolvedQolPatch] = []
    for root, kind in candidates:
        install = _find_script(root, spec.install_script_name)
        remove = _find_script(root, spec.remove_script_name)
        license_path = _find_license(root)
        if install is None and remove is None:
            continue
        found.append(
            ResolvedQolPatch(
                spec=spec,
                source_kind=kind,
                source_root=root.resolve(strict=False),
                install_script=install,
                remove_script=remove,
                license_path=license_path,
            )
        )
    for item in found:
        if item.apply_available and item.remove_available:
            return item
    if found:
        return found[0]
    return ResolvedQolPatch(spec, "missing", None, None, None, None)


def detect_majesty_branch(path: Path) -> MajestyBranch | None:
    """Match the canonical QOL bundle's append-tolerant PE evidence."""

    try:
        data = path.read_bytes()
        if len(data) < 0x400 or data[:2] != b"MZ":
            return None
        pe_offset = struct.unpack_from("<I", data, 0x3C)[0]
        if pe_offset + 24 > len(data) or data[pe_offset : pe_offset + 4] != b"PE\0\0":
            return None
        machine, section_count = struct.unpack_from("<HH", data, pe_offset + 4)
        timestamp = struct.unpack_from("<I", data, pe_offset + 8)[0]
        optional_size = struct.unpack_from("<H", data, pe_offset + 20)[0]
        optional_offset = pe_offset + 24
        section_table = optional_offset + optional_size
        if machine != 0x014C or section_count < 4 or optional_size != 0x00E0:
            return None
        if section_table + (section_count * 40) > 0x400:
            return None
        if struct.unpack_from("<H", data, optional_offset)[0] != 0x010B:
            return None
        if struct.unpack_from("<I", data, optional_offset + 28)[0] != 0x00400000:
            return None
        section_alignment, file_alignment = struct.unpack_from(
            "<II", data, optional_offset + 32
        )
        if section_alignment != 0x1000 or file_alignment != 0x0200:
            return None
        if struct.unpack_from("<I", data, optional_offset + 60)[0] != 0x0400:
            return None

        for index in range(section_count):
            offset = section_table + (index * 40)
            raw_size, raw_offset = struct.unpack_from("<II", data, offset + 16)
            if raw_size and (raw_offset < 0x400 or raw_offset + raw_size > len(data)):
                return None

        branch = next(
            (item for item in SUPPORTED_BRANCHES if item.coff_timestamp == timestamp),
            None,
        )
        if branch is None:
            return None
        for index, expected in enumerate(branch.stock_sections):
            offset = section_table + (index * 40)
            name = data[offset : offset + 8].rstrip(b"\0").decode("ascii")
            virtual_size, rva, raw_size, raw_offset = struct.unpack_from(
                "<IIII", data, offset + 8
            )
            characteristics = struct.unpack_from("<I", data, offset + 36)[0]
            actual = StockSectionSignature(
                name,
                virtual_size,
                rva,
                raw_size,
                raw_offset,
                characteristics,
            )
            if actual != expected:
                return None
        return branch
    except (OSError, UnicodeDecodeError, struct.error, ValueError):
        return None


def default_prefs_path() -> Path:
    return default_documents_root() / "My Games" / "MajestyHD" / "MajXPrefs"


def intro_videos_disabled(prefs_path: Path) -> bool:
    try:
        root = ET.parse(prefs_path).getroot()
        node = root.find("IntroVideo")
        return node is not None and (node.text or "").strip() == "0"
    except (OSError, ET.ParseError):
        return False


def _find_script(root: Path, filename: str) -> Path | None:
    for candidate in (root / filename, root / "scripts" / filename):
        if candidate.is_file():
            return candidate.resolve()
    return None


def _find_license(root: Path) -> Path | None:
    for name in ("LICENSE.txt", "LICENSE"):
        candidate = root / name
        if candidate.is_file():
            return candidate.resolve()
    return None


def _combined_output(completed: subprocess.CompletedProcess[str]) -> str:
    text = "\n".join((completed.stdout or "", completed.stderr or "")).strip()
    return text[-2400:]


__all__ = [
    "BETA2_BRANCH",
    "MajestyBranch",
    "PUBLIC_BRANCH",
    "QOL_PATCHES",
    "QolCatalogSnapshot",
    "QolPatchSpec",
    "QolService",
    "QolServiceError",
    "QolUtilityState",
    "QolUtilityStatus",
    "ResolvedQolPatch",
    "SUPPORTED_BRANCHES",
    "StockSectionSignature",
    "default_prefs_path",
    "detect_majesty_branch",
    "intro_videos_disabled",
    "resolve_qol_patch",
]
