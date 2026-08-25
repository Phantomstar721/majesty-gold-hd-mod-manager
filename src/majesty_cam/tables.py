from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable, Sequence


class TableFormatError(ValueError):
    """Raised when a supported whole-table resource is malformed."""


class TableMergeConflict(ValueError):
    """Raised when mods make different changes to one semantic table row."""

    def __init__(self, table: str, key: str, owners: Sequence[str]) -> None:
        self.table = table
        self.key = key
        self.owners = tuple(owners)
        super().__init__(
            f"conflicting {table} changes for {key}: {', '.join(self.owners)}"
        )


@dataclass(frozen=True)
class BdepRow:
    building_id: str
    expression: bytes | None

    @property
    def line(self) -> bytes:
        result = self.building_id.encode("ascii")
        if self.expression is not None:
            result += b" : " + self.expression
        return result


@dataclass(frozen=True)
class BdepDelta:
    owner: str
    rows: tuple[BdepRow, ...]


@dataclass(frozen=True)
class BdepMergeResult:
    payload: bytes
    deltas: tuple[BdepDelta, ...]


_BDEP_ROW = re.compile(rb"^([A-Za-z0-9_]+)(?:\s*:\s*(.*?))?\s*$")


def parse_bdep(data: bytes) -> tuple[BdepRow, ...]:
    if b"\n" in data.replace(b"\r\n", b""):
        raise TableFormatError("BDEP must use CRLF line endings")
    if data and not data.endswith(b"\r\n"):
        raise TableFormatError("BDEP must end with CRLF")

    rows: list[BdepRow] = []
    seen: set[str] = set()
    for line_number, raw_line in enumerate(data.split(b"\r\n"), 1):
        line = raw_line.strip()
        if not line or line.startswith(b"#"):
            continue
        match = _BDEP_ROW.fullmatch(line)
        if match is None:
            raise TableFormatError(
                f"BDEP line {line_number} is not a dependency row: {raw_line!r}"
            )
        try:
            building_id = match.group(1).decode("ascii")
        except UnicodeDecodeError as exc:
            raise TableFormatError(
                f"BDEP line {line_number} has a non-ASCII building ID"
            ) from exc
        if building_id in seen:
            raise TableFormatError(f"BDEP contains duplicate row {building_id}")
        seen.add(building_id)
        rows.append(BdepRow(building_id=building_id, expression=match.group(2)))
    return tuple(rows)


def merge_bdep(
    stock: bytes, variants: Iterable[tuple[str, bytes]]
) -> BdepMergeResult:
    """Merge complete BDEP blobs as semantic row deltas against stock."""

    stock_rows = parse_bdep(stock)
    stock_map = {row.building_id: row for row in stock_rows}
    deltas: list[BdepDelta] = []
    chosen: dict[str, tuple[BdepRow, list[str]]] = {}
    addition_order: list[str] = []

    for owner, payload in variants:
        variant_rows = parse_bdep(payload)
        rows = tuple(
            row
            for row in variant_rows
            if stock_map.get(row.building_id) != row
        )
        deltas.append(BdepDelta(owner=owner, rows=rows))
        for row in rows:
            key = row.building_id
            current = chosen.get(key)
            if current is None:
                chosen[key] = (row, [owner])
                if key not in stock_map:
                    addition_order.append(key)
                continue
            if current[0] != row:
                raise TableMergeConflict("BDEP", row.building_id, (*current[1], owner))
            current[1].append(owner)

    output_rows = list(stock_rows)
    positions = {
        row.building_id: index for index, row in enumerate(output_rows)
    }
    for key, (row, _owners) in chosen.items():
        if key in positions:
            output_rows[positions[key]] = row
    for key in addition_order:
        if key not in positions:
            positions[key] = len(output_rows)
            output_rows.append(chosen[key][0])

    # Stock owns the base ordering and byte shape. Only add the semantic rows
    # that are not already represented in its exact payload.
    result = bytearray(stock)
    added = [row for row in output_rows[len(stock_rows) :]]
    if added:
        if not result.endswith(b"\r\n"):
            raise TableFormatError("stock BDEP does not end with CRLF")
        result += b"\r\n# Majesty CAM Merger generated dependencies\r\n"
        for row in added:
            result += row.line + b"\r\n"

    # Replacements of stock rows are uncommon but supported without silently
    # changing unrelated whitespace or comments: rebuild only when necessary.
    replacements = [
        row
        for index, row in enumerate(output_rows[: len(stock_rows)])
        if row != stock_rows[index]
    ]
    if replacements:
        result = bytearray()
        for row in output_rows:
            result += row.line + b"\r\n"

    return BdepMergeResult(payload=bytes(result), deltas=tuple(deltas))
