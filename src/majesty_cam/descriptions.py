from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
import re
from types import MappingProxyType
from typing import (
    Callable,
    Dict,
    Iterable,
    Mapping,
    Optional,
    Sequence,
    Tuple,
    Union,
)
import xml.etree.ElementTree as ET


DescriptionKey = Tuple[str, str]
XmlSource = Union[bytes, str]


class DescriptionFormatError(ValueError):
    """Raised when a Majesty descriptions document is not safe to merge."""


class DescriptionResolutionError(ValueError):
    """Raised when an explicit conflict resolver returns an invalid choice."""


@dataclass(frozen=True)
class DescriptionRecord:
    """One top-level ``Description`` and its semantic merge identity."""

    key: DescriptionKey
    payload: bytes = field(repr=False)
    source_index: int
    _fingerprint: tuple = field(repr=False, compare=False)

    @property
    def type(self) -> str:
        return self.key[0]

    @property
    def description_id(self) -> str:
        return self.key[1]

    def to_element(self) -> ET.Element:
        """Return a new mutable element containing this record's payload."""

        try:
            return ET.fromstring(self.payload)
        except ET.ParseError as exc:  # pragma: no cover - guarded at construction
            raise DescriptionFormatError(
                f"stored Description {self.key!r} is no longer valid XML"
            ) from exc


@dataclass(frozen=True)
class DescriptionsDocument:
    root_tag: str
    root_attributes: Tuple[Tuple[str, str], ...]
    records: Tuple[DescriptionRecord, ...]
    source: str = "<memory>"

    @property
    def index(self) -> Mapping[DescriptionKey, DescriptionRecord]:
        """A read-only, case-sensitive ``(type, ID)`` index."""

        return MappingProxyType({record.key: record for record in self.records})

    def to_bytes(self) -> bytes:
        return serialize_descriptions(self)


@dataclass(frozen=True)
class DescriptionDelta:
    owner: str
    records: Tuple[DescriptionRecord, ...]


@dataclass(frozen=True)
class DescriptionCandidate:
    owner: str
    record: DescriptionRecord


@dataclass(frozen=True)
class DescriptionConflict:
    key: DescriptionKey
    stock: Optional[DescriptionRecord]
    candidates: Tuple[DescriptionCandidate, ...]
    fields: Tuple[str, ...] = ()

    @property
    def owners(self) -> Tuple[str, ...]:
        return tuple(candidate.owner for candidate in self.candidates)


class DescriptionMergeConflict(ValueError):
    """Raised with every unresolved divergent Description change."""

    def __init__(self, conflicts: Sequence[DescriptionConflict]) -> None:
        self.conflicts = tuple(conflicts)
        summary = "; ".join(
            f"{conflict.key!r}: {', '.join(conflict.owners)}"
            + (f" (conflicting field: {', '.join(conflict.fields)})" if conflict.fields else "")
            for conflict in self.conflicts
        )
        super().__init__(f"conflicting Description changes: {summary}")


@dataclass(frozen=True)
class DescriptionSelection:
    key: DescriptionKey
    record: DescriptionRecord
    owners: Tuple[str, ...]


@dataclass(frozen=True)
class DescriptionMergeResult:
    document: DescriptionsDocument
    payload: bytes
    deltas: Tuple[DescriptionDelta, ...]
    selections: Tuple[DescriptionSelection, ...]


RecordTransform = Callable[[str, DescriptionKey, ET.Element], ET.Element]
ResolutionChoice = Union[
    str, DescriptionCandidate, DescriptionRecord, ET.Element
]
ConflictResolver = Callable[[DescriptionConflict], Optional[ResolutionChoice]]


_SUPPORTED_ROOT_TAGS = frozenset(("Majesty", "Descriptions"))
_FORBIDDEN_DECLARATION = re.compile(
    rb"<!\s*(?:DOCTYPE|ENTITY)\b", re.IGNORECASE
)
_MAX_XML_BYTES = 128 * 1024 * 1024
_MAX_ELEMENT_DEPTH = 128


def parse_descriptions(
    data: XmlSource, *, source: str = "<memory>"
) -> DescriptionsDocument:
    """Parse and validate one Majesty descriptions XML document.

    Only direct ``Description`` children are indexed. XML entities and DTDs
    are rejected before parsing, keys are case-sensitive, and duplicate keys
    fail closed even when their payloads happen to be identical.
    """

    raw = _xml_bytes(data, source)
    if len(raw) > _MAX_XML_BYTES:
        raise DescriptionFormatError(
            f"{source} exceeds the {_MAX_XML_BYTES}-byte XML safety limit"
        )
    # Majesty description resources are UTF-8/ASCII in practice. Rejecting
    # NUL-bearing encodings also prevents a UTF-16 spelling from bypassing the
    # byte-level DTD/entity guard below.
    if b"\x00" in raw:
        raise DescriptionFormatError(
            f"{source} contains NUL bytes or an unsupported UTF-16/32 encoding"
        )
    if _FORBIDDEN_DECLARATION.search(raw):
        raise DescriptionFormatError(f"{source} contains a forbidden DTD/entity")

    parser = ET.XMLParser(
        target=ET.TreeBuilder(insert_comments=True, insert_pis=True)
    )
    try:
        root = ET.fromstring(raw, parser=parser)
    except (ET.ParseError, ValueError) as exc:
        raise DescriptionFormatError(f"{source} is not valid XML: {exc}") from exc

    if root.tag not in _SUPPORTED_ROOT_TAGS:
        raise DescriptionFormatError(
            f"{source} root must be Majesty or Descriptions, got {root.tag!r}"
        )
    if root.text and root.text.strip():
        raise DescriptionFormatError(
            f"{source} has unexpected text directly inside {root.tag}"
        )

    _validate_tree_shape(root, source)
    records = []
    seen: set = set()
    for child in root:
        if child.tail and child.tail.strip():
            raise DescriptionFormatError(
                f"{source} has unexpected text between top-level elements"
            )
        if child.tag is ET.Comment:
            continue
        if child.tag is ET.ProcessingInstruction:
            raise DescriptionFormatError(
                f"{source} contains an unsupported processing instruction"
            )
        if child.tag != "Description":
            raise DescriptionFormatError(
                f"{source} contains unsupported top-level element {child.tag!r}"
            )
        record = _record_from_element(child, len(records), source)
        if record.key in seen:
            raise DescriptionFormatError(
                f"{source} contains duplicate Description key {record.key!r}"
            )
        seen.add(record.key)
        records.append(record)

    return DescriptionsDocument(
        root_tag=root.tag,
        root_attributes=tuple(root.attrib.items()),
        records=tuple(records),
        source=source,
    )


def merge_descriptions(
    stock: Union[XmlSource, DescriptionsDocument],
    variants: Iterable[
        Tuple[str, Union[XmlSource, DescriptionsDocument]]
    ],
    *,
    transform: Optional[RecordTransform] = None,
    resolve: Optional[ConflictResolver] = None,
    field_merge_stock: Optional[Mapping[DescriptionKey, DescriptionRecord]] = None,
) -> DescriptionMergeResult:
    """Merge any number of Description documents as additions/stock deltas.

    Omission from a variant means "no change"; it does not delete a stock
    record. Stock order is retained, replacements stay in their stock slot,
    and additions follow variant order then source order. Identical semantic
    changes are co-owned. Independent fields can be combined against stock;
    competing or ambiguous edits require ``resolve`` or raise a structured
    :class:`DescriptionMergeConflict`. ``field_merge_stock`` supplies additional
    baselines for conflict reconciliation only, without emitting those stock
    records or changing sparse-output ownership.

    ``transform`` receives a fresh element and is applied only to variant
    records before delta calculation. It must return a ``Description`` with
    the same key, making targeted rewrites possible without global text
    replacement.
    """

    stock_document = _as_document(stock, source="stock")
    root_attributes = list(stock_document.root_attributes)
    root_attribute_map = dict(root_attributes)
    stock_index = stock_document.index
    parsed_variants = []
    deltas = []

    for variant_index, (owner, source_value) in enumerate(variants):
        if not isinstance(owner, str) or not owner:
            raise DescriptionFormatError(
                f"variant {variant_index} has an empty/non-string owner"
            )
        document = _as_document(
            source_value, source=f"variant {owner!r} #{variant_index}"
        )
        if document.root_tag != stock_document.root_tag:
            raise DescriptionFormatError(
                f"{document.source} root {document.root_tag!r} does not match "
                f"stock root {stock_document.root_tag!r}"
            )
        _merge_root_attributes(
            root_attributes,
            root_attribute_map,
            document.root_attributes,
            document.source,
        )

        transformed_records = tuple(
            _transform_record(owner, record, transform, document.source)
            for record in document.records
        )
        changed = tuple(
            record
            for record in transformed_records
            if record.key not in stock_index
            or record._fingerprint != stock_index[record.key]._fingerprint
        )
        deltas.append(DescriptionDelta(owner=owner, records=changed))
        parsed_variants.append((owner, changed))

    candidates_by_key: Dict[DescriptionKey, list] = {}
    addition_order = []
    for owner, changed in parsed_variants:
        for record in changed:
            if record.key not in candidates_by_key:
                candidates_by_key[record.key] = []
                if record.key not in stock_index:
                    addition_order.append(record.key)
            candidates_by_key[record.key].append(
                DescriptionCandidate(owner=owner, record=record)
            )

    selected: Dict[DescriptionKey, DescriptionSelection] = {}
    unresolved = []
    for key, candidates in candidates_by_key.items():
        groups = _candidate_groups(candidates)
        if len(groups) == 1:
            group = groups[0]
            selected[key] = DescriptionSelection(
                key=key,
                record=group[0].record,
                owners=tuple(candidate.owner for candidate in group),
            )
            continue

        conflict = DescriptionConflict(
            key=key,
            stock=stock_index.get(key) or (field_merge_stock or {}).get(key),
            candidates=tuple(candidates),
        )
        choice = resolve(conflict) if resolve is not None else None
        if choice is not None:
            selected[key] = _resolve_conflict(conflict, choice)
            continue
        if conflict.stock is not None:
            try:
                selected[key] = _merge_stock_fields(conflict)
                continue
            except _FieldConflict as exc:
                conflict = DescriptionConflict(key, conflict.stock, tuple(candidates), (exc.path,))
        unresolved.append(conflict)

    if unresolved:
        raise DescriptionMergeConflict(unresolved)

    output_records = list(stock_document.records)
    positions = {
        record.key: index for index, record in enumerate(output_records)
    }
    for key, selection in selected.items():
        if key in positions:
            output_records[positions[key]] = selection.record
    for key in addition_order:
        if key not in positions:
            positions[key] = len(output_records)
            output_records.append(selected[key].record)

    output_document = DescriptionsDocument(
        root_tag=stock_document.root_tag,
        root_attributes=tuple(root_attributes),
        records=tuple(output_records),
        source="<merged>",
    )
    return DescriptionMergeResult(
        document=output_document,
        payload=serialize_descriptions(output_document),
        deltas=tuple(deltas),
        selections=tuple(selected.values()),
    )


def serialize_descriptions(document: DescriptionsDocument) -> bytes:
    """Serialize a validated descriptions document deterministically."""

    if document.root_tag not in _SUPPORTED_ROOT_TAGS:
        raise DescriptionFormatError(
            f"unsupported descriptions root {document.root_tag!r}"
        )
    root = ET.Element(document.root_tag)
    for name, value in document.root_attributes:
        if name in root.attrib:
            raise DescriptionFormatError(f"duplicate root attribute {name!r}")
        root.set(name, value)
    seen = set()
    for record in document.records:
        if record.key in seen:
            raise DescriptionFormatError(
                f"document contains duplicate Description key {record.key!r}"
            )
        seen.add(record.key)
        element = record.to_element()
        checked = _record_from_element(
            element, record.source_index, document.source
        )
        if checked.key != record.key:
            raise DescriptionFormatError(
                f"record key {record.key!r} does not match its payload "
                f"{checked.key!r}"
            )
        root.append(element)

    ET.indent(root, space="\t")
    return ET.tostring(
        root,
        encoding="utf-8",
        xml_declaration=False,
        short_empty_elements=True,
    ) + b"\n"


def _xml_bytes(data: XmlSource, source: str) -> bytes:
    if isinstance(data, bytes):
        return data
    if isinstance(data, str):
        return data.encode("utf-8")
    raise TypeError(
        f"{source} XML must be bytes or str, got {type(data).__name__}"
    )


def _as_document(
    value: Union[XmlSource, DescriptionsDocument], *, source: str
) -> DescriptionsDocument:
    if isinstance(value, DescriptionsDocument):
        # Dataclasses are intentionally easy for callers to inspect and build;
        # reparse them at the trust boundary so forged keys/fingerprints cannot
        # bypass the same validation applied to file input.
        return parse_descriptions(value.to_bytes(), source=value.source)
    return parse_descriptions(value, source=source)


def _validate_tree_shape(root: ET.Element, source: str) -> None:
    stack = [(root, 1)]
    while stack:
        element, depth = stack.pop()
        if depth > _MAX_ELEMENT_DEPTH:
            raise DescriptionFormatError(
                f"{source} exceeds the {_MAX_ELEMENT_DEPTH}-level XML depth limit"
            )
        if element.tag is ET.ProcessingInstruction:
            raise DescriptionFormatError(
                f"{source} contains an unsupported processing instruction"
            )
        if isinstance(element.tag, str) and element.tag.startswith("{"):
            raise DescriptionFormatError(
                f"{source} contains unsupported XML namespace tag {element.tag!r}"
            )
        for attribute in element.attrib:
            if attribute.startswith("{"):
                raise DescriptionFormatError(
                    f"{source} contains unsupported XML namespace attribute "
                    f"{attribute!r}"
                )
        stack.extend((child, depth + 1) for child in element)


def _record_from_element(
    element: ET.Element, source_index: int, source: str
) -> DescriptionRecord:
    _validate_tree_shape(element, source)
    if element.tag != "Description":
        raise DescriptionFormatError(
            f"{source} record {source_index} is not a Description element"
        )
    record_type = element.get("type")
    description_id = element.get("ID")
    if record_type is None or not record_type:
        raise DescriptionFormatError(
            f"{source} Description {source_index} has no non-empty type"
        )
    if description_id is None or not description_id:
        raise DescriptionFormatError(
            f"{source} Description {source_index} has no non-empty ID"
        )
    clone = deepcopy(element)
    clone.tail = None
    payload = ET.tostring(
        clone,
        encoding="utf-8",
        xml_declaration=False,
        short_empty_elements=True,
    )
    return DescriptionRecord(
        key=(record_type, description_id),
        payload=payload,
        source_index=source_index,
        _fingerprint=_element_fingerprint(clone, include_tail=False),
    )


def _element_fingerprint(
    element: ET.Element, *, include_tail: bool = True
) -> tuple:
    children = tuple(
        _element_fingerprint(child)
        for child in element
        if child.tag is not ET.Comment
    )
    return (
        element.tag,
        tuple(sorted(element.attrib.items())),
        _meaningful_text(element.text),
        children,
        _meaningful_text(element.tail) if include_tail else None,
    )


def _meaningful_text(value: Optional[str]) -> Optional[str]:
    if value is None or not value.strip():
        return None
    return value.strip()


def _transform_record(
    owner: str,
    record: DescriptionRecord,
    transform: Optional[RecordTransform],
    source: str,
) -> DescriptionRecord:
    if transform is None:
        return record
    element = record.to_element()
    transformed = transform(owner, record.key, element)
    if not isinstance(transformed, ET.Element):
        raise DescriptionFormatError(
            f"transform for {owner} {record.key!r} did not return an Element"
        )
    result = _record_from_element(
        transformed, record.source_index, f"transformed {source}"
    )
    if result.key != record.key:
        raise DescriptionFormatError(
            f"transform for {owner} changed Description key "
            f"{record.key!r} to {result.key!r}"
        )
    return result


def _merge_root_attributes(
    output: list,
    output_map: Dict[str, str],
    incoming: Sequence[Tuple[str, str]],
    source: str,
) -> None:
    for name, value in incoming:
        current = output_map.get(name)
        if current is not None and current != value:
            raise DescriptionFormatError(
                f"{source} root attribute {name!r}={value!r} conflicts with "
                f"{current!r}"
            )
        if current is None:
            output_map[name] = value
            output.append((name, value))


def _candidate_groups(
    candidates: Sequence[DescriptionCandidate],
) -> Tuple[Tuple[DescriptionCandidate, ...], ...]:
    groups: Dict[tuple, list] = {}
    order = []
    for candidate in candidates:
        fingerprint = candidate.record._fingerprint
        if fingerprint not in groups:
            groups[fingerprint] = []
            order.append(fingerprint)
        groups[fingerprint].append(candidate)
    return tuple(tuple(groups[fingerprint]) for fingerprint in order)


class _FieldConflict(Exception):
    def __init__(self, path: str) -> None:
        self.path = path


def _field_value(stock, variants, path):
    changes = set(value for value in variants if value != stock)
    if len(changes) > 1:
        raise _FieldConflict(path)
    return next(iter(changes), stock)


def _child_groups(children: Sequence[ET.Element]) -> Optional[dict[str, list[ET.Element]]]:
    """Only contiguous repeated tags have an unambiguous group position."""
    groups = {}
    previous = None
    for child in children:
        if child.tag != previous and child.tag in groups:
            return None
        groups.setdefault(child.tag, []).append(child)
        previous = child.tag
    return groups


def _merge_element_fields(
    stock: ET.Element, variants: Sequence[ET.Element], path: str
) -> ET.Element:
    fingerprint = lambda element: _element_fingerprint(element, include_tail=False)
    baseline = fingerprint(stock)
    changed = {}
    for item in variants:
        key = fingerprint(item)
        if key != baseline:
            changed[key] = item
    if not changed:
        return deepcopy(stock)
    if len(changed) == 1:
        return deepcopy(next(iter(changed.values())))
    result = ET.Element(stock.tag)
    for name in sorted(set(stock.attrib).union(*(item.attrib for item in variants))):
        value = _field_value(stock.get(name), (item.get(name) for item in variants), path + "/@" + name)
        if value is not None:
            result.set(name, value)
    result.text = _field_value(_meaningful_text(stock.text),
                               (_meaningful_text(item.text) for item in variants), path + "/text()")
    rows = [tuple(child for child in item if child.tag is not ET.Comment) for item in (stock, *variants)]
    row_keys = [tuple(_element_fingerprint(child) for child in row) for row in rows]
    changed_rows = {key: row for key, row in zip(row_keys[1:], rows[1:]) if key != row_keys[0]}
    if len(changed_rows) <= 1:
        result.extend(deepcopy(next(iter(changed_rows.values()), rows[0])))
        return result
    # Mixed text and noncontiguous repeated tags have no unique field address.
    # Leave their entire ordered child sequence atomic instead of guessing.
    if (any(_meaningful_text(child.tail) is not None for row in rows for child in row)
            or any(_meaningful_text(item.text) is not None for item in (stock, *variants))):
        raise _FieldConflict(path + "/children()")
    groups = [_child_groups(row) for row in rows]
    if any(group is None for group in groups):
        raise _FieldConflict(path + "/children()")
    base, *incoming = groups
    merged = {}
    for tag in sorted(set(base).union(*(item for item in incoming))):
        original = base.get(tag, [])
        alternatives = [item.get(tag, []) for item in incoming]
        field_path = path + "/" + tag
        if len(original) == 1 and all(len(row) == 1 for row in alternatives):
            merged[tag] = (_merge_element_fields(original[0], [row[0] for row in alternatives], field_path),)
        else:
            # Add/delete and repeated sibling groups are atomic. In particular,
            # two different edits to a newly added subtree have no stock base.
            original_key = tuple(fingerprint(child) for child in original)
            choices = {tuple(fingerprint(child) for child in row): row for row in alternatives}
            key = _field_value(original_key, choices, field_path)
            chosen = choices.get(key, original)
            if chosen:
                merged[tag] = tuple(deepcopy(child) for child in chosen)
    # Preserve the authored relative order. Combining insertions is safe only
    # when the source constraints determine a unique order, without cycles.
    predecessors = {tag: set() for tag in merged}
    for group in groups:
        order = [tag for tag in group if tag in merged]
        for first, second in zip(order, order[1:]):
            predecessors[second].add(first)
    while predecessors:
        ready = [tag for tag, before in predecessors.items() if not before]
        if len(ready) != 1:
            raise _FieldConflict(path + "/child-order()")
        tag = ready[0]
        result.extend(merged[tag])
        del predecessors[tag]
        for before in predecessors.values():
            before.discard(tag)
    return result


def _merge_stock_fields(conflict: DescriptionConflict) -> DescriptionSelection:
    assert conflict.stock is not None
    stock = _record_from_element(conflict.stock.to_element(), conflict.stock.source_index, "stock field baseline")
    if stock.key != conflict.key:
        raise DescriptionFormatError(f"stock field baseline key {stock.key!r} does not match {conflict.key!r}")
    element = _merge_element_fields(stock.to_element(),
                                    [candidate.record.to_element() for candidate in conflict.candidates],
                                    "Description")
    record = _record_from_element(element, stock.source_index, "stock-relative field merge")
    return DescriptionSelection(conflict.key, record, tuple(
        candidate.owner for candidate in conflict.candidates
        if candidate.record._fingerprint != stock._fingerprint
    ))


def _resolve_conflict(
    conflict: DescriptionConflict, choice: ResolutionChoice
) -> DescriptionSelection:
    if isinstance(choice, str):
        matching = [
            candidate
            for candidate in conflict.candidates
            if candidate.owner == choice
        ]
        fingerprints = {
            candidate.record._fingerprint for candidate in matching
        }
        if not matching:
            raise DescriptionResolutionError(
                f"resolver selected unknown owner {choice!r} for {conflict.key!r}"
            )
        if len(fingerprints) != 1:
            raise DescriptionResolutionError(
                f"owner {choice!r} has multiple divergent candidates for "
                f"{conflict.key!r}; return a DescriptionCandidate instead"
            )
        record = matching[0].record
        owners = tuple(
            candidate.owner
            for candidate in conflict.candidates
            if candidate.record._fingerprint == record._fingerprint
        )
        return DescriptionSelection(conflict.key, record, owners)

    if isinstance(choice, DescriptionCandidate):
        if choice not in conflict.candidates:
            raise DescriptionResolutionError(
                f"resolver returned a candidate outside conflict {conflict.key!r}"
            )
        return DescriptionSelection(conflict.key, choice.record, (choice.owner,))

    if isinstance(choice, ET.Element):
        record = _record_from_element(choice, -1, "explicit resolution")
        owners = ("<resolution>",)
    elif isinstance(choice, DescriptionRecord):
        record = _record_from_element(
            choice.to_element(), choice.source_index, "explicit resolution"
        )
        owners = ("<resolution>",)
    else:  # pragma: no cover - typing plus explicit branches above
        raise DescriptionResolutionError(
            f"resolver returned unsupported {type(choice).__name__} for "
            f"{conflict.key!r}"
        )

    if record.key != conflict.key:
        raise DescriptionResolutionError(
            f"resolver returned key {record.key!r} for conflict {conflict.key!r}"
        )
    return DescriptionSelection(conflict.key, record, owners)
