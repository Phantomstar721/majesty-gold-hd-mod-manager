from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import hashlib
from pathlib import Path
import re
from typing import Mapping, Sequence
import xml.etree.ElementTree as ET


StringKey = tuple[str, str]


class StringsFormatError(ValueError):
    pass


@dataclass(frozen=True)
class StringRecord:
    key: StringKey
    payload: bytes
    source_index: int

    def to_element(self) -> ET.Element:
        try:
            return ET.fromstring(self.payload)
        except ET.ParseError as exc:  # pragma: no cover - validated on input
            raise StringsFormatError(f"stored Strings record {self.key!r} is invalid") from exc


@dataclass(frozen=True)
class StringsDocument:
    records: tuple[StringRecord, ...]
    source: str

    @property
    def index(self) -> Mapping[StringKey, StringRecord]:
        return {record.key: record for record in self.records}


@dataclass(frozen=True)
class StringCandidate:
    owner: str
    record: StringRecord


@dataclass(frozen=True)
class StringConflict:
    key: StringKey
    candidates: tuple[StringCandidate, ...]


@dataclass(frozen=True)
class StringsMergeResult:
    payload: bytes
    records: tuple[StringRecord, ...]
    conflicts: tuple[StringConflict, ...]


def parse_strings(data: bytes | str, *, source: str = "<memory>") -> StringsDocument:
    """Parse the exact XML overlay consumed by Majesty's ``Strings`` loader.

    The stock loader accepts ``Majesty/Language/Text`` records. It applies
    duplicate IDs in file order, so the final occurrence is the effective one.
    Other text formats (notably ``.qdd`` quest descriptions) are not Strings
    dictionaries even when an old mod accidentally points this directive at one.
    """

    raw = data.encode("utf-8") if isinstance(data, str) else data
    if b"\x00" in raw:
        raise StringsFormatError(f"{source} contains an unsupported UTF-16/32 encoding")
    upper = raw.upper()
    if b"<!DOCTYPE" in upper or b"<!ENTITY" in upper:
        raise StringsFormatError(f"{source} contains a forbidden DTD/entity")
    try:
        root = ET.fromstring(raw)
    except (ET.ParseError, ValueError) as exc:
        raise StringsFormatError(f"{source} is not a valid Majesty Strings XML table") from exc
    if root.tag != "Majesty":
        raise StringsFormatError(f"{source} Strings root must be Majesty")

    effective: dict[StringKey, StringRecord] = {}
    order: list[StringKey] = []
    source_index = 0
    for child in root:
        if child.tag != "Language":
            # Whitespace and comments are not Elements in the default parser;
            # actual top-level elements outside the stock grammar are unsafe.
            raise StringsFormatError(
                f"{source} Strings table contains unsupported {child.tag!r}"
            )
        language = (child.get("id") or "").strip()
        if not language:
            raise StringsFormatError(f"{source} has a Language without id")
        for entry in child:
            if entry.tag != "Text":
                raise StringsFormatError(
                    f"{source} Language {language!r} contains unsupported {entry.tag!r}"
                )
            entry_id = (entry.get("id") or "").strip()
            if not entry_id:
                raise StringsFormatError(
                    f"{source} Language {language!r} has Text without id"
                )
            key = (language, entry_id)
            clone = deepcopy(entry)
            clone.tail = None
            record = StringRecord(
                key=key,
                payload=ET.tostring(clone, encoding="utf-8", short_empty_elements=True),
                source_index=source_index,
            )
            source_index += 1
            if key not in effective:
                order.append(key)
            effective[key] = record
    return StringsDocument(tuple(effective[key] for key in order), source)


def merge_strings(
    variants: Sequence[tuple[str, StringsDocument]],
    *,
    resolutions: Mapping[StringKey, StringRecord] | None = None,
) -> StringsMergeResult:
    candidates: dict[StringKey, list[StringCandidate]] = {}
    order: list[StringKey] = []
    for owner, document in variants:
        for record in document.records:
            if record.key not in candidates:
                candidates[record.key] = []
                order.append(record.key)
            candidates[record.key].append(StringCandidate(owner, record))

    selected: list[StringRecord] = []
    conflicts: list[StringConflict] = []
    supplied = dict(resolutions or {})
    used: set[StringKey] = set()
    for key in order:
        values = candidates[key]
        groups: dict[bytes, list[StringCandidate]] = {}
        for candidate in values:
            groups.setdefault(candidate.record.payload, []).append(candidate)
        if len(groups) == 1:
            selected.append(values[-1].record)
            continue
        resolution = supplied.get(key)
        if resolution is None:
            conflicts.append(StringConflict(key, tuple(values)))
            continue
        if resolution.key != key:
            raise StringsFormatError(
                f"Strings resolution key {resolution.key!r} does not match {key!r}"
            )
        if resolution.payload not in groups:
            raise StringsFormatError(f"Strings resolution for {key!r} is not a candidate")
        selected.append(resolution)
        used.add(key)
    unused = set(supplied) - used
    if unused:
        raise StringsFormatError(f"Strings resolutions name no conflict: {sorted(unused)!r}")
    if conflicts:
        return StringsMergeResult(b"", tuple(selected), tuple(conflicts))
    records = tuple(selected)
    return StringsMergeResult(serialize_string_records(records), records, ())


def load_strings(path: Path) -> StringsDocument:
    return parse_strings(path.read_bytes(), source=str(path))


def load_effective_stock_strings(
    game_path: Path,
) -> tuple[StringsDocument, tuple[tuple[str, str], ...]]:
    """Load Majesty's installed Strings dictionaries in dataset load order.

    Both the manifests and every manifest-declared Strings file are hashed so
    callers can bind reconciliation to the exact installed ancestry they read.
    Later files replace earlier rows exactly as Majesty's dictionary loader
    does, while the first occurrence retains deterministic output order.
    """

    root = game_path.resolve(strict=True)
    if not root.is_dir():
        raise StringsFormatError(f"installed game path is not a directory: {root}")
    manifests = (
        root / "Data" / "MajestyDatasetDefinitions.xml",
        root / "DataMX" / "MajestyExpansionDatasetDefinitions.xml",
    )
    variable_roots = {
        "majestydatapath": root / "Data",
        "majestyexpansiondatapath": root / "DataMX",
    }
    effective: dict[StringKey, StringRecord] = {}
    order: list[StringKey] = []
    hashed: dict[str, str] = {}

    for manifest in manifests:
        if not manifest.is_file() or manifest.is_symlink():
            raise StringsFormatError(
                f"stock dataset definition was not found or is unsafe: {manifest}"
            )
        payload = manifest.read_bytes()
        hashed[str(manifest)] = hashlib.sha256(payload).hexdigest()
        try:
            document = ET.fromstring(payload)
        except (ET.ParseError, ValueError) as exc:
            raise StringsFormatError(
                f"stock dataset definition could not be read: {manifest}"
            ) from exc
        for node in document.findall(".//Dataset/Load/Strings"):
            declared = (node.text or "").strip()
            if not declared:
                raise StringsFormatError(
                    f"stock dataset definition contains an empty Strings path: {manifest}"
                )
            variable = re.fullmatch(r"\$\(([^)]+)\)[\\/](.+)", declared)
            if variable is not None:
                parent = variable_roots.get(variable.group(1).casefold())
                if parent is None:
                    raise StringsFormatError(
                        f"unsupported stock Strings path variable in {manifest}: "
                        f"{declared}"
                    )
                relative = Path(variable.group(2).replace("\\", "/"))
            else:
                parent = manifest.parent
                relative = Path(declared.replace("\\", "/"))
            if relative.is_absolute() or ".." in relative.parts:
                raise StringsFormatError(
                    f"unsafe stock Strings path in {manifest}: {declared}"
                )
            path = (parent / relative).resolve(strict=False)
            try:
                path.relative_to(root)
            except ValueError as exc:
                raise StringsFormatError(
                    f"stock Strings path escapes the installed game: {declared}"
                ) from exc
            if not path.is_file() or path.is_symlink():
                raise StringsFormatError(
                    f"stock Strings file was not found or is unsafe: {path}"
                )
            raw = path.read_bytes()
            hashed[str(path)] = hashlib.sha256(raw).hexdigest()
            table = parse_strings(raw, source=str(path))
            for record in table.records:
                if record.key not in effective:
                    order.append(record.key)
                effective[record.key] = record

    return (
        StringsDocument(
            tuple(effective[key] for key in order),
            "<installed stock Strings load order>",
        ),
        tuple(sorted(hashed.items(), key=lambda row: row[0].casefold())),
    )


def serialize_string_records(records: Sequence[StringRecord]) -> bytes:
    root = ET.Element("Majesty")
    languages: dict[str, ET.Element] = {}
    for record in records:
        element = record.to_element()
        language = record.key[0]
        parent = languages.get(language)
        if parent is None:
            parent = ET.SubElement(root, "Language", {"id": language})
            languages[language] = parent
        if element.tag != "Text" or (element.get("id") or "").strip() != record.key[1]:
            raise StringsFormatError(f"Strings record {record.key!r} changed identity")
        parent.append(element)
    ET.indent(root, space="\t")
    return ET.tostring(root, encoding="utf-8", short_empty_elements=True) + b"\n"


__all__ = [
    "StringCandidate",
    "StringConflict",
    "StringKey",
    "StringRecord",
    "StringsDocument",
    "StringsFormatError",
    "StringsMergeResult",
    "load_effective_stock_strings",
    "load_strings",
    "merge_strings",
    "parse_strings",
    "serialize_string_records",
]
