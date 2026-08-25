from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from .compose import ComposePackageResult, SelectedMod, compose_package
from .gpl import DefinitionKind
from .package import load_mod_definition, load_package


@dataclass(frozen=True)
class PocBuildResult:
    profiles: tuple[ComposePackageResult, ...]


def build_poc_profiles(
    game_path: Path,
    input_root: Path,
    output_root: Path,
    *,
    definition_root: Path | None = None,
) -> PocBuildResult:
    """Build the Haunt-only, Alchemist-only, and combined proof profiles."""

    if definition_root is None:
        definition_root = Path(__file__).resolve().parents[2] / "profiles" / "poc"
    haunt_definition = load_mod_definition(
        definition_root / "phantoms-haunt.mod-definition.json"
    )
    alchemist_definition = load_mod_definition(
        definition_root / "alchemist.mod-definition.json"
    )

    haunt = SelectedMod(
        "haunt",
        load_package(input_root / "haunt-ap07", definition=haunt_definition),
    )
    alchemist_standalone = SelectedMod(
        "alchemist",
        load_package(
            input_root / "alchemist-standalone", definition=alchemist_definition
        ),
    )
    alchemist_resolution = SelectedMod(
        "alchemist",
        load_package(
            input_root / "alchemist-haunt-resolution",
            definition=alchemist_definition,
        ),
    )

    common_runtime = ("expanded-building-slots.cg-prefix",)
    alchemist_runtime = (
        *common_runtime,
        "alchemist.cgbrewing-secondary-controller",
        "alchemist.ap78-private-oil-rows",
        "alchemist.nm18-name-generator",
    )
    profiles = (
        compose_package(
            game_path,
            output_root / "haunt-only",
            (haunt,),
            profile_slug="haunt-only",
            display_name="CAM POC: Phantoms Haunt",
            internal_name="CAMManagerPocHaunt",
            runtime_capabilities=common_runtime,
        ),
        compose_package(
            game_path,
            output_root / "alchemist-only",
            (alchemist_standalone,),
            profile_slug="alchemist-only",
            display_name="CAM POC: Alchemist Lab",
            internal_name="CAMManagerPocAlchemist",
            runtime_capabilities=alchemist_runtime,
        ),
        # Alchemist is intentionally first: its three direct/unmapped TILE
        # slots remain fixed, while the complete typed Haunt art run can move.
        compose_package(
            game_path,
            output_root / "combined",
            (alchemist_resolution, haunt),
            profile_slug="haunt-alchemist",
            display_name="CAM POC: Haunt + Alchemist",
            internal_name="CAMManagerPocHauntAlchemist",
            resolution_owners={
                (DefinitionKind.FUNCTION, "Random_Hero_Type"): "alchemist",
                (DefinitionKind.FUNCTION, "spell_extra_value"): "alchemist",
            },
            runtime_capabilities=alchemist_runtime,
        ),
    )
    return PocBuildResult(profiles=profiles)


__all__: Sequence[str] = ("PocBuildResult", "build_poc_profiles")
