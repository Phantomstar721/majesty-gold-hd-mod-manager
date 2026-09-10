from __future__ import annotations

from dataclasses import dataclass
import struct
from typing import Iterable, Literal, Mapping, Sequence


StrtKeyMode = Literal["id", "index"]


class StrtFormatError(ValueError):
    """Raised when an STRT payload is malformed."""


class StrtMergeConflict(ValueError):
    """Raised when mods make different changes to the same semantic string."""

    def __init__(self, key: int, owners: Sequence[str]) -> None:
        self.key = key
        self.owners = tuple(owners)
        super().__init__(
            f"conflicting STRT changes for key {key}: {', '.join(self.owners)}"
        )


class StrtAncestryError(ValueError):
    """Raised when a complete STRT table's stock ancestor is ambiguous."""


@dataclass(frozen=True)
class StrtRecord:
    string_id: int
    text: bytes


@dataclass(frozen=True)
class StrtTable:
    version: bytes
    records: tuple[StrtRecord, ...]

    def __post_init__(self) -> None:
        if len(self.version) != 2:
            raise StrtFormatError("STRT version must be exactly two bytes")
        for record in self.records:
            if not 0 <= record.string_id <= 0xFFFFFFFF:
                raise StrtFormatError(
                    f"STRT string ID is outside the uint32 range: {record.string_id}"
                )
            if b"\x00" in record.text:
                raise StrtFormatError("STRT strings cannot contain embedded NUL bytes")

    def to_bytes(self) -> bytes:
        if len(self.records) > 0xFFFF:
            raise StrtFormatError("STRT record count exceeds uint16 capacity")

        output = bytearray(struct.pack("<H", len(self.records)) + self.version)
        output += b"\x00\x00\x00\x00" * len(self.records)
        offsets: list[int] = []
        for record in self.records:
            offsets.append(len(output))
            output += struct.pack("<I", record.string_id)
            output += record.text
            output += b"\x00"
        for index, offset in enumerate(offsets):
            struct.pack_into("<I", output, 4 + index * 4, offset)
        return bytes(output)


@dataclass(frozen=True)
class StrtDelta:
    owner: str
    changes: tuple[tuple[int, StrtRecord], ...]


@dataclass(frozen=True)
class StrtRowResolution:
    record: StrtRecord
    participant_owners: frozenset[str]

    def __post_init__(self) -> None:
        if not self.participant_owners:
            raise ValueError("STRT row resolution participants cannot be empty")


@dataclass(frozen=True)
class StrtStockRelativeProof:
    """One provider's effective delta and every equally valid maximal ancestry."""

    delta: StrtDelta
    candidate_ancestors: tuple[tuple[str, StrtTable], ...]


def parse_strt(data: bytes) -> StrtTable:
    if len(data) < 4:
        raise StrtFormatError("STRT payload is shorter than its count/version header")
    count = struct.unpack_from("<H", data, 0)[0]
    header_end = 4 + count * 4
    if header_end > len(data):
        raise StrtFormatError("STRT offset table extends beyond the payload")

    offsets = struct.unpack_from(f"<{count}I", data, 4) if count else ()
    records: list[StrtRecord] = []
    previous_offset = header_end - 1
    for index, offset in enumerate(offsets):
        if offset < header_end or offset + 4 > len(data):
            raise StrtFormatError(
                f"STRT record {index} has an out-of-bounds offset: {offset}"
            )
        if offset <= previous_offset:
            raise StrtFormatError("STRT record offsets are not strictly increasing")
        try:
            end = data.index(b"\x00", offset + 4)
        except ValueError as exc:
            raise StrtFormatError(f"STRT record {index} is not NUL terminated") from exc
        records.append(
            StrtRecord(
                string_id=struct.unpack_from("<I", data, offset)[0],
                text=data[offset + 4 : end],
            )
        )
        previous_offset = offset
    return StrtTable(version=data[2:4], records=tuple(records))


def strt_delta(
    base: StrtTable,
    modified: StrtTable,
    *,
    owner: str,
    key_mode: StrtKeyMode,
) -> StrtDelta:
    _require_compatible_versions(base, modified, owner)
    base_semantic_items = _semantic_items(base, key_mode)
    modified_items = _semantic_items(modified, key_mode)
    _require_complete_stock_rows(
        base,
        modified,
        owner=owner,
        key_mode=key_mode,
        base_items=base_semantic_items,
        modified_items=modified_items,
    )
    base_items = dict(base_semantic_items)
    changes = tuple(
        (key, record)
        for key, record in modified_items
        if base_items.get(key) != record
        and not (
            key_mode == "index"
            and key >= len(base.records)
            and record.string_id == key
            and record.text == b""
        )
    )
    return StrtDelta(owner=owner, changes=changes)


def merge_strt(
    base: StrtTable,
    variants: Iterable[tuple[str, StrtTable]],
    *,
    key_mode: StrtKeyMode,
    resolutions: Mapping[int, StrtRowResolution] | None = None,
) -> tuple[StrtTable, tuple[StrtDelta, ...]]:
    """Merge any number of complete STRT tables as deltas against stock.

    Identical changes from multiple mods are co-owned and accepted. Different
    changes to the same semantic key fail closed and require an explicit
    higher-level resolution.
    """

    deltas = tuple(
        strt_delta(base, table, owner=owner, key_mode=key_mode)
        for owner, table in variants
    )
    return _merge_strt_deltas(
        base,
        deltas,
        key_mode=key_mode,
        resolutions=resolutions,
    )


def merge_strt_stock_relative(
    effective_stock: StrtTable,
    stock_ancestors: Sequence[tuple[str, StrtTable]],
    variants: Iterable[tuple[str, StrtTable]],
    *,
    key_mode: StrtKeyMode,
    resolutions: Mapping[int, StrtRowResolution] | None = None,
) -> tuple[StrtTable, tuple[StrtDelta, ...]]:
    """Merge complete STRT tables after proving each provider's stock lineage.

    A provider built from an older, smaller stock table contributes only the
    rows it changed relative to that ancestor; newer effective-stock rows are
    retained. A provider carrying a newer complete topology is instead diffed
    against that newer ancestor, preserving intentional reversions. When
    multiple maximal ancestries could explain the table, every interpretation
    must produce the same effective result or the merge fails closed.
    """

    ancestors = tuple(stock_ancestors)
    if not ancestors:
        raise StrtAncestryError("STRT stock ancestry list is empty")
    for label, ancestor in ancestors:
        _require_compatible_versions(effective_stock, ancestor, label)

    proofs = tuple(
        prove_strt_stock_relative_delta(
            owner,
            table,
            effective_stock,
            ancestors,
            key_mode=key_mode,
        )
        for owner, table in variants
    )
    deltas = tuple(proof.delta for proof in proofs)
    return _merge_strt_deltas(
        effective_stock,
        deltas,
        key_mode=key_mode,
        resolutions=resolutions,
    )


def prove_strt_stock_relative_delta(
    owner: str,
    package: StrtTable,
    effective_stock: StrtTable,
    ancestors: Sequence[tuple[str, StrtTable]],
    *,
    key_mode: StrtKeyMode,
) -> StrtStockRelativeProof:
    _require_compatible_versions(effective_stock, package, owner)
    package_keys = _strt_topology(package, key_mode)
    package_key_set = frozenset(package_keys)
    covered = tuple(
        (
            label,
            ancestor,
            _strt_topology(ancestor, key_mode),
        )
        for label, ancestor in ancestors
        if frozenset(_strt_topology(ancestor, key_mode)) <= package_key_set
    )
    ordered = tuple(
        (label, ancestor, keys, frozenset(keys))
        for label, ancestor, keys in covered
        if _ordered_subset(keys, package_keys)
    )
    blocking_misordered = tuple(
        label
        for label, _ancestor, keys in covered
        if not _ordered_subset(keys, package_keys)
        and not any(
            frozenset(keys) <= ordered_key_set
            for _label, _table, _ordered_keys, ordered_key_set in ordered
        )
    )
    if blocking_misordered:
        raise StrtAncestryError(
            f"{owner}: STRT contains the complete "
            f"{'/'.join(blocking_misordered)} row set but does not preserve "
            "its stock ordering"
        )
    if not ordered:
        labels = ", ".join(label for label, _ancestor in ancestors)
        raise StrtAncestryError(
            f"{owner}: STRT is not a complete table based on any installed "
            f"stock lineage ({labels})"
        )

    possible = tuple(
        candidate
        for candidate in ordered
        if not any(
            candidate[3] < other[3]
            for other in ordered
        )
    )
    outcomes: list[tuple[str, StrtTable]] = []
    for label, ancestor, _keys, _key_set in possible:
        delta = strt_delta(
            ancestor,
            package,
            owner=owner,
            key_mode=key_mode,
        )
        outcomes.append(
            (
                label,
                _apply_strt_changes(
                    effective_stock,
                    delta.changes,
                    key_mode=key_mode,
                ),
            )
        )

    first_outcome = outcomes[0][1]
    if any(outcome != first_outcome for _label, outcome in outcomes[1:]):
        labels = ", ".join(label for label, _outcome in outcomes)
        differing = _different_strt_outcome_keys(
            tuple(outcome for _label, outcome in outcomes),
            key_mode=key_mode,
        )
        suffix = f" ({', '.join(differing)})" if differing else ""
        raise StrtAncestryError(
            f"{owner}: STRT stock ancestry is ambiguous between {labels}; "
            f"choosing an ancestor would change effective rows{suffix}"
        )
    return StrtStockRelativeProof(
        delta=strt_delta(
            effective_stock,
            first_outcome,
            owner=owner,
            key_mode=key_mode,
        ),
        candidate_ancestors=tuple(
            (label, ancestor)
            for label, ancestor, _keys, _key_set in possible
        ),
    )


def _strt_topology(table: StrtTable, key_mode: StrtKeyMode) -> tuple[int, ...]:
    return tuple(key for key, _record in _semantic_items(table, key_mode))


def _ordered_subset(required: Sequence[int], available: Sequence[int]) -> bool:
    cursor = iter(available)
    return all(any(candidate == item for candidate in cursor) for item in required)


def _apply_strt_changes(
    base: StrtTable,
    changes: Sequence[tuple[int, StrtRecord]],
    *,
    key_mode: StrtKeyMode,
) -> StrtTable:
    records = list(base.records)
    if key_mode == "index":
        if changes:
            last_index = max(key for key, _record in changes)
            while len(records) <= last_index:
                index = len(records)
                records.append(StrtRecord(string_id=index, text=b""))
        for index, record in changes:
            records[index] = record
        return StrtTable(version=base.version, records=tuple(records))
    if key_mode != "id":
        raise ValueError(f"unsupported STRT key mode: {key_mode!r}")

    positions = {record.string_id: index for index, record in enumerate(records)}
    for key, record in changes:
        position = positions.get(key)
        if position is None:
            positions[key] = len(records)
            records.append(record)
        else:
            records[position] = record
    return StrtTable(version=base.version, records=tuple(records))


def _different_strt_outcome_keys(
    outcomes: Sequence[StrtTable],
    *,
    key_mode: StrtKeyMode,
) -> tuple[str, ...]:
    maps = tuple(dict(_semantic_items(outcome, key_mode)) for outcome in outcomes)
    keys = set().union(*(mapping for mapping in maps))
    differing = sorted(
        key
        for key in keys
        if len({mapping.get(key) for mapping in maps}) > 1
    )
    if key_mode == "index":
        return tuple(f"row {key}" for key in differing)
    return tuple(f"0x{key:08X}" for key in differing)


def _merge_strt_deltas(
    base: StrtTable,
    deltas: Sequence[StrtDelta],
    *,
    key_mode: StrtKeyMode,
    resolutions: Mapping[int, StrtRowResolution] | None = None,
) -> tuple[StrtTable, tuple[StrtDelta, ...]]:
    resolution_map = dict(resolutions or {})
    chosen: dict[int, tuple[StrtRecord, list[str]]] = {}
    addition_order: list[int] = []
    base_keys = {key for key, _ in _semantic_items(base, key_mode)}
    changed_owners: dict[int, set[str]] = {}

    for delta in deltas:
        for key, record in delta.changes:
            changed_owners.setdefault(key, set()).add(delta.owner)
            resolution = resolution_map.get(key)
            if resolution is not None and delta.owner in resolution.participant_owners:
                record = resolution.record
            existing = chosen.get(key)
            if existing is None:
                chosen[key] = (record, [delta.owner])
                if key not in base_keys:
                    addition_order.append(key)
                continue
            if existing[0] != record:
                raise StrtMergeConflict(key, (*existing[1], delta.owner))
            existing[1].append(delta.owner)

    for key, resolution in resolution_map.items():
        missing = resolution.participant_owners.difference(
            changed_owners.get(key, set())
        )
        if missing:
            raise StrtMergeConflict(key, tuple(sorted(missing)))

    if key_mode == "index":
        records = list(base.records)
        if chosen:
            last_index = max(chosen)
            while len(records) <= last_index:
                index = len(records)
                records.append(StrtRecord(string_id=index, text=b""))
        for index, (record, _owners) in chosen.items():
            records[index] = record
        result = StrtTable(version=base.version, records=tuple(records))
    else:
        records = list(base.records)
        positions = {record.string_id: i for i, record in enumerate(records)}
        for key, (record, _owners) in chosen.items():
            if key in positions:
                records[positions[key]] = record
        for key in addition_order:
            if key not in positions:
                positions[key] = len(records)
                records.append(chosen[key][0])
        result = StrtTable(version=base.version, records=tuple(records))

    return result, tuple(deltas)


def _semantic_items(
    table: StrtTable, key_mode: StrtKeyMode
) -> tuple[tuple[int, StrtRecord], ...]:
    if key_mode == "index":
        return tuple(enumerate(table.records))
    if key_mode != "id":
        raise ValueError(f"unsupported STRT key mode: {key_mode!r}")
    seen: set[int] = set()
    items: list[tuple[int, StrtRecord]] = []
    for record in table.records:
        if record.string_id in seen:
            raise StrtFormatError(
                f"STRT contains duplicate semantic ID 0x{record.string_id:08X}"
            )
        seen.add(record.string_id)
        items.append((record.string_id, record))
    return tuple(items)


def _require_compatible_versions(
    base: StrtTable, modified: StrtTable, owner: str
) -> None:
    if modified.version != base.version:
        raise StrtFormatError(
            f"{owner} STRT version {modified.version.hex()} does not match "
            f"stock {base.version.hex()}"
        )


def _require_complete_stock_rows(
    base: StrtTable,
    modified: StrtTable,
    *,
    owner: str,
    key_mode: StrtKeyMode,
    base_items: Sequence[tuple[int, StrtRecord]],
    modified_items: Sequence[tuple[int, StrtRecord]],
) -> None:
    if key_mode == "index":
        if len(modified.records) < len(base.records):
            raise StrtFormatError(
                f"{owner} STRT table is truncated ({len(modified.records)} rows; "
                f"stock has {len(base.records)}); complete positional tables are "
                "required"
            )
        return

    modified_keys = {key for key, _record in modified_items}
    missing = [key for key, _record in base_items if key not in modified_keys]
    if missing:
        formatted = ", ".join(f"0x{key:08X}" for key in missing)
        raise StrtFormatError(
            f"{owner} STRT table omits stock semantic ID(s): {formatted}; "
            "complete ID-addressed tables are required"
        )
