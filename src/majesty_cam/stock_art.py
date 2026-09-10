"""Discover and prove Majesty's independent stock positional-art lineages."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
import re
from typing import Sequence
import xml.etree.ElementTree as ET

from .art import (
    ArtArchiveAnalysis,
    ArtFormatError,
    analyze_art_archive,
    parse_best_imag_tile_references,
    parse_stock_imag_tile_references,
    parse_tile_palette_reference,
)
from .cam import CamArchive, CamEntry, CamSection, read_cam


class StockArtError(ValueError):
    """Raised when a positional-art archive has no unique stock ancestry."""


@dataclass(frozen=True)
class StockArtLineage:
    lineage_id: str
    source_paths: tuple[Path, ...]
    ancestors: tuple[CamArchive, ...]
    effective: CamArchive

    @property
    def display_name(self) -> str:
        return " -> ".join(path.name for path in self.source_paths)

    @property
    def imag_keys(self) -> frozenset[bytes]:
        return frozenset(_imag_entries(self.effective))

    @property
    def palette_extension(self) -> bytes | None:
        return _palette_extension(self.effective)

    @property
    def domain(self) -> str:
        if self.palette_extension == b"SPLT":
            return "main"
        if b"CUR1" in self.imag_keys:
            return "interface"
        return self.lineage_id


@dataclass(frozen=True)
class ClassifiedArtArchive:
    lineage: StockArtLineage
    archive: CamArchive
    analysis: ArtArchiveAnalysis
    paths: tuple[Path, ...]


def load_stock_art_lineages(game_path: Path) -> tuple[StockArtLineage, ...]:
    """Build independent stock art families from native dataset CAM order."""

    root = Path(game_path).resolve(strict=True)
    declared = _stock_cam_paths(root)
    lineages: list[StockArtLineage] = []
    for path in declared:
        archive = read_cam(path)
        extensions = {section.extension for section in archive.sections}
        if b"IMAG" not in extensions and b"TILE" not in extensions:
            continue
        if b"IMAG" not in extensions or b"TILE" not in extensions:
            raise StockArtError(
                f"stock positional art must contain both IMAG and TILE: {path}"
            )
        keys = set(_imag_entries(archive))
        matches = [lineage for lineage in lineages if keys & lineage.imag_keys]
        if len(matches) > 1:
            labels = ", ".join(item.display_name for item in matches)
            raise StockArtError(
                f"stock art archive {path} joins multiple independent lineages: "
                f"{labels}"
            )
        if not matches:
            lineages.append(
                StockArtLineage(
                    lineage_id=f"art-{len(lineages) + 1:02d}",
                    source_paths=(path,),
                    ancestors=(archive,),
                    effective=_art_overlay(archive, ()),
                )
            )
            continue
        previous = matches[0]
        index = lineages.index(previous)
        lineages[index] = StockArtLineage(
            lineage_id=previous.lineage_id,
            source_paths=(*previous.source_paths, path),
            ancestors=(*previous.ancestors, archive),
            effective=_art_overlay(previous.effective, (archive,)),
        )
    if not lineages:
        raise StockArtError("installed Majesty datasets contain no typed stock art")
    domains = [lineage.domain for lineage in lineages]
    if len(domains) != len(set(domains)):
        raise StockArtError(
            "installed stock art has ambiguous main/interface lineage identities"
        )
    return tuple(lineages)


def snapshot_stock_art_inputs(game_path: Path) -> tuple[tuple[str, str], ...]:
    """Fingerprint every manifest and CAM used to derive stock art ancestry."""

    root = Path(game_path).resolve(strict=True)
    paths = {
        root / "Data" / "MajestyDatasetDefinitions.xml",
        root / "DataMX" / "MajestyExpansionDatasetDefinitions.xml",
        *_stock_cam_paths(root),
    }
    return tuple(
        (str(path), hashlib.sha256(path.read_bytes()).hexdigest())
        for path in sorted(paths, key=lambda value: str(value).casefold())
    )


def classify_art_archive(
    lineages: Sequence[StockArtLineage],
    archive: CamArchive,
    *,
    owner: str,
) -> tuple[StockArtLineage, ArtArchiveAnalysis]:
    """Choose one ancestry from the archive's typed content evidence."""

    extensions = {section.extension for section in archive.sections}
    if b"IMAG" not in extensions:
        raise StockArtError(f"{owner}: positional art requires IMAG")
    if b"TILE" not in extensions and extensions.intersection((b"SPLT", b"PALT")):
        raise StockArtError(f"{owner}: a positional palette requires TILE")
    if b"SPLT" in extensions and b"PALT" in extensions:
        raise StockArtError(f"{owner}: positional art cannot contain SPLT and PALT")
    palette = _palette_extension(archive)
    mod_images = _imag_entries(archive)
    mod_tiles = _optional_section(archive, b"TILE")
    evidence: set[str] = set()
    if palette is not None:
        palette_candidates = [
            lineage
            for lineage in lineages
            if lineage.palette_extension == palette
        ]
        if len(palette_candidates) == 1:
            evidence.add(palette_candidates[0].lineage_id)

    for key in mod_images:
        matches = [lineage for lineage in lineages if key in lineage.imag_keys]
        if len(matches) == 1:
            evidence.add(matches[0].lineage_id)

    if mod_tiles is not None:
        stock_image_payloads: dict[bytes, set[bytes]] = {}
        for lineage in lineages:
            for candidate in (*lineage.ancestors, lineage.effective):
                for key, entry in _imag_entries(candidate).items():
                    stock_image_payloads.setdefault(key, set()).add(entry.data)
        referenced_tiles: set[int] = set()
        for key, entry in mod_images.items():
            try:
                parsed = (
                    parse_stock_imag_tile_references(
                        entry.data,
                        tile_count=len(mod_tiles.entries),
                        entry_name=entry.name,
                    )
                    if entry.data in stock_image_payloads.get(key, set())
                    else parse_best_imag_tile_references(
                        entry.data,
                        tile_count=len(mod_tiles.entries),
                        entry_name=entry.name,
                    )
                )
            except (ArtFormatError, ValueError):
                # Unrelated inherited records with legacy shapes are not
                # positional ancestry evidence. A changed owned record will be
                # rejected later if no other typed anchor proves its family.
                continue
            referenced_tiles.update(
                reference.tile_index for reference in parsed.references
            )
        for index in sorted(referenced_tiles):
            if index >= len(mod_tiles.entries):
                continue
            entry = mod_tiles.entries[index]
            if not entry.data:
                continue
            matches = [
                lineage
                for lineage in lineages
                if any(
                    index < len(section.entries)
                    and section.entries[index].name == entry.name
                    and section.entries[index].data == entry.data
                    for ancestor in (*lineage.ancestors, lineage.effective)
                    for section in (_optional_section(ancestor, b"TILE"),)
                    if section is not None
                )
            ]
            if len(matches) == 1:
                evidence.add(matches[0].lineage_id)
    if not evidence:
        raise StockArtError(
            f"{owner}: positional art has no provable installed stock lineage "
            "(no compatible named or positional stock anchor)"
        )
    if len(evidence) != 1:
        labels = ", ".join(
            lineage.display_name
            for lineage in lineages
            if lineage.lineage_id in evidence
        )
        raise StockArtError(
            f"{owner}: positional art ancestry is ambiguous between {labels}"
        )
    lineage = next(
        item for item in lineages if item.lineage_id == next(iter(evidence))
    )
    sparse = _sparse_component_archive(lineage, (archive,))
    try:
        analysis = analyze_art_archive(
            lineage.effective,
            sparse,
            mod_id=owner,
            fallthrough_ancestors=lineage.ancestors,
        )
    except (ArtFormatError, ValueError) as exc:
        raise StockArtError(
            f"{owner}: owned art cannot be proved for {lineage.display_name}: {exc}"
        ) from exc
    return lineage, analysis


def collapse_art_archives(
    game_path: Path,
    paths: Sequence[Path],
    *,
    owner: str,
) -> tuple[ClassifiedArtArchive, ...]:
    """Apply one component's native CAM order independently per stock family."""

    source_archives: list[tuple[Path, CamArchive]] = []
    for path in paths:
        archive = read_cam(path)
        extensions = {section.extension for section in archive.sections}
        if b"IMAG" not in extensions and b"TILE" not in extensions:
            continue
        if b"TILE" in extensions and b"IMAG" not in extensions:
            raise StockArtError(
                f"{owner}: positional TILE art requires IMAG evidence: {path}"
            )
        source_archives.append((path, archive))
    if not source_archives:
        return ()

    lineages = load_stock_art_lineages(game_path)
    assigned: list[
        tuple[Path, CamArchive, StockArtLineage, ArtArchiveAnalysis] | None
    ] = []
    unresolved: list[tuple[int, StockArtError]] = []
    for index, (path, archive) in enumerate(source_archives):
        try:
            lineage, analysis = classify_art_archive(lineages, archive, owner=owner)
        except StockArtError as exc:
            if "no provable installed stock lineage" not in str(exc):
                raise
            assigned.append(None)
            unresolved.append((index, exc))
        else:
            assigned.append((path, archive, lineage, analysis))

    explicit_providers = tuple(
        (item[1], item[2], item[3]) for item in assigned if item is not None
    )
    for index, original_error in unresolved:
        path, archive = source_archives[index]
        evidence = set(_structural_dependency_lineages(
            archive,
            explicit_providers,
        ))
        evidence.update(_path_declared_lineages(path, lineages))
        if not evidence:
            raise original_error
        if len(evidence) != 1:
            labels = ", ".join(
                lineage.display_name
                for lineage in lineages
                if lineage.lineage_id in evidence
            )
            raise StockArtError(
                f"{owner}: positional art ancestry is ambiguous between {labels}"
            )
        lineage_id = next(iter(evidence))
        lineage = next(
            candidate for candidate in lineages if candidate.lineage_id == lineage_id
        )
        palette = _palette_extension(archive)
        if palette is not None and palette != lineage.palette_extension:
            raise original_error
        assigned[index] = (path, archive, lineage, None)

    grouped: dict[str, list[tuple[Path, CamArchive]]] = {}
    lineage_by_id: dict[str, StockArtLineage] = {}
    order: list[str] = []
    for item in assigned:
        if item is None:  # pragma: no cover - unresolved entries fail above
            raise StockArtError(f"{owner}: unresolved positional art ancestry")
        path, archive, lineage, _analysis = item
        if lineage.lineage_id not in grouped:
            grouped[lineage.lineage_id] = []
            lineage_by_id[lineage.lineage_id] = lineage
            order.append(lineage.lineage_id)
        grouped[lineage.lineage_id].append((path, archive))

    result: list[ClassifiedArtArchive] = []
    for lineage_id in order:
        lineage = lineage_by_id[lineage_id]
        members = grouped[lineage_id]
        effective = _sparse_component_archive(
            lineage,
            tuple(archive for _path, archive in members),
        )
        try:
            analysis = analyze_art_archive(
                lineage.effective,
                effective,
                mod_id=owner,
                fallthrough_ancestors=lineage.ancestors,
            )
        except (ArtFormatError, ValueError) as exc:
            raise StockArtError(
                f"{owner}: effective native art order cannot be proved for "
                f"{lineage.display_name}: {exc}"
            ) from exc
        result.append(
            ClassifiedArtArchive(
                lineage=lineage,
                archive=effective,
                analysis=analysis,
                paths=tuple(path for path, _archive in members),
            )
        )
    return tuple(result)


def _path_declared_lineages(
    path: Path,
    lineages: Sequence[StockArtLineage],
) -> frozenset[str]:
    """Interpret an exact stock-CAM filename suffix as an ancestry declaration.

    Historical Majesty mods commonly publish complete positional art tables
    without retaining a stock IMAG/PALT/SPLT anchor.  Their SDK convention is
    to preserve the target stock CAM's basename as the final, separator-bound
    portion of the custom filename (for example ``my_mod_interfacedata.cam``).
    That convention is usable evidence because the candidates come from the
    installed game's manifests rather than a manager-maintained name list.

    The final archive is still checked against the selected lineage by
    ``analyze_art_archive``.  A coincidental substring, table length, or merely
    being adjacent to another archive remains insufficient.
    """

    candidate_name = path.name.casefold()
    result: set[str] = set()
    separators = frozenset("._- ")
    for lineage in lineages:
        for source_path in lineage.source_paths:
            stock_name = source_path.name.casefold()
            if candidate_name == stock_name:
                result.add(lineage.lineage_id)
                continue
            if not candidate_name.endswith(stock_name):
                continue
            boundary = len(candidate_name) - len(stock_name) - 1
            if boundary >= 0 and candidate_name[boundary] in separators:
                result.add(lineage.lineage_id)
    return frozenset(result)


def _structural_dependency_lineages(
    archive: CamArchive,
    providers: Sequence[
        tuple[CamArchive, StockArtLineage, ArtArchiveAnalysis]
    ],
) -> frozenset[str]:
    """Find uniquely typed provider dependencies without guessing from table size.

    An unanchored archive may join a lineage only when its authored IMAG/TILE
    records actually depend on a separately stock-anchored archive from the
    same component. Merely fitting a stock table length or appearing beside a
    single classified archive is not ancestry evidence.
    """

    result: set[str] = set()
    images = _imag_entries(archive)
    tiles = _optional_section(archive, b"TILE")
    for _provider_archive, lineage, analysis in providers:
        stock_images = _imag_entries(lineage.effective)
        owned_images = {
            key: entry
            for key, entry in images.items()
            if key not in stock_images or entry.data != stock_images[key].data
        }
        provider_owned_keys = {
            entry.name.rstrip(b"\0")[:4] for entry in analysis.imag_entries
        }
        if set(owned_images).intersection(provider_owned_keys):
            result.add(lineage.lineage_id)
            continue

        stock_tiles = _section(lineage.effective, b"TILE")
        candidate_tile_count = max(
            len(stock_tiles.entries),
            len(tiles.entries) if tiles is not None else 0,
            max(analysis.tile_delta.changed_indices, default=-1) + 1,
        )
        referenced_tiles: set[int] = set()
        recognized_payloads: dict[bytes, set[bytes]] = {}
        for candidate in (*lineage.ancestors, lineage.effective):
            for key, entry in _imag_entries(candidate).items():
                recognized_payloads.setdefault(key, set()).add(entry.data)
        for key, entry in owned_images.items():
            try:
                parsed = (
                    parse_stock_imag_tile_references(
                        entry.data,
                        tile_count=candidate_tile_count,
                        entry_name=entry.name,
                    )
                    if entry.data in recognized_payloads.get(key, set())
                    else parse_best_imag_tile_references(
                        entry.data,
                        tile_count=candidate_tile_count,
                        entry_name=entry.name,
                        preferred_tile_indices=analysis.tile_delta.changed_indices,
                    )
                )
            except (ArtFormatError, ValueError):
                continue
            referenced_tiles.update(
                reference.tile_index for reference in parsed.references
            )
        if referenced_tiles.intersection(analysis.tile_delta.changed_indices):
            result.add(lineage.lineage_id)
            continue

        if tiles is None:
            continue
        archive_changed_tiles = _private_positional_indices(tiles, (stock_tiles,))
        provider_references = {
            reference.tile_index for reference in analysis.imag_references
        }
        if archive_changed_tiles.intersection(provider_references):
            result.add(lineage.lineage_id)
    return frozenset(result)


def _stock_cam_paths(root: Path) -> tuple[Path, ...]:
    manifests = (
        root / "Data" / "MajestyDatasetDefinitions.xml",
        root / "DataMX" / "MajestyExpansionDatasetDefinitions.xml",
    )
    result: list[Path] = []
    for manifest in manifests:
        try:
            document = ET.fromstring(manifest.read_bytes())
        except (OSError, ET.ParseError) as exc:
            raise StockArtError(f"stock dataset manifest could not be read: {manifest}") from exc
        loads = document.findall("./DataConfiguration/Dataset/Load")
        if len(loads) != 1:
            raise StockArtError(f"stock dataset has no unique CAM load order: {manifest}")
        for node in loads[0].findall("./CAM"):
            raw = (node.text or "").strip()
            if not raw:
                continue
            variable = re.fullmatch(r"\$\(([^)]+)\)[\\/]([^<>:\"|?*]+)", raw)
            if variable is not None:
                roots = {
                    "majestydatapath": root / "Data",
                    "majestyexpansiondatapath": root / "DataMX",
                }
                parent = roots.get(variable.group(1).casefold())
                if parent is None:
                    raise StockArtError(
                        f"unsupported stock CAM path variable in {manifest}: {raw!r}"
                    )
                relative = Path(variable.group(2))
            else:
                parent = manifest.parent
                relative = Path(raw.replace("\\", "/"))
            if relative.is_absolute() or ".." in relative.parts:
                raise StockArtError(f"unsafe stock CAM path in {manifest}: {raw!r}")
            path = (parent / relative).resolve(strict=True)
            try:
                path.relative_to(root)
            except ValueError as exc:
                raise StockArtError(f"stock CAM escapes game root: {path}") from exc
            if path.suffix.casefold() != ".cam" or path.is_symlink():
                raise StockArtError(f"unsafe stock CAM declaration: {path}")
            result.append(path)
    return tuple(result)


def _art_overlay(base: CamArchive, overlays: Sequence[CamArchive]) -> CamArchive:
    effective = base
    for overlay in overlays:
        base_images = list(_section(effective, b"IMAG").entries)
        image_index = {
            entry.name.rstrip(b"\0")[:4]: index
            for index, entry in enumerate(base_images)
        }
        for key, entry in _imag_entries(overlay).items():
            if key in image_index:
                base_images[image_index[key]] = entry
            else:
                image_index[key] = len(base_images)
                base_images.append(entry)

        base_tiles = _section(effective, b"TILE")
        overlay_tiles = _section(overlay, b"TILE")
        tiles = _overlay_positional(base_tiles, overlay_tiles)
        base_palette = _palette_section(effective)
        overlay_palette = _palette_section(overlay)
        if base_palette is not None and overlay_palette is not None:
            if base_palette.extension != overlay_palette.extension:
                raise StockArtError("art overlay changes positional palette type")
            palette = _overlay_positional(base_palette, overlay_palette)
        elif overlay_palette is not None:
            palette = overlay_palette
        else:
            palette = base_palette
        sections = [
            CamSection(
                b"IMAG",
                tuple(base_images),
                padding=_section(effective, b"IMAG").padding,
            ),
            tiles,
        ]
        if palette is not None:
            sections.append(palette)
        effective = CamArchive(tuple(sections))
    return effective


def _sparse_component_archive(
    lineage: StockArtLineage,
    overlays: Sequence[CamArchive],
) -> CamArchive:
    """Apply native order while retaining only component-owned art writes."""

    stock_images = _section(lineage.effective, b"IMAG")
    stock_tiles = _section(lineage.effective, b"TILE")
    stock_palette = _palette_section(lineage.effective)
    images: list[CamEntry] = []
    image_positions: dict[bytes, int] = {}
    tiles = CamSection(
        b"TILE",
        tuple(CamEntry(entry.name, b"") for entry in stock_tiles.entries),
        padding=stock_tiles.padding,
    )
    palette: CamSection | None = None

    for overlay in overlays:
        for key, entry in _imag_entries(overlay).items():
            position = image_positions.get(key)
            if position is None:
                image_positions[key] = len(images)
                images.append(entry)
            else:
                images[position] = entry
        overlay_tiles = _optional_section(overlay, b"TILE")
        if overlay_tiles is not None:
            tiles = _overlay_positional(tiles, overlay_tiles)
        overlay_palette = _palette_section(overlay)
        if overlay_palette is not None:
            if stock_palette is None or stock_palette.extension != overlay_palette.extension:
                raise StockArtError("art overlay changes positional palette type")
            if palette is None:
                palette = CamSection(
                    stock_palette.extension,
                    tuple(
                        CamEntry(entry.name, b"")
                        for entry in stock_palette.entries
                    ),
                    padding=stock_palette.padding,
                )
            palette = _overlay_positional(palette, overlay_palette)

    # A value copied from an older stock ancestor is still an authored write
    # when it differs from the effective installed lineage.  Keep that write
    # in the sparse archive so analysis can preserve its exact provenance.
    # Older ancestors remain valid parsing/dependency candidates below, but
    # they must never redefine what counts as unchanged at runtime.
    changed_tiles = _private_positional_indices(tiles, (stock_tiles,))
    changed_palettes = (
        _private_positional_indices(
            palette,
            (stock_palette,),
        )
        if palette is not None
        else frozenset()
    )
    effective_image_payloads: dict[bytes, set[bytes]] = {}
    recognized_stock_image_payloads: dict[bytes, set[bytes]] = {}
    for archive in (*lineage.ancestors, lineage.effective):
        for key, entry in _imag_entries(archive).items():
            recognized_stock_image_payloads.setdefault(key, set()).add(entry.data)
    for key, entry in _imag_entries(lineage.effective).items():
        effective_image_payloads.setdefault(key, set()).add(entry.data)

    owned_images: list[CamEntry] = []
    for entry in images:
        key = entry.name.rstrip(b"\0")[:4]
        if entry.data not in effective_image_payloads.get(key, set()):
            owned_images.append(entry)
            continue
        # A byte-identical stock IMAG is still necessary evidence when the
        # component changes one of the positional records it references.  If
        # this untouched stock record uses an unsupported legacy shape, skip
        # it; an affected positional write then remains explicitly unreferenced
        # and relocation will fail closed rather than parsing unrelated stock.
        try:
            parsed = parse_stock_imag_tile_references(
                entry.data,
                tile_count=len(tiles.entries),
                entry_name=entry.name,
            )
        except (ArtFormatError, ValueError):
            continue
        referenced_tiles = {
            reference.tile_index for reference in parsed.references
        }
        if referenced_tiles.intersection(changed_tiles):
            owned_images.append(entry)
            continue
        if changed_palettes and any(
            reference is not None
            and reference.palette_index in changed_palettes
            for tile_index in referenced_tiles
            if tile_index < len(tiles.entries) and tiles.entries[tile_index].data
            for reference in (
                parse_tile_palette_reference(
                    tiles.entries[tile_index].data,
                    tile_index=tile_index,
                ),
            )
        ):
            owned_images.append(entry)

    # A generated load-last archive must contain only proved visual writes.
    # Package builders commonly carry extra positional records copied from a
    # source archive; a non-stock TILE or palette slot that no effective owned
    # IMAG reaches is not a mergeable change and must not shadow another mod.
    referenced_tiles: set[int] = set()
    for entry in owned_images:
        key = entry.name.rstrip(b"\0")[:4]
        inherited = entry.data in recognized_stock_image_payloads.get(key, set())
        try:
            parsed = (
                parse_stock_imag_tile_references(
                    entry.data,
                    tile_count=len(tiles.entries),
                    entry_name=entry.name,
                )
                if inherited
                else parse_best_imag_tile_references(
                    entry.data,
                    tile_count=len(tiles.entries),
                    entry_name=entry.name,
                    preferred_tile_indices=changed_tiles,
                )
            )
        except (ArtFormatError, ValueError) as exc:
            raise StockArtError(
                f"owned IMAG {key!r} has no supported TILE reference layout: {exc}"
            ) from exc
        referenced_tiles.update(
            reference.tile_index for reference in parsed.references
        )
    unowned_tiles = changed_tiles.difference(referenced_tiles)
    if unowned_tiles:
        tiles = CamSection(
            tiles.extension,
            tuple(
                CamEntry(entry.name, b"") if index in unowned_tiles else entry
                for index, entry in enumerate(tiles.entries)
            ),
            padding=tiles.padding,
        )

    if palette is not None and changed_palettes:
        referenced_palettes = {
            reference.palette_index
            for tile_index in referenced_tiles
            if tile_index < len(tiles.entries) and tiles.entries[tile_index].data
            for reference in (
                parse_tile_palette_reference(
                    tiles.entries[tile_index].data,
                    tile_index=tile_index,
                ),
            )
            if reference is not None
        }
        unowned_palettes = changed_palettes.difference(referenced_palettes)
        if unowned_palettes:
            palette = CamSection(
                palette.extension,
                tuple(
                    CamEntry(entry.name, b"")
                    if index in unowned_palettes
                    else entry
                    for index, entry in enumerate(palette.entries)
                ),
                padding=palette.padding,
            )

    sections = [
        CamSection(
            b"IMAG",
            tuple(owned_images),
            padding=stock_images.padding,
        ),
        tiles,
    ]
    if palette is not None:
        sections.append(palette)
    return CamArchive(tuple(sections))


def _private_positional_indices(
    section: CamSection,
    stock_variants: Sequence[CamSection],
) -> frozenset[int]:
    return frozenset(
        index
        for index, entry in enumerate(section.entries)
        if entry.data
        and not any(
            index < len(stock.entries)
            and stock.entries[index].data == entry.data
            for stock in stock_variants
        )
    )


def _overlay_positional(base: CamSection, overlay: CamSection) -> CamSection:
    output = list(base.entries)
    if len(output) < len(overlay.entries):
        output.extend(overlay.entries[len(output) :])
    for index, entry in enumerate(overlay.entries):
        if entry.data:
            output[index] = entry
    return CamSection(base.extension, tuple(output), padding=base.padding)


def _imag_entries(archive: CamArchive) -> dict[bytes, CamEntry]:
    return {
        entry.name.rstrip(b"\0")[:4]: entry
        for entry in _section(archive, b"IMAG").entries
    }


def _optional_section(archive: CamArchive, extension: bytes) -> CamSection | None:
    matches = [
        section for section in archive.sections if section.extension == extension
    ]
    if len(matches) > 1:
        raise StockArtError(
            f"art archive contains multiple {extension!r} sections"
        )
    return matches[0] if matches else None


def _palette_extension(archive: CamArchive) -> bytes | None:
    section = _palette_section(archive)
    return None if section is None else section.extension


def _palette_section(archive: CamArchive) -> CamSection | None:
    matches = [
        section for section in archive.sections if section.extension in (b"SPLT", b"PALT")
    ]
    if len(matches) > 1:
        raise StockArtError("art archive contains multiple positional palette sections")
    return matches[0] if matches else None


def _section(archive: CamArchive, extension: bytes) -> CamSection:
    matches = [section for section in archive.sections if section.extension == extension]
    if len(matches) != 1:
        raise StockArtError(
            f"art archive must contain exactly one {extension!r} section; found {len(matches)}"
        )
    return matches[0]


__all__ = [
    "ClassifiedArtArchive",
    "StockArtError",
    "StockArtLineage",
    "classify_art_archive",
    "collapse_art_archives",
    "load_stock_art_lineages",
    "snapshot_stock_art_inputs",
]
