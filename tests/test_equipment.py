from dataclasses import replace
from pathlib import Path
import struct
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
import xml.etree.ElementTree as ET

from majesty_cam.cam import CamArchive, CamEntry, CamSection, pad_name
from majesty_cam.compose import (CamResource, _join_imag_sets, _split_imag_sets,
                                resolve_runtime_feature_registry)
from majesty_cam.equipment import (StockEquipment, EquipmentRegistration, parse_equipment,
    equipment_mapping, registration, require_beta2, EQUIPMENT_FEATURE_TYPE)
from majesty_cam.equipment_compose import (resolve_equipment, validate_art,
    transform_equipment_description, bind_equipment_art, validate_generated_equipment)
from majesty_cam.runtime_features import (NativeTimingFeature, MapFogQueryFeature,
    encode_runtime_feature_registry, decode_runtime_feature_registry,
    derive_feature_runtime_capabilities)
from majesty_cam.package import parse_mod_definition, mod_definition_mapping
from majesty_cam.strt import StrtTable, StrtRecord


UUID = "39ee2697-33c8-42e2-a575-c26c00640f24"
FEATURE = StockEquipment("field-blade", "weapon", "ZN01", "ZI01", 1004, ("ZH01",))


def image(key=b"ZI01", set_id=1004, start=0, version=3):
    prefix = [1, 0, 0, 256] + [0] * 12 + [68, 0, 262145, 0, 0]
    if version == 4:
        prefix += [65536, 0]
    values = prefix + [0] * 8
    for n, i in enumerate(range(len(prefix) + 1, len(values), 2)):
        values[i] = start + n
    return _join_imag_sets(CamEntry(pad_name(key), b""), struct.pack("<5I", version, 0, 0, 0, 0),
                           ((set_id, struct.pack(f"<{len(values)}I", *values)),))


def inventory(root, features=(FEATURE,), mod_id=UUID, hero="ZH01"):
    description = root / "characters.xml"
    description.write_text(f'<Majesty><Description type="Unit" subType="Character" ID="{hero}" Name="FieldHero"><Game>'
                           '<AllowedWeapon value="Longsword"/><WeaponBasicDamage value="4"/>'
                           '<AllowedArmor value="Leather"/><ArmorBasicDamage value="3"/>'
                           '</Game></Description></Majesty>')
    names = CamEntry(pad_name(b"ZN01"), StrtTable(b"\0\2", tuple(StrtRecord(i, f"Rank {i}".encode()) for i in range(4))).to_bytes())
    tile = struct.pack("<10H", 1, 23, 23, 23, 0, 0, 0, 0, 255, 0) + bytes(1567)
    archive = CamArchive((CamSection(b"IMAG", (image(),)), CamSection(b"STRT", (names,)),
                          CamSection(b"TILE", tuple(CamEntry(pad_name(str(i).encode()), tile) for i in range(4)))))
    resources = tuple(CamResource("test", root / "art.cam", 0, si, ei, section.extension, entry)
                      for si, section in enumerate(archive.sections) for ei, entry in enumerate(section.entries))
    definition = SimpleNamespace(mod_id=mod_id, runtime_features=features, runtime_capabilities=())
    return SimpleNamespace(resources=resources, descriptions=(description,),
        selected=SimpleNamespace(alias="test", package=SimpleNamespace(mod_id=mod_id, definition=definition))), archive


class EquipmentTests(unittest.TestCase):
    def test_schema_and_identity(self):
        self.assertEqual(parse_equipment(equipment_mapping(FEATURE)), FEATURE)
        definition = dict(schema_version=3, mod_id=UUID, internal_name="Example",
                          display_name="Example", custom_buildings=[],
                          runtime_features=[equipment_mapping(FEATURE)])
        self.assertEqual(mod_definition_mapping(parse_mod_definition(definition)), definition)
        self.assertEqual(registration(UUID.upper(), FEATURE), registration(UUID, FEATURE))
        self.assertNotEqual(registration(UUID, FEATURE).equipment_id,
                            registration(UUID, replace(FEATURE, feature_key="other")).equipment_id)
        for field, value in (("slot", "boots"), ("image_set", True), ("image_set", 0x1000000),
                              ("hero_ids", []), ("hero_ids", ["ZH01", "ZH01"]),
                              ("feature_key", "../bad"), ("name_table", "bad")):
            with self.subTest(field=field), self.assertRaises(ValueError):
                parse_equipment(dict(equipment_mapping(FEATURE), **{field: value}))
        with self.assertRaises(ValueError):
            parse_equipment(dict(equipment_mapping(FEATURE), price=100))

    def test_registry_round_trip_and_corruption(self):
        records = (registration(UUID, FEATURE), EquipmentRegistration(0x800001, 1, "ZN02"))
        for extras in ((), (MapFogQueryFeature(),), (NativeTimingFeature(("ZS01",), ("ZE01",)),)):
            wire = encode_runtime_feature_registry((*records, *extras))
            parsed = decode_runtime_feature_registry(wire)
            self.assertEqual(encode_runtime_feature_registry(parsed), wire)
            self.assertIn(EQUIPMENT_FEATURE_TYPE, derive_feature_runtime_capabilities((), parsed))
            for length in range(len(wire)):
                with self.assertRaises(ValueError):
                    decode_runtime_feature_registry(wire[:length])
        with self.assertRaisesRegex(ValueError, "duplicate"):
            encode_runtime_feature_registry((records[0], records[0]))
        for bad in (EquipmentRegistration(1, 0, "ZN01"), EquipmentRegistration(0x800001, 2, "ZN01")):
            with self.assertRaises(ValueError):
                encode_runtime_feature_registry((bad,))

    def test_evidence_and_description_transform(self):
        with TemporaryDirectory() as tmp:
            inv, _ = inventory(Path(tmp))
            records = resolve_equipment((inv,))
            self.assertEqual(records, (registration(UUID, FEATURE),))
            self.assertEqual(resolve_runtime_feature_registry((inv,)).equipment, records)
            element = ET.parse(inv.descriptions[0]).getroot()[0]
            transform_equipment_description(inv.selected.package.definition, element)
            self.assertEqual(element.find("Game/AllowedWeapon").get("value"), records[0].enum_name)
            self.assertEqual(element.find("Game/WeaponBasicDamage").get("value"), "4")
            self.assertEqual(element.find("Game/AllowedArmor").get("value"), "Leather")
            inv.selected.package.definition.runtime_features = (FEATURE, replace(FEATURE, feature_key="other"))
            with self.assertRaisesRegex(ValueError, "also assigned"):
                resolve_equipment((inv,))

    def test_armor_and_generated_evidence(self):
        with TemporaryDirectory() as tmp:
            feature = replace(FEATURE, slot="armor")
            inv, archive = inventory(Path(tmp), (feature,))
            record = resolve_equipment((inv,))[0]
            tree = ET.parse(inv.descriptions[0])
            transform_equipment_description(inv.selected.package.definition, tree.getroot()[0])
            tree.write(inv.descriptions[0])
            inv.resources = tuple(replace(item, entry=image(b"INBa", record.equipment_id))
                                  if item.section == b"IMAG" else item for item in inv.resources)
            validate_generated_equipment(inv, record)

    def test_reject_changed_topology_and_bad_tiles(self):
        with TemporaryDirectory() as tmp:
            inv, _ = inventory(Path(tmp))
            original = inv.resources
            data = bytearray(original[0].entry.data)
            data[32 + 12] = 0x55
            inv.resources = (replace(original[0], entry=replace(original[0].entry, data=bytes(data))), *original[1:])
            with self.assertRaisesRegex(ValueError, "stock frame"):
                validate_art(inv, "ZI01", 1004)
            inv.resources = tuple(replace(item, entry=replace(item.entry, data=item.entry.data[:-1]))
                                  if item.section == b"TILE" else item for item in original)
            with self.assertRaisesRegex(ValueError, "TILE"):
                validate_art(inv, "ZI01", 1004)

    def test_art_graft_preserves_stock_and_relocated_indices(self):
        with TemporaryDirectory() as tmp:
            inv, archive = inventory(Path(tmp))
            source, stock = image(start=200), image(b"INBw", 1004, 100)
            archive = replace(archive, sections=(CamSection(b"IMAG", (source, stock)), *archive.sections[1:]))
            from majesty_cam.compose import ArtDomainComposeResult
            result = ArtDomainComposeResult("interface", archive, (), (), (), None)
            output = bind_equipment_art((result,), (inv,))[0]
            output_stock = output.archive.sections[0].entries[1]
            sets = dict(_split_imag_sets(output_stock)[1])
            self.assertEqual(sets[1004], dict(_split_imag_sets(stock)[1])[1004])
            self.assertEqual(sets[registration(UUID, FEATURE).equipment_id], dict(_split_imag_sets(source)[1])[1004])
            with self.assertRaisesRegex(ValueError, "collides"):
                bind_equipment_art((output,), (inv,))

    def test_profile_gate(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "game.exe"
            header = bytearray(128)
            header[:2] = b"MZ"
            struct.pack_into("<I", header, 60, 64)
            header[64:68] = b"PE\0\0"
            struct.pack_into("<H", header, 68, 0x14C)
            for stamp in (0x5A8A11D5, 0x5897B72F, 0):
                struct.pack_into("<I", header, 72, stamp)
                path.write_bytes(header)
                if stamp == 0x5A8A11D5:
                    require_beta2(path)
                else:
                    with self.assertRaisesRegex(ValueError, "beta2"):
                        require_beta2(path)

    def test_art_binding_clones_destination_version_for_both_slots(self):
        from majesty_cam.compose import ArtDomainComposeResult
        for slot, target_key, template in (("weapon", b"INBw", 1004), ("armor", b"INBa", 1000)):
            for source_version, target_version in ((3, 3), (3, 4), (4, 3), (4, 4)):
                with self.subTest(slot=slot, source=source_version, target=target_version), TemporaryDirectory() as tmp:
                    feature = replace(FEATURE, slot=slot)
                    inv, archive = inventory(Path(tmp), (feature,))
                    source = image(version=source_version)
                    stock = image(target_key, template, 200, version=target_version)
                    archive = replace(archive, sections=(CamSection(b"IMAG", (source, stock)), *archive.sections[1:]))
                    result = bind_equipment_art((ArtDomainComposeResult("interface", archive, (), (), (), None),), (inv,))[0]
                    bound = result.archive.sections[0].entries[1]
                    key = registration(UUID, feature).equipment_id
                    header, sets = _split_imag_sets(bound)
                    self.assertEqual(header, stock.data[:20])
                    self.assertEqual(dict(sets)[template], dict(_split_imag_sets(stock)[1])[template])
                    self.assertEqual(dict(sets)[key], dict(_split_imag_sets(image(version=target_version))[1])[1004])
                    # Exercise the final generated-art validator, not merely
                    # the version-agnostic end-anchored reference reader.
                    inv.resources = tuple(replace(item, entry=bound) if item.section == b"IMAG" else item
                                          for item in inv.resources)
                    validate_art(inv, target_key.decode(), key)

    def test_art_rejects_mixed_container_and_set_versions(self):
        with TemporaryDirectory() as tmp:
            inv, _ = inventory(Path(tmp))
            original = inv.resources[0]
            mixed = image().data
            mixed = struct.pack("<I", 4) + mixed[4:]
            inv.resources = (replace(original, entry=replace(original.entry, data=mixed)), *inv.resources[1:])
            with self.assertRaisesRegex(ValueError, "version-4 stock frame layout"):
                validate_art(inv, "ZI01", 1004)
