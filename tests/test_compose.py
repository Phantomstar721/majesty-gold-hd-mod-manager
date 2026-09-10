from dataclasses import replace
from pathlib import Path
import struct
import sys
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from majesty_cam.art import (
    compute_stock_relative_delta,
    find_positional_collisions,
    parse_stock_imag_tile_references,
)
from majesty_cam.cam import CamArchive, CamEntry, CamSection, pad_name, read_cam
from majesty_cam.compose import (
    CamResource,
    ComposeError,
    DescriptionStockDelta,
    PackageInventory,
    ScopedSemanticResolution,
    SelectedMod,
    _blank_positional_section,
    _build_manifest,
    _derive_runtime_capabilities,
    _discard_incomplete_staging,
    _effective_analysis_tile_entries,
    _first_free_after_reserved,
    _generated_definition,
    _generated_mod_id,
    _validate_generated_runtime_evidence,
    _materialize_effective_stock_prefix,
    _materialize_imag_tile_dependencies,
    _materialize_required_stock_imag_entries,
    _merge_tactical_cursor_entry,
    _imag_set_start,
    _split_imag_sets,
    _strip_unowned_secondary_imag_layers,
    _prove_private_cursor_set_clone,
    _select_later_conflict_runs,
    _selected_art_archive_paths,
    _selected_report_files,
    _validate_generated_cam_outputs,
    compose_package,
    inventory_package,
    merge_art_resources,
    merge_bdep_resource,
    merge_description_resources,
    merge_named_resources,
    merge_gpl_resources,
    merge_text_resources,
    resolve_building_dialogs,
    resolve_controller_registry,
    validate_controller_stock_evidence,
)
from majesty_cam.gpl import GplProjectSourceSet, parse_gpl
from majesty_cam.intent_text import PrivateActivityTextBinding
from majesty_cam.package import (
    CamLoad,
    CustomBuildingDefinition,
    ModDefinition,
    PackagePath,
)
from majesty_cam.runtime_capabilities import (
    PRIVATE_ACTIVITY_TEXT_RUNTIME_CAPABILITY,
    decode_runtime_capability_manifest,
)
from majesty_cam.runtime_features import (
    EnchantmentRowFeature,
    RuntimeFeatureRegistry,
    normalize_runtime_features,
)
from majesty_cam.stock_controller_features import (
    StockAp10Ap69SecondaryPanel,
    StockAp22ResourceMeter,
    StockAp24TimedRageAction,
    legacy_alchemist_controller_features,
)
from majesty_cam.stock_controller_registry import (
    encode_stock_controller_registry,
    resolve_stock_controller_registry,
)


def resource(owner, key, payload, order=0):
    return CamResource(
        owner=owner,
        source=Path(f"{owner}.cam"),
        cam_order=0,
        section_order=0,
        entry_order=order,
        section=b"SMNU",
        entry=CamEntry(name=pad_name(key), data=payload),
    )


def positional(extension, payloads):
    return CamSection(
        extension=extension,
        entries=tuple(
            CamEntry(name=index.to_bytes(4, "little").ljust(20, b"\x00"), data=data)
            for index, data in enumerate(payloads)
        ),
    )


def _generated_cam_paths(root, art_specs=()):
    specs = (
        ("merged_textdata.cam", (b"SMNU", b"STRT")),
        ("merged_gpltext.cam", (b"STRT",)),
        ("merged_miscdata.cam", (b"DATA",)),
        ("merged_audio.cam", (b"WAVE",)),
        ("merged_sounddesc.cam", (b"DSND",)),
        *art_specs,
    )
    data = root / "Data"
    data.mkdir(parents=True, exist_ok=True)
    paths = []
    for filename, extensions in specs:
        path = data / filename
        archive = CamArchive(
            tuple(
                CamSection(
                    extension,
                    (),
                    padding=(
                        b"\x01\x00\x00\x00"
                        if extension in {b"TILE", b"SPLT"}
                        else b"\x00\x00\x00\x00"
                    ),
                )
                for extension in extensions
            )
        )
        path.write_bytes(archive.to_bytes())
        paths.append(
            PackagePath(
                f"Data\\{filename}",
                f"Data/{filename}",
                path,
            )
        )
    return tuple(paths)


def cursor_entry(sets):
    header = b"\x04" + b"\x00" * 19
    offset = 24 + len(sets) * 8
    directory = bytearray()
    payloads = bytearray()
    for set_id, payload in sets:
        directory.extend(struct.pack("<II", set_id, offset))
        payloads.extend(payload)
        offset += len(payload)
    return CamEntry(
        name=pad_name(b"CUR1Tactical Cursor"),
        data=b"".join((header, struct.pack("<I", len(sets)), directory, payloads)),
    )


def typed_cursor_entry(set_id, tile_indices):
    direction = bytearray(28 + (len(tile_indices) - 1) * 8 + 4)
    struct.pack_into("<I", direction, 4, len(tile_indices) << 16 | 1)
    struct.pack_into("<I", direction, 16, 0x00010000)
    for frame, tile_index in enumerate(tile_indices):
        struct.pack_into("<I", direction, 28 + frame * 8, tile_index)
    payload = bytearray(68)
    struct.pack_into("<I", payload, 0, 1)
    struct.pack_into("<i", payload, 64, 68)
    payload.extend(direction)
    return cursor_entry(((set_id, bytes(payload)),))


def typed_imag_set_payload(tile_indices):
    return _split_imag_sets(typed_cursor_entry(1, tile_indices))[1][0][1]


class SecondaryImagLayerOwnershipTests(unittest.TestCase):
    def archive(self, *, secondary_payload=b""):
        image = cursor_entry(
            (
                (0xC0, typed_imag_set_payload((2,))),
                (0x010000C0, typed_imag_set_payload((1,))),
            )
        )
        return CamArchive(
            sections=(
                CamSection(b"IMAG", (image,)),
                positional(b"TILE", (b"", secondary_payload, b"private-base")),
            )
        )

    def analysis(self):
        image = self.archive().sections[0].entries[0]
        parsed = parse_stock_imag_tile_references(
            image.data,
            tile_count=3,
            entry_name=image.name,
        )
        return SimpleNamespace(
            imag_references=parsed.references,
            retained_tile_dependencies=(1,),
        )

    def test_empty_stock_secondary_layer_is_removed_beneath_private_base(self):
        result = _strip_unowned_secondary_imag_layers(
            self.archive(),
            self.analysis(),
        )
        sets = _split_imag_sets(result.sections[0].entries[0])[1]
        self.assertEqual([set_id for set_id, _payload in sets], [0xC0])

    def test_explicit_secondary_layer_payload_is_preserved(self):
        archive = self.archive(secondary_payload=b"explicit-secondary")
        result = _strip_unowned_secondary_imag_layers(
            archive,
            self.analysis(),
        )
        sets = _split_imag_sets(result.sections[0].entries[0])[1]
        self.assertEqual(
            [set_id for set_id, _payload in sets],
            [0xC0, 0x010000C0],
        )


class TacticalCursorMergeTests(unittest.TestCase):
    def test_private_cursor_clone_requires_coherent_auxiliary_stock_art(self):
        stock_cursor = typed_cursor_entry(1005, (7, 8, 7))
        private_cursor = typed_cursor_entry(1038, (20, 8, 20))
        stock_tiles = positional(
            b"TILE",
            tuple(
                b"stock-primary" if index == 7
                else b"stock-aux" if index == 8
                else b""
                for index in range(21)
            ),
        )
        private_tiles = positional(
            b"TILE",
            tuple(
                b"stock-aux" if index == 8
                else b"private-primary" if index == 20
                else b""
                for index in range(21)
            ),
        )
        stock_start = _imag_set_start(stock_cursor, 1005)
        primary_offsets = frozenset(
            reference.offset - stock_start
            for reference in parse_stock_imag_tile_references(
                stock_cursor.data,
                tile_count=len(stock_tiles.entries),
                entry_name=stock_cursor.name,
            ).references
            if reference.set_id == 1005 and reference.tile_index == 7
        )

        accepted, reason = _prove_private_cursor_set_clone(
            private_cursor,
            private_tiles,
            1038,
            stock_cursor,
            stock_tiles,
            1005,
            primary_offsets,
        )
        self.assertTrue(accepted, reason)

        hybrid_entries = list(private_tiles.entries)
        hybrid_entries[8] = replace(hybrid_entries[8], data=b"wrong-dataset-art")
        accepted, reason = _prove_private_cursor_set_clone(
            private_cursor,
            replace(private_tiles, entries=tuple(hybrid_entries)),
            1038,
            stock_cursor,
            stock_tiles,
            1005,
            primary_offsets,
        )
        self.assertFalse(accepted)
        self.assertIn("different stock dataset", reason)

    def test_emitted_cursor_materializes_unchanged_stock_tile_dependencies(self):
        stock_tiles = positional(b"TILE", (b"zero", b"normal-cursor"))
        output_tiles = list(positional(b"TILE", (b"", b"")).entries)
        parsed = SimpleNamespace(
            references=(SimpleNamespace(tile_index=1),),
        )
        with patch(
            "majesty_cam.compose.parse_imag_tile_references",
            return_value=parsed,
        ), patch(
            "majesty_cam.compose.parse_stock_imag_tile_references",
            return_value=parsed,
        ):
            materialized = _materialize_imag_tile_dependencies(
                output_tiles,
                stock_tiles,
                (cursor_entry(((1000, b"stock"),)),),
            )

        self.assertEqual(materialized, (1,))
        self.assertEqual(output_tiles[1].data, b"normal-cursor")

    def test_stock_sets_fall_through_and_private_sets_combine(self):
        stock = cursor_entry(((1000, b"stock"),))
        ancestor = cursor_entry(((1000, b"original"),))
        resources = (
            CamResource(
                owner="first", source=Path("first.cam"), cam_order=0,
                section_order=0, entry_order=0, section=b"IMAG",
                entry=cursor_entry(((1000, b"original"), (1038, b"first"))),
            ),
            CamResource(
                owner="second", source=Path("second.cam"), cam_order=0,
                section_order=0, entry_order=0, section=b"IMAG",
                entry=cursor_entry(((1000, b"stock"), (1039, b"second"))),
            ),
        )

        merged = _merge_tactical_cursor_entry(stock, (ancestor,), resources)
        count = struct.unpack_from("<I", merged.data, 20)[0]
        set_ids = tuple(
            struct.unpack_from("<I", merged.data, 24 + index * 8)[0]
            for index in range(count)
        )

        self.assertEqual(set_ids, (1000, 1038, 1039))


class PassthroughCompositionBoundaryTests(unittest.TestCase):
    @staticmethod
    def _art_archive() -> CamArchive:
        return CamArchive(
            sections=(
                CamSection(b"IMAG", ()),
                positional(b"TILE", (b"private-art",)),
            )
        )

    @staticmethod
    def _stock_art(root: Path) -> None:
        data = root / "Data"
        data.mkdir(parents=True)
        data_mx = root / "DataMX"
        data_mx.mkdir()
        (data / "MajestyDatasetDefinitions.xml").write_text(
            "<Majesty><DataConfiguration><Dataset><Load>"
            "<CAM>interfacedata.cam</CAM><CAM>maindata.cam</CAM>"
            "</Load></Dataset></DataConfiguration></Majesty>",
            encoding="utf-8",
        )
        (data_mx / "MajestyExpansionDatasetDefinitions.xml").write_text(
            "<Majesty><DataConfiguration><Dataset><Load />"
            "</Dataset></DataConfiguration></Majesty>",
            encoding="utf-8",
        )
        (data / "interfacedata.cam").write_bytes(
            CamArchive(
                sections=(
                    CamSection(b"IMAG", (CamEntry(pad_name(b"CUR1"), b"cursor"),)),
                    positional(b"TILE", (b"stock-art",)),
                )
            ).to_bytes()
        )
        (data / "maindata.cam").write_bytes(
            CamArchive(
                sections=(
                    CamSection(b"IMAG", (CamEntry(pad_name(b"MAIN"), b"main"),)),
                    positional(b"TILE", (b"stock-main-0", b"stock-main-1")),
                    positional(b"SPLT", (b"palette",)),
                )
            ).to_bytes()
        )

    @staticmethod
    def _standard_inventory(
        root: Path,
        *,
        art_archive_filter=None,
    ) -> tuple[PackageInventory, Path]:
        data = root / "Data"
        data.mkdir(parents=True)
        art = data / "standard-art.cam"
        art.write_bytes(
            PassthroughCompositionBoundaryTests._art_archive().to_bytes()
        )
        package = SimpleNamespace(
            root=root,
            definition=SimpleNamespace(schema_version=3),
            datasets=(
                SimpleNamespace(
                    base="Any",
                    loads=(
                        SimpleNamespace(
                            directives=(
                                CamLoad(
                                    PackagePath(
                                        declared_path="Data\\standard-art.cam",
                                        relative_path="Data/standard-art.cam",
                                        absolute_path=art,
                                    )
                                ),
                            )
                        ),
                    ),
                ),
            ),
        )
        selected = SelectedMod(
            "standard",
            package,
            semantic_passthrough=True,
            art_archive_filter=art_archive_filter,
        )
        return inventory_package(selected), art

    def test_passthrough_art_is_excluded_until_exact_archive_is_opted_in(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            game = root / "game"
            package_root = root / "standard"
            self._stock_art(game)
            inventory, art = self._standard_inventory(package_root)

            self.assertEqual(inventory.cams, (art,))
            self.assertEqual(inventory.art_cams, ())

            def reject_standard_art(path):
                if Path(path).resolve() == art.resolve():
                    raise AssertionError("passthrough art crossed composition boundary")
                return read_cam(path)

            with patch(
                "majesty_cam.compose.read_cam", side_effect=reject_standard_art
            ):
                main, interface = merge_art_resources(game, (inventory,))

            self.assertEqual(main.analyses, ())
            self.assertEqual(interface.analyses, ())
            self.assertTrue(
                all(not section.entries for section in main.archive.sections)
            )
            self.assertTrue(
                all(not section.entries for section in interface.archive.sections)
            )
            self.assertEqual(main.report.tile_allocation.stock_count, 2)
            self.assertEqual(interface.report.tile_allocation.stock_count, 1)

    def test_explicit_passthrough_art_archive_is_consumed(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            game = root / "game"
            package_root = root / "standard"
            self._stock_art(game)
            inventory, art = self._standard_inventory(
                package_root,
                art_archive_filter=frozenset((Path("Data/standard-art.cam"),)),
            )

            self.assertEqual(inventory.art_cams, (art,))

            def observe_standard_art(path):
                if Path(path).resolve() == art.resolve():
                    raise AssertionError("explicit archive reached art composer")
                return read_cam(path)

            with self.assertRaisesRegex(
                AssertionError, "explicit archive reached art composer"
            ), patch("majesty_cam.stock_art.read_cam", side_effect=observe_standard_art):
                merge_art_resources(game, (inventory,))

    def test_normal_merge_art_default_remains_all_declared_archives(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = root / "Data" / "first.cam"
            second = root / "Data" / "second.cam"
            selected = SelectedMod(
                "merge",
                SimpleNamespace(root=root),
            )

            self.assertEqual(
                _selected_art_archive_paths(selected, (first, second)),
                (first, second),
            )

    def test_art_filter_rejects_undeclared_or_external_paths(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            declared = root / "Data" / "declared.cam"
            unknown = SelectedMod(
                "standard",
                SimpleNamespace(root=root),
                semantic_passthrough=True,
                art_archive_filter=frozenset((Path("Data/other.cam"),)),
            )
            with self.assertRaisesRegex(ComposeError, "not a declared CAM"):
                _selected_art_archive_paths(unknown, (declared,))

            external = SelectedMod(
                "standard",
                SimpleNamespace(root=root),
                semantic_passthrough=True,
                art_archive_filter=frozenset((root.parent / "outside.cam",)),
            )
            with self.assertRaisesRegex(ComposeError, "escapes package root"):
                _selected_art_archive_paths(external, (declared,))

    def test_exact_report_files_exclude_sibling_component_content(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            chosen = root / "Data" / "chosen.cam"
            sibling = root / "Data" / "sibling.cam"
            chosen.parent.mkdir()
            chosen.write_bytes(b"chosen")
            sibling.write_bytes(b"sibling")
            selected = SelectedMod(
                "standard",
                SimpleNamespace(root=root),
                semantic_passthrough=True,
                report_files=(Path("Data/chosen.cam"), chosen),
            )

            files = _selected_report_files(selected)

            self.assertEqual(files, ((Path("Data/chosen.cam"), chosen.resolve()),))

    def test_exact_report_files_reject_content_outside_package(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            package_root = root / "package"
            package_root.mkdir()
            outside = root / "outside-component.cam"
            outside.write_bytes(b"outside")
            selected = SelectedMod(
                "standard",
                SimpleNamespace(root=package_root),
                semantic_passthrough=True,
                report_files=(outside,),
            )

            with self.assertRaisesRegex(ComposeError, "escapes package root"):
                _selected_report_files(selected)


class EffectiveArtDependencyTests(unittest.TestCase):
    def test_runtime_presenter_materializes_its_exact_stock_imag(self):
        stock_entry = CamEntry(
            name=pad_name(b"IX93ic enchant"),
            data=b"stock-enchantment-atlas",
        )
        stock = CamArchive(
            sections=(CamSection(b"IMAG", (stock_entry,)),)
        )

        result = _materialize_required_stock_imag_entries(
            (),
            stock,
            (b"IX93",),
            domain="interface",
        )

        self.assertEqual(result, (stock_entry,))

    def test_runtime_presenter_rejects_replaced_stock_imag(self):
        stock_entry = CamEntry(
            name=pad_name(b"IX93ic enchant"),
            data=b"stock-enchantment-atlas",
        )
        replacement = replace(stock_entry, data=b"replacement")
        stock = CamArchive(
            sections=(CamSection(b"IMAG", (stock_entry,)),)
        )

        with self.assertRaisesRegex(ComposeError, "IX93.*replaced"):
            _materialize_required_stock_imag_entries(
                (replacement,),
                stock,
                (b"IX93",),
                domain="interface",
            )

    def test_promoted_fallthrough_tile_replaces_empty_package_placeholder(self):
        archive = CamArchive(
            sections=(positional(b"TILE", (b"",)),)
        )
        promoted = CamEntry(name=pad_name(b"stock-effective"), data=b"stock-art")
        analysis = SimpleNamespace(
            tile_delta=SimpleNamespace(
                changes=(SimpleNamespace(index=0, entry=promoted),)
            )
        )

        entries = _effective_analysis_tile_entries(archive, analysis)

        self.assertEqual(entries, (promoted,))


class NamedComposeTests(unittest.TestCase):
    def test_named_union_preserves_order_accepts_identical_and_renames(self):
        resources = (
            resource("haunt", b"AP07", b"panel"),
            resource("alchemist", b"CGAL", b"lab", 1),
            resource("other", b"CGAL", b"lab", 2),
        )

        entries, selections = merge_named_resources(
            resources,
            b"SMNU",
            renames={("haunt", b"AP07"): b"CGPH"},
        )

        self.assertEqual([entry.name[:4] for entry in entries], [b"CGPH", b"CGAL"])
        self.assertEqual(selections[1].owners, ("alchemist", "other"))

    def test_named_union_rejects_cross_owner_divergence(self):
        with self.assertRaisesRegex(ComposeError, "conflicting SMNU"):
            merge_named_resources(
                (resource("a", b"SAME", b"one"), resource("b", b"SAME", b"two")),
                b"SMNU",
            )

    def test_named_union_applies_same_owner_native_last_write(self):
        entries, selections = merge_named_resources(
            (
                resource("a", b"SAME", b"older"),
                resource("a", b"SAME", b"newer", 1),
            ),
            b"SMNU",
        )

        self.assertEqual(tuple(entry.data for entry in entries), (b"newer",))
        self.assertEqual(selections[0].owners, ("a",))

    def test_named_union_omits_ancestry_only_stock_copy(self):
        entries, selections = merge_named_resources(
            (resource("copy", b"SAME", b"installed stock"),),
            b"SMNU",
            stock_resources={(b"SMNU", b"SAME"): b"installed stock"},
        )

        self.assertEqual(entries, ())
        self.assertEqual(selections, ())


class PositionalComposeTests(unittest.TestCase):
    def test_stock_lineage_slot_moves_even_without_another_mod_collision(self):
        stock = positional(b"TILE", [b"s0", b"s1", b"s2"])
        inherited = positional(b"TILE", [b"", b"base-1", b"base-2"])
        deltas = {
            "inherited": compute_stock_relative_delta(stock, inherited),
        }

        selected = _select_later_conflict_runs(
            deltas,
            (),
            {"inherited": 0},
            protected_indices={"inherited": (1,)},
        )

        self.assertEqual(selected["inherited"], {1, 2})

    def test_stock_lineage_protection_applies_only_to_its_owner(self):
        stock = positional(b"TILE", [b"s0", b"s1", b"s2"])
        deltas = {
            "inherited": compute_stock_relative_delta(
                stock, positional(b"TILE", [b"", b"base-1", b"base-2"])
            ),
            "unrelated": compute_stock_relative_delta(
                stock, positional(b"TILE", [b"", b"custom-1", b"custom-2"])
            ),
        }

        selected = _select_later_conflict_runs(
            deltas,
            (),
            {"inherited": 0, "unrelated": 1},
            protected_indices={"inherited": (1,)},
        )

        self.assertEqual(selected["inherited"], {1, 2})
        self.assertEqual(selected["unrelated"], set())

    def test_later_owner_moves_complete_contiguous_conflict_run(self):
        stock = positional(b"TILE", [b"s0", b"s1", b"s2", b"s3", b"s4"])
        alchemist = positional(
            b"TILE", [b"", b"", b"", b"", b"", b"a5", b"a6", b"a7"]
        )
        haunt = positional(
            b"TILE", [b"", b"", b"", b"", b"h4", b"h5", b"h6", b"h7", b"h8"]
        )
        deltas = {
            "alchemist": compute_stock_relative_delta(stock, alchemist),
            "haunt": compute_stock_relative_delta(stock, haunt),
        }
        collisions = find_positional_collisions(deltas)

        selected = _select_later_conflict_runs(
            deltas, collisions, {"alchemist": 0, "haunt": 1}
        )

        self.assertEqual(selected["alchemist"], set())
        self.assertEqual(selected["haunt"], {4, 5, 6, 7, 8})
        self.assertEqual(_first_free_after_reserved(deltas, selected), 8)

    def test_blank_stock_slots_do_not_redistribute_payloads(self):
        stock = positional(b"TILE", [b"proprietary-0", b"proprietary-1"])
        output = _blank_positional_section(stock, 3)
        self.assertEqual([entry.data for entry in output], [b"", b"", b""])
        self.assertEqual(output[0].name, stock.entries[0].name)
        self.assertEqual(output[2].name[:4], (2).to_bytes(4, "little"))

    def test_effective_stock_prefix_fills_only_unresolved_slots(self):
        stock = positional(b"SPLT", [b"stock-0", b"stock-1"])
        output = _blank_positional_section(stock, 3)
        output[1] = CamEntry(name=output[1].name, data=b"mod-1")

        _materialize_effective_stock_prefix(output, stock)

        self.assertEqual(
            [entry.data for entry in output],
            [b"stock-0", b"mod-1", b""],
        )


class ScopedGplResolutionTests(unittest.TestCase):
    def test_pair_resolution_allows_unrelated_third_mod_but_rejects_contributor(self):
        def parsed(owner, function_name, value):
            return parse_gpl(
                f"function {function_name}() is integer\n"
                f"begin\nreturn {value};\nend\n",
                f"{owner}.gpl",
            )

        inventories = tuple(
            SimpleNamespace(selected=SimpleNamespace(alias=owner))
            for owner in ("first", "second", "third")
        )
        sources = {
            "first": parsed("first", "Shared_Result", 1),
            "second": parsed("second", "Shared_Result", 2),
            "third": parsed("third", "Unrelated_Result", 9),
        }
        resolution_item = parsed("resolution", "Shared_Result", 3).items[0]
        scoped = ScopedSemanticResolution(
            item=resolution_item,
            participant_owners=frozenset(("first", "second")),
        )
        key = resolution_item.key

        with patch(
            "majesty_cam.compose._parse_inventory_gpl_sources",
            side_effect=lambda inventory: [sources[inventory.selected.alias]],
        ):
            result = merge_gpl_resources(
                inventories,
                semantic_resolutions={key: scoped},
            )

        self.assertIn("return 3", result.source_set.gpl_text)
        self.assertIn("Unrelated_Result", result.source_set.gpl_text)

        sources["third"] = parsed("third", "Shared_Result", 4)
        with patch(
            "majesty_cam.compose._parse_inventory_gpl_sources",
            side_effect=lambda inventory: [sources[inventory.selected.alias]],
        ), self.assertRaisesRegex(
            ComposeError,
            "additional mod owners.*third",
        ):
            merge_gpl_resources(
                inventories,
                semantic_resolutions={key: scoped},
            )

        sources["third"] = parsed("third", "Shared_Result", 1)
        with patch(
            "majesty_cam.compose._parse_inventory_gpl_sources",
            side_effect=lambda inventory: [sources[inventory.selected.alias]],
        ):
            duplicate_variant = merge_gpl_resources(
                inventories,
                semantic_resolutions={key: scoped},
            )

        self.assertIn("return 3", duplicate_variant.source_set.gpl_text)

        sources["third"] = parsed("third", "Shared_Result", 3)
        with patch(
            "majesty_cam.compose._parse_inventory_gpl_sources",
            side_effect=lambda inventory: [sources[inventory.selected.alias]],
        ):
            resolved_variant = merge_gpl_resources(
                inventories,
                semantic_resolutions={key: scoped},
            )

        self.assertIn("return 3", resolved_variant.source_set.gpl_text)


class PassthroughGplRewriteTests(unittest.TestCase):
    def test_private_aitx_relocation_emits_rewritten_standard_only_caller(self):
        merge_source = parse_gpl(
            "function Merge_Only() is integer\n"
            "begin\nreturn 1;\nend\n",
            "merge.gpl",
        )
        standard_source = parse_gpl(
            "function Standard_Only(agent ThisAgent) is\n"
            "begin\n"
            "    $SpecifyIntent(ThisAgent, 741);\n"
            "end\n",
            "standard.gpl",
        )
        inventories = (
            SimpleNamespace(
                selected=SimpleNamespace(
                    alias="merge",
                    semantic_passthrough=False,
                )
            ),
            SimpleNamespace(
                selected=SimpleNamespace(
                    alias="standard",
                    semantic_passthrough=True,
                )
            ),
        )
        sources = {
            "merge": merge_source,
            "standard": standard_source,
        }
        binding = PrivateActivityTextBinding(
            owner="standard",
            source_mod_id="{00000000-0000-0000-0000-000000000741}",
            source_index=741,
            expressions=(),
            expected_text="Standard private activity",
            runtime_id=0x60000741,
        )

        with patch(
            "majesty_cam.compose._parse_inventory_gpl_sources",
            side_effect=lambda inventory: [sources[inventory.selected.alias]],
        ):
            result = merge_gpl_resources(
                inventories,
                private_activity_texts=(binding,),
            )

        self.assertIn("Merge_Only", result.source_set.gpl_text)
        self.assertIn("Standard_Only", result.source_set.gpl_text)
        self.assertIn(binding.generated_expression, result.source_set.gpl_text)
        self.assertNotIn("$SpecifyIntent(ThisAgent, 741)", result.source_set.gpl_text)
        self.assertIn(
            f"$SpecifyIntent(ThisAgent, {binding.generated_expression})",
            result.source_set.gpl_text,
        )


class ProfileIdentityTests(unittest.TestCase):
    def test_failed_composition_staging_is_discarded(self):
        with TemporaryDirectory() as tmp:
            staging = Path(tmp) / ".manager-merged-abandoned"
            staging.mkdir()
            (staging / "partial.cam").write_bytes(b"partial")

            self.assertIsNone(_discard_incomplete_staging(staging))
            self.assertFalse(staging.exists())

    def test_private_text_runtime_capability_is_derived_not_caller_asserted(self):
        other = "freestyle-cam-rebind.v1"
        without_records, without_payload = _derive_runtime_capabilities(
            (other, PRIVATE_ACTIVITY_TEXT_RUNTIME_CAPABILITY),
            has_private_activity_text=False,
            runtime_feature_registry=RuntimeFeatureRegistry(),
        )
        with_records, with_payload = _derive_runtime_capabilities(
            (other,),
            has_private_activity_text=True,
            runtime_feature_registry=RuntimeFeatureRegistry(),
        )

        self.assertEqual(without_records, (other,))
        self.assertEqual(
            decode_runtime_capability_manifest(without_payload),
            without_records,
        )
        self.assertEqual(
            with_records,
            (other, PRIVATE_ACTIVITY_TEXT_RUNTIME_CAPABILITY),
        )
        self.assertEqual(
            decode_runtime_capability_manifest(with_payload),
            with_records,
        )

    def test_generated_definition_round_trips_exact_runtime_capabilities(self):
        source_definition = ModDefinition(
            schema_version=2,
            mod_id="{00000000-0000-0000-0000-000000000001}",
            internal_name="Fixture",
            display_name="Fixture",
            custom_buildings=(
                CustomBuildingDefinition(
                    local_name="FixtureGuild",
                    dialog_id="CGFX",
                    controller_base="CGGuild",
                    panel_resource_template="CGFX",
                ),
            ),
            runtime_capabilities=(),
        )
        selected = (
            SelectedMod(
                "fixture",
                SimpleNamespace(definition=source_definition),
            ),
        )
        for capabilities in (
            (),
            (
                "expanded-building-slots.cg-prefix",
                "freestyle-cam-rebind.v1",
            ),
        ):
            with self.subTest(capabilities=capabilities):
                payload = _generated_definition(
                    source_definition.mod_id,
                    "GeneratedFixture",
                    "Generated Fixture",
                    selected,
                    capabilities,
                )

                self.assertEqual(payload["schema_version"], 2)
                self.assertEqual(
                    tuple(payload["runtime_capabilities"]), capabilities
                )

    def test_generated_ids_are_distinct_stable_and_ordered(self):
        first = SelectedMod("first", SimpleNamespace(mod_id="{00000000-0000-0000-0000-000000000001}"))
        second = SelectedMod("second", SimpleNamespace(mod_id="{00000000-0000-0000-0000-000000000002}"))
        single = _generated_mod_id((first,), "first-only")
        self.assertNotEqual(
            single, "{00000000-0000-0000-0000-000000000001}"
        )
        self.assertEqual(single, _generated_mod_id((first,), "first-only"))
        self.assertNotEqual(single, _generated_mod_id((first,), "alternate"))
        combined = _generated_mod_id((first, second), "combined")
        self.assertEqual(combined, _generated_mod_id((first, second), "combined"))
        self.assertNotEqual(
            combined, _generated_mod_id((second, first), "combined")
        )

    def test_compose_rejects_equivalent_uuid_spellings(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            definition = ModDefinition(
                schema_version=3,
                mod_id="{00000000-0000-0000-0000-000000000001}",
                internal_name="One",
                display_name="One",
                custom_buildings=(),
                runtime_features=(),
            )
            selected = (
                SelectedMod(
                    "braced",
                    SimpleNamespace(
                        mod_id=definition.mod_id,
                        definition=definition,
                    ),
                ),
                SelectedMod(
                    "compact",
                    SimpleNamespace(
                        mod_id="00000000000000000000000000000001",
                        definition=definition,
                    ),
                ),
            )
            with self.assertRaisesRegex(ComposeError, "Mod IDs must be unique"):
                compose_package(
                    root,
                    root / "output",
                    selected,
                    profile_slug="duplicate-uuid",
                )

    def test_manifest_preserves_native_load_order(self):
        source_set = GplProjectSourceSet(
            project_text='data="Merged.dat"\nsource="Merged.gpl"\n',
            gpl_filename="Merged.gpl",
            gpl_text="Function X()\nBegin\nEnd\n",
            dat_filename="Merged.dat",
            dat_text="[X]\n[end]\n",
        )
        payload = _build_manifest(
            mod_id="{00000000-0000-0000-0000-000000000001}",
            internal_name="Fixture",
            display_name="Fixture",
            cam_filenames=("one.cam", "two.cam"),
            description_filename="merged.xml",
            source_set=source_set,
        )
        load = ET.fromstring(payload).find("./Mod/DataConfiguration/Dataset/Load")
        self.assertIsNotNone(load)
        self.assertEqual(
            [child.tag for child in load],
            ["CAM", "CAM", "Descriptions", "GPL"],
        )
        self.assertEqual(
            [child.tag for child in load.find("GPL")],
            ["Target", "Source", "Source"],
        )


class GeneratedCamOutputValidationTests(unittest.TestCase):
    def test_accepts_any_number_of_well_formed_art_family_outputs(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            cams = _generated_cam_paths(
                root,
                (
                    ("merged_maindata.cam", (b"IMAG", b"TILE", b"SPLT")),
                    ("merged_interfacedata.cam", (b"IMAG", b"TILE", b"PALT")),
                    ("merged_art-03.cam", (b"IMAG", b"TILE")),
                ),
            )

            summaries, palette_references = _validate_generated_cam_outputs(cams)

            self.assertEqual(len(summaries), 8)
            self.assertEqual(palette_references, 0)

    def test_rejects_missing_fixed_cam_role(self):
        with TemporaryDirectory() as tmp:
            cams = tuple(
                path
                for path in _generated_cam_paths(Path(tmp))
                if not path.relative_path.endswith("merged_audio.cam")
            )

            with self.assertRaisesRegex(
                ComposeError,
                "missing required CAM role.*merged_audio.cam",
            ):
                _validate_generated_cam_outputs(cams)

    def test_rejects_unrecognized_or_malformed_art_output(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.subTest("filename"):
                cams = _generated_cam_paths(
                    root,
                    (("merged_bonus.cam", (b"IMAG", b"TILE")),),
                )
                with self.assertRaisesRegex(
                    ComposeError,
                    "unsupported generated art CAM filename",
                ):
                    _validate_generated_cam_outputs(cams)

            with self.subTest("sections"):
                cams = _generated_cam_paths(
                    root,
                    (("merged_art-03.cam", (b"IMAG", b"STRT")),),
                )
                with self.assertRaisesRegex(
                    ComposeError,
                    "must begin with exactly IMAG and TILE",
                ):
                    _validate_generated_cam_outputs(cams)

    def test_rejects_duplicate_cam_paths_and_sections(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            cams = _generated_cam_paths(root)
            with self.assertRaisesRegex(ComposeError, "duplicate CAM path"):
                _validate_generated_cam_outputs((*cams, cams[0]))

            cams = _generated_cam_paths(
                root,
                (("merged_art-03.cam", (b"IMAG", b"TILE", b"TILE")),),
            )
            with self.assertRaisesRegex(ComposeError, "duplicate section.*TILE"):
                _validate_generated_cam_outputs(cams)


class DeclarativeDialogTests(unittest.TestCase):
    def test_v3_dialog_allocation_honors_external_scoped_standard_reservation(self):
        with TemporaryDirectory() as tmp:
            merge = _v3_dialog_inventory(
                Path(tmp),
                alias="merge",
                mod_id="{00000000-0000-0000-0000-000000000001}",
                local_name="MergeGuild",
                source=b"AP10",
            )

            resolved = resolve_building_dialogs(
                (merge,),
                reserved_dialog_ids=(b"CG00",),
            )

            self.assertEqual(resolved[0].resolved_dialog_id, b"CG01")

    def test_v3_dialog_allocation_reserves_native_standard_panel_ids(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            merge = _v3_dialog_inventory(
                root,
                alias="merge",
                mod_id="{00000000-0000-0000-0000-000000000001}",
                local_name="MergeGuild",
                source=b"AP10",
            )
            standard_definition = ModDefinition(
                schema_version=3,
                mod_id="{00000000-0000-0000-0000-000000000002}",
                internal_name="LegacyStandard",
                display_name="Legacy Standard",
                custom_buildings=(),
                runtime_capabilities=(),
            )
            standard_selected = SelectedMod(
                "standard",
                SimpleNamespace(
                    definition=standard_definition,
                    mod_id=standard_definition.mod_id,
                ),
                semantic_passthrough=True,
                cam_resource_filter=frozenset(),
                reserved_dialog_ids=frozenset((b"CG00",)),
            )
            standard = SimpleNamespace(
                selected=standard_selected,
                resources=(),
                descriptions=(),
            )

            resolved = resolve_building_dialogs((merge, standard))

            self.assertEqual(resolved[0].source_dialog_id, b"AP10")
            self.assertEqual(resolved[0].resolved_dialog_id, b"CG01")
            self.assertEqual(standard.resources, ())

    def test_v2_explicit_dialog_id_and_controller_fallback_are_preserved(self):
        definition = ModDefinition(
            schema_version=2,
            mod_id="{00000000-0000-0000-0000-000000000001}",
            internal_name="LegacyFixture",
            display_name="Legacy Fixture",
            custom_buildings=(
                CustomBuildingDefinition(
                    local_name="LegacyGuild",
                    dialog_id="CGFX",
                    controller_base="AP10",
                    panel_resource_template="AP10",
                ),
            ),
            runtime_capabilities=(),
        )
        inventory = SimpleNamespace(
            selected=SelectedMod(
                "legacy",
                SimpleNamespace(definition=definition, mod_id=definition.mod_id),
            ),
            descriptions=(),
            resources=(resource("legacy", b"AP10", b"legacy-panel"),),
            cams=(),
        )

        resolved = resolve_building_dialogs((inventory,))

        self.assertEqual(resolved[0].source_dialog_id, b"AP10")
        self.assertEqual(resolved[0].resolved_dialog_id, b"CGFX")

    def test_v2_fixed_dialog_cannot_overwrite_native_standard_reservation(self):
        definition = ModDefinition(
            schema_version=2,
            mod_id="{00000000-0000-0000-0000-000000000001}",
            internal_name="LegacyFixture",
            display_name="Legacy Fixture",
            custom_buildings=(
                CustomBuildingDefinition(
                    local_name="LegacyGuild",
                    dialog_id="CG00",
                    controller_base="AP10",
                    panel_resource_template="AP10",
                ),
            ),
            runtime_capabilities=(),
        )
        legacy = SimpleNamespace(
            selected=SelectedMod(
                "legacy",
                SimpleNamespace(definition=definition, mod_id=definition.mod_id),
            ),
            descriptions=(),
            resources=(resource("legacy", b"AP10", b"legacy-panel"),),
            cams=(),
        )
        standard_definition = replace(definition, custom_buildings=())
        standard = SimpleNamespace(
            selected=SelectedMod(
                "standard",
                SimpleNamespace(
                    definition=standard_definition,
                    mod_id="{00000000-0000-0000-0000-000000000002}",
                ),
                semantic_passthrough=True,
                cam_resource_filter=frozenset(),
                reserved_dialog_ids=frozenset((b"CG00",)),
            ),
            descriptions=(),
            resources=(),
            cams=(),
        )

        with self.assertRaisesRegex(ComposeError, "fixed dialog ID CG00"):
            resolve_building_dialogs((legacy, standard))

    def test_v3_dialog_allocation_is_stable_rewrites_panel_and_description(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = _v3_dialog_inventory(
                root,
                alias="zeta",
                mod_id="{00000000-0000-0000-0000-000000000002}",
                local_name="ZetaGuild",
                source=b"ZP10",
            )
            second = _v3_dialog_inventory(
                root,
                alias="alpha",
                mod_id="{00000000-0000-0000-0000-000000000001}",
                local_name="AlphaGuild",
                source=b"AP10",
            )

            forward = resolve_building_dialogs((first, second))
            reverse = resolve_building_dialogs((second, first))
            forward_map = {
                (item.owner, item.local_name): item.resolved_dialog_id
                for item in forward
            }
            reverse_map = {
                (item.owner, item.local_name): item.resolved_dialog_id
                for item in reverse
            }
            self.assertEqual(forward_map, reverse_map)
            self.assertEqual(forward_map[("alpha", "AlphaGuild")], b"CG00")
            self.assertEqual(forward_map[("zeta", "ZetaGuild")], b"CG01")

            text = merge_text_resources(
                root,
                (first, second),
                dialog_resolutions=forward,
            )
            smnu = text.text_archive.sections[0]
            strt = text.text_archive.sections[1]
            self.assertEqual(
                {entry.name[:4] for entry in smnu.entries}, {b"CG00", b"CG01"}
            )
            self.assertEqual(
                {entry.name[:4] for entry in strt.entries}, {b"CG00", b"CG01"}
            )

            descriptions = merge_description_resources(
                (first, second), dialog_resolutions=forward
            )
            rewritten = {
                record.to_element().get("Name"): record.to_element()
                .find("./Game/DialogID")
                .get("value")
                for record in descriptions.document.records
            }
            self.assertEqual(rewritten["AlphaGuild"], "CG00")
            self.assertEqual(rewritten["ZetaGuild"], "CG01")

            selected = (first.selected, second.selected)
            generated = _generated_definition(
                "{00000000-0000-0000-0000-000000000099}",
                "Generated",
                "Generated",
                selected,
                (),
                forward,
            )
            self.assertEqual(generated["schema_version"], 2)
            self.assertEqual(
                {item["dialog_id"] for item in generated["custom_buildings"]},
                {"CG00", "CG01"},
            )

    def test_generated_definition_owner_qualifies_reused_local_names(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = _v3_dialog_inventory(
                root,
                alias="first",
                mod_id="{00000000-0000-0000-0000-000000000001}",
                local_name="SharedBuilding",
                source=b"B001",
            )
            second = _v3_dialog_inventory(
                root,
                alias="second",
                mod_id="{00000000-0000-0000-0000-000000000002}",
                local_name="SharedBuilding",
                source=b"B002",
            )
            resolutions = resolve_building_dialogs((first, second))
            generated = _generated_definition(
                "{00000000-0000-0000-0000-000000000099}",
                "Generated",
                "Generated",
                (first.selected, second.selected),
                (),
                resolutions,
            )
            names = [
                item["local_name"] for item in generated["custom_buildings"]
            ]
            self.assertEqual(len(set(names)), 2)
            self.assertTrue(all(name.startswith("m000000000000") for name in names))

            reversed_generated = _generated_definition(
                "{00000000-0000-0000-0000-000000000099}",
                "Generated",
                "Generated",
                (second.selected, first.selected),
                (),
                resolutions,
            )
            self.assertEqual(
                {
                    item["dialog_id"]: item["local_name"]
                    for item in generated["custom_buildings"]
                },
                {
                    item["dialog_id"]: item["local_name"]
                    for item in reversed_generated["custom_buildings"]
                },
            )

    def test_v3_allocation_skips_legacy_and_existing_cg_resources(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            modern = _v3_dialog_inventory(
                root,
                alias="modern",
                mod_id="{00000000-0000-0000-0000-000000000001}",
                local_name="ModernGuild",
                source=b"AP10",
            )
            modern.resources += (
                resource("modern", b"CG01", b"unrelated-manager-safe-resource"),
            )
            legacy_definition = ModDefinition(
                schema_version=2,
                mod_id="{00000000-0000-0000-0000-000000000002}",
                internal_name="Legacy",
                display_name="Legacy",
                custom_buildings=(
                    CustomBuildingDefinition(
                        local_name="LegacyGuild",
                        dialog_id="CG00",
                        controller_base="LP10",
                        panel_resource_template="LP10",
                    ),
                ),
                runtime_capabilities=(),
            )
            legacy = SimpleNamespace(
                selected=SelectedMod(
                    "legacy",
                    SimpleNamespace(
                        definition=legacy_definition,
                        mod_id=legacy_definition.mod_id,
                    ),
                ),
                descriptions=(),
                resources=(resource("legacy", b"CG00", b"legacy"),),
                cams=(),
            )

            resolved = resolve_building_dialogs((modern, legacy))
            modern_result = next(item for item in resolved if item.owner == "modern")
            self.assertEqual(modern_result.resolved_dialog_id, b"CG02")

    def test_v3_rejects_two_buildings_sharing_one_inferred_panel(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            inventory = _v3_dialog_inventory(
                root,
                alias="ambiguous",
                mod_id="{00000000-0000-0000-0000-000000000001}",
                local_name="FirstGuild",
                source=b"AP10",
            )
            second_description = root / "ambiguous-second.xml"
            second_description.write_text(
                "<Majesty><Description type=\"Building\" ID=\"second\" "
                "subType=\"Building\" Name=\"SecondGuild\"><Game><DialogID "
                "value=\"AP10\" /></Game></Description></Majesty>",
                encoding="utf-8",
            )
            original = inventory.selected.package.definition
            inventory.selected.package.definition = ModDefinition(
                schema_version=3,
                mod_id=original.mod_id,
                internal_name=original.internal_name,
                display_name=original.display_name,
                custom_buildings=(
                    *original.custom_buildings,
                    CustomBuildingDefinition(
                        local_name="SecondGuild",
                        dialog_id=None,
                        controller_base="AP10",
                        panel_resource_template="AP10",
                    ),
                ),
                runtime_features=(),
            )
            inventory.descriptions += (second_description,)

            with self.assertRaisesRegex(ComposeError, "share source DialogID AP10"):
                resolve_building_dialogs((inventory,))

    def test_nonbuilding_packages_emit_noop_data_and_art_overlays(self):
        with TemporaryDirectory() as tmp:
            game = Path(tmp)
            (game / "Data").mkdir()
            (game / "DataMX").mkdir()
            bdep = CamEntry(name=pad_name(b"BDEP"), data=b"PALACE : GUILD\r\n")
            (game / "Data" / "miscdata.cam").write_bytes(
                CamArchive(
                    sections=(CamSection(extension=b"DATA", entries=(bdep,)),)
                ).to_bytes()
            )
            (game / "DataMX" / "mx_miscdata.cam").write_bytes(
                CamArchive(
                    sections=(CamSection(extension=b"DATA", entries=(bdep,)),)
                ).to_bytes()
            )
            main = CamArchive(
                sections=(
                    positional(b"IMAG", []),
                    positional(b"TILE", [b"tile"]),
                    positional(b"SPLT", [b"palette"]),
                )
            )
            interface = CamArchive(
                sections=(
                    CamSection(b"IMAG", (CamEntry(pad_name(b"CUR1"), b"cursor"),)),
                    positional(b"TILE", [b"tile"]),
                ),
            )
            (game / "Data" / "maindata.cam").write_bytes(main.to_bytes())
            (game / "Data" / "interfacedata.cam").write_bytes(interface.to_bytes())
            (game / "Data" / "MajestyDatasetDefinitions.xml").write_text(
                "<Majesty><DataConfiguration><Dataset><Load>"
                "<CAM>interfacedata.cam</CAM><CAM>maindata.cam</CAM>"
                "</Load></Dataset></DataConfiguration></Majesty>",
                encoding="utf-8",
            )
            (game / "DataMX" / "MajestyExpansionDatasetDefinitions.xml").write_text(
                "<Majesty><DataConfiguration><Dataset><Load />"
                "</Dataset></DataConfiguration></Majesty>",
                encoding="utf-8",
            )
            inventory = SimpleNamespace(
                selected=SimpleNamespace(
                    alias="data-only",
                    package=SimpleNamespace(
                        definition=ModDefinition(
                            schema_version=3,
                            mod_id="{00000000-0000-0000-0000-000000000003}",
                            internal_name="DataOnly",
                            display_name="Data Only",
                            custom_buildings=(),
                            runtime_features=(),
                        )
                    ),
                ),
                resources=(),
                cams=(),
                descriptions=(),
            )

            bdep_result = merge_bdep_resource(game, (inventory,))
            main_result, interface_result = merge_art_resources(game, (inventory,))
            descriptions = merge_description_resources((inventory,))

            self.assertEqual(bdep_result.deltas, ())
            self.assertEqual(bdep_result.archive.sections[0].extension, b"DATA")
            self.assertEqual(bdep_result.archive.sections[0].entries, ())
            self.assertEqual(
                read_cam(bdep_result.archive.to_bytes()).to_bytes(),
                bdep_result.archive.to_bytes(),
            )
            self.assertTrue(
                all(not section.entries for section in main_result.archive.sections)
            )
            self.assertTrue(
                all(
                    not section.entries
                    for section in interface_result.archive.sections
                )
            )
            self.assertEqual(main_result.report.tile_allocation.stock_count, 1)
            self.assertEqual(main_result.report.tile_allocation.final_count, 1)
            self.assertEqual(
                main_result.report.palette_allocation.stock_count, 1
            )
            self.assertEqual(
                interface_result.report.tile_allocation.stock_count, 1
            )
            self.assertEqual(
                interface_result.report.tile_allocation.final_count, 1
            )
            self.assertNotEqual(main_result.archive.to_bytes(), main.to_bytes())
            self.assertNotEqual(
                interface_result.archive.to_bytes(), interface.to_bytes()
            )
            for result in (main_result, interface_result):
                payload = result.archive.to_bytes()
                self.assertEqual(read_cam(payload).to_bytes(), payload)
            self.assertEqual(descriptions.document.records, ())

    def test_controlled_follower_markers_are_registered_as_stock_shaped_overlays(self):
        inventory = SimpleNamespace(
            selected=SimpleNamespace(
                alias="follower-owner",
                package=SimpleNamespace(
                    definition=ModDefinition(
                        schema_version=3,
                        mod_id="{00000000-0000-0000-0000-000000000003}",
                        internal_name="FollowerOwner",
                        display_name="Follower Owner",
                        custom_buildings=(),
                        runtime_features=(),
                    )
                ),
            ),
            resources=(),
            cams=(),
            descriptions=(),
        )
        markers = ("MCF0123456789AB1", "MCF0123456789AB2")

        result = merge_description_resources(
            (inventory,),
            controlled_follower_markers=markers,
            reserved_description_keys=(("Unit", "MF00"),),
        )

        overlays = {
            record.to_element().get("Name"): record.to_element()
            for record in result.document.records
        }
        self.assertEqual(set(overlays), set(markers))
        self.assertEqual(
            {element.get("ID") for element in overlays.values()},
            {"MF01", "MF02"},
        )
        for marker in markers:
            element = overlays[marker]
            self.assertEqual(element.get("subType"), "Overlay")
            self.assertEqual(
                [item.get("value") for item in element.findall("./Engine/Info")],
                ["Directionless", "DontBlock", "NotVisibleInISOView"],
            )
            self.assertEqual(
                element.find("./Engine/ImageIDBase").get("value"), "CRB2"
            )
            self.assertEqual(
                element.find("./Game/StackPriority").get("value"), "0"
            )
            self.assertIsNone(element.find("./Engine/Script"))

    def test_bdep_merge_uses_proven_original_ancestry_without_reverting_mx(self):
        with TemporaryDirectory() as tmp:
            game = Path(tmp)
            (game / "Data").mkdir()
            (game / "DataMX").mkdir()
            original = CamEntry(
                name=pad_name(b"BDEP"),
                data=b"PAL1\r\nMARKET : PAL1\r\n",
            )
            expansion = CamEntry(
                name=pad_name(b"BDEP"),
                data=(
                    b"PAL1\r\n"
                    b"MARKET : PAL1 OUTPOST ||\r\n"
                    b"OUTPOST : PAL1\r\n"
                ),
            )
            for path, entry in (
                (game / "Data" / "miscdata.cam", original),
                (game / "DataMX" / "mx_miscdata.cam", expansion),
            ):
                path.write_bytes(
                    CamArchive(
                        sections=(CamSection(extension=b"DATA", entries=(entry,)),)
                    ).to_bytes()
                )
            zoo_payload = original.data + b"ZOO1\r\nZOO2\r\nZOO3\r\n"
            definition = ModDefinition(
                schema_version=3,
                mod_id="{00000000-0000-0000-0000-000000000004}",
                internal_name="Zoo",
                display_name="Zoo",
                custom_buildings=(),
                runtime_features=(),
            )
            inventory = SimpleNamespace(
                selected=SimpleNamespace(
                    alias="zoo",
                    package=SimpleNamespace(definition=definition),
                ),
                resources=(
                    CamResource(
                        owner="zoo",
                        source=Path("zoo.cam"),
                        cam_order=0,
                        section_order=0,
                        entry_order=0,
                        section=b"DATA",
                        entry=CamEntry(name=pad_name(b"BDEP"), data=zoo_payload),
                    ),
                ),
            )

            result = merge_bdep_resource(game, (inventory,))
            payload = result.archive.sections[0].entries[0].data

            self.assertIn(b"MARKET : PAL1 OUTPOST ||\r\n", payload)
            self.assertIn(b"OUTPOST : PAL1\r\n", payload)
            self.assertEqual(
                tuple(row.building_id for row in result.deltas[0].rows),
                ("ZOO1", "ZOO2", "ZOO3"),
            )


class ControllerComposeTests(unittest.TestCase):
    def test_v3_building_requires_both_owned_panel_sections(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            for missing_section in (b"SMNU", b"STRT"):
                with self.subTest(missing_section=missing_section):
                    inventory = _v3_dialog_inventory(
                        root,
                        alias="fixture",
                        mod_id="{00000000-0000-0000-0000-000000000001}",
                        local_name="FixtureGuild",
                        source=b"B001",
                    )
                    inventory.resources = tuple(
                        item
                        for item in inventory.resources
                        if item.section != missing_section
                    )
                    with self.assertRaisesRegex(
                        ComposeError, missing_section.decode("ascii")
                    ):
                        resolve_building_dialogs((inventory,))

    def test_package_local_keys_are_owner_qualified_and_deterministic(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = _v3_controller_inventory(
                root,
                alias="alpha",
                mod_id="{00000000-0000-0000-0000-000000000001}",
                local_name="AlphaGuild",
                building_source=b"B001",
                family="A1",
            )
            second = _v3_controller_inventory(
                root,
                alias="beta",
                mod_id="{00000000-0000-0000-0000-000000000002}",
                local_name="BetaGuild",
                building_source=b"B002",
                family="B1",
            )

            forward = resolve_controller_registry((first, second))
            reverse = resolve_controller_registry((second, first))

            self.assertEqual(
                encode_stock_controller_registry(forward.registry),
                encode_stock_controller_registry(reverse.registry),
            )
            qualified = {
                item.qualified_key
                for item in forward.key_mappings
                if item.kind == "panel" and item.raw_key == "shared-panel"
            }
            self.assertEqual(len(qualified), 2)
            self.assertTrue(
                all(value.startswith("m000000000000") for value in qualified)
            )
            self.assertEqual(
                {item.raw_panel_key for item in forward.panels},
                {"shared-panel"},
            )
            self.assertEqual(
                len({item.resolved_child_dialog_id for item in forward.panels}),
                2,
            )

    def test_controller_child_allocation_reserves_native_standard_panel_ids(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            inventory = _v3_controller_inventory(
                root,
                alias="fixture",
                mod_id="{00000000-0000-0000-0000-000000000001}",
                local_name="FixtureGuild",
                building_source=b"B001",
                family="FX",
            )
            inventory.selected = replace(
                inventory.selected,
                reserved_dialog_ids=frozenset((b"CG01",)),
            )

            result = resolve_controller_registry((inventory,))

            self.assertEqual(result.panels[0].resolved_parent_dialog_id, b"CG00")
            self.assertEqual(result.panels[0].resolved_child_dialog_id, b"CG02")

    def test_controller_child_allocation_honors_external_scoped_reservation(self):
        with TemporaryDirectory() as tmp:
            inventory = _v3_controller_inventory(
                Path(tmp),
                alias="fixture",
                mod_id="{00000000-0000-0000-0000-000000000001}",
                local_name="FixtureGuild",
                building_source=b"B001",
                family="FX",
            )
            dialogs = resolve_building_dialogs(
                (inventory,),
                reserved_dialog_ids=(b"CG01",),
            )

            result = resolve_controller_registry(
                (inventory,),
                building_dialogs=dialogs,
                reserved_dialog_ids=(b"CG01",),
            )

            self.assertEqual(result.panels[0].resolved_parent_dialog_id, b"CG00")
            self.assertEqual(result.panels[0].resolved_child_dialog_id, b"CG02")

    def test_global_runtime_identifiers_still_conflict(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = _v3_controller_inventory(
                root,
                alias="alpha",
                mod_id="{00000000-0000-0000-0000-000000000001}",
                local_name="AlphaGuild",
                building_source=b"B001",
                family="DUP",
            )
            second = _v3_controller_inventory(
                root,
                alias="beta",
                mod_id="{00000000-0000-0000-0000-000000000002}",
                local_name="BetaGuild",
                building_source=b"B002",
                family="DUP",
            )
            with self.assertRaisesRegex(ComposeError, "building family"):
                resolve_controller_registry((first, second))

    def test_v3_allows_unrelated_panel_pair_but_rejects_wrong_parent_lifecycle(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            inventory = _v3_controller_inventory(
                root,
                alias="fixture",
                mod_id="{00000000-0000-0000-0000-000000000001}",
                local_name="FixtureGuild",
                building_source=b"B001",
                family="FX",
            )
            inventory.resources += _panel_pair("fixture", b"XTRA")
            self.assertEqual(
                len(resolve_controller_registry((inventory,)).registry.panels),
                1,
            )

            definition = inventory.selected.package.definition
            inventory.resources = tuple(
                item for item in inventory.resources if item.key != b"XTRA"
            )
            inventory.selected.package.definition = ModDefinition(
                schema_version=3,
                mod_id=definition.mod_id,
                internal_name=definition.internal_name,
                display_name=definition.display_name,
                custom_buildings=(
                    CustomBuildingDefinition(
                        local_name="FixtureGuild",
                        dialog_id=None,
                        controller_base="AP07",
                        panel_resource_template="AP10",
                    ),
                ),
                runtime_features=definition.runtime_features,
            )
            with self.assertRaisesRegex(ComposeError, "requires parent building"):
                resolve_controller_registry((inventory,))

    def test_controller_family_cannot_override_a_stock_description(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_stock_description_dirs(root)
            inventory = _v3_controller_inventory(
                root,
                alias="fixture",
                mod_id="{00000000-0000-0000-0000-000000000001}",
                local_name="FixtureGuild",
                building_source=b"B001",
                family="FX",
            )
            result = resolve_controller_registry((inventory,))
            with self.assertRaisesRegex(ComposeError, "cannot override stock"):
                validate_controller_stock_evidence(
                    root,
                    (inventory,),
                    result.registry,
                    controller_panels=result.panels,
                    description_stock_deltas=(
                        DescriptionStockDelta(
                            owner="fixture",
                            key=("Building", "FX1"),
                            kind="stock_override",
                            mod_source="fixture-controller.xml",
                            stock_source="stock.xml",
                        ),
                    ),
                )

    def test_controller_controls_must_exist_in_their_authored_panels(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_stock_description_dirs(root)
            inventory = _v3_controller_inventory(
                root,
                alias="fixture",
                mod_id="{00000000-0000-0000-0000-000000000001}",
                local_name="FixtureGuild",
                building_source=b"B001",
                family="FX",
            )
            _add_resource_meter(inventory, "FXV1", 0x6000)
            inventory.resources = tuple(
                replace(
                    item,
                    entry=replace(
                        item.entry,
                        data=_smnu_payload(0x6001, 0x6002),
                    ),
                )
                if item.section == b"SMNU" and item.key == b"P001"
                else item
                for item in inventory.resources
            )
            result = resolve_controller_registry((inventory,))
            with self.assertRaisesRegex(
                ComposeError,
                "AP22 binding_control_id=0x00006003",
            ):
                validate_controller_stock_evidence(
                    root,
                    (inventory,),
                    result.registry,
                    controller_panels=result.panels,
                    description_stock_deltas=(
                        DescriptionStockDelta(
                            "fixture", ("Building", "FX1"), "addition",
                            "fixture-controller.xml", None,
                        ),
                    ),
                )

            inventory.resources = tuple(
                replace(
                    item,
                    entry=replace(
                        item.entry,
                        data=_smnu_payload(0x6001, 0x6002, 0x6003),
                    ),
                )
                if item.section == b"SMNU" and item.key == b"P001"
                else item
                for item in inventory.resources
            )
            validate_controller_stock_evidence(
                root,
                (inventory,),
                result.registry,
                controller_panels=result.panels,
                description_stock_deltas=(
                    DescriptionStockDelta(
                        "fixture", ("Building", "FX1"), "addition",
                        "fixture-controller.xml", None,
                    ),
                ),
            )

            inventory.resources = tuple(
                replace(
                    item,
                    entry=replace(item.entry, data=_smnu_payload()),
                )
                if item.section == b"SMNU" and item.key == b"B001"
                else item
                for item in inventory.resources
            )
            with self.assertRaisesRegex(
                ComposeError,
                "open_command_id=0x00004100",
            ):
                validate_controller_stock_evidence(
                    root,
                    (inventory,),
                    result.registry,
                    controller_panels=result.panels,
                    description_stock_deltas=(
                        DescriptionStockDelta(
                            "fixture", ("Building", "FX1"), "addition",
                            "fixture-controller.xml", None,
                        ),
                    ),
                )

    def test_controller_family_cannot_attach_to_another_mods_building(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_stock_description_dirs(root)
            owner = _v3_controller_inventory(
                root,
                alias="owner",
                mod_id="{00000000-0000-0000-0000-000000000001}",
                local_name="OwnerGuild",
                building_source=b"B001",
                family="FX",
            )
            other = _v3_dialog_inventory(
                root,
                alias="other",
                mod_id="{00000000-0000-0000-0000-000000000002}",
                local_name="OtherGuild",
                source=b"B002",
            )
            other.descriptions[0].write_text(
                '<Majesty><Description type="Building" ID="FX9" '
                'subType="Building" Name="OtherGuild"><Game><DialogID '
                'value="B002" /></Game></Description></Majesty>',
                encoding="utf-8",
            )
            result = resolve_controller_registry((owner, other))
            deltas = (
                DescriptionStockDelta(
                    "owner", ("Building", "FX1"), "addition",
                    "owner-controller.xml", None,
                ),
                DescriptionStockDelta(
                    "other", ("Building", "FX9"), "addition",
                    "other.xml", None,
                ),
            )
            with self.assertRaisesRegex(ComposeError, "owned by 'owner'"):
                validate_controller_stock_evidence(
                    root,
                    (owner, other),
                    result.registry,
                    controller_panels=result.panels,
                    description_stock_deltas=deltas,
                )

    def test_controller_family_cannot_match_an_untouched_stock_building(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_stock_description_dirs(root, ("FX0",))
            inventory = _v3_controller_inventory(
                root,
                alias="owner",
                mod_id="{00000000-0000-0000-0000-000000000001}",
                local_name="OwnerGuild",
                building_source=b"B001",
                family="FX",
            )
            result = resolve_controller_registry((inventory,))
            with self.assertRaisesRegex(ComposeError, "untouched stock"):
                validate_controller_stock_evidence(
                    root,
                    (inventory,),
                    result.registry,
                    controller_panels=result.panels,
                    description_stock_deltas=(
                        DescriptionStockDelta(
                            "owner", ("Building", "FX1"), "addition",
                            "owner-controller.xml", None,
                        ),
                    ),
                )

    def test_controller_family_is_exclusive_to_its_declared_parent(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            inventory = _v3_controller_inventory(
                root,
                alias="owner",
                mod_id="{00000000-0000-0000-0000-000000000001}",
                local_name="OwnerGuild",
                building_source=b"B001",
                family="AX",
            )
            inventory.descriptions[0].write_text(
                '<Majesty><Description type="Building" ID="AX1" '
                'subType="Building" Name="OwnerGuild"><Game><DialogID '
                'value="B001" /></Game></Description>'
                '<Description type="Building" ID="AX9" '
                'subType="Building" Name="OtherBuilding"><Game><DialogID '
                'value="B009" /></Game></Description></Majesty>',
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ComposeError, "owned exclusively"):
                resolve_controller_registry((inventory,))

    def test_callback_identity_is_case_insensitive_across_packages(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = _v3_controller_inventory(
                root,
                alias="first",
                mod_id="{00000000-0000-0000-0000-000000000001}",
                local_name="FirstGuild",
                building_source=b"B001",
                family="A1",
            )
            second = _v3_controller_inventory(
                root,
                alias="second",
                mod_id="{00000000-0000-0000-0000-000000000002}",
                local_name="SecondGuild",
                building_source=b"B002",
                family="B1",
            )
            _add_timed_callback(first, root, "ApplyThing", 0x6000, "A101")
            _add_timed_callback(second, root, "applything", 0x6100, "B101")
            with self.assertRaisesRegex(ComposeError, "GPL callback"):
                resolve_controller_registry((first, second))

    def test_ap22_attribute_id_cannot_alias_across_packages(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = _v3_controller_inventory(
                root,
                alias="first",
                mod_id="{00000000-0000-0000-0000-000000000001}",
                local_name="FirstGuild",
                building_source=b"B001",
                family="A1",
            )
            second = _v3_controller_inventory(
                root,
                alias="second",
                mod_id="{00000000-0000-0000-0000-000000000002}",
                local_name="SecondGuild",
                building_source=b"B002",
                family="B1",
            )
            _add_resource_meter(first, "PV01", 0x6000)
            _add_resource_meter(second, "PV01", 0x6100)
            with self.assertRaisesRegex(ComposeError, "duplicate AP22.*attribute_id"):
                resolve_controller_registry((first, second))

    def test_v3_stock_evidence_allows_lairs_and_stock_dialog_reuse(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_stock_description_dirs(root)
            empty_registry = resolve_stock_controller_registry((), {})
            cases = (
                (
                    "lair",
                    '<Description type="Building" ID="LR01" '
                    'subType="Building" Name="PrivateLair"><Game>'
                    '<DialogID value="0" /></Game></Description>',
                ),
                (
                    "stock-dialog",
                    '<Description type="Building" ID="SD01" '
                    'subType="Building" Name="StockPanelBuilding"><Game>'
                    '<DialogID value="AP10" /></Game></Description>',
                ),
            )
            for alias, record in cases:
                with self.subTest(alias=alias):
                    inventory = _v3_description_inventory(
                        root, alias, f"<Majesty>{record}</Majesty>"
                    )
                    record_id = "LR01" if alias == "lair" else "SD01"
                    validate_controller_stock_evidence(
                        root,
                        (inventory,),
                        empty_registry,
                        description_stock_deltas=(
                            DescriptionStockDelta(
                                alias,
                                ("Building", record_id),
                                "addition",
                                f"{alias}.xml",
                                None,
                            ),
                        ),
                    )

    def test_v3_private_building_panel_must_be_complete_and_declared(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_stock_description_dirs(root)
            empty_registry = resolve_stock_controller_registry((), {})
            xml = (
                '<Majesty><Description type="Building" ID="PV01" '
                'subType="Building" Name="PrivateBuilding"><Game>'
                '<DialogID value="B001" /></Game></Description></Majesty>'
            )
            undeclared = _v3_description_inventory(
                root,
                "undeclared",
                xml,
                resources=_panel_pair("undeclared", b"B001"),
            )
            delta = DescriptionStockDelta(
                "undeclared", ("Building", "PV01"), "addition",
                "undeclared.xml", None,
            )
            with self.assertRaisesRegex(ComposeError, "custom_building"):
                validate_controller_stock_evidence(
                    root,
                    (undeclared,),
                    empty_registry,
                    description_stock_deltas=(delta,),
                )

            missing = _v3_description_inventory(
                root,
                "missing-half",
                xml,
                resources=(resource("missing-half", b"B001", b"panel"),),
            )
            with self.assertRaisesRegex(ComposeError, "exactly one package-owned"):
                validate_controller_stock_evidence(
                    root,
                    (missing,),
                    empty_registry,
                    description_stock_deltas=(
                        DescriptionStockDelta(
                            "missing-half", ("Building", "PV01"), "addition",
                            "missing-half.xml", None,
                        ),
                    ),
                )

    def test_enchantment_row_must_be_a_package_addition(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_stock_description_dirs(root)
            inventory = _v3_description_inventory(
                root,
                "overlay",
                '<Majesty><Description type="Unit" ID="OV42" '
                'subType="Overlay" /></Majesty>',
            )
            features = normalize_runtime_features(
                (EnchantmentRowFeature("OV42", "Private effect"),)
            )
            with self.assertRaisesRegex(ComposeError, "cannot override a stock ID"):
                validate_controller_stock_evidence(
                    root,
                    (inventory,),
                    resolve_stock_controller_registry((), {}),
                    runtime_feature_registry=features,
                    description_stock_deltas=(
                        DescriptionStockDelta(
                            "overlay", ("Overlay", "OV42"), "stock_override",
                            "overlay.xml", "stock.xml",
                        ),
                    ),
                )


class GeneratedRuntimeEvidenceTests(unittest.TestCase):
    def test_controller_evidence_is_reproved_and_each_corruption_fails(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            inventory, registry, description, gpl = (
                _generated_controller_evidence_fixture(root)
            )
            _validate_generated_runtime_evidence(
                inventory, RuntimeFeatureRegistry(), registry
            )

            parent_corrupt = replace(
                registry,
                panels=(
                    replace(
                        registry.panels[0],
                        parent_dialog_id=int.from_bytes(b"BAD1", "little"),
                    ),
                ),
            )
            with self.assertRaisesRegex(ComposeError, "parent DialogID"):
                _validate_generated_runtime_evidence(
                    inventory, RuntimeFeatureRegistry(), parent_corrupt
                )

            missing_child = replace(
                inventory,
                resources=tuple(
                    item
                    for item in inventory.resources
                    if not (item.section == b"STRT" and item.key == b"CGBR")
                ),
            )
            with self.assertRaisesRegex(ComposeError, "STRT/CGBR"):
                _validate_generated_runtime_evidence(
                    missing_child, RuntimeFeatureRegistry(), registry
                )

            description.write_text(
                _generated_controller_description(family="ZZZ"),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ComposeError, "family 'ALB'"):
                _validate_generated_runtime_evidence(
                    inventory, RuntimeFeatureRegistry(), registry
                )
            description.write_text(
                _generated_controller_description(), encoding="utf-8"
            )

            gpl.write_text(
                "function Alchemist_DoInvigoratingElixer(agent ThisAgent)\n"
                "begin\nend\n",
                encoding="cp1252",
            )
            with self.assertRaisesRegex(ComposeError, "Arcane_Infusion"):
                _validate_generated_runtime_evidence(
                    inventory, RuntimeFeatureRegistry(), registry
                )
            gpl.write_text(_generated_controller_gpl(), encoding="cp1252")

            description.write_text(
                _generated_controller_description(include_unit=False),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ComposeError, "private unit 'ALS1'"):
                _validate_generated_runtime_evidence(
                    inventory, RuntimeFeatureRegistry(), registry
                )

            description.write_text(
                _generated_controller_description(name_generator="NM_1"),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ComposeError, "NM_1"):
                _validate_generated_runtime_evidence(
                    inventory, RuntimeFeatureRegistry(), registry
                )


def _v3_dialog_inventory(
    root: Path, *, alias: str, mod_id: str, local_name: str, source: bytes
):
    definition = ModDefinition(
        schema_version=3,
        mod_id=mod_id,
        internal_name=local_name,
        display_name=local_name,
        custom_buildings=(
            CustomBuildingDefinition(
                local_name=local_name,
                dialog_id=None,
                controller_base="AP10",
                panel_resource_template="AP10",
            ),
        ),
        runtime_features=(),
    )
    description = root / f"{alias}.xml"
    description.write_text(
        f"<Majesty><Description type=\"Building\" ID=\"{alias}\" "
        f"subType=\"Building\" Name=\"{local_name}\"><Game><DialogID "
        f"value=\"{source.decode('ascii')}\" /></Game></Description></Majesty>",
        encoding="utf-8",
    )
    selected = SelectedMod(
        alias,
        SimpleNamespace(definition=definition, mod_id=definition.mod_id),
    )
    return SimpleNamespace(
        selected=selected,
        descriptions=(description,),
        resources=(
            resource(alias, source, b"panel"),
            CamResource(
                owner=alias,
                source=Path(f"{alias}.cam"),
                cam_order=0,
                section_order=1,
                entry_order=0,
                section=b"STRT",
                entry=CamEntry(name=pad_name(source), data=b"labels"),
            ),
        ),
        cams=(),
    )


def _v3_description_inventory(
    root: Path,
    alias: str,
    xml: str,
    *,
    custom_buildings=(),
    resources=(),
):
    definition = ModDefinition(
        schema_version=3,
        mod_id=(
            "{00000000-0000-0000-0000-"
            + f"{len(alias):012d}"
            + "}"
        ),
        internal_name=alias,
        display_name=alias,
        custom_buildings=tuple(custom_buildings),
        runtime_features=(),
    )
    description = root / f"{alias}.xml"
    description.write_text(xml, encoding="utf-8")
    return SimpleNamespace(
        selected=SelectedMod(
            alias,
            SimpleNamespace(definition=definition, mod_id=definition.mod_id),
        ),
        descriptions=(description,),
        resources=tuple(resources),
        cams=(),
        gpl_loads=(),
    )


def _write_stock_description_dirs(
    root: Path, building_ids=()
) -> None:
    data = root / "SDK" / "OriginalQuests" / "Data"
    data_mx = root / "SDK" / "OriginalQuests" / "DataMX"
    data.mkdir(parents=True, exist_ok=True)
    data_mx.mkdir(parents=True, exist_ok=True)
    if building_ids:
        records = "".join(
            '<Description type="Building" '
            f'ID="{identifier}" subType="Building" '
            f'Name="Stock{identifier}" />'
            for identifier in building_ids
        )
        (data / "stock.xml").write_text(
            f"<Majesty>{records}</Majesty>", encoding="utf-8"
        )


def _smnu_payload(*control_ids: int) -> bytes:
    return struct.pack(f"<{len(control_ids) + 1}I", 0, *control_ids)


def _panel_pair(owner: str, key: bytes, control_ids=()):
    return (
        resource(owner, key, _smnu_payload(*control_ids)),
        CamResource(
            owner=owner,
            source=Path(f"{owner}.cam"),
            cam_order=0,
            section_order=1,
            entry_order=0,
            section=b"STRT",
            entry=CamEntry(name=pad_name(key), data=b"labels"),
        ),
    )


def _v3_controller_inventory(
    root: Path,
    *,
    alias: str,
    mod_id: str,
    local_name: str,
    building_source: bytes,
    family: str,
):
    panel = StockAp10Ap69SecondaryPanel(
        panel_key="shared-panel",
        parent_building=local_name,
        source_dialog_id="P001",
        building_family_id=family,
        open_command_id=0x4100,
    )
    definition = ModDefinition(
        schema_version=3,
        mod_id=mod_id,
        internal_name=local_name,
        display_name=local_name,
        custom_buildings=(
            CustomBuildingDefinition(
                local_name=local_name,
                dialog_id=None,
                controller_base="AP10",
                panel_resource_template="AP10",
            ),
        ),
        runtime_features=(panel,),
    )
    description = root / f"{alias}-controller.xml"
    description.write_text(
        f'<Majesty><Description type="Building" ID="{family}1" '
        f'subType="Building" Name="{local_name}"><Game><DialogID '
        f'value="{building_source.decode("ascii")}" /></Game></Description></Majesty>',
        encoding="utf-8",
    )
    return SimpleNamespace(
        selected=SelectedMod(
            alias,
            SimpleNamespace(definition=definition, mod_id=mod_id),
        ),
        descriptions=(description,),
        resources=(
            *_panel_pair(alias, building_source, (0x4100,)),
            *_panel_pair(alias, b"P001"),
        ),
        cams=(),
        gpl_loads=(),
    )


def _add_timed_callback(
    inventory,
    root: Path,
    callback: str,
    control_base: int,
    attribute_id: str,
) -> None:
    definition = inventory.selected.package.definition
    panel = definition.runtime_features[0]
    meter = StockAp22ResourceMeter(
        panel_key=panel.panel_key,
        resource_key="shared-resource",
        attribute_id=attribute_id,
        label_control_id=control_base + 1,
        count_control_id=control_base + 2,
        binding_control_id=control_base + 3,
    )
    action = StockAp24TimedRageAction(
        panel_key=panel.panel_key,
        action_key="shared-action",
        action_control_id=control_base + 10,
        descriptor_template_control_id=0x1140,
        level_price_template_control_id=0x113E,
        required_level=3,
        gold_cost=1500,
        resource_key=meter.resource_key,
        resource_cost=1,
        callback_symbol=callback,
        duration_ms=1000,
        icon_control_id=control_base + 11,
        price_control_id=control_base + 12,
        progress_control_id=control_base + 13,
        active_display_control_id=control_base + 14,
    )
    inventory.selected.package.definition = ModDefinition(
        schema_version=definition.schema_version,
        mod_id=definition.mod_id,
        internal_name=definition.internal_name,
        display_name=definition.display_name,
        custom_buildings=definition.custom_buildings,
        runtime_features=(panel, meter, action),
    )
    source = root / f"{inventory.selected.alias}-{callback}.gpl"
    source.write_text(
        f"function {callback}()\nbegin\nend\n",
        encoding="cp1252",
    )
    inventory.gpl_loads = (
        SimpleNamespace(
            sources=(SimpleNamespace(absolute_path=source),),
        ),
    )


def _add_resource_meter(
    inventory,
    attribute_id: str,
    control_base: int,
) -> None:
    definition = inventory.selected.package.definition
    panel = definition.runtime_features[0]
    meter = StockAp22ResourceMeter(
        panel_key=panel.panel_key,
        resource_key="shared-resource",
        attribute_id=attribute_id,
        label_control_id=control_base + 1,
        count_control_id=control_base + 2,
        binding_control_id=control_base + 3,
    )
    inventory.selected.package.definition = replace(
        definition,
        runtime_features=(panel, meter),
    )


def _generated_controller_description(
    *,
    family: str = "ALB",
    include_unit: bool = True,
    name_generator=None,
) -> str:
    unit = ""
    if include_unit:
        name = (
            f'<NameGenType value="{name_generator}" />'
            if name_generator is not None
            else ""
        )
        unit = (
            '<Description type="Unit" ID="ALS1" subType="Character">'
            f"<Game>{name}</Game></Description>"
        )
    return (
        '<Majesty><Description type="Building" '
        f'ID="{family}1" subType="Building" Name="GeneratedBuilding">'
        '<Game><DialogID value="CGAL" /></Game></Description>'
        f"{unit}</Majesty>"
    )


def _generated_controller_gpl() -> str:
    return (
        "function Alchemist_DoInvigoratingElixer(agent ThisAgent)\n"
        "begin\nend\n"
        "function Alchemist_Arcane_Infusion(agent laboratory)\n"
        "begin\nend\n"
    )


def _generated_controller_evidence_fixture(root: Path):
    definition = ModDefinition(
        schema_version=2,
        mod_id="{00000000-0000-0000-0000-000000000099}",
        internal_name="Generated",
        display_name="Generated",
        custom_buildings=(
            CustomBuildingDefinition(
                local_name="GeneratedBuilding",
                dialog_id="CGAL",
                controller_base="AP10",
                panel_resource_template="AP10",
            ),
        ),
        runtime_capabilities=(),
    )
    description = root / "generated.xml"
    description.write_text(_generated_controller_description(), encoding="utf-8")
    gpl = root / "generated.gpl"
    gpl.write_text(_generated_controller_gpl(), encoding="cp1252")
    inventory = PackageInventory(
        selected=SelectedMod(
            "generated",
            SimpleNamespace(definition=definition, mod_id=definition.mod_id),
        ),
        cams=(),
        descriptions=(description,),
        gpl_loads=(
            SimpleNamespace(
                sources=(SimpleNamespace(absolute_path=gpl),),
            ),
        ),
        resources=(
            *_panel_pair(
                "generated",
                b"CGAL",
                (0x1F49, 0x1F47, 0x1F4F),
            ),
            *_panel_pair(
                "generated",
                b"CGBR",
                (
                    0x2A23, 0x2A24, 0x2A25,
                    0x2A13, 0x2A13 + 1000, 0x2A11, 0x2A12,
                    0x2A16, 0x2A16 + 1000, 0x2A17, 0x2A18,
                    0x2A16 + 500,
                    0x2A10, 0x2A10 + 1000, 0x2A10 - 1000,
                    0x2009, 0x227A,
                    0x1132, 0x1132 + 1000, 0x1132 - 1000,
                    0x1133, 0x1133 + 1000, 0x1133 - 1000,
                ),
            ),
        ),
    )
    features = legacy_alchemist_controller_features("GeneratedBuilding")
    registry = resolve_stock_controller_registry(
        features,
        {
            "brewing": (
                int.from_bytes(b"CGAL", "little"),
                int.from_bytes(b"CGBR", "little"),
            )
        },
    )
    return inventory, registry, description, gpl


if __name__ == "__main__":
    unittest.main()
