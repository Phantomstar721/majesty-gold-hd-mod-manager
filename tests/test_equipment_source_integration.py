"""Opt-in, read-only source integration. Never builds a Manager profile.

MAJESTY_EQUIPMENT_PACKAGE selects any schema-3 source package; MAJESTY_BETA2_EXE
selects the audited game. All resource binding/relocation below is in memory.
"""
import hashlib
import os
from pathlib import Path
import unittest
from xml.etree.ElementTree import tostring
from types import SimpleNamespace

from majesty_cam.art import parse_stock_imag_tile_references, rewrite_stock_imag_entries
from majesty_cam.cam import CamArchive, CamEntry, CamSection, pad_name
from majesty_cam.compose import (ArtDomainComposeResult, CamResource, SelectedMod, _parse_description_file,
                                _split_imag_sets, inventory_package, resolve_runtime_feature_registry)
from majesty_cam.equipment import registration, require_beta2
from majesty_cam.equipment_compose import (bind_equipment_art, declarations,
                                         transform_equipment_description, validate_art)
from majesty_cam.package import load_package
from majesty_cam.runtime_features import encode_runtime_feature_registry, decode_runtime_feature_registry
from majesty_cam.stock_art import collapse_art_archives


class EquipmentSourceIntegrationTests(unittest.TestCase):
    def test_authored_resources_survive_relocation_and_native_binding(self):
        package_path = os.environ.get("MAJESTY_EQUIPMENT_PACKAGE")
        executable_path = os.environ.get("MAJESTY_BETA2_EXE")
        if not package_path or not executable_path:
            self.skipTest("equipment source package and beta2 executable were not supplied")
        root, executable = Path(package_path), Path(executable_path)
        require_beta2(executable)
        paths = tuple(path for path in root.rglob("*") if path.is_file())
        original_hashes = {path: hashlib.sha256(path.read_bytes()).digest() for path in paths}
        package = load_package(root)
        inventory = inventory_package(SelectedMod("equipment-integration", package))
        features = declarations(inventory)
        self.assertTrue(features)
        registry = resolve_runtime_feature_registry((inventory,))
        self.assertEqual(len(registry.equipment), len(features))
        self.assertEqual(decode_runtime_feature_registry(encode_runtime_feature_registry(registry)), registry)

        # Every assignment changes only the intended Allowed* field. Stock base
        # values and the other equipment slot remain native Description data.
        for path in inventory.descriptions:
            for record in _parse_description_file(path).records:
                element = record.to_element()
                expected = record.to_element()
                for feature in features:
                    if record.key == ("Unit", element.get("ID")) and element.get("ID") in feature.hero_ids:
                        expected.find(f"./Game/Allowed{feature.slot.title()}").set(
                            "value", registration(package.mod_id, feature).enum_name)
                transform_equipment_description(package.definition, element)
                self.assertEqual(tostring(element), tostring(expected))

        classified = collapse_art_archives(executable.parent, tuple(inventory.art_cams),
                                          owner=inventory.selected.alias)
        source_keys = {feature.image_id.encode("ascii") for feature in features}
        candidates = [item for item in classified if source_keys <= {
            entry.name[:4] for section in item.archive.sections if section.extension == b"IMAG"
            for entry in section.entries}]
        self.assertEqual(len(candidates), 1, "equipment icons must share one interface lineage")
        source = candidates[0]
        source_images = tuple(entry for section in source.archive.sections if section.extension == b"IMAG"
                              for entry in section.entries if entry.name[:4] in source_keys)
        source_tiles = next(section.entries for section in source.archive.sections if section.extension == b"TILE")
        stock_images = tuple(entry for section in source.lineage.effective.sections if section.extension == b"IMAG"
                             for entry in section.entries if entry.name[:4] in (b"INBw", b"INBa"))
        self.assertEqual(len(stock_images), 2)
        referenced = sorted({reference.tile_index for entry in source_images
            for reference in parse_stock_imag_tile_references(entry.data, tile_count=len(source_tiles)).references})
        mapping = {old: len(source_tiles) + 20 + i for i, old in enumerate(referenced)}
        rewritten = rewrite_stock_imag_entries(source_images, mapping, tile_count=len(source_tiles))
        relocated_tiles = list(source_tiles)
        relocated_tiles.extend(CamEntry(pad_name(b""), b"")
                               for _ in range(max(mapping.values()) + 1 - len(relocated_tiles)))
        for old, new in mapping.items():
            relocated_tiles[new] = source_tiles[old]
        fixture = ArtDomainComposeResult("interface", CamArchive((
            CamSection(b"IMAG", (*stock_images, *rewritten.entries)),
            CamSection(b"TILE", tuple(relocated_tiles)))),
                                        (), (), (), None)
        result = bind_equipment_art((fixture,), (inventory,))[0]
        generated_art_inventory = SimpleNamespace(resources=tuple(
            CamResource("fixture", root / "in-memory-fixture.cam", 0, si, ei, section.extension, entry)
            for si, section in enumerate(result.archive.sections) for ei, entry in enumerate(section.entries)))
        bound = {entry.name[:4]: entry for entry in result.archive.sections[0].entries}
        for stock in stock_images:
            before = dict(_split_imag_sets(stock)[1])
            after = dict(_split_imag_sets(bound[stock.name[:4]])[1])
            self.assertTrue(all(after[key] == payload for key, payload in before.items()))
        for feature in features:
            native = registration(package.mod_id, feature)
            # Include the final validator: generic end-anchored parsing alone
            # can read a v3 set incorrectly inserted beneath an MX/v4 header.
            validate_art(generated_art_inventory, native.image_id, native.equipment_id)
            original = next(entry for entry in source_images if entry.name[:4] == feature.image_id.encode("ascii"))
            old_refs = [ref for ref in parse_stock_imag_tile_references(original.data, tile_count=len(source_tiles)).references
                        if ref.set_id == feature.image_set]
            new_refs = [ref for ref in parse_stock_imag_tile_references(bound[native.image_id.encode("ascii")].data,
                            tile_count=max(mapping.values()) + 1).references if ref.set_id == native.equipment_id]
            self.assertEqual([ref.tile_index for ref in new_refs], [mapping[ref.tile_index] for ref in old_refs])
            self.assertEqual(len(new_refs), 4)
        self.assertEqual({path: hashlib.sha256(path.read_bytes()).digest() for path in paths}, original_hashes)

    def test_deployed_source_matches_canonical_package(self):
        source, deployed = os.environ.get("MAJESTY_EQUIPMENT_PACKAGE"), os.environ.get("MAJESTY_EQUIPMENT_DEPLOYED")
        if not source or not deployed:
            self.skipTest("source and deployed package were not supplied")
        def hashes(root):
            root = Path(root)
            return {path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).digest()
                    for path in root.rglob("*") if path.is_file()}
        self.assertEqual(hashes(source), hashes(deployed))
