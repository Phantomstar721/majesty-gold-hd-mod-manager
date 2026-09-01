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


class TableAncestryError(ValueError):
    """Raised when a complete table's stock ancestor cannot be proven safely."""


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

    for owner, payload in variants:
        variant_rows = parse_bdep(payload)
        rows = tuple(
            row
            for row in variant_rows
            if stock_map.get(row.building_id) != row
        )
        deltas.append(BdepDelta(owner=owner, rows=rows))

    return _merge_bdep_deltas(stock, deltas)


def merge_bdep_stock_relative(
    effective_stock: bytes,
    stock_ancestors: Sequence[tuple[str, bytes]],
    variants: Iterable[tuple[str, bytes]],
) -> BdepMergeResult:
    """Merge complete BDEP tables after proving each package's stock lineage.

    Gold HD ships distinct complete Original and Northern Expansion BDEP
    tables.  A package authored from Original must contribute only its real
    changes; Original rows which Northern Expansion changed are not package
    replacements.  Conversely, a package which intentionally changes an MX
    row back to its Original value must not lose that change merely because an
    Original table also exists.

    A stock table is a possible ancestor only when every one of its row IDs is
    present in stock order in the package table.  Strict-subset ancestors are
    then discarded: carrying the complete newer topology makes differences
    from that newer table intentional replacements.  Each remaining maximal
    ancestor's semantic delta is applied to the effective installed table. If
    incomparable or same-topology ancestries produce different results, intent
    is unknowable and the merge fails closed instead of guessing.
    """

    effective_rows = parse_bdep(effective_stock)
    ancestors = tuple(
        (label, parse_bdep(payload)) for label, payload in stock_ancestors
    )
    if not ancestors:
        raise TableAncestryError("BDEP stock ancestry list is empty")

    deltas = tuple(
        _resolve_bdep_stock_relative_delta(
            owner,
            parse_bdep(payload),
            effective_rows,
            ancestors,
        )
        for owner, payload in variants
    )
    return _merge_bdep_deltas(effective_stock, deltas)


def _resolve_bdep_stock_relative_delta(
    owner: str,
    package_rows: Sequence[BdepRow],
    effective_rows: Sequence[BdepRow],
    ancestors: Sequence[tuple[str, Sequence[BdepRow]]],
) -> BdepDelta:
    package_ids = tuple(row.building_id for row in package_rows)
    package_id_set = frozenset(package_ids)
    covered = tuple(
        (
            label,
            rows,
            tuple(row.building_id for row in rows),
            frozenset(row.building_id for row in rows),
        )
        for label, rows in ancestors
        if frozenset(row.building_id for row in rows) <= package_id_set
    )
    ordered = tuple(
        (label, rows, id_set)
        for label, rows, ids, id_set in covered
        if _ordered_subset(ids, package_ids)
    )
    blocking_misordered = tuple(
        label
        for label, _rows, ids, id_set in covered
        if not _ordered_subset(ids, package_ids)
        and not any(id_set <= ordered_id_set for _a, _b, ordered_id_set in ordered)
    )
    if blocking_misordered:
        raise TableAncestryError(
            f"{owner}: BDEP contains the complete "
            f"{'/'.join(blocking_misordered)} row "
            "set but does not preserve its stock ordering"
        )
    possible = ordered
    if not possible:
        labels = ", ".join(label for label, _rows in ancestors)
        raise TableAncestryError(
            f"{owner}: BDEP is not a complete table based on any installed "
            f"stock lineage ({labels})"
        )

    # Prefer the most complete stock topology the package actually carries.
    # Original is a strict ordered subset of Northern Expansion, so a package
    # which carries every MX row is an MX-effective table and every differing
    # value is an intentional replacement.  A package which omits MX-only rows
    # cannot be treated as MX and falls through to Original.  Incomparable (or
    # same-topology) ancestors remain candidates and must agree below.
    possible = tuple(
        candidate
        for candidate in possible
        if not any(
            candidate[2] < other[2]
            for other in possible
        )
    )

    outcomes: list[tuple[str, tuple[BdepRow, ...]]] = []
    for label, baseline_rows, _id_set in possible:
        baseline_map = {row.building_id: row for row in baseline_rows}
        package_delta = tuple(
            row
            for row in package_rows
            if baseline_map.get(row.building_id) != row
        )
        outcomes.append(
            (label, _apply_bdep_rows(effective_rows, package_delta))
        )

    first_outcome = outcomes[0][1]
    if any(outcome != first_outcome for _label, outcome in outcomes[1:]):
        labels = ", ".join(label for label, _outcome in outcomes)
        differing = _different_bdep_outcome_keys(
            tuple(outcome for _label, outcome in outcomes)
        )
        suffix = f" ({', '.join(differing)})" if differing else ""
        raise TableAncestryError(
            f"{owner}: BDEP stock ancestry is ambiguous between {labels}; "
            f"choosing an ancestor would change effective rows{suffix}"
        )

    effective_map = {row.building_id: row for row in effective_rows}
    rows = tuple(
        row
        for row in first_outcome
        if effective_map.get(row.building_id) != row
    )
    return BdepDelta(owner=owner, rows=rows)


def _ordered_subset(required: Sequence[str], available: Sequence[str]) -> bool:
    cursor = iter(available)
    return all(any(candidate == item for candidate in cursor) for item in required)


def _apply_bdep_rows(
    stock_rows: Sequence[BdepRow], rows: Sequence[BdepRow]
) -> tuple[BdepRow, ...]:
    output = list(stock_rows)
    positions = {row.building_id: index for index, row in enumerate(output)}
    for row in rows:
        position = positions.get(row.building_id)
        if position is None:
            positions[row.building_id] = len(output)
            output.append(row)
        else:
            output[position] = row
    return tuple(output)


def _different_bdep_outcome_keys(
    outcomes: Sequence[Sequence[BdepRow]],
) -> tuple[str, ...]:
    maps = tuple(
        {row.building_id: row for row in outcome}
        for outcome in outcomes
    )
    keys = set().union(*(mapping for mapping in maps))
    return tuple(
        sorted(
            key
            for key in keys
            if len({mapping.get(key) for mapping in maps}) > 1
        )
    )


def _merge_bdep_deltas(
    stock: bytes, deltas: Sequence[BdepDelta]
) -> BdepMergeResult:
    stock_rows = parse_bdep(stock)
    stock_map = {row.building_id: row for row in stock_rows}
    chosen: dict[str, tuple[BdepRow, list[str]]] = {}
    addition_order: list[str] = []

    for delta in deltas:
        owner = delta.owner
        for row in delta.rows:
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
