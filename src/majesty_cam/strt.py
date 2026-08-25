from __future__ import annotations

from dataclasses import dataclass
import struct
from typing import Iterable, Literal, Sequence


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
    base_items = dict(_semantic_items(base, key_mode))
    modified_items = _semantic_items(modified, key_mode)
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
    chosen: dict[int, tuple[StrtRecord, list[str]]] = {}
    addition_order: list[int] = []
    base_keys = {key for key, _ in _semantic_items(base, key_mode)}

    for delta in deltas:
        for key, record in delta.changes:
            existing = chosen.get(key)
            if existing is None:
                chosen[key] = (record, [delta.owner])
                if key not in base_keys:
                    addition_order.append(key)
                continue
            if existing[0] != record:
                raise StrtMergeConflict(key, (*existing[1], delta.owner))
            existing[1].append(delta.owner)

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

    return result, deltas


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
