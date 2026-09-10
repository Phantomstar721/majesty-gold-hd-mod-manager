from __future__ import annotations

import base64
from dataclasses import dataclass, replace
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import re
import shutil
import struct
import subprocess
import tempfile
from typing import Iterable, Mapping, Sequence
import uuid
import xml.etree.ElementTree as ET

from ._subprocess import no_console_window_options
from .art import (
    ArtArchiveAnalysis,
    ArtFormatError,
    ArtRelocationReport,
    ImagRelocationReport,
    ParsedImag,
    PaletteRelocationReport,
    PositionalAllocationReport,
    PositionalCollision,
    PositionalSectionDelta,
    UnprovenReferenceError,
    allocate_collision_free_ranges,
    analyze_art_archive,
    find_positional_collisions,
    parse_best_imag_tile_references,
    parse_imag_tile_references,
    parse_stock_imag_tile_references,
    rewrite_parsed_imag_entries,
    rewrite_stock_imag_entries,
    rewrite_tile_palette_indices,
    validate_external_palette_closure,
)
from .cam import CamArchive, CamEntry, CamSection, pad_name, read_cam
from .descriptions import (
    DescriptionFormatError,
    DescriptionKey,
    DescriptionMergeResult,
    DescriptionRecord,
    DescriptionsDocument,
    merge_descriptions,
    parse_descriptions,
    serialize_descriptions,
)
from .gpl import (
    DefinitionKind,
    GplProjectSourceSet,
    ParsedSemanticSource,
    SemanticConflict,
    SemanticItem,
    SemanticMergeResult,
    add_controlled_follower_movement_adjustments,
    add_hero_quest_lifecycle_callbacks,
    add_inventory_death_drop_exclusions,
    add_purchase_bazaar_tail_callbacks,
    add_purchase_equipment_tail_callbacks,
    merge_sources,
    parse_dat,
    parse_gpl,
    require_complete_semantic_coverage,
)
from .gpl_features import (
    StockControlledFollowerSpeedSync,
    StockGplmxPurchaseBazaarTail,
    StockGplmxPurchaseEquipmentTail,
    StockHeroQuestLifecycle,
)
from .intent_text import (
    ActivityTextDiscoveryPackage,
    INTENT_REGISTRY_RELATIVE_PATH,
    IntentTextError,
    PrivateActivityTextBinding,
    PrivateActivityTextRecord,
    audit_private_activity_text_resolver_aliases,
    collect_exact_integer_expressions,
    collect_integer_expression_environment,
    decode_intent_registry,
    discover_private_activity_text_bindings,
    encode_intent_registry,
    rewrite_private_activity_text_resolver_calls,
    rewrite_unowned_private_activity_text_resolver_calls,
)
from .package import (
    CamLoad,
    DescriptionsLoad,
    GplLoad,
    ModPackage,
    OpaqueLoad,
    PackagePath,
    StringsLoad,
    load_package,
    parse_mod_definition,
)
from .strings import (
    StringKey,
    StringRecord,
    StringsFormatError,
    StringsMergeResult,
    load_effective_stock_strings,
    load_strings,
    merge_strings,
    serialize_string_records,
)
from .stock_art import (
    StockArtError,
    collapse_art_archives,
    load_stock_art_lineages,
)
from .stock_cam import (
    STOCK_NAMED_CAM_SECTIONS,
    StockCamError,
    load_effective_stock_named_resources,
)
from .stock_gpl import (
    StockGplError,
    load_verified_stock_semantic_sources,
)
from .semantic_diff3 import join_logical_lines, split_logical_lines
from .runtime_capabilities import (
    PRIVATE_ACTIVITY_TEXT_RUNTIME_CAPABILITY,
    RUNTIME_CAPABILITY_MANIFEST_RELATIVE_PATH,
    decode_runtime_capability_manifest,
    encode_runtime_capability_manifest,
)
from .runtime_features import (
    ENCHANTMENT_ROW_RUNTIME_CAPABILITY,
    NAME_GENERATOR_RUNTIME_CAPABILITY,
    RUNTIME_FEATURE_REGISTRY_RELATIVE_PATH,
    EnchantmentRowFeature,
    NameGeneratorFeature,
    RuntimeFeature,
    RuntimeFeatureRegistry,
    decode_runtime_feature_registry,
    derive_feature_runtime_capabilities,
    encode_runtime_feature_registry,
    legacy_runtime_features,
    normalize_runtime_features,
)
from .stock_controller_features import (
    LEGACY_ALCHEMIST_CONTROLLER_CAPABILITY,
    ControllerFeature,
    ControllerFeatureError,
    StockAp08Mx05QuestBoardPanel,
    StockAp10Ap69SecondaryPanel,
    StockAp41Fl00HostileMonsterFlag,
    StockMx09Ap41RewardPanel,
    StockMx04Mx05OccupantActionPanel,
    StockMx22BuildingOpenToggle,
    StockAp17UpgradeResearchGate,
    StockAp22ResourceMeter,
    StockAp24RageCommandAction,
    StockAp24TimedRageAction,
    StockAp69SovereignTargetAction,
    StockAp99ResearchRow,
    UpgradeRequirement,
    legacy_controller_features,
    normalize_controller_features,
)
from .stock_controller_registry import (
    CONTROLLER_REGISTRY_RELATIVE_PATH,
    QUEST_REFRESH_COIN_CONTROL_ID,
    QUEST_REFRESH_CONTROL_ID,
    QUEST_REFRESH_PRICE_BINDING_ID,
    STOCK_CONTROLLER_RUNTIME_CAPABILITY,
    ControllerRegistryError,
    ResolvedControllerRegistry,
    decode_stock_controller_registry,
    encode_stock_controller_registry,
    resolve_stock_controller_registry,
)
from .strt import (
    StrtAncestryError,
    StrtDelta,
    StrtRecord,
    StrtRowResolution,
    StrtStockRelativeProof,
    StrtTable,
    merge_strt_stock_relative,
    parse_strt,
    prove_strt_stock_relative_delta,
)
from .tables import (
    BdepDelta,
    BdepRowResolution,
    TableAncestryError,
    TableFormatError,
    TableMergeConflict,
    merge_bdep_stock_relative,
)


class ComposeError(ValueError):
    """Raised when selected packages cannot be composed without guessing."""


@dataclass(frozen=True)
class StockComposeInput:
    """One exact installed-stock file consumed by package composition."""

    relative_path: Path
    present: bool
    size: int
    sha256: str


_STOCK_COMPOSE_FIXED_INPUTS = (
    Path("Data/textdata.cam"),
    Path("Data/miscdata.cam"),
    Path("Data/maindata.cam"),
    Path("Data/interfacedata.cam"),
    Path("DataMX/mx_gpltext.cam"),
    Path("DataMX/mx_miscdata.cam"),
    Path("SDK/Gplbcc.exe"),
    Path("SDK/OriginalQuests/GPLMx/mx_defines.gpl"),
)
_STOCK_COMPOSE_OPTIONAL_INPUTS = (
    # These expansion art archives are not present in every supported install,
    # but composition consumes them when they exist.  Their absence is itself
    # an input state and therefore must be fingerprinted deterministically.
    Path("DataMX/mx_maindata.cam"),
    Path("DataMX/mx_interfacedata.cam"),
    # Required only when a selected package requests the AP08/MX05 quest-board
    # recipe. Its presence/hash is still part of every prepared plan so that a
    # later selection cannot silently consume a different stock template.
    Path("DataMX/mx_textdata.cam"),
)
_STOCK_COMPOSE_XML_DIRECTORIES = (
    Path("SDK/OriginalQuests/Data"),
    Path("SDK/OriginalQuests/DataMX"),
)

_FIXED_GENERATED_CAM_SECTIONS = {
    "merged_textdata.cam": (b"SMNU", b"STRT"),
    "merged_gpltext.cam": (b"STRT",),
    "merged_miscdata.cam": (b"DATA",),
    "merged_audio.cam": (b"WAVE",),
    "merged_sounddesc.cam": (b"DSND",),
}
_GENERATED_ART_CAM_NAME = re.compile(
    r"merged_(?:maindata|interfacedata|art-[0-9]{2,})\.cam"
)

# These are the exact primary TILE fields of the stock cursor lifecycles exposed
# by the generic controller-feature schema.  Authors may replace only these
# visible glyph frames; the complete stock set body and every auxiliary frame
# must remain from one coherent stock dataset.
_HOSTILE_MONSTER_FLAG_CURSOR_TEMPLATE = (
    1005,
    frozenset((0x78, 0xA8, 0xE0)),
    "Attack",
)
_SOVEREIGN_TARGET_CURSOR_TEMPLATE = (
    1014,
    frozenset((0x7C, 0xAC, 0xE4, 0x10C)),
    "Lightning",
)


@dataclass(frozen=True)
class SelectedMod:
    alias: str
    package: ModPackage
    # Ordinary Mods remain independently enabled. Their readable text resources
    # participate only so the generated load-last patch can reconcile collisions.
    semantic_passthrough: bool = False
    # ``None`` means all authored CAM records. Ordinary Mods receive an exact
    # collided-record set during reconciliation so unrelated records remain
    # owned and loaded solely by their original component.
    cam_resource_filter: frozenset[tuple[bytes, bytes]] | None = None
    # Reconciled ordinary components may load the same named CAM key more than
    # once. Majesty uses the last manifest directive, so a key-only filter
    # would accidentally resurrect every earlier copy at build time. When
    # present, this exact source/key set preserves the component's effective
    # native last-write view.
    cam_resource_source_filter: frozenset[
        tuple[bytes, bytes, Path, int, int, int]
    ] | None = None
    # Art CAMs are positional archives and cannot be safely reduced to the
    # named-record filter above. ``None`` retains the historical all-art
    # behavior for merge inputs, but means no art for semantic passthrough
    # inputs. Reconciliation must explicitly opt a Standard package's exact
    # declared CAM paths into the generated load-last patch.
    art_archive_filter: frozenset[Path] | None = None
    # ``None`` fingerprints the complete package as before. Reconciled
    # multi-component packages may instead supply the exact files belonging to
    # the selected component so the report never attributes sibling content.
    report_files: tuple[Path, ...] | None = None
    # Reconciliation may quarantine ambiguous legacy source definitions while
    # conservatively auditing the compiled target. Keep that exact prepared
    # semantic view through composition instead of reparsing the raw source
    # differently at the build boundary.
    semantic_sources: tuple[ParsedSemanticSource, ...] | None = None
    # Complete panel FourCC namespace observed before passthrough CAM filtering.
    # These IDs reserve allocator space without causing the Standard resource
    # itself to be emitted into the generated profile.
    reserved_dialog_ids: frozenset[bytes] = frozenset()


@dataclass(frozen=True)
class ScopedSemanticResolution:
    """One explicit semantic result and the mod owners it is allowed to cover."""

    item: SemanticItem
    participant_owners: frozenset[str]

    def __post_init__(self) -> None:
        if not self.participant_owners:
            raise ValueError("semantic resolution participants cannot be empty")


@dataclass(frozen=True)
class ScopedNamedResourceResolution:
    """One chosen named CAM record and the owners whose collision it resolves."""

    entry: CamEntry
    participant_owners: frozenset[str]
    selected_owner: str | None = None

    def __post_init__(self) -> None:
        if not self.participant_owners:
            raise ValueError("named CAM resolution participants cannot be empty")
        if (
            self.selected_owner is not None
            and self.selected_owner not in self.participant_owners
        ):
            raise ValueError("selected named CAM owner must be a participant")


@dataclass(frozen=True)
class ScopedArtResourceResolution:
    """One selected owner for an IMAG key within one stock art lineage."""

    selected_owner: str
    participant_owners: frozenset[str]

    def __post_init__(self) -> None:
        if not self.participant_owners:
            raise ValueError("art resolution participants cannot be empty")
        if self.selected_owner not in self.participant_owners:
            raise ValueError("selected art owner must be a participant")


@dataclass(frozen=True)
class CamResource:
    owner: str
    source: Path
    cam_order: int
    section_order: int
    entry_order: int
    section: bytes
    entry: CamEntry

    @property
    def key(self) -> bytes:
        return self.entry.name[:4]


@dataclass(frozen=True)
class OpaqueCamSection:
    """One native Standard-Mod CAM section outside generated namespaces."""

    source: Path
    extension: bytes


@dataclass(frozen=True)
class PackageInventory:
    selected: SelectedMod
    cams: tuple[Path, ...]
    descriptions: tuple[Path, ...]
    gpl_loads: tuple[GplLoad, ...]
    resources: tuple[CamResource, ...]
    strings: tuple[Path, ...] = ()
    semantic_sources: tuple[ParsedSemanticSource, ...] | None = None
    dataset_bases: tuple[str, ...] = ("Any",)
    opaque_loads: tuple[OpaqueLoad, ...] = ()
    opaque_cam_sections: tuple[OpaqueCamSection, ...] = ()
    # Exact manifest CAM paths eligible for positional art composition. This
    # deliberately differs from ``cams``, which remains the complete declared
    # inventory used by reconciliation and diagnostics.
    art_cams: tuple[Path, ...] | None = None


@dataclass(frozen=True)
class NamedMergeSelection:
    section: bytes
    key: bytes
    owners: tuple[str, ...]
    entry: CamEntry


@dataclass(frozen=True)
class StrtMergeSelection:
    key: bytes
    entry: CamEntry
    deltas: tuple[StrtDelta, ...]


@dataclass(frozen=True)
class TextMergeResult:
    text_archive: CamArchive
    gpltext_archive: CamArchive
    whole_tables: tuple[StrtMergeSelection, ...]
    named: tuple[NamedMergeSelection, ...]
    dialog_renames: tuple[tuple[str, bytes, bytes], ...]
    private_activity_texts: tuple[PrivateActivityTextRecord, ...]


@dataclass(frozen=True)
class BdepComposeResult:
    archive: CamArchive
    deltas: tuple[BdepDelta, ...]


@dataclass(frozen=True)
class GplComposeResult:
    source_set: GplProjectSourceSet
    conflicts: tuple[SemanticConflict, ...]
    resolution_owners: tuple[tuple[DefinitionKind, str, str], ...]
    resolution_sources: tuple[tuple[DefinitionKind, str, str], ...]
    inventory_death_drop_exclusions: tuple[str, ...]
    purchase_equipment_tail_callbacks: tuple[tuple[str, str, str], ...] = ()
    purchase_bazaar_tail_callbacks: tuple[tuple[str, str, str], ...] = ()
    controlled_follower_speed_sync: tuple[
        tuple[str, str, str, int, tuple[str, ...]], ...
    ] = ()
    hero_quest_lifecycles: tuple[
        tuple[str, str, tuple[str, ...], str, str, str], ...
    ] = ()


@dataclass(frozen=True)
class GplFeatureEvidence:
    lifecycle: str
    mod_id: str
    feature_key: str
    callback_symbol: str
    movement_rate_modifier_per_tier: int = 0
    marker_effectors: tuple[str, ...] = ()
    hero_scripts: tuple[str, ...] = ()
    reset_callback_symbol: str = ""
    death_callback_symbol: str = ""


@dataclass(frozen=True)
class CompiledGpl:
    target: Path
    size: int
    stdout: str
    stderr: str


@dataclass(frozen=True)
class ArtDomainComposeResult:
    domain: str
    archive: CamArchive
    analyses: tuple[ArtArchiveAnalysis, ...]
    tile_collisions: tuple[PositionalCollision, ...]
    palette_collisions: tuple[PositionalCollision, ...]
    report: ArtRelocationReport


@dataclass(frozen=True)
class DescriptionStockDelta:
    owner: str
    key: DescriptionKey
    kind: str
    mod_source: str
    stock_source: str | None


@dataclass(frozen=True)
class ResolvedBuildingDialog:
    """One author declaration resolved to source and manager-owned FourCCs."""

    owner: str
    local_name: str
    source_dialog_id: bytes
    resolved_dialog_id: bytes


@dataclass(frozen=True)
class ResolvedControllerPanel:
    """One package-local secondary panel resolved for merged output."""

    owner: str
    raw_panel_key: str
    qualified_panel_key: str
    raw_parent_building: str
    qualified_parent_building: str
    source_dialog_id: bytes
    resolved_parent_dialog_id: bytes
    resolved_child_dialog_id: bytes


@dataclass(frozen=True)
class ResolvedControllerToggle:
    """One package-local MX22 toggle resolved onto its custom building."""

    owner: str
    raw_toggle_key: str
    qualified_toggle_key: str
    raw_parent_building: str
    resolved_parent_dialog_id: bytes


@dataclass(frozen=True)
class ControllerKeyMapping:
    """Auditable package-local to manager-global logical-key mapping."""

    owner: str
    mod_id: str
    kind: str
    raw_key: str
    qualified_key: str


@dataclass(frozen=True)
class ControllerComposeResult:
    registry: ResolvedControllerRegistry
    panels: tuple[ResolvedControllerPanel, ...]
    key_mappings: tuple[ControllerKeyMapping, ...]
    toggles: tuple[ResolvedControllerToggle, ...] = ()


@dataclass(frozen=True)
class ComposePackageResult:
    output_root: Path
    manifest: Path
    mod_id: str
    profile_slug: str
    report: Path
    validation: Mapping[str, object]


_PROFILE_NAMESPACE = uuid.UUID("634a1b44-a04c-5f83-bb0f-8ace03b8900b")
_PROFILE_SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


_SUPPORTED_CAM_SECTIONS = frozenset(
    (b"SMNU", b"STRT", b"DATA", b"IMAG", b"TILE", b"SPLT", b"PALT", b"DSND", b"WAVE")
)
_NAMED_SECTIONS = frozenset((b"SMNU", b"STRT", b"IMAG", b"DSND", b"WAVE"))
_NATIVE_LAST_WRITE_SECTIONS = frozenset(
    (b"SMNU", b"STRT", b"DATA", b"DSND", b"WAVE")
)
_WHOLE_STRT = {
    b"UNTN": ((("Original", Path("Data/textdata.cam")),), "id"),
    b"ACTN": ((("Original", Path("Data/textdata.cam")),), "id"),
    b"QITM": (
        (
            ("Original", Path("Data/gpltext.cam")),
            ("Northern Expansion", Path("DataMX/mx_gpltext.cam")),
        ),
        "index",
    ),
    b"AITX": (
        (
            ("Original", Path("Data/gpltext.cam")),
            ("Northern Expansion", Path("DataMX/mx_gpltext.cam")),
        ),
        "index",
    ),
    # Help text is addressed by its embedded FourCC ID (for example hAL0 and
    # hPH0), not by the physical append slot used by an individual builder.
    b"HPTX": (
        (
            ("Original", Path("Data/gpltext.cam")),
            ("Northern Expansion", Path("DataMX/mx_gpltext.cam")),
        ),
        "id",
    ),
}
_TEXT_WHOLE_ORDER = (b"UNTN", b"ACTN")
_GPLTEXT_WHOLE_ORDER = (b"QITM", b"AITX", b"HPTX")


def _selected_art_archive_paths(
    selected: SelectedMod,
    declared_cams: Sequence[Path],
) -> tuple[Path, ...]:
    """Resolve the explicit positional-art boundary for one package.

    A merge input keeps the historical behavior of offering every declared
    CAM to the typed art composer. A semantic-passthrough Standard offers none
    unless reconciliation names exact declared paths. Unknown or out-of-root
    selections fail closed instead of silently widening the boundary.
    """

    requested = selected.art_archive_filter
    if requested is None:
        return () if selected.semantic_passthrough else tuple(declared_cams)

    root = selected.package.root.resolve()
    declared_by_path = {path.resolve(): path for path in declared_cams}
    normalized: set[Path] = set()
    for raw_path in requested:
        path = raw_path if raw_path.is_absolute() else root / raw_path
        resolved = path.resolve()
        try:
            resolved.relative_to(root)
        except ValueError as exc:
            raise ComposeError(
                f"{selected.alias}: art archive selection escapes package root: "
                f"{raw_path}"
            ) from exc
        if resolved not in declared_by_path:
            raise ComposeError(
                f"{selected.alias}: art archive selection is not a declared CAM: "
                f"{raw_path}"
            )
        normalized.add(resolved)
    return tuple(
        path for path in declared_cams if path.resolve() in normalized
    )


def inventory_package(selected: SelectedMod) -> PackageInventory:
    """Read one safe package into an ordered, fail-closed resource inventory."""

    if not selected.alias or selected.alias.casefold() != selected.alias:
        raise ComposeError(
            f"mod alias must be non-empty lowercase text: {selected.alias!r}"
        )

    cam_paths: list[Path] = []
    description_paths: list[Path] = []
    gpl_loads: list[GplLoad] = []
    string_paths: list[Path] = []
    resources: list[CamResource] = []
    opaque_loads: list[OpaqueLoad] = []
    opaque_cam_sections: list[OpaqueCamSection] = []
    source_filter = None
    if selected.cam_resource_source_filter is not None:
        resolved_filter_paths: dict[Path, Path] = {}
        source_filter = set()
        for (
            section,
            key,
            path,
            cam_order,
            section_order,
            entry_order,
        ) in selected.cam_resource_source_filter:
            resolved_path = resolved_filter_paths.get(path)
            if resolved_path is None:
                resolved_path = path.resolve()
                resolved_filter_paths[path] = resolved_path
            source_filter.add(
                (
                    section,
                    key,
                    resolved_path,
                    cam_order,
                    section_order,
                    entry_order,
                )
            )

    for dataset_index, dataset in enumerate(selected.package.datasets):
        if dataset.base.casefold() != "any" and not selected.semantic_passthrough:
            raise ComposeError(
                f"{selected.alias}: Dataset[{dataset_index}] base={dataset.base!r} "
                "is not supported by the proof-of-concept composer"
            )
        for load in dataset.loads:
            for directive in load.directives:
                if isinstance(directive, CamLoad):
                    source = directive.file.absolute_path
                    cam_order = len(cam_paths)
                    cam_paths.append(source)
                    archive = read_cam(source)
                    resolved_source = (
                        source.resolve() if source_filter is not None else None
                    )
                    for section_order, section in enumerate(archive.sections):
                        if section.extension not in _SUPPORTED_CAM_SECTIONS:
                            if not selected.semantic_passthrough:
                                raise ComposeError(
                                    f"{selected.alias}: unsupported CAM section "
                                    f"{section.extension!r} in {source}"
                                )
                            opaque_cam_sections.append(
                                OpaqueCamSection(source, section.extension)
                            )
                            continue
                        for entry_order, entry in enumerate(section.entries):
                            if source_filter is not None:
                                resource_identity = (
                                    section.extension,
                                    entry.name[:4],
                                    resolved_source,
                                    cam_order,
                                    section_order,
                                    entry_order,
                                )
                                if resource_identity not in source_filter:
                                    continue
                            elif (
                                selected.cam_resource_filter is not None
                                and (section.extension, entry.name[:4])
                                not in selected.cam_resource_filter
                            ):
                                continue
                            resources.append(
                                CamResource(
                                    owner=selected.alias,
                                    source=source,
                                    cam_order=cam_order,
                                    section_order=section_order,
                                    entry_order=entry_order,
                                    section=section.extension,
                                    entry=entry,
                                )
                            )
                elif isinstance(directive, DescriptionsLoad):
                    description_paths.append(directive.file.absolute_path)
                elif isinstance(directive, GplLoad):
                    gpl_loads.append(directive)
                elif isinstance(directive, StringsLoad):
                    string_paths.append(directive.file.absolute_path)
                elif isinstance(directive, OpaqueLoad):
                    if not selected.semantic_passthrough:
                        raise ComposeError(
                            f"{selected.alias}: unsupported manifest directive "
                            f"{directive.tag}"
                        )
                    opaque_loads.append(directive)
                else:  # pragma: no cover - package parser owns this closed union
                    raise ComposeError(
                        f"{selected.alias}: unsupported manifest directive "
                        f"{type(directive).__name__}"
                    )

    if not cam_paths and not selected.semantic_passthrough:
        raise ComposeError(f"{selected.alias}: package has no CAM resources")
    if not gpl_loads and not selected.semantic_passthrough:
        raise ComposeError(f"{selected.alias}: package has no GPL load")
    return PackageInventory(
        selected=selected,
        cams=tuple(cam_paths),
        descriptions=tuple(description_paths),
        gpl_loads=tuple(gpl_loads),
        strings=tuple(string_paths),
        resources=collapse_native_cam_resources(resources),
        semantic_sources=selected.semantic_sources,
        dataset_bases=tuple(dataset.base for dataset in selected.package.datasets),
        art_cams=_selected_art_archive_paths(selected, cam_paths),
        opaque_loads=tuple(opaque_loads),
        opaque_cam_sections=tuple(opaque_cam_sections),
    )


def collapse_native_cam_resources(
    resources: Iterable[CamResource],
) -> tuple[CamResource, ...]:
    """Apply one package's native last-write semantics to keyed registries.

    Majesty evaluates a component's CAM directives in manifest order. For a
    keyed registry, a later record from that same component replaces its
    earlier value; those records are not independent providers and must never
    become a manager conflict. Positional art is deliberately excluded and
    remains under the typed stock-lineage composer.
    """

    ordered = tuple(resources)
    last_position: dict[tuple[str, bytes, bytes], int] = {}
    for index, resource in enumerate(ordered):
        if resource.section in _NATIVE_LAST_WRITE_SECTIONS:
            last_position[(resource.owner, resource.section, resource.key)] = index
    return tuple(
        resource
        for index, resource in enumerate(ordered)
        if resource.section not in _NATIVE_LAST_WRITE_SECTIONS
        or last_position[(resource.owner, resource.section, resource.key)] == index
    )


def merge_named_resources(
    resources: Iterable[CamResource],
    section: bytes,
    *,
    renames: Mapping[tuple[str, bytes], bytes] | None = None,
    resolutions: Mapping[
        tuple[bytes, bytes], ScopedNamedResourceResolution
    ] | None = None,
    stock_resources: Mapping[tuple[bytes, bytes], bytes] | None = None,
) -> tuple[tuple[CamEntry, ...], tuple[NamedMergeSelection, ...]]:
    """Union a named CAM registry using its native four-byte resource key."""

    if section not in _NAMED_SECTIONS:
        raise ComposeError(f"section {section!r} is not a supported named registry")
    resources = tuple(resources)
    rename_map = dict(renames or {})
    resolution_map = dict(resolutions or {})
    stock_map = dict(stock_resources or {})
    # Majesty applies one component's CAM directives in manifest order.  A
    # later record with the same native key replaces its earlier sibling; it is
    # not a cross-mod conflict.  Collapse that native view before applying any
    # manager-owned renames or comparing different owners.
    last_native_position: dict[tuple[str, bytes], int] = {}
    for index, resource in enumerate(resources):
        if resource.section == section:
            last_native_position[(resource.owner, resource.key)] = index
    resources = tuple(
        resource
        for index, resource in enumerate(resources)
        if resource.section != section
        or last_native_position[(resource.owner, resource.key)] == index
    )
    ordered: list[tuple[bytes, CamEntry, list[str]]] = []
    positions: dict[bytes, int] = {}
    owner_keys: set[tuple[str, bytes]] = set()

    for resource in resources:
        if resource.section != section:
            continue
        old_key = resource.key
        key = rename_map.get((resource.owner, old_key), old_key)
        if len(key) != 4:
            raise ComposeError(
                f"{resource.owner}: renamed {section!r} key must be four bytes: {key!r}"
            )
        owner_key = (resource.owner, key)
        if owner_key in owner_keys:
            raise ComposeError(
                f"{resource.owner}: duplicate {section.decode('ascii')} resource "
                f"{_display_key(key)} across selected CAMs"
            )
        owner_keys.add(owner_key)

        entry = resource.entry
        if key != old_key:
            entry = CamEntry(name=key + entry.name[4:], data=entry.data)
        resolution = resolution_map.get((section, key))
        if resolution is not None and resource.owner in resolution.participant_owners:
            if resolution.entry.name[:4] != key:
                raise ComposeError(
                    f"named CAM resolution for {section!r}/{key!r} has a mismatched key"
                )
            entry = resolution.entry
        elif stock_map.get((section, key)) == entry.data:
            # The generated profile loads last. Re-emitting an unchanged stock
            # record would be an active override that could erase a normally
            # loaded Standard Mod; ancestry-only records are true no-ops.
            continue
        existing_position = positions.get(key)
        if existing_position is None:
            positions[key] = len(ordered)
            ordered.append((key, entry, [resource.owner]))
            continue
        existing_key, existing_entry, owners = ordered[existing_position]
        if existing_entry.data != entry.data:
            raise ComposeError(
                f"conflicting {section.decode('ascii')} resource "
                f"{_display_key(existing_key)}: {', '.join((*owners, resource.owner))}"
            )
        owners.append(resource.owner)

    entries = tuple(item[1] for item in ordered)
    selections = tuple(
        NamedMergeSelection(
            section=section,
            key=key,
            owners=tuple(owners),
            entry=entry,
        )
        for key, entry, owners in ordered
    )
    for (resolution_section, key), resolution in resolution_map.items():
        if resolution_section != section:
            continue
        actual_owners = {
            resource.owner
            for resource in resources
            if rename_map.get((resource.owner, resource.key), resource.key) == key
        }
        missing = resolution.participant_owners.difference(actual_owners)
        if missing:
            raise ComposeError(
                f"named CAM resolution for {section!r}/{key!r} names absent owners: "
                + ", ".join(sorted(missing))
            )
    return entries, selections


_MX05_NATIVE_LIST_CONTROL_ID = 0x1388
_MX05_NATIVE_ACTION_CONTROL_ID = 0x138B
_MX05_NATIVE_COIN_CONTROL_ID = 0x138C
_MX05_NATIVE_SCROLL_CONTROL_ID = 0x1392
_MX05_NATIVE_PRICE_CONTROL_ID = 0x1F46


def _split_smnu_records(payload: bytes, *, owner: str, label: str) -> tuple[bytes, ...]:
    """Split Majesty's DWORD-aligned SMNU stream at literal record sentinels."""

    if not payload or len(payload) % 4:
        raise ComposeError(f"{owner}: SMNU/{label} is not a DWORD-aligned stream")
    records: list[bytes] = []
    start = 0
    for offset in range(0, len(payload), 4):
        if payload[offset:offset + 4] != b"\xff\xff\xff\xff":
            continue
        records.append(payload[start:offset + 4])
        start = offset + 4
    if start != len(payload) or not records or records[-1] != b"\xff\xff\xff\xff":
        raise ComposeError(f"{owner}: SMNU/{label} has an invalid record boundary")
    return tuple(records)


def _smnu_record_index(
    records: Sequence[bytes], control_id: int, *, owner: str, label: str
) -> int:
    token = struct.pack("<I", control_id)
    matches = [
        index
        for index, record in enumerate(records[:-1])
        if any(record[offset:offset + 4] == token for offset in range(0, len(record), 4))
    ]
    if len(matches) != 1:
        raise ComposeError(
            f"{owner}: SMNU/{label} must contain exactly one literal "
            f"control 0x{control_id:08X}; found {len(matches)}"
        )
    return matches[0]


def _patch_mx05_record(
    record: bytes,
    *,
    expected_size: int,
    expected_rect: tuple[int, int, int, int],
    rectangle: tuple[int, int, int, int],
    owner: str,
    label: str,
    control_offset: int | None = None,
    control_id: int | None = None,
    string_patches: Mapping[int, int] | None = None,
) -> bytes:
    if (
        len(record) != expected_size
        or record[-4:] != b"\xff\xff\xff\xff"
        or struct.unpack_from("<4I", record, 8) != expected_rect
    ):
        raise ComposeError(
            f"{owner}: stock MX05 {label} record shape has changed"
        )
    result = bytearray(record)
    struct.pack_into("<4I", result, 8, *rectangle)
    if control_offset is not None and control_id is not None:
        struct.pack_into("<I", result, control_offset, control_id)
    for offset, value in (string_patches or {}).items():
        struct.pack_into("<I", result, offset, value)
    return bytes(result)


def _append_quest_refresh_strings(
    payload: bytes, *, owner: str, label: str
) -> tuple[bytes, tuple[int, int, int, int]]:
    try:
        table = parse_strt(payload)
    except ValueError as exc:
        raise ComposeError(f"{owner}: STRT/{label} is invalid: {exc}") from exc
    if len(table.records) > 0xFFFB:
        raise ComposeError(f"{owner}: STRT/{label} has no room for Refresh strings")
    first = len(table.records)
    texts = (
        b"REFRESH",
        b"Replace all available quests.",
        b"0",
        b"Gold required to refresh the quest board.",
    )
    records = tuple(table.records) + tuple(
        StrtRecord(string_id=first + index, text=text)
        for index, text in enumerate(texts)
    )
    return StrtTable(version=table.version, records=records).to_bytes(), (
        first, first + 1, first + 2, first + 3,
    )


def _materialize_mx05_quest_refresh_row(
    game_path: Path,
    payload: bytes,
    strings: tuple[int, int, int, int],
    *,
    owner: str,
    label: str,
) -> bytes:
    """Add a second literal MX05 bottom action row for quest-board Refresh.

    The package supplies an unchanged MX05 panel. The Manager shortens the
    native list/scrollbar by one stock row, moves the native selected action up
    by exactly 25 pixels, and appends stock-cloned action/coin/price records at
    the original bottom coordinates. No AP54 control or parent-panel workaround
    is accepted or retained.
    """

    stock_payload = _require_cam_entry(
        game_path / Path("DataMX/mx_textdata.cam"), b"SMNU", b"MX05"
    ).data
    stock = list(_split_smnu_records(stock_payload, owner="stock", label="MX05"))
    records = list(_split_smnu_records(payload, owner=owner, label=label))
    ids = (
        _MX05_NATIVE_LIST_CONTROL_ID,
        _MX05_NATIVE_ACTION_CONTROL_ID,
        _MX05_NATIVE_COIN_CONTROL_ID,
        _MX05_NATIVE_SCROLL_CONTROL_ID,
        _MX05_NATIVE_PRICE_CONTROL_ID,
    )
    stock_indices = {
        control: _smnu_record_index(stock, control, owner="stock", label="MX05")
        for control in ids
    }
    indices = {
        control: _smnu_record_index(records, control, owner=owner, label=label)
        for control in ids
    }
    for control in ids:
        if records[indices[control]] != stock[stock_indices[control]]:
            raise ComposeError(
                f"{owner}: SMNU/{label} control 0x{control:08X} is not the "
                "literal stock MX05 record required for Manager layout"
            )

    records[indices[_MX05_NATIVE_LIST_CONTROL_ID]] = _patch_mx05_record(
        stock[stock_indices[_MX05_NATIVE_LIST_CONTROL_ID]],
        expected_size=0x90, expected_rect=(10, 55, 164, 160),
        rectangle=(10, 55, 164, 135), owner=owner, label="list",
    )
    records[indices[_MX05_NATIVE_SCROLL_CONTROL_ID]] = _patch_mx05_record(
        stock[stock_indices[_MX05_NATIVE_SCROLL_CONTROL_ID]],
        expected_size=0x54, expected_rect=(174, 51, 25, 167),
        rectangle=(174, 51, 25, 142), owner=owner, label="scrollbar",
    )
    records[indices[_MX05_NATIVE_COIN_CONTROL_ID]] = _patch_mx05_record(
        stock[stock_indices[_MX05_NATIVE_COIN_CONTROL_ID]],
        expected_size=0x74, expected_rect=(33, 219, 16, 17),
        rectangle=(33, 194, 16, 17), owner=owner, label="selected-action coin",
    )
    records[indices[_MX05_NATIVE_ACTION_CONTROL_ID]] = _patch_mx05_record(
        stock[stock_indices[_MX05_NATIVE_ACTION_CONTROL_ID]],
        expected_size=0xAC, expected_rect=(51, 219, 103, 21),
        rectangle=(51, 194, 103, 21), owner=owner, label="selected action",
    )
    records[indices[_MX05_NATIVE_PRICE_CONTROL_ID]] = _patch_mx05_record(
        stock[stock_indices[_MX05_NATIVE_PRICE_CONTROL_ID]],
        expected_size=0xA8, expected_rect=(115, 222, 39, 16),
        rectangle=(115, 197, 39, 16), owner=owner, label="selected-action price",
    )

    refresh_label, refresh_tooltip, refresh_price, refresh_price_tooltip = strings
    refresh_coin = _patch_mx05_record(
        stock[stock_indices[_MX05_NATIVE_COIN_CONTROL_ID]],
        expected_size=0x74, expected_rect=(33, 219, 16, 17),
        rectangle=(33, 219, 16, 17), owner=owner, label="Refresh coin",
        control_offset=0x64, control_id=QUEST_REFRESH_COIN_CONTROL_ID,
        string_patches={0x20: refresh_price_tooltip},
    )
    refresh_action = _patch_mx05_record(
        stock[stock_indices[_MX05_NATIVE_ACTION_CONTROL_ID]],
        expected_size=0xAC, expected_rect=(51, 219, 103, 21),
        rectangle=(51, 219, 103, 21), owner=owner, label="Refresh action",
        control_offset=0x88, control_id=QUEST_REFRESH_CONTROL_ID,
        string_patches={
            0x2C: refresh_label,
            0x30: refresh_label,
            0x38: refresh_tooltip,
        },
    )
    refresh_price_record = _patch_mx05_record(
        stock[stock_indices[_MX05_NATIVE_PRICE_CONTROL_ID]],
        expected_size=0xA8, expected_rect=(115, 222, 39, 16),
        rectangle=(115, 222, 39, 16), owner=owner, label="Refresh price",
        control_offset=0x7C, control_id=QUEST_REFRESH_PRICE_BINDING_ID,
        string_patches={0x1C: refresh_price, 0x24: refresh_price_tooltip},
    )
    records[-1:-1] = (refresh_coin, refresh_action, refresh_price_record)
    result = b"".join(records)
    for control in (
        QUEST_REFRESH_CONTROL_ID,
        QUEST_REFRESH_PRICE_BINDING_ID,
        QUEST_REFRESH_COIN_CONTROL_ID,
    ):
        if result.count(struct.pack("<I", control)) != 1:
            raise ComposeError(
                f"{owner}: generated quest-board control 0x{control:08X} is not unique"
            )
    return result


def _materialize_quest_board_panel_resources(
    game_path: Path,
    resources: Sequence[CamResource],
    *,
    controller_panels: Sequence[ResolvedControllerPanel],
    controller_registry: ResolvedControllerRegistry,
    dialog_resolutions: Sequence[ResolvedBuildingDialog],
) -> tuple[CamResource, ...]:
    if not controller_registry.quest_boards:
        return tuple(resources)
    panels = {item.qualified_panel_key: item for item in controller_panels}
    output = list(resources)
    for board in controller_registry.quest_boards:
        panel = panels.get(board.panel_key)
        if panel is None:
            raise ComposeError(f"quest-board panel mapping is missing: {board.panel_key}")
        parent = next((
            item for item in dialog_resolutions
            if item.owner == panel.owner
            and int.from_bytes(item.resolved_dialog_id, "little") == board.parent_dialog_id
        ), None)
        if parent is None:
            raise ComposeError(f"quest-board parent mapping is missing: {board.panel_key}")
        parent_smnu = [
            resource for resource in output
            if resource.owner == panel.owner and resource.section == b"SMNU"
            and resource.key == parent.source_dialog_id
        ]
        if len(parent_smnu) != 1:
            raise ComposeError(f"{panel.owner}: quest-board parent SMNU is missing")
        parent_values = _smnu_dword_values(
            parent_smnu[0].entry.data, panel.owner,
            _display_key(parent.source_dialog_id),
        )
        authored = [
            value for value in (
                QUEST_REFRESH_CONTROL_ID,
                QUEST_REFRESH_PRICE_BINDING_ID,
                QUEST_REFRESH_COIN_CONTROL_ID,
            ) if value in parent_values
        ]
        if authored:
            raise ComposeError(
                f"{panel.owner}: remove the obsolete AP54 parent Refresh controls: "
                + ", ".join(f"0x{value:08X}" for value in authored)
            )

        child_matches = [
            (index, resource) for index, resource in enumerate(output)
            if resource.owner == panel.owner and resource.key == panel.source_dialog_id
            and resource.section in (b"SMNU", b"STRT")
        ]
        child_by_section = {
            section: [(index, resource) for index, resource in child_matches
                      if resource.section == section]
            for section in (b"SMNU", b"STRT")
        }
        if any(len(matches) != 1 for matches in child_by_section.values()):
            raise ComposeError(f"{panel.owner}: quest-board child panel is incomplete")
        strt_index, strt_resource = child_by_section[b"STRT"][0]
        strings_payload, string_indices = _append_quest_refresh_strings(
            strt_resource.entry.data, owner=panel.owner,
            label=_display_key(panel.source_dialog_id),
        )
        smnu_index, smnu_resource = child_by_section[b"SMNU"][0]
        child_values = _smnu_dword_values(
            smnu_resource.entry.data, panel.owner,
            _display_key(panel.source_dialog_id),
        )
        if any(value in child_values for value in (
            QUEST_REFRESH_CONTROL_ID,
            QUEST_REFRESH_PRICE_BINDING_ID,
            QUEST_REFRESH_COIN_CONTROL_ID,
        )):
            raise ComposeError(
                f"{panel.owner}: quest-board child must not pre-author Manager Refresh controls"
            )
        smnu_payload = _materialize_mx05_quest_refresh_row(
            game_path, smnu_resource.entry.data, string_indices,
            owner=panel.owner, label=_display_key(panel.source_dialog_id),
        )
        output[strt_index] = replace(
            strt_resource,
            entry=CamEntry(name=strt_resource.entry.name, data=strings_payload),
        )
        output[smnu_index] = replace(
            smnu_resource,
            entry=CamEntry(name=smnu_resource.entry.name, data=smnu_payload),
        )
    return tuple(output)


def _load_whole_strt_stock_lineage(
    game_path: Path,
    key: bytes,
) -> tuple[StrtTable, tuple[tuple[str, StrtTable], ...]]:
    """Load every installed stock ancestor for one complete STRT registry.

    The last declared table is Majesty's effective stock value.  Older tables
    remain valid package ancestries, but never become the output base merely
    because a legacy mod was authored against them.
    """

    try:
        stock_paths, _key_mode = _WHOLE_STRT[key]
    except KeyError as exc:
        raise ComposeError(f"unsupported complete STRT registry: {_display_key(key)}") from exc
    ancestors: list[tuple[str, StrtTable]] = []
    for label, relative in stock_paths:
        entry = _require_cam_entry(game_path / relative, b"STRT", key)
        ancestors.append((label, parse_strt(entry.data)))
    if not ancestors:  # defensive configuration invariant
        raise ComposeError(f"no stock ancestry is configured for {_display_key(key)}")
    return ancestors[-1][1], tuple(ancestors)


def merge_text_resources(
    game_path: Path,
    inventories: Sequence[PackageInventory],
    *,
    private_activity_texts: Sequence[PrivateActivityTextBinding] | None = None,
    dialog_resolutions: Sequence[ResolvedBuildingDialog] | None = None,
    controller_panels: Sequence[ResolvedControllerPanel] = (),
    controller_registry: ResolvedControllerRegistry | None = None,
    named_resolutions: Mapping[
        tuple[bytes, bytes], ScopedNamedResourceResolution
    ] | None = None,
    strt_resolutions: Mapping[
        tuple[bytes, int], StrtRowResolution
    ] | None = None,
    stock_named_resources: Mapping[tuple[bytes, bytes], bytes] | None = None,
) -> TextMergeResult:
    """Merge Majesty's known whole STRT tables and all private panel/name tables."""

    resources = collapse_native_cam_resources(
        resource for inv in inventories for resource in inv.resources
    )
    if controller_registry is not None and controller_registry.quest_boards:
        if dialog_resolutions is None:
            raise ComposeError(
                "quest-board materialization requires resolved building dialogs"
            )
        resources = _materialize_quest_board_panel_resources(
            game_path,
            resources,
            controller_panels=controller_panels,
            controller_registry=controller_registry,
            dialog_resolutions=dialog_resolutions,
        )
    dialog_renames = _dialog_renames(
        inventories,
        resources,
        resolutions=dialog_resolutions,
        controller_panels=controller_panels,
    )
    rename_map = {(owner, old): new for owner, old, new in dialog_renames}

    whole: dict[bytes, StrtMergeSelection] = {}
    processed_whole_keys: set[bytes] = set()
    whole_resource_ids: set[int] = set()
    detached_activity_texts: tuple[PrivateActivityTextRecord, ...] = ()
    for key, (_stock_paths, key_mode) in _WHOLE_STRT.items():
        variants = [
            resource
            for resource in resources
            if resource.section == b"STRT" and resource.key == key
        ]
        if not variants:
            continue
        variant_owners = [resource.owner for resource in variants]
        duplicate_owners = sorted(
            owner for owner in set(variant_owners) if variant_owners.count(owner) > 1
        )
        if duplicate_owners:
            raise ComposeError(
                f"complete {_display_key(key)} STRT table appears more than once "
                f"for selected owner(s): {', '.join(duplicate_owners)}"
            )
        stock_table, stock_ancestors = _load_whole_strt_stock_lineage(game_path, key)
        parsed_variants = tuple(
            (resource.owner, parse_strt(resource.entry.data)) for resource in variants
        )
        if key == b"AITX" and private_activity_texts is not None:
            parsed_variants, detached_activity_texts = _detach_private_activity_texts(
                stock_table,
                parsed_variants,
                private_activity_texts,
                stock_ancestors=stock_ancestors,
            )
        try:
            merged, deltas = merge_strt_stock_relative(
                stock_table,
                stock_ancestors,
                parsed_variants,
                key_mode=key_mode,
                resolutions={
                    row_key: resolution
                    for (table_key, row_key), resolution in (strt_resolutions or {}).items()
                    if table_key == key
                },
            )
        except StrtAncestryError as exc:
            raise ComposeError(
                f"{_display_key(key)} STRT stock ancestry is not safe: {exc}"
            ) from exc
        processed_whole_keys.add(key)
        # A complete stock table is ancestry evidence, not an authored
        # load-last replacement.  Emit this registry only when at least one
        # provider has a real stock-relative row delta.  A reviewed choice to
        # restore stock still has non-empty provider deltas and is retained.
        if any(delta.changes for delta in deltas):
            whole[key] = StrtMergeSelection(
                key=key,
                entry=CamEntry(name=variants[0].entry.name, data=merged.to_bytes()),
                deltas=deltas,
            )
        whole_resource_ids.update(id(resource) for resource in variants)

    if private_activity_texts and b"AITX" not in processed_whole_keys:
        raise ComposeError(
            "private activity-text bindings exist but no selected mod provides AITX"
        )

    private_strt_resources = tuple(
        resource
        for resource in resources
        if resource.section == b"STRT" and id(resource) not in whole_resource_ids
    )
    smnu_entries, smnu_selections = merge_named_resources(
        resources,
        b"SMNU",
        renames=rename_map,
        resolutions=named_resolutions,
        stock_resources=stock_named_resources,
    )
    private_strt_entries, private_strt_selections = merge_named_resources(
        private_strt_resources,
        b"STRT",
        renames=rename_map,
        resolutions=named_resolutions,
        stock_resources=stock_named_resources,
    )

    dialog_keys = {entry.name[:4] for entry in smnu_entries}
    panel_strt = [entry for entry in private_strt_entries if entry.name[:4] in dialog_keys]
    gpl_private_strt = [
        entry for entry in private_strt_entries if entry.name[:4] not in dialog_keys
    ]
    text_strt = [
        whole[key].entry for key in _TEXT_WHOLE_ORDER if key in whole
    ] + panel_strt
    gpltext_strt = [
        whole[key].entry for key in _GPLTEXT_WHOLE_ORDER if key in whole
    ] + gpl_private_strt

    text_archive = CamArchive(
        sections=(
            CamSection(extension=b"SMNU", entries=tuple(smnu_entries)),
            CamSection(extension=b"STRT", entries=tuple(text_strt)),
        )
    )
    gpltext_archive = CamArchive(
        sections=(CamSection(extension=b"STRT", entries=tuple(gpltext_strt)),)
    )
    whole_order = (*_TEXT_WHOLE_ORDER, *_GPLTEXT_WHOLE_ORDER)
    return TextMergeResult(
        text_archive=text_archive,
        gpltext_archive=gpltext_archive,
        whole_tables=tuple(whole[key] for key in whole_order if key in whole),
        named=(*smnu_selections, *private_strt_selections),
        dialog_renames=dialog_renames,
        private_activity_texts=detached_activity_texts,
    )


def discover_private_activity_texts(
    game_path: Path,
    inventories: Sequence[PackageInventory],
) -> tuple[PrivateActivityTextBinding, ...]:
    """Derive quest-safe private AITX bindings from every selected package.

    This is deliberately package-independent: it compares each supplied AITX
    table to the stock table and proves each changed row against that package's
    complete GPL source.  No Mod UUID, row, symbol, or string is recognized by
    name.  A package that cannot prove the stock resolver lifecycle is rejected.
    """

    stock, stock_ancestors = _load_whole_strt_stock_lineage(game_path, b"AITX")
    packages: list[ActivityTextDiscoveryPackage] = []
    for inventory in inventories:
        owner = inventory.selected.alias
        variants = [
            resource
            for resource in inventory.resources
            if resource.section == b"STRT" and resource.key == b"AITX"
        ]
        if len(variants) > 1:
            raise ComposeError(
                f"{owner}: complete AITX STRT table appears more than once"
            )
        if not variants:
            continue
        table = parse_strt(variants[0].entry.data)
        try:
            proof = prove_strt_stock_relative_delta(
                owner,
                table,
                stock,
                stock_ancestors,
                key_mode="index",
            )
        except StrtAncestryError as exc:
            raise ComposeError(f"{owner}: AITX stock ancestry is not safe: {exc}") from exc
        delta = proof.delta
        if not delta.changes:
            continue
        for source_index, record in delta.changes:
            if record.string_id != source_index:
                raise ComposeError(
                    f"{owner}: AITX[{source_index}] embeds ID {record.string_id}, "
                    "expected its positional index"
                )
        packages.append(
            ActivityTextDiscoveryPackage(
                owner=owner,
                source_mod_id=inventory.selected.package.mod_id,
                changes=tuple(
                    (source_index, record.text)
                    for source_index, record in delta.changes
                ),
                stock_rows=_private_aitx_ancestor_rows(owner, proof),
                gpl_sources=tuple(_parse_inventory_gpl_sources(inventory)),
            )
        )
    if not packages:
        return ()
    try:
        stock_expressions = _load_stock_activity_text_expressions(game_path)
        return discover_private_activity_text_bindings(
            packages,
            stock_integer_expressions=stock_expressions,
        )
    except IntentTextError as exc:
        raise ComposeError(str(exc)) from exc


def _private_aitx_ancestor_rows(
    owner: str,
    proof: StrtStockRelativeProof,
) -> tuple[tuple[int, bytes], ...]:
    """Return the proven authoring-ancestor row for each private AITX edit."""

    result: list[tuple[int, bytes]] = []
    for source_index, _record in proof.delta.changes:
        candidates = {
            (
                ancestor.records[source_index].text
                if source_index < len(ancestor.records)
                else b""
            )
            for _label, ancestor in proof.candidate_ancestors
        }
        if len(candidates) != 1:
            raise ComposeError(
                f"{owner}: AITX[{source_index}] has ambiguous stock-row ancestry"
            )
        result.append((source_index, next(iter(candidates))))
    return tuple(result)


def discover_selected_private_activity_texts(
    game_path: Path,
    selected_mods: Sequence[SelectedMod],
) -> tuple[PrivateActivityTextBinding, ...]:
    """Convenience wrapper used by manager plan/catalog preflight."""

    inventories = tuple(inventory_package(selected) for selected in selected_mods)
    return discover_private_activity_texts(game_path, inventories)


def _load_stock_activity_text_expressions(game_path: Path) -> dict[str, int]:
    source = _load_stock_activity_text_expression_source(game_path)
    try:
        return collect_exact_integer_expressions((source,), owner="stock-datamx")
    except IntentTextError as exc:
        raise ComposeError(str(exc)) from exc


def _load_stock_activity_text_expression_source(
    game_path: Path,
) -> ParsedSemanticSource:
    path = game_path / "SDK" / "OriginalQuests" / "GPLMx" / "mx_defines.gpl"
    if not path.is_file():
        raise ComposeError(
            "stock DataMX GPL definitions are required for activity-text "
            f"discovery: {path}"
        )
    return _parse_semantic_source_file(path)


def _load_stock_purchase_equipment_source(
    game_path: Path,
) -> ParsedSemanticSource:
    path = (
        game_path
        / "SDK"
        / "OriginalQuests"
        / "GPLMx"
        / "DecisionTrees"
        / "Modules"
        / "mx_Purchase_Equipment.gpl"
    )
    if not path.is_file():
        raise ComposeError(
            "installed stock GPLMx Purchase_Equipment source is required for "
            f"purchase-tail composition: {path}"
        )
    source = _parse_semantic_source_file(path)
    require_complete_semantic_coverage(source)
    source.require(DefinitionKind.FUNCTION, "Purchase_Equipment")
    return source


def _load_stock_purchase_bazaar_source(
    game_path: Path,
) -> ParsedSemanticSource:
    path = (
        game_path
        / "SDK"
        / "OriginalQuests"
        / "GPLMx"
        / "TaskModules"
        / "Buildings"
        / "Magic_Bazaar.gpl"
    )
    if not path.is_file():
        raise ComposeError(
            "installed stock GPLMx Purchase_Bazaar source is required for "
            f"purchase-tail composition: {path}"
        )
    source = _parse_semantic_source_file(path)
    require_complete_semantic_coverage(source)
    source.require(DefinitionKind.FUNCTION, "Purchase_Bazaar")
    return source


def _load_stock_controlled_follower_items(
    game_path: Path,
) -> tuple[SemanticItem, SemanticItem, SemanticItem]:
    root = game_path / "SDK" / "OriginalQuests" / "GPLMx" / "TaskModules"
    paths = (
        root / "Subtasks" / "mx_Control_Monster.gpl",
        root / "Characters" / "Monsters" / "mx_Controlled_Monster.gpl",
    )
    parsed: list[ParsedSemanticSource] = []
    for path in paths:
        if not path.is_file():
            raise ComposeError(
                "installed stock GPLMx controlled-monster source is required "
                f"for follower movement composition: {path}"
            )
        source = _parse_semantic_source_file(path)
        require_complete_semantic_coverage(source)
        parsed.append(source)
    return (
        parsed[0].require(DefinitionKind.FUNCTION, "Control_Monster"),
        parsed[1].require(DefinitionKind.FUNCTION, "Controlled_Monster_Death"),
        parsed[1].require(DefinitionKind.FUNCTION, "leader_dead"),
    )


def _load_stock_hero_quest_lifecycle_items(
    game_path: Path,
) -> tuple[dict[str, SemanticItem], SemanticItem, SemanticItem]:
    root = game_path / "SDK" / "OriginalQuests" / "GPLMx"
    decision_root = root / "DecisionTrees"
    scripts = (
        "mx_adept", "mx_barbarian", "mx_cultist", "mx_discord", "mx_dwarf",
        "mx_elf", "mx_gnome", "mx_healer", "mx_monk", "mx_paladin",
        "mx_priestess", "mx_ranger", "mx_rogue", "mx_solarus",
        "mx_warrior", "mx_wizard",
    )
    trees: dict[str, SemanticItem] = {}
    for script in scripts:
        candidates = list(decision_root.glob(script + ".gpl"))
        if not candidates:
            candidates = [
                path for path in decision_root.glob("*.gpl")
                if path.stem.casefold() == script
            ]
        if len(candidates) != 1:
            raise ComposeError(
                f"installed stock hero decision source is missing or ambiguous: {script}"
            )
        source = _parse_semantic_source_file(candidates[0])
        require_complete_semantic_coverage(source)
        functions = [item for item in source.items if item.kind is DefinitionKind.FUNCTION]
        if len(functions) != 1:
            raise ComposeError(
                f"stock hero decision source must contain exactly one function: {candidates[0]}"
            )
        trees[script] = functions[0]
    reset_path = root / "mx_LowLevel.gpl"
    death_path = root / "mx_Hero_Deaths.gpl"
    for path in (reset_path, death_path):
        if not path.is_file():
            raise ComposeError(
                f"installed stock hero lifecycle source is required: {path}"
            )
    reset_source = _parse_semantic_source_file(reset_path)
    death_source = _parse_semantic_source_file(death_path)
    return (
        trees,
        reset_source.require(DefinitionKind.FUNCTION, "reset_tasks"),
        death_source.require(DefinitionKind.FUNCTION, "Unit_Call_Deathscript"),
    )


def _detach_private_activity_texts(
    stock: StrtTable,
    variants: Sequence[tuple[str, StrtTable]],
    bindings: Sequence[PrivateActivityTextBinding],
    *,
    stock_ancestors: Sequence[tuple[str, StrtTable]] | None = None,
) -> tuple[
    tuple[tuple[str, StrtTable], ...],
    tuple[PrivateActivityTextRecord, ...],
]:
    """Detach every discovered AITX delta into the manager runtime registry.

    AITX is a quest-replaceable positional singleton.  Keeping even one
    Merge-mod delta in that table would let a later quest silently substitute
    unrelated text. Therefore every selected AITX change must have a proven
    stock-resolver call-site binding and be restored to its stock placeholder
    or removed from the emitted table. Incomplete discovery stops the build.
    """

    by_owner: dict[str, list[PrivateActivityTextBinding]] = {}
    known_owners = {owner for owner, _table in variants}
    runtime_ids: set[int] = set()
    for binding in bindings:
        if binding.owner not in known_owners:
            raise ComposeError(
                f"{binding.owner}: private activity-text binding has no AITX provider"
            )
        if binding.runtime_id in runtime_ids:
            raise ComposeError(
                f"duplicate private activity-text runtime ID 0x{binding.runtime_id:08X}"
            )
        runtime_ids.add(binding.runtime_id)
        by_owner.setdefault(binding.owner, []).append(binding)

    if stock_ancestors is None:
        for owner, table in variants:
            _require_complete_aitx_provider(owner, stock, table)
    ancestry = tuple(stock_ancestors or (("installed stock", stock),))
    sanitized: list[tuple[str, StrtTable]] = []
    detached: list[PrivateActivityTextRecord] = []
    for owner, table in variants:
        try:
            normalized, deltas = merge_strt_stock_relative(
                stock,
                ancestry,
                ((owner, table),),
                key_mode="index",
            )
        except StrtAncestryError as exc:
            raise ComposeError(f"{owner}: AITX stock ancestry is not safe: {exc}") from exc
        delta = deltas[0]
        changed = {index for index, _record in delta.changes}
        declared = {binding.source_index for binding in by_owner.get(owner, ())}
        undeclared = sorted(changed - declared)
        stale = sorted(declared - changed)
        if undeclared:
            raise ComposeError(
                f"{owner}: AITX changes at indices {undeclared} were not discovered "
                "as safe private activity text; quest-safe composition cannot be proven"
            )
        if stale:
            raise ComposeError(
                f"{owner}: private activity-text discovery names unchanged/missing "
                f"AITX indices {stale}"
            )

        records = list(normalized.records)
        for binding in by_owner.get(owner, ()):
            record = records[binding.source_index]
            expected = binding.expected_text.encode("cp1252")
            if record.string_id != binding.source_index:
                raise ComposeError(
                    f"{owner}: AITX[{binding.source_index}] embeds ID "
                    f"{record.string_id}, expected its positional index"
                )
            if record.text != expected:
                raise ComposeError(
                    f"{owner}: AITX[{binding.source_index}] does not match the "
                    f"discovered text for AITX[{binding.source_index}]"
                )
            detached.append(PrivateActivityTextRecord(binding=binding, text=record.text))
            records[binding.source_index] = (
                stock.records[binding.source_index]
                if binding.source_index < len(stock.records)
                else StrtRecord(string_id=binding.source_index, text=b"")
            )

        while len(records) > len(stock.records) and not records[-1].text:
            records.pop()
        sanitized.append((owner, StrtTable(version=table.version, records=tuple(records))))

    if bindings and len(detached) != len(bindings):  # defensive closed-world check
        raise ComposeError("not every discovered private activity-text row was detached")
    detached.sort(key=lambda record: record.binding.runtime_id)
    return tuple(sanitized), tuple(detached)


def _require_complete_aitx_provider(
    owner: str, stock: StrtTable, table: StrtTable
) -> None:
    if len(table.records) < len(stock.records):
        raise ComposeError(
            f"{owner}: AITX provider is truncated ({len(table.records)} rows; "
            f"installed stock has {len(stock.records)}); complete effective "
            "positional tables are required"
        )


def merge_bdep_resource(
    game_path: Path,
    inventories: Sequence[PackageInventory],
    *,
    resolutions: Mapping[str, BdepRowResolution] | None = None,
) -> BdepComposeResult:
    resources = [
        resource
        for resource in collapse_native_cam_resources(
            resource
            for inventory in inventories
            for resource in inventory.resources
        )
        if resource.section == b"DATA"
    ]
    unsupported = [resource for resource in resources if resource.key != b"BDEP"]
    if unsupported:
        labels = ", ".join(
            f"{resource.owner}:{_display_key(resource.key)}" for resource in unsupported
        )
        raise ComposeError(f"unsupported DATA resources: {labels}")
    original_stock = _require_cam_entry(
        game_path / "Data" / "miscdata.cam", b"DATA", b"BDEP"
    )
    effective_stock = _require_cam_entry(
        game_path / "DataMX" / "mx_miscdata.cam", b"DATA", b"BDEP"
    )
    if not resources:
        if any(
            inventory.selected.package.definition.schema_version < 3
            for inventory in inventories
        ):
            raise ComposeError("selected packages provide no DATA/BDEP resource")
        return BdepComposeResult(
            archive=CamArchive(
                # The generated package loads after independently enabled
                # Standard Mods. Re-emitting effective stock here would undo a
                # Standard's native BDEP change even though no selected input
                # asked the composer to own BDEP. An empty DATA registry is a
                # valid no-op overlay.
                sections=(CamSection(extension=b"DATA", entries=()),)
            ),
            deltas=(),
        )
    try:
        result = merge_bdep_stock_relative(
            effective_stock.data,
            (
                ("Original Majesty", original_stock.data),
                ("Northern Expansion", effective_stock.data),
            ),
            ((resource.owner, resource.entry.data) for resource in resources),
            resolutions=resolutions,
        )
    except (TableAncestryError, TableFormatError, TableMergeConflict) as exc:
        raise ComposeError(str(exc)) from exc
    if not any(delta.rows for delta in result.deltas):
        return BdepComposeResult(
            archive=CamArchive(
                sections=(CamSection(extension=b"DATA", entries=()),)
            ),
            deltas=result.deltas,
        )
    entry = CamEntry(name=resources[0].entry.name, data=result.payload)
    archive = CamArchive(
        sections=(CamSection(extension=b"DATA", entries=(entry,)),)
    )
    return BdepComposeResult(archive=archive, deltas=result.deltas)


def merge_sound_resources(
    inventories: Sequence[PackageInventory],
    *,
    named_resolutions: Mapping[
        tuple[bytes, bytes], ScopedNamedResourceResolution
    ] | None = None,
    stock_named_resources: Mapping[tuple[bytes, bytes], bytes] | None = None,
) -> tuple[CamArchive, CamArchive, tuple[NamedMergeSelection, ...]]:
    resources = collapse_native_cam_resources(
        resource for inv in inventories for resource in inv.resources
    )
    waves, wave_selections = merge_named_resources(
        resources,
        b"WAVE",
        resolutions=named_resolutions,
        stock_resources=stock_named_resources,
    )
    sounds, sound_selections = merge_named_resources(
        resources,
        b"DSND",
        resolutions=named_resolutions,
        stock_resources=stock_named_resources,
    )
    return (
        CamArchive(sections=(CamSection(extension=b"WAVE", entries=waves),)),
        CamArchive(sections=(CamSection(extension=b"DSND", entries=sounds),)),
        (*wave_selections, *sound_selections),
    )


def merge_art_resources(
    game_path: Path,
    inventories: Sequence[PackageInventory],
    *,
    required_stock_interface_imag_ids: Sequence[bytes] = (),
    art_resolutions: Mapping[
        tuple[str, bytes], ScopedArtResourceResolution
    ] | None = None,
) -> tuple[ArtDomainComposeResult, ArtDomainComposeResult]:
    """Compatibility view of the generalized stock-lineage art composer."""

    results = merge_art_resource_domains(
        game_path,
        inventories,
        required_stock_imag_ids=required_stock_interface_imag_ids,
        art_resolutions=art_resolutions,
    )
    by_domain = {result.domain: result for result in results}
    lineages = load_stock_art_lineages(game_path)
    for domain in ("main", "interface"):
        if domain not in by_domain:
            lineage = next(
                (item for item in lineages if item.domain == domain),
                None,
            )
            if lineage is None:
                raise ComposeError(f"installed stock {domain} art lineage is missing")
            by_domain[domain] = _stock_art_domain(domain, lineage.effective)
    return by_domain["main"], by_domain["interface"]


def merge_art_resource_domains(
    game_path: Path,
    inventories: Sequence[PackageInventory],
    *,
    required_stock_imag_ids: Sequence[bytes] = (),
    art_resolutions: Mapping[
        tuple[str, bytes], ScopedArtResourceResolution
    ] | None = None,
) -> tuple[ArtDomainComposeResult, ...]:
    """Compose each independent stock art lineage in native-content order.

    The first selected owner retains a divergent positional slot. A later
    owner moves the complete contiguous changed run containing that conflict,
    which keeps a mod's authored sprite block together. Every moved TILE must
    be reachable through an audited IMAG frame field; otherwise the operation
    fails closed in ``rewrite_imag_entries``.
    """

    try:
        lineages = load_stock_art_lineages(game_path)
    except (OSError, StockArtError, ValueError) as exc:
        raise ComposeError(f"installed stock art lineages are not safe: {exc}") from exc
    by_lineage: dict[
        str,
        list[tuple[PackageInventory, Path, CamArchive, ArtArchiveAnalysis]],
    ] = {}
    for inventory in inventories:
        semantic_passthrough = getattr(
            inventory.selected, "semantic_passthrough", False
        )
        eligible_art_cams = getattr(inventory, "art_cams", None)
        if eligible_art_cams is None:
            eligible_art_cams = (
                ()
                if semantic_passthrough
                else inventory.cams
            )
        try:
            classified = collapse_art_archives(
                game_path,
                tuple(eligible_art_cams),
                owner=inventory.selected.alias,
                lineages=lineages,
            )
        except (OSError, StockArtError, ValueError) as exc:
            raise ComposeError(
                f"{inventory.selected.alias}: positional art cannot be reconciled: {exc}"
            ) from exc
        for item in classified:
            by_lineage.setdefault(item.lineage.lineage_id, []).append(
                (inventory, item.paths[-1], item.archive, item.analysis)
            )

    results: list[ArtDomainComposeResult] = []
    required_lineages = {
        lineage.lineage_id
        for required_id in required_stock_imag_ids
        for lineage in lineages
        if required_id in lineage.imag_keys
    }
    for required_id in required_stock_imag_ids:
        matches = [lineage for lineage in lineages if required_id in lineage.imag_keys]
        if len(matches) != 1:
            raise ComposeError(
                f"required stock IMAG {_display_key(required_id)} has no unique "
                "installed art lineage"
            )
    selected_lineage_ids = set(by_lineage) | required_lineages
    for lineage in lineages:
        if lineage.lineage_id not in selected_lineage_ids:
            continue
        providers = by_lineage.get(lineage.lineage_id, [])
        required = tuple(
            key for key in required_stock_imag_ids if key in lineage.imag_keys
        )
        if not providers:
            results.append(
                _required_stock_art_domain(lineage.domain, lineage.effective, required)
            )
            continue
        prepared_providers: list[tuple[PackageInventory, Path, CamArchive]] = []
        analyses: list[ArtArchiveAnalysis] = []
        for inventory, path, archive, raw_analysis in providers:
            prepared_archive = _strip_unowned_secondary_imag_layers(
                archive,
                raw_analysis,
            )
            prepared_providers.append((inventory, path, prepared_archive))
            analyses.append(
                raw_analysis
                if prepared_archive is archive
                else analyze_art_archive(
                    lineage.effective,
                    prepared_archive,
                    mod_id=inventory.selected.alias,
                    fallthrough_ancestors=lineage.ancestors,
                )
            )
        result = _compose_art_domain(
            lineage.lineage_id,
            lineage.domain,
            lineage.effective,
            tuple(prepared_providers),
            analyses,
            fallthrough_ancestors=lineage.ancestors,
            required_stock_imag_ids=required,
            art_resolutions=art_resolutions,
        )
        results.append(result)
    emitted_imag: dict[bytes, str] = {}
    for result in results:
        for section in result.archive.sections:
            if section.extension != b"IMAG":
                continue
            for entry in section.entries:
                key = entry.name.rstrip(b"\0")[:4]
                previous = emitted_imag.get(key)
                if previous is not None and previous != result.domain:
                    raise ComposeError(
                        f"generated art lineages {previous!r} and {result.domain!r} "
                        f"both emit global IMAG {_display_key(key)}; Majesty can "
                        "load only one final named image resource"
                    )
                emitted_imag[key] = result.domain
    return tuple(results)


def _required_stock_art_domain(
    domain: str,
    stock: CamArchive,
    required_ids: Sequence[bytes],
) -> ArtDomainComposeResult:
    result = _stock_art_domain(domain, stock)
    images = _materialize_required_stock_imag_entries(
        (), stock, required_ids, domain=domain
    )
    stock_tiles = _require_section(stock, b"TILE")
    tiles = _blank_positional_section(stock_tiles, len(stock_tiles.entries))
    _materialize_imag_tile_dependencies(
        tiles,
        stock_tiles,
        images,
    )
    sections = [
        CamSection(
            b"IMAG",
            images,
            padding=_require_section(stock, b"IMAG").padding,
        ),
        CamSection(b"TILE", tuple(tiles), padding=stock_tiles.padding),
    ]
    return replace(result, archive=CamArchive(tuple(sections)))


def _effective_stock_art_ancestor(game_path: Path, domain: str) -> CamArchive:
    """Materialize Gold HD's Original-then-MX positional art ancestry."""

    filename = "maindata.cam" if domain == "main" else "interfacedata.cam"
    mx_filename = "mx_maindata.cam" if domain == "main" else "mx_interfacedata.cam"
    base = read_cam(game_path / "Data" / filename)
    expansion_path = game_path / "DataMX" / mx_filename
    if not expansion_path.is_file():
        return base
    expansion = read_cam(expansion_path)

    def optional(archive: CamArchive, extension: bytes) -> CamSection | None:
        return next((item for item in archive.sections if item.extension == extension), None)

    def overlay(extension: bytes) -> CamSection:
        first = _require_section(base, extension)
        second = optional(expansion, extension)
        if second is None:
            return first
        output = list(first.entries)
        if len(output) < len(second.entries):
            output.extend(second.entries[len(output):])
        for index, entry in enumerate(second.entries):
            if entry.data:
                output[index] = entry
        return CamSection(extension, tuple(output), padding=first.padding)

    images: list[CamEntry] = []
    image_index: dict[bytes, int] = {}
    for archive in (base, expansion):
        section = _require_section(archive, b"IMAG")
        for entry in section.entries:
            key = entry.name.rstrip(b"\x00")[:4]
            if key in image_index:
                images[image_index[key]] = entry
            else:
                image_index[key] = len(images)
                images.append(entry)

    palette_extension = b"SPLT" if domain == "main" else b"PALT"
    return CamArchive(
        sections=(
            CamSection(b"IMAG", tuple(images), padding=_require_section(base, b"IMAG").padding),
            overlay(b"TILE"),
            overlay(palette_extension),
        )
    )


def _stock_art_domain(domain: str, stock: CamArchive) -> ArtDomainComposeResult:
    """Describe stock lineage while emitting a payload-free art overlay."""

    stock_tiles = _require_section(stock, b"TILE")
    stock_palettes = next(
        (section for section in stock.sections if section.extension in {b"SPLT", b"PALT"}), None
    )
    sparse_archive = CamArchive(
        sections=tuple(
            CamSection(
                extension=section.extension,
                entries=(),
                padding=section.padding,
            )
            for section in stock.sections
            if section.extension in {b"IMAG", b"TILE", b"SPLT", b"PALT"}
        )
    )
    return ArtDomainComposeResult(
        domain=domain,
        # No selected provider owns this domain. Keep all stock ancestry in the
        # allocation report, but let Majesty fall through to the already-loaded
        # game/Standard resources instead of overwriting them from this
        # load-last patch.
        archive=sparse_archive,
        analyses=(),
        tile_collisions=(),
        palette_collisions=(),
        report=ArtRelocationReport(
            tile_allocation=PositionalAllocationReport(
                extension=b"TILE",
                stock_count=len(stock_tiles.entries),
                final_count=len(stock_tiles.entries),
                ranges=(),
            ),
            palette_allocation=(
                PositionalAllocationReport(
                    extension=stock_palettes.extension,
                    stock_count=len(stock_palettes.entries),
                    final_count=len(stock_palettes.entries),
                    ranges=(),
                )
                if stock_palettes is not None
                else None
            ),
            imag_reports=(),
            palette_reports=(),
        ),
    )


def _apply_art_resolutions(
    lineage_id: str,
    stock: CamArchive,
    providers: Sequence[tuple[PackageInventory, Path, CamArchive]],
    analyses: Sequence[ArtArchiveAnalysis],
    *,
    fallthrough_ancestors: Sequence[CamArchive],
    resolutions: Mapping[tuple[str, bytes], ScopedArtResourceResolution],
) -> tuple[
    tuple[tuple[PackageInventory, Path, CamArchive], ...],
    tuple[ArtArchiveAnalysis, ...],
]:
    scoped = {
        key: resolution
        for (candidate_lineage, key), resolution in resolutions.items()
        if candidate_lineage == lineage_id
    }
    if not scoped:
        return tuple(providers), tuple(analyses)

    effective_stock_payloads: dict[bytes, set[bytes]] = {}
    for entry in _require_section(stock, b"IMAG").entries:
        effective_stock_payloads.setdefault(
            entry.name.rstrip(b"\0")[:4], set()
        ).add(entry.data)
    analysis_by_owner = {analysis.mod_id: analysis for analysis in analyses}
    owned_by_owner = {
        owner: _analysis_owned_imag_keys(
            analysis,
            effective_stock_image_payloads=effective_stock_payloads,
        )
        for owner, analysis in analysis_by_owner.items()
    }
    for key, resolution in scoped.items():
        actual = {
            owner for owner, keys in owned_by_owner.items() if key in keys
        }
        missing = resolution.participant_owners.difference(actual)
        if missing:
            raise ComposeError(
                f"art resolution for {lineage_id}/IMAG/{_display_key(key)} "
                "names absent owners: " + ", ".join(sorted(missing))
            )
        if resolution.selected_owner not in actual:
            raise ComposeError(
                f"art resolution for {lineage_id}/IMAG/{_display_key(key)} "
                "selects an absent owner"
            )

    output_providers: list[tuple[PackageInventory, Path, CamArchive]] = []
    output_analyses: list[ArtArchiveAnalysis] = []
    for inventory, path, archive in providers:
        owner = inventory.selected.alias
        analysis = analysis_by_owner[owner]
        lost_keys = {
            key
            for key, resolution in scoped.items()
            if owner in resolution.participant_owners
            and owner != resolution.selected_owner
        }
        if not lost_keys:
            output_providers.append((inventory, path, archive))
            output_analyses.append(analysis)
            continue
        if analysis.unreferenced_tile_changes or analysis.unreferenced_palette_changes:
            raise ComposeError(
                f"{owner}: art choice for {lineage_id} cannot partition "
                "unreferenced positional changes safely"
            )

        refs_by_key: dict[bytes, set[int]] = {}
        for reference in analysis.imag_references:
            refs_by_key.setdefault(
                reference.entry_name.rstrip(b"\0")[:4], set()
            ).add(reference.tile_index)
        lost_tiles = {
            index for key in lost_keys for index in refs_by_key.get(key, ())
        }
        retained_tiles = {
            index
            for key, indices in refs_by_key.items()
            if key not in lost_keys
            for index in indices
        }
        removable_tiles = lost_tiles.difference(retained_tiles).intersection(
            analysis.tile_delta.changed_indices
        )
        lost_palettes = {
            reference.palette_index
            for reference in analysis.tile_palette_references
            if reference.tile_index in lost_tiles
        }
        retained_palettes = {
            reference.palette_index
            for reference in analysis.tile_palette_references
            if reference.tile_index in retained_tiles
        }
        removable_palettes = lost_palettes.difference(retained_palettes)
        if analysis.palette_delta is not None:
            removable_palettes.intersection_update(
                analysis.palette_delta.changed_indices
            )
        else:
            removable_palettes.clear()

        sections: list[CamSection] = []
        for section in archive.sections:
            if section.extension == b"IMAG":
                entries = tuple(
                    entry
                    for entry in section.entries
                    if entry.name.rstrip(b"\0")[:4] not in lost_keys
                )
            elif section.extension == b"TILE":
                entries = tuple(
                    CamEntry(entry.name, b"") if index in removable_tiles else entry
                    for index, entry in enumerate(section.entries)
                )
            elif (
                analysis.palette_delta is not None
                and section.extension == analysis.palette_delta.extension
            ):
                entries = tuple(
                    CamEntry(entry.name, b"")
                    if index in removable_palettes
                    else entry
                    for index, entry in enumerate(section.entries)
                )
            else:
                entries = section.entries
            sections.append(
                CamSection(section.extension, entries, padding=section.padding)
            )
        filtered = CamArchive(tuple(sections))
        try:
            filtered_analysis = analyze_art_archive(
                stock,
                filtered,
                mod_id=owner,
                fallthrough_ancestors=fallthrough_ancestors,
            )
        except (ArtFormatError, ValueError) as exc:
            raise ComposeError(
                f"{owner}: selected art result for {lineage_id} is not safe: {exc}"
            ) from exc
        output_providers.append((inventory, path, filtered))
        output_analyses.append(filtered_analysis)
    return tuple(output_providers), tuple(output_analyses)


def _compose_art_domain(
    lineage_id: str,
    domain: str,
    stock: CamArchive,
    providers: Sequence[tuple[PackageInventory, Path, CamArchive]],
    analyses: Sequence[ArtArchiveAnalysis],
    *,
    fallthrough_ancestors: Sequence[CamArchive] = (),
    required_stock_imag_ids: Sequence[bytes] = (),
    art_resolutions: Mapping[
        tuple[str, bytes], ScopedArtResourceResolution
    ] | None = None,
) -> ArtDomainComposeResult:
    providers, analyses = _apply_art_resolutions(
        lineage_id,
        stock,
        providers,
        analyses,
        fallthrough_ancestors=fallthrough_ancestors,
        resolutions=art_resolutions or {},
    )
    providers, analyses = _coalesce_identical_art_providers(providers, analyses)
    order = {
        inventory.selected.alias: index
        for index, (inventory, _path, _archive) in enumerate(providers)
    }
    analysis_by_owner = {analysis.mod_id: analysis for analysis in analyses}
    tile_deltas = {
        analysis.mod_id: analysis.tile_delta for analysis in analyses
    }
    tile_collisions = find_positional_collisions(tile_deltas)
    protected_tile_indices = {
        analysis.mod_id: {
            change.index
            for change in analysis.tile_delta.changes
            if change.index in analysis.retained_tile_dependencies
            and change.stock_entry is not None
            and change.entry.data != change.stock_entry.data
        }
        for analysis in analyses
    }
    tile_moves = _select_later_conflict_runs(
        tile_deltas,
        tile_collisions,
        order,
        protected_indices=protected_tile_indices,
    )
    tile_start = _first_free_after_reserved(tile_deltas, tile_moves)
    tile_allocation = allocate_collision_free_ranges(
        tile_deltas,
        start=tile_start,
        indices_by_mod=tile_moves,
        maximum_index=0xFFFE,
    )

    palette_deltas = {
        analysis.mod_id: analysis.palette_delta
        for analysis in analyses
        if analysis.palette_delta is not None
        and analysis.palette_delta.changed_indices
    }
    palette_collisions: tuple[PositionalCollision, ...] = ()
    palette_allocation: PositionalAllocationReport | None = None
    palette_moves: dict[str, set[int]] = {}
    if palette_deltas:
        concrete_palette_deltas = {
            owner: delta
            for owner, delta in palette_deltas.items()
            if delta is not None
        }
        palette_collisions = find_positional_collisions(concrete_palette_deltas)
        protected_palette_indices = {
            analysis.mod_id: {
                change.index
                for change in analysis.palette_delta.changes
                if change.index in analysis.retained_palette_dependencies
                and change.stock_entry is not None
                and change.entry.data != change.stock_entry.data
            }
            for analysis in analyses
            if analysis.palette_delta is not None
        }
        palette_moves = _select_later_conflict_runs(
            concrete_palette_deltas,
            palette_collisions,
            order,
            protected_indices=protected_palette_indices,
        )
        palette_start = _first_free_after_reserved(
            concrete_palette_deltas, palette_moves
        )
        palette_allocation = allocate_collision_free_ranges(
            concrete_palette_deltas,
            start=palette_start,
            indices_by_mod=palette_moves,
        )

    rewritten_tiles: dict[str, tuple[CamEntry, ...]] = {}
    palette_reports: list[tuple[str, PaletteRelocationReport]] = []
    for inventory, _path, archive in providers:
        owner = inventory.selected.alias
        effective_entries = _effective_analysis_tile_entries(
            archive,
            analysis_by_owner[owner],
        )
        mapping = (
            palette_allocation.mapping_for(owner)
            if (
                palette_allocation is not None
                and analysis_by_owner[owner].palette_delta is not None
            )
            else {}
        )
        if mapping:
            rewritten = rewrite_tile_palette_indices(
                effective_entries,
                mapping,
                tile_indices=analysis_by_owner[owner].tile_delta.changed_indices,
            )
            effective_entries = rewritten.entries
            palette_reports.append((owner, rewritten.report))
        rewritten_tiles[owner] = effective_entries

    imag_resources: list[CamResource] = []
    imag_reports: list[tuple[str, ImagRelocationReport]] = []
    effective_stock_image_payloads: dict[bytes, set[bytes]] = {}
    recognized_stock_image_payloads: dict[bytes, set[bytes]] = {}
    for archive in (stock, *fallthrough_ancestors):
        for entry in _require_section(archive, b"IMAG").entries:
            recognized_stock_image_payloads.setdefault(
                entry.name.rstrip(b"\x00")[:4], set()
            ).add(entry.data)
    for entry in _require_section(stock, b"IMAG").entries:
        effective_stock_image_payloads.setdefault(
            entry.name.rstrip(b"\x00")[:4], set()
        ).add(entry.data)
    for inventory, path, archive in providers:
        owner = inventory.selected.alias
        mapping = tile_allocation.mapping_for(owner)
        owned_image_keys = _analysis_owned_imag_keys(
            analysis_by_owner[owner],
            effective_stock_image_payloads=effective_stock_image_payloads,
        )
        imag_entries = tuple(
            entry
            for entry in _require_section(archive, b"IMAG").entries
            if entry.name.rstrip(b"\x00")[:4] in owned_image_keys
        )
        inherited_entries = tuple(
            entry
            for entry in imag_entries
            if entry.data in recognized_stock_image_payloads.get(
                entry.name.rstrip(b"\x00")[:4], set()
            )
        )
        custom_entries = tuple(
            entry for entry in imag_entries if entry not in inherited_entries
        )
        inherited_references = {
            reference.tile_index
            for entry in inherited_entries
            for reference in parse_stock_imag_tile_references(
                entry.data,
                tile_count=len(_require_section(archive, b"TILE").entries),
                entry_name=entry.name,
            ).references
        }
        inherited_mapping = {
            old: new for old, new in mapping.items() if old in inherited_references
        }
        preferred_tile_indices = analysis_by_owner[owner].tile_delta.changed_indices
        custom_parsed: list[ParsedImag] = []
        proven_references = analysis_by_owner[owner].imag_references
        for entry in custom_entries:
            parsed = parse_best_imag_tile_references(
                entry.data,
                tile_count=len(_require_section(archive, b"TILE").entries),
                entry_name=entry.name,
                preferred_tile_indices=preferred_tile_indices,
            )
            if entry.name.rstrip(b"\x00")[:4] == b"CUR1":
                # CUR1 is a composite container.  A package normally carries
                # all of Majesty's stock cursor sets plus one private set.  Art
                # analysis has already proven which references belong to that
                # package by filtering out every byte-identical stock set.
                # Relocate only that proven subset; otherwise a private
                # dependency that shares an index with an inherited cursor can
                # mutate the inherited set and create a false CUR1 conflict.
                allowed_offsets = {
                    reference.offset
                    for reference in proven_references
                    if reference.entry_name.rstrip(b"\x00")
                    == entry.name.rstrip(b"\x00")
                }
                parsed = replace(
                    parsed,
                    references=tuple(
                        reference
                        for reference in parsed.references
                        if reference.offset in allowed_offsets
                    ),
                )
            custom_parsed.append(parsed)
        custom_references = {
            reference.tile_index
            for parsed in custom_parsed
            for reference in parsed.references
        }
        custom_mapping = {
            old: new for old, new in mapping.items() if old in custom_references
        }
        unproven = set(mapping).difference(inherited_references, custom_references)
        if unproven:
            try:
                raise UnprovenReferenceError(unproven)
            except UnprovenReferenceError as exc:
                raise ComposeError(f"{owner}: {exc}") from exc
        inherited_rewritten = rewrite_stock_imag_entries(
            inherited_entries,
            inherited_mapping,
            tile_count=tile_allocation.final_count,
        )
        custom_rewritten = rewrite_parsed_imag_entries(
            custom_entries,
            custom_mapping,
            custom_parsed,
        )
        combined_entries = tuple(
            next(
                item
                for item in (*inherited_rewritten.entries, *custom_rewritten.entries)
                if item.name == source_entry.name
            )
            for source_entry in imag_entries
        )
        imag_reports.extend(
            (
                (owner, inherited_rewritten.report),
                (owner, custom_rewritten.report),
            )
        )
        for entry_order, entry in enumerate(combined_entries):
            imag_resources.append(
                CamResource(
                    owner=owner,
                    source=path,
                    cam_order=0,
                    section_order=0,
                    entry_order=entry_order,
                    section=b"IMAG",
                    entry=entry,
                )
            )
    cursor_resources = tuple(
        resource
        for resource in imag_resources
        if resource.entry.name.rstrip(b"\x00")[:4] == b"CUR1"
    )
    ordinary_imag_resources = tuple(
        resource
        for resource in imag_resources
        if resource.entry.name.rstrip(b"\x00")[:4] != b"CUR1"
    )
    # Stock-relative union: an inherited stock IMAG carried only to reach a
    # provider's positional changes is not a competing named value.  When one
    # compatible provider owns a custom IMAG payload, retain that payload and
    # let the other provider's disjoint TILE/palette writes coexist beneath it.
    custom_payloads_by_key: dict[bytes, set[bytes]] = {}
    for resource in ordinary_imag_resources:
        if resource.entry.data not in effective_stock_image_payloads.get(
            resource.key, set()
        ):
            custom_payloads_by_key.setdefault(resource.key, set()).add(
                resource.entry.data
            )
    uniquely_custom_keys = {
        key
        for key, payloads in custom_payloads_by_key.items()
        if len(payloads) == 1
    }
    ordinary_imag_resources = tuple(
        resource
        for resource in ordinary_imag_resources
        if resource.key not in uniquely_custom_keys
        or resource.entry.data
        not in effective_stock_image_payloads.get(resource.key, set())
    )
    imag_entries, _imag_selections = merge_named_resources(
        ordinary_imag_resources,
        b"IMAG",
    )
    if cursor_resources:
        stock_cursor = next(
            entry
            for entry in _require_section(stock, b"IMAG").entries
            if entry.name.rstrip(b"\x00")[:4] == b"CUR1"
        )
        ancestor_cursors = tuple(
            entry
            for archive in fallthrough_ancestors
            for entry in _require_section(archive, b"IMAG").entries
            if entry.name.rstrip(b"\x00")[:4] == b"CUR1"
        )
        imag_entries = (
            *imag_entries,
            _merge_tactical_cursor_entry(
                stock_cursor,
                ancestor_cursors,
                cursor_resources,
            ),
        )

    imag_entries = _materialize_required_stock_imag_entries(
        imag_entries,
        stock,
        required_stock_imag_ids,
        domain=domain,
    )

    stock_tiles = _require_section(stock, b"TILE")
    output_tiles = _blank_positional_section(
        stock_tiles, tile_allocation.final_count
    )
    for inventory, _path, _archive in providers:
        owner = inventory.selected.alias
        mapping = tile_allocation.mapping_for(owner)
        for change in analysis_by_owner[owner].tile_delta.changes:
            destination = mapping.get(change.index, change.index)
            source_entry = rewritten_tiles[owner][change.index]
            _place_positional(output_tiles, destination, source_entry, owner, b"TILE")

    _materialize_imag_tile_dependencies(
        output_tiles,
        stock_tiles,
        imag_entries,
    )

    stock_images = _require_section(stock, b"IMAG")
    sections = [
        CamSection(
            extension=b"IMAG",
            entries=imag_entries,
            padding=stock_images.padding,
        ),
        CamSection(
            extension=b"TILE",
            entries=tuple(output_tiles),
            padding=stock_tiles.padding,
        ),
    ]
    if palette_allocation is not None:
        palette_extension = next(
            analysis.palette_delta.extension
            for analysis in analyses
            if analysis.palette_delta is not None
        )
        stock_palettes = _require_section(stock, palette_extension)
        output_palettes = _blank_positional_section(
            stock_palettes, palette_allocation.final_count
        )
        for inventory, _path, _archive in providers:
            owner = inventory.selected.alias
            analysis = analysis_by_owner[owner]
            if analysis.palette_delta is None:
                continue
            mapping = palette_allocation.mapping_for(owner)
            for change in analysis.palette_delta.changes:
                destination = mapping.get(change.index, change.index)
                _place_positional(
                    output_palettes,
                    destination,
                    change.entry,
                    owner,
                    palette_extension,
                )
        _materialize_effective_stock_prefix(output_palettes, stock_palettes)
        palette_section = CamSection(
            extension=palette_extension,
            entries=tuple(output_palettes),
            padding=stock_palettes.padding,
        )
        validate_external_palette_closure(sections[1], palette_section)
        sections.append(
            palette_section
        )

    return ArtDomainComposeResult(
        domain=domain,
        archive=CamArchive(sections=tuple(sections)),
        analyses=tuple(analyses),
        tile_collisions=tile_collisions,
        palette_collisions=palette_collisions,
        report=ArtRelocationReport(
            tile_allocation=tile_allocation,
            palette_allocation=palette_allocation,
            imag_reports=tuple(imag_reports),
            palette_reports=tuple(palette_reports),
        ),
    )


def _coalesce_identical_art_providers(
    providers: Sequence[tuple[PackageInventory, Path, CamArchive]],
    analyses: Sequence[ArtArchiveAnalysis],
) -> tuple[
    tuple[tuple[PackageInventory, Path, CamArchive], ...],
    tuple[ArtArchiveAnalysis, ...],
]:
    """Keep one copy of an exact effective archive shared by several owners.

    Retained ancestor dependencies are deliberately relocated away from their
    stock slots. Relocating two byte-identical providers independently would
    give their otherwise identical IMAG records different rewritten indices
    and manufacture a named-resource conflict. One representative preserves
    the complete shared visual result without duplicating its positional run.
    """

    analysis_by_owner = {analysis.mod_id: analysis for analysis in analyses}
    seen: list[CamArchive] = []
    output_providers: list[tuple[PackageInventory, Path, CamArchive]] = []
    output_analyses: list[ArtArchiveAnalysis] = []
    for provider in providers:
        inventory, _path, archive = provider
        if archive in seen:
            continue
        seen.append(archive)
        output_providers.append(provider)
        output_analyses.append(analysis_by_owner[inventory.selected.alias])
    return tuple(output_providers), tuple(output_analyses)


def _materialize_required_stock_imag_entries(
    entries: Sequence[CamEntry],
    stock: CamArchive,
    required_ids: Sequence[bytes],
    *,
    domain: str,
) -> tuple[CamEntry, ...]:
    """Carry exact stock IMAG records required by a runtime presenter.

    Some stock controllers name an IMAG atlas directly instead of resolving it
    through a package description.  A private runtime feature that reuses such
    a controller therefore needs the controller's exact stock atlas in the
    composed archive, together with the TILE closure materialized below.  A
    package may carry the same stock record, but it cannot replace the fixed
    layout expected by the stock controller.
    """

    output = list(entries)
    by_id = {
        entry.name.rstrip(b"\x00")[:4]: entry
        for entry in output
    }
    stock_by_id = {
        entry.name.rstrip(b"\x00")[:4]: entry
        for entry in _require_section(stock, b"IMAG").entries
    }
    for required_id in dict.fromkeys(required_ids):
        if len(required_id) != 4:
            raise ComposeError(
                f"required stock {domain} IMAG ID must contain four bytes: "
                f"{required_id!r}"
            )
        stock_entry = stock_by_id.get(required_id)
        if stock_entry is None:
            raise ComposeError(
                f"required stock {domain} IMAG {_display_key(required_id)} is missing"
            )
        existing = by_id.get(required_id)
        if existing is not None:
            if existing.data != stock_entry.data:
                raise ComposeError(
                    f"required stock {domain} IMAG {_display_key(required_id)} "
                    "was replaced by a selected package"
                )
            continue
        output.append(stock_entry)
        by_id[required_id] = stock_entry
    return tuple(output)


def _effective_analysis_tile_entries(
    archive: CamArchive,
    analysis: ArtArchiveAnalysis,
) -> tuple[CamEntry, ...]:
    """Materialize the effective payload for every analyzed TILE change."""

    entries = list(_require_section(archive, b"TILE").entries)
    # Art analysis promotes every typed stock/fall-through dependency into
    # the owner's effective TILE delta. Relocation must carry that promoted
    # payload, not the package's original empty placeholder; otherwise a
    # rewritten IMAG points at an allocated but blank slot.
    for change in analysis.tile_delta.changes:
        entries[change.index] = change.entry
    return tuple(entries)


def _analysis_owned_imag_keys(
    analysis: ArtArchiveAnalysis,
    *,
    effective_stock_image_payloads: Mapping[bytes, set[bytes]],
) -> frozenset[bytes]:
    """Return only IMAG records whose visual result this provider changes.

    A collapsed art archive is an effective native view and therefore contains
    effective-stock records. Those records are ancestry evidence, not writes
    for the generated load-last patch. An older ancestor payload is still an
    authored write when it differs from the effective installed value.
    An IMAG is owned when its named payload differs from effective stock or
    when it reaches a package-owned TILE/palette change.
    """

    keys = {
        entry.name.rstrip(b"\x00")[:4]
        for entry in analysis.imag_entries
        if entry.data
        not in effective_stock_image_payloads.get(
            entry.name.rstrip(b"\x00")[:4], set()
        )
    }
    private_tiles = set(analysis.tile_delta.changed_indices).difference(
        analysis.retained_tile_dependencies
    )
    palette = analysis.palette_delta
    private_palettes = (
        set(palette.changed_indices).difference(
            analysis.retained_palette_dependencies
        )
        if palette is not None
        else set()
    )
    if private_palettes:
        private_tiles.update(
            reference.tile_index
            for reference in analysis.tile_palette_references
            if reference.palette_index in private_palettes
        )
    keys.update(
        reference.entry_name.rstrip(b"\x00")[:4]
        for reference in analysis.imag_references
        if reference.tile_index in private_tiles
    )
    return frozenset(keys)


def _materialize_imag_tile_dependencies(
    output_tiles: list[CamEntry],
    stock_tiles: CamSection,
    imag_entries: Sequence[CamEntry],
) -> tuple[int, ...]:
    """Close stock TILE dependencies of every emitted IMAG record.

    Synthesized resources such as merged CUR1 contain both retained stock sets
    and private sets. The mod analyses account for package-owned art, but the
    synthesized record can still reference unchanged stock TILEs. Materialize
    those exact stock payloads so a composed positional table never blanks a
    valid stock frame during a private-to-stock UI transition.
    """

    referenced: set[int] = set()
    for entry in imag_entries:
        accepted = False
        errors: list[Exception] = []
        for parser in (
            parse_imag_tile_references,
            parse_stock_imag_tile_references,
        ):
            try:
                parsed = parser(
                    entry.data,
                    tile_count=len(output_tiles),
                    entry_name=entry.name,
                )
            except (ArtFormatError, ValueError) as exc:
                errors.append(exc)
                continue
            accepted = True
            referenced.update(reference.tile_index for reference in parsed.references)
        if not accepted:
            raise ComposeError(
                f"{_display_key(entry.name[:4])}: cannot prove emitted IMAG TILE "
                f"dependencies: {errors[0]}"
            )

    materialized = []
    for index in sorted(referenced):
        if output_tiles[index].data or index >= len(stock_tiles.entries):
            continue
        stock_entry = stock_tiles.entries[index]
        if not stock_entry.data:
            continue
        output_tiles[index] = stock_entry
        materialized.append(index)
    return tuple(materialized)


def _split_imag_sets(entry: CamEntry) -> tuple[bytes, tuple[tuple[int, bytes], ...]]:
    data = entry.data
    if len(data) < 24:
        raise ComposeError(f"{_display_key(entry.name[:4])}: truncated IMAG set table")
    count = struct.unpack_from("<I", data, 20)[0]
    table_end = 24 + count * 8
    if count == 0 or table_end > len(data):
        raise ComposeError(f"{_display_key(entry.name[:4])}: invalid IMAG set count")
    directory = tuple(
        struct.unpack_from("<II", data, 24 + index * 8)
        for index in range(count)
    )
    offsets = tuple(offset for _set_id, offset in directory)
    if (
        offsets != tuple(sorted(offsets))
        or len(set(offsets)) != len(offsets)
        or offsets[0] < table_end
        or offsets[-1] >= len(data)
    ):
        raise ComposeError(f"{_display_key(entry.name[:4])}: invalid IMAG set offsets")
    sets = tuple(
        (
            set_id,
            data[offset:(directory[index + 1][1] if index + 1 < count else len(data))],
        )
        for index, (set_id, offset) in enumerate(directory)
    )
    if len({set_id for set_id, _payload in sets}) != len(sets):
        raise ComposeError(f"{_display_key(entry.name[:4])}: duplicate IMAG set ID")
    return data[:20], sets


def _join_imag_sets(
    entry: CamEntry,
    header: bytes,
    sets: Sequence[tuple[int, bytes]],
) -> CamEntry:
    """Rebuild one validated IMAG set directory without changing set payloads."""

    table_end = 24 + len(sets) * 8
    cursor = table_end
    directory = bytearray()
    payloads = bytearray()
    for set_id, payload in sets:
        directory.extend(struct.pack("<II", set_id, cursor))
        payloads.extend(payload)
        cursor += len(payload)
    return CamEntry(
        name=entry.name,
        data=b"".join(
            (header, struct.pack("<I", len(sets)), directory, payloads)
        ),
    )


def _strip_unowned_secondary_imag_layers(
    archive: CamArchive,
    analysis: ArtArchiveAnalysis,
) -> CamArchive:
    """Drop stock fall-through layers beneath an explicitly private base layer.

    Majesty encodes additional visual layers by placing a one-based layer number
    in the high byte of an IMAG set ID.  A stock-derived private sprite can
    replace the base set while accidentally retaining a template building's
    secondary layer through empty positional TILE slots.  That produces valid
    but unrelated stock art at runtime (for example Marketplace awnings over a
    private building).

    Empty slots are implicit fall-through, not an ownership declaration.  When
    a base layer references package-owned TILE data, suppress a corresponding
    secondary layer only when every one of its TILE references is empty in the
    package.  A package that intentionally keeps or replaces the layer can do so
    simply by carrying its TILE payloads, so this rule remains content-agnostic.
    """

    tile_section = _require_section(archive, b"TILE")
    imag_section = _require_section(archive, b"IMAG")
    references_by_entry_and_set: dict[tuple[bytes, int], set[int]] = {}
    for reference in analysis.imag_references:
        references_by_entry_and_set.setdefault(
            (reference.entry_name.rstrip(b"\x00"), reference.set_id), set()
        ).add(reference.tile_index)

    changed = False
    output_entries: list[CamEntry] = []
    for entry in imag_section.entries:
        header, sets = _split_imag_sets(entry)
        set_ids = {set_id for set_id, _payload in sets}
        entry_key = entry.name.rstrip(b"\x00")
        private_base_sets = {
            set_id
            for set_id in set_ids
            if set_id < 0x01000000
            and any(
                index < len(tile_section.entries)
                and bool(tile_section.entries[index].data)
                and index not in analysis.retained_tile_dependencies
                for index in references_by_entry_and_set.get(
                    (entry_key, set_id), ()
                )
            )
        }
        stripped: set[int] = set()
        for set_id in set_ids:
            if set_id < 0x01000000:
                continue
            base_set_id = set_id & 0x00FFFFFF
            if base_set_id not in private_base_sets:
                continue
            referenced = references_by_entry_and_set.get((entry_key, set_id), set())
            if not referenced:
                continue
            if all(
                index < len(tile_section.entries)
                and not tile_section.entries[index].data
                for index in referenced
            ):
                stripped.add(set_id)
        if stripped:
            kept_sets = tuple(
                item for item in sets if item[0] not in stripped
            )
            output_entries.append(_join_imag_sets(entry, header, kept_sets))
            changed = True
        else:
            output_entries.append(entry)

    if not changed:
        return archive
    return CamArchive(
        sections=tuple(
            CamSection(
                extension=section.extension,
                entries=(
                    tuple(output_entries)
                    if section.extension == b"IMAG"
                    else section.entries
                ),
                padding=section.padding,
            )
            for section in archive.sections
        )
    )


def _merge_tactical_cursor_entry(
    stock: CamEntry,
    ancestors: Sequence[CamEntry],
    resources: Sequence[CamResource],
) -> CamEntry:
    """Merge CUR1 by its stock animation-set directory, never by raw overlay."""

    header, stock_sets = _split_imag_sets(stock)
    stock_variants: dict[int, set[bytes]] = {}
    for entry in (stock, *ancestors):
        candidate_header, sets = _split_imag_sets(entry)
        if candidate_header != header:
            raise ComposeError("CUR1 stock ancestors have incompatible IMAG headers")
        for set_id, payload in sets:
            stock_variants.setdefault(set_id, set()).add(payload)

    output = list(stock_sets)
    occupied = {set_id: payload for set_id, payload in stock_sets}
    owners: dict[int, str] = {}
    for resource in resources:
        candidate_header, sets = _split_imag_sets(resource.entry)
        if candidate_header != header:
            raise ComposeError(f"{resource.owner}: CUR1 has an incompatible IMAG header")
        for set_id, payload in sets:
            if payload in stock_variants.get(set_id, set()):
                continue
            if set_id in occupied:
                prior_owner = owners.get(set_id, "stock Majesty")
                if occupied[set_id] != payload:
                    raise ComposeError(
                        f"conflicting CUR1 cursor set {set_id}: "
                        f"{prior_owner}, {resource.owner}"
                    )
                continue
            occupied[set_id] = payload
            owners[set_id] = resource.owner
            output.append((set_id, payload))

    table_end = 24 + len(output) * 8
    cursor = table_end
    directory = bytearray()
    payloads = bytearray()
    for set_id, payload in output:
        directory.extend(struct.pack("<II", set_id, cursor))
        payloads.extend(payload)
        cursor += len(payload)
    return CamEntry(
        name=stock.name,
        data=b"".join((header, struct.pack("<I", len(output)), directory, payloads)),
    )


def _imag_set_start(entry: CamEntry, set_id: int) -> int:
    """Return one validated IMAG set's absolute payload offset."""

    _header, sets = _split_imag_sets(entry)
    if sum(candidate == set_id for candidate, _payload in sets) != 1:
        raise ComposeError(
            f"{_display_key(entry.name[:4])}: expected exactly one IMAG set {set_id}"
        )
    count = struct.unpack_from("<I", entry.data, 20)[0]
    return next(
        struct.unpack_from("<I", entry.data, 28 + index * 8)[0]
        for index in range(count)
        if struct.unpack_from("<I", entry.data, 24 + index * 8)[0] == set_id
    )


def _prove_private_cursor_set_clone(
    private_cursor: CamEntry,
    private_tiles: CamSection,
    private_set_id: int,
    stock_cursor: CamEntry,
    stock_tiles: CamSection,
    stock_set_id: int,
    primary_offsets: frozenset[int],
) -> tuple[bool, str]:
    """Prove a private CUR1 set is an exact stock clone with one glyph swap."""

    try:
        private_start = _imag_set_start(private_cursor, private_set_id)
        stock_start = _imag_set_start(stock_cursor, stock_set_id)
        private_payload = dict(_split_imag_sets(private_cursor)[1])[private_set_id]
        stock_payload = dict(_split_imag_sets(stock_cursor)[1])[stock_set_id]
        private_parsed = parse_stock_imag_tile_references(
            private_cursor.data,
            tile_count=len(private_tiles.entries),
            entry_name=private_cursor.name,
        )
        stock_parsed = parse_stock_imag_tile_references(
            stock_cursor.data,
            tile_count=len(stock_tiles.entries),
            entry_name=stock_cursor.name,
        )
    except (ArtFormatError, ComposeError, ValueError) as exc:
        return False, str(exc)

    private_refs = {
        reference.offset - private_start: reference
        for reference in private_parsed.references
        if reference.set_id == private_set_id
    }
    stock_refs = {
        reference.offset - stock_start: reference
        for reference in stock_parsed.references
        if reference.set_id == stock_set_id
    }
    if set(private_refs) != set(stock_refs):
        return False, "typed TILE-reference topology differs"
    if not primary_offsets.issubset(stock_refs):
        return False, "stock primary cursor fields are missing"
    if len(private_payload) != len(stock_payload):
        return False, "cursor set payload length differs"

    for offset in sorted(stock_refs):
        private = private_refs[offset]
        stock = stock_refs[offset]
        if (
            private.flag_bits != stock.flag_bits
            or private.direction != stock.direction
            or private.frame != stock.frame
            or private.layout != stock.layout
        ):
            return False, f"typed cursor field 0x{offset:X} differs"

    private_primary = {private_refs[offset].tile_index for offset in primary_offsets}
    stock_primary = {stock_refs[offset].tile_index for offset in primary_offsets}
    if len(stock_primary) != 1:
        return False, "stock primary cursor frames do not share one TILE"
    if len(private_primary) != 1:
        return False, "private primary cursor frames do not share one TILE"
    private_primary_index = next(iter(private_primary))
    if private_primary_index == next(iter(stock_primary)):
        return False, "private cursor did not replace the stock primary TILE"
    if (
        private_primary_index >= len(private_tiles.entries)
        or not private_tiles.entries[private_primary_index].data
    ):
        return False, f"private primary TILE {private_primary_index} is empty"

    # Compare every byte after erasing only the low 16-bit primary indices.
    # This preserves and proves flags, direction timing, hotspot geometry,
    # cleanup frames, and every other field in the stock lifecycle.
    normalized_private = bytearray(private_payload)
    normalized_stock = bytearray(stock_payload)
    for offset in primary_offsets:
        struct.pack_into("<H", normalized_private, offset, 0)
        struct.pack_into("<H", normalized_stock, offset, 0)
    if normalized_private != normalized_stock:
        return False, "cursor set differs outside its primary TILE indices"

    for offset, stock_ref in sorted(stock_refs.items()):
        if offset in primary_offsets:
            continue
        private_ref = private_refs[offset]
        if private_ref.tile_index != stock_ref.tile_index:
            return False, f"auxiliary cursor field 0x{offset:X} changed TILE"
        index = private_ref.tile_index
        if (
            index >= len(private_tiles.entries)
            or not private_tiles.entries[index].data
        ):
            return False, f"auxiliary TILE {index} is not carried by the package"
        if (
            index >= len(stock_tiles.entries)
            or private_tiles.entries[index].data != stock_tiles.entries[index].data
        ):
            return False, f"auxiliary TILE {index} is from a different stock dataset"
    return True, ""


def _validate_private_controller_cursor_sets(
    game_path: Path,
    inventories: Sequence[PackageInventory],
    registry: ResolvedControllerRegistry,
    panel_owners: Mapping[str, str],
) -> None:
    """Fail closed when a declared private cursor mixes stock art lineages."""

    requirements: list[tuple[str, int, int, frozenset[int], str]] = []
    for feature in registry.hostile_monster_flags:
        template_set, primary_offsets, label = _HOSTILE_MONSTER_FLAG_CURSOR_TEMPLATE
        requirements.append(
            (
                panel_owners[feature.panel_key],
                1000 + feature.cursor_ordinal,
                template_set,
                primary_offsets,
                label,
            )
        )
    for feature in registry.sovereign_target_actions:
        template_set, primary_offsets, label = _SOVEREIGN_TARGET_CURSOR_TEMPLATE
        requirements.append(
            (
                panel_owners[feature.panel_key],
                1000 + feature.cursor_ordinal,
                template_set,
                primary_offsets,
                label,
            )
        )
    if not requirements:
        return

    original = read_cam(game_path / "Data" / "interfacedata.cam")
    effective = _effective_stock_art_ancestor(game_path, "interface")
    stock_lineages = (
        ("Original", original),
        ("Northern Expansion", effective),
    )
    inventories_by_owner = {
        inventory.selected.alias: inventory for inventory in inventories
    }

    for owner, private_set_id, stock_set_id, primary_offsets, label in dict.fromkeys(
        requirements
    ):
        inventory = inventories_by_owner[owner]
        providers: list[tuple[CamEntry, CamSection, Path]] = []
        for path in inventory.cams:
            archive = read_cam(path)
            tile_sections = [
                section for section in archive.sections if section.extension == b"TILE"
            ]
            for section in archive.sections:
                if section.extension != b"IMAG":
                    continue
                for entry in section.entries:
                    if entry.name.rstrip(b"\x00")[:4] != b"CUR1":
                        continue
                    _header, sets = _split_imag_sets(entry)
                    if any(set_id == private_set_id for set_id, _payload in sets):
                        if len(tile_sections) != 1:
                            raise ComposeError(
                                f"{owner}: private CUR1 set {private_set_id} must share "
                                "one archive with exactly one TILE section"
                            )
                        providers.append((entry, tile_sections[0], path))
        if len(providers) != 1:
            raise ComposeError(
                f"{owner}: expected exactly one package source for private CUR1 set "
                f"{private_set_id}; found {len(providers)}"
            )
        private_cursor, private_tiles, source = providers[0]

        failures = []
        for lineage_name, archive in stock_lineages:
            stock_tiles = _require_section(archive, b"TILE")
            stock_cursor = next(
                (
                    entry
                    for entry in _require_section(archive, b"IMAG").entries
                    if entry.name.rstrip(b"\x00")[:4] == b"CUR1"
                ),
                None,
            )
            if stock_cursor is None:
                failures.append(f"{lineage_name}: stock CUR1 is missing")
                continue
            accepted, reason = _prove_private_cursor_set_clone(
                private_cursor,
                private_tiles,
                private_set_id,
                stock_cursor,
                stock_tiles,
                stock_set_id,
                primary_offsets,
            )
            if accepted:
                break
            failures.append(f"{lineage_name}: {reason}")
        else:
            raise ComposeError(
                f"{owner}: private CUR1 set {private_set_id} does not preserve "
                f"Majesty's complete stock {label} cursor lifecycle and auxiliary "
                f"frames ({'; '.join(failures)}): {source}"
            )


def merge_description_resources(
    inventories: Sequence[PackageInventory],
    *,
    dialog_resolutions: Sequence[ResolvedBuildingDialog] | None = None,
    controlled_follower_markers: Sequence[str] = (),
    reserved_description_keys: Iterable[DescriptionKey] = (),
    reserved_description_names: Iterable[str] = (),
    resolutions: Mapping[DescriptionKey, DescriptionRecord] | None = None,
) -> DescriptionMergeResult:
    """Merge every XML Description and apply only declared building DialogIDs."""

    variants: list[tuple[str, bytes]] = []
    for inventory in inventories:
        owner = inventory.selected.alias
        effective: dict[DescriptionKey, DescriptionRecord] = {}
        for path in inventory.descriptions:
            payload = path.read_bytes()
            document = parse_descriptions(payload, source=str(path))
            # Majesty applies a component's Description directives in manifest
            # order. Later records from that same component replace earlier
            # records before the component competes with any other owner.
            effective.update(document.index)
        if effective:
            document = DescriptionsDocument(
                root_tag="Majesty",
                root_attributes=(),
                records=tuple(effective.values()),
                source=f"<{owner} effective native Description load order>",
            )
            variants.append((owner, serialize_descriptions(document)))

    if not variants and any(
        inventory.selected.package.definition.schema_version < 3
        for inventory in inventories
    ):
        raise ComposeError("selected packages provide no XML Description resources")

    definitions = {
        inventory.selected.alias: inventory.selected.package.definition
        for inventory in inventories
    }
    if dialog_resolutions is None:
        dialog_resolutions = resolve_building_dialogs(inventories)
    resolution_by_building = {
        (item.owner, item.local_name): item for item in dialog_resolutions
    }
    matched: dict[tuple[str, str], int] = {}

    def transform(owner: str, key: DescriptionKey, element):
        definition = definitions[owner]
        if definition is None:
            return element
        if element.get("subType") != "Building":
            return element
        local_name = element.get("Name", "")
        for building in definition.custom_buildings:
            if not _is_building_name(local_name, building.local_name):
                continue
            dialog = element.find("./Game/DialogID")
            if dialog is None or not dialog.get("value"):
                raise DescriptionFormatError(
                    f"{owner} {key!r} has no Game/DialogID for declared building "
                    f"{building.local_name!r}"
                )
            current = dialog.get("value")
            resolution = resolution_by_building.get((owner, building.local_name))
            if resolution is None:
                raise DescriptionFormatError(
                    f"{owner}: no resolved dialog exists for {building.local_name!r}"
                )
            source = resolution.source_dialog_id.decode("ascii")
            target = resolution.resolved_dialog_id.decode("ascii")
            allowed = (
                {building.dialog_id, building.controller_base}
                if definition.schema_version < 3
                else {source}
            )
            if current not in allowed:
                if definition.schema_version < 3:
                    raise DescriptionFormatError(
                        f"{owner} {key!r} DialogID {current!r} is neither declared "
                        f"dialog_id {building.dialog_id!r} nor controller_base "
                        f"{building.controller_base!r}"
                    )
                raise DescriptionFormatError(
                    f"{owner} {key!r} DialogID {current!r} does not match inferred "
                    f"source DialogID {source!r}"
                )
            dialog.set("value", target)
            marker = (owner, building.local_name)
            matched[marker] = matched.get(marker, 0) + 1
        return element

    requested_resolutions = dict(resolutions or {})
    used_resolutions: set[DescriptionKey] = set()

    def resolve(conflict):
        record = requested_resolutions.get(conflict.key)
        if record is not None:
            used_resolutions.add(conflict.key)
        return record

    result = merge_descriptions(
        b"<Majesty />",
        variants,
        transform=transform,
        resolve=resolve if requested_resolutions else None,
    )
    unused = set(requested_resolutions) - used_resolutions
    if unused:
        labels = ", ".join(repr(key) for key in sorted(unused))
        raise ComposeError(
            f"Description resolutions do not name real conflicts: {labels}"
        )
    for owner, definition in definitions.items():
        if definition is None:
            raise ComposeError(f"{owner}: a v1 mod definition is required")
        for building in definition.custom_buildings:
            if matched.get((owner, building.local_name), 0) == 0:
                raise ComposeError(
                    f"{owner}: declared building {building.local_name!r} did not "
                    "match any XML Description"
                )
    return _add_controlled_follower_marker_descriptions(
        result,
        controlled_follower_markers,
        reserved_description_keys=reserved_description_keys,
        reserved_description_names=reserved_description_names,
    )


def filter_passthrough_descriptions(
    result: DescriptionMergeResult,
    inventories: Sequence[PackageInventory],
    *,
    stock_records: Mapping[DescriptionKey, DescriptionRecord] | None = None,
    forced_keys: Iterable[DescriptionKey] = (),
) -> DescriptionMergeResult:
    """Keep only Description records required by the load-last patch.

    Ordinary-Mod-only records stay native unless multiple Standards require a
    typed merge. Merge records are retained only when their final value differs
    from installed stock. Generated records and explicitly reviewed resolution
    keys are always retained; the latter permits a deliberate choice to restore
    the stock value after an earlier native Standard override.
    """

    stock = dict(stock_records or {})
    owners_by_key: dict[DescriptionKey, set[str]] = {}
    standard_payloads_by_key: dict[DescriptionKey, set[tuple]] = {}
    standard_owners_by_key: dict[DescriptionKey, set[str]] = {}
    changed_merge_keys: set[DescriptionKey] = set()
    for inventory in inventories:
        owner = inventory.selected.alias
        effective: dict[DescriptionKey, DescriptionRecord] = {}
        for path in inventory.descriptions:
            document = _parse_description_file(path)
            # Match merge_description_resources: Majesty applies this owner's
            # Description directives in manifest order, so only its final
            # record for a key can affect the native result.
            effective.update(document.index)
        for key, record in effective.items():
            owners_by_key.setdefault(key, set()).add(owner)
            stock_record = stock.get(key)
            changed = (
                stock_record is None
                or record._fingerprint != stock_record._fingerprint
            )
            if changed:
                if not inventory.selected.semantic_passthrough:
                    changed_merge_keys.add(key)
            if inventory.selected.semantic_passthrough:
                standard_payloads_by_key.setdefault(key, set()).add(
                    record._fingerprint
                )
                standard_owners_by_key.setdefault(key, set()).add(owner)

    final_records = result.document.index
    explicit_stock_restorations = {
        key
        for key in forced_keys
        if key in final_records
        and key in stock
        and final_records[key]._fingerprint == stock[key]._fingerprint
    }
    keep = explicit_stock_restorations | changed_merge_keys | (
        set(final_records) - set(owners_by_key)
    ) | {
        key
        for key, payloads in standard_payloads_by_key.items()
        if len(standard_owners_by_key.get(key, ())) > 1 and len(payloads) > 1
    }
    records = tuple(record for record in result.document.records if record.key in keep)
    document = DescriptionsDocument(
        root_tag=result.document.root_tag,
        root_attributes=result.document.root_attributes,
        records=records,
        source="<merged reconciliation patch>",
    )
    deltas = tuple(
        replace(
            delta,
            records=tuple(record for record in delta.records if record.key in keep),
        )
        for delta in result.deltas
        if any(record.key in keep for record in delta.records)
    )
    return replace(
        result,
        document=document,
        payload=serialize_descriptions(document),
        deltas=deltas,
        selections=tuple(
            selection for selection in result.selections if selection.key in keep
        ),
    )


def merge_string_resources(
    inventories: Sequence[PackageInventory],
    *,
    resolutions: Mapping[StringKey, StringRecord] | None = None,
    stock_records: Mapping[StringKey, StringRecord] | None = None,
) -> StringsMergeResult | None:
    """Build the one final stock-relative overlay only when reconciliation needs it."""

    variants = []
    standard_dictionaries: list[frozenset[tuple[StringKey, bytes]]] = []
    for inventory in inventories:
        owner_records: dict[StringKey, StringRecord] = {}
        owner_order: list[StringKey] = []
        has_valid_strings_load = False
        for path in inventory.strings:
            try:
                document = load_strings(path)
            except StringsFormatError as exc:
                if inventory.selected.semantic_passthrough:
                    # Old ordinary Mods sometimes put a QDD quest-description
                    # file in <Strings>. The stock Strings XML loader ignores
                    # its contents; the quest system consumes QDD separately.
                    continue
                raise ComposeError(str(exc)) from exc
            has_valid_strings_load = True
            for key, record in document.index.items():
                if key not in owner_records:
                    owner_order.append(key)
                # The stock dictionary loader is last-write-wins within one
                # component, including across several <Strings> files.
                owner_records[key] = record
        if has_valid_strings_load:
            from .strings import StringsDocument

            variants.append(
                (
                    inventory.selected.alias,
                    StringsDocument(
                        tuple(owner_records[key] for key in owner_order),
                        f"<{inventory.selected.alias} Strings>",
                    ),
                )
            )
            if inventory.selected.semantic_passthrough:
                standard_dictionaries.append(
                    frozenset(
                        (key, record.payload)
                        for key, record in owner_records.items()
                    )
                )
    if not variants:
        return None
    stock = dict(stock_records or {})
    merge_owners = {
        inventory.selected.alias
        for inventory in inventories
        if not inventory.selected.semantic_passthrough
    }
    standard_owners = {
        inventory.selected.alias
        for inventory in inventories
        if inventory.selected.semantic_passthrough
    }
    candidates_by_key: dict[StringKey, list[tuple[str, StringRecord]]] = {}
    for owner, document in variants:
        for record in document.records:
            candidates_by_key.setdefault(record.key, []).append((owner, record))

    # Majesty replaces the active mod Strings dictionary on each valid load.
    # Two native Standards therefore cannot preserve different complete
    # dictionaries through load order, even when their keys are disjoint or
    # one dictionary is a strict subset of the other.  One generated union is
    # required whenever at least two selected Standard dictionaries differ.
    overlay_required = (
        len(standard_dictionaries) > 1
        and len(set(standard_dictionaries)) > 1
    )
    supplied_resolutions = dict(resolutions or {})
    for key, candidates in candidates_by_key.items():
        stock_record = stock.get(key)
        changed = tuple(
            (owner, record)
            for owner, record in candidates
            if stock_record is None or record.payload != stock_record.payload
        )
        if any(owner in merge_owners for owner, _record in changed):
            overlay_required = True
            break
        standard_candidates = tuple(
            (owner, record)
            for owner, record in candidates
            if owner in standard_owners
        )
        if (
            len({owner for owner, _record in standard_candidates}) > 1
            and len({record.payload for _owner, record in standard_candidates}) > 1
        ):
            overlay_required = True
            break
        resolution = supplied_resolutions.get(key)
        if (
            resolution is not None
            and stock_record is not None
            and resolution.payload == stock_record.payload
        ):
            overlay_required = True
            break
    if not overlay_required:
        # A lone (or mutually identical) native Standard modification already
        # loads in the game's normal dependency order. Re-emitting it would
        # create a needless global Strings overlay in the load-last profile.
        return None
    try:
        result = merge_strings(variants, resolutions=resolutions)
    except StringsFormatError as exc:
        raise ComposeError(str(exc)) from exc
    if result.conflicts:
        labels = ", ".join(repr(conflict.key) for conflict in result.conflicts)
        raise ComposeError(f"unresolved Strings conflicts: {labels}")
    forced = set(supplied_resolutions)
    records = tuple(
        record
        for record in result.records
        if record.key in forced
        or record.key not in stock
        or record.payload != stock[record.key].payload
    )
    if not records:
        return None
    return replace(
        result,
        payload=serialize_string_records(records),
        records=records,
    )


def _add_controlled_follower_marker_descriptions(
    result: DescriptionMergeResult,
    marker_names: Sequence[str],
    *,
    reserved_description_keys: Iterable[DescriptionKey],
    reserved_description_names: Iterable[str],
) -> DescriptionMergeResult:
    """Register private follower-state effectors using a stock overlay shape.

    Stock ``vines_icon`` is a persistent, manually checked/deleted effector with
    no callback. Its overlay is directionless, non-blocking, and hidden from
    the isometric view. The manager clones that exact lifecycle shape while
    changing only the private Description ID and Name used by generated GPL.
    """

    markers = tuple(sorted(set(marker_names), key=str.casefold))
    if len(markers) != len(tuple(marker_names)):
        raise ComposeError("controlled-follower marker names must be unique")
    if not markers:
        return result
    for marker in markers:
        if re.fullmatch(r"MCF[0-9A-F]{12}[1-4]", marker) is None:
            raise ComposeError(
                f"invalid generated controlled-follower marker name: {marker!r}"
            )

    existing_names = {
        element.get("Name", "").casefold()
        for record in result.document.records
        for element in (record.to_element(),)
        if element.get("Name")
    }
    unavailable_names = existing_names | {
        name.casefold() for name in reserved_description_names if name
    }
    duplicate_names = [
        marker for marker in markers if marker.casefold() in unavailable_names
    ]
    if duplicate_names:
        raise ComposeError(
            "generated controlled-follower marker Description Name already exists: "
            + ", ".join(duplicate_names)
        )

    unavailable = set(reserved_description_keys) | set(result.document.index)
    available = (
        f"MF{left}{right}"
        for left in "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        for right in "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        if ("Unit", f"MF{left}{right}") not in unavailable
    )
    root = ET.Element("Majesty")
    for marker in markers:
        try:
            description_id = next(available)
        except StopIteration as exc:  # pragma: no cover - 1296 private slots
            raise ComposeError(
                "no manager-owned MFxx follower-state Description IDs remain"
            ) from exc
        description = ET.SubElement(
            root,
            "Description",
            {
                "type": "Unit",
                "subType": "Overlay",
                "ID": description_id,
                "Name": marker,
                "Description": "Majesty Mod Manager follower speed state",
            },
        )
        engine = ET.SubElement(description, "Engine", {"version": "1"})
        for value in ("Directionless", "DontBlock", "NotVisibleInISOView"):
            ET.SubElement(engine, "Info", {"value": value})
        ET.SubElement(engine, "Menu", {"value": "11"})
        ET.SubElement(engine, "ImageIDBase", {"value": "CRB2"})
        ET.SubElement(engine, "DefaultSound", {"value": "0"})
        game = ET.SubElement(description, "Game", {"version": "1"})
        ET.SubElement(game, "DialogID", {"value": "0"})
        ET.SubElement(game, "StackPriority", {"value": "0"})

    generated = ET.tostring(root, encoding="utf-8", short_empty_elements=True)
    merged = merge_descriptions(
        result.document,
        (("<CAM Manager controlled-follower state>", generated),),
    )
    resolved_names = {
        element.get("Name")
        for record in merged.document.records
        for element in (record.to_element(),)
        if element.get("subType") == "Overlay"
    }
    missing = [marker for marker in markers if marker not in resolved_names]
    if missing:  # pragma: no cover - guarded by merge_descriptions
        raise ComposeError(
            "generated controlled-follower marker descriptions are missing: "
            + ", ".join(missing)
        )
    # ``result.document`` is the stock argument for this second merge, so the
    # merge helper reports only the newly generated marker records. Preserve
    # the already selected source records as part of the final output metadata.
    return replace(
        merged,
        deltas=(*result.deltas, *merged.deltas),
        selections=(*result.selections, *merged.selections),
    )


def analyze_description_stock_deltas(
    game_path: Path,
    inventories: Sequence[PackageInventory],
    *,
    descriptions: DescriptionMergeResult | None = None,
) -> tuple[DescriptionStockDelta, ...]:
    """Classify Description records against the effective stock baseline.

    Catalog/preflight callers may omit ``descriptions`` to classify package
    inputs directly. Composition passes its final filtered result so report and
    controller evidence describe only records that the load-last profile will
    actually emit, attributed to the owners selected for those records.
    """

    stock = _load_effective_stock_descriptions(game_path)
    if descriptions is not None:
        sources: dict[tuple[str, DescriptionKey], str] = {}
        owners_by_key: dict[DescriptionKey, list[str]] = {}
        for inventory in inventories:
            owner = inventory.selected.alias
            for path in inventory.descriptions:
                document = _parse_description_file(path)
                relative = path.relative_to(
                    inventory.selected.package.root
                ).as_posix()
                for key in document.index:
                    sources[(owner, key)] = relative
                    owners_by_key.setdefault(key, []).append(owner)

        selections = {selection.key: selection for selection in descriptions.selections}
        missing = set(descriptions.document.index) - set(selections)
        if missing:
            labels = ", ".join(repr(key) for key in sorted(missing))
            raise ComposeError(
                "final Description output is missing selected-owner metadata: "
                + labels
            )

        result: list[DescriptionStockDelta] = []
        for record in descriptions.document.records:
            selection = selections[record.key]
            owners = selection.owners
            if owners == ("<resolution>",):
                # A stock-relative three-way result is manager-authored but is
                # jointly attributable to the source owners whose records it
                # reconciles. Keep their controller evidence attached.
                owners = tuple(dict.fromkeys(owners_by_key.get(record.key, ())))
                if not owners:
                    owners = selection.owners
            stock_item = stock.get(record.key)
            if stock_item is None:
                kind = "addition"
                stock_source = None
            else:
                stock_record, stock_source = stock_item
                kind = (
                    "identical_stock"
                    if record._fingerprint == stock_record._fingerprint
                    else "stock_override"
                )
            for owner in owners:
                result.append(
                    DescriptionStockDelta(
                        owner=owner,
                        key=record.key,
                        kind=kind,
                        mod_source=sources.get((owner, record.key), "<generated>"),
                        stock_source=stock_source,
                    )
                )
        return tuple(result)

    result: list[DescriptionStockDelta] = []
    for inventory in inventories:
        owner = inventory.selected.alias
        for path in inventory.descriptions:
            document = _parse_description_file(path)
            for key, record in document.index.items():
                stock_item = stock.get(key)
                if stock_item is None:
                    kind = "addition"
                    stock_source = None
                else:
                    stock_record, stock_source = stock_item
                    kind = (
                        "identical_stock"
                        if record._fingerprint == stock_record._fingerprint
                        else "stock_override"
                    )
                result.append(
                    DescriptionStockDelta(
                        owner=owner,
                        key=key,
                        kind=kind,
                        mod_source=path.relative_to(inventory.selected.package.root).as_posix(),
                        stock_source=stock_source,
                    )
                )
    return tuple(result)


def _load_effective_stock_descriptions(
    game_path: Path,
) -> dict[DescriptionKey, tuple[object, str]]:
    """Load the effective Original+MX stock Description index."""

    sdk_root = game_path / "SDK" / "OriginalQuests"
    paths: list[Path] = []
    for relative_directory in (Path("Data"), Path("DataMX")):
        directory = sdk_root / relative_directory
        if not directory.is_dir():
            raise ComposeError(f"stock Description directory was not found: {directory}")
        paths.extend(
            sorted(directory.glob("*.xml"), key=lambda item: item.name.casefold())
        )
    signature = tuple(
        (str(path), info.st_size, info.st_mtime_ns)
        for path in paths
        for info in (path.stat(),)
    )
    return dict(_load_effective_stock_descriptions_cached(str(sdk_root), signature))


@lru_cache(maxsize=8)
def _load_effective_stock_descriptions_cached(
    sdk_root_text: str,
    signature: tuple[tuple[str, int, int], ...],
) -> tuple[tuple[DescriptionKey, tuple[object, str]], ...]:
    sdk_root = Path(sdk_root_text)
    stock: dict[DescriptionKey, tuple[object, str]] = {}
    for relative_directory in (Path("Data"), Path("DataMX")):
        directory = sdk_root / relative_directory
        layer_seen: set[DescriptionKey] = set()
        for path_text, _size, _mtime_ns in signature:
            path = Path(path_text)
            if path.parent != directory:
                continue
            document = _parse_description_file(path)
            duplicate = layer_seen.intersection(document.index)
            if duplicate:
                labels = ", ".join(repr(key) for key in sorted(duplicate))
                raise ComposeError(
                    f"stock Description layer {relative_directory} has duplicate "
                    f"keys across files: {labels}"
                )
            layer_seen.update(document.index)
            for key, record in document.index.items():
                stock[key] = (record, path.relative_to(sdk_root).as_posix())
    return tuple(stock.items())


def validate_controller_stock_evidence(
    game_path: Path,
    inventories: Sequence[PackageInventory],
    registry: ResolvedControllerRegistry,
    *,
    controller_panels: Sequence[ResolvedControllerPanel] = (),
    controller_toggles: Sequence[ResolvedControllerToggle] = (),
    runtime_feature_registry: RuntimeFeatureRegistry = RuntimeFeatureRegistry(),
    description_stock_deltas: Sequence[DescriptionStockDelta] | None = None,
) -> None:
    """Prove private controller identifiers are additions, not stock overrides."""

    needs_stock_proof = (
        bool(_controller_record_count(registry))
        or bool(runtime_feature_registry.enchantment_rows)
        or any(
        inventory.selected.package.definition is not None
        and inventory.selected.package.definition.schema_version == 3
        for inventory in inventories
        )
    )
    if not needs_stock_proof:
        return
    stock_building_ids = tuple(
        key[1]
        for key, (record, _source) in _load_effective_stock_descriptions(
            game_path
        ).items()
        if record.to_element().get("subType") == "Building"
    )
    deltas = tuple(description_stock_deltas or analyze_description_stock_deltas(
        game_path, inventories
    ))
    description_kinds: dict[tuple[str, DescriptionKey], str] = {}
    description_subtypes: dict[tuple[str, DescriptionKey], str] = {}
    for inventory in inventories:
        owner = inventory.selected.alias
        for path in inventory.descriptions:
            document = _parse_description_file(path)
            for record in document.records:
                description_subtypes[(owner, record.key)] = (
                    record.to_element().get("subType", "")
                )
    for delta in deltas:
        description_kinds[(delta.owner, delta.key)] = delta.kind

    for inventory in inventories:
        definition = inventory.selected.package.definition
        if definition is None or definition.schema_version != 3:
            continue
        owner = inventory.selected.alias
        declared = tuple(definition.custom_buildings)
        resource_counts: dict[tuple[bytes, bytes], int] = {}
        for resource in inventory.resources:
            key = (resource.section, resource.key)
            resource_counts[key] = resource_counts.get(key, 0) + 1
        for path in inventory.descriptions:
            document = _parse_description_file(path)
            for record in document.records:
                element = record.to_element()
                if element.get("subType") != "Building":
                    continue
                if description_kinds.get((owner, record.key)) != "addition":
                    continue
                dialog = element.find("./Game/DialogID")
                dialog_text = dialog.get("value", "") if dialog is not None else ""
                try:
                    source = dialog_text.encode("ascii")
                except UnicodeEncodeError:
                    continue
                if len(source) != 4:
                    # Lairs commonly use DialogID 0, and additions may reuse a
                    # stock dialog without shipping a private panel.
                    continue
                smnu_count = resource_counts.get((b"SMNU", source), 0)
                strt_count = resource_counts.get((b"STRT", source), 0)
                if smnu_count == 0 and strt_count == 0:
                    continue
                if smnu_count != 1 or strt_count != 1:
                    raise ComposeError(
                        f"{owner}: package-added Building Description "
                        f"{record.key!r} references private panel "
                        f"{dialog_text}, which requires exactly one package-owned "
                        f"SMNU and STRT resource; found {smnu_count} and {strt_count}"
                    )
                matches = [
                    building
                    for building in declared
                    if _is_building_name(
                        element.get("Name", ""), building.local_name
                    )
                ]
                if len(matches) != 1:
                    raise ComposeError(
                        f"{owner}: package-added Building Description "
                        f"{record.key!r} must match exactly one declared "
                        f"custom_building; found {len(matches)}"
                    )

    panel_owners: dict[str, str] = {}
    for item in controller_panels:
        if item.qualified_panel_key in panel_owners:
            raise ComposeError(
                f"controller panel owner metadata repeats "
                f"{item.qualified_panel_key!r}"
            )
        panel_owners[item.qualified_panel_key] = item.owner
    registry_panel_keys = {
        item.panel_key for item in (*registry.panels, *registry.reward_panels,
                                    *registry.occupant_action_panels,
                                    *registry.quest_boards)
    }
    if registry_panel_keys != set(panel_owners):
        raise ComposeError(
            "controller stock evidence requires exact manager-owned panel "
            "ownership metadata"
        )

    _validate_private_controller_cursor_sets(
        game_path,
        inventories,
        registry,
        panel_owners,
    )

    for panel in registry.panels:
        panel_owner = panel_owners[panel.panel_key]
        stock_matches = sorted(
            identifier
            for identifier in stock_building_ids
            if identifier.startswith(panel.building_family_id)
        )
        if stock_matches:
            raise ComposeError(
                f"controller building_family_id {panel.building_family_id!r} "
                "collides with untouched stock Building Description IDs: "
                + ", ".join(stock_matches)
            )
        matches = [
            (owner, key, kind)
            for (owner, key), kind in description_kinds.items()
            if key[1].startswith(panel.building_family_id)
            and description_subtypes.get((owner, key)) == "Building"
        ]
        if (
            not matches
            or any(owner != panel_owner for owner, _key, _kind in matches)
            or any(kind != "addition" for _owner, _key, kind in matches)
        ):
            rendered = ", ".join(
                f"{owner}:{key[1]}={kind}" for owner, key, kind in matches
            ) or "none"
            raise ComposeError(
                f"controller building_family_id {panel.building_family_id!r} "
                f"must identify only package-added Building Descriptions owned "
                f"by {panel_owner!r} and cannot override stock IDs "
                f"(matches: {rendered})"
            )

    _validate_authored_controller_panel_controls(
        inventories,
        registry,
        controller_panels,
    )
    _validate_authored_building_toggle_controls(
        inventories,
        registry,
        controller_toggles,
    )

    for row in runtime_feature_registry.enchantment_rows:
        matches = [
            (owner, key, kind)
            for (owner, key), kind in description_kinds.items()
            if key[1] == row.overlay_id
            and description_subtypes.get((owner, key)) == "Overlay"
        ]
        if len(matches) != 1 or matches[0][2] != "addition":
            rendered = ", ".join(
                f"{owner}:{key[1]}={kind}" for owner, key, kind in matches
            ) or "none"
            raise ComposeError(
                f"enchantment row overlay_id {row.overlay_id!r} must identify "
                "exactly one package-added Overlay Description and cannot "
                f"override a stock ID (matches: {rendered})"
            )

    for action in registry.sovereign_target_actions:
        matches = [
            (owner, key, kind)
            for (owner, key), kind in description_kinds.items()
            if key[1] == action.private_unit_id
            and description_subtypes.get((owner, key)) == "Character"
        ]
        if len(matches) != 1 or matches[0][2] != "addition":
            rendered = ", ".join(
                f"{owner}:{key[1]}={kind}" for owner, key, kind in matches
            ) or "none"
            raise ComposeError(
                f"controller private_unit_id {action.private_unit_id!r} must "
                "identify exactly one package-added Character Description and "
                f"cannot override a stock ID (matches: {rendered})"
            )
    for action in registry.hostile_monster_flags:
        matches = [
            (owner, key, kind)
            for (owner, key), kind in description_kinds.items()
            if key[1] == action.private_flag_id
            and description_subtypes.get((owner, key)) == "Overlay"
        ]
        if len(matches) != 1 or matches[0][2] != "addition":
            rendered = ", ".join(
                f"{owner}:{key[1]}={kind}" for owner, key, kind in matches
            ) or "none"
            raise ComposeError(
                f"controller private_flag_id {action.private_flag_id!r} must "
                "identify exactly one package-added Overlay Description and "
                f"cannot override a stock ID (matches: {rendered})"
            )


def _validate_authored_controller_panel_controls(
    inventories: Sequence[PackageInventory],
    registry: ResolvedControllerRegistry,
    controller_panels: Sequence[ResolvedControllerPanel],
) -> None:
    """Prove every package-owned presenter control exists before launch.

    SMNU is a DWORD-aligned tagged resource.  Control identifiers appear as
    aligned DWORD values even when their enclosing record type differs (for
    example AP22's quantity child and AP99's command row).  The manager does
    not reinterpret or rewrite those records; it only proves that each ID a
    recipe will address is present in the exact parent or child panel it owns.
    Stock descriptor-template IDs are validated separately by the bounded
    recipe parser and are intentionally not required in package SMNU data.
    """

    inventory_by_owner = {
        inventory.selected.alias: inventory for inventory in inventories
    }
    for resolved in controller_panels:
        inventory = inventory_by_owner.get(resolved.owner)
        if inventory is None:
            raise ComposeError(
                f"controller panel {resolved.qualified_panel_key!r} has no "
                f"package inventory for owner {resolved.owner!r}"
            )
        parent_sources = _description_dialog_sources(
            inventory,
            resolved.raw_parent_building,
        )
        if len(parent_sources) != 1:
            rendered = ", ".join(repr(item) for item in sorted(parent_sources))
            raise ComposeError(
                f"{resolved.owner}: controller panel {resolved.raw_panel_key!r} "
                f"cannot resolve one source panel for parent building "
                f"{resolved.raw_parent_building!r} (found: {rendered or 'none'})"
            )
        parent_text = next(iter(parent_sources))
        try:
            parent_source = parent_text.encode("ascii")
        except UnicodeEncodeError as exc:  # pragma: no cover - dialog resolver guards it
            raise ComposeError(
                f"{resolved.owner}: parent DialogID {parent_text!r} is not ASCII"
            ) from exc
        parent_payload = _owned_smnu_payload(
            inventory,
            parent_source,
            f"parent panel {parent_text}",
        )
        child_payload = _owned_smnu_payload(
            inventory,
            resolved.source_dialog_id,
            f"secondary panel {_display_key(resolved.source_dialog_id)}",
        )
        _validate_controller_panel_controls(
            registry,
            resolved.qualified_panel_key,
            parent_payload,
            child_payload,
            owner=resolved.owner,
            parent_label=parent_text,
            child_label=_display_key(resolved.source_dialog_id),
        )


def _validate_authored_building_toggle_controls(
    inventories: Sequence[PackageInventory],
    registry: ResolvedControllerRegistry,
    controller_toggles: Sequence[ResolvedControllerToggle],
) -> None:
    inventory_by_owner = {
        inventory.selected.alias: inventory for inventory in inventories
    }
    resolved_by_key = {
        item.toggle_key: item for item in registry.building_open_toggles
    }
    if set(resolved_by_key) != {
        item.qualified_toggle_key for item in controller_toggles
    }:
        raise ComposeError(
            "controller stock evidence requires exact manager-owned building "
            "toggle ownership metadata"
        )
    for toggle in controller_toggles:
        inventory = inventory_by_owner[toggle.owner]
        sources = _description_dialog_sources(
            inventory, toggle.raw_parent_building
        )
        if len(sources) != 1:
            raise ComposeError(
                f"{toggle.owner}: building toggle {toggle.raw_toggle_key!r} "
                "cannot resolve exactly one parent DialogID"
            )
        source_text = next(iter(sources))
        payload = _owned_smnu_payload(
            inventory,
            source_text.encode("ascii"),
            f"building toggle parent {source_text}",
        )
        _validate_mx22_toggle_controls(
            payload,
            resolved_by_key[toggle.qualified_toggle_key],
            owner=toggle.owner,
            panel_label=source_text,
        )


def _validate_mx22_toggle_controls(
    payload: bytes,
    toggle,
    *,
    owner: str,
    panel_label: str,
) -> None:
    """Require one audited stock presentation for the MX22 toggle lifecycle."""

    _smnu_dword_values(payload, owner, panel_label)
    values = struct.unpack(f"<{len(payload) // 4}I", payload)
    # One MX22 record is 35 DWORDs. Rectangle, label STRT index, and tooltip
    # STRT index are intentionally package-owned presentation. Every tag,
    # control type, stock INBb resource, image selector, font/color value, and
    # record boundary remains literal. The command alone becomes manager data.
    common_prefix = (
        0xFFFFFFFF, 0x00, 0x02,
        None, None, None, None,  # package layout rectangle
        0x07,
        None,                   # package label STRT index
        0x21,
        None,                   # package tooltip STRT index
        0x0A, 0x02, 0x0C, 0x62424E49, 0x0D, 0x3ED,
        0x14, 0x04, 0x03, 0x02, 0x03, 0x400, 0x05,
        None,                   # exact open/close image selector below
        0x06,
    )
    suffix = (
        0x12, 0x37746E66, 0x24, 0x03, 0x8000003F,
        0x40000000, 0x40000000, 0xFFFFFFFF,
    )
    mx22_counts = tuple(
        _count_stock_control_clones(
            values,
            command=command,
            prefix=common_prefix,
            suffix=suffix,
            required_prefix_values=((24, image_selector),),
        )
        for command, image_selector in (
            (toggle.open_command_id, 79),
            (toggle.close_command_id, 67),
        )
    )

    # AP39's REWARDS action is Majesty's exact half-width building-panel
    # presentation.  It is the stock visual analogue when the paired toggle
    # must share a two-column row.  Rectangle and string indices remain
    # package-owned, and the command becomes manager data; every other opcode,
    # INBb set, selector, font, color, and record terminator stays literal.
    ap39_prefix = (
        0x00, 0x02,
        None, None, None, None,  # package layout rectangle
        0x07,
        None,                   # package label STRT index
        0x21,
        None,                   # package tooltip STRT index
        0x0A, 0x02, 0x0C, 0x62424E49, 0x0D, 0x3F8,
        0x03, 0x02, 0x03, 0x400, 0x05, 0x52, 0x06,
    )
    ap39_suffix = (
        0x12, 0x34746E66, 0x24, 0x03, 0x8000003F,
        0x40000000, 0x40000000, 0x00000102, 0x45, 0x10A, 0x4E,
        0xFFFFFFFF,
    )
    ap39_counts = tuple(
        _count_stock_control_clones(
            values,
            command=command,
            prefix=ap39_prefix,
            suffix=ap39_suffix,
        )
        for command in (toggle.open_command_id, toggle.close_command_id)
    )

    # AP10's secondary-panel action is Majesty's exact 93x26 gold-framed
    # building-panel button.  It is the stock presentation analogue for a
    # narrow parent-panel row where neither MX22's fixed-width art nor AP39's
    # shorter action control is visually suitable.  Rectangle, string
    # indices, and the INBb image set are package-owned presentation; the
    # command becomes manager data.  The INBb token and every other stock
    # opcode, font/color value, and record boundary remain literal.
    ap10_prefix = (
        0x00, 0x02,
        None, None, None, None,  # package layout rectangle
        0x2A, 0x16, 0x04, 0x44, 0x12, 0x07,
        None,                   # package label STRT index
        0x21,
        None,                   # package tooltip STRT index
        0x0A, 0x02, 0x0C, 0x62424E49, 0x0D,
        None,                   # package-owned INBb image set
        0x14, 0x01, 0x14, 0x08, 0x14, 0x04,
        0x03, 0x02, 0x03, 0x400, 0x05, 0x53, 0x06,
    )
    ap10_suffix = (
        0x2C, 0x02, 0x12, 0x34746E66, 0x24, 0x03,
        0x8000003F, 0x40000000, 0x40000000,
        0x00000102, 0x5A, 0x10A, 0x43, 0xFFFFFFFF,
    )
    ap10_counts = tuple(
        _count_stock_control_clones(
            values,
            command=command,
            prefix=ap10_prefix,
            suffix=ap10_suffix,
        )
        for command in (toggle.open_command_id, toggle.close_command_id)
    )

    if (
        mx22_counts == (1, 1)
        or ap39_counts == (1, 1)
        or ap10_counts == (1, 1)
    ):
        return
    raise ComposeError(
        f"{owner}: SMNU/{panel_label} must contain one coherent pair of "
        "literal MX22 open/close button clones, audited AP39 half-width "
        "open/close clones, or audited AP10 action-button clones using private commands "
        f"0x{toggle.open_command_id:08X}/0x{toggle.close_command_id:08X}; "
        f"found MX22 {mx22_counts[0]}/{mx22_counts[1]} and "
        f"AP39 {ap39_counts[0]}/{ap39_counts[1]} and "
        f"AP10 {ap10_counts[0]}/{ap10_counts[1]}"
    )


def _count_stock_control_clones(
    values: Sequence[int],
    *,
    command: int,
    prefix: Sequence[int | None],
    suffix: Sequence[int],
    required_prefix_values: Sequence[tuple[int, int]] = (),
) -> int:
    matches = 0
    for index, value in enumerate(values):
        if (
            value != command
            or index < len(prefix)
            or index + len(suffix) >= len(values)
        ):
            continue
        candidate = values[index - len(prefix):index]
        if not all(
            expected is None or actual == expected
            for actual, expected in zip(candidate, prefix)
        ):
            continue
        if any(candidate[offset] != expected for offset, expected in required_prefix_values):
            continue
        if tuple(values[index + 1:index + 1 + len(suffix)]) != tuple(suffix):
            continue
        matches += 1
    return matches


def _owned_smnu_payload(
    inventory: PackageInventory,
    dialog_id: bytes,
    label: str,
) -> bytes:
    matches = [
        resource.entry.data
        for resource in inventory.resources
        if resource.section == b"SMNU" and resource.key == dialog_id
    ]
    if len(matches) != 1:
        raise ComposeError(
            f"{inventory.selected.alias}: {label} requires exactly one "
            f"package-owned SMNU/{_display_key(dialog_id)} resource; "
            f"found {len(matches)}"
        )
    return matches[0]


def _validate_controller_panel_controls(
    registry: ResolvedControllerRegistry,
    panel_key: str,
    parent_payload: bytes,
    child_payload: bytes,
    *,
    owner: str,
    parent_label: str,
    child_label: str,
    allow_manager_generated_refresh: bool = False,
) -> None:
    parent_values = _smnu_dword_values(parent_payload, owner, parent_label)
    child_values = _smnu_dword_values(child_payload, owner, child_label)
    panel = next((
        item for item in (*registry.panels, *registry.reward_panels,
                          *registry.occupant_action_panels,
                          *registry.quest_boards)
        if item.panel_key == panel_key
    ), None)
    if panel is None:  # pragma: no cover - registry/panel ownership equality guards it
        raise ComposeError(f"controller registry has no panel {panel_key!r}")

    parent_requirements: list[tuple[str, int]] = [
        ("secondary-panel open_command_id", panel.open_command_id),
    ]
    child_requirements: list[tuple[str, int]] = []
    # These are the controls stored literally in stock SMNU/MX05.  Other
    # controls used by the MX05 constructor/command paths are created or
    # resolved by code and therefore cannot be required as package-authored
    # SMNU evidence.  Both MX05-derived feature recipes share this exact
    # stock-resource boundary.
    mx05_authored_controls = (
        0x1388, 0x138B, 0x138C, 0x1392, 0x1F40,
        0x1F41, 0x1F45, 0x1F46, 0x1F4D,
    )
    if panel in registry.occupant_action_panels:
        child_requirements.extend((f"MX05 stock control {value:#x}", value)
                                  for value in mx05_authored_controls)
    if panel in registry.quest_boards:
        child_requirements.extend((f"MX05 stock control {value:#x}", value)
                                  for value in mx05_authored_controls)
        # Refresh is a Manager-generated clone of MX05's literal child action,
        # coin and price records. Packages must not author those controls in
        # either panel (including the retired AP54 parent workaround).
        refresh_controls = (
            panel.refresh_control_id,
            panel.refresh_price_binding_id,
            QUEST_REFRESH_COIN_CONTROL_ID,
        )
        authored_refresh = [
            value
            for value in refresh_controls
            if value in parent_values or value in child_values
        ]
        if authored_refresh and not allow_manager_generated_refresh:
            raise ComposeError(
                f"{owner}: quest-board Refresh controls are Manager-generated; "
                "remove package-authored AP54/duplicate controls "
                + ", ".join(f"0x{value:08X}" for value in authored_refresh)
            )
        if allow_manager_generated_refresh:
            parent_refresh = [
                value for value in refresh_controls if value in parent_values
            ]
            missing_child = [
                value for value in refresh_controls if value not in child_values
            ]
            if parent_refresh or missing_child:
                details = []
                if parent_refresh:
                    details.append(
                        "unexpected parent controls "
                        + ", ".join(f"0x{value:08X}" for value in parent_refresh)
                    )
                if missing_child:
                    details.append(
                        "missing child controls "
                        + ", ".join(f"0x{value:08X}" for value in missing_child)
                    )
                raise ComposeError(
                    f"{owner}: generated quest-board Refresh row is invalid: "
                    + "; ".join(details)
                )
    for meter in registry.meters:
        if meter.panel_key == panel_key:
            child_requirements.extend((
                ("AP22 label_control_id", meter.label_control_id),
                ("AP22 count_control_id", meter.count_control_id),
                ("AP22 binding_control_id", meter.binding_control_id),
            ))
    for row in registry.research_rows:
        if row.panel_key == panel_key:
            child_requirements.extend((
                ("AP99 action_control_id", row.action_control_id),
                ("AP99 price_control_id", row.price_control_id),
                ("AP99 progress_control_id", row.progress_control_id),
                ("AP99 active_display_control_id", row.active_display_control_id),
                ("AP99 icon_control_id", row.icon_control_id),
            ))
    for gate in registry.upgrade_gates:
        if gate.panel_key == panel_key:
            parent_requirements.extend((
                ("AP17 upgrade_control_id", gate.upgrade_control_id),
                ("AP17 upgrade_price_control_id", gate.upgrade_price_control_id),
            ))
    for action in registry.timed_rage_actions:
        if action.panel_key == panel_key:
            child_requirements.extend((
                ("AP24 timed action_control_id", action.action_control_id),
                ("AP24 timed icon_control_id", action.icon_control_id),
                ("AP24 timed price_control_id", action.price_control_id),
                ("AP24 timed progress_control_id", action.progress_control_id),
                ("AP24 timed active_display_control_id", action.active_display_control_id),
            ))
    for action in registry.rage_command_actions:
        if action.panel_key == panel_key:
            child_requirements.extend((
                ("AP24 command action_control_id", action.action_control_id),
                ("AP24 command icon_control_id", action.icon_control_id),
                ("AP24 command price_control_id", action.price_control_id),
            ))
    for action in registry.sovereign_target_actions:
        if action.panel_key == panel_key:
            # private_control_id is a manager-registered descriptor identity,
            # not an authored visible control.  The visual row and its stock-
            # shaped icon/price children must exist in the authored panel.
            child_requirements.extend((
                ("AP69 visual_control_id", action.visual_control_id),
                ("AP69 icon_control_id", action.icon_control_id),
                ("AP69 price_control_id", action.price_control_id),
            ))
    for action in registry.hostile_monster_flags:
        if action.panel_key == panel_key:
            child_requirements.extend((
                ("AP41 action control", 5002),
                ("AP41 amount control", 8),
                ("AP41 decrease control", 10),
                ("AP41 increase control", 11),
                ("AP41 gold display control", 8013),
            ))

    _require_smnu_values(
        parent_values,
        parent_requirements,
        owner=owner,
        panel_label=parent_label,
    )
    _require_smnu_values(
        child_values,
        child_requirements,
        owner=owner,
        panel_label=child_label,
    )


def _smnu_dword_values(payload: bytes, owner: str, panel_label: str) -> frozenset[int]:
    if len(payload) % 4 != 0:
        raise ComposeError(
            f"{owner}: SMNU/{panel_label} is not DWORD-aligned"
        )
    if not payload:
        raise ComposeError(f"{owner}: SMNU/{panel_label} is empty")
    return frozenset(
        struct.unpack(f"<{len(payload) // 4}I", payload)
    )


def _require_smnu_values(
    values: frozenset[int],
    requirements: Sequence[tuple[str, int]],
    *,
    owner: str,
    panel_label: str,
) -> None:
    missing = [
        f"{field}=0x{value:08X}"
        for field, value in requirements
        if value != 0 and value not in values
    ]
    if missing:
        raise ComposeError(
            f"{owner}: SMNU/{panel_label} does not contain declared controller "
            "control(s): " + ", ".join(missing)
        )


def merge_gpl_resources(
    inventories: Sequence[PackageInventory],
    *,
    resolution_owners: Mapping[tuple[DefinitionKind | str, str], str] | None = None,
    semantic_resolutions: Mapping[
        tuple[DefinitionKind | str, str],
        SemanticItem | ScopedSemanticResolution,
    ] | None = None,
    inventory_death_drop_exclusions: Sequence[str] = (),
    private_activity_texts: Sequence[PrivateActivityTextBinding] | None = None,
    stock_integer_expression_sources: Sequence[ParsedSemanticSource] = (),
    stock_semantic_sources: Sequence[ParsedSemanticSource] = (),
    stock_purchase_equipment_source: ParsedSemanticSource | None = None,
    stock_purchase_bazaar_source: ParsedSemanticSource | None = None,
    stock_control_monster: SemanticItem | None = None,
    stock_controlled_monster_death: SemanticItem | None = None,
    stock_leader_dead: SemanticItem | None = None,
    stock_hero_trees: Mapping[str, SemanticItem] | None = None,
    stock_reset_tasks: SemanticItem | None = None,
    stock_unit_death: SemanticItem | None = None,
) -> GplComposeResult:
    parsed_by_owner: dict[str, list[ParsedSemanticSource]] = {}
    for inventory in inventories:
        owner = inventory.selected.alias
        parsed_by_owner.setdefault(owner, []).extend(
            _parse_inventory_gpl_sources(inventory)
        )

    variants_by_key: dict[tuple[DefinitionKind, str], list[tuple[str, str]]] = {}
    standard_payloads_by_key: dict[
        tuple[DefinitionKind, str], set[str]
    ] = {}
    standard_owners_by_key: dict[
        tuple[DefinitionKind, str], set[str]
    ] = {}
    required_patch_keys: set[tuple[DefinitionKind, str]] = set()
    passthrough_aliases = {
        inventory.selected.alias
        for inventory in inventories
        if getattr(inventory.selected, "semantic_passthrough", False)
    }
    stock_items = {
        item.key: item
        for source in stock_semantic_sources
        for item in source.items
    }
    requested = {
        (DefinitionKind(kind), name.casefold()): owner
        for (kind, name), owner in (resolution_owners or {}).items()
    }
    for owner, sources in parsed_by_owner.items():
        for source in sources:
            for item in source.items:
                variants_by_key.setdefault(item.key, []).append((owner, item.text))
                stock_item = stock_items.get(item.key)
                changed = (
                    stock_item is None
                    or join_logical_lines(split_logical_lines(item.text))
                    != join_logical_lines(split_logical_lines(stock_item.text))
                )
                if owner not in passthrough_aliases and changed:
                    required_patch_keys.add(item.key)
                if owner in passthrough_aliases:
                    standard_payloads_by_key.setdefault(item.key, set()).add(
                        join_logical_lines(split_logical_lines(item.text))
                    )
                    standard_owners_by_key.setdefault(item.key, set()).add(owner)
    required_patch_keys.update(
        key for key, payloads in standard_payloads_by_key.items()
        if len(payloads) > 1 and len(standard_owners_by_key.get(key, ())) > 1
    )

    integer_expression_environment = collect_integer_expression_environment(
        (
            *stock_integer_expression_sources,
            *(
                source
                for owner_sources in parsed_by_owner.values()
                for source in owner_sources
            ),
        )
    )

    private_rewrite_items_before: dict[
        tuple[str, tuple[DefinitionKind, str]], list[str]
    ] = {}
    for owner, sources in parsed_by_owner.items():
        for source in sources:
            for item in source.items:
                private_rewrite_items_before.setdefault(
                    (owner, item.key), []
                ).append(item.text)

    try:
        parsed_by_owner = rewrite_private_activity_text_resolver_calls(
            parsed_by_owner,
            private_activity_texts or (),
            integer_expression_environment=integer_expression_environment,
        )
    except IntentTextError as exc:
        raise ComposeError(str(exc)) from exc

    private_rewrite_items_after: dict[
        tuple[str, tuple[DefinitionKind, str]], list[str]
    ] = {}
    for owner, sources in parsed_by_owner.items():
        for source in sources:
            for item in source.items:
                private_rewrite_items_after.setdefault(
                    (owner, item.key), []
                ).append(item.text)
    required_patch_keys.update(
        key
        for owner, key in (
            set(private_rewrite_items_before) | set(private_rewrite_items_after)
        )
        if private_rewrite_items_before.get((owner, key))
        != private_rewrite_items_after.get((owner, key))
    )

    # The low-level semantic merger deliberately compares exact source text,
    # while Majesty accepts LF and CRLF identically. Canonicalize every parsed
    # item to logical lines before exact merging so physically different but
    # gameplay-identical providers co-own one value without a false conflict
    # or an unnecessary explicit load-last resolution.
    parsed_by_owner = {
        owner: [
            replace(
                source,
                items=tuple(
                    replace(
                        item,
                        text=join_logical_lines(split_logical_lines(item.text)),
                    )
                    for item in source.items
                ),
            )
            for source in sources
        ]
        for owner, sources in parsed_by_owner.items()
    }
    # Full legacy source trees commonly repeat definitions identical to the
    # installed game. They are ancestry, not load-last candidates. Ordinary
    # Merge copies are removed before conflict resolution so one native
    # Standard change remains native. Stock-valued Standard candidates stay
    # only when two Standards actually compete and native order must be
    # reconciled.
    parsed_by_owner = {
        owner: [
            replace(
                source,
                items=tuple(
                    item
                    for item in source.items
                    if (
                        item.key not in stock_items
                        or item.text
                        != join_logical_lines(
                            split_logical_lines(stock_items[item.key].text)
                        )
                        or (
                            owner in passthrough_aliases
                            and len(standard_owners_by_key.get(item.key, ())) > 1
                        )
                        or requested.get(item.key) == owner
                    )
                ),
            )
            for source in sources
        ]
        for owner, sources in parsed_by_owner.items()
    }

    initial = merge_sources([], parsed_by_owner)
    explicit: dict[tuple[DefinitionKind, str], SemanticItem] = {}
    explicit_scopes: dict[tuple[DefinitionKind, str], frozenset[str]] = {}
    for (kind, name), resolution in (semantic_resolutions or {}).items():
        key = (DefinitionKind(kind), name.casefold())
        if isinstance(resolution, ScopedSemanticResolution):
            explicit[key] = resolution.item
            explicit_scopes[key] = resolution.participant_owners
        else:
            explicit[key] = resolution
    for key, item in explicit.items():
        if item.key != key:
            raise ComposeError(
                f"GPL semantic resolution key {key!r} does not match item {item.key!r}"
            )
    if explicit and private_activity_texts:
        try:
            rewritten_explicit = rewrite_unowned_private_activity_text_resolver_calls(
                tuple(explicit.values()),
                private_activity_texts,
                integer_expression_environment=integer_expression_environment,
            )
        except IntentTextError as exc:
            raise ComposeError(str(exc)) from exc
        explicit = {
            key: item for key, item in zip(explicit.keys(), rewritten_explicit)
        }
    overlap = set(requested) & set(explicit)
    if overlap:
        labels = ", ".join(f"{kind.value}:{name}" for kind, name in sorted(overlap))
        raise ComposeError(
            f"GPL conflicts cannot have both owner and explicit resolutions: {labels}"
        )
    resolutions: dict[tuple[DefinitionKind, str], SemanticItem] = {}
    used: list[tuple[DefinitionKind, str, str]] = []
    used_sources: list[tuple[DefinitionKind, str, str]] = []
    for conflict in initial.conflicts:
        explicit_item = explicit.get(conflict.key)
        if explicit_item is not None:
            allowed_owners = explicit_scopes.get(conflict.key)
            novel_extra_owners: set[str] = set()
            if allowed_owners is not None:
                allowed_texts = {
                    variant.item.text
                    for variant in conflict.variants
                    if variant.side_name in allowed_owners
                }
                allowed_texts.add(explicit_item.text)
                novel_extra_owners = {
                    variant.side_name
                    for variant in conflict.variants
                    if variant.side_name not in allowed_owners
                    and variant.item.text not in allowed_texts
                }
            if novel_extra_owners:
                extras = sorted(novel_extra_owners)
                raise ComposeError(
                    "GPL semantic resolution for "
                    f"{conflict.key[0].value}:{conflict.name} is scoped to "
                    f"{sorted(allowed_owners or ())}, but additional mod owners "
                    f"provide novel changes: {extras}"
                )
            resolutions[conflict.key] = explicit_item
            used_sources.append(
                (conflict.key[0], conflict.name, explicit_item.source_name)
            )
            continue
        owner = requested.get(conflict.key)
        if owner is None:
            continue
        choices = [variant.item for variant in conflict.variants if variant.side_name == owner]
        if len(choices) != 1:
            raise ComposeError(
                f"GPL resolution for {conflict.key[0].value}:{conflict.name} "
                f"selects unavailable owner {owner!r}"
            )
        resolutions[conflict.key] = choices[0]
        used.append((conflict.key[0], conflict.name, owner))

    unused = set(requested) - set(resolutions)
    if unused:
        labels = ", ".join(f"{kind.value}:{name}" for kind, name in sorted(unused))
        raise ComposeError(f"GPL resolutions do not name real conflicts: {labels}")
    unused_explicit = set(explicit) - set(resolutions)
    if unused_explicit:
        labels = ", ".join(
            f"{kind.value}:{name}" for kind, name in sorted(unused_explicit)
        )
        raise ComposeError(
            f"GPL semantic resolutions do not name real conflicts: {labels}"
        )
    for key in set(requested) | set(explicit):
        selected = resolutions.get(key)
        stock_item = stock_items.get(key)
        if (
            selected is not None
            and stock_item is not None
            and join_logical_lines(split_logical_lines(selected.text))
            == join_logical_lines(split_logical_lines(stock_item.text))
        ):
            # A reviewed stock restoration is itself a load-last edit. A
            # non-stock resolution which merely selects one lone Standard
            # change over package-carried stock ancestry remains native.
            required_patch_keys.add(key)
    final = merge_sources([], parsed_by_owner, resolutions or None)
    final.require_clean()
    before_generated_features = {item.key: item.text for item in final.items}
    final = add_inventory_death_drop_exclusions(
        final,
        inventory_death_drop_exclusions,
        source_name="<CAM Manager stock death-drop composition>",
    )
    gpl_callback_evidence = validate_gpl_feature_evidence(inventories)
    purchase_callbacks = [
        item for item in gpl_callback_evidence if item.lifecycle == "equipment"
    ]
    bazaar_callbacks = [
        item for item in gpl_callback_evidence if item.lifecycle == "bazaar"
    ]
    movement_hooks = [
        item
        for item in gpl_callback_evidence
        if item.lifecycle == "controlled_follower_speed_sync"
    ]
    hero_quest_hooks = [
        item for item in gpl_callback_evidence
        if item.lifecycle == "hero_quest"
    ]
    callback_symbols = [item.callback_symbol for item in purchase_callbacks]
    if purchase_callbacks:
        stock_item = None
        if stock_purchase_equipment_source is not None:
            stock_item = stock_purchase_equipment_source.get(
                DefinitionKind.FUNCTION, "Purchase_Equipment"
            )
        try:
            final = add_purchase_equipment_tail_callbacks(
                final,
                callback_symbols,
                stock_purchase_equipment=stock_item,
                source_name="<CAM Manager stock Purchase_Equipment tail composition>",
            )
        except ValueError as exc:
            raise ComposeError(str(exc)) from exc
    if bazaar_callbacks:
        stock_item = None
        if stock_purchase_bazaar_source is not None:
            stock_item = stock_purchase_bazaar_source.get(
                DefinitionKind.FUNCTION, "Purchase_Bazaar"
            )
        try:
            final = add_purchase_bazaar_tail_callbacks(
                final,
                [item.callback_symbol for item in bazaar_callbacks],
                stock_purchase_bazaar=stock_item,
                source_name="<CAM Manager stock Purchase_Bazaar tail composition>",
            )
        except ValueError as exc:
            raise ComposeError(str(exc)) from exc
    if movement_hooks:
        try:
            final = add_controlled_follower_movement_adjustments(
                final,
                (
                    (
                        item.callback_symbol,
                        item.movement_rate_modifier_per_tier,
                        item.marker_effectors,
                    )
                    for item in movement_hooks
                ),
                stock_control_monster=stock_control_monster,
                stock_controlled_monster_death=stock_controlled_monster_death,
                stock_leader_dead=stock_leader_dead,
                source_name=(
                    "<CAM Manager stock controlled-follower movement composition>"
                ),
            )
        except ValueError as exc:
            raise ComposeError(str(exc)) from exc
    if hero_quest_hooks:
        if stock_hero_trees is None:
            raise ComposeError(
                "hero-quest lifecycle requires installed stock hero decision sources"
            )
        try:
            final = add_hero_quest_lifecycle_callbacks(
                final,
                (
                    (
                        item.hero_scripts,
                        item.callback_symbol,
                        item.reset_callback_symbol,
                        item.death_callback_symbol,
                    )
                    for item in hero_quest_hooks
                ),
                stock_hero_trees=stock_hero_trees,
                stock_reset_tasks=stock_reset_tasks,
                stock_unit_death=stock_unit_death,
                source_name="<CAM Manager stock hero-quest lifecycle composition>",
            )
        except ValueError as exc:
            raise ComposeError(str(exc)) from exc
    if private_activity_texts:
        try:
            audit_private_activity_text_resolver_aliases(
                final.items, private_activity_texts
            )
        except IntentTextError as exc:
            raise ComposeError(str(exc)) from exc
    after_generated_features = {item.key: item.text for item in final.items}
    required_patch_keys.update(
        key
        for key, text in after_generated_features.items()
        if before_generated_features.get(key) != text
    )
    if passthrough_aliases or stock_semantic_sources:
        final = SemanticMergeResult(
            tuple(item for item in final.items if item.key in required_patch_keys),
            final.conflicts,
        )
    return GplComposeResult(
        source_set=final.emit_project_source_set(),
        conflicts=initial.conflicts,
        resolution_owners=tuple(used),
        resolution_sources=tuple(used_sources),
        inventory_death_drop_exclusions=tuple(inventory_death_drop_exclusions),
        purchase_equipment_tail_callbacks=tuple(
            (item.mod_id, item.feature_key, item.callback_symbol)
            for item in purchase_callbacks
        ),
        purchase_bazaar_tail_callbacks=tuple(
            (item.mod_id, item.feature_key, item.callback_symbol)
            for item in bazaar_callbacks
        ),
        controlled_follower_speed_sync=tuple(
            (
                item.mod_id,
                item.feature_key,
                item.callback_symbol,
                item.movement_rate_modifier_per_tier,
                item.marker_effectors,
            )
            for item in movement_hooks
        ),
        hero_quest_lifecycles=tuple(
            (
                item.mod_id,
                item.feature_key,
                item.hero_scripts,
                item.callback_symbol,
                item.reset_callback_symbol,
                item.death_callback_symbol,
            )
            for item in hero_quest_hooks
        ),
    )


def _require_boolean_agent_callback_signature(
    text: str, symbol: str, label: str
) -> None:
    from .gpl import _mask_non_code

    pattern = (
        r"\s*function\s+" + re.escape(symbol)
        + r"\s*\(\s*agent\s+[A-Za-z_][A-Za-z0-9_]*\s*\)"
        + r"\s+is\s+boolean\s*(?:declare|begin)\b"
    )
    if re.match(pattern, _mask_non_code(text), re.IGNORECASE) is None:
        raise ComposeError(
            f"{label} {symbol!r} must use the stock signature (agent) is boolean"
        )


def _require_boolean_two_agent_callback_signature(
    text: str, symbol: str, label: str
) -> None:
    from .gpl import _mask_non_code

    argument = r"agent\s+[A-Za-z_][A-Za-z0-9_]*"
    pattern = (
        r"\s*function\s+" + re.escape(symbol)
        + r"\s*\(\s*" + argument + r"\s*,\s*" + argument + r"\s*\)"
        + r"\s+is\s+boolean\s*declare\b"
    )
    if re.match(pattern, _mask_non_code(text), re.IGNORECASE) is None:
        raise ComposeError(
            f"{label} {symbol!r} must use the stock signature "
            "(agent leader, agent follower) is boolean"
        )


def _require_void_agent_callback_signature(text: str, symbol: str, label: str) -> None:
    from .gpl import _mask_non_code

    pattern = (
        r"\s*function\s+" + re.escape(symbol)
        + r"\s*\(\s*agent\s+[A-Za-z_][A-Za-z0-9_]*\s*\)"
        + r"\s*(?:declare|begin)\b"
    )
    if re.match(pattern, _mask_non_code(text), re.IGNORECASE) is None:
        raise ComposeError(
            f"{label} {symbol!r} must use the stock signature (agent)"
        )


def validate_gpl_feature_evidence(
    inventories: Sequence[PackageInventory],
    *,
    game_path: Path | None = None,
) -> tuple[GplFeatureEvidence, ...]:
    """Validate and deterministically order source-composed GPL callbacks."""

    callbacks: list[GplFeatureEvidence] = []
    seen_symbols: dict[tuple[str, str], str] = {}
    for inventory in inventories:
        package = getattr(inventory.selected, "package", None)
        if package is None:
            continue
        definition = package.definition
        if definition is None:
            raise ComposeError(
                f"{inventory.selected.alias}: a mod definition is required"
            )
        parsed = _parse_inventory_gpl_sources(inventory)
        functions = [
            item
            for source in parsed
            for item in source.items
            if item.kind is DefinitionKind.FUNCTION
        ]
        for feature in definition.runtime_features:
            if not isinstance(
                feature,
                (
                    StockGplmxPurchaseEquipmentTail,
                    StockGplmxPurchaseBazaarTail,
                    StockControlledFollowerSpeedSync,
                    StockHeroQuestLifecycle,
                ),
            ):
                continue
            if isinstance(feature, StockGplmxPurchaseEquipmentTail):
                lifecycle = "equipment"
                feature_key = feature.callback_key
                callback_symbol = feature.callback_symbol
            elif isinstance(feature, StockGplmxPurchaseBazaarTail):
                lifecycle = "bazaar"
                feature_key = feature.callback_key
                callback_symbol = feature.callback_symbol
            else:
                if isinstance(feature, StockControlledFollowerSpeedSync):
                    lifecycle = "controlled_follower_speed_sync"
                    feature_key = feature.feature_key
                    callback_symbol = feature.eligibility_callback_symbol
                else:
                    lifecycle = "hero_quest"
                    feature_key = feature.feature_key
                    callback_symbol = feature.decision_callback_symbol
            required_symbols = (
                (
                    feature.decision_callback_symbol,
                    feature.reset_callback_symbol,
                    feature.death_callback_symbol,
                )
                if isinstance(feature, StockHeroQuestLifecycle)
                else (callback_symbol,)
            )
            matches_by_symbol = {
                symbol: [
                    item for item in functions
                    if item.name.casefold() == symbol.casefold()
                ]
                for symbol in required_symbols
            }
            invalid = [symbol for symbol, matches in matches_by_symbol.items() if len(matches) != 1]
            if invalid:
                label = (
                    "Controlled-follower speed-sync eligibility callback"
                    if isinstance(feature, StockControlledFollowerSpeedSync)
                    else (
                        "Hero-quest lifecycle callback"
                        if isinstance(feature, StockHeroQuestLifecycle)
                        else f"Purchase_{lifecycle.title()} tail callback"
                    )
                )
                raise ComposeError(
                    f"{inventory.selected.alias}: {label} "
                    f"{invalid[0]!r} requires exactly one package-owned GPL function; "
                    f"found {len(matches_by_symbol[invalid[0]])}"
                )
            if isinstance(feature, StockControlledFollowerSpeedSync):
                _require_boolean_two_agent_callback_signature(
                    matches_by_symbol[callback_symbol][0].text,
                    callback_symbol,
                    "Controlled-follower speed-sync eligibility callback",
                )
            elif isinstance(feature, StockHeroQuestLifecycle):
                _require_boolean_agent_callback_signature(
                    matches_by_symbol[feature.decision_callback_symbol][0].text,
                    feature.decision_callback_symbol,
                    "Hero-quest decision callback",
                )
                _require_void_agent_callback_signature(
                    matches_by_symbol[feature.reset_callback_symbol][0].text,
                    feature.reset_callback_symbol,
                    "Hero-quest reset callback",
                )
                _require_void_agent_callback_signature(
                    matches_by_symbol[feature.death_callback_symbol][0].text,
                    feature.death_callback_symbol,
                    "Hero-quest death callback",
                )
            else:
                _require_boolean_agent_callback_signature(
                    matches_by_symbol[callback_symbol][0].text,
                    callback_symbol,
                    f"Purchase_{lifecycle.title()} tail callback",
                )
            for symbol in required_symbols:
                symbol_key = (lifecycle, symbol.casefold())
                previous = seen_symbols.get(symbol_key)
                if previous is not None:
                    raise ComposeError(
                        f"{lifecycle.replace('_', ' ').title()} callback symbol "
                        f"{symbol!r} is owned by both {previous} "
                        f"and {inventory.selected.alias}"
                    )
                seen_symbols[symbol_key] = inventory.selected.alias
            mod_id = _normalized_mod_uuid(package.mod_id)
            markers = (
                _controlled_follower_markers(mod_id, feature_key)
                if isinstance(feature, StockControlledFollowerSpeedSync)
                else ()
            )
            callbacks.append(
                GplFeatureEvidence(
                    lifecycle=lifecycle,
                    mod_id=mod_id,
                    feature_key=feature_key,
                    callback_symbol=callback_symbol,
                    movement_rate_modifier_per_tier=(
                        feature.movement_rate_modifier_per_tier
                        if isinstance(feature, StockControlledFollowerSpeedSync)
                        else 0
                    ),
                    marker_effectors=markers,
                    hero_scripts=(
                        feature.hero_scripts
                        if isinstance(feature, StockHeroQuestLifecycle)
                        else ()
                    ),
                    reset_callback_symbol=(
                        feature.reset_callback_symbol
                        if isinstance(feature, StockHeroQuestLifecycle)
                        else ""
                    ),
                    death_callback_symbol=(
                        feature.death_callback_symbol
                        if isinstance(feature, StockHeroQuestLifecycle)
                        else ""
                    ),
                )
            )
    callbacks.sort(
        key=lambda item: (
            item.lifecycle,
            item.mod_id,
            item.feature_key.casefold(),
            item.callback_symbol.casefold(),
        )
    )
    movement = [
        item
        for item in callbacks
        if item.lifecycle == "controlled_follower_speed_sync"
    ]
    if movement and game_path is not None:
        parsed_by_owner = {
            inventory.selected.alias: _parse_inventory_gpl_sources(inventory)
            for inventory in inventories
        }
        initial = merge_sources([], parsed_by_owner)
        protected_functions = {
            "control_monster",
            "controlled_monster_death",
            "leader_dead",
            *(item.callback_symbol.casefold() for item in movement),
        }
        unrelated_resolutions = {
            conflict.key: min(
                conflict.variants,
                key=lambda variant: (
                    variant.side_name.casefold(),
                    variant.item.source_name.casefold(),
                    variant.item.text,
                ),
            ).item
            for conflict in initial.conflicts
            if not (
                conflict.key[0] is DefinitionKind.FUNCTION
                and conflict.key[1] in protected_functions
            )
        }
        # This preflight proves only the generated controlled-follower lifecycle.
        # Other GPL conflicts are validated and resolved by the normal build plan;
        # they must not make an independent runtime feature appear unsupported.
        # Conflicts in a lifecycle function or declared callback stay unresolved
        # here and therefore fail closed below.
        merged = merge_sources([], parsed_by_owner, unrelated_resolutions or None)
        merged.require_clean()
        control, death, leader_dead = _load_stock_controlled_follower_items(
            game_path
        )
        try:
            add_controlled_follower_movement_adjustments(
                merged,
                (
                    (
                        item.callback_symbol,
                        item.movement_rate_modifier_per_tier,
                        item.marker_effectors,
                    )
                    for item in movement
                ),
                stock_control_monster=control,
                stock_controlled_monster_death=death,
                stock_leader_dead=leader_dead,
            )
        except ValueError as exc:
            raise ComposeError(str(exc)) from exc
    hero_quest = [item for item in callbacks if item.lifecycle == "hero_quest"]
    if hero_quest and game_path is not None:
        parsed_by_owner = {
            inventory.selected.alias: _parse_inventory_gpl_sources(inventory)
            for inventory in inventories
        }
        initial = merge_sources([], parsed_by_owner)
        protected = {
            "reset_tasks", "unit_call_deathscript",
            *(item.callback_symbol.casefold() for item in hero_quest),
            *(item.reset_callback_symbol.casefold() for item in hero_quest),
            *(item.death_callback_symbol.casefold() for item in hero_quest),
        }
        unrelated = {
            conflict.key: min(
                conflict.variants,
                key=lambda variant: (
                    variant.side_name.casefold(), variant.item.source_name.casefold(),
                    variant.item.text,
                ),
            ).item
            for conflict in initial.conflicts
            if not (
                conflict.key[0] is DefinitionKind.FUNCTION
                and conflict.key[1] in protected
            )
        }
        merged = merge_sources([], parsed_by_owner, unrelated or None)
        merged.require_clean()
        trees, reset_item, death_item = _load_stock_hero_quest_lifecycle_items(game_path)
        try:
            add_hero_quest_lifecycle_callbacks(
                merged,
                (
                    (
                        item.hero_scripts, item.callback_symbol,
                        item.reset_callback_symbol, item.death_callback_symbol,
                    )
                    for item in hero_quest
                ),
                stock_hero_trees=trees,
                stock_reset_tasks=reset_item,
                stock_unit_death=death_item,
            )
        except ValueError as exc:
            raise ComposeError(str(exc)) from exc
    return tuple(callbacks)


def _controlled_follower_markers(
    mod_id: str, feature_key: str
) -> tuple[str, str, str, str]:
    digest = hashlib.sha256(
        f"{mod_id}|{feature_key.casefold()}".encode("ascii")
    ).hexdigest().upper()
    return tuple("MCF" + digest[:12] + str(tier) for tier in range(1, 5))


def _parse_inventory_gpl_sources(
    inventory: PackageInventory,
) -> list[ParsedSemanticSource]:
    semantic_sources = getattr(inventory, "semantic_sources", None)
    if semantic_sources is not None:
        return list(semantic_sources)
    owner = inventory.selected.alias
    effective: dict[tuple[DefinitionKind, str], SemanticItem] = {}
    for load in inventory.gpl_loads:
        for source_path in load.sources:
            path = source_path.absolute_path
            suffix = path.suffix.casefold()
            if suffix not in {".gpl", ".dat"}:
                raise ComposeError(
                    f"{owner}: unsupported GPL source extension: {path}"
                )
            source = _parse_semantic_source_file(path)
            try:
                require_complete_semantic_coverage(source)
            except ValueError as exc:
                raise ComposeError(
                    f"{owner}: GPL source has unparsed content the composer "
                    f"cannot preserve: {path}: {exc}"
                ) from exc
            # GPL targets are loaded in manifest order. Reusing a physical
            # source later is a real last-write directive, not a duplicate to
            # discard, so replay every occurrence into the effective view.
            for item in source.items:
                effective[item.key] = item
    if not effective:
        return []
    return [
        ParsedSemanticSource(
            source_name=f"<{owner} effective native GPL load order>",
            text="",
            items=tuple(effective.values()),
        )
    ]


def compile_gpl(
    source_set: GplProjectSourceSet,
    compiler: Path,
    output_directory: Path,
    *,
    stem: str = "Merged",
) -> CompiledGpl:
    """Write one semantic source set and invoke Majesty's stock GPL compiler."""

    if not compiler.is_file():
        raise ComposeError(f"Majesty GPL compiler was not found: {compiler}")
    output_directory.mkdir(parents=True, exist_ok=False)
    project_name = f"{stem}.gplproj"
    (output_directory / project_name).write_bytes(
        source_set.project_text.encode("cp1252")
    )
    for filename, text in source_set.files.items():
        (output_directory / filename).write_bytes(text.encode("cp1252"))
    target = output_directory / f"{stem}.bcd"
    process = subprocess.run(
        (str(compiler), "-in", project_name, "-out", target.name, "-stdout"),
        cwd=output_directory,
        check=False,
        capture_output=True,
        text=True,
        encoding="cp1252",
        errors="replace",
        **no_console_window_options(),
    )
    if process.returncode != 0:
        raise ComposeError(
            f"GPL compiler failed with exit code {process.returncode}: "
            f"{process.stdout[-2000:]}{process.stderr[-2000:]}"
        )
    if not target.is_file() or target.stat().st_size == 0:
        raise ComposeError(f"GPL compiler did not produce a non-empty target: {target}")
    return CompiledGpl(
        target=target,
        size=target.stat().st_size,
        stdout=process.stdout,
        stderr=process.stderr,
    )


def snapshot_stock_compose_inputs(game_path: Path) -> tuple[StockComposeInput, ...]:
    """Hash the complete, deterministic installed-stock composition input set.

    The fixed CAM/compiler/defines inputs are required.  Both stock Description
    directories are required and every direct ``*.xml`` child is included, so
    adding or deleting a stock Description document changes the snapshot.  The
    symlink anywhere below the resolved game root is rejected rather than
    silently following a mutable external target.
    """

    root = game_path.resolve(strict=True)
    if not root.is_dir():
        raise ComposeError(f"game path is not a directory: {root}")

    required_relative_paths = _enumerate_stock_compose_relative_paths(root)
    input_specs = (
        *((relative, True) for relative in required_relative_paths),
        *((relative, False) for relative in _STOCK_COMPOSE_OPTIONAL_INPUTS),
    )

    snapshots: list[StockComposeInput] = []
    seen: set[str] = set()
    for relative, required in input_specs:
        normalized = relative.as_posix().casefold()
        if normalized in seen:
            raise ComposeError(
                "installed stock composition inputs contain a duplicate "
                f"case-insensitive path: {relative.as_posix()}"
            )
        seen.add(normalized)
        path = root / relative
        _require_stock_input_ancestry(root, path)
        if not required and not path.exists():
            snapshots.append(
                StockComposeInput(
                    relative_path=relative,
                    present=False,
                    size=0,
                    sha256="",
                )
            )
            continue
        _require_stock_input_path(root, path, expect_directory=False)
        before = path.stat()
        digest = _sha256(path)
        _require_stock_input_path(root, path, expect_directory=False)
        after = path.stat()
        before_identity = (
            before.st_size,
            before.st_mtime_ns,
            before.st_ctime_ns,
            getattr(before, "st_ino", 0),
        )
        after_identity = (
            after.st_size,
            after.st_mtime_ns,
            after.st_ctime_ns,
            getattr(after, "st_ino", 0),
        )
        if before_identity != after_identity:
            raise ComposeError(
                f"installed stock composition input changed while hashing: {path}"
            )
        snapshots.append(
            StockComposeInput(
                relative_path=relative,
                present=True,
                size=after.st_size,
                sha256=digest,
            )
        )
    if required_relative_paths != _enumerate_stock_compose_relative_paths(root):
        raise ComposeError(
            "installed stock Description inputs changed while creating the "
            "composition snapshot"
        )
    for snapshot in snapshots:
        if snapshot.relative_path not in _STOCK_COMPOSE_OPTIONAL_INPUTS:
            continue
        path = root / snapshot.relative_path
        _require_stock_input_ancestry(root, path)
        if path.exists() != snapshot.present:
            raise ComposeError(
                "installed optional stock composition input changed presence "
                f"while creating the snapshot: {path}"
            )
        if snapshot.present and not path.is_file():
            raise ComposeError(
                f"installed optional stock composition input is not a file: {path}"
            )
    return tuple(snapshots)


def _enumerate_stock_compose_relative_paths(root: Path) -> tuple[Path, ...]:
    relative_paths = list(_STOCK_COMPOSE_FIXED_INPUTS)
    for relative_directory in _STOCK_COMPOSE_XML_DIRECTORIES:
        directory = root / relative_directory
        _require_stock_input_path(root, directory, expect_directory=True)
        xml_paths: list[Path] = []
        for child in directory.iterdir():
            if child.suffix.casefold() != ".xml":
                continue
            _require_stock_input_path(root, child, expect_directory=False)
            xml_paths.append(child.relative_to(root))
        relative_paths.extend(
            sorted(xml_paths, key=lambda value: value.as_posix().casefold())
        )
    return tuple(relative_paths)


def _require_stock_input_path(
    root: Path, path: Path, *, expect_directory: bool
) -> None:
    _require_stock_input_ancestry(root, path)
    expected = "directory" if expect_directory else "file"
    if (expect_directory and not path.is_dir()) or (
        not expect_directory and not path.is_file()
    ):
        raise ComposeError(
            f"required installed stock composition {expected} was not found: {path}"
        )


def _require_stock_input_ancestry(root: Path, path: Path) -> None:
    try:
        relative = path.relative_to(root)
    except ValueError as exc:
        raise ComposeError(f"stock composition input escapes the game root: {path}") from exc
    current = root
    for part in relative.parts:
        current /= part
        if current.is_symlink():
            raise ComposeError(
                f"installed stock composition input cannot be a symlink: {current}"
            )


def resolve_runtime_feature_registry(
    inventories: Sequence[PackageInventory],
    runtime_capabilities: Sequence[str] = (),
) -> RuntimeFeatureRegistry:
    """Prove package-owned typed features and translate trusted v2 aliases.

    A feature declaration is not sufficient by itself. Name generators must
    own all four HN STRT tables and be selected by a package Description;
    enchantment rows must own the matching Overlay Description. Compatibility
    adapters may still supply a legacy v2 capability, but its fixed feature is
    attributed only when exactly one selected package proves that evidence.
    """

    claims: list[tuple[str, RuntimeFeature]] = []
    definition_legacy_capabilities: set[str] = set()
    for inventory in inventories:
        definition = inventory.selected.package.definition
        if definition is None:
            raise ComposeError(
                f"{inventory.selected.alias}: a mod definition is required"
            )
        definition_legacy_capabilities.update(definition.runtime_capabilities)
        owned = (
            *(
                feature
                for feature in definition.runtime_features
                if isinstance(feature, (NameGeneratorFeature, EnchantmentRowFeature))
            ),
            *legacy_runtime_features(definition.runtime_capabilities),
        )
        for feature in owned:
            _require_runtime_feature_evidence(inventory, feature)
            claims.append((inventory.selected.alias, feature))

    # A schema-v1 compatibility adapter owns capabilities outside the package
    # definition. Attribute each translated fixed record by concrete package
    # evidence rather than by load order or package identity.
    adapter_capabilities = tuple(
        capability
        for capability in runtime_capabilities
        if capability not in definition_legacy_capabilities
    )
    for capability in sorted(set(adapter_capabilities)):
        translated_group = legacy_runtime_features((capability,))
        if not translated_group:
            continue
        candidates = [
            inventory
            for inventory in inventories
            if all(
                not _runtime_feature_evidence_errors(inventory, feature)
                for feature in translated_group
            )
        ]
        if len(candidates) != 1:
            labels = ", ".join(
                inventory.selected.alias for inventory in candidates
            ) or "none"
            raise ComposeError(
                f"legacy runtime capability {capability!r} must be owned as one "
                "indivisible feature group by exactly one selected package "
                f"(candidates: {labels})"
            )
        claims.extend(
            (candidates[0].selected.alias, feature)
            for feature in translated_group
        )

    for inventory in inventories:
        _require_name_generator_declarations(
            inventory,
            tuple(
                feature
                for owner, feature in claims
                if owner == inventory.selected.alias
                and isinstance(feature, NameGeneratorFeature)
            ),
        )

    owners: dict[tuple[str, str], tuple[str, RuntimeFeature]] = {}
    for owner, feature in claims:
        if isinstance(feature, NameGeneratorFeature):
            key = ("name-generator", feature.generator_id)
        elif isinstance(feature, EnchantmentRowFeature):
            key = ("enchantment-row", feature.overlay_id)
        else:  # Keep unrelated schema-v3 feature families out of MMFR.
            raise ComposeError(
                "runtime feature registry received an unsupported feature family: "
                f"{type(feature).__name__}"
            )
        prior = owners.get(key)
        if prior is not None and prior[0] != owner:
            raise ComposeError(
                f"runtime feature {key[1]!r} is claimed by both "
                f"{prior[0]} and {owner}"
            )
        owners[key] = (owner, feature)
    try:
        return normalize_runtime_features(feature for _owner, feature in claims)
    except ValueError as exc:
        raise ComposeError(f"invalid combined runtime features: {exc}") from exc


def _require_name_generator_declarations(
    inventory: PackageInventory,
    features: Sequence[RuntimeFeature],
) -> None:
    """Require every private NameGenType used by a package to be typed."""

    declared = {
        feature.generator_id
        for feature in features
        if isinstance(feature, NameGeneratorFeature)
    }
    stock = {f"NM{index:02d}" for index in range(1, 18)}
    used: set[str] = set()
    for path in inventory.descriptions:
        document = _parse_description_file(path)
        for record in document.records:
            for element in record.to_element().findall(".//NameGenType"):
                value = element.get("value", "")
                try:
                    encoded = value.encode("ascii")
                except UnicodeEncodeError:
                    continue
                if (
                    len(encoded) == 4
                    and value.startswith("NM")
                    and all(0x21 <= byte <= 0x7E for byte in encoded)
                    and value not in stock
                ):
                    used.add(value)
    missing = sorted(used - declared)
    if missing:
        raise ComposeError(
            f"{inventory.selected.alias}: private NameGenType selection(s) "
            f"{', '.join(missing)} require matching name-generator runtime_features"
        )


def _require_runtime_feature_evidence(
    inventory: PackageInventory,
    feature: RuntimeFeature,
) -> None:
    errors = _runtime_feature_evidence_errors(inventory, feature)
    if errors:
        raise ComposeError(
            f"{inventory.selected.alias}: " + "; ".join(errors)
        )


def _runtime_feature_evidence_errors(
    inventory: PackageInventory,
    feature: RuntimeFeature,
) -> tuple[str, ...]:
    errors: list[str] = []
    description_elements: list[ET.Element] = []
    for path in inventory.descriptions:
        document = _parse_description_file(path)
        description_elements.extend(record.to_element() for record in document.records)

    if isinstance(feature, NameGeneratorFeature):
        for table in feature.name_part_ids:
            key = table.encode("ascii")
            matches = [
                resource
                for resource in inventory.resources
                if resource.section == b"STRT" and resource.key == key
            ]
            if len(matches) != 1:
                errors.append(
                    f"name generator {feature.generator_id} requires exactly one "
                    f"package-owned STRT/{table} resource; found {len(matches)}"
                )
        references = sum(
            1
            for element in description_elements
            for name_gen in element.findall(".//NameGenType")
            if name_gen.get("value") == feature.generator_id
        )
        if references == 0:
            errors.append(
                f"name generator {feature.generator_id} is not selected by any "
                "package-owned Description NameGenType"
            )
    elif isinstance(feature, EnchantmentRowFeature):
        matches = [
            element
            for element in description_elements
            if element.get("subType") == "Overlay"
            and element.get("ID") == feature.overlay_id
        ]
        if len(matches) != 1:
            errors.append(
                f"enchantment row {feature.overlay_id} requires exactly one "
                f"package-owned Overlay Description; found {len(matches)}"
            )
    else:  # pragma: no cover - guarded by package parsing and normalization
        errors.append(f"unsupported runtime feature record: {feature!r}")
    return tuple(errors)


def resolve_controller_registry(
    inventories: Sequence[PackageInventory],
    runtime_capabilities: Sequence[str] = (),
    *,
    building_dialogs: Sequence[ResolvedBuildingDialog] | None = None,
    reserved_dialog_ids: Sequence[bytes] = (),
) -> ControllerComposeResult:
    """Resolve package-local stock-controller recipes into manager-owned MMCR.

    Author keys remain local to one package. Before records from different
    packages meet, every logical key is qualified with the package's complete
    UUID and a collision-checked digest. Parent buildings and child panel
    DialogIDs are then resolved to the same manager allocation used by the
    composed CAM/XML output.
    """

    if building_dialogs is None:
        building_dialogs = resolve_building_dialogs(
            inventories,
            reserved_dialog_ids=reserved_dialog_ids,
        )
    building_by_owner = {
        (item.owner, item.local_name): item for item in building_dialogs
    }

    claims: list[tuple[PackageInventory, ControllerFeature]] = []
    declared_legacy = False
    for inventory in inventories:
        definition = inventory.selected.package.definition
        if definition is None:
            raise ComposeError(
                f"{inventory.selected.alias}: a mod definition is required"
            )
        owned = [
            feature
            for feature in definition.runtime_features
            if isinstance(feature, _CONTROLLER_FEATURE_CLASSES)
        ]
        if LEGACY_ALCHEMIST_CONTROLLER_CAPABILITY in definition.runtime_capabilities:
            declared_legacy = True
            owned.extend(
                legacy_controller_features(
                    definition.runtime_capabilities,
                    parent_building=_legacy_controller_parent(inventory),
                )
            )
        _require_v3_panel_declaration_completeness(
            inventory,
            owned,
            building_dialogs,
        )
        if owned:
            _require_controller_feature_evidence(inventory, owned)
            claims.extend((inventory, feature) for feature in owned)

    # Compatibility adapters for schema-v1 packages still carry the old
    # Alchemist capability. Attribute it by exact package evidence, never UUID,
    # display name, selection order, or install path.
    if (
        LEGACY_ALCHEMIST_CONTROLLER_CAPABILITY in runtime_capabilities
        and not declared_legacy
    ):
        candidates: list[tuple[PackageInventory, tuple[ControllerFeature, ...]]] = []
        for inventory in inventories:
            try:
                legacy = legacy_controller_features(
                    (LEGACY_ALCHEMIST_CONTROLLER_CAPABILITY,),
                    parent_building=_legacy_controller_parent(inventory),
                )
                _require_controller_feature_evidence(inventory, legacy)
            except (ComposeError, ControllerFeatureError):
                continue
            candidates.append((inventory, legacy))
        if len(candidates) != 1:
            labels = ", ".join(
                item.selected.alias for item, _features in candidates
            ) or "none"
            raise ComposeError(
                "legacy controller capability could not be attributed to exactly "
                f"one selected package (candidates: {labels})"
            )
        inventory, legacy = candidates[0]
        claims.extend((inventory, feature) for feature in legacy)

    if not claims:
        empty = resolve_stock_controller_registry((), {})
        return ControllerComposeResult(empty, (), (), ())

    qualified: list[ControllerFeature] = []
    mappings: dict[tuple[str, str, str], ControllerKeyMapping] = {}
    qualified_origins: dict[str, tuple[str, str]] = {}
    panel_types = (StockAp10Ap69SecondaryPanel, StockMx09Ap41RewardPanel,
                   StockMx04Mx05OccupantActionPanel, StockAp08Mx05QuestBoardPanel)
    raw_panels: dict[str, tuple[PackageInventory, ControllerFeature]] = {}
    raw_toggles: dict[str, tuple[PackageInventory, StockMx22BuildingOpenToggle]] = {}
    flag_prototypes: dict[str, str] = {}
    for inventory, feature in claims:
        package_id = _normalized_mod_uuid(inventory.selected.package.mod_id)

        def qualify(kind: str, raw: str) -> str:
            value = _qualified_controller_key(package_id, raw)
            origin = (package_id, raw)
            prior = qualified_origins.get(value)
            if prior is not None and prior != origin:
                raise ComposeError(
                    "controller logical-key digest collision between "
                    f"{prior!r} and {origin!r}"
                )
            qualified_origins[value] = origin
            mappings[(inventory.selected.alias, kind, raw)] = ControllerKeyMapping(
                owner=inventory.selected.alias,
                mod_id=package_id,
                kind=kind,
                raw_key=raw,
                qualified_key=value,
            )
            return value

        resolved_feature = _qualify_controller_feature(feature, qualify)
        qualified.append(resolved_feature)
        if isinstance(feature, panel_types):
            raw_panels[resolved_feature.panel_key] = (inventory, feature)
        elif isinstance(feature, StockMx22BuildingOpenToggle):
            raw_toggles[resolved_feature.toggle_key] = (inventory, feature)
        elif isinstance(feature, StockAp41Fl00HostileMonsterFlag):
            descriptions = []
            for path in inventory.descriptions:
                document = _parse_description_file(path)
                descriptions.extend(record.to_element() for record in document.records)
            matches = [
                element for element in descriptions
                if element.get("ID") == feature.private_flag_id
                and element.get("subType") == "Overlay"
            ]
            if len(matches) == 1:
                prototype = matches[0].get("Name", "")
                if not prototype:
                    raise ComposeError(
                        f"{inventory.selected.alias}: private_flag_id "
                        f"{feature.private_flag_id!r} has no prototype Name"
                    )
                flag_prototypes[resolved_feature.action_key] = prototype

    # ``source_dialog_id`` names a package-owned CAM resource and is discarded
    # after that resource is rewritten to its manager-allocated child DialogID.
    # Give it a deterministic temporary FourCC for global recipe validation so
    # unrelated packages may safely reuse the same authored source FourCC.
    temporary_panel_sources = {
        feature.panel_key: f"Q{index:03X}"
        for index, feature in enumerate(
            sorted(
                (
                    item
                    for item in qualified
                    if isinstance(item, panel_types)
                ),
                key=lambda item: item.panel_key,
            )
        )
    }
    qualified = [
        replace(
            feature,
            source_dialog_id=temporary_panel_sources[feature.panel_key],
        )
        if isinstance(feature, panel_types)
        else feature
        for feature in qualified
    ]

    try:
        normalized = normalize_controller_features(qualified)
    except ControllerFeatureError as exc:
        raise ComposeError(f"combined controller recipes are unsafe: {exc}") from exc

    reserved_dialogs = {
        resource.key
        for inventory in inventories
        for resource in inventory.resources
        if len(resource.key) == 4
    }
    reserved_dialogs.update(
        dialog_id
        for inventory in inventories
        for dialog_id in getattr(inventory.selected, "reserved_dialog_ids", ())
        if len(dialog_id) == 4
    )
    reserved_dialogs.update(item.resolved_dialog_id for item in building_dialogs)
    reserved_dialogs.update(
        dialog_id for dialog_id in reserved_dialog_ids if len(dialog_id) == 4
    )
    available = (
        f"CG{left}{right}".encode("ascii")
        for left in "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        for right in "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    )
    free = (candidate for candidate in available if candidate not in reserved_dialogs)
    panel_dialog_ids: dict[str, tuple[int, int]] = {}
    occupant_parent_bases: dict[str, str] = {}
    toggle_parents: dict[str, tuple[int, str]] = {}
    toggles: list[ResolvedControllerToggle] = []
    panels: list[ResolvedControllerPanel] = []
    panel_features = [
        feature
        for feature in normalized
        if isinstance(feature, panel_types)
    ]
    for feature in panel_features:
        inventory, raw = raw_panels[feature.panel_key]
        if isinstance(feature, (StockMx04Mx05OccupantActionPanel,
                                StockAp08Mx05QuestBoardPanel)):
            definition = inventory.selected.package.definition
            occupant_parent_bases[feature.panel_key] = next(
                b.controller_base for b in definition.custom_buildings
                if b.local_name == raw.parent_building
            )
        parent = building_by_owner.get(
            (inventory.selected.alias, raw.parent_building)
        )
        if parent is None:
            raise ComposeError(
                f"{inventory.selected.alias}: controller panel {raw.panel_key!r} "
                f"refers to undeclared parent building {raw.parent_building!r}"
            )
        try:
            child = next(free)
        except StopIteration as exc:
            raise ComposeError(
                "no manager-owned CGxx secondary-panel DialogIDs remain"
            ) from exc
        reserved_dialogs.add(child)
        source = raw.source_dialog_id.encode("ascii")
        if any(
            item.owner == inventory.selected.alias
            and item.source_dialog_id == source
            for item in building_dialogs
        ):
            raise ComposeError(
                f"{inventory.selected.alias}: secondary panel {raw.panel_key!r} "
                f"shares source DialogID {raw.source_dialog_id!r} with its "
                "building panel"
            )
        panel_dialog_ids[feature.panel_key] = (
            int.from_bytes(parent.resolved_dialog_id, "little"),
            int.from_bytes(child, "little"),
        )
        panels.append(
            ResolvedControllerPanel(
                owner=inventory.selected.alias,
                raw_panel_key=raw.panel_key,
                qualified_panel_key=feature.panel_key,
                raw_parent_building=raw.parent_building,
                qualified_parent_building=feature.parent_building,
                source_dialog_id=source,
                resolved_parent_dialog_id=parent.resolved_dialog_id,
                resolved_child_dialog_id=child,
            )
        )
    for feature in normalized:
        if not isinstance(feature, StockMx22BuildingOpenToggle):
            continue
        inventory, raw = raw_toggles[feature.toggle_key]
        parent = building_by_owner.get((inventory.selected.alias, raw.parent_building))
        if parent is None:
            raise ComposeError(
                f"{inventory.selected.alias}: building toggle {raw.toggle_key!r} "
                f"refers to undeclared parent building {raw.parent_building!r}"
            )
        definition = inventory.selected.package.definition
        assert definition is not None
        declaration = next(
            item for item in definition.custom_buildings
            if item.local_name == raw.parent_building
        )
        toggle_parents[feature.toggle_key] = (
            int.from_bytes(parent.resolved_dialog_id, "little"),
            declaration.controller_base,
        )
        toggles.append(ResolvedControllerToggle(
            owner=inventory.selected.alias,
            raw_toggle_key=raw.toggle_key,
            qualified_toggle_key=feature.toggle_key,
            raw_parent_building=raw.parent_building,
            resolved_parent_dialog_id=parent.resolved_dialog_id,
        ))
    try:
        registry = resolve_stock_controller_registry(
            normalized, panel_dialog_ids, flag_prototypes=flag_prototypes,
            occupant_parent_bases=occupant_parent_bases,
            toggle_parents=toggle_parents,
        )
    except ControllerRegistryError as exc:
        raise ComposeError(f"resolved controller registry is unsafe: {exc}") from exc
    return ControllerComposeResult(
        registry=registry,
        panels=tuple(panels),
        key_mappings=tuple(
            mappings[key]
            for key in sorted(
                mappings,
                key=lambda item: (
                    mappings[item].mod_id,
                    item[1],
                    item[2].casefold(),
                ),
            )
        ),
        toggles=tuple(toggles),
    )


_CONTROLLER_FEATURE_CLASSES = (
    StockAp08Mx05QuestBoardPanel,
    StockMx04Mx05OccupantActionPanel,
    StockMx22BuildingOpenToggle,
    StockAp10Ap69SecondaryPanel,
    StockMx09Ap41RewardPanel,
    StockAp41Fl00HostileMonsterFlag,
    StockAp22ResourceMeter,
    StockAp99ResearchRow,
    StockAp17UpgradeResearchGate,
    StockAp24TimedRageAction,
    StockAp24RageCommandAction,
    StockAp69SovereignTargetAction,
)


def _legacy_controller_parent(inventory: PackageInventory) -> str:
    definition = inventory.selected.package.definition
    if definition is None or len(definition.custom_buildings) != 1:
        raise ComposeError(
            f"{inventory.selected.alias}: legacy controller compatibility requires "
            "exactly one declared parent building"
        )
    return definition.custom_buildings[0].local_name


def _normalized_mod_uuid(value: str) -> str:
    try:
        return uuid.UUID(value.strip().strip("{}")).hex
    except ValueError as exc:
        raise ComposeError(f"package Mod id is not a UUID: {value!r}") from exc


def _qualified_controller_key(mod_uuid: str, raw_key: str) -> str:
    digest = base64.b32encode(
        hashlib.sha256(raw_key.encode("ascii")).digest()
    ).decode("ascii").rstrip("=").lower()[:26]
    # 1 + 32 + 1 + 26 = 60 ASCII bytes, within MMCR's strict 64-byte bound.
    return f"m{mod_uuid}.{digest}"


def _qualify_controller_feature(feature: ControllerFeature, qualify) -> ControllerFeature:
    if isinstance(feature, StockMx22BuildingOpenToggle):
        return replace(
            feature,
            toggle_key=qualify("toggle", feature.toggle_key),
            parent_building=qualify("parent_building", feature.parent_building),
        )
    panel = qualify("panel", feature.panel_key)
    if isinstance(feature, StockAp10Ap69SecondaryPanel):
        return replace(
            feature,
            panel_key=panel,
            parent_building=qualify("parent_building", feature.parent_building),
        )
    if isinstance(feature, (StockMx09Ap41RewardPanel, StockMx04Mx05OccupantActionPanel,
                            StockAp08Mx05QuestBoardPanel)):
        return replace(
            feature,
            panel_key=panel,
            parent_building=qualify("parent_building", feature.parent_building),
        )
    if isinstance(feature, StockAp41Fl00HostileMonsterFlag):
        return replace(
            feature,
            panel_key=panel,
            action_key=qualify("action", feature.action_key),
        )
    if isinstance(feature, StockAp22ResourceMeter):
        return replace(
            feature,
            panel_key=panel,
            resource_key=qualify("resource", feature.resource_key),
        )
    if isinstance(feature, StockAp99ResearchRow):
        return replace(
            feature,
            panel_key=panel,
            recipe_key=qualify("recipe", feature.recipe_key),
        )
    if isinstance(feature, StockAp17UpgradeResearchGate):
        return replace(
            feature,
            panel_key=panel,
            parent_building=qualify("parent_building", feature.parent_building),
            requirements=tuple(
                UpgradeRequirement(
                    item.building_level,
                    qualify("recipe", item.recipe_key),
                )
                for item in feature.requirements
            ),
        )
    if isinstance(feature, (StockAp24TimedRageAction, StockAp24RageCommandAction)):
        return replace(
            feature,
            panel_key=panel,
            action_key=qualify("action", feature.action_key),
            resource_key=qualify("resource", feature.resource_key),
        )
    if isinstance(feature, StockAp69SovereignTargetAction):
        return replace(
            feature,
            panel_key=panel,
            action_key=qualify("action", feature.action_key),
            resource_key=qualify("resource", feature.resource_key),
        )
    raise ComposeError(f"unsupported controller feature: {feature!r}")


def _require_controller_feature_evidence(
    inventory: PackageInventory,
    features: Sequence[ControllerFeature],
) -> None:
    try:
        normalized = normalize_controller_features(features)
    except ControllerFeatureError as exc:
        raise ComposeError(
            f"{inventory.selected.alias}: invalid controller recipes: {exc}"
        ) from exc

    descriptions = []
    for path in inventory.descriptions:
        document = _parse_description_file(path)
        descriptions.extend(record.to_element() for record in document.records)
    gpl_functions: dict[str, list[str]] = {}
    callback_sources = _parse_inventory_gpl_sources(inventory)
    for source in callback_sources:
        for item in source.items:
            if item.kind is DefinitionKind.FUNCTION:
                gpl_functions.setdefault(item.name.casefold(), []).append(
                    item.source_name
                )

    definition = inventory.selected.package.definition
    assert definition is not None
    declared_buildings = {
        item.local_name: item for item in definition.custom_buildings
    }
    for feature in normalized:
        if isinstance(feature, StockMx22BuildingOpenToggle):
            parent = declared_buildings.get(feature.parent_building)
            if parent is None:
                raise ComposeError(
                    f"{inventory.selected.alias}: building toggle "
                    f"{feature.toggle_key!r} parent_building "
                    f"{feature.parent_building!r} is not declared"
                )
            if parent.controller_base not in ("AP07", "AP10", "MX09"):
                raise ComposeError(
                    "building open toggles require an AP07, AP10, or MX09 "
                    "parent controller"
                )
        elif isinstance(feature, StockAp10Ap69SecondaryPanel):
            parent = declared_buildings.get(feature.parent_building)
            if parent is None:
                raise ComposeError(
                    f"{inventory.selected.alias}: panel {feature.panel_key!r} "
                    f"parent_building {feature.parent_building!r} is not declared"
                )
            if (
                parent.controller_base,
                parent.panel_resource_template,
            ) != ("AP10", "AP10"):
                raise ComposeError(
                    f"{inventory.selected.alias}: panel {feature.panel_key!r} "
                    "uses the stock AP10/AP69 secondary-panel lifecycle and "
                    f"therefore requires parent building {feature.parent_building!r} "
                    "to declare controller_base AP10 and "
                    "panel_resource_template AP10"
                )
            source = feature.source_dialog_id.encode("ascii")
            for section in (b"SMNU", b"STRT"):
                matches = [
                    resource
                    for resource in inventory.resources
                    if resource.section == section and resource.key == source
                ]
                if len(matches) != 1:
                    raise ComposeError(
                        f"{inventory.selected.alias}: panel {feature.panel_key!r} "
                        f"requires exactly one package-owned "
                        f"{section.decode('ascii')}/{feature.source_dialog_id}; "
                        f"found {len(matches)}"
                    )
            family_records = [
                element
                for element in descriptions
                if element.get("subType") == "Building"
                and element.get("ID", "").startswith(feature.building_family_id)
            ]
            family_matches = [
                element
                for element in family_records
                if _is_building_name(
                    element.get("Name", ""), feature.parent_building
                )
            ]
            if not family_records or len(family_matches) != len(family_records):
                raise ComposeError(
                    f"{inventory.selected.alias}: panel {feature.panel_key!r} "
                    f"building_family_id {feature.building_family_id!r} is not "
                    "owned exclusively by matching parent Building Descriptions"
                )
        elif isinstance(feature, (
            StockMx09Ap41RewardPanel,
            StockMx04Mx05OccupantActionPanel,
            StockAp08Mx05QuestBoardPanel,
        )):
            parent = declared_buildings.get(feature.parent_building)
            if parent is None:
                raise ComposeError(
                    f"{inventory.selected.alias}: panel {feature.panel_key!r} "
                    f"parent_building {feature.parent_building!r} is not declared"
                )
            if isinstance(feature, StockMx09Ap41RewardPanel) and (parent.controller_base, parent.panel_resource_template) != ("MX09", "MX09"):
                raise ComposeError(
                    f"{inventory.selected.alias}: panel {feature.panel_key!r} "
                    "uses the stock MX09/AP41 reward lifecycle and therefore "
                    "requires an MX09/MX09 parent building"
                )
            source = feature.source_dialog_id.encode("ascii")
            for section in (b"SMNU", b"STRT"):
                matches = [
                    resource for resource in inventory.resources
                    if resource.section == section and resource.key == source
                ]
                if len(matches) != 1:
                    raise ComposeError(
                        f"{inventory.selected.alias}: reward panel {feature.panel_key!r} "
                        f"requires exactly one package-owned {section.decode('ascii')}/"
                        f"{feature.source_dialog_id}; found {len(matches)}"
                    )
            if isinstance(feature, StockMx04Mx05OccupantActionPanel):
                if parent.controller_base not in ("AP07", "AP10", "MX09"):
                    raise ComposeError("occupant panels require an AP07, AP10, or MX09 building controller")
                for symbol in (feature.cost_callback_symbol, feature.action_callback_symbol):
                    matches = gpl_functions.get(symbol.casefold(), ())
                    if len(matches) != 1:
                        raise ComposeError(
                            f"{inventory.selected.alias}: occupant callback {symbol!r} "
                            "requires exactly one package-owned GPL function"
                        )
                    item = next(item for source in callback_sources for item in source.items
                                if item.kind is DefinitionKind.FUNCTION and item.name.casefold() == symbol.casefold())
                    _require_occupant_callback_signature(
                        item.text, symbol, symbol == feature.cost_callback_symbol
                    )
            elif isinstance(feature, StockAp08Mx05QuestBoardPanel):
                if (
                    parent.controller_base,
                    parent.panel_resource_template,
                ) != ("AP08", "AP08"):
                    raise ComposeError(
                        "quest-board panels use Majesty's stock AP08 quest-"
                        "building lifecycle and require an AP08/AP08 parent"
                    )
                callbacks = (
                    (feature.list_source_callback_symbol, ("agent", "integer"), "agent"),
                    (feature.revision_callback_symbol, ("agent",), "integer"),
                    (feature.offer_name_callback_symbol, ("agent", "integer"), "string"),
                    (feature.offer_goal_callback_symbol, ("agent", "integer"), "string"),
                    (feature.offer_reward_callback_symbol, ("agent", "integer"), "integer"),
                    (feature.selected_cost_callback_symbol, ("agent",), "integer"),
                    (feature.selected_action_callback_symbol, ("agent",), "boolean"),
                    (feature.refresh_cost_callback_symbol, ("agent",), "integer"),
                    (feature.can_refresh_callback_symbol, ("agent",), "boolean"),
                    (feature.refresh_callback_symbol, ("agent",), "boolean"),
                )
                for symbol, parameters, result_type in callbacks:
                    matches = gpl_functions.get(symbol.casefold(), ())
                    if len(matches) != 1:
                        raise ComposeError(
                            f"{inventory.selected.alias}: quest-board callback "
                            f"{symbol!r} requires exactly one package-owned GPL "
                            f"function; found {len(matches)}"
                        )
                    item = next(
                        item
                        for source in callback_sources
                        for item in source.items
                        if item.kind is DefinitionKind.FUNCTION
                        and item.name.casefold() == symbol.casefold()
                    )
                    _require_quest_board_callback_signature(
                        item.text, symbol, parameters, result_type
                    )
        elif isinstance(feature, StockAp41Fl00HostileMonsterFlag):
            matches = [
                element for element in descriptions
                if element.get("ID") == feature.private_flag_id
                and element.get("subType") == "Overlay"
                and bool(element.get("Name"))
            ]
            if len(matches) != 1:
                raise ComposeError(
                    f"{inventory.selected.alias}: private_flag_id "
                    f"{feature.private_flag_id!r} requires exactly one package-owned "
                    "Overlay Description with a prototype Name"
                )
            expected_set = 1000 + feature.cursor_ordinal
            cursor_matches = 0
            for resource in inventory.resources:
                if (
                    resource.section == b"IMAG"
                    and resource.entry.name.rstrip(b"\x00")[:4] == b"CUR1"
                ):
                    _header, sets = _split_imag_sets(resource.entry)
                    cursor_matches += sum(
                        set_id == expected_set for set_id, _payload in sets
                    )
            if cursor_matches != 1:
                raise ComposeError(
                    f"{inventory.selected.alias}: cursor_ordinal "
                    f"{feature.cursor_ordinal} requires exactly one package-owned "
                    f"CUR1 set {expected_set}; found {cursor_matches}"
                )
        elif isinstance(feature, (StockAp24TimedRageAction, StockAp24RageCommandAction)):
            matches = gpl_functions.get(feature.callback_symbol.casefold(), ())
            if len(matches) != 1:
                raise ComposeError(
                    f"{inventory.selected.alias}: callback_symbol "
                    f"{feature.callback_symbol!r} requires exactly one "
                    f"package-owned GPL function; found {len(matches)}"
                )
        elif isinstance(feature, StockAp69SovereignTargetAction):
            matches = [
                element
                for element in descriptions
                if element.get("ID") == feature.private_unit_id
                and element.get("subType") == "Character"
            ]
            if len(matches) != 1:
                raise ComposeError(
                    f"{inventory.selected.alias}: private_unit_id "
                    f"{feature.private_unit_id!r} requires exactly one "
                    "package-owned Character Description"
                )


def _require_occupant_callback_signature(text: str, symbol: str, cost: bool) -> None:
    from .gpl import _mask_non_code

    returns = r"\s+is\s+integer" if cost else ""
    pattern = (r"\s*function\s+" + re.escape(symbol) +
               r"\s*\(\s*agent\s+[A-Za-z_][A-Za-z0-9_]*\s*\)" +
               returns + r"\s*(?:declare|begin)\b")
    if re.match(pattern, _mask_non_code(text), re.IGNORECASE) is None:
        expected = "(agent) is integer" if cost else "(agent) with no return type"
        raise ComposeError(f"occupant callback {symbol!r} must use the stock signature {expected}")


def _require_quest_board_callback_signature(
    text: str,
    symbol: str,
    parameter_types: Sequence[str],
    result_type: str,
) -> None:
    """Require the bounded native evaluator ABI used by the quest board."""

    from .gpl import _mask_non_code

    parameters = r"\s*,\s*".join(
        re.escape(kind) + r"\s+[A-Za-z_][A-Za-z0-9_]*"
        for kind in parameter_types
    )
    pattern = (
        r"\s*function\s+" + re.escape(symbol)
        + r"\s*\(\s*" + parameters + r"\s*\)"
        + r"\s+is\s+" + re.escape(result_type)
        + r"\s*(?:declare|begin)\b"
    )
    if re.match(pattern, _mask_non_code(text), re.IGNORECASE) is None:
        expected = f"({', '.join(parameter_types)}) is {result_type}"
        raise ComposeError(
            f"quest-board callback {symbol!r} must use signature {expected}"
        )


def _require_v3_panel_declaration_completeness(
    inventory: PackageInventory,
    controller_features: Sequence[ControllerFeature],
    building_dialogs: Sequence[ResolvedBuildingDialog],
) -> None:
    """Reject undeclared v3 panel resources and custom Building records."""

    definition = inventory.selected.package.definition
    if definition is None or getattr(definition, "schema_version", 2) != 3:
        return

    owner = inventory.selected.alias
    declared_sources: dict[bytes, str] = {}

    def declare(source: bytes, label: str) -> None:
        previous = declared_sources.get(source)
        if previous is not None:
            raise ComposeError(
                f"{owner}: panel source {_display_key(source)} is declared by "
                f"both {previous} and {label}"
            )
        declared_sources[source] = label

    for building in building_dialogs:
        if building.owner == owner:
            declare(
                building.source_dialog_id,
                f"building {building.local_name!r}",
            )
    for feature in controller_features:
        if isinstance(feature, (StockAp10Ap69SecondaryPanel, StockMx09Ap41RewardPanel,
                                StockMx04Mx05OccupantActionPanel,
                                StockAp08Mx05QuestBoardPanel)):
            declare(
                feature.source_dialog_id.encode("ascii"),
                f"secondary panel {feature.panel_key!r}",
            )


def prepare_final_gpl_resources(
    game_path: Path,
    inventories: Sequence[PackageInventory],
    *,
    resolution_owners: Mapping[tuple[DefinitionKind | str, str], str] | None = None,
    semantic_resolutions: Mapping[
        tuple[DefinitionKind | str, str],
        SemanticItem | ScopedSemanticResolution,
    ] | None = None,
    inventory_death_drop_exclusions: Sequence[str] = (),
    private_activity_texts: Sequence[PrivateActivityTextBinding] = (),
) -> GplComposeResult:
    """Build the exact final GPL source set used by both Prepare and Build."""

    stock_semantic_sources: Sequence[ParsedSemanticSource] = ()
    if any(inventory.selected.semantic_passthrough for inventory in inventories):
        try:
            stock_semantic_sources = load_verified_stock_semantic_sources(game_path)[0]
        except (OSError, StockGplError, ValueError) as exc:
            raise ComposeError(
                "installed stock GPL source could not be proven against the bytecode "
                f"Majesty actually loads: {exc}"
            ) from exc

    has_purchase_tail = any(
        isinstance(feature, StockGplmxPurchaseEquipmentTail)
        for inventory in inventories
        for feature in inventory.selected.package.definition.runtime_features
    )
    has_bazaar_tail = any(
        isinstance(feature, StockGplmxPurchaseBazaarTail)
        for inventory in inventories
        for feature in inventory.selected.package.definition.runtime_features
    )
    has_controlled_follower_movement = any(
        isinstance(feature, StockControlledFollowerSpeedSync)
        for inventory in inventories
        for feature in inventory.selected.package.definition.runtime_features
    )
    controlled_follower_stock_items = (
        _load_stock_controlled_follower_items(game_path)
        if has_controlled_follower_movement
        else (None, None, None)
    )
    has_hero_quest_lifecycle = any(
        isinstance(feature, StockHeroQuestLifecycle)
        for inventory in inventories
        for feature in inventory.selected.package.definition.runtime_features
    )
    hero_quest_stock_items = (
        _load_stock_hero_quest_lifecycle_items(game_path)
        if has_hero_quest_lifecycle
        else (None, None, None)
    )
    return merge_gpl_resources(
        inventories,
        resolution_owners=resolution_owners,
        semantic_resolutions=semantic_resolutions,
        inventory_death_drop_exclusions=inventory_death_drop_exclusions,
        private_activity_texts=private_activity_texts,
        stock_semantic_sources=stock_semantic_sources,
        stock_integer_expression_sources=(
            (_load_stock_activity_text_expression_source(game_path),)
            if private_activity_texts
            else ()
        ),
        stock_purchase_equipment_source=(
            _load_stock_purchase_equipment_source(game_path)
            if has_purchase_tail
            else None
        ),
        stock_purchase_bazaar_source=(
            _load_stock_purchase_bazaar_source(game_path)
            if has_bazaar_tail
            else None
        ),
        stock_control_monster=controlled_follower_stock_items[0],
        stock_controlled_monster_death=controlled_follower_stock_items[1],
        stock_leader_dead=controlled_follower_stock_items[2],
        stock_hero_trees=hero_quest_stock_items[0],
        stock_reset_tasks=hero_quest_stock_items[1],
        stock_unit_death=hero_quest_stock_items[2],
    )


def compose_package(
    game_path: Path,
    output_root: Path,
    selected_mods: Sequence[SelectedMod],
    *,
    profile_slug: str,
    display_name: str | None = None,
    internal_name: str | None = None,
    resolution_owners: Mapping[tuple[DefinitionKind | str, str], str] | None = None,
    semantic_resolutions: Mapping[
        tuple[DefinitionKind | str, str],
        SemanticItem | ScopedSemanticResolution,
    ] | None = None,
    description_resolutions: Mapping[DescriptionKey, DescriptionRecord] | None = None,
    string_resolutions: Mapping[StringKey, StringRecord] | None = None,
    named_cam_resolutions: Mapping[
        tuple[bytes, bytes], ScopedNamedResourceResolution
    ] | None = None,
    art_resolutions: Mapping[
        tuple[str, bytes], ScopedArtResourceResolution
    ] | None = None,
    strt_resolutions: Mapping[
        tuple[bytes, int], StrtRowResolution
    ] | None = None,
    bdep_resolutions: Mapping[str, BdepRowResolution] | None = None,
    reserved_dialog_ids: Sequence[bytes] = (),
    reserved_description_keys: Sequence[DescriptionKey] = (),
    reserved_description_names: Sequence[str] = (),
    inventory_death_drop_exclusions: Sequence[str] = (),
    runtime_capabilities: Sequence[str] = (),
    private_activity_texts: Sequence[PrivateActivityTextBinding] | None = None,
    prepared_inventories: Sequence[PackageInventory] | None = None,
) -> ComposePackageResult:
    """Generate one atomic, self-contained local profile from any N packages.

    Inputs are read only. The final destination must not exist; generation and
    validation occur in a sibling staging directory that is renamed into place
    only after all checks pass.
    """

    game_path = game_path.resolve(strict=True)
    if not game_path.is_dir():
        raise ComposeError(f"game path is not a directory: {game_path}")
    if not _PROFILE_SLUG.fullmatch(profile_slug):
        raise ComposeError(f"invalid profile slug: {profile_slug!r}")
    if not selected_mods:
        raise ComposeError("at least one mod must be selected")
    aliases = [selected.alias for selected in selected_mods]
    if len(set(aliases)) != len(aliases):
        raise ComposeError("selected mod aliases must be unique")
    mod_ids = [
        _normalized_mod_uuid(selected.package.mod_id)
        for selected in selected_mods
    ]
    if len(set(mod_ids)) != len(mod_ids):
        raise ComposeError("selected package Mod IDs must be unique")
    for selected in selected_mods:
        if selected.package.definition is None:
            raise ComposeError(f"{selected.alias}: a v1 mod definition is required")
    output_root = output_root.resolve(strict=False)
    if output_root.exists():
        raise ComposeError(f"output destination already exists: {output_root}")
    output_root.parent.mkdir(parents=True, exist_ok=True)

    if prepared_inventories is None:
        inventories = tuple(inventory_package(selected) for selected in selected_mods)
    else:
        inventories = tuple(prepared_inventories)
        if (
            len(inventories) != len(selected_mods)
            or any(
                inventory.selected != selected
                for inventory, selected in zip(inventories, selected_mods)
            )
        ):
            raise ComposeError(
                "prepared package inventories do not match the selected mods"
            )
    has_named_cam_resources = any(
        resource.section in STOCK_NAMED_CAM_SECTIONS
        for inventory in inventories
        for resource in inventory.resources
    )
    try:
        stock_named_resources = (
            load_effective_stock_named_resources(game_path)[0]
            if has_named_cam_resources
            else {}
        )
        stock_string_records = (
            load_effective_stock_strings(game_path)[0].index
            if any(inventory.strings for inventory in inventories)
            else {}
        )
    except (OSError, StockCamError, StringsFormatError, ValueError) as exc:
        raise ComposeError(
            f"installed stock resource ancestry is not safe: {exc}"
        ) from exc
    dialog_resolutions = resolve_building_dialogs(
        inventories,
        reserved_dialog_ids=reserved_dialog_ids,
    )
    controller_result = resolve_controller_registry(
        inventories,
        runtime_capabilities,
        building_dialogs=dialog_resolutions,
        reserved_dialog_ids=reserved_dialog_ids,
    )
    controller_registry_payload = encode_stock_controller_registry(
        controller_result.registry
    )
    runtime_feature_registry = resolve_runtime_feature_registry(
        inventories, runtime_capabilities
    )
    runtime_feature_registry_payload = encode_runtime_feature_registry(
        runtime_feature_registry
    )
    if private_activity_texts is None:
        private_activity_texts = discover_private_activity_texts(
            game_path, inventories
        )
    (
        canonical_runtime_capabilities,
        capability_manifest_payload,
    ) = _derive_runtime_capabilities(
        runtime_capabilities,
        has_private_activity_text=bool(private_activity_texts),
        runtime_feature_registry=runtime_feature_registry,
        controller_registry=controller_result.registry,
    )
    text_result = merge_text_resources(
        game_path,
        inventories,
        private_activity_texts=private_activity_texts,
        dialog_resolutions=dialog_resolutions,
        controller_panels=controller_result.panels,
        controller_registry=controller_result.registry,
        named_resolutions=named_cam_resolutions,
        strt_resolutions=strt_resolutions,
        stock_named_resources=stock_named_resources,
    )
    bdep_result = merge_bdep_resource(
        game_path,
        inventories,
        resolutions=bdep_resolutions,
    )
    art_results = merge_art_resource_domains(
        game_path,
        inventories,
        required_stock_imag_ids=(
            (b"IX93",)
            if runtime_feature_registry.enchantment_rows
            else ()
        ),
        art_resolutions=art_resolutions,
    )
    audio_archive, sound_archive, sound_selections = merge_sound_resources(
        inventories,
        named_resolutions=named_cam_resolutions,
        stock_named_resources=stock_named_resources,
    )
    controlled_follower_markers = tuple(
        sorted(
            (
                marker
                for inventory in inventories
                for feature in inventory.selected.package.definition.runtime_features
                if isinstance(feature, StockControlledFollowerSpeedSync)
                for marker in _controlled_follower_markers(
                    _normalized_mod_uuid(inventory.selected.package.mod_id),
                    feature.feature_key,
                )
            ),
            key=str.casefold,
        )
    )
    stock_description_keys = (
        tuple(
            set(_load_effective_stock_descriptions(game_path))
            | set(reserved_description_keys)
        )
        if controlled_follower_markers
        else ()
    )
    descriptions = merge_description_resources(
        inventories,
        dialog_resolutions=dialog_resolutions,
        controlled_follower_markers=controlled_follower_markers,
        reserved_description_keys=stock_description_keys,
        reserved_description_names=reserved_description_names,
        resolutions=description_resolutions,
    )
    descriptions = filter_passthrough_descriptions(
        descriptions,
        inventories,
        stock_records={
            key: value[0]
            for key, value in _load_effective_stock_descriptions(game_path).items()
        },
        forced_keys=(description_resolutions or {}),
    )
    strings = merge_string_resources(
        inventories,
        resolutions=string_resolutions,
        stock_records=stock_string_records,
    )
    description_stock_deltas = analyze_description_stock_deltas(
        game_path,
        inventories,
        descriptions=descriptions,
    )
    validate_controller_stock_evidence(
        game_path,
        inventories,
        controller_result.registry,
        controller_panels=controller_result.panels,
        controller_toggles=controller_result.toggles,
        runtime_feature_registry=runtime_feature_registry,
        description_stock_deltas=description_stock_deltas,
    )
    gpl = prepare_final_gpl_resources(
        game_path,
        inventories,
        resolution_owners=resolution_owners,
        semantic_resolutions=semantic_resolutions,
        inventory_death_drop_exclusions=inventory_death_drop_exclusions,
        private_activity_texts=private_activity_texts,
    )

    output_mod_id = _generated_mod_id(selected_mods, profile_slug)
    actual_display_name = display_name or f"CAM Manager: {profile_slug}"
    actual_internal_name = internal_name or (
        "CAMManager" + "".join(part.title() for part in profile_slug.split("-"))
    )
    definition_payload = _generated_definition(
        output_mod_id,
        actual_internal_name,
        actual_display_name,
        selected_mods,
        canonical_runtime_capabilities,
        dialog_resolutions,
    )

    staging = Path(
        tempfile.mkdtemp(prefix=f".{profile_slug}-", dir=output_root.parent)
    )
    try:
        data_directory = staging / "Data"
        data_directory.mkdir()
        art_outputs = tuple(
            (
                (
                    "merged_maindata.cam"
                    if result.domain == "main"
                    else (
                        "merged_interfacedata.cam"
                        if result.domain == "interface"
                        else f"merged_{result.domain}.cam"
                    )
                ),
                result.archive,
            )
            for result in art_results
        )
        cam_outputs = (
            ("merged_textdata.cam", text_result.text_archive),
            ("merged_gpltext.cam", text_result.gpltext_archive),
            ("merged_miscdata.cam", bdep_result.archive),
            *art_outputs,
            ("merged_audio.cam", audio_archive),
            ("merged_sounddesc.cam", sound_archive),
        )
        for filename, archive in cam_outputs:
            (data_directory / filename).write_bytes(archive.to_bytes())
        descriptions_path = data_directory / "merged_descriptions.xml"
        descriptions_path.write_bytes(descriptions.payload)
        strings_paths: list[Path] = []
        if strings is not None:
            strings_path = data_directory / "merged_strings.xml"
            strings_path.write_bytes(strings.payload)
            strings_paths.append(strings_path)

        compiled = compile_gpl(
            gpl.source_set,
            game_path / "SDK" / "Gplbcc.exe",
            staging / "GPL",
        )
        target = data_directory / "Merged.bcd"
        shutil.copy2(compiled.target, target)
        compiled.target.unlink()

        manifest_name = f"CAMManager-{profile_slug}.mmxml"
        manifest_path = staging / manifest_name
        manifest_path.write_bytes(
            _build_manifest(
                mod_id=output_mod_id,
                internal_name=actual_internal_name,
                display_name=actual_display_name,
                cam_filenames=tuple(filename for filename, _archive in cam_outputs),
                description_filename=descriptions_path.name,
                strings_filenames=tuple(path.name for path in strings_paths),
                source_set=gpl.source_set,
            )
        )
        (staging / "mod-definition.json").write_text(
            json.dumps(definition_payload, indent=2) + "\n", encoding="utf-8"
        )
        registry_path = staging / Path(INTENT_REGISTRY_RELATIVE_PATH)
        registry_path.write_bytes(
            encode_intent_registry(text_result.private_activity_texts)
        )
        capability_manifest_path = staging / Path(
            RUNTIME_CAPABILITY_MANIFEST_RELATIVE_PATH
        )
        capability_manifest_path.parent.mkdir(parents=True, exist_ok=True)
        capability_manifest_path.write_bytes(capability_manifest_payload)
        runtime_feature_registry_path = staging / Path(
            RUNTIME_FEATURE_REGISTRY_RELATIVE_PATH
        )
        runtime_feature_registry_path.parent.mkdir(parents=True, exist_ok=True)
        runtime_feature_registry_path.write_bytes(runtime_feature_registry_payload)
        controller_registry_path = staging / CONTROLLER_REGISTRY_RELATIVE_PATH
        controller_registry_path.parent.mkdir(parents=True, exist_ok=True)
        controller_registry_path.write_bytes(controller_registry_payload)

        validation = validate_composed_package(staging)
        report_payload = _build_report(
            profile_slug=profile_slug,
            output_mod_id=output_mod_id,
            selected_mods=selected_mods,
            game_path=game_path,
            text_result=text_result,
            bdep_result=bdep_result,
            art_results=art_results,
            sound_selections=sound_selections,
            descriptions=descriptions,
            description_stock_deltas=description_stock_deltas,
            dialog_resolutions=dialog_resolutions,
            gpl=gpl,
            compiled=compiled,
            runtime_capabilities=canonical_runtime_capabilities,
            runtime_feature_registry=runtime_feature_registry,
            controller_result=controller_result,
            staging=staging,
            validation=validation,
        )
        report_name = "CAM-MERGE-REPORT.json"
        (staging / report_name).write_text(
            json.dumps(report_payload, indent=2) + "\n", encoding="utf-8"
        )
        staging.rename(output_root)
    except Exception as exc:
        raise ComposeError(
            f"profile generation failed; incomplete staging data was left at "
            f"{staging}: {exc}"
        ) from exc

    return ComposePackageResult(
        output_root=output_root,
        manifest=output_root / manifest_name,
        mod_id=output_mod_id,
        profile_slug=profile_slug,
        report=output_root / report_name,
        validation=validation,
    )


def _controller_record_count(registry: ResolvedControllerRegistry) -> int:
    return sum(
        len(section)
        for section in (
            registry.panels,
            registry.meters,
            registry.research_rows,
            registry.upgrade_gates,
            registry.timed_rage_actions,
            registry.rage_command_actions,
            registry.sovereign_target_actions,
            registry.reward_panels,
            registry.occupant_action_panels,
            registry.hostile_monster_flags,
            registry.building_open_toggles,
            registry.quest_boards,
        )
    )


def _derive_runtime_capabilities(
    runtime_capabilities: Sequence[str],
    *,
    has_private_activity_text: bool,
    runtime_feature_registry: RuntimeFeatureRegistry = RuntimeFeatureRegistry(),
    controller_registry: ResolvedControllerRegistry | None = None,
) -> tuple[tuple[str, ...], bytes]:
    """Validate caller capabilities and derive evidence-owned hook groups.

    MMTX, MMFR, and MMCR hook groups are evidence-owned by composition, never
    by a package identity or caller assertion. Legacy package aliases are
    translated to manager-owned registries and canonicalized out of MMCP.
    """

    try:
        provided = decode_runtime_capability_manifest(
            encode_runtime_capability_manifest(runtime_capabilities)
        )
        effective = set(provided)
        effective.discard(PRIVATE_ACTIVITY_TEXT_RUNTIME_CAPABILITY)
        effective.discard(STOCK_CONTROLLER_RUNTIME_CAPABILITY)
        if has_private_activity_text:
            effective.add(PRIVATE_ACTIVITY_TEXT_RUNTIME_CAPABILITY)
        effective = set(
            derive_feature_runtime_capabilities(
                effective, runtime_feature_registry
            )
        )
        effective.discard(LEGACY_ALCHEMIST_CONTROLLER_CAPABILITY)
        if controller_registry is not None and _controller_record_count(
            controller_registry
        ):
            effective.add(STOCK_CONTROLLER_RUNTIME_CAPABILITY)
        payload = encode_runtime_capability_manifest(tuple(sorted(effective)))
        return decode_runtime_capability_manifest(payload), payload
    except ValueError as exc:
        raise ComposeError(f"invalid runtime capability requirements: {exc}") from exc


def _validate_generated_cam_outputs(
    cam_paths: Sequence[PackagePath],
) -> tuple[list[dict[str, object]], int]:
    normalized_paths = tuple(
        path.relative_path.replace("\\", "/").casefold() for path in cam_paths
    )
    duplicates = sorted(
        path for path in set(normalized_paths) if normalized_paths.count(path) > 1
    )
    if duplicates:
        raise ComposeError(
            "generated package contains duplicate CAM path(s): "
            + ", ".join(duplicates)
        )

    names_by_path: dict[str, str] = {}
    for path, normalized in zip(cam_paths, normalized_paths):
        if normalized.count("/") != 1 or not normalized.startswith("data/"):
            raise ComposeError(
                "generated CAM is not directly under Data: "
                f"{path.relative_path}"
            )
        names_by_path[normalized] = normalized.removeprefix("data/")

    present_names = set(names_by_path.values())
    missing = sorted(set(_FIXED_GENERATED_CAM_SECTIONS) - present_names)
    if missing:
        raise ComposeError(
            "generated package is missing required CAM role(s): "
            + ", ".join(missing)
        )

    cam_summaries: list[dict[str, object]] = []
    palette_reference_count = 0
    for path, normalized in zip(cam_paths, normalized_paths):
        filename = names_by_path[normalized]
        fixed_sections = _FIXED_GENERATED_CAM_SECTIONS.get(filename)
        is_art = fixed_sections is None
        if is_art and _GENERATED_ART_CAM_NAME.fullmatch(filename) is None:
            raise ComposeError(
                f"unsupported generated art CAM filename: {path.relative_path}"
            )

        original = path.absolute_path.read_bytes()
        archive = read_cam(original)
        if archive.to_bytes() != original:
            raise ComposeError(
                f"generated CAM is not byte-stable: {path.relative_path}"
            )
        extensions = tuple(section.extension for section in archive.sections)
        duplicate_extensions = sorted(
            extension
            for extension in set(extensions)
            if extensions.count(extension) > 1
        )
        if duplicate_extensions:
            labels = ", ".join(
                value.decode("ascii", errors="replace")
                for value in duplicate_extensions
            )
            raise ComposeError(
                f"generated CAM contains duplicate section(s) {labels}: "
                f"{path.relative_path}"
            )
        if fixed_sections is not None and extensions != fixed_sections:
            expected = ", ".join(
                extension.decode("ascii") for extension in fixed_sections
            )
            actual = ", ".join(
                extension.decode("ascii", errors="replace")
                for extension in extensions
            )
            raise ComposeError(
                f"generated {filename} CAM role has sections [{actual}], "
                f"expected [{expected}]"
            )
        if is_art:
            if (
                len(extensions) not in {2, 3}
                or extensions[:2] != (b"IMAG", b"TILE")
            ):
                raise ComposeError(
                    "generated art CAM must begin with exactly IMAG and TILE: "
                    f"{path.relative_path}"
                )
            if len(extensions) == 3 and extensions[2] not in {b"SPLT", b"PALT"}:
                raise ComposeError(
                    "generated art CAM has unsupported section "
                    f"{extensions[2].decode('ascii', errors='replace')}: "
                    f"{path.relative_path}"
                )
            if filename == "merged_maindata.cam" and b"PALT" in extensions:
                raise ComposeError(
                    "generated main art CAM cannot contain PALT: "
                    f"{path.relative_path}"
                )
            if filename != "merged_maindata.cam" and b"SPLT" in extensions:
                raise ComposeError(
                    "generated non-main art CAM cannot contain SPLT: "
                    f"{path.relative_path}"
                )

        sections_by_extension = {
            section.extension: section for section in archive.sections
        }
        tile_section = sections_by_extension.get(b"TILE")
        palette_sections = [
            section
            for extension, section in sections_by_extension.items()
            if extension in {b"SPLT", b"PALT"}
        ]
        if len(palette_sections) > 1:
            raise ComposeError(
                f"generated art CAM contains both SPLT and PALT: {path.relative_path}"
            )
        palette_section = palette_sections[0] if palette_sections else None
        if tile_section is not None:
            if tile_section.padding != b"\x01\x00\x00\x00":
                raise ComposeError(
                    f"generated TILE section lost its stock positional flag: "
                    f"{path.relative_path}"
                )
            if palette_section is not None:
                expected_palette_padding = (
                    b"\x01\x00\x00\x00"
                    if palette_section.extension == b"SPLT"
                    else b"\x00\x00\x00\x00"
                )
                if palette_section.padding != expected_palette_padding:
                    raise ComposeError(
                        f"generated {palette_section.extension.decode('ascii')} "
                        "section lost its stock positional flag: "
                        f"{path.relative_path}"
                    )
                palette_reference_count += len(
                    validate_external_palette_closure(
                        tile_section,
                        palette_section,
                    )
                )
        cam_summaries.append(
            {
                "path": path.relative_path,
                "sections": [
                    {
                        "extension": section.display_extension,
                        "entries": len(section.entries),
                        "payload_entries": sum(
                            bool(entry.data) for entry in section.entries
                        ),
                    }
                    for section in archive.sections
                ],
            }
        )
    return cam_summaries, palette_reference_count


def validate_composed_package(root: Path) -> Mapping[str, object]:
    """Reparse every emitted resource and verify the generated load graph."""

    package = load_package(root)
    if len(package.datasets) != 1 or len(package.datasets[0].loads) != 1:
        raise ComposeError("generated package does not contain one Any/Load graph")
    load = package.datasets[0].loads[0]
    if package.datasets[0].base.casefold() != "any":
        raise ComposeError("generated package Dataset base is not Any")
    cam_summaries, palette_reference_count = _validate_generated_cam_outputs(
        load.cams
    )
    if len(load.descriptions) != 1:
        raise ComposeError("generated package does not contain one Description document")
    document = parse_descriptions(
        load.descriptions[0].absolute_path.read_bytes(),
        source=str(load.descriptions[0].absolute_path),
    )
    if len(load.gpl) != 1:
        raise ComposeError("generated package does not contain one GPL project")
    gpl_load = load.gpl[0]
    if gpl_load.target.absolute_path.stat().st_size == 0:
        raise ComposeError("generated GPL target is empty")
    parsed_sources = 0
    controlled_follower_marker_references: set[str] = set()
    for source in gpl_load.sources:
        text = _read_source_text(source.absolute_path)
        controlled_follower_marker_references.update(
            re.findall(r"\bMCF[0-9A-F]{12}[1-4]\b", text)
        )
        if source.absolute_path.suffix.casefold() == ".gpl":
            parsed_sources += len(parse_gpl(text, source.relative_path).items)
        elif source.absolute_path.suffix.casefold() == ".dat":
            parsed_sources += len(parse_dat(text, source.relative_path).items)
        else:
            raise ComposeError(f"generated GPL source has unsupported type: {source.relative_path}")
    _validate_generated_controlled_follower_marker_descriptions(
        document,
        controlled_follower_marker_references,
    )
    registry_path = root / Path(INTENT_REGISTRY_RELATIVE_PATH)
    if not registry_path.is_file():
        raise ComposeError(
            f"generated package has no private activity-text registry: {registry_path}"
        )
    try:
        private_activity_texts = decode_intent_registry(registry_path.read_bytes())
    except ValueError as exc:
        raise ComposeError(
            f"generated private activity-text registry is invalid: {exc}"
        ) from exc
    capability_manifest_path = root / Path(
        RUNTIME_CAPABILITY_MANIFEST_RELATIVE_PATH
    )
    if not capability_manifest_path.is_file():
        raise ComposeError(
            "generated package has no runtime capability manifest: "
            f"{capability_manifest_path}"
        )
    try:
        runtime_capabilities = decode_runtime_capability_manifest(
            capability_manifest_path.read_bytes()
        )
    except ValueError as exc:
        raise ComposeError(
            f"generated runtime capability manifest is invalid: {exc}"
        ) from exc
    runtime_feature_path = root / Path(RUNTIME_FEATURE_REGISTRY_RELATIVE_PATH)
    if not runtime_feature_path.is_file():
        raise ComposeError(
            "generated package has no runtime feature registry: "
            f"{runtime_feature_path}"
        )
    try:
        runtime_features = decode_runtime_feature_registry(
            runtime_feature_path.read_bytes()
        )
    except ValueError as exc:
        raise ComposeError(
            f"generated runtime feature registry is invalid: {exc}"
        ) from exc
    if package.definition is None or package.definition.schema_version != 2:
        raise ComposeError(
            "generated package must carry a schema-version 2 merge definition"
        )
    if package.definition.runtime_capabilities != runtime_capabilities:
        raise ComposeError(
            "generated package definition and runtime capability manifest disagree"
        )
    if legacy_runtime_features(runtime_capabilities) or (
        LEGACY_ALCHEMIST_CONTROLLER_CAPABILITY in runtime_capabilities
    ):
        raise ComposeError(
            "generated runtime capability manifest contains legacy package aliases"
        )
    has_private_activity_text = bool(private_activity_texts)
    has_private_activity_capability = (
        PRIVATE_ACTIVITY_TEXT_RUNTIME_CAPABILITY in runtime_capabilities
    )
    if has_private_activity_text != has_private_activity_capability:
        raise ComposeError(
            "generated private activity-text registry and runtime capability "
            "manifest disagree"
        )
    if bool(runtime_features.name_generators) != (
        NAME_GENERATOR_RUNTIME_CAPABILITY in runtime_capabilities
    ):
        raise ComposeError(
            "generated name-generator feature registry and generic MMCP hook "
            "selection disagree"
        )
    if bool(runtime_features.enchantment_rows) != (
        ENCHANTMENT_ROW_RUNTIME_CAPABILITY in runtime_capabilities
    ):
        raise ComposeError(
            "generated enchantment-row feature registry and generic MMCP hook "
            "selection disagree"
        )
    controller_path = root / CONTROLLER_REGISTRY_RELATIVE_PATH
    if not controller_path.is_file():
        raise ComposeError(
            f"generated package has no controller registry: {controller_path}"
        )
    try:
        controller_registry = decode_stock_controller_registry(
            controller_path.read_bytes()
        )
    except ControllerRegistryError as exc:
        raise ComposeError(
            f"generated controller registry is invalid: {exc}"
        ) from exc
    if bool(_controller_record_count(controller_registry)) != (
        STOCK_CONTROLLER_RUNTIME_CAPABILITY in runtime_capabilities
    ):
        raise ComposeError(
            "generated controller registry and generic MMCP hook selection disagree"
        )

    generated_inventory = inventory_package(SelectedMod("generated", package))
    _validate_generated_runtime_evidence(
        generated_inventory,
        runtime_features,
        controller_registry,
    )
    return {
        "status": "passed",
        "manifest": package.manifest_path.name,
        "cam_count": len(load.cams),
        "cams": cam_summaries,
        "description_count": len(document.records),
        "gpl_source_item_count": parsed_sources,
        "bcd_size": gpl_load.target.absolute_path.stat().st_size,
        "private_activity_text_count": len(private_activity_texts),
        "runtime_capability_count": len(runtime_capabilities),
        "runtime_name_generator_count": len(runtime_features.name_generators),
        "runtime_enchantment_row_count": len(runtime_features.enchantment_rows),
        "runtime_controller_record_count": _controller_record_count(
            controller_registry
        ),
        "controlled_follower_marker_count": len(
            controlled_follower_marker_references
        ),
        "resolved_external_palette_references": palette_reference_count,
    }


def _validate_generated_controlled_follower_marker_descriptions(
    document,
    referenced_markers: set[str],
) -> None:
    marker_descriptions: dict[str, ET.Element] = {}
    for record in document.records:
        element = record.to_element()
        name = element.get("Name", "")
        if re.fullmatch(r"MCF[0-9A-F]{12}[1-4]", name):
            if name in marker_descriptions:  # pragma: no cover - Description parser
                raise ComposeError(
                    f"generated controlled-follower marker {name!r} is duplicated"
                )
            marker_descriptions[name] = element
    if set(marker_descriptions) != referenced_markers:
        missing = sorted(referenced_markers - set(marker_descriptions))
        orphaned = sorted(set(marker_descriptions) - referenced_markers)
        details = []
        if missing:
            details.append("missing " + ", ".join(missing))
        if orphaned:
            details.append("unreferenced " + ", ".join(orphaned))
        raise ComposeError(
            "generated controlled-follower GPL and marker Descriptions disagree: "
            + "; ".join(details)
        )
    for name, element in marker_descriptions.items():
        info = [item.get("value") for item in element.findall("./Engine/Info")]
        image = element.find("./Engine/ImageIDBase")
        sound = element.find("./Engine/DefaultSound")
        dialog = element.find("./Game/DialogID")
        priority = element.find("./Game/StackPriority")
        if not (
            element.get("type") == "Unit"
            and element.get("subType") == "Overlay"
            and re.fullmatch(r"MF[A-Z0-9]{2}", element.get("ID", ""))
            and info == ["Directionless", "DontBlock", "NotVisibleInISOView"]
            and element.find("./Engine/Menu") is not None
            and element.find("./Engine/Menu").get("value") == "11"
            and image is not None
            and image.get("value") == "CRB2"
            and element.find("./Engine/Script") is None
            and sound is not None
            and sound.get("value") == "0"
            and dialog is not None
            and dialog.get("value") == "0"
            and priority is not None
            and priority.get("value") == "0"
        ):
            raise ComposeError(
                f"generated controlled-follower marker {name!r} does not "
                "preserve the recognized stock marker overlay shape"
            )


def _require_generated_dialog_pair(
    inventory: PackageInventory,
    dialog_id: bytes,
    label: str,
) -> None:
    for section in (b"SMNU", b"STRT"):
        count = sum(
            1
            for resource in inventory.resources
            if resource.section == section and resource.key == dialog_id
        )
        if count != 1:
            raise ComposeError(
                f"generated {label} requires exactly one "
                f"{section.decode('ascii')}/{_display_key(dialog_id)} resource; "
                f"found {count}"
            )


def _validate_generated_runtime_evidence(
    inventory: PackageInventory,
    runtime_features: RuntimeFeatureRegistry,
    controller_registry: ResolvedControllerRegistry,
) -> None:
    """Re-prove every emitted runtime record from generated CAM/XML/GPL data."""

    definition = inventory.selected.package.definition
    if definition is None:
        raise ComposeError("generated package has no merge definition")

    for feature in runtime_features.features:
        _require_runtime_feature_evidence(inventory, feature)
    _require_name_generator_declarations(
        inventory,
        runtime_features.name_generators,
    )

    building_dialogs: dict[bytes, str] = {}
    for building in definition.custom_buildings:
        if building.dialog_id is None:  # pragma: no cover - generated schema v2
            raise ComposeError(
                f"generated building {building.local_name!r} has no DialogID"
            )
        dialog_id = building.dialog_id.encode("ascii")
        if dialog_id in building_dialogs:
            raise ComposeError(
                f"generated building DialogID {_display_key(dialog_id)} is "
                "declared more than once"
            )
        _require_generated_dialog_pair(
            inventory,
            dialog_id,
            f"building {building.local_name!r}",
        )
        building_dialogs[dialog_id] = building.local_name

    descriptions: list[ET.Element] = []
    for path in inventory.descriptions:
        document = _parse_description_file(path)
        descriptions.extend(record.to_element() for record in document.records)

    gpl_functions: dict[str, int] = {}
    gpl_function_texts: dict[str, str] = {}
    for source in _parse_inventory_gpl_sources(inventory):
        for item in source.items:
            if item.kind is DefinitionKind.FUNCTION:
                key = item.name.casefold()
                gpl_functions[key] = gpl_functions.get(key, 0) + 1
                gpl_function_texts[key] = item.text

    for panel in controller_registry.panels:
        parent = panel.parent_dialog_id.to_bytes(4, "little")
        child = panel.child_dialog_id.to_bytes(4, "little")
        if parent not in building_dialogs:
            raise ComposeError(
                f"generated controller panel {panel.panel_key!r} parent "
                f"DialogID {_display_key(parent)} is not owned by exactly one "
                "generated building declaration"
            )
        if child in building_dialogs or child == parent:
            raise ComposeError(
                f"generated controller panel {panel.panel_key!r} child "
                "DialogID collides with a generated building"
            )
        _require_generated_dialog_pair(
            inventory,
            parent,
            f"controller parent {panel.panel_key!r}",
        )
        _require_generated_dialog_pair(
            inventory,
            child,
            f"controller panel {panel.panel_key!r}",
        )
        parent_text = _display_key(parent)
        family_records = [
            element
            for element in descriptions
            if element.get("subType") == "Building"
            and element.get("ID", "").startswith(panel.building_family_id)
        ]
        family_matches = [
            element
            for element in family_records
            if (element.find("./Game/DialogID") is not None)
            and element.find("./Game/DialogID").get("value") == parent_text
        ]
        if not family_records or len(family_matches) != len(family_records):
            raise ComposeError(
                f"generated controller panel {panel.panel_key!r} requires every "
                f"Building Description in family {panel.building_family_id!r} "
                f"to use parent DialogID {parent_text}; found "
                f"{len(family_matches)} of {len(family_records)}"
            )
        _validate_controller_panel_controls(
            controller_registry,
            panel.panel_key,
            _owned_smnu_payload(
                inventory,
                parent,
                f"generated controller parent {parent_text}",
            ),
            _owned_smnu_payload(
                inventory,
                child,
                f"generated controller panel {_display_key(child)}",
            ),
            owner="generated",
            parent_label=parent_text,
            child_label=_display_key(child),
        )

    for panel in (
        *controller_registry.reward_panels,
        *controller_registry.occupant_action_panels,
        *controller_registry.quest_boards,
    ):
        parent = panel.parent_dialog_id.to_bytes(4, "little")
        child = panel.child_dialog_id.to_bytes(4, "little")
        if parent not in building_dialogs or child in building_dialogs or child == parent:
            raise ComposeError(
                f"generated reward panel {panel.panel_key!r} has invalid parent/child ownership"
            )
        _require_generated_dialog_pair(
            inventory, child, f"reward panel {panel.panel_key!r}"
        )
        _validate_controller_panel_controls(
            controller_registry,
            panel.panel_key,
            _owned_smnu_payload(inventory, parent, "generated reward parent"),
            _owned_smnu_payload(inventory, child, "generated reward panel"),
            owner="generated",
            parent_label=_display_key(parent),
            child_label=_display_key(child),
            allow_manager_generated_refresh=True,
        )

    for panel in controller_registry.occupant_action_panels:
        for symbol in (panel.cost_callback_symbol, panel.action_callback_symbol):
            if gpl_functions.get(symbol.casefold(), 0) != 1:
                raise ComposeError(f"generated occupant callback {symbol!r} must exist exactly once")
            _require_occupant_callback_signature(
                gpl_function_texts[symbol.casefold()], symbol,
                symbol == panel.cost_callback_symbol,
            )
    for panel in controller_registry.quest_boards:
        callbacks = (
            (panel.list_source_callback_symbol, ("agent", "integer"), "agent"),
            (panel.revision_callback_symbol, ("agent",), "integer"),
            (panel.offer_name_callback_symbol, ("agent", "integer"), "string"),
            (panel.offer_goal_callback_symbol, ("agent", "integer"), "string"),
            (panel.offer_reward_callback_symbol, ("agent", "integer"), "integer"),
            (panel.selected_cost_callback_symbol, ("agent",), "integer"),
            (panel.selected_action_callback_symbol, ("agent",), "boolean"),
            (panel.refresh_cost_callback_symbol, ("agent",), "integer"),
            (panel.can_refresh_callback_symbol, ("agent",), "boolean"),
            (panel.refresh_callback_symbol, ("agent",), "boolean"),
        )
        for symbol, parameters, result_type in callbacks:
            if gpl_functions.get(symbol.casefold(), 0) != 1:
                raise ComposeError(
                    f"generated quest-board callback {symbol!r} must exist "
                    "exactly once"
                )
            _require_quest_board_callback_signature(
                gpl_function_texts[symbol.casefold()],
                symbol,
                parameters,
                result_type,
            )
    for toggle in controller_registry.building_open_toggles:
        parent = toggle.parent_dialog_id.to_bytes(4, "little")
        if parent not in building_dialogs:
            raise ComposeError(
                f"generated building toggle {toggle.toggle_key!r} parent is not "
                "owned by a generated building declaration"
            )
        _validate_mx22_toggle_controls(
            _owned_smnu_payload(inventory, parent, "generated toggle parent"),
            toggle,
            owner="generated",
            panel_label=_display_key(parent),
        )
    callbacks = (
        *controller_registry.timed_rage_actions,
        *controller_registry.rage_command_actions,
    )
    for action in callbacks:
        count = gpl_functions.get(action.callback_symbol.casefold(), 0)
        if count != 1:
            raise ComposeError(
                f"generated controller callback {action.callback_symbol!r} "
                f"requires exactly one generated GPL function; found {count}"
            )
    for action in controller_registry.sovereign_target_actions:
        matches = [
            element
            for element in descriptions
            if element.get("subType") == "Character"
            and element.get("ID") == action.private_unit_id
        ]
        if len(matches) != 1:
            raise ComposeError(
                f"generated controller private unit {action.private_unit_id!r} "
                f"requires exactly one Character Description; found {len(matches)}"
            )
    for action in controller_registry.hostile_monster_flags:
        matches = [
            element for element in descriptions
            if element.get("subType") == "Overlay"
            and element.get("ID") == action.private_flag_id
            and element.get("Name") == action.flag_prototype_name
        ]
        if len(matches) != 1:
            raise ComposeError(
                f"generated private reward flag {action.private_flag_id!r} "
                "does not resolve to its encoded Overlay prototype"
            )


def _generated_mod_id(
    selected_mods: Sequence[SelectedMod], profile_slug: str
) -> str:
    normalized_ids = []
    for selected in selected_mods:
        raw = selected.package.mod_id.strip().strip("{}")
        try:
            normalized_ids.append(str(uuid.UUID(raw)))
        except ValueError as exc:
            raise ComposeError(
                f"package Mod id is not a UUID: {selected.package.mod_id!r}"
            ) from exc
    # Generated profiles must not reuse a selected Workshop item's identity:
    # Majesty's active-mod registry is UUID-based, so a distinct stable ID is
    # required even for a one-mod profile while the subscribed item remains
    # installed but disabled.
    identity = "\n".join(("cam-manager-profile-v1", profile_slug, *normalized_ids))
    return "{" + str(uuid.uuid5(_PROFILE_NAMESPACE, identity)) + "}"


def _generated_definition(
    mod_id: str,
    internal_name: str,
    display_name: str,
    selected_mods: Sequence[SelectedMod],
    runtime_capabilities: Sequence[str],
    dialog_resolutions: Sequence[ResolvedBuildingDialog] | None = None,
) -> dict:
    if dialog_resolutions is None:
        if all(
            building.dialog_id is not None
            for selected in selected_mods
            for building in selected.package.definition.custom_buildings
        ):
            dialog_resolutions = tuple(
                ResolvedBuildingDialog(
                    owner=selected.alias,
                    local_name=building.local_name,
                    source_dialog_id=building.dialog_id.encode("ascii"),
                    resolved_dialog_id=building.dialog_id.encode("ascii"),
                )
                for selected in selected_mods
                for building in selected.package.definition.custom_buildings
            )
        else:
            inventories = tuple(inventory_package(selected) for selected in selected_mods)
            dialog_resolutions = resolve_building_dialogs(inventories)
    resolved_by_building = {
        (item.owner, item.local_name): item for item in dialog_resolutions
    }
    buildings = []
    for selected in selected_mods:
        definition = selected.package.definition
        assert definition is not None
        for building in definition.custom_buildings:
            resolution = resolved_by_building.get((selected.alias, building.local_name))
            if resolution is None:
                raise ComposeError(
                    f"{selected.alias}: no resolved dialog exists for "
                    f"{building.local_name!r}"
                )
            buildings.append(
                {
                    "local_name": _generated_building_local_name(
                        getattr(selected.package, "mod_id", definition.mod_id),
                        building.local_name,
                    ),
                    "dialog_id": resolution.resolved_dialog_id.decode("ascii"),
                    "controller_base": building.controller_base,
                    "panel_resource_template": building.panel_resource_template,
                }
            )
    payload = {
        "schema_version": 2,
        "mod_id": mod_id,
        "internal_name": internal_name,
        "display_name": display_name,
        "custom_buildings": buildings,
        "runtime_capabilities": list(runtime_capabilities),
    }
    # Reuse the public exact-schema validator before serializing the sidecar.
    parse_mod_definition(payload)
    return payload


def _generated_building_local_name(mod_id: str, raw_local_name: str) -> str:
    """Create a stable owner-qualified name for generated sidecar metadata."""

    owner = _normalized_mod_uuid(mod_id)
    digest = base64.b32encode(
        hashlib.sha256(raw_local_name.encode("utf-8")).digest()
    ).decode("ascii").rstrip("=").lower()[:26]
    return f"m{owner}.{digest}"


def _build_manifest(
    *,
    mod_id: str,
    internal_name: str,
    display_name: str,
    cam_filenames: Sequence[str],
    description_filename: str,
    source_set: GplProjectSourceSet,
    strings_filenames: Sequence[str] = (),
) -> bytes:
    root = ET.Element("Majesty")
    mod = ET.SubElement(root, "Mod", {"id": mod_id})
    ET.SubElement(mod, "Name").text = internal_name
    ET.SubElement(mod, "DisplayName", {"lang": "en_US"}).text = display_name
    description = ET.SubElement(mod, "Description", {"lang": "en_US"})
    ET.SubElement(description, "Short").text = "Generated CAM Manager profile."
    ET.SubElement(description, "Long").text = (
        "A validated, load-last profile generated from selected standalone CAM mods."
    )
    configuration = ET.SubElement(mod, "DataConfiguration")
    dataset = ET.SubElement(configuration, "Dataset", {"base": "Any"})
    load = ET.SubElement(dataset, "Load")
    for filename in cam_filenames:
        ET.SubElement(load, "CAM").text = f"Data\\{filename}"
    ET.SubElement(load, "Descriptions").text = (
        f"Data\\{description_filename}"
    )
    for strings_filename in strings_filenames:
        ET.SubElement(load, "Strings").text = f"Data\\{strings_filename}"
    gpl = ET.SubElement(load, "GPL")
    ET.SubElement(gpl, "Target").text = "Data\\Merged.bcd"
    if source_set.dat_filename is not None:
        ET.SubElement(gpl, "Source").text = (
            f"GPL\\{source_set.dat_filename}"
        )
    if source_set.gpl_filename is not None:
        ET.SubElement(gpl, "Source").text = (
            f"GPL\\{source_set.gpl_filename}"
        )
    ET.indent(root, space="\t")
    return ET.tostring(root, encoding="utf-8") + b"\n"


def _build_report(
    *,
    profile_slug: str,
    output_mod_id: str,
    selected_mods: Sequence[SelectedMod],
    game_path: Path,
    text_result: TextMergeResult,
    bdep_result: BdepComposeResult,
    art_results: Sequence[ArtDomainComposeResult],
    sound_selections: Sequence[NamedMergeSelection],
    descriptions: DescriptionMergeResult,
    description_stock_deltas: Sequence[DescriptionStockDelta],
    dialog_resolutions: Sequence[ResolvedBuildingDialog],
    gpl: GplComposeResult,
    compiled: CompiledGpl,
    runtime_capabilities: Sequence[str],
    runtime_feature_registry: RuntimeFeatureRegistry,
    controller_result: ControllerComposeResult,
    staging: Path,
    validation: Mapping[str, object],
) -> dict:
    stock_inputs = snapshot_stock_compose_inputs(game_path)
    selected_payload = []
    for selected in selected_mods:
        files = [
            {
                "path": relative_path.as_posix(),
                "size": path.stat().st_size,
                "sha256": _sha256(path),
            }
            for relative_path, path in _selected_report_files(selected)
        ]
        selected_payload.append(
            {
                "alias": selected.alias,
                "mod_id": selected.package.mod_id,
                "display_name": selected.package.display_name,
                "package_sha256": _aggregate_fingerprint(files),
                "files": files,
            }
        )
    stock_aitx = parse_strt(
        _require_cam_entry(
            game_path / Path("DataMX/mx_gpltext.cam"), b"STRT", b"AITX"
        ).data
    )
    return {
        "schema_version": 1,
        "profile_slug": profile_slug,
        "output_mod_id": output_mod_id,
        "selected_order": [selected.alias for selected in selected_mods],
        "inputs": selected_payload,
        "stock_ancestor": {
            "files": [
                {
                    "path": stock_input.relative_path.as_posix(),
                    "present": stock_input.present,
                    "size": stock_input.size,
                    "sha256": stock_input.sha256,
                }
                for stock_input in stock_inputs
            ],
            "stock_art_payloads_redistributed": True,
            "stock_palette_prefix_materialized_locally": True,
            "effective_whole_tables_include_stock_ancestor": True,
        },
        "runtime": {
            "outside_workshop_required": bool(runtime_capabilities),
            "capabilities": list(runtime_capabilities),
            "capability_manifest": {
                "path": RUNTIME_CAPABILITY_MANIFEST_RELATIVE_PATH,
                "sha256": _sha256(
                    staging / Path(RUNTIME_CAPABILITY_MANIFEST_RELATIVE_PATH)
                ),
                "record_count": len(runtime_capabilities),
            },
            "feature_registry": {
                "path": RUNTIME_FEATURE_REGISTRY_RELATIVE_PATH,
                "sha256": _sha256(
                    staging / Path(RUNTIME_FEATURE_REGISTRY_RELATIVE_PATH)
                ),
                "name_generator_count": len(
                    runtime_feature_registry.name_generators
                ),
                "enchantment_row_count": len(
                    runtime_feature_registry.enchantment_rows
                ),
            },
            "controller_registry": {
                "path": CONTROLLER_REGISTRY_RELATIVE_PATH.as_posix(),
                "sha256": _sha256(staging / CONTROLLER_REGISTRY_RELATIVE_PATH),
                "record_count": _controller_record_count(
                    controller_result.registry
                ),
            },
        },
        "merge": {
            "building_declarations": [
                {
                    "owner": selected.alias,
                    "mod_id": selected.package.mod_id,
                    "raw_local_name": building.local_name,
                    "generated_local_name": _generated_building_local_name(
                        selected.package.mod_id,
                        building.local_name,
                    ),
                    "source_dialog_id": resolution.source_dialog_id.decode(
                        "ascii"
                    ),
                    "resolved_dialog_id": resolution.resolved_dialog_id.decode(
                        "ascii"
                    ),
                }
                for selected in selected_mods
                for building in selected.package.definition.custom_buildings
                for resolution in dialog_resolutions
                if resolution.owner == selected.alias
                and resolution.local_name == building.local_name
            ],
            "controller_recipes": {
                "key_mappings": [
                    {
                        "owner": item.owner,
                        "mod_id": item.mod_id,
                        "kind": item.kind,
                        "raw_key": item.raw_key,
                        "qualified_key": item.qualified_key,
                    }
                    for item in controller_result.key_mappings
                ],
                "panels": [
                    {
                        "owner": item.owner,
                        "raw_panel_key": item.raw_panel_key,
                        "qualified_panel_key": item.qualified_panel_key,
                        "parent_building": item.raw_parent_building,
                        "parent_dialog_id": item.resolved_parent_dialog_id.decode(
                            "ascii"
                        ),
                        "source_dialog_id": item.source_dialog_id.decode("ascii"),
                        "child_dialog_id": item.resolved_child_dialog_id.decode(
                            "ascii"
                        ),
                    }
                    for item in controller_result.panels
                ],
                "building_open_toggles": [
                    {
                        "owner": item.owner,
                        "raw_toggle_key": item.raw_toggle_key,
                        "qualified_toggle_key": item.qualified_toggle_key,
                        "parent_building": item.raw_parent_building,
                        "parent_dialog_id": item.resolved_parent_dialog_id.decode(
                            "ascii"
                        ),
                    }
                    for item in controller_result.toggles
                ],
            },
            "private_activity_text": {
                "registry_path": INTENT_REGISTRY_RELATIVE_PATH,
                "registry_sha256": _sha256(
                    staging / Path(INTENT_REGISTRY_RELATIVE_PATH)
                ),
                "records": [
                    {
                        "owner": record.binding.owner,
                        "source_mod_id": record.binding.source_mod_id,
                        "source_index": record.binding.source_index,
                        "source_expressions": list(record.binding.expressions),
                        "package_defined_source_expressions": list(
                            record.binding.package_expressions
                        ),
                        "generated_expression": record.binding.generated_expression,
                        "runtime_id": record.binding.runtime_id,
                        "text": record.text.decode("cp1252"),
                        "rewrite_scope": "owner_resolver_argument_two_only",
                        "row_origin": (
                            "existing_stock_placeholder"
                            if record.binding.source_index < len(stock_aitx.records)
                            else "appended"
                        ),
                    }
                    for record in text_result.private_activity_texts
                ],
            },
            "dialog_renames": [
                {
                    "owner": owner,
                    "from": old.decode("ascii"),
                    "to": new.decode("ascii"),
                }
                for owner, old, new in text_result.dialog_renames
            ],
            "whole_strt": [
                {
                    "key": selection.key.decode("ascii"),
                    "deltas": [
                        {"owner": delta.owner, "change_count": len(delta.changes)}
                        for delta in selection.deltas
                    ],
                }
                for selection in text_result.whole_tables
            ],
            "bdep": [
                {
                    "owner": delta.owner,
                    "rows": [row.building_id for row in delta.rows],
                }
                for delta in bdep_result.deltas
            ],
            "descriptions": {
                "record_count": len(descriptions.document.records),
                "deltas": [
                    {"owner": delta.owner, "record_count": len(delta.records)}
                    for delta in descriptions.deltas
                ],
                "stock_classification": {
                    kind: sum(
                        delta.kind == kind for delta in description_stock_deltas
                    )
                    for kind in ("addition", "stock_override", "identical_stock")
                },
                "stock_overrides": [
                    {
                        "owner": delta.owner,
                        "type": delta.key[0],
                        "id": delta.key[1],
                        "mod_source": delta.mod_source,
                        "stock_source": delta.stock_source,
                    }
                    for delta in description_stock_deltas
                    if delta.kind == "stock_override"
                ],
            },
            "named_audio": [
                {
                    "section": selection.section.decode("ascii"),
                    "key": _display_key(selection.key),
                    "owners": list(selection.owners),
                }
                for selection in sound_selections
            ],
            "gpl": {
                "conflicts": [
                    {
                        "kind": conflict.key[0].value,
                        "name": conflict.name,
                        "owners": [variant.side_name for variant in conflict.variants],
                    }
                    for conflict in gpl.conflicts
                ],
                "resolutions": [
                    {"kind": kind.value, "name": name, "owner": owner}
                    for kind, name, owner in gpl.resolution_owners
                ],
                "explicit_resolutions": [
                    {
                        "kind": kind.value,
                        "name": name,
                        "source": source,
                    }
                    for kind, name, source in gpl.resolution_sources
                ],
                "inventory_death_drop_exclusions": list(
                    gpl.inventory_death_drop_exclusions
                ),
                "purchase_equipment_tail_callbacks": [
                    {
                        "source_mod_id": mod_id,
                        "callback_key": callback_key,
                        "callback_symbol": callback_symbol,
                    }
                    for mod_id, callback_key, callback_symbol in (
                        gpl.purchase_equipment_tail_callbacks
                    )
                ],
                "purchase_bazaar_tail_callbacks": [
                    {
                        "source_mod_id": mod_id,
                        "callback_key": callback_key,
                        "callback_symbol": callback_symbol,
                    }
                    for mod_id, callback_key, callback_symbol in (
                        gpl.purchase_bazaar_tail_callbacks
                    )
                ],
                "controlled_follower_speed_sync": [
                    {
                        "source_mod_id": mod_id,
                        "feature_key": feature_key,
                        "eligibility_callback_symbol": callback_symbol,
                        "movement_rate_modifier_per_tier": modifier,
                        "marker_effectors": list(markers),
                    }
                    for mod_id, feature_key, callback_symbol, modifier, markers in (
                        gpl.controlled_follower_speed_sync
                    )
                ],
                "hero_quest_lifecycles": [
                    {
                        "source_mod_id": mod_id,
                        "feature_key": feature_key,
                        "hero_scripts": list(hero_scripts),
                        "decision_callback_symbol": decision,
                        "reset_callback_symbol": reset,
                        "death_callback_symbol": death,
                    }
                    for mod_id, feature_key, hero_scripts, decision, reset, death in (
                        gpl.hero_quest_lifecycles
                    )
                ],
                "compiled_bcd_size": compiled.size,
            },
            "art": {
                result.domain: _art_report_payload(result)
                for result in art_results
            },
        },
        "validation": dict(validation),
        "outputs": [
            {
                "path": path.relative_to(staging).as_posix(),
                "size": path.stat().st_size,
                "sha256": _sha256(path),
            }
            for path in sorted(staging.rglob("*"))
            if path.is_file() and path.name != "CAM-MERGE-REPORT.json"
        ],
    }


def _selected_report_files(selected: SelectedMod) -> tuple[tuple[Path, Path], ...]:
    """Return stable ``(relative, absolute)`` report inputs for one selection."""

    root = selected.package.root.resolve()
    if selected.report_files is None:
        candidates = tuple(path for path in root.rglob("*") if path.is_file())
    else:
        candidates = tuple(selected.report_files)

    exact: dict[Path, Path] = {}
    for raw_path in candidates:
        path = raw_path if raw_path.is_absolute() else root / raw_path
        resolved = path.resolve()
        try:
            relative = resolved.relative_to(root)
        except ValueError as exc:
            raise ComposeError(
                f"{selected.alias}: report input escapes package root: {raw_path}"
            ) from exc
        if not resolved.is_file():
            raise ComposeError(
                f"{selected.alias}: report input is not a file: {raw_path}"
            )
        exact.setdefault(relative, resolved)
    return tuple(
        sorted(
            exact.items(),
            key=lambda item: (item[0].as_posix().casefold(), item[0].as_posix()),
        )
    )


def _art_report_payload(result: ArtDomainComposeResult) -> dict:
    return {
        "retained_tile_dependencies": [
            {
                "owner": analysis.mod_id,
                "count": len(analysis.retained_tile_dependencies),
                "slots": list(analysis.retained_tile_dependencies),
            }
            for analysis in result.analyses
        ],
        "retained_palette_dependencies": [
            {
                "owner": analysis.mod_id,
                "count": len(analysis.retained_palette_dependencies),
                "slots": list(analysis.retained_palette_dependencies),
            }
            for analysis in result.analyses
        ],
        "tile_collision_count": len(result.tile_collisions),
        "tile_collisions": [
            {
                "index": collision.index,
                "owners": list(collision.mods),
                "identical": collision.identical_payload,
            }
            for collision in result.tile_collisions
        ],
        "tile_final_count": result.report.tile_allocation.final_count,
        "tile_allocations": [
            {
                "owner": allocation.mod_id,
                "start": allocation.start,
                "stop": allocation.stop,
                "relocation_count": len(allocation.relocations),
            }
            for allocation in result.report.tile_allocation.ranges
        ],
        "palette_collision_count": len(result.palette_collisions),
        "palette_final_count": (
            result.report.palette_allocation.final_count
            if result.report.palette_allocation is not None
            else None
        ),
        "imag_rewrites": [
            {
                "owner": owner,
                "rewrite_count": len(report.rewrites),
                "rewritten_slots": list(report.rewritten_slots),
                "supported_layouts": list(report.supported_layouts),
            }
            for owner, report in result.report.imag_reports
        ],
    }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _aggregate_fingerprint(files: Sequence[Mapping[str, object]]) -> str:
    digest = hashlib.sha256()
    for item in files:
        digest.update(str(item["path"]).encode("utf-8"))
        digest.update(b"\x00")
        digest.update(str(item["sha256"]).encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()


def resolve_building_dialogs(
    inventories: Sequence[PackageInventory],
    *,
    reserved_dialog_ids: Sequence[bytes] = (),
) -> tuple[ResolvedBuildingDialog, ...]:
    """Resolve legacy explicit IDs and allocate v3 building IDs deterministically.

    V3 authors declare a semantic building name and stock controller only. The
    source FourCC is proved from every matching Building Description and the
    manager assigns the first collision-free ``CGxx`` ID in stable package-ID /
    local-name order. Reordering the same selected set therefore cannot change
    its allocation; changing the selected set produces a newly resolved profile.
    """

    resources = tuple(resource for inventory in inventories for resource in inventory.resources)
    claimed_targets: dict[bytes, str] = {}
    reserved_target_owners: dict[bytes, set[str]] = {}
    for resource in resources:
        if re.fullmatch(rb"CG[A-Z0-9]{2}", resource.key):
            reserved_target_owners.setdefault(resource.key, set()).add(resource.owner)
    for inventory in inventories:
        for dialog_id in getattr(inventory.selected, "reserved_dialog_ids", ()):
            if re.fullmatch(rb"CG[A-Z0-9]{2}", dialog_id):
                reserved_target_owners.setdefault(dialog_id, set()).add(
                    inventory.selected.alias
                )
    for dialog_id in reserved_dialog_ids:
        if re.fullmatch(rb"CG[A-Z0-9]{2}", dialog_id):
            reserved_target_owners.setdefault(dialog_id, set()).add(
                "selected native Standard content"
            )
    reserved_targets = set(reserved_target_owners)
    pending_v3: list[tuple[str, str, str, bytes]] = []
    resolved: list[ResolvedBuildingDialog] = []

    for inventory in inventories:
        selected = inventory.selected
        definition = selected.package.definition
        if definition is None:
            raise ComposeError(f"{selected.alias}: a v1 mod definition is required")
        owner_dialog_keys = {
            resource.key
            for resource in resources
            if resource.owner == selected.alias
            and resource.section in (b"SMNU", b"STRT")
        }
        for building in definition.custom_buildings:
            if definition.schema_version == 3:
                sources = _description_dialog_sources(inventory, building.local_name)
                if not sources:
                    raise ComposeError(
                        f"{selected.alias}: declared building {building.local_name!r} "
                        "did not match any XML Building Description"
                    )
                if len(sources) != 1:
                    rendered = ", ".join(repr(value) for value in sorted(sources))
                    raise ComposeError(
                        f"{selected.alias}: building {building.local_name!r} uses "
                        f"multiple source DialogIDs: {rendered}"
                    )
                source_text = next(iter(sources))
                try:
                    source = source_text.encode("ascii")
                except UnicodeEncodeError as exc:
                    raise ComposeError(
                        f"{selected.alias}: inferred DialogID {source_text!r} is not ASCII"
                    ) from exc
                if len(source) != 4:
                    raise ComposeError(
                        f"{selected.alias}: inferred DialogID {source_text!r} is not a FourCC"
                    )
                for section in (b"SMNU", b"STRT"):
                    matches = [
                        resource
                        for resource in resources
                        if resource.owner == selected.alias
                        and resource.section == section
                        and resource.key == source
                    ]
                    if len(matches) != 1:
                        raise ComposeError(
                            f"{selected.alias}: inferred DialogID "
                            f"{_display_key(source)} requires exactly one "
                            f"package-owned {section.decode('ascii')} panel "
                            f"resource; found {len(matches)}"
                        )
                pending_v3.append(
                    (
                        selected.package.mod_id.strip().strip("{}").casefold(),
                        selected.alias,
                        building.local_name,
                        source,
                    )
                )
                continue

            assert building.dialog_id is not None
            try:
                target = building.dialog_id.encode("ascii")
                controller = building.controller_base.encode("ascii")
            except UnicodeEncodeError as exc:
                raise ComposeError(
                    f"{selected.alias}: dialog IDs must be ASCII"
                ) from exc
            if len(target) != 4 or len(controller) != 4:
                raise ComposeError(
                    f"{selected.alias}: dialog_id and controller_base must be FourCCs"
                )
            other_reservation_owners = reserved_target_owners.get(target, set()).difference(
                (selected.alias,)
            )
            if other_reservation_owners:
                raise ComposeError(
                    f"{selected.alias}: fixed dialog ID {_display_key(target)} is "
                    "already used by selected content from "
                    + ", ".join(sorted(other_reservation_owners))
                )
            previous = claimed_targets.get(target)
            if previous is not None and previous != selected.alias:
                raise ComposeError(
                    f"dialog ID {_display_key(target)} is declared by both "
                    f"{previous} and {selected.alias}"
                )
            claimed_targets[target] = selected.alias
            source = target if target in owner_dialog_keys else controller
            if source not in owner_dialog_keys:
                raise ComposeError(
                    f"{selected.alias}: neither declared dialog_id "
                    f"{_display_key(target)} nor controller_base "
                    f"{_display_key(controller)} exists in its panel resources"
                )
            resolved.append(
                ResolvedBuildingDialog(
                    owner=selected.alias,
                    local_name=building.local_name,
                    source_dialog_id=source,
                    resolved_dialog_id=target,
                )
            )

    source_owners: dict[tuple[str, bytes], str] = {}
    for _mod_id, owner, local_name, source in pending_v3:
        prior = source_owners.get((owner, source))
        if prior is not None:
            raise ComposeError(
                f"{owner}: buildings {prior!r} and {local_name!r} share source "
                f"DialogID {_display_key(source)}; each declared building needs "
                "its own panel resource"
            )
        source_owners[(owner, source)] = local_name

    unavailable = set(reserved_targets) | set(claimed_targets)
    available = (
        f"CG{left}{right}".encode("ascii")
        for left in "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        for right in "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    )
    free = (candidate for candidate in available if candidate not in unavailable)
    for _mod_id, owner, local_name, source in sorted(
        pending_v3,
        key=lambda item: (item[0], item[2].casefold(), item[1]),
    ):
        try:
            target = next(free)
        except StopIteration as exc:
            raise ComposeError("no manager-owned CGxx building DialogIDs remain") from exc
        unavailable.add(target)
        resolved.append(
            ResolvedBuildingDialog(
                owner=owner,
                local_name=local_name,
                source_dialog_id=source,
                resolved_dialog_id=target,
            )
        )

    return tuple(resolved)


def _description_dialog_sources(
    inventory: PackageInventory, local_name: str
) -> set[str]:
    sources: set[str] = set()
    for path in inventory.descriptions:
        document = _parse_description_file(path)
        for record in document.records:
            element = record.to_element()
            if element.get("subType") != "Building":
                continue
            if not _is_building_name(element.get("Name", ""), local_name):
                continue
            dialog = element.find("./Game/DialogID")
            if dialog is None or not dialog.get("value"):
                raise ComposeError(
                    f"{inventory.selected.alias} {record.key!r} has no Game/DialogID "
                    f"for declared building {local_name!r}"
                )
            sources.add(dialog.get("value"))
    return sources


def _dialog_renames(
    inventories: Sequence[PackageInventory],
    resources: Sequence[CamResource],
    *,
    resolutions: Sequence[ResolvedBuildingDialog] | None = None,
    controller_panels: Sequence[ResolvedControllerPanel] = (),
) -> tuple[tuple[str, bytes, bytes], ...]:
    del resources  # Resource ownership is proved by resolve_building_dialogs().
    effective = (
        tuple(resolutions)
        if resolutions is not None
        else resolve_building_dialogs(inventories)
    )
    building_renames = tuple(
        (item.owner, item.source_dialog_id, item.resolved_dialog_id)
        for item in effective
        if item.source_dialog_id != item.resolved_dialog_id
    )
    panel_renames = tuple(
        (item.owner, item.source_dialog_id, item.resolved_child_dialog_id)
        for item in controller_panels
        if item.source_dialog_id != item.resolved_child_dialog_id
    )
    return (*building_renames, *panel_renames)


def _select_later_conflict_runs(
    deltas: Mapping[str, PositionalSectionDelta],
    collisions: Sequence[PositionalCollision],
    owner_order: Mapping[str, int],
    *,
    protected_indices: Mapping[str, Iterable[int]] | None = None,
) -> dict[str, set[int]]:
    selected = {owner: set() for owner in deltas}
    changed = {
        owner: set(delta.changed_indices) for owner, delta in deltas.items()
    }
    protected_by_owner = {
        owner: frozenset(indices)
        for owner, indices in (protected_indices or {}).items()
    }
    for owner, indices in changed.items():
        for index in sorted(indices.intersection(protected_by_owner.get(owner, ()))):
            selected[owner].update(_contiguous_component(indices, index))
    for collision in collisions:
        if collision.identical_payload:
            continue
        owners = [
            owner
            for owner in sorted(collision.mods, key=lambda owner: owner_order[owner])
            if collision.index not in selected[owner]
        ]
        for owner in owners[1:]:
            selected[owner].update(
                _contiguous_component(changed[owner], collision.index)
            )
    return selected


def _contiguous_component(indices: set[int], member: int) -> set[int]:
    if member not in indices:
        raise ComposeError(f"positional conflict {member} is not a changed slot")
    start = member
    stop = member
    while start - 1 in indices:
        start -= 1
    while stop + 1 in indices:
        stop += 1
    return set(range(start, stop + 1))


def _first_free_after_reserved(
    deltas: Mapping[str, PositionalSectionDelta],
    selected: Mapping[str, set[int]],
) -> int:
    stock_counts = {delta.stock_count for delta in deltas.values()}
    if len(stock_counts) != 1:
        raise ComposeError("positional deltas disagree on their stock count")
    stock_count = next(iter(stock_counts))
    reserved = {
        index
        for owner, delta in deltas.items()
        for index in delta.changed_indices
        if index not in selected.get(owner, set()) and index >= stock_count
    }
    return max(reserved) + 1 if reserved else stock_count


def _require_section(archive: CamArchive, extension: bytes) -> CamSection:
    matches = [
        section for section in archive.sections if section.extension == extension
    ]
    if len(matches) != 1:
        raise ComposeError(
            f"expected exactly one {extension!r} section; found {len(matches)}"
        )
    return matches[0]


def _blank_positional_section(
    stock: CamSection, final_count: int
) -> list[CamEntry]:
    if final_count < len(stock.entries):
        raise ComposeError(
            f"generated {stock.extension!r} count {final_count} is below stock "
            f"count {len(stock.entries)}"
        )
    result = []
    for index in range(final_count):
        name = (
            stock.entries[index].name
            if index < len(stock.entries)
            else struct.pack("<I", index).ljust(20, b"\x00")
        )
        result.append(CamEntry(name=name, data=b""))
    return result


def _materialize_effective_stock_prefix(
    entries: list[CamEntry], stock: CamSection
) -> None:
    """Fill unresolved positional slots from the immutable stock ancestor.

    This is intentionally used for SPLT, whose effective prefix is shipped by
    both completed source mods.  Mod replacements are placed first and remain
    authoritative; only still-empty stock-range records are materialized.
    """

    if len(entries) < len(stock.entries):
        raise ComposeError(
            f"generated {stock.extension!r} count {len(entries)} is below stock "
            f"count {len(stock.entries)}"
        )
    for index, stock_entry in enumerate(stock.entries):
        if entries[index].data:
            continue
        entries[index] = CamEntry(
            name=entries[index].name,
            data=stock_entry.data,
        )


def _place_positional(
    entries: list[CamEntry],
    destination: int,
    source: CamEntry,
    owner: str,
    extension: bytes,
) -> None:
    if destination < 0 or destination >= len(entries):
        raise ComposeError(
            f"{owner}: {extension!r} destination {destination} is outside "
            f"generated count {len(entries)}"
        )
    existing = entries[destination]
    if existing.data:
        if existing.data == source.data:
            return
        raise ComposeError(
            f"{owner}: unresolved {extension.decode('ascii')} placement "
            f"collision at {destination}"
        )
    name = struct.pack("<I", destination) + source.name[4:]
    entries[destination] = CamEntry(name=name, data=source.data)


def _require_cam_entry(path: Path, section: bytes, key: bytes) -> CamEntry:
    archive = read_cam(path)
    matches = [
        entry
        for current_section in archive.sections
        if current_section.extension == section
        for entry in current_section.entries
        if entry.name[:4] == key
    ]
    if len(matches) != 1:
        raise ComposeError(
            f"expected exactly one {section!r}/{key!r} in {path}; found {len(matches)}"
        )
    return matches[0]


def _parse_description_file(path: Path) -> DescriptionsDocument:
    info = path.stat()
    return _parse_description_file_cached(
        str(path),
        info.st_size,
        info.st_mtime_ns,
    )


@lru_cache(maxsize=1024)
def _parse_description_file_cached(
    path_text: str,
    _size: int,
    _mtime_ns: int,
) -> DescriptionsDocument:
    path = Path(path_text)
    return parse_descriptions(path.read_bytes(), source=path_text)


def _parse_semantic_source_file(path: Path) -> ParsedSemanticSource:
    info = path.stat()
    return _parse_semantic_source_file_cached(
        str(path),
        info.st_size,
        info.st_mtime_ns,
    )


@lru_cache(maxsize=1024)
def _parse_semantic_source_file_cached(
    path_text: str,
    _size: int,
    _mtime_ns: int,
) -> ParsedSemanticSource:
    path = Path(path_text)
    text = _read_source_text(path)
    if path.suffix.casefold() == ".gpl":
        return parse_gpl(text, path_text)
    if path.suffix.casefold() == ".dat":
        return parse_dat(text, path_text)
    raise ComposeError(f"unsupported semantic source extension: {path}")


def _read_source_text(path: Path) -> str:
    data = path.read_bytes()
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ComposeError(f"GPL source is not UTF-8 or Windows-1252: {path}")


def _is_building_name(actual: str, declared: str) -> bool:
    if actual == declared:
        return True
    suffix = actual[len(declared) :] if actual.startswith(declared) else ""
    return bool(suffix) and suffix.isdigit()


def _display_key(key: bytes) -> str:
    return key.decode("ascii", errors="backslashreplace")


__all__ = [
    "ArtDomainComposeResult",
    "BdepComposeResult",
    "CamResource",
    "CompiledGpl",
    "ComposeError",
    "ComposePackageResult",
    "ControllerComposeResult",
    "ControllerKeyMapping",
    "DescriptionStockDelta",
    "GplComposeResult",
    "NamedMergeSelection",
    "PackageInventory",
    "ResolvedBuildingDialog",
    "ResolvedControllerPanel",
    "ResolvedControllerToggle",
    "SelectedMod",
    "ScopedSemanticResolution",
    "ScopedNamedResourceResolution",
    "ScopedArtResourceResolution",
    "StockComposeInput",
    "StrtMergeSelection",
    "TextMergeResult",
    "compile_gpl",
    "compose_package",
    "analyze_description_stock_deltas",
    "discover_private_activity_texts",
    "discover_selected_private_activity_texts",
    "inventory_package",
    "collapse_native_cam_resources",
    "merge_bdep_resource",
    "merge_art_resources",
    "merge_description_resources",
    "merge_gpl_resources",
    "merge_named_resources",
    "merge_sound_resources",
    "merge_text_resources",
    "resolve_building_dialogs",
    "resolve_controller_registry",
    "resolve_runtime_feature_registry",
    "snapshot_stock_compose_inputs",
    "validate_controller_stock_evidence",
    "validate_gpl_feature_evidence",
    "validate_composed_package",
]
