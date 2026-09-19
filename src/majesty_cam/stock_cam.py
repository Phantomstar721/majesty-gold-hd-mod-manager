from __future__ import annotations

import hashlib
from functools import lru_cache
from pathlib import Path
import re
import struct
import xml.etree.ElementTree as ET

from .cam import MAGIC as CAM_MAGIC, read_cam


STOCK_NAMED_CAM_SECTIONS = frozenset((b"SMNU", b"STRT", b"DSND", b"WAVE"))


class StockCamError(ValueError):
    """Raised when installed stock named-CAM ancestry cannot be proven."""


def stock_image_ids(game_path: Path) -> frozenset[bytes]:
    """Collision evidence from directories only; never read art pixel payloads."""
    from .stock_art import _stock_cam_paths
    result = set()
    for path in _stock_cam_paths(game_path.resolve(strict=True)):
        stat = path.stat()
        result.update(_stock_image_ids_cached(path, stat.st_size, stat.st_mtime_ns))
    return frozenset(result)


@lru_cache(maxsize=32)
def _stock_image_ids_cached(path: Path, size: int, modified: int) -> frozenset[bytes]:
    del modified  # part of the invalidation key
    with path.open("rb") as stream:
        header = stream.read(20)
        if len(header) != 20 or header[:12] != CAM_MAGIC:
            raise StockCamError(f"stock CAM has an invalid header: {path}")
        count, length = struct.unpack_from("<II", header, 12)
        if count > 4096 or 20+8*count+length > size:
            raise StockCamError(f"stock CAM directory exceeds its file: {path}")
        directory = stream.read(count*8)
        if len(directory) != count*8:
            raise StockCamError(f"stock CAM directory is truncated: {path}")
        result = set()
        end = 20+8*count+length
        for i in range(count):
            extension, offset = struct.unpack_from("<4sI", directory, i*8)
            if extension != b"IMAG":
                continue
            if offset < 20+8*count or offset+8 > end:
                raise StockCamError(f"stock IMAG directory offset is invalid: {path}")
            stream.seek(offset)
            prefix = stream.read(8)
            if len(prefix) != 8:
                raise StockCamError(f"stock IMAG directory is truncated: {path}")
            entries = struct.unpack_from("<I", prefix)[0]
            if entries > (end-offset-8)//28:
                raise StockCamError(f"stock IMAG entries exceed their directory: {path}")
            records = stream.read(entries*28)
            if len(records) != entries*28:
                raise StockCamError(f"stock IMAG entries are truncated: {path}")
            result.update(records[j:j+4] for j in range(0, len(records), 28))
    return frozenset(result)


def load_effective_stock_named_resources(
    game_path: Path,
) -> tuple[
    dict[tuple[bytes, bytes], bytes],
    tuple[tuple[str, str], ...],
]:
    """Load named stock CAM registries in Majesty's actual dataset order."""

    root = game_path.resolve(strict=True)
    manifests = (
        root / "Data" / "MajestyDatasetDefinitions.xml",
        root / "DataMX" / "MajestyExpansionDatasetDefinitions.xml",
    )
    effective: dict[tuple[bytes, bytes], bytes] = {}
    hashed: dict[str, str] = {}
    variable_roots = {
        "majestydatapath": root / "Data",
        "majestyexpansiondatapath": root / "DataMX",
    }

    for manifest in manifests:
        if not manifest.is_file() or manifest.is_symlink():
            raise StockCamError(
                f"stock dataset definition was not found or is unsafe: {manifest}"
            )
        hashed[str(manifest)] = hashlib.sha256(manifest.read_bytes()).hexdigest()
        try:
            document = ET.parse(manifest)
        except (ET.ParseError, OSError) as exc:
            raise StockCamError(
                f"stock dataset definition could not be read: {manifest}"
            ) from exc
        cam_nodes = document.findall(".//Dataset/Load/CAM")
        if not cam_nodes:
            raise StockCamError(
                f"stock dataset definition contains no CAM load order: {manifest}"
            )
        for node in cam_nodes:
            declared = (node.text or "").strip()
            if not declared:
                raise StockCamError(
                    f"stock dataset definition contains an empty CAM path: {manifest}"
                )
            variable = re.fullmatch(r"\$\(([^)]+)\)[\\/](.+)", declared)
            if variable is not None:
                base = variable_roots.get(variable.group(1).casefold())
                if base is None:
                    raise StockCamError(
                        f"unsupported stock CAM path variable in {manifest}: {declared}"
                    )
                candidate = base / Path(variable.group(2).replace("\\", "/"))
            else:
                candidate = manifest.parent / Path(declared.replace("\\", "/"))
            path = candidate.resolve(strict=False)
            try:
                path.relative_to(root)
            except ValueError as exc:
                raise StockCamError(
                    f"stock CAM path escapes the installed game: {declared}"
                ) from exc
            if not path.is_file() or path.is_symlink():
                raise StockCamError(
                    f"stock CAM load was not found or is unsafe: {path}"
                )
            if not _stock_cam_has_named_sections(path):
                continue
            payload = path.read_bytes()
            hashed[str(path)] = hashlib.sha256(payload).hexdigest()
            try:
                archive = read_cam(path)
            except (OSError, ValueError) as exc:
                raise StockCamError(f"stock CAM could not be read: {path}") from exc
            for section in archive.sections:
                if section.extension not in STOCK_NAMED_CAM_SECTIONS:
                    continue
                for entry in section.entries:
                    effective[(section.extension, entry.name[:4])] = entry.data

    return effective, tuple(sorted(hashed.items(), key=lambda row: row[0].casefold()))


def _stock_cam_has_named_sections(path: Path) -> bool:
    try:
        with path.open("rb") as stream:
            header = stream.read(20)
            if len(header) != 20 or header[:12] != CAM_MAGIC:
                raise StockCamError(f"stock CAM has an invalid header: {path}")
            section_count = struct.unpack_from("<I", header, 12)[0]
            if section_count > 4096:
                raise StockCamError(
                    f"stock CAM has an unreasonable section count: {path}"
                )
            directory = stream.read(section_count * 8)
            if len(directory) != section_count * 8:
                raise StockCamError(
                    f"stock CAM has a truncated section directory: {path}"
                )
    except OSError as exc:
        raise StockCamError(f"stock CAM could not be inspected: {path}") from exc
    return any(
        directory[index : index + 4] in STOCK_NAMED_CAM_SECTIONS
        for index in range(0, len(directory), 8)
    )


__all__ = (
    "STOCK_NAMED_CAM_SECTIONS",
    "StockCamError",
    "load_effective_stock_named_resources",
)
