from pathlib import Path
import struct
import sys
from tempfile import TemporaryDirectory
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from majesty_cam.cam import (
    CamArchive,
    CamEntry,
    CamSection,
    pad_name,
    read_cam,
    write_cam,
)
from majesty_cam.stock_art import (
    StockArtError,
    classify_art_archive,
    collapse_art_archives,
    load_stock_art_lineages,
    StockArtLineage,
    _sparse_component_archive,
    _overlay_positional,
)
from majesty_cam.art import analyze_art_archive


class StockArtTests(unittest.TestCase):
    def test_empty_named_inheritance_survives_sparse_collapse(self):
        original = _named_tiles(_archive((_image(b"MAIN", 300, 1),),
                                         (b"", _tile(0, marker=7)), palette=b"SPLT"), b"Adept")
        expansion = _named_tiles(_archive((_image(b"MAIN", 300, 1),),
                                          (b"", _tile(0, marker=90)), palette=b"SPLT"), b"Ratapult")
        lineage = StockArtLineage("main", (Path("original.cam"),Path("expansion.cam")), (original,), expansion)
        private = _named_tiles(_archive((_image(b"NEW1", 300, 1),), (b"", b"")), b"Adept")
        sparse = _sparse_component_archive(lineage, (private,))
        self.assertEqual(_section(sparse,b"TILE").entries[1].name, _section(original,b"TILE").entries[1].name)
        analysis = analyze_art_archive(expansion,sparse,mod_id="private",fallthrough_ancestors=(original,))
        change = next(item for item in analysis.tile_delta.changes if item.index == 1)
        self.assertEqual(change.entry.data, _section(original,b"TILE").entries[1].data)
        self.assertNotEqual(change.entry.data, _section(expansion,b"TILE").entries[1].data)
        # Empty hints never replace an earlier actual authored payload, and
        # native stock dataset overlays still ignore empty slots entirely.
        written = _overlay_positional(_section(expansion,b"TILE"), _section(private,b"TILE"), preserve_inherited_names=True)
        self.assertEqual(written.entries[1], _section(expansion,b"TILE").entries[1])
        native = _overlay_positional(_section(expansion,b"TILE"), _section(private,b"TILE"))
        self.assertEqual(native, _section(expansion,b"TILE"))

    def test_equal_tile_indices_in_different_named_tables_are_not_dependencies(self):
        # A panel's stock fallthrough slot and a world sprite may use the same
        # number. Neither direction of dependency inference may join them.
        for world_writes, ui_writes in ((True, False), (False, True)):
            with self.subTest(world_writes=world_writes), TemporaryDirectory() as tmp:
                root = Path(tmp)
                game, stock_paths = _stock_game(root)
                # These empty dependencies must name their actual stock
                # family; arbitrary placeholder labels aren't ancestry proof.
                for domain, family in (("main", b"world"), ("interface", b"panel")):
                    write_cam(_named_tiles(read_cam(stock_paths[domain]), family), stock_paths[domain])
                world = _named_tiles(_archive(
                    (_image(b"MAIN", 2801, 1),),
                    (b"", _tile(0, marker=110) if world_writes else b"", b""),
                ), b"world")
                panel = _named_tiles(_archive(
                    (_image(b"NEW1", 2802, 1), _image(b"NEW2", 2803, 3)),
                    (b"", _tile(0, marker=111) if ui_writes else b"", b"", _tile(0, marker=112)),
                ), b"panel")
                world_path = _write_cam(root / "world.cam", world)
                panel_path = _write_cam(root / "example_interfacedata.cam", panel)
                for paths in ((world_path, panel_path), (panel_path, world_path)):
                    collapsed = collapse_art_archives(game, paths, owner="unrelated-tables")
                    by_domain = {item.lineage.domain: item for item in collapsed}
                    self.assertEqual(set(by_domain), {"main", "interface"})
                    self.assertEqual(by_domain["main"].paths, (world_path,))
                    self.assertEqual(by_domain["interface"].paths, (panel_path,))

    def test_named_blank_slot_can_depend_on_matching_provider(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            game, _ = _stock_game(root)
            provider = _named_tiles(_archive(
                (_image(b"MAIN", 2811, 1),), (b"", _tile(0, marker=115), b""),
            ), b"shared")
            dependent = _named_tiles(_archive(
                (_image(b"NEW1", 2812, 1),), (b"", b"", b""),
            ), b"shared")
            paths = (_write_cam(root / "one.cam", provider), _write_cam(root / "two.cam", dependent))
            (collapsed,) = collapse_art_archives(game, paths, owner="named-dependency")
            self.assertEqual(collapsed.lineage.domain, "main")
            self.assertEqual(collapsed.paths, paths)

    def test_named_table_contradiction_without_declaration_stays_unresolved(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            game, _ = _stock_game(root)
            provider = _named_tiles(_archive(
                (_image(b"MAIN", 2821, 1),), (b"", _tile(0, marker=115), b""),
            ), b"world")
            dependent = _named_tiles(_archive(
                (_image(b"NEW1", 2822, 1),), (b"", b"", b""),
            ), b"unrelated")
            paths = (_write_cam(root / "one.cam", provider), _write_cam(root / "two.cam", dependent))
            with self.assertRaisesRegex(StockArtError, "no provable installed stock lineage"):
                collapse_art_archives(game, paths, owner="not-a-dependency")

    def test_imag_only_multiple_suppliers_remain_ambiguous(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            game, _ = _stock_game(root)
            world = _named_tiles(_archive(
                (_image(b"MAIN", 2831, 1),), (b"", _tile(0, marker=115), b""),
            ), b"world")
            panel = _named_tiles(_archive(
                (_image(b"CUR1", 2832, 1),), (b"", _tile(0, marker=116), b""),
            ), b"panel")
            unknown = CamArchive((CamSection(b"IMAG", (_image(b"NEW1", 2833, 1),)),))
            paths = (_write_cam(root / "one.cam", world), _write_cam(root / "two.cam", panel),
                     _write_cam(root / "ambiguous.cam", unknown))
            with self.assertRaisesRegex(StockArtError, "ambiguous.cam: positional art ancestry is ambiguous"):
                collapse_art_archives(game, paths, owner="unknown")

    def test_same_lineage_stock_overlay_preserves_positional_padding(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            game, stock_paths = _stock_game(root)
            tile_padding = b"\x12\x34\x56\x78"
            palette_padding = b"\x87\x65\x43\x21"

            base = read_cam(stock_paths["main"])
            write_cam(
                CamArchive(
                    tuple(
                        CamSection(
                            section.extension,
                            section.entries,
                            padding=(
                                tile_padding
                                if section.extension == b"TILE"
                                else (
                                    palette_padding
                                    if section.extension == b"SPLT"
                                    else section.padding
                                )
                            ),
                        )
                        for section in base.sections
                    )
                ),
                stock_paths["main"],
            )

            expansion = game / "DataMX"
            _write_cam(
                expansion / "mx_maindata.cam",
                _archive(
                    (_image(b"MAIN", 1005, 1),),
                    (b"", _tile(0, marker=13), b""),
                    palette=b"SPLT",
                ),
            )
            (expansion / "MajestyExpansionDatasetDefinitions.xml").write_text(
                '<Majesty><DataConfiguration><Dataset base="Majesty"><Load>'
                "<CAM>mx_maindata.cam</CAM><CAM>addinterface.cam</CAM>"
                "<CAM>tileset.cam</CAM>"
                "</Load></Dataset></DataConfiguration></Majesty>",
                encoding="utf-8",
            )

            lineage = next(
                item for item in load_stock_art_lineages(game) if item.domain == "main"
            )
            self.assertEqual(
                tuple(path.name for path in lineage.source_paths),
                ("maindata.cam", "mx_maindata.cam"),
            )
            self.assertEqual(
                _section(lineage.effective, b"TILE").padding,
                tile_padding,
            )
            self.assertEqual(
                _section(lineage.effective, b"SPLT").padding,
                palette_padding,
            )

            round_trip = read_cam(lineage.effective.to_bytes())
            self.assertEqual(_section(round_trip, b"TILE").padding, tile_padding)
            self.assertEqual(
                _section(round_trip, b"SPLT").padding,
                palette_padding,
            )

    def test_stock_copy_has_no_delta_despite_unrelated_unsupported_imag(self):
        with TemporaryDirectory() as tmp:
            game, stock_paths = _stock_game(Path(tmp))
            lineages = load_stock_art_lineages(game)

            lineage, analysis = classify_art_archive(
                lineages,
                read_cam(stock_paths["main"]),
                owner="stock-copy",
            )

            self.assertEqual(lineage.domain, "main")
            self.assertEqual(analysis.tile_delta.changes, ())
            self.assertEqual(analysis.palette_delta.changes, ())
            self.assertEqual(analysis.imag_entries, ())
            self.assertEqual(analysis.unreferenced_tile_changes, ())

    def test_sparse_main_and_interface_overlays_analyze_only_owned_art(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            game, _stock_paths = _stock_game(root)
            lineages = load_stock_art_lineages(game)
            cases = (
                ("main", b"MAIN", 2101),
                ("interface", b"CUR1", 2102),
            )
            for expected_domain, image_id, set_id in cases:
                with self.subTest(expected_domain):
                    image = _image(image_id, set_id, 1)
                    changed_tile = _tile(0, marker=20 + set_id)
                    overlay = _archive(
                        (image,),
                        (b"", changed_tile, b""),
                    )

                    lineage, analysis = classify_art_archive(
                        lineages,
                        overlay,
                        owner=f"sparse-{expected_domain}",
                    )

                    self.assertEqual(lineage.domain, expected_domain)
                    self.assertEqual(
                        tuple(entry.name[:4] for entry in analysis.imag_entries),
                        (image_id,),
                    )
                    self.assertEqual(analysis.tile_delta.changed_indices, (1,))
                    self.assertEqual(analysis.unreferenced_tile_changes, ())
                    self.assertNotIn(b"BAD1", {
                        entry.name[:4] for entry in analysis.imag_entries
                    })
                    self.assertNotIn(b"BAD2", {
                        entry.name[:4] for entry in analysis.imag_entries
                    })

    def test_addinterface_and_tileset_classify_as_independent_families(self):
        with TemporaryDirectory() as tmp:
            game, _stock_paths = _stock_game(Path(tmp))
            lineages = load_stock_art_lineages(game)
            classified = {}
            for label, image_id, set_id in (
                ("addinterface", b"AIF1", 2201),
                ("tileset", b"TSET", 2202),
            ):
                overlay = _archive(
                    (_image(image_id, set_id, 0),),
                    (_tile(0, marker=set_id), b"", b""),
                )
                lineage, analysis = classify_art_archive(
                    lineages,
                    overlay,
                    owner=label,
                )
                classified[label] = lineage
                self.assertEqual(analysis.tile_delta.changed_indices, (0,))
                self.assertEqual(analysis.unreferenced_tile_changes, ())

            self.assertNotEqual(
                classified["addinterface"].lineage_id,
                classified["tileset"].lineage_id,
            )
            self.assertEqual(
                classified["addinterface"].source_paths[-1].name,
                "addinterface.cam",
            )
            self.assertEqual(
                classified["tileset"].source_paths[-1].name,
                "tileset.cam",
            )

    def test_same_owner_later_cam_overrides_earlier_same_key_art(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            game, _stock_paths = _stock_game(root)
            mod_root = root / "mod"
            mod_root.mkdir()
            first_image = _image(b"MAIN", 2301, 1)
            second_image = _image(b"MAIN", 2302, 1)
            first_tile = _tile(0, marker=31)
            second_tile = _tile(0, marker=32)
            first = _write_cam(
                mod_root / "first.cam",
                _archive((first_image,), (b"", first_tile, b"")),
            )
            second = _write_cam(
                mod_root / "second.cam",
                _archive((second_image,), (b"", second_tile, b"")),
            )

            (collapsed,) = collapse_art_archives(
                game,
                (first, second),
                owner="same-owner",
            )

            self.assertEqual(collapsed.paths, (first, second))
            self.assertEqual(
                _entry_for(collapsed.archive, b"IMAG", b"MAIN").data,
                second_image.data,
            )
            self.assertEqual(
                _section(collapsed.archive, b"TILE").entries[1].data,
                second_tile,
            )
            self.assertEqual(collapsed.analysis.tile_delta.changed_indices, (1,))

    def test_unanchored_custom_art_fails_closed_when_lineage_is_ambiguous(self):
        with TemporaryDirectory() as tmp:
            game, _stock_paths = _stock_game(Path(tmp))
            lineages = load_stock_art_lineages(game)
            unanchored = _archive(
                (_image(b"NEW1", 2401, 0),),
                (_tile(0, marker=99), b"", b""),
            )

            with self.assertRaisesRegex(
                StockArtError,
                "no provable installed stock lineage",
            ):
                classify_art_archive(
                    lineages,
                    unanchored,
                    owner="unanchored",
                )

    def test_stock_family_length_is_not_positional_lineage_evidence(self):
        with TemporaryDirectory() as tmp:
            game, _stock_paths = _stock_game(Path(tmp))
            lineages = load_stock_art_lineages(game)
            # Every synthetic stock family has three TILE rows. A custom
            # archive beginning its private range at index three therefore
            # looks superficially like an append, but that coincidence is not
            # ancestry evidence.
            unanchored = _archive(
                (
                    _image(b"NEW1", 2501, 3),
                    _image(b"NEW2", 2502, 4),
                ),
                (
                    b"",
                    b"",
                    b"",
                    _tile(0, marker=100),
                    _tile(0, marker=101),
                ),
            )

            with self.assertRaisesRegex(
                StockArtError,
                "no provable installed stock lineage",
            ):
                classify_art_archive(
                    lineages,
                    unanchored,
                    owner="length-coincidence",
                )

    def test_stock_basename_suffix_declares_unanchored_art_lineage(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            game, _stock_paths = _stock_game(root)
            mod_root = root / "mod"
            mod_root.mkdir()
            declared = _write_cam(
                mod_root / "example_interfacedata.cam",
                _archive(
                    (_image(b"NEW1", 2551, 3),),
                    (
                        b"",
                        b"",
                        b"",
                        _tile(0, marker=100),
                    ),
                ),
            )

            (collapsed,) = collapse_art_archives(
                game,
                (declared,),
                owner="filename-declared",
            )

            self.assertEqual(collapsed.lineage.domain, "interface")
            self.assertEqual(collapsed.paths, (declared,))

    def test_stock_basename_substring_without_separator_is_not_a_declaration(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            game, _stock_paths = _stock_game(root)
            mod_root = root / "mod"
            mod_root.mkdir()
            coincidental = _write_cam(
                mod_root / "notinterfacedata.cam",
                _archive(
                    (_image(b"NEW1", 2552, 3),),
                    (
                        b"",
                        b"",
                        b"",
                        _tile(0, marker=101),
                    ),
                ),
            )

            with self.assertRaisesRegex(
                StockArtError,
                "no provable installed stock lineage",
            ):
                collapse_art_archives(
                    game,
                    (coincidental,),
                    owner="filename-coincidence",
                )

    def test_unrelated_unanchored_cam_does_not_inherit_sole_proven_lineage(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            game, stock_paths = _stock_game(root)
            mod_root = root / "mod"
            mod_root.mkdir()
            unanchored = _write_cam(
                mod_root / "first.cam",
                _archive(
                    (_image(b"NEW1", 2601, 1),),
                    (b"", _tile(0, marker=101), b""),
                ),
            )
            main_stock = read_cam(stock_paths["main"])
            main_anchor = _entry_for(main_stock, b"IMAG", b"MAIN")
            anchored = _write_cam(
                mod_root / "second.cam",
                _archive((main_anchor,), (b"", b"", b"")),
            )

            with self.assertRaisesRegex(
                StockArtError,
                "no provable installed stock lineage",
            ):
                collapse_art_archives(
                    game,
                    (unanchored, anchored),
                    owner="ordered-component",
                )

    def test_unanchored_cam_can_join_unique_stock_anchored_tile_provider(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            game, _stock_paths = _stock_game(root)
            mod_root = root / "mod"
            mod_root.mkdir()
            anchored = _write_cam(
                mod_root / "first.cam",
                _archive(
                    (_image(b"MAIN", 2701, 1),),
                    (b"", _tile(0, marker=111), b""),
                ),
            )
            dependent = mod_root / "second.cam"
            write_cam(
                CamArchive(
                    (
                        CamSection(
                            b"IMAG",
                            (_image(b"NEW1", 2702, 1),),
                        ),
                    )
                ),
                dependent,
            )

            (collapsed,) = collapse_art_archives(
                game,
                (anchored, dependent),
                owner="dependent-component",
            )

            self.assertEqual(collapsed.lineage.domain, "main")
            self.assertEqual(collapsed.paths, (anchored, dependent))
            self.assertEqual(
                tuple(entry.name[:4] for entry in collapsed.analysis.imag_entries),
                (b"MAIN", b"NEW1"),
            )
            self.assertEqual(collapsed.analysis.tile_delta.changed_indices, (1,))


def _stock_game(root: Path):
    game = root / "game"
    data = game / "Data"
    expansion = game / "DataMX"
    data.mkdir(parents=True)
    expansion.mkdir()

    stock_paths = {
        "main": _write_cam(
            data / "maindata.cam",
            _archive(
                (
                    _image(b"MAIN", 1001, 0),
                    CamEntry(pad_name(b"BAD1 unsupported"), b"not-an-imag"),
                ),
                (_tile(0, marker=1), _tile(0, marker=2), _tile(0, marker=3)),
                palette=b"SPLT",
            ),
        ),
        "interface": _write_cam(
            data / "interfacedata.cam",
            _archive(
                (
                    _image(b"CUR1", 1002, 0),
                    CamEntry(pad_name(b"BAD2 unsupported"), b"not-an-imag"),
                ),
                (_tile(0, marker=4), _tile(0, marker=5), _tile(0, marker=6)),
                palette=b"PALT",
            ),
        ),
        "addinterface": _write_cam(
            expansion / "addinterface.cam",
            _archive(
                (_image(b"AIF1", 1003, 0),),
                (_tile(0, marker=7), _tile(0, marker=8), _tile(0, marker=9)),
            ),
        ),
        "tileset": _write_cam(
            expansion / "tileset.cam",
            _archive(
                (_image(b"TSET", 1004, 0),),
                (_tile(0, marker=10), _tile(0, marker=11), _tile(0, marker=12)),
            ),
        ),
    }
    (data / "MajestyDatasetDefinitions.xml").write_text(
        "<Majesty><DataConfiguration><Dataset><Load>"
        "<CAM>maindata.cam</CAM><CAM>interfacedata.cam</CAM>"
        "</Load></Dataset></DataConfiguration></Majesty>",
        encoding="utf-8",
    )
    (expansion / "MajestyExpansionDatasetDefinitions.xml").write_text(
        "<Majesty><DataConfiguration><Dataset base=\"Majesty\"><Load>"
        "<CAM>addinterface.cam</CAM><CAM>tileset.cam</CAM>"
        "</Load></Dataset></DataConfiguration></Majesty>",
        encoding="utf-8",
    )
    return game, stock_paths


def _archive(images, tiles, *, palette=None):
    sections = [
        CamSection(b"IMAG", tuple(images)),
        CamSection(
            b"TILE",
            tuple(
                CamEntry(index.to_bytes(4, "little").ljust(20, b"\x00"), payload)
                for index, payload in enumerate(tiles)
            ),
            padding=b"\x01\x00\x00\x00",
        ),
    ]
    if palette is not None:
        sections.append(
            CamSection(
                palette,
                tuple(
                    CamEntry(
                        index.to_bytes(4, "little").ljust(20, b"\x00"),
                        bytes((index + 1,)),
                    )
                    for index in range(2)
                ),
                padding=(
                    b"\x01\x00\x00\x00"
                    if palette == b"SPLT"
                    else b"\x00\x00\x00\x00"
                ),
            )
        )
    return CamArchive(tuple(sections))


def _named_tiles(archive: CamArchive, family: bytes) -> CamArchive:
    return CamArchive(tuple(
        CamSection(section.extension, tuple(
            CamEntry(pad_name(index.to_bytes(4, "little") + family), entry.data)
            for index, entry in enumerate(section.entries)
        ), padding=section.padding) if section.extension == b"TILE" else section
        for section in archive.sections
    ))


def _image(name: bytes, set_id: int, tile_index: int) -> CamEntry:
    direction = bytearray(32)
    struct.pack_into("<I", direction, 4, 0x00010001)
    struct.pack_into("<I", direction, 16, 0x00010000)
    struct.pack_into("<I", direction, 28, tile_index)
    chunk = bytearray(68)
    struct.pack_into("<I", chunk, 0, 1)
    struct.pack_into("<i", chunk, 64, 68)
    chunk.extend(direction)
    payload = bytearray(20)
    payload.extend(struct.pack("<I", 1))
    payload.extend(struct.pack("<II", set_id, 32))
    payload.extend(chunk)
    return CamEntry(pad_name(name), bytes(payload))


def _tile(palette_index: int, *, marker: int) -> bytes:
    tile = bytearray(27)
    struct.pack_into("<H", tile, 0, 1)
    struct.pack_into("<H", tile, 2, 1)
    struct.pack_into("<H", tile, 4, 1)
    struct.pack_into("<I", tile, 22, palette_index)
    tile[26] = marker & 0xFF
    return bytes(tile)


def _write_cam(path: Path, archive: CamArchive) -> Path:
    path.write_bytes(archive.to_bytes())
    return path


def _section(archive: CamArchive, extension: bytes) -> CamSection:
    return next(section for section in archive.sections if section.extension == extension)


def _entry_for(archive: CamArchive, extension: bytes, key: bytes) -> CamEntry:
    return next(
        entry
        for entry in _section(archive, extension).entries
        if entry.name.rstrip(b"\x00")[:4] == key
    )


if __name__ == "__main__":
    unittest.main()
