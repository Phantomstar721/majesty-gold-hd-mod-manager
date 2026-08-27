from pathlib import Path
import struct
import sys
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from majesty_cam.art import (
    ArtFormatError,
    UnprovenReferenceError,
    UnsupportedImagShapeError,
    allocate_collision_free_ranges,
    analyze_art_archive,
    compute_stock_relative_delta,
    find_positional_collisions,
    parse_imag_tile_references,
    parse_tile_palette_reference,
    rewrite_imag_entries,
    rewrite_imag_tile_indices,
    rewrite_tile_palette_indices,
    validate_external_palette_closure,
)
from majesty_cam.cam import CamArchive, CamEntry, CamSection, pad_extension, pad_name


class PositionalArtTests(unittest.TestCase):
    def test_stock_relative_delta_ignores_fallthrough_and_identical_payloads(self):
        stock = _section(
            "TILE",
            [
                _entry("stock-0", b"zero"),
                _entry("stock-1", b"one"),
                _entry("stock-2", b"two"),
            ],
        )
        mod = _section(
            "TILE",
            [
                _entry("empty", b""),
                _entry("renamed-identical", b"one"),
                _entry("private-2", b"changed-two"),
                _entry("private-3", b"three"),
            ],
        )

        delta = compute_stock_relative_delta(stock, mod)

        self.assertEqual(delta.changed_indices, (2, 3))
        self.assertEqual([change.kind for change in delta.changes], ["replace", "append"])
        self.assertEqual(delta.fallthrough_count, 1)
        self.assertEqual(delta.stock_identical_count, 1)

    def test_collision_report_distinguishes_shared_and_conflicting_payloads(self):
        stock = _section("SPLT", [_entry("stock", b"base")])
        first = compute_stock_relative_delta(
            stock,
            _section("SPLT", [_entry("first", b"shared"), _entry("first-1", b"one")]),
        )
        second = compute_stock_relative_delta(
            stock,
            _section("SPLT", [_entry("second", b"shared"), _entry("second-1", b"two")]),
        )

        collisions = find_positional_collisions({"zeta": second, "alpha": first})

        self.assertEqual([(item.index, item.mods) for item in collisions], [
            (0, ("alpha", "zeta")),
            (1, ("alpha", "zeta")),
        ])
        self.assertTrue(collisions[0].identical_payload)
        self.assertFalse(collisions[1].identical_payload)

    def test_allocation_is_dense_deterministic_and_can_select_movable_slots(self):
        stock = _section("TILE", [_entry("stock-0", b"base")])
        alpha = compute_stock_relative_delta(
            stock,
            _section(
                "TILE",
                [_entry("alpha-fixed", b"fixed"), _entry("alpha-a", b"a"), _entry("alpha-b", b"b")],
            ),
        )
        zeta = compute_stock_relative_delta(
            stock,
            _section("TILE", [_entry("zeta-fixed", b"other"), _entry("zeta-a", b"z")]),
        )

        report = allocate_collision_free_ranges(
            {"zeta": zeta, "alpha": alpha},
            indices_by_mod={"alpha": (1, 2), "zeta": (1,)},
            maximum_index=10,
        )

        self.assertEqual([item.mod_id for item in report.ranges], ["alpha", "zeta"])
        self.assertEqual(report.mapping_for("alpha"), {1: 1, 2: 2})
        self.assertEqual(report.mapping_for("zeta"), {1: 3})
        self.assertEqual((report.ranges[0].start, report.ranges[0].stop), (1, 3))
        self.assertEqual(report.final_count, 4)

    def test_allocation_rejects_a_slot_that_is_not_a_delta(self):
        stock = _section("TILE", [_entry("stock", b"base")])
        delta = compute_stock_relative_delta(
            stock,
            _section("TILE", [_entry("empty", b"")]),
        )

        with self.assertRaisesRegex(ArtFormatError, "has no"):
            allocate_collision_free_ranges(
                {"mod": delta},
                indices_by_mod={"mod": (0,)},
            )

    def test_unselected_appended_slots_are_reserved_not_reused(self):
        stock = _section("TILE", [_entry("stock", b"base")])
        delta = compute_stock_relative_delta(
            stock,
            _section(
                "TILE",
                [
                    _entry("changed-stock", b"fixed"),
                    _entry("movable", b"move"),
                    _entry("empty-2", b""),
                    _entry("empty-3", b""),
                    _entry("empty-4", b""),
                    _entry("direct-5", b"direct"),
                ],
            ),
        )

        report = allocate_collision_free_ranges(
            {"mod": delta},
            indices_by_mod={"mod": (1,)},
        )

        self.assertEqual(report.ranges[0].start, 6)
        self.assertEqual(report.mapping_for("mod"), {1: 6})


class ImagParserTests(unittest.TestCase):
    def test_compact_extended_and_projectile_layouts_are_typed(self):
        data = _imag(
            [
                _SetSpec(1003, "compact", (3, 4), flag_bits=0x12000000),
                _SetSpec(1, "extended", (5, 6, 7, 8), layers=2),
                _SetSpec(64, "projectile", (9, 10)),
            ]
        )

        parsed = parse_imag_tile_references(
            data,
            tile_count=32,
            entry_name=b"synthetic",
        )

        self.assertEqual(parsed.layouts, ("compact", "extended", "projectile"))
        self.assertEqual(
            [reference.tile_index for reference in parsed.references],
            [3, 4, 5, 6, 7, 8, 9, 10],
        )
        self.assertEqual(parsed.references[0].flag_bits, 0x12000000)
        self.assertEqual(parsed.references[2].layout, "extended")

    def test_short_compact_layout_covers_progress_control_shape(self):
        data = _imag([_SetSpec(1003, "compact-short", (12,))])

        parsed = parse_imag_tile_references(
            data,
            tile_count=20,
            entry_name=b"ALSRalchemy progress",
        )

        self.assertEqual(len(parsed.references), 1)
        self.assertEqual(parsed.references[0].tile_index, 12)
        self.assertEqual(parsed.references[0].offset, 120)

    def test_raw_texture_multiset_records_are_rewritten_with_flags_preserved(self):
        for name in (b"PHTIraw textures", b"ALTIraw textures"):
            data = _imag(
                [
                    _SetSpec(1003, "compact", (7,), flag_bits=0xABCD0000),
                    _SetSpec(1005, "compact", (8,)),
                ]
            )
            entry = CamEntry(name=pad_name(name), data=data)

            result = rewrite_imag_entries(
                (entry,),
                {7: 42},
                tile_count=64,
            )
            reparsed = parse_imag_tile_references(
                result.entries[0].data,
                tile_count=64,
                entry_name=name,
            )

            self.assertEqual(reparsed.references[0].tile_index, 42)
            self.assertEqual(reparsed.references[0].flag_bits, 0xABCD0000)
            self.assertEqual(reparsed.references[1].tile_index, 8)
            self.assertEqual(result.report.supported_layouts, ("compact",))

    def test_stock_building_set_terminal_tile_is_typed_and_rewritten(self):
        data = _imag(
            [
                _SetSpec(
                    208,
                    "extended",
                    (7,),
                    terminal_tile=12,
                    terminal_flag_bits=0x34000000,
                )
            ]
        )

        parsed = parse_imag_tile_references(
            data,
            tile_count=64,
            entry_name=b"ABQ1Temple, Fervus1",
        )

        self.assertEqual(
            [reference.tile_index for reference in parsed.references],
            [7, 12],
        )
        terminal = parsed.references[1]
        self.assertEqual(terminal.layout, "building-terminal")
        self.assertEqual((terminal.direction, terminal.frame), (-1, -1))
        self.assertEqual(terminal.offset, len(data) - 4)
        self.assertEqual(terminal.flag_bits, 0x34000000)

        rewritten = rewrite_imag_tile_indices(
            data,
            {12: 40},
            tile_count=64,
            entry_name=b"PHG1Phantom Guild",
        )
        reparsed = parse_imag_tile_references(rewritten, tile_count=64)
        self.assertEqual(
            [reference.tile_index for reference in reparsed.references],
            [7, 40],
        )
        self.assertEqual(reparsed.references[1].flag_bits, 0x34000000)

    def test_rewriter_changes_only_typed_frame_fields_not_equal_header_words(self):
        data = bytearray(_imag([_SetSpec(64, "compact", (7, 8))]))
        struct.pack_into("<I", data, 0, 7)  # Looks like a TILE index, but is an IMAG header field.

        rewritten = rewrite_imag_tile_indices(
            bytes(data),
            {7: 30},
            tile_count=64,
            entry_name=b"typed-only",
        )

        self.assertEqual(struct.unpack_from("<I", rewritten, 0)[0], 7)
        parsed = parse_imag_tile_references(rewritten, tile_count=64)
        self.assertEqual([item.tile_index for item in parsed.references], [30, 8])

    def test_rewriter_fails_when_an_affected_slot_has_no_reference(self):
        entry = CamEntry(
            name=pad_name("known"),
            data=_imag([_SetSpec(64, "compact", (7,))]),
        )

        with self.assertRaises(UnprovenReferenceError) as raised:
            rewrite_imag_entries((entry,), {12: 40}, tile_count=64)

        self.assertEqual(raised.exception.slots, (12,))

    def test_unsupported_direction_shape_fails_instead_of_scanning(self):
        data = bytearray(_imag([_SetSpec(64, "compact", (7,))]))
        # The direction begins at 100. Remove both audited count words while a
        # coincidental value 7 remains elsewhere in the payload.
        struct.pack_into("<I", data, 104, 0)
        struct.pack_into("<I", data, 128, 0)

        with self.assertRaises(UnsupportedImagShapeError):
            parse_imag_tile_references(bytes(data), tile_count=64)

    def test_reference_outside_tile_section_fails(self):
        data = _imag([_SetSpec(64, "compact", (99,))])

        with self.assertRaisesRegex(UnsupportedImagShapeError, "missing TILE 99"):
            parse_imag_tile_references(data, tile_count=10)


class PaletteReferenceTests(unittest.TestCase):
    def test_external_palette_closure_requires_materialized_payload(self):
        tiles = _section("TILE", [_entry("custom", _tile(1, marker=9))])
        palettes = _section(
            "SPLT",
            [_entry("palette-0", b"stock"), _entry("palette-1", b"")],
        )

        with self.assertRaisesRegex(
            ArtFormatError,
            "TILE 0 -> SPLT 1",
        ):
            validate_external_palette_closure(tiles, palettes)

    def test_external_palette_closure_accepts_materialized_payload(self):
        tiles = _section("TILE", [_entry("custom", _tile(1, marker=9))])
        palettes = _section(
            "SPLT",
            [_entry("palette-0", b"stock"), _entry("palette-1", b"resolved")],
        )

        references = validate_external_palette_closure(tiles, palettes)

        self.assertEqual(
            [(item.tile_index, item.palette_index) for item in references],
            [(0, 1)],
        )

    def test_external_palette_header_is_parsed_and_rewritten(self):
        entries = (
            _entry("custom-0", _tile(560)),
            _entry("custom-1", _tile(854)),
        )

        result = rewrite_tile_palette_indices(entries, {560: 900})

        self.assertEqual(
            parse_tile_palette_reference(result.entries[0].data, tile_index=0).palette_index,
            900,
        )
        self.assertEqual(
            parse_tile_palette_reference(result.entries[1].data, tile_index=1).palette_index,
            854,
        )
        self.assertEqual(result.report.rewritten_slots, (560,))

    def test_palette_rewriter_only_touches_selected_owned_tiles(self):
        entries = (
            _entry("stock-copy", _tile(560)),
            _entry("private", _tile(560)),
        )

        result = rewrite_tile_palette_indices(
            entries,
            {560: 900},
            tile_indices=(1,),
        )

        self.assertEqual(struct.unpack_from("<I", result.entries[0].data, 22)[0], 560)
        self.assertEqual(struct.unpack_from("<I", result.entries[1].data, 22)[0], 900)

    def test_palette_rewriter_fails_without_a_proven_owned_tile_reference(self):
        entries = (_entry("custom", _tile(854)),)

        with self.assertRaises(UnprovenReferenceError) as raised:
            rewrite_tile_palette_indices(entries, {560: 900})

        self.assertEqual(raised.exception.slots, (560,))

    def test_embedded_palette_is_not_reported_as_splt_reference(self):
        tile = bytearray(_tile(0))
        tile.extend(b"palette")
        struct.pack_into("<H", tile, 20, 1)
        struct.pack_into("<I", tile, 22, 26)

        self.assertIsNone(parse_tile_palette_reference(bytes(tile), tile_index=4))


class ArtArchiveAnalysisTests(unittest.TestCase):
    def test_analysis_combines_stock_delta_and_typed_reference_proofs(self):
        stock = CamArchive(
            sections=(
                _section("TILE", [_entry("stock-0", _tile(0)), _entry("stock-1", _tile(0))]),
                _section("SPLT", [_entry("stock-palette", b"stock")]),
            )
        )
        mod = CamArchive(
            sections=(
                _section(
                    "IMAG",
                    [_entry("PHTIraw textures", _imag([_SetSpec(1003, "compact", (1,))]))],
                ),
                _section("TILE", [_entry("fallback", b""), _entry("private", _tile(0, marker=9))]),
                _section("SPLT", [_entry("private-palette", b"private")]),
            )
        )

        analysis = analyze_art_archive(stock, mod, mod_id="fixture")

        self.assertEqual(analysis.tile_delta.changed_indices, (1,))
        self.assertEqual(analysis.retained_tile_dependencies, ())
        self.assertEqual(analysis.palette_delta.changed_indices, (0,))
        self.assertEqual(analysis.unreferenced_tile_changes, ())
        self.assertEqual(analysis.unreferenced_palette_changes, ())
        self.assertEqual(analysis.supported_imag_layouts, ("compact",))

    def test_analysis_exposes_direct_or_unknown_tile_slots_without_guessing(self):
        stock = CamArchive(sections=(_section("TILE", [_entry("stock", _tile(0))]),))
        mod = CamArchive(
            sections=(
                _section("IMAG", [_entry("known", _imag([_SetSpec(64, "compact", (0,))]))]),
                _section("TILE", [_entry("changed-known", _tile(0, marker=1)), _entry("direct", _tile(0, marker=2))]),
            )
        )

        analysis = analyze_art_archive(stock, mod, mod_id="fixture")

        self.assertEqual(analysis.unreferenced_tile_changes, (1,))

    def test_analysis_retains_nonempty_stock_tile_owned_by_custom_imag(self):
        stock_tile = _tile(0)
        stock = CamArchive(
            sections=(_section("TILE", [_entry("stock", stock_tile)]),)
        )
        mod = CamArchive(
            sections=(
                _section(
                    "IMAG",
                    [_entry("private", _imag([_SetSpec(1016, "compact", (0,))]))],
                ),
                _section("TILE", [_entry("retained-stock", stock_tile)]),
            )
        )

        analysis = analyze_art_archive(stock, mod, mod_id="fixture")

        self.assertEqual(analysis.tile_delta.changed_indices, (0,))
        self.assertEqual(analysis.retained_tile_dependencies, (0,))
        self.assertEqual(analysis.tile_delta.stock_identical_count, 0)
        self.assertEqual(analysis.unreferenced_tile_changes, ())

    def test_analysis_leaves_unreferenced_stock_copy_as_fallthrough(self):
        first = _tile(0)
        second = _tile(0, marker=1)
        stock = CamArchive(
            sections=(
                _section(
                    "TILE",
                    [_entry("stock-copy", first), _entry("referenced", second)],
                ),
            )
        )
        mod = CamArchive(
            sections=(
                _section(
                    "IMAG",
                    [_entry("private", _imag([_SetSpec(1016, "compact", (1,))]))],
                ),
                _section(
                    "TILE",
                    [_entry("unused-copy", first), _entry("changed", _tile(0, marker=2))],
                ),
            )
        )

        analysis = analyze_art_archive(stock, mod, mod_id="fixture")

        self.assertEqual(analysis.tile_delta.changed_indices, (1,))
        self.assertEqual(analysis.retained_tile_dependencies, ())
        self.assertEqual(analysis.tile_delta.stock_identical_count, 1)


class _SetSpec:
    def __init__(
        self,
        set_id: int,
        layout: str,
        tile_indices: tuple[int, ...],
        *,
        layers: int = 1,
        flag_bits: int = 0,
        terminal_tile=None,
        terminal_flag_bits: int = 0,
    ) -> None:
        self.set_id = set_id
        self.layout = layout
        self.tile_indices = tile_indices
        self.layers = layers
        self.flag_bits = flag_bits
        self.terminal_tile = terminal_tile
        self.terminal_flag_bits = terminal_flag_bits


def _imag(specs: list[_SetSpec]) -> bytes:
    header_size = 24 + len(specs) * 8
    chunks = [_set_chunk(spec) for spec in specs]
    offsets: list[int] = []
    cursor = header_size
    for chunk in chunks:
        offsets.append(cursor)
        cursor += len(chunk)

    output = bytearray(20)
    output += struct.pack("<I", len(specs))
    for spec, offset in zip(specs, offsets):
        output += struct.pack("<II", spec.set_id, offset)
    for chunk in chunks:
        output += chunk
    return bytes(output)


def _set_chunk(spec: _SetSpec) -> bytes:
    if not spec.tile_indices or len(spec.tile_indices) % spec.layers:
        raise AssertionError("Synthetic frames must divide evenly across layers")
    frames = len(spec.tile_indices) // spec.layers
    direction = bytearray()
    if spec.layout in ("compact", "compact-short", "extended"):
        discriminator = 0x3 if spec.layout == "extended" else 0
        base_header = 20 if spec.layout == "compact-short" else 28
        first_tile = base_header + 8 * bin(discriminator).count("1")
        direction.extend(b"\x00" * (first_tile + (len(spec.tile_indices) - 1) * 8 + 4))
        struct.pack_into("<I", direction, 4, (frames << 16) | spec.layers)
        struct.pack_into("<I", direction, 8, discriminator)
        if base_header == 28:
            struct.pack_into("<I", direction, 16, 0x00010000)
    elif spec.layout == "projectile":
        first_tile = 36
        direction.extend(b"\x00" * (first_tile + (len(spec.tile_indices) - 1) * 8 + 4))
        struct.pack_into("<I", direction, 28, (frames << 16) | spec.layers)
    else:
        raise AssertionError(f"Unknown synthetic layout {spec.layout}")

    for frame, tile_index in enumerate(spec.tile_indices):
        struct.pack_into(
            "<I",
            direction,
            first_tile + frame * 8,
            spec.flag_bits | tile_index,
        )

    chunk = bytearray(68)
    struct.pack_into("<I", chunk, 0, 1)
    struct.pack_into("<i", chunk, 64, 68)
    chunk.extend(direction)
    if spec.terminal_tile is not None:
        chunk += struct.pack(
            "<I", spec.terminal_flag_bits | spec.terminal_tile
        )
    return bytes(chunk)


def _tile(palette_index: int, *, marker: int = 0) -> bytes:
    tile = bytearray(27)
    struct.pack_into("<H", tile, 0, 1)
    struct.pack_into("<H", tile, 2, 1)
    struct.pack_into("<H", tile, 4, 1)
    struct.pack_into("<H", tile, 20, 0)
    struct.pack_into("<I", tile, 22, palette_index)
    tile[26] = marker
    return bytes(tile)


def _entry(name: str, data: bytes) -> CamEntry:
    return CamEntry(name=pad_name(name), data=data)


def _section(extension: str, entries: list[CamEntry]) -> CamSection:
    return CamSection(extension=pad_extension(extension), entries=tuple(entries))


if __name__ == "__main__":
    unittest.main()
