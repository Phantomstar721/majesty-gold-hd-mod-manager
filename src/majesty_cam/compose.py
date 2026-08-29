from __future__ import annotations

from dataclasses import dataclass
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
    ArtRelocationReport,
    ImagRelocationReport,
    PaletteRelocationReport,
    PositionalAllocationReport,
    PositionalCollision,
    PositionalSectionDelta,
    allocate_collision_free_ranges,
    analyze_art_archive,
    find_positional_collisions,
    rewrite_imag_entries,
    rewrite_tile_palette_indices,
    validate_external_palette_closure,
)
from .cam import CamArchive, CamEntry, CamSection, pad_name, read_cam
from .descriptions import (
    DescriptionFormatError,
    DescriptionKey,
    DescriptionMergeResult,
    merge_descriptions,
    parse_descriptions,
)
from .gpl import (
    DefinitionKind,
    GplProjectSourceSet,
    ParsedSemanticSource,
    SemanticConflict,
    SemanticItem,
    add_inventory_death_drop_exclusions,
    merge_sources,
    parse_dat,
    parse_gpl,
    require_complete_semantic_coverage,
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
    load_package,
    parse_mod_definition,
)
from .runtime_capabilities import (
    PRIVATE_ACTIVITY_TEXT_RUNTIME_CAPABILITY,
    RUNTIME_CAPABILITY_MANIFEST_RELATIVE_PATH,
    decode_runtime_capability_manifest,
    encode_runtime_capability_manifest,
)
from .strt import StrtDelta, StrtRecord, StrtTable, merge_strt, parse_strt, strt_delta
from .tables import BdepDelta, merge_bdep


class ComposeError(ValueError):
    """Raised when selected packages cannot be composed without guessing."""


@dataclass(frozen=True)
class StockComposeInput:
    """One exact installed-stock file consumed by package composition."""

    relative_path: Path
    size: int
    sha256: str


_STOCK_COMPOSE_FIXED_INPUTS = (
    Path("Data/textdata.cam"),
    Path("Data/maindata.cam"),
    Path("Data/interfacedata.cam"),
    Path("DataMX/mx_gpltext.cam"),
    Path("DataMX/mx_miscdata.cam"),
    Path("SDK/Gplbcc.exe"),
    Path("SDK/OriginalQuests/GPLMx/mx_defines.gpl"),
)
_STOCK_COMPOSE_XML_DIRECTORIES = (
    Path("SDK/OriginalQuests/Data"),
    Path("SDK/OriginalQuests/DataMX"),
)


@dataclass(frozen=True)
class SelectedMod:
    alias: str
    package: ModPackage


@dataclass(frozen=True)
class ScopedSemanticResolution:
    """One explicit semantic result and the mod owners it is allowed to cover."""

    item: SemanticItem
    participant_owners: frozenset[str]

    def __post_init__(self) -> None:
        if not self.participant_owners:
            raise ValueError("semantic resolution participants cannot be empty")


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
class PackageInventory:
    selected: SelectedMod
    cams: tuple[Path, ...]
    descriptions: tuple[Path, ...]
    gpl_loads: tuple[GplLoad, ...]
    resources: tuple[CamResource, ...]


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
    (b"SMNU", b"STRT", b"DATA", b"IMAG", b"TILE", b"SPLT", b"DSND", b"WAVE")
)
_NAMED_SECTIONS = frozenset((b"SMNU", b"STRT", b"IMAG", b"DSND", b"WAVE"))
_WHOLE_STRT = {
    b"UNTN": (Path("Data/textdata.cam"), "id"),
    b"ACTN": (Path("Data/textdata.cam"), "id"),
    b"QITM": (Path("DataMX/mx_gpltext.cam"), "index"),
    b"AITX": (Path("DataMX/mx_gpltext.cam"), "index"),
    # Help text is addressed by its embedded FourCC ID (for example hAL0 and
    # hPH0), not by the physical append slot used by an individual builder.
    b"HPTX": (Path("DataMX/mx_gpltext.cam"), "id"),
}
_TEXT_WHOLE_ORDER = (b"UNTN", b"ACTN")
_GPLTEXT_WHOLE_ORDER = (b"QITM", b"AITX", b"HPTX")


def inventory_package(selected: SelectedMod) -> PackageInventory:
    """Read one safe package into an ordered, fail-closed resource inventory."""

    if not selected.alias or selected.alias.casefold() != selected.alias:
        raise ComposeError(
            f"mod alias must be non-empty lowercase text: {selected.alias!r}"
        )

    cam_paths: list[Path] = []
    description_paths: list[Path] = []
    gpl_loads: list[GplLoad] = []
    resources: list[CamResource] = []

    for dataset_index, dataset in enumerate(selected.package.datasets):
        if dataset.base.casefold() != "any":
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
                    for section_order, section in enumerate(archive.sections):
                        if section.extension not in _SUPPORTED_CAM_SECTIONS:
                            raise ComposeError(
                                f"{selected.alias}: unsupported CAM section "
                                f"{section.extension!r} in {source}"
                            )
                        for entry_order, entry in enumerate(section.entries):
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
                else:  # pragma: no cover - package parser owns this closed union
                    raise ComposeError(
                        f"{selected.alias}: unsupported manifest directive "
                        f"{type(directive).__name__}"
                    )

    if not cam_paths:
        raise ComposeError(f"{selected.alias}: package has no CAM resources")
    if not gpl_loads:
        raise ComposeError(f"{selected.alias}: package has no GPL load")
    return PackageInventory(
        selected=selected,
        cams=tuple(cam_paths),
        descriptions=tuple(description_paths),
        gpl_loads=tuple(gpl_loads),
        resources=tuple(resources),
    )


def merge_named_resources(
    resources: Iterable[CamResource],
    section: bytes,
    *,
    renames: Mapping[tuple[str, bytes], bytes] | None = None,
) -> tuple[tuple[CamEntry, ...], tuple[NamedMergeSelection, ...]]:
    """Union a named CAM registry using its native four-byte resource key."""

    if section not in _NAMED_SECTIONS:
        raise ComposeError(f"section {section!r} is not a supported named registry")
    rename_map = dict(renames or {})
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
    return entries, selections


def merge_text_resources(
    game_path: Path,
    inventories: Sequence[PackageInventory],
    *,
    private_activity_texts: Sequence[PrivateActivityTextBinding] | None = None,
) -> TextMergeResult:
    """Merge Majesty's known whole STRT tables and all private panel/name tables."""

    resources = tuple(resource for inv in inventories for resource in inv.resources)
    dialog_renames = _dialog_renames(inventories, resources)
    rename_map = {(owner, old): new for owner, old, new in dialog_renames}

    whole: dict[bytes, StrtMergeSelection] = {}
    whole_resource_ids: set[int] = set()
    detached_activity_texts: tuple[PrivateActivityTextRecord, ...] = ()
    for key, (stock_relative, key_mode) in _WHOLE_STRT.items():
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
        stock_entry = _require_cam_entry(game_path / stock_relative, b"STRT", key)
        stock_table = parse_strt(stock_entry.data)
        parsed_variants = tuple(
            (resource.owner, parse_strt(resource.entry.data)) for resource in variants
        )
        if key == b"AITX" and private_activity_texts is not None:
            parsed_variants, detached_activity_texts = _detach_private_activity_texts(
                stock_table,
                parsed_variants,
                private_activity_texts,
            )
        merged, deltas = merge_strt(
            stock_table,
            parsed_variants,
            key_mode=key_mode,
        )
        whole[key] = StrtMergeSelection(
            key=key,
            entry=CamEntry(name=variants[0].entry.name, data=merged.to_bytes()),
            deltas=deltas,
        )
        whole_resource_ids.update(id(resource) for resource in variants)

    if private_activity_texts and b"AITX" not in whole:
        raise ComposeError(
            "private activity-text bindings exist but no selected mod provides AITX"
        )

    private_strt_resources = tuple(
        resource
        for resource in resources
        if resource.section == b"STRT" and id(resource) not in whole_resource_ids
    )
    smnu_entries, smnu_selections = merge_named_resources(
        resources, b"SMNU", renames=rename_map
    )
    private_strt_entries, private_strt_selections = merge_named_resources(
        private_strt_resources, b"STRT", renames=rename_map
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

    stock_entry = _require_cam_entry(
        game_path / _WHOLE_STRT[b"AITX"][0], b"STRT", b"AITX"
    )
    stock = parse_strt(stock_entry.data)
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
        _require_complete_aitx_provider(owner, stock, table)
        delta = strt_delta(stock, table, owner=owner, key_mode="index")
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
                stock_rows=tuple(
                    (
                        source_index,
                        stock.records[source_index].text
                        if source_index < len(stock.records)
                        else b"",
                    )
                    for source_index, _record in delta.changes
                ),
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
    return parse_gpl(_read_source_text(path), str(path))


def _detach_private_activity_texts(
    stock: StrtTable,
    variants: Sequence[tuple[str, StrtTable]],
    bindings: Sequence[PrivateActivityTextBinding],
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

    sanitized: list[tuple[str, StrtTable]] = []
    detached: list[PrivateActivityTextRecord] = []
    for owner, table in variants:
        _require_complete_aitx_provider(owner, stock, table)
        delta = strt_delta(stock, table, owner=owner, key_mode="index")
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

        records = list(table.records)
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
    game_path: Path, inventories: Sequence[PackageInventory]
) -> BdepComposeResult:
    resources = [
        resource
        for inventory in inventories
        for resource in inventory.resources
        if resource.section == b"DATA"
    ]
    unsupported = [resource for resource in resources if resource.key != b"BDEP"]
    if unsupported:
        labels = ", ".join(
            f"{resource.owner}:{_display_key(resource.key)}" for resource in unsupported
        )
        raise ComposeError(f"unsupported DATA resources: {labels}")
    if not resources:
        raise ComposeError("selected packages provide no DATA/BDEP resource")
    stock = _require_cam_entry(
        game_path / "DataMX" / "mx_miscdata.cam", b"DATA", b"BDEP"
    )
    result = merge_bdep(
        stock.data,
        ((resource.owner, resource.entry.data) for resource in resources),
    )
    entry = CamEntry(name=resources[0].entry.name, data=result.payload)
    archive = CamArchive(
        sections=(CamSection(extension=b"DATA", entries=(entry,)),)
    )
    return BdepComposeResult(archive=archive, deltas=result.deltas)


def merge_sound_resources(
    inventories: Sequence[PackageInventory],
) -> tuple[CamArchive, CamArchive, tuple[NamedMergeSelection, ...]]:
    resources = tuple(resource for inv in inventories for resource in inv.resources)
    waves, wave_selections = merge_named_resources(resources, b"WAVE")
    sounds, sound_selections = merge_named_resources(resources, b"DSND")
    return (
        CamArchive(sections=(CamSection(extension=b"WAVE", entries=waves),)),
        CamArchive(sections=(CamSection(extension=b"DSND", entries=sounds),)),
        (*wave_selections, *sound_selections),
    )


def merge_art_resources(
    game_path: Path,
    inventories: Sequence[PackageInventory],
) -> tuple[ArtDomainComposeResult, ArtDomainComposeResult]:
    """Compose main and interface art with typed, stock-relative relocation.

    The first selected owner retains a divergent positional slot. A later
    owner moves the complete contiguous changed run containing that conflict,
    which keeps a mod's authored sprite block together. Every moved TILE must
    be reachable through an audited IMAG frame field; otherwise the operation
    fails closed in ``rewrite_imag_entries``.
    """

    by_domain: dict[str, list[tuple[PackageInventory, Path, CamArchive]]] = {
        "main": [],
        "interface": [],
    }
    for inventory in inventories:
        art_paths: list[Path] = []
        for path in inventory.cams:
            archive = read_cam(path)
            extensions = {section.extension for section in archive.sections}
            if b"TILE" not in extensions:
                continue
            if b"IMAG" not in extensions:
                raise ComposeError(
                    f"{inventory.selected.alias}: positional TILE archive has no "
                    f"auditable IMAG section: {path}"
                )
            art_paths.append(path)
            domain = "main" if b"SPLT" in extensions else "interface"
            by_domain[domain].append((inventory, path, archive))

        if len(art_paths) != 2:
            raise ComposeError(
                f"{inventory.selected.alias}: expected exactly one main and one "
                f"interface art archive; found {len(art_paths)}"
            )

    results: list[ArtDomainComposeResult] = []
    stock_paths = {
        "main": game_path / "Data" / "maindata.cam",
        "interface": game_path / "Data" / "interfacedata.cam",
    }
    for domain in ("main", "interface"):
        providers = by_domain[domain]
        if len(providers) != len(inventories):
            owners = ", ".join(item[0].selected.alias for item in providers)
            raise ComposeError(
                f"{domain} art domain must have one provider per selected mod; "
                f"found {owners or 'none'}"
            )
        stock = read_cam(stock_paths[domain])
        analyses = tuple(
            analyze_art_archive(stock, archive, mod_id=inventory.selected.alias)
            for inventory, _path, archive in providers
        )
        result = _compose_art_domain(domain, stock, providers, analyses)
        results.append(result)
    return results[0], results[1]


def _compose_art_domain(
    domain: str,
    stock: CamArchive,
    providers: Sequence[tuple[PackageInventory, Path, CamArchive]],
    analyses: Sequence[ArtArchiveAnalysis],
) -> ArtDomainComposeResult:
    order = {
        inventory.selected.alias: index
        for index, (inventory, _path, _archive) in enumerate(providers)
    }
    analysis_by_owner = {analysis.mod_id: analysis for analysis in analyses}
    tile_deltas = {
        analysis.mod_id: analysis.tile_delta for analysis in analyses
    }
    tile_collisions = find_positional_collisions(tile_deltas)
    tile_moves = _select_later_conflict_runs(tile_deltas, tile_collisions, order)
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
    }
    if palette_deltas and len(palette_deltas) != len(analyses):
        raise ComposeError(f"{domain}: mixed SPLT/no-SPLT art providers")
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
        palette_moves = _select_later_conflict_runs(
            concrete_palette_deltas, palette_collisions, order
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
        entries = _require_section(archive, b"TILE").entries
        mapping = (
            palette_allocation.mapping_for(owner)
            if palette_allocation is not None
            else {}
        )
        if mapping:
            rewritten = rewrite_tile_palette_indices(
                entries,
                mapping,
                tile_indices=analysis_by_owner[owner].tile_delta.changed_indices,
            )
            entries = rewritten.entries
            palette_reports.append((owner, rewritten.report))
        rewritten_tiles[owner] = entries

    imag_resources: list[CamResource] = []
    imag_reports: list[tuple[str, ImagRelocationReport]] = []
    for inventory, path, archive in providers:
        owner = inventory.selected.alias
        mapping = tile_allocation.mapping_for(owner)
        imag_entries = _require_section(archive, b"IMAG").entries
        rewritten = rewrite_imag_entries(
            imag_entries,
            mapping,
            tile_count=tile_allocation.final_count,
        )
        imag_reports.append((owner, rewritten.report))
        for entry_order, entry in enumerate(rewritten.entries):
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
    imag_entries, _imag_selections = merge_named_resources(imag_resources, b"IMAG")

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
        stock_palettes = _require_section(stock, b"SPLT")
        output_palettes = _blank_positional_section(
            stock_palettes, palette_allocation.final_count
        )
        for inventory, _path, _archive in providers:
            owner = inventory.selected.alias
            analysis = analysis_by_owner[owner]
            assert analysis.palette_delta is not None
            mapping = palette_allocation.mapping_for(owner)
            mod_palettes = _require_section(_archive, b"SPLT").entries
            for change in analysis.palette_delta.changes:
                destination = mapping.get(change.index, change.index)
                _place_positional(
                    output_palettes,
                    destination,
                    mod_palettes[change.index],
                    owner,
                    b"SPLT",
                )
        _materialize_effective_stock_prefix(output_palettes, stock_palettes)
        palette_section = CamSection(
            extension=b"SPLT",
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


def merge_description_resources(
    inventories: Sequence[PackageInventory],
) -> DescriptionMergeResult:
    """Merge every XML Description and apply only declared building DialogIDs."""

    variants: list[tuple[str, bytes]] = []
    seen_by_owner: dict[str, set[DescriptionKey]] = {}
    for inventory in inventories:
        owner = inventory.selected.alias
        owner_seen = seen_by_owner.setdefault(owner, set())
        for path in inventory.descriptions:
            payload = path.read_bytes()
            document = parse_descriptions(payload, source=str(path))
            duplicate = owner_seen.intersection(document.index)
            if duplicate:
                labels = ", ".join(repr(key) for key in sorted(duplicate))
                raise ComposeError(
                    f"{owner}: duplicate Description keys across XML files: {labels}"
                )
            owner_seen.update(document.index)
            variants.append((owner, payload))

    if not variants:
        raise ComposeError("selected packages provide no XML Description resources")

    definitions = {
        inventory.selected.alias: inventory.selected.package.definition
        for inventory in inventories
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
            allowed = {building.dialog_id, building.controller_base}
            if current not in allowed:
                raise DescriptionFormatError(
                    f"{owner} {key!r} DialogID {current!r} is neither declared "
                    f"dialog_id {building.dialog_id!r} nor controller_base "
                    f"{building.controller_base!r}"
                )
            dialog.set("value", building.dialog_id)
            marker = (owner, building.local_name)
            matched[marker] = matched.get(marker, 0) + 1
        return element

    result = merge_descriptions(b"<Majesty />", variants, transform=transform)
    for owner, definition in definitions.items():
        if definition is None:
            raise ComposeError(f"{owner}: a v1 mod definition is required")
        for building in definition.custom_buildings:
            if matched.get((owner, building.local_name), 0) == 0:
                raise ComposeError(
                    f"{owner}: declared building {building.local_name!r} did not "
                    "match any XML Description"
                )
    return result


def analyze_description_stock_deltas(
    game_path: Path,
    inventories: Sequence[PackageInventory],
) -> tuple[DescriptionStockDelta, ...]:
    """Classify XML records against the effective Original+MX SDK baseline."""

    sdk_root = game_path / "SDK" / "OriginalQuests"
    stock: dict[DescriptionKey, tuple[object, str]] = {}
    for relative_directory in (Path("Data"), Path("DataMX")):
        directory = sdk_root / relative_directory
        if not directory.is_dir():
            raise ComposeError(f"stock Description directory was not found: {directory}")
        layer_seen: set[DescriptionKey] = set()
        for path in sorted(directory.glob("*.xml"), key=lambda item: item.name.casefold()):
            document = parse_descriptions(path.read_bytes(), source=str(path))
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

    result: list[DescriptionStockDelta] = []
    for inventory in inventories:
        owner = inventory.selected.alias
        for path in inventory.descriptions:
            document = parse_descriptions(path.read_bytes(), source=str(path))
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
) -> GplComposeResult:
    parsed_by_owner: dict[str, list[ParsedSemanticSource]] = {}
    for inventory in inventories:
        owner = inventory.selected.alias
        parsed_by_owner.setdefault(owner, []).extend(
            _parse_inventory_gpl_sources(inventory)
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

    try:
        parsed_by_owner = rewrite_private_activity_text_resolver_calls(
            parsed_by_owner,
            private_activity_texts or (),
            integer_expression_environment=integer_expression_environment,
        )
    except IntentTextError as exc:
        raise ComposeError(str(exc)) from exc

    initial = merge_sources([], parsed_by_owner)
    requested = {
        (DefinitionKind(kind), name.casefold()): owner
        for (kind, name), owner in (resolution_owners or {}).items()
    }
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
    final = merge_sources([], parsed_by_owner, resolutions or None)
    final.require_clean()
    final = add_inventory_death_drop_exclusions(
        final,
        inventory_death_drop_exclusions,
        source_name="<CAM Manager stock death-drop composition>",
    )
    if private_activity_texts:
        try:
            audit_private_activity_text_resolver_aliases(
                final.items, private_activity_texts
            )
        except IntentTextError as exc:
            raise ComposeError(str(exc)) from exc
    return GplComposeResult(
        source_set=final.emit_project_source_set(),
        conflicts=initial.conflicts,
        resolution_owners=tuple(used),
        resolution_sources=tuple(used_sources),
        inventory_death_drop_exclusions=tuple(inventory_death_drop_exclusions),
    )


def _parse_inventory_gpl_sources(
    inventory: PackageInventory,
) -> list[ParsedSemanticSource]:
    owner = inventory.selected.alias
    parsed: list[ParsedSemanticSource] = []
    for load in inventory.gpl_loads:
        for source_path in load.sources:
            path = source_path.absolute_path
            text = _read_source_text(path)
            suffix = path.suffix.casefold()
            if suffix == ".gpl":
                source = parse_gpl(text, str(path))
            elif suffix == ".dat":
                source = parse_dat(text, str(path))
            else:
                raise ComposeError(
                    f"{owner}: unsupported GPL source extension: {path}"
                )
            try:
                require_complete_semantic_coverage(source)
            except ValueError as exc:
                raise ComposeError(
                    f"{owner}: GPL source has unparsed content the composer "
                    f"cannot preserve: {path}: {exc}"
                ) from exc
            parsed.append(source)
    return parsed


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
    adding or deleting a stock Description document changes the snapshot.  A
    symlink anywhere below the resolved game root is rejected rather than
    silently following a mutable external target.
    """

    root = game_path.resolve(strict=True)
    if not root.is_dir():
        raise ComposeError(f"game path is not a directory: {root}")

    relative_paths = _enumerate_stock_compose_relative_paths(root)

    snapshots: list[StockComposeInput] = []
    seen: set[str] = set()
    for relative in relative_paths:
        normalized = relative.as_posix().casefold()
        if normalized in seen:
            raise ComposeError(
                "installed stock composition inputs contain a duplicate "
                f"case-insensitive path: {relative.as_posix()}"
            )
        seen.add(normalized)
        path = root / relative
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
                size=after.st_size,
                sha256=digest,
            )
        )
    if relative_paths != _enumerate_stock_compose_relative_paths(root):
        raise ComposeError(
            "installed stock Description inputs changed while creating the "
            "composition snapshot"
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
    expected = "directory" if expect_directory else "file"
    if (expect_directory and not path.is_dir()) or (
        not expect_directory and not path.is_file()
    ):
        raise ComposeError(
            f"required installed stock composition {expected} was not found: {path}"
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
    inventory_death_drop_exclusions: Sequence[str] = (),
    runtime_capabilities: Sequence[str] = (),
    private_activity_texts: Sequence[PrivateActivityTextBinding] | None = None,
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
    mod_ids = [selected.package.mod_id.casefold() for selected in selected_mods]
    if len(set(mod_ids)) != len(mod_ids):
        raise ComposeError("selected package Mod IDs must be unique")
    for selected in selected_mods:
        if selected.package.definition is None:
            raise ComposeError(f"{selected.alias}: a v1 mod definition is required")
    output_root = output_root.resolve(strict=False)
    if output_root.exists():
        raise ComposeError(f"output destination already exists: {output_root}")
    output_root.parent.mkdir(parents=True, exist_ok=True)

    inventories = tuple(inventory_package(selected) for selected in selected_mods)
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
    )
    text_result = merge_text_resources(
        game_path,
        inventories,
        private_activity_texts=private_activity_texts,
    )
    bdep_result = merge_bdep_resource(game_path, inventories)
    main_art, interface_art = merge_art_resources(game_path, inventories)
    audio_archive, sound_archive, sound_selections = merge_sound_resources(inventories)
    descriptions = merge_description_resources(inventories)
    description_stock_deltas = analyze_description_stock_deltas(
        game_path, inventories
    )
    gpl = merge_gpl_resources(
        inventories,
        resolution_owners=resolution_owners,
        semantic_resolutions=semantic_resolutions,
        inventory_death_drop_exclusions=inventory_death_drop_exclusions,
        private_activity_texts=private_activity_texts,
        stock_integer_expression_sources=(
            (_load_stock_activity_text_expression_source(game_path),)
            if private_activity_texts
            else ()
        ),
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
    )

    staging = Path(
        tempfile.mkdtemp(prefix=f".{profile_slug}-", dir=output_root.parent)
    )
    try:
        data_directory = staging / "Data"
        data_directory.mkdir()
        cam_outputs = (
            ("merged_textdata.cam", text_result.text_archive),
            ("merged_gpltext.cam", text_result.gpltext_archive),
            ("merged_miscdata.cam", bdep_result.archive),
            ("merged_maindata.cam", main_art.archive),
            ("merged_interfacedata.cam", interface_art.archive),
            ("merged_audio.cam", audio_archive),
            ("merged_sounddesc.cam", sound_archive),
        )
        for filename, archive in cam_outputs:
            (data_directory / filename).write_bytes(archive.to_bytes())
        descriptions_path = data_directory / "merged_descriptions.xml"
        descriptions_path.write_bytes(descriptions.payload)

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

        validation = validate_composed_package(staging)
        report_payload = _build_report(
            profile_slug=profile_slug,
            output_mod_id=output_mod_id,
            selected_mods=selected_mods,
            game_path=game_path,
            text_result=text_result,
            bdep_result=bdep_result,
            main_art=main_art,
            interface_art=interface_art,
            sound_selections=sound_selections,
            descriptions=descriptions,
            description_stock_deltas=description_stock_deltas,
            gpl=gpl,
            compiled=compiled,
            runtime_capabilities=canonical_runtime_capabilities,
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


def _derive_runtime_capabilities(
    runtime_capabilities: Sequence[str],
    *,
    has_private_activity_text: bool,
) -> tuple[tuple[str, ...], bytes]:
    """Validate caller capabilities and derive the private-text requirement.

    The MMTX runtime feature is evidence-owned by composition, never by a
    package identity or caller assertion. This keeps direct API and POC builds
    coherent in both directions as well as manager-driven builds.
    """

    try:
        provided = decode_runtime_capability_manifest(
            encode_runtime_capability_manifest(runtime_capabilities)
        )
        effective = set(provided)
        effective.discard(PRIVATE_ACTIVITY_TEXT_RUNTIME_CAPABILITY)
        if has_private_activity_text:
            effective.add(PRIVATE_ACTIVITY_TEXT_RUNTIME_CAPABILITY)
        payload = encode_runtime_capability_manifest(tuple(sorted(effective)))
        return decode_runtime_capability_manifest(payload), payload
    except ValueError as exc:
        raise ComposeError(f"invalid runtime capability requirements: {exc}") from exc


def validate_composed_package(root: Path) -> Mapping[str, object]:
    """Reparse every emitted resource and verify the generated load graph."""

    package = load_package(root)
    if len(package.datasets) != 1 or len(package.datasets[0].loads) != 1:
        raise ComposeError("generated package does not contain one Any/Load graph")
    load = package.datasets[0].loads[0]
    if package.datasets[0].base.casefold() != "any":
        raise ComposeError("generated package Dataset base is not Any")
    if len(load.cams) != 7:
        raise ComposeError(f"generated package has {len(load.cams)} CAMs, expected 7")
    cam_summaries = []
    palette_reference_count = 0
    for path in load.cams:
        original = path.absolute_path.read_bytes()
        archive = read_cam(original)
        if archive.to_bytes() != original:
            raise ComposeError(f"generated CAM is not byte-stable: {path.relative_path}")
        sections_by_extension = {
            section.extension: section for section in archive.sections
        }
        tile_section = sections_by_extension.get(b"TILE")
        palette_section = sections_by_extension.get(b"SPLT")
        if tile_section is not None:
            if tile_section.padding != b"\x01\x00\x00\x00":
                raise ComposeError(
                    f"generated TILE section lost its stock positional flag: "
                    f"{path.relative_path}"
                )
            if palette_section is not None:
                if palette_section.padding != b"\x01\x00\x00\x00":
                    raise ComposeError(
                        f"generated SPLT section lost its stock positional flag: "
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
                        "payload_entries": sum(bool(entry.data) for entry in section.entries),
                    }
                    for section in archive.sections
                ],
            }
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
    for source in gpl_load.sources:
        text = _read_source_text(source.absolute_path)
        if source.absolute_path.suffix.casefold() == ".gpl":
            parsed_sources += len(parse_gpl(text, source.relative_path).items)
        elif source.absolute_path.suffix.casefold() == ".dat":
            parsed_sources += len(parse_dat(text, source.relative_path).items)
        else:
            raise ComposeError(f"generated GPL source has unsupported type: {source.relative_path}")
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
    if package.definition is None or package.definition.schema_version != 2:
        raise ComposeError(
            "generated package must carry a schema-version 2 merge definition"
        )
    if package.definition.runtime_capabilities != runtime_capabilities:
        raise ComposeError(
            "generated package definition and runtime capability manifest disagree"
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
        "resolved_external_palette_references": palette_reference_count,
    }


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
) -> dict:
    buildings = []
    for selected in selected_mods:
        definition = selected.package.definition
        assert definition is not None
        for building in definition.custom_buildings:
            buildings.append(
                {
                    "local_name": building.local_name,
                    "dialog_id": building.dialog_id,
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


def _build_manifest(
    *,
    mod_id: str,
    internal_name: str,
    display_name: str,
    cam_filenames: Sequence[str],
    description_filename: str,
    source_set: GplProjectSourceSet,
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
    main_art: ArtDomainComposeResult,
    interface_art: ArtDomainComposeResult,
    sound_selections: Sequence[NamedMergeSelection],
    descriptions: DescriptionMergeResult,
    description_stock_deltas: Sequence[DescriptionStockDelta],
    gpl: GplComposeResult,
    compiled: CompiledGpl,
    runtime_capabilities: Sequence[str],
    staging: Path,
    validation: Mapping[str, object],
) -> dict:
    stock_inputs = snapshot_stock_compose_inputs(game_path)
    selected_payload = []
    for selected in selected_mods:
        files = [
            {
                "path": path.relative_to(selected.package.root).as_posix(),
                "size": path.stat().st_size,
                "sha256": _sha256(path),
            }
            for path in sorted(selected.package.root.rglob("*"))
            if path.is_file()
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
        },
        "merge": {
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
                "compiled_bcd_size": compiled.size,
            },
            "art": {
                "main": _art_report_payload(main_art),
                "interface": _art_report_payload(interface_art),
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


def _dialog_renames(
    inventories: Sequence[PackageInventory], resources: Sequence[CamResource]
) -> tuple[tuple[str, bytes, bytes], ...]:
    renames: list[tuple[str, bytes, bytes]] = []
    claimed_targets: dict[bytes, str] = {}
    for inventory in inventories:
        selected = inventory.selected
        definition = selected.package.definition
        if definition is None:
            raise ComposeError(f"{selected.alias}: a v1 mod definition is required")
        for building in definition.custom_buildings:
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
            previous = claimed_targets.get(target)
            if previous is not None and previous != selected.alias:
                raise ComposeError(
                    f"dialog ID {_display_key(target)} is declared by both "
                    f"{previous} and {selected.alias}"
                )
            claimed_targets[target] = selected.alias

            owner_dialog_keys = {
                resource.key
                for resource in resources
                if resource.owner == selected.alias
                and resource.section in (b"SMNU", b"STRT")
            }
            source = target if target in owner_dialog_keys else controller
            if source not in owner_dialog_keys:
                raise ComposeError(
                    f"{selected.alias}: neither declared dialog_id "
                    f"{_display_key(target)} nor controller_base "
                    f"{_display_key(controller)} exists in its panel resources"
                )
            if source != target:
                renames.append((selected.alias, source, target))
    return tuple(renames)


def _select_later_conflict_runs(
    deltas: Mapping[str, PositionalSectionDelta],
    collisions: Sequence[PositionalCollision],
    owner_order: Mapping[str, int],
) -> dict[str, set[int]]:
    selected = {owner: set() for owner in deltas}
    changed = {
        owner: set(delta.changed_indices) for owner, delta in deltas.items()
    }
    for collision in collisions:
        if collision.identical_payload:
            continue
        owners = sorted(collision.mods, key=lambda owner: owner_order[owner])
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
    "DescriptionStockDelta",
    "GplComposeResult",
    "NamedMergeSelection",
    "PackageInventory",
    "SelectedMod",
    "ScopedSemanticResolution",
    "StockComposeInput",
    "StrtMergeSelection",
    "TextMergeResult",
    "compile_gpl",
    "compose_package",
    "analyze_description_stock_deltas",
    "discover_private_activity_texts",
    "discover_selected_private_activity_texts",
    "inventory_package",
    "merge_bdep_resource",
    "merge_art_resources",
    "merge_description_resources",
    "merge_gpl_resources",
    "merge_named_resources",
    "merge_sound_resources",
    "merge_text_resources",
    "snapshot_stock_compose_inputs",
    "validate_composed_package",
]
