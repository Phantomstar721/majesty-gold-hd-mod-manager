from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import struct
from typing import BinaryIO, Iterable


MAGIC = b"CYLBPC  \x01\x00\x01\x00"
HEADER_SIZE = 12 + 4 + 4
SECTION_DIRECTORY_ENTRY_SIZE = 8
SECTION_HEADER_PREFIX_SIZE = 8
ENTRY_HEADER_SIZE = 20 + 4 + 4


class CamFormatError(ValueError):
    """Raised when a CAM archive is malformed or unsupported."""


@dataclass(frozen=True)
class CamEntry:
    name: bytes
    data: bytes
    data_offset: int | None = None

    def __post_init__(self) -> None:
        if len(self.name) != 20:
            raise CamFormatError(f"CAM entry names must be exactly 20 bytes, got {len(self.name)}")

    @property
    def display_name(self) -> str:
        return _decode_display_name(self.name)


@dataclass(frozen=True)
class CamSection:
    extension: bytes
    entries: tuple[CamEntry, ...]
    header_offset: int | None = None
    padding: bytes = b"\x00\x00\x00\x00"

    def __post_init__(self) -> None:
        if len(self.extension) != 4:
            raise CamFormatError(
                f"CAM section extensions must be exactly 4 bytes, got {len(self.extension)}"
            )
        if len(self.padding) != 4:
            raise CamFormatError(f"CAM section padding must be exactly 4 bytes, got {len(self.padding)}")

    @property
    def display_extension(self) -> str:
        return self.extension.decode("ascii", errors="replace").rstrip()


@dataclass(frozen=True)
class CamArchive:
    sections: tuple[CamSection, ...]

    def to_bytes(self) -> bytes:
        return write_cam(self)


def read_cam(path_or_bytes: str | Path | bytes | bytearray) -> CamArchive:
    if isinstance(path_or_bytes, (bytes, bytearray)):
        data = bytes(path_or_bytes)
    else:
        data = Path(path_or_bytes).read_bytes()

    return parse_cam(data)


def parse_cam(data: bytes) -> CamArchive:
    if len(data) < HEADER_SIZE:
        raise CamFormatError("CAM archive is too small to contain a header")

    cursor = 0
    magic = data[cursor : cursor + len(MAGIC)]
    cursor += len(MAGIC)
    if magic != MAGIC:
        raise CamFormatError(f"Invalid CAM magic: {magic!r}")

    section_count = _u32(data, cursor)
    cursor += 4
    content_header_length = _u32(data, cursor)
    cursor += 4

    directory_length = section_count * SECTION_DIRECTORY_ENTRY_SIZE
    if cursor + directory_length > len(data):
        raise CamFormatError("CAM section directory extends beyond end of file")

    section_extensions: list[bytes] = []
    section_offsets: list[int] = []
    for _ in range(section_count):
        section_extensions.append(data[cursor : cursor + 4])
        cursor += 4
        section_offsets.append(_u32(data, cursor))
        cursor += 4

    content_header_start = cursor
    if content_header_start + content_header_length > len(data):
        raise CamFormatError("CAM content header extends beyond end of file")

    sections_meta: list[tuple[bytes, int, bytes, list[tuple[bytes, int, int]]]] = []
    for section_index in range(section_count):
        expected_offset = section_offsets[section_index]
        if expected_offset != cursor:
            raise CamFormatError(
                "Unexpected section header offset for section "
                f"{section_index}: directory says {expected_offset}, parser is at {cursor}"
            )

        file_count = _u32(data, cursor)
        cursor += 4
        padding = data[cursor : cursor + 4]
        cursor += 4

        entries_meta: list[tuple[bytes, int, int]] = []
        for _ in range(file_count):
            name = data[cursor : cursor + 20]
            cursor += 20
            data_offset = _u32(data, cursor)
            cursor += 4
            data_size = _u32(data, cursor)
            cursor += 4

            end = data_offset + data_size
            if end > len(data):
                raise CamFormatError(
                    f"Entry {name!r} points past EOF: offset={data_offset} size={data_size}"
                )
            entries_meta.append((name, data_offset, data_size))

        sections_meta.append(
            (section_extensions[section_index], expected_offset, padding, entries_meta)
        )

    if cursor != content_header_start + content_header_length:
        raise CamFormatError(
            "Parsed content header length mismatch: "
            f"expected end {content_header_start + content_header_length}, got {cursor}"
        )

    sections: list[CamSection] = []
    for extension, header_offset, padding, entries_meta in sections_meta:
        entries = tuple(
            CamEntry(
                name=name,
                data=data[data_offset : data_offset + data_size],
                data_offset=data_offset,
            )
            for name, data_offset, data_size in entries_meta
        )
        sections.append(
            CamSection(
                extension=extension,
                entries=entries,
                header_offset=header_offset,
                padding=padding,
            )
        )

    return CamArchive(sections=tuple(sections))


def write_cam(archive: CamArchive, destination: str | Path | BinaryIO | None = None) -> bytes:
    section_count = len(archive.sections)
    file_header_size = HEADER_SIZE + section_count * SECTION_DIRECTORY_ENTRY_SIZE
    content_header_size = sum(_section_header_size(section) for section in archive.sections)
    content_start = file_header_size + content_header_size

    data_offsets: list[list[int]] = []
    cursor = content_start
    for section in archive.sections:
        offsets: list[int] = []
        for entry in section.entries:
            offsets.append(cursor)
            cursor += len(entry.data)
        data_offsets.append(offsets)

    output = bytearray()
    output += MAGIC
    output += struct.pack("<I", section_count)
    output += struct.pack("<I", content_header_size)

    section_header_offset = file_header_size
    for section in archive.sections:
        output += section.extension
        output += struct.pack("<I", section_header_offset)
        section_header_offset += _section_header_size(section)

    for section_index, section in enumerate(archive.sections):
        output += struct.pack("<I", len(section.entries))
        output += section.padding
        for entry_index, entry in enumerate(section.entries):
            output += entry.name
            output += struct.pack("<I", data_offsets[section_index][entry_index])
            output += struct.pack("<I", len(entry.data))

    for section in archive.sections:
        for entry in section.entries:
            output += entry.data

    result = bytes(output)
    if destination is None:
        return result
    if hasattr(destination, "write"):
        destination.write(result)
    else:
        Path(destination).write_bytes(result)
    return result


def make_archive(sections: Iterable[CamSection]) -> CamArchive:
    return CamArchive(sections=tuple(sections))


def pad_name(name: str | bytes) -> bytes:
    raw = name.encode("ascii") if isinstance(name, str) else name
    if len(raw) > 20:
        raise CamFormatError(f"CAM entry name is longer than 20 bytes: {name!r}")
    return raw.ljust(20, b"\x00")


def pad_extension(extension: str | bytes) -> bytes:
    raw = extension.encode("ascii") if isinstance(extension, str) else extension
    if len(raw) > 4:
        raise CamFormatError(f"CAM section extension is longer than 4 bytes: {extension!r}")
    return raw.ljust(4, b" ")


def _section_header_size(section: CamSection) -> int:
    return SECTION_HEADER_PREFIX_SIZE + len(section.entries) * ENTRY_HEADER_SIZE


def _u32(data: bytes, offset: int) -> int:
    if offset + 4 > len(data):
        raise CamFormatError(f"Unexpected EOF while reading u32 at offset {offset}")
    return struct.unpack_from("<I", data, offset)[0]


def _decode_display_name(raw_name: bytes) -> str:
    trimmed = raw_name.rstrip(b"\x00")
    return trimmed.decode("ascii", errors="replace")
