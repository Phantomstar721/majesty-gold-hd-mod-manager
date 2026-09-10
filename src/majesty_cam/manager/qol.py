from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import subprocess

from .._subprocess import no_console_window_options
from .elevation import directory_requires_elevation, run_elevated_hidden


class QolPatchError(RuntimeError):
    """Raised when a mandatory guarded QOL preflight cannot be completed."""


@dataclass(frozen=True)
class QolPatchStatus:
    name: str
    available: bool
    installed: bool
    detail: str


def inspect_qol_patch(
    *,
    name: str,
    installer: Path,
    game_path: Path,
    installed_phrase: str,
) -> QolPatchStatus:
    if not installer.is_file():
        return QolPatchStatus(
            name=name,
            available=False,
            installed=False,
            detail=f"Bundled installer is missing: {installer}",
        )
    process = _run_installer(installer, game_path, dry_run=True)
    output = (process.stdout + process.stderr).strip()
    if process.returncode != 0:
        return QolPatchStatus(
            name=name,
            available=True,
            installed=False,
            detail=output[-1000:] or f"Dry-run failed with exit code {process.returncode}",
        )
    return QolPatchStatus(
        name=name,
        available=True,
        installed=installed_phrase.casefold() in output.casefold(),
        detail=output[-1000:] or "Guarded preflight completed.",
    )


def install_qol_patch(
    *,
    name: str,
    installer: Path,
    game_path: Path,
    installed_phrase: str,
) -> QolPatchStatus:
    """Run an idempotent, version-guarded patch installer.

    This is used only after the user invokes Build/Launch.  The canonical patch
    scripts validate the executable branch and every byte site before writing.
    """

    current = inspect_qol_patch(
        name=name,
        installer=installer,
        game_path=game_path,
        installed_phrase=installed_phrase,
    )
    if current.installed:
        return current
    if not current.available:
        raise QolPatchError(current.detail)
    process = _run_installer(installer, game_path, dry_run=False)
    output = (process.stdout + process.stderr).strip()
    if process.returncode != 0:
        raise QolPatchError(
            f"{name} could not be installed: "
            f"{output[-1400:] or f'exit code {process.returncode}'}"
        )
    verified = inspect_qol_patch(
        name=name,
        installer=installer,
        game_path=game_path,
        installed_phrase=installed_phrase,
    )
    if not verified.installed:
        raise QolPatchError(f"{name} installer finished but verification did not pass")
    return verified


def inspect_required_qol(paths) -> tuple[QolPatchStatus, QolPatchStatus]:
    visitor = inspect_qol_patch(
        name="Generic Visitor Lists",
        installer=paths.generic_visitor_installer,
        game_path=paths.game_path,
        installed_phrase="already installed",
    )
    persistence = inspect_qol_patch(
        name="Remember Active Mods interoperability",
        installer=paths.remember_mods_installer,
        game_path=paths.game_path,
        installed_phrase="already installed",
    )
    return visitor, persistence


def ensure_required_qol(paths) -> tuple[QolPatchStatus, QolPatchStatus]:
    visitor = install_qol_patch(
        name="Generic Visitor Lists",
        installer=paths.generic_visitor_installer,
        game_path=paths.game_path,
        installed_phrase="already installed",
    )
    persistence = install_qol_patch(
        name="Remember Active Mods interoperability",
        installer=paths.remember_mods_installer,
        game_path=paths.game_path,
        installed_phrase="already installed",
    )
    return visitor, persistence


def _run_installer(installer: Path, game_path: Path, *, dry_run: bool) -> subprocess.CompletedProcess:
    command = [
        "powershell.exe",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(installer),
        "-GamePath",
        str(game_path),
    ]
    if dry_run:
        command.append("-DryRun")
    try:
        if not dry_run and directory_requires_elevation(game_path):
            return run_elevated_hidden(command)
        return subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=45,
            **no_console_window_options(),
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise QolPatchError(f"cannot run {installer}: {exc}") from exc


__all__ = [
    "QolPatchError",
    "QolPatchStatus",
    "ensure_required_qol",
    "inspect_qol_patch",
    "inspect_required_qol",
    "install_qol_patch",
]
