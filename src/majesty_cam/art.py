"""Stock-relative analysis and safe relocation for Majesty CAM art.

Majesty resolves ``TILE`` and ``SPLT`` records by their position in a CAM
section.  A mod CAM commonly contains thousands of empty records so the game
falls through to the stock archive, followed by a private block of records.
Consequently, entry names are useful diagnostics but are not allocation keys.

This module deliberately understands only the IMAG frame layouts proved by the
Phantoms Haunt and Alchemist packages.  It never searches an IMAG byte string
for integer-looking values.  Unknown direction layouts fail closed before any
bytes are changed.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
import struct
from typing import Iterable, Mapping, Sequence

from .cam import CamArchive, CamEntry, CamFormatError, CamSection, pad_extension, pad_name


IMAG = b"IMAG"
TILE = b"TILE"
SPLT = b"SPLT"

IMAG_HEADER_SIZE = 20
IMAG_SET_ENTRY_SIZE = 8
IMAG_SET_FIXED_SIZE = 64
MAX_IMAG_SETS = 256
MAX_DIRECTIONS = 32
MAX_FRAMES = 256
LOW16_SENTINEL = 0xFFFF
BUILDING_TERMINAL_TILE_SET_ID = 208


class ArtFormatError(CamFormatError):
    """Raised when positional art data is malformed or cannot be proved safe."""


class UnsupportedImagShapeError(ArtFormatError):
    """Raised when an IMAG direction does not match an audited frame layout."""


class UnprovenReferenceError(ArtFormatError):
    """Raised rather than relocating a slot without a complete reference map."""

    def __init__(self, slots: Iterable[int], *, kind: str = "TILE") -> None:
        self.slots = tuple(sorted(set(slots)))
        rendered = ", ".join(str(slot) for slot in self.slots)
        super().__init__(
            f"Cannot relocate {kind} slot(s) {rendered}: no proven affected reference map"
        )


@dataclass(frozen=True)
class PositionalChange:
    """One non-fall-through mod record relative to the stock section."""

    index: int
    entry: CamEntry
    stock_entry: CamEntry | None

    @property
    def kind(self) -> str:
        return "replace" if self.stock_entry is not None else "append"

    @property
    def name_changed(self) -> bool:
        return self.stock_entry is not None and self.entry.name != self.stock_entry.name


@dataclass(frozen=True)
class PositionalSectionDelta:
    """The payload-bearing records a mod contributes to one positional section."""

    extension: bytes
    stock_count: int
    mod_count: int
    changes: tuple[PositionalChange, ...]
    fallthrough_count: int
    stock_identical_count: int

    def __post_init__(self) -> None:
        if len(self.extension) != 4:
            raise ArtFormatError("Positional section extensions must contain four bytes")

    @property
    def changed_indices(self) -> tuple[int, ...]:
        return tuple(change.index for change in self.changes)

    def change_at(self, index: int) -> PositionalChange | None:
        return next((change for change in self.changes if change.index == index), None)


@dataclass(frozen=True)
class PositionalCollision:
    """Two or more mods contributing payload at the same positional slot."""

    extension: bytes
    index: int
    mods: tuple[str, ...]
    identical_payload: bool


@dataclass(frozen=True)
class SlotRelocation:
    mod_id: str
    extension: bytes
    old_index: int
    new_index: int
    entry_name: bytes


@dataclass(frozen=True)
class ModRangeAllocation:
    """A half-open deterministic output range allocated to one mod."""

    mod_id: str
    extension: bytes
    start: int
    stop: int
    relocations: tuple[SlotRelocation, ...]

    @property
    def mapping(self) -> dict[int, int]:
        return {
            relocation.old_index: relocation.new_index
            for relocation in self.relocations
        }


@dataclass(frozen=True)
class PositionalAllocationReport:
    extension: bytes
    stock_count: int
    final_count: int
    ranges: tuple[ModRangeAllocation, ...]

    def mapping_for(self, mod_id: str) -> dict[int, int]:
        for allocation in self.ranges:
            if allocation.mod_id == mod_id:
                return allocation.mapping
        raise KeyError(mod_id)


@dataclass(frozen=True)
class ImagTileReference:
    """One typed low-16 TILE field in an IMAG frame record."""

    entry_name: bytes
    set_id: int
    direction: int
    frame: int
    offset: int
    encoded_value: int
    layout: str

    @property
    def tile_index(self) -> int:
        return self.encoded_value & 0xFFFF

    @property
    def flag_bits(self) -> int:
        return self.encoded_value & 0xFFFF0000


@dataclass(frozen=True)
class ParsedImag:
    entry_name: bytes
    references: tuple[ImagTileReference, ...]
    layouts: tuple[str, ...]
    set_count: int


@dataclass(frozen=True)
class ImagReferenceRewrite:
    entry_name: bytes
    set_id: int
    direction: int
    frame: int
    offset: int
    old_index: int
    new_index: int
    preserved_flag_bits: int


@dataclass(frozen=True)
class ImagRelocationReport:
    mapping: tuple[tuple[int, int], ...]
    rewrites: tuple[ImagReferenceRewrite, ...]
    parsed_entries: tuple[bytes, ...]
    supported_layouts: tuple[str, ...]

    @property
    def rewritten_slots(self) -> tuple[int, ...]:
        return tuple(sorted({rewrite.old_index for rewrite in self.rewrites}))


@dataclass(frozen=True)
class ImagRewriteResult:
    entries: tuple[CamEntry, ...]
    report: ImagRelocationReport


@dataclass(frozen=True)
class TilePaletteReference:
    tile_index: int
    palette_index: int
    offset: int = 22


@dataclass(frozen=True)
class TilePaletteRewrite:
    tile_index: int
    old_index: int
    new_index: int
    offset: int = 22


@dataclass(frozen=True)
class PaletteRelocationReport:
    mapping: tuple[tuple[int, int], ...]
    rewrites: tuple[TilePaletteRewrite, ...]

    @property
    def rewritten_slots(self) -> tuple[int, ...]:
        return tuple(sorted({rewrite.old_index for rewrite in self.rewrites}))


@dataclass(frozen=True)
class PaletteRewriteResult:
    entries: tuple[CamEntry, ...]
    report: PaletteRelocationReport


@dataclass(frozen=True)
class ArtArchiveAnalysis:
    """Read-only, stock-relative inventory of one mod art archive."""

    mod_id: str
    tile_delta: PositionalSectionDelta
    palette_delta: PositionalSectionDelta | None
    imag_entries: tuple[CamEntry, ...]
    imag_references: tuple[ImagTileReference, ...]
    retained_tile_dependencies: tuple[int, ...]
    tile_palette_references: tuple[TilePaletteReference, ...]
    unreferenced_tile_changes: tuple[int, ...]
    unreferenced_palette_changes: tuple[int, ...]
    supported_imag_layouts: tuple[str, ...]


@dataclass(frozen=True)
class ArtRelocationReport:
    """Combined report suitable for a manager UI or serialized diagnostic."""

    tile_allocation: PositionalAllocationReport
    palette_allocation: PositionalAllocationReport | None
    imag_reports: tuple[tuple[str, ImagRelocationReport], ...]
    palette_reports: tuple[tuple[str, PaletteRelocationReport], ...]


def compute_stock_relative_delta(
    stock: CamSection,
    mod: CamSection,
) -> PositionalSectionDelta:
    """Compare a positional section using Majesty's empty-entry fall-through.

    Empty mod payloads do not replace stock.  A nonempty payload identical to
    stock is also not a semantic delta, even if its diagnostic entry name was
    changed.  Every other nonempty payload is a replacement or append.
    """

    if stock.extension != mod.extension:
        raise ArtFormatError(
            f"Cannot compare {stock.extension!r} with {mod.extension!r}"
        )

    changes: list[PositionalChange] = []
    fallthrough_count = 0
    stock_identical_count = 0
    for index, entry in enumerate(mod.entries):
        if not entry.data:
            fallthrough_count += 1
            continue
        stock_entry = stock.entries[index] if index < len(stock.entries) else None
        if stock_entry is not None and entry.data == stock_entry.data:
            stock_identical_count += 1
            continue
        changes.append(
            PositionalChange(index=index, entry=entry, stock_entry=stock_entry)
        )

    return PositionalSectionDelta(
        extension=mod.extension,
        stock_count=len(stock.entries),
        mod_count=len(mod.entries),
        changes=tuple(changes),
        fallthrough_count=fallthrough_count,
        stock_identical_count=stock_identical_count,
    )


def find_positional_collisions(
    deltas: Mapping[str, PositionalSectionDelta],
) -> tuple[PositionalCollision, ...]:
    """Report desired-slot overlaps, distinguishing identical shared payloads."""

    _validate_compatible_deltas(deltas)
    by_index: dict[int, list[tuple[str, PositionalChange]]] = {}
    for mod_id, delta in deltas.items():
        for change in delta.changes:
            by_index.setdefault(change.index, []).append((mod_id, change))

    collisions: list[PositionalCollision] = []
    for index, owners in sorted(by_index.items()):
        if len(owners) < 2:
            continue
        payloads = {change.entry.data for _, change in owners}
        collisions.append(
            PositionalCollision(
                extension=next(iter(deltas.values())).extension,
                index=index,
                mods=tuple(sorted(mod_id for mod_id, _ in owners)),
                identical_payload=len(payloads) == 1,
            )
        )
    return tuple(collisions)


def allocate_collision_free_ranges(
    deltas: Mapping[str, PositionalSectionDelta],
    *,
    start: int | None = None,
    indices_by_mod: Mapping[str, Iterable[int]] | None = None,
    maximum_index: int | None = None,
) -> PositionalAllocationReport:
    """Allocate one dense, deterministic positional range per mod.

    Mod IDs are sorted, so input mapping order cannot alter the result.  Within
    a mod, source positions are sorted and retain their relative order.  The
    optional ``indices_by_mod`` lets a later planner leave proven fixed slots in
    place and allocate only the positions that genuinely need relocation.
    """

    extension, stock_count = _validate_compatible_deltas(deltas)
    selected_by_mod: dict[str, set[int]] = {}
    reserved_indices: set[int] = set()
    for mod_id, delta in deltas.items():
        selected = (
            set(delta.changed_indices)
            if indices_by_mod is None
            else set(indices_by_mod.get(mod_id, ()))
        )
        unknown = selected - set(delta.changed_indices)
        if unknown:
            rendered = ", ".join(str(index) for index in sorted(unknown))
            raise ArtFormatError(f"{mod_id} has no {extension!r} delta at {rendered}")
        selected_by_mod[mod_id] = selected
        reserved_indices.update(set(delta.changed_indices) - selected)

    # Positions deliberately left out of the relocation set remain occupied.
    # Put automatic allocations above every appended reserved position rather
    # than silently reusing a direct/unknown slot as private storage.
    minimum_safe_start = stock_count
    appended_reserved = {index for index in reserved_indices if index >= stock_count}
    if appended_reserved:
        minimum_safe_start = max(appended_reserved) + 1
    cursor = minimum_safe_start if start is None else start
    if cursor < stock_count:
        raise ArtFormatError(
            f"Allocation start {cursor} precedes stock {extension!r} count {stock_count}"
        )

    ranges: list[ModRangeAllocation] = []
    for mod_id in sorted(deltas):
        delta = deltas[mod_id]
        selected = selected_by_mod[mod_id]
        changes = [change for change in delta.changes if change.index in selected]
        range_start = cursor
        relocations: list[SlotRelocation] = []
        for change in changes:
            if cursor in reserved_indices:
                raise ArtFormatError(
                    f"Allocation target {cursor} is occupied by an unrelocated "
                    f"{extension!r} delta; choose a later start"
                )
            if maximum_index is not None and cursor > maximum_index:
                raise ArtFormatError(
                    f"Allocated {extension!r} index {cursor} exceeds {maximum_index}"
                )
            relocations.append(
                SlotRelocation(
                    mod_id=mod_id,
                    extension=extension,
                    old_index=change.index,
                    new_index=cursor,
                    entry_name=change.entry.name,
                )
            )
            cursor += 1
        ranges.append(
            ModRangeAllocation(
                mod_id=mod_id,
                extension=extension,
                start=range_start,
                stop=cursor,
                relocations=tuple(relocations),
            )
        )

    return PositionalAllocationReport(
        extension=extension,
        stock_count=stock_count,
        final_count=cursor,
        ranges=tuple(ranges),
    )


def parse_imag_tile_references(
    data: bytes,
    *,
    tile_count: int,
    entry_name: str | bytes = b"",
) -> ParsedImag:
    """Parse audited Majesty IMAG frame layouts without scanning raw words.

    Supported direction records are:

    * ``compact`` -- overlays, icons, missiles and interface/raw textures;
    * ``extended`` -- actor and building frames with geometry fields;
    * ``projectile`` -- the 32-direction projectile table.

    These three layouts cover every IMAG emitted by the current Phantoms Haunt
    and Alchemist main/interface builders, including ``PHTIraw textures`` and
    ``ALTIraw textures``.  The parser validates the animation-set directory,
    direction directory, frame count, record boundary and every low-16 TILE
    index before returning offsets that may be rewritten.
    """

    raw_name = _entry_name_bytes(entry_name)
    if tile_count < 0 or tile_count > LOW16_SENTINEL:
        raise ArtFormatError(f"Invalid TILE count {tile_count}; IMAG indices are low-16")
    if len(data) < IMAG_HEADER_SIZE + 4:
        raise UnsupportedImagShapeError(
            f"IMAG {_display_name(raw_name)!r} is too short for a set table"
        )

    set_count = _u32(data, IMAG_HEADER_SIZE)
    table_start = IMAG_HEADER_SIZE + 4
    table_end = table_start + set_count * IMAG_SET_ENTRY_SIZE
    if set_count <= 0 or set_count > MAX_IMAG_SETS or table_end > len(data):
        raise UnsupportedImagShapeError(
            f"IMAG {_display_name(raw_name)!r} has invalid set count {set_count}"
        )

    set_entries: list[tuple[int, int]] = []
    for set_index in range(set_count):
        offset = table_start + set_index * IMAG_SET_ENTRY_SIZE
        set_entries.append((_u32(data, offset), _u32(data, offset + 4)))
    set_offsets = [offset for _, offset in set_entries]
    if set_offsets != sorted(set_offsets) or len(set(set_offsets)) != len(set_offsets):
        raise UnsupportedImagShapeError(
            f"IMAG {_display_name(raw_name)!r} set offsets are not strictly increasing"
        )
    if set_offsets[0] < table_end or set_offsets[-1] >= len(data):
        raise UnsupportedImagShapeError(
            f"IMAG {_display_name(raw_name)!r} set offsets leave the record"
        )

    references: list[ImagTileReference] = []
    layouts: set[str] = set()
    for set_index, (set_id, set_offset) in enumerate(set_entries):
        set_end = (
            set_entries[set_index + 1][1]
            if set_index + 1 < len(set_entries)
            else len(data)
        )
        if set_end - set_offset < IMAG_SET_FIXED_SIZE + 4:
            raise UnsupportedImagShapeError(
                f"IMAG {_display_name(raw_name)!r} set {set_id} is truncated"
            )

        direction_count = _u32(data, set_offset)
        direction_table_start = set_offset + IMAG_SET_FIXED_SIZE
        direction_table_end = direction_table_start + direction_count * 4
        if (
            direction_count <= 0
            or direction_count > MAX_DIRECTIONS
            or direction_table_end > set_end
        ):
            raise UnsupportedImagShapeError(
                f"IMAG {_display_name(raw_name)!r} set {set_id} has invalid "
                f"direction count {direction_count}"
            )

        relative_offsets = [
            _i32(data, direction_table_start + direction * 4)
            for direction in range(direction_count)
        ]
        if (
            relative_offsets != sorted(relative_offsets)
            or len(set(relative_offsets)) != len(relative_offsets)
            or any(relative <= 0 for relative in relative_offsets)
        ):
            raise UnsupportedImagShapeError(
                f"IMAG {_display_name(raw_name)!r} set {set_id} has unsupported "
                "direction offsets"
            )

        anchors = [set_offset + relative for relative in relative_offsets]
        if anchors[0] < direction_table_end or anchors[-1] >= set_end:
            raise UnsupportedImagShapeError(
                f"IMAG {_display_name(raw_name)!r} set {set_id} direction data "
                "overlaps its directory or leaves the set"
            )

        for direction, anchor in enumerate(anchors):
            direction_end = anchors[direction + 1] if direction + 1 < len(anchors) else set_end
            layout, frame_count, first_tile_offset = _parse_direction_layout(
                data,
                anchor=anchor,
                direction_end=direction_end,
                entry_name=raw_name,
                set_id=set_id,
                direction=direction,
            )
            layouts.add(layout)
            for frame in range(frame_count):
                tile_offset = first_tile_offset + frame * 8
                encoded_value = _u32(data, tile_offset)
                tile_index = encoded_value & 0xFFFF
                if tile_index == LOW16_SENTINEL:
                    continue
                if tile_index >= tile_count:
                    raise UnsupportedImagShapeError(
                        f"IMAG {_display_name(raw_name)!r} set {set_id} direction "
                        f"{direction} frame {frame} references missing TILE {tile_index} "
                        f"of {tile_count}"
                    )
                references.append(
                    ImagTileReference(
                        entry_name=raw_name,
                        set_id=set_id,
                        direction=direction,
                        frame=frame,
                        offset=tile_offset,
                        encoded_value=encoded_value,
                        layout=layout,
                    )
                )

        # Stock building IMAG set 208 carries one additional TILE reference in
        # the final u32 of the set, after its direction records.  It is present
        # in every ordinary stock building family (including the three Fervus
        # levels cloned by Phantoms Haunt) and is not part of a frame table.
        # Treat the field explicitly so relocation preserves the complete stock
        # building-image lifecycle without scanning arbitrary integer values.
        terminal_offset = set_end - 4
        if (
            set_id == BUILDING_TERMINAL_TILE_SET_ID
            and terminal_offset >= direction_table_end
            and all(reference.offset != terminal_offset for reference in references)
        ):
            encoded_value = _u32(data, terminal_offset)
            tile_index = encoded_value & 0xFFFF
            if tile_index != LOW16_SENTINEL:
                if tile_index >= tile_count:
                    raise UnsupportedImagShapeError(
                        f"IMAG {_display_name(raw_name)!r} set {set_id} terminal "
                        f"field references missing TILE {tile_index} of {tile_count}"
                    )
                references.append(
                    ImagTileReference(
                        entry_name=raw_name,
                        set_id=set_id,
                        direction=-1,
                        frame=-1,
                        offset=terminal_offset,
                        encoded_value=encoded_value,
                        layout="building-terminal",
                    )
                )
                layouts.add("building-terminal")

    return ParsedImag(
        entry_name=raw_name,
        references=tuple(references),
        layouts=tuple(sorted(layouts)),
        set_count=set_count,
    )


def rewrite_imag_entries(
    entries: Sequence[CamEntry],
    mapping: Mapping[int, int],
    *,
    tile_count: int,
    require_all_referenced: bool = True,
) -> ImagRewriteResult:
    """Rewrite typed IMAG references and return an auditable report.

    Every entry is parsed before any result is returned.  If an entry has an
    unsupported shape, or an affected old slot is absent from the complete
    parsed reference set, the operation fails without returning partial data.
    """

    normalized = _validated_low16_mapping(mapping)
    parsed = [
        parse_imag_tile_references(
            entry.data,
            tile_count=tile_count,
            entry_name=entry.name,
        )
        for entry in entries
    ]
    referenced = {
        reference.tile_index
        for image in parsed
        for reference in image.references
    }
    effective = {old: new for old, new in normalized.items() if old != new}
    missing = set(effective) - referenced
    if require_all_referenced and missing:
        raise UnprovenReferenceError(missing)

    rewritten_entries: list[CamEntry] = []
    rewrites: list[ImagReferenceRewrite] = []
    for entry, image in zip(entries, parsed):
        patched = bytearray(entry.data)
        for reference in image.references:
            new_index = effective.get(reference.tile_index)
            if new_index is None:
                continue
            encoded = reference.flag_bits | new_index
            struct.pack_into("<I", patched, reference.offset, encoded)
            rewrites.append(
                ImagReferenceRewrite(
                    entry_name=entry.name,
                    set_id=reference.set_id,
                    direction=reference.direction,
                    frame=reference.frame,
                    offset=reference.offset,
                    old_index=reference.tile_index,
                    new_index=new_index,
                    preserved_flag_bits=reference.flag_bits,
                )
            )
        rewritten_entries.append(replace(entry, data=bytes(patched)))

    layouts = sorted(
        {layout for image in parsed for layout in image.layouts}
    )
    return ImagRewriteResult(
        entries=tuple(rewritten_entries),
        report=ImagRelocationReport(
            mapping=tuple(sorted(normalized.items())),
            rewrites=tuple(rewrites),
            parsed_entries=tuple(entry.name for entry in entries),
            supported_layouts=tuple(layouts),
        ),
    )


def rewrite_imag_tile_indices(
    data: bytes,
    mapping: Mapping[int, int],
    *,
    tile_count: int,
    entry_name: str | bytes = b"",
    require_all_referenced: bool = True,
) -> bytes:
    """Convenience wrapper returning one rewritten IMAG payload."""

    entry = CamEntry(name=pad_name(_entry_name_bytes(entry_name)), data=data)
    return rewrite_imag_entries(
        (entry,),
        mapping,
        tile_count=tile_count,
        require_all_referenced=require_all_referenced,
    ).entries[0].data


def parse_tile_palette_reference(
    tile: bytes,
    *,
    tile_index: int,
) -> TilePaletteReference | None:
    """Return the external SPLT field from a validated TILE v1/v3 payload."""

    if len(tile) < 26:
        raise ArtFormatError(f"TILE {tile_index} is shorter than its 26-byte header")
    version = _u16(tile, 0)
    height = _u16(tile, 2)
    width = _u16(tile, 4)
    if version not in (1, 3) or width <= 0 or height <= 0:
        raise ArtFormatError(
            f"TILE {tile_index} has unsupported header version={version} size={width}x{height}"
        )
    palette_mode = _u16(tile, 20)
    palette_value = _u32(tile, 22)
    if palette_mode == 0:
        return TilePaletteReference(
            tile_index=tile_index,
            palette_index=palette_value,
        )
    if palette_mode == 1:
        if palette_value < 26 or palette_value >= len(tile):
            raise ArtFormatError(
                f"TILE {tile_index} has invalid embedded palette offset {palette_value}"
            )
        return None
    raise ArtFormatError(f"TILE {tile_index} uses unsupported palette mode {palette_mode}")


def validate_external_palette_closure(
    tiles: CamSection,
    palettes: CamSection,
) -> tuple[TilePaletteReference, ...]:
    """Prove that every payload-bearing TILE can resolve its external SPLT.

    Majesty's TILE records fall through independently, but an emitted main-art
    archive owns its positional SPLT table.  The completed Haunt and Alchemist
    packages therefore materialize the effective stock palette prefix instead
    of writing zero-length palette records.  Rejecting an incomplete closure
    here prevents valid TILE pixels from being decoded through empty palettes.
    """

    if tiles.extension != TILE:
        raise ArtFormatError(
            f"Expected a TILE section, found {tiles.extension!r}"
        )
    if palettes.extension != SPLT:
        raise ArtFormatError(
            f"Expected an SPLT section, found {palettes.extension!r}"
        )

    references: list[TilePaletteReference] = []
    missing: list[tuple[int, int]] = []
    for tile_index, entry in enumerate(tiles.entries):
        if not entry.data:
            continue
        reference = parse_tile_palette_reference(
            entry.data,
            tile_index=tile_index,
        )
        if reference is None:
            continue
        references.append(reference)
        palette_index = reference.palette_index
        if (
            palette_index >= len(palettes.entries)
            or not palettes.entries[palette_index].data
        ):
            missing.append((tile_index, palette_index))

    if missing:
        rendered = ", ".join(
            f"TILE {tile_index} -> SPLT {palette_index}"
            for tile_index, palette_index in missing
        )
        raise ArtFormatError(
            "Main-art palette closure is incomplete: " + rendered
        )
    return tuple(references)


def rewrite_tile_palette_indices(
    entries: Sequence[CamEntry],
    mapping: Mapping[int, int],
    *,
    tile_indices: Iterable[int] | None = None,
    require_all_referenced: bool = True,
) -> PaletteRewriteResult:
    """Rewrite external SPLT references in explicitly owned TILE payloads."""

    normalized = _validated_u32_mapping(mapping, kind="SPLT")
    selected = (
        set(range(len(entries)))
        if tile_indices is None
        else set(tile_indices)
    )
    invalid = {index for index in selected if index < 0 or index >= len(entries)}
    if invalid:
        rendered = ", ".join(str(index) for index in sorted(invalid))
        raise ArtFormatError(f"TILE selection leaves the section: {rendered}")

    references: dict[int, TilePaletteReference] = {}
    for tile_index in sorted(selected):
        entry = entries[tile_index]
        if not entry.data:
            continue
        reference = parse_tile_palette_reference(entry.data, tile_index=tile_index)
        if reference is not None:
            references[tile_index] = reference

    effective = {old: new for old, new in normalized.items() if old != new}
    referenced_palettes = {reference.palette_index for reference in references.values()}
    missing = set(effective) - referenced_palettes
    if require_all_referenced and missing:
        raise UnprovenReferenceError(missing, kind="SPLT")

    result = list(entries)
    rewrites: list[TilePaletteRewrite] = []
    for tile_index, reference in references.items():
        new_index = effective.get(reference.palette_index)
        if new_index is None:
            continue
        patched = bytearray(entries[tile_index].data)
        struct.pack_into("<I", patched, reference.offset, new_index)
        result[tile_index] = replace(entries[tile_index], data=bytes(patched))
        rewrites.append(
            TilePaletteRewrite(
                tile_index=tile_index,
                old_index=reference.palette_index,
                new_index=new_index,
            )
        )

    return PaletteRewriteResult(
        entries=tuple(result),
        report=PaletteRelocationReport(
            mapping=tuple(sorted(normalized.items())),
            rewrites=tuple(rewrites),
        ),
    )


def analyze_art_archive(
    stock: CamArchive,
    mod: CamArchive,
    *,
    mod_id: str,
) -> ArtArchiveAnalysis:
    """Inventory TILE/SPLT deltas and prove all IMAG frame-field locations."""

    stock_tile = _required_section(stock, TILE)
    mod_tile = _required_section(mod, TILE)
    tile_delta = compute_stock_relative_delta(stock_tile, mod_tile)

    stock_palette = _optional_section(stock, SPLT)
    mod_palette = _optional_section(mod, SPLT)
    if (stock_palette is None) != (mod_palette is None):
        raise ArtFormatError(
            "Stock and mod must either both contain SPLT or both omit it"
        )
    palette_delta = (
        compute_stock_relative_delta(stock_palette, mod_palette)
        if stock_palette is not None and mod_palette is not None
        else None
    )

    imag_section = _required_section(mod, IMAG)
    parsed_images = [
        parse_imag_tile_references(
            entry.data,
            tile_count=len(mod_tile.entries),
            entry_name=entry.name,
        )
        for entry in imag_section.entries
    ]
    imag_references = tuple(
        reference
        for image in parsed_images
        for reference in image.references
    )
    referenced_tiles = {reference.tile_index for reference in imag_references}

    # A namespaced IMAG owns the nonempty TILE payloads it references even
    # when those payloads happen to match the Original Majesty ancestor.  The
    # completed source package materializes them deliberately: a later stock
    # dataset (notably DataMX/mx_interfacedata.cam) can reuse the same
    # positional slot for unrelated art.  Treating such records as disposable
    # stock copies makes that later layer leak through the generated package.
    # Promote only typed, nonempty IMAG dependencies; unrelated copied stock
    # records remain ordinary fall-through and do not bloat the output.
    changes = {change.index: change for change in tile_delta.changes}
    retained_tile_dependencies: list[int] = []
    for index in sorted(referenced_tiles):
        if index in changes:
            continue
        entry = mod_tile.entries[index]
        if not entry.data:
            continue
        stock_entry = (
            stock_tile.entries[index]
            if index < len(stock_tile.entries)
            else None
        )
        if stock_entry is None or entry.data != stock_entry.data:
            raise ArtFormatError(
                f"TILE {index} has a nonempty referenced payload missing from its "
                "stock-relative delta"
            )
        changes[index] = PositionalChange(
            index=index,
            entry=entry,
            stock_entry=stock_entry,
        )
        retained_tile_dependencies.append(index)
    if retained_tile_dependencies:
        tile_delta = replace(
            tile_delta,
            changes=tuple(changes[index] for index in sorted(changes)),
            stock_identical_count=(
                tile_delta.stock_identical_count - len(retained_tile_dependencies)
            ),
        )

    palette_references: list[TilePaletteReference] = []
    for change in tile_delta.changes:
        reference = parse_tile_palette_reference(
            change.entry.data,
            tile_index=change.index,
        )
        if reference is not None:
            palette_references.append(reference)
    referenced_palettes = {
        reference.palette_index for reference in palette_references
    }

    return ArtArchiveAnalysis(
        mod_id=mod_id,
        tile_delta=tile_delta,
        palette_delta=palette_delta,
        imag_entries=imag_section.entries,
        imag_references=imag_references,
        retained_tile_dependencies=tuple(retained_tile_dependencies),
        tile_palette_references=tuple(palette_references),
        unreferenced_tile_changes=tuple(
            index for index in tile_delta.changed_indices if index not in referenced_tiles
        ),
        unreferenced_palette_changes=(
            tuple(
                index
                for index in palette_delta.changed_indices
                if index not in referenced_palettes
            )
            if palette_delta is not None
            else ()
        ),
        supported_imag_layouts=tuple(
            sorted({layout for image in parsed_images for layout in image.layouts})
        ),
    )


def plan_art_relocation(
    analyses: Sequence[ArtArchiveAnalysis],
    *,
    tile_indices_by_mod: Mapping[str, Iterable[int]] | None = None,
    palette_indices_by_mod: Mapping[str, Iterable[int]] | None = None,
) -> tuple[PositionalAllocationReport, PositionalAllocationReport | None]:
    """Allocate deterministic private TILE and SPLT ranges for N analyses."""

    if not analyses:
        raise ArtFormatError("At least one art analysis is required")
    by_id = {analysis.mod_id: analysis for analysis in analyses}
    if len(by_id) != len(analyses):
        raise ArtFormatError("Art analysis mod IDs must be unique")

    tile_allocation = allocate_collision_free_ranges(
        {mod_id: analysis.tile_delta for mod_id, analysis in by_id.items()},
        indices_by_mod=tile_indices_by_mod,
        maximum_index=LOW16_SENTINEL - 1,
    )
    have_palettes = [analysis.palette_delta is not None for analysis in analyses]
    if any(have_palettes) and not all(have_palettes):
        raise ArtFormatError("Cannot jointly allocate archives with mixed SPLT presence")
    palette_allocation = None
    if all(have_palettes):
        palette_allocation = allocate_collision_free_ranges(
            {
                mod_id: analysis.palette_delta
                for mod_id, analysis in by_id.items()
                if analysis.palette_delta is not None
            },
            indices_by_mod=palette_indices_by_mod,
        )
    return tile_allocation, palette_allocation


def _parse_direction_layout(
    data: bytes,
    *,
    anchor: int,
    direction_end: int,
    entry_name: bytes,
    set_id: int,
    direction: int,
) -> tuple[str, int, int]:
    """Select one audited direction schema from structural discriminators."""

    if anchor + 12 > direction_end:
        raise UnsupportedImagShapeError(
            _direction_error(entry_name, set_id, direction, "is truncated")
        )

    early_count_word = _u32(data, anchor + 4)
    early_frame_count = early_count_word >> 16
    early_layer_count = early_count_word & 0xFFFF
    total_early_fields = early_frame_count * early_layer_count
    if (
        early_frame_count > 0
        and early_layer_count > 0
        and total_early_fields <= MAX_FRAMES
    ):
        if anchor + 20 > direction_end:
            raise UnsupportedImagShapeError(
                _direction_error(entry_name, set_id, direction, "is truncated")
            )
        discriminator = _u32(data, anchor + 8)
        # The direction's bit 16 control word, rather than the animation-set
        # ID, selects the extra fixed geometry pair seen in interface, actor,
        # and particle records.  This distinction is visible in stock clones:
        # AP progress bars use the 20-byte base while PHTI/ALTI use 28 bytes.
        base_header_size = 28 if _u32(data, anchor + 16) != 0 else 20
        if discriminator & ~0x7:
            raise UnsupportedImagShapeError(
                _direction_error(
                    entry_name,
                    set_id,
                    direction,
                    f"uses unsupported geometry mask {discriminator:#x}",
                )
            )
        if discriminator == 0:
            layout = "compact"
        else:
            layout = "extended"
        first_tile = anchor + base_header_size + 8 * _bit_count(discriminator)
        frame_count = total_early_fields
    else:
        if anchor + 36 > direction_end:
            raise UnsupportedImagShapeError(
                _direction_error(entry_name, set_id, direction, "is truncated")
            )
        projectile_count_word = _u32(data, anchor + 28)
        projectile_frame_count = projectile_count_word >> 16
        projectile_layer_count = projectile_count_word & 0xFFFF
        projectile_count = projectile_frame_count * projectile_layer_count
        if not (
            0 < projectile_count <= MAX_FRAMES
            and projectile_frame_count > 0
            and projectile_layer_count > 0
        ):
            raise UnsupportedImagShapeError(
                _direction_error(
                    entry_name,
                    set_id,
                    direction,
                    "matches none of compact, extended, or projectile",
                )
            )
        layout = "projectile"
        frame_count = projectile_count
        first_tile = anchor + 36

    last_reference_end = first_tile + (frame_count - 1) * 8 + 4
    if last_reference_end > direction_end:
        raise UnsupportedImagShapeError(
            _direction_error(
                entry_name,
                set_id,
                direction,
                f"declares {frame_count} {layout} frames beyond its boundary",
            )
        )
    return layout, frame_count, first_tile


def _bit_count(value: int) -> int:
    # Keep this compatible with the repository's minimum Python runtime.
    return bin(value).count("1")


def _validate_compatible_deltas(
    deltas: Mapping[str, PositionalSectionDelta],
) -> tuple[bytes, int]:
    if not deltas:
        raise ArtFormatError("At least one positional delta is required")
    extensions = {delta.extension for delta in deltas.values()}
    stock_counts = {delta.stock_count for delta in deltas.values()}
    if len(extensions) != 1 or len(stock_counts) != 1:
        raise ArtFormatError("Positional deltas must share an extension and stock count")
    return next(iter(extensions)), next(iter(stock_counts))


def _validated_low16_mapping(mapping: Mapping[int, int]) -> dict[int, int]:
    normalized: dict[int, int] = {}
    for old, new in mapping.items():
        if old < 0 or old >= LOW16_SENTINEL:
            raise ArtFormatError(f"Source TILE index {old} is outside usable low-16 range")
        if new < 0 or new >= LOW16_SENTINEL:
            raise ArtFormatError(f"Target TILE index {new} is outside usable low-16 range")
        normalized[int(old)] = int(new)
    return normalized


def _validated_u32_mapping(mapping: Mapping[int, int], *, kind: str) -> dict[int, int]:
    normalized: dict[int, int] = {}
    for old, new in mapping.items():
        if old < 0 or old > 0xFFFFFFFF:
            raise ArtFormatError(f"Source {kind} index {old} is outside u32 range")
        if new < 0 or new > 0xFFFFFFFF:
            raise ArtFormatError(f"Target {kind} index {new} is outside u32 range")
        normalized[int(old)] = int(new)
    return normalized


def _required_section(archive: CamArchive, extension: bytes) -> CamSection:
    section = _optional_section(archive, extension)
    if section is None:
        raise ArtFormatError(f"CAM archive has no {extension!r} section")
    return section


def _optional_section(archive: CamArchive, extension: bytes) -> CamSection | None:
    normalized = pad_extension(extension)
    matches = [section for section in archive.sections if section.extension == normalized]
    if len(matches) > 1:
        raise ArtFormatError(f"CAM archive has multiple {extension!r} sections")
    return matches[0] if matches else None


def _entry_name_bytes(name: str | bytes) -> bytes:
    raw = name.encode("ascii") if isinstance(name, str) else name
    if len(raw) > 20:
        raise ArtFormatError(f"IMAG entry name is longer than 20 bytes: {name!r}")
    return raw.rstrip(b"\x00")


def _display_name(name: bytes) -> str:
    return name.rstrip(b"\x00").decode("ascii", errors="replace")


def _direction_error(entry_name: bytes, set_id: int, direction: int, detail: str) -> str:
    return (
        f"IMAG {_display_name(entry_name)!r} set {set_id} direction {direction} "
        f"{detail}"
    )


def _u16(data: bytes, offset: int) -> int:
    if offset < 0 or offset + 2 > len(data):
        raise ArtFormatError(f"Unexpected EOF reading u16 at {offset}")
    return struct.unpack_from("<H", data, offset)[0]


def _u32(data: bytes, offset: int) -> int:
    if offset < 0 or offset + 4 > len(data):
        raise ArtFormatError(f"Unexpected EOF reading u32 at {offset}")
    return struct.unpack_from("<I", data, offset)[0]


def _i32(data: bytes, offset: int) -> int:
    if offset < 0 or offset + 4 > len(data):
        raise ArtFormatError(f"Unexpected EOF reading i32 at {offset}")
    return struct.unpack_from("<i", data, offset)[0]


__all__ = [
    "ArtArchiveAnalysis",
    "ArtFormatError",
    "ArtRelocationReport",
    "ImagReferenceRewrite",
    "ImagRelocationReport",
    "ImagRewriteResult",
    "ImagTileReference",
    "ModRangeAllocation",
    "PaletteRelocationReport",
    "PaletteRewriteResult",
    "ParsedImag",
    "PositionalAllocationReport",
    "PositionalChange",
    "PositionalCollision",
    "PositionalSectionDelta",
    "SlotRelocation",
    "TilePaletteReference",
    "TilePaletteRewrite",
    "UnprovenReferenceError",
    "UnsupportedImagShapeError",
    "allocate_collision_free_ranges",
    "analyze_art_archive",
    "compute_stock_relative_delta",
    "find_positional_collisions",
    "parse_imag_tile_references",
    "parse_tile_palette_reference",
    "plan_art_relocation",
    "rewrite_imag_entries",
    "rewrite_imag_tile_indices",
    "rewrite_tile_palette_indices",
    "validate_external_palette_closure",
]
