"""Extract a tiny Majesty-branded UI set from the player's own game files.

No stock artwork is stored in this repository or bundled into the executable.
The manager reads one audited, stable interface TILE from the installed game
and writes an ordinary PNG into its per-user cache for Qt to display.  The
game's icon is referenced in place.
"""

from __future__ import annotations

from dataclasses import dataclass
import binascii
import os
from pathlib import Path
import struct
import tempfile
import zlib

from ..cam import CamFormatError, read_cam


@dataclass(frozen=True)
class BrandAssets:
    header_texture: Path | None
    divider: Path | None
    icon: Path | None
    issues: tuple[str, ...] = ()


@dataclass(frozen=True)
class _TileSpec:
    relative_cam: Path
    tile_index: int
    output_name: str
    relative_palette_cam: Path | None = None


_HEADER = _TileSpec(
    Path("DataMX/mx_interfacedata.cam"),
    # Stock IX51 "base image": the Gold HD main-menu study (room, map,
    # candles, chest, and royal curios).  The app shows a dark, subtle crop of
    # its upper room rather than an arbitrary blue masonry swatch.
    580,
    "majesty-main-menu-header-v3.png",
)


def ensure_brand_assets(game_path: Path, output_root: Path) -> BrandAssets:
    """Return cached stock-derived theme art, extracting missing files safely."""

    output_root = output_root.resolve(strict=False)
    issues: list[str] = []
    produced: dict[str, Path | None] = {}
    try:
        output_root.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        return BrandAssets(None, None, _game_icon(game_path), (str(exc),))

    for label, spec in (("header", _HEADER),):
        target = output_root / spec.output_name
        if target.is_file():
            produced[label] = target
            continue
        try:
            width, height, rgba = _read_theme_tile(
                game_path / spec.relative_cam,
                spec.tile_index,
                (
                    game_path / spec.relative_palette_cam
                    if spec.relative_palette_cam is not None
                    else None
                ),
            )
            if label == "header":
                width, height, rgba = _prepare_header_texture(width, height, rgba)
            _atomic_write(target, _png_rgba(width, height, rgba))
            produced[label] = target
        except (OSError, ValueError, CamFormatError) as exc:
            produced[label] = None
            issues.append(f"Could not extract {label} theme art: {exc}")

    return BrandAssets(
        produced.get("header"),
        # The old divider used an entire 594x29 stock panel squeezed into a
        # 12-pixel strip.  That distorted the panel's controls and filigree
        # into an arbitrary-looking line.  The UI intentionally has no
        # decorative strip now.
        None,
        _game_icon(game_path),
        tuple(issues),
    )


def _game_icon(game_path: Path) -> Path | None:
    candidate = game_path / "MajestyIcon.ico"
    return candidate if candidate.is_file() else None


def _read_theme_tile(
    cam_path: Path,
    tile_index: int,
    palette_cam_path: Path | None = None,
) -> tuple[int, int, bytes]:
    archive = read_cam(cam_path)
    sections = [section for section in archive.sections if section.extension == b"TILE"]
    if len(sections) != 1:
        raise ValueError(f"{cam_path} does not contain exactly one TILE section")
    section = sections[0]
    if tile_index < 0 or tile_index >= len(section.entries):
        raise ValueError(f"{cam_path} has no TILE index {tile_index}")
    tile = section.entries[tile_index].data
    if len(tile) < 26:
        raise ValueError("theme TILE is shorter than its header")
    width = _u16(tile, 4)
    height = _u16(tile, 2)
    row_stride = _u16(tile, 6)
    if row_stride == width * 2:
        return _decode_v1_rgb565(tile)
    palette_mode = _u16(tile, 20)
    if palette_mode == 1:
        return _decode_v1_embedded_palette(tile)
    if palette_mode != 0:
        raise ValueError(f"theme TILE uses unsupported palette mode {palette_mode}")

    palette_index = _u32(tile, 22)
    palette_archive = read_cam(palette_cam_path) if palette_cam_path else archive
    palettes = [
        candidate
        for candidate in palette_archive.sections
        if candidate.extension in {b"SPLT", b"PALT"}
    ]
    if len(palettes) != 1:
        raise ValueError(f"{cam_path} does not contain exactly one palette section")
    palette_section = palettes[0]
    if palette_index >= len(palette_section.entries):
        raise ValueError(f"theme TILE references missing palette {palette_index}")
    return _decode_v1_external_palette(
        tile,
        palette_section.entries[palette_index].data,
    )


def _decode_v1_embedded_palette(data: bytes) -> tuple[int, int, bytes]:
    if len(data) < 26 or _u16(data, 0) != 1:
        raise ValueError("theme TILE is not a version-1 raster")
    if _u16(data, 20) != 1:
        raise ValueError("theme TILE does not use an embedded palette")
    palette_offset = _u32(data, 22)
    if palette_offset + 1032 > len(data):
        raise ValueError("theme TILE has no complete embedded palette")
    return _decode_v1_palette(data, data[palette_offset : palette_offset + 1032])


def _decode_v1_external_palette(
    data: bytes,
    palette_data: bytes,
) -> tuple[int, int, bytes]:
    if len(data) < 26 or _u16(data, 0) != 1:
        raise ValueError("theme TILE is not a version-1 raster")
    if _u16(data, 20) != 0:
        raise ValueError("theme TILE does not use an external palette")
    if len(palette_data) != 1032:
        raise ValueError("theme TILE external palette is incomplete")
    return _decode_v1_palette(data, palette_data)


def _decode_v1_rgb565(data: bytes) -> tuple[int, int, bytes]:
    """Decode a stock full-background 16-bit TILE without dropping black.

    The main-menu study is RGB565 despite carrying the same palette-mode words
    as indexed TILEs.  Stock distinguishes it by a two-byte row stride.  Black
    is real background art here, not sprite transparency, matching the art
    extractor's audited full-background rule.
    """

    if len(data) < 26 or _u16(data, 0) != 1:
        raise ValueError("theme TILE is not a version-1 raster")
    height = _u16(data, 2)
    width = _u16(data, 4)
    row_stride = _u16(data, 6)
    if not (0 < width <= 4096 and 0 < height <= 4096):
        raise ValueError("theme TILE dimensions are invalid")
    if row_stride != width * 2 or 26 + height * row_stride > len(data):
        raise ValueError("theme TILE is not a complete RGB565 raster")
    rgba = bytearray(width * height * 4)
    for y in range(height):
        source_row = 26 + y * row_stride
        target_row = y * width * 4
        for x in range(width):
            value = _u16(data, source_row + x * 2)
            offset = target_row + x * 4
            rgba[offset : offset + 4] = bytes(
                (
                    ((value >> 11) & 0x1F) * 255 // 31,
                    ((value >> 5) & 0x3F) * 255 // 63,
                    (value & 0x1F) * 255 // 31,
                    255,
                )
            )
    return width, height, bytes(rgba)


def _decode_v1_palette(
    data: bytes,
    palette_data: bytes,
) -> tuple[int, int, bytes]:
    if len(data) < 26 or _u16(data, 0) != 1:
        raise ValueError("theme TILE is not a version-1 raster")
    height = _u16(data, 2)
    width = _u16(data, 4)
    row_stride = _u16(data, 6)
    transparent_index = _u16(data, 16) & 0xFF
    if not (0 < width <= 4096 and 0 < height <= 4096):
        raise ValueError("theme TILE dimensions are invalid")
    if row_stride < width:
        raise ValueError("theme TILE row stride is shorter than its width")
    pixel_count = row_stride * height
    if 26 + pixel_count > len(data):
        raise ValueError("theme TILE pixel data is truncated")
    palette = tuple(
        (
            palette_data[8 + index * 4],
            palette_data[9 + index * 4],
            palette_data[10 + index * 4],
        )
        for index in range(256)
    )
    pixels = data[26 : 26 + pixel_count]
    transparent_offsets = _edge_connected_transparency(
        pixels,
        width,
        height,
        row_stride,
        transparent_index,
    )
    rgba = bytearray(width * height * 4)
    for y in range(height):
        source_row = y * row_stride
        target_row = y * width * 4
        for x in range(width):
            index = pixels[source_row + x]
            red, green, blue = palette[index]
            if source_row + x in transparent_offsets:
                continue
            offset = target_row + x * 4
            rgba[offset : offset + 4] = bytes((red, green, blue, 255))
    return width, height, bytes(rgba)


def _prepare_header_texture(
    width: int,
    height: int,
    rgba: bytes,
    *,
    crop_height: int = 176,
) -> tuple[int, int, bytes]:
    """Compose the stock menu backdrop as a quiet, header-shaped crop.

    Mirroring the wide crop gives the title area the balanced composition of a
    game-menu frame and avoids asking Qt's cover crop to discard most of the
    tall 768x520 scene.  It also retains source pixels exactly; no generated or
    redistributed art is involved.
    """

    if len(rgba) != width * height * 4:
        raise ValueError("header RGBA payload does not match its dimensions")
    cropped_height = min(height, crop_height)
    if width <= 0 or cropped_height <= 0:
        raise ValueError("header dimensions are invalid")
    output = bytearray(width * 2 * cropped_height * 4)
    for y in range(cropped_height):
        source_start = y * width * 4
        source = rgba[source_start : source_start + width * 4]
        target_start = y * width * 8
        output[target_start : target_start + width * 4] = source
        for x in range(width):
            source_pixel = (width - 1 - x) * 4
            target_pixel = target_start + (width + x) * 4
            output[target_pixel : target_pixel + 4] = source[
                source_pixel : source_pixel + 4
            ]
    return width * 2, cropped_height, bytes(output)


def _edge_connected_transparency(
    pixels: bytes,
    width: int,
    height: int,
    row_stride: int,
    transparent_index: int,
) -> set[int]:
    """Match Majesty UI art's enclosed transparent-index recovery rule."""

    pending: list[tuple[int, int]] = []
    for x in range(width):
        if pixels[x] == transparent_index:
            pending.append((x, 0))
        bottom = (height - 1) * row_stride + x
        if height > 1 and pixels[bottom] == transparent_index:
            pending.append((x, height - 1))
    for y in range(1, height - 1):
        left = y * row_stride
        if pixels[left] == transparent_index:
            pending.append((0, y))
        right = left + width - 1
        if width > 1 and pixels[right] == transparent_index:
            pending.append((width - 1, y))

    connected: set[int] = set()
    while pending:
        x, y = pending.pop()
        offset = y * row_stride + x
        if offset in connected or pixels[offset] != transparent_index:
            continue
        connected.add(offset)
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                nx, ny = x + dx, y + dy
                if (dx or dy) and 0 <= nx < width and 0 <= ny < height:
                    pending.append((nx, ny))
    return connected


def _png_rgba(width: int, height: int, rgba: bytes) -> bytes:
    expected = width * height * 4
    if len(rgba) != expected:
        raise ValueError(f"RGBA payload has {len(rgba)} bytes; expected {expected}")
    scanlines = b"".join(
        b"\x00" + rgba[row * width * 4 : (row + 1) * width * 4]
        for row in range(height)
    )
    return (
        b"\x89PNG\r\n\x1a\n"
        + _png_chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
        + _png_chunk(b"IDAT", zlib.compress(scanlines, level=9))
        + _png_chunk(b"IEND", b"")
    )


def _png_chunk(kind: bytes, payload: bytes) -> bytes:
    checksum = binascii.crc32(kind)
    checksum = binascii.crc32(payload, checksum) & 0xFFFFFFFF
    return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", checksum)


def _atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(handle, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _u16(data: bytes, offset: int) -> int:
    return struct.unpack_from("<H", data, offset)[0]


def _u32(data: bytes, offset: int) -> int:
    return struct.unpack_from("<I", data, offset)[0]


__all__ = ["BrandAssets", "ensure_brand_assets"]
