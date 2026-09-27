"""Executable-specific availability; unknown GOG capabilities fail before launch."""
from __future__ import annotations
from pathlib import Path
from .qol_service import GOG_BRANCH, detect_majesty_branch

GOG_RUNTIME_CAPABILITIES = frozenset((
    "generic-visitor-lists.v1",
    "expanded-building-slots.cg-prefix",
    "freestyle-cam-rebind.v1",
    "stock.name-generator.v1",
    "stock.ap78-enchantment-row.v1",
    "private-activity-text-registry.v1",
    "stock.map-fog-query.v1",
    "stock.movement-query.v1",
    "stock.native-timing.v1",
    "stock.controller-recipes.v1",
    "manager.source-exploration.v1",
    "manager.spell-origin.v1",
    "stock.equipment.v1",
    "manager.kingdom-research.v1",
    "stock.ap78-info-row.v1",
    "manager.inventory-spell-display.v1",
    "manager.overlay-movement-scale.v1",
))


def require_supported_runtime(executable: Path | None) -> None:
    """Cheap PE identity gate; native installers separately verify their sites."""
    if executable is None or detect_majesty_branch(executable) is None:
        raise ValueError("Selected runtime features require an audited default Steam, Steam beta2, or GOG executable")

def unsupported_runtime_capabilities(branch, capabilities):
    if branch == GOG_BRANCH:
        return tuple(sorted(set(capabilities) - GOG_RUNTIME_CAPABILITIES))
    return ()

def runtime_installation_identity(game_path: Path | None) -> tuple[str, str]:
    if game_path is None:
        return ("", "")
    branch = detect_majesty_branch(game_path / "MajestyHD.exe")
    return (str(game_path.resolve(strict=False)).casefold(), branch.key if branch else "unknown")
