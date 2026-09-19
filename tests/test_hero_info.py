from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import os
import re
import struct
import unittest
from xml.etree import ElementTree as ET

from majesty_cam.hero_info import (HeroInfoRow, hero_info_mapping, parse_hero_info,
                                  validate_hero_info_evidence, HERO_INFO_TYPE, enable_native_tooltips)
from majesty_cam.runtime_features import (encode_runtime_feature_registry, decode_runtime_feature_registry,
    normalize_runtime_features, derive_feature_runtime_capabilities, EnchantmentRowFeature)
from majesty_cam.package import parse_mod_definition, mod_definition_mapping
from majesty_cam.compose import CamResource, _join_imag_sets, _split_imag_sets, resolve_runtime_feature_registry
from majesty_cam.cam import CamEntry, pad_name, read_cam
from test_occupant_runtime_profiles import PeImage

ROW = HeroInfoRow("field-lore", "passive", "ZH01", 2, "Field lore", "Read-only explanation", "ZI01", 1019)


def inventory(root, row=ROW, *, stock=None):
    description = root / "characters.xml"
    typ, sub = {"spell": ("Action", "Standard"), "enchantment": ("Unit", "Overlay"), "passive": ("Unit", "Character")}[row.kind]
    description.write_text(f'<Majesty><Description type="{typ}" subType="{sub}" ID="{row.subject_id}" Name="Private">'
        '<Game><Flags value="IsSpell"/></Game></Description></Majesty>')
    side = 25 if row.kind == "enchantment" else 24
    values = [1, 0, 0, 256] + [0]*12 + [68, 0, 65537, 0, 0, 65536, 0, 0, 0]
    header, payload = struct.pack("<5I", 4, 0, 0, 0, 0), struct.pack("<25I", *values)
    tile = struct.pack("<10H", 1, side, side, side, 0, 0, 0, 0, 255, 0) + bytes(1038+side*side)
    if stock is not None:
        archive, name = stock
        image = next(e for s in archive.sections if s.extension == b"IMAG" for e in s.entries if e.name[:4] == name)
        header, sets = _split_imag_sets(image)
        payload = dict(sets)[1019]
        index = struct.unpack_from("<I", payload, len(payload)-4)[0]
        tile = next(s for s in archive.sections if s.extension == b"TILE").entries[index].data
        payload = payload[:-4] + bytes(4)
    image = _join_imag_sets(CamEntry(pad_name(row.image_id.encode()), b""), header, ((row.image_set, payload),))
    resources = (CamResource("owner", root/"art.cam", 0, 0, 0, b"IMAG", image),
                 CamResource("owner", root/"art.cam", 0, 1, 0, b"TILE", CamEntry(pad_name(b"0000"), tile)))
    definition = SimpleNamespace(runtime_features=(row,), runtime_capabilities=())
    return SimpleNamespace(resources=resources, descriptions=(description,),
        selected=SimpleNamespace(alias="owner", package=SimpleNamespace(definition=definition)))


class HeroInfoTests(unittest.TestCase):
    def test_tooltip_flags_use_stock_list_properties_only(self):
        from majesty_cam.compose import merge_text_resources
        # Literal stock AP78 list property headers, with unrelated records kept.
        left = [6, 2, 13, 56, 158, 82, 33, 0, 10, 16, 10, 1048576,
                12, 1230261833, 13, 1005, 3, 128, 6, 0x221A, 0xFFFFFFFF]
        right = left.copy()
        right[3], right[5], right[19] = 161, 52, 0x221B
        other = [99, 0x400, 0xFFFFFFFF]
        pack = lambda parts: b''.join(struct.pack(f'<{len(p)}I', *p) for p in parts)
        payload = pack([other, left, right, [0xFFFFFFFF]])
        expected_left, expected_right = left.copy(), right.copy()
        expected_left[17] |= 0x400
        expected_right[17] |= 0x400
        expected = pack([other, expected_left, expected_right, [0xFFFFFFFF]])
        self.assertEqual(enable_native_tooltips(payload), expected)
        self.assertEqual(enable_native_tooltips(expected), expected)
        stock = {(b'SMNU', b'AP78'): payload}
        result = merge_text_resources(Path('unused'), (), stock_named_resources=stock,
                                      hero_info_tooltips=True)
        self.assertEqual(result.text_archive.sections[0].entries[0].data, expected)
        plain = merge_text_resources(Path('unused'), (), stock_named_resources=stock)
        self.assertEqual(plain.text_archive.sections[0].entries, ())
        with self.assertRaises(ValueError):
            enable_native_tooltips(pack([left, [0xFFFFFFFF]]))
        with self.assertRaises(ValueError):
            enable_native_tooltips(pack([left, left, right, [0xFFFFFFFF]]))
        left[16] = 7
        with self.assertRaises(ValueError):
            enable_native_tooltips(pack([left, right, [0xFFFFFFFF]]))

    def test_schema_and_wire(self):
        definition = dict(schema_version=3, mod_id="39ee2697-33c8-42e2-a575-c26c00640f24",
                          internal_name="Example", display_name="Example", custom_buildings=[],
                          runtime_features=[hero_info_mapping(ROW)])
        self.assertEqual(mod_definition_mapping(parse_mod_definition(definition)), definition)
        spell = replace(ROW, kind="spell", subject_id="ZA01", unlock_level=0)
        effect = replace(ROW, kind="enchantment", subject_id="ZE01", unlock_level=0)
        features = (ROW, replace(ROW, feature_key="second-row", unlock_level=5), spell, effect)
        data = encode_runtime_feature_registry(features)
        self.assertEqual(struct.unpack_from("<I", data, 4)[0], 7)
        self.assertEqual(data, encode_runtime_feature_registry(reversed(features)))
        registry = decode_runtime_feature_registry(data)
        self.assertEqual(registry, normalize_runtime_features(features))
        self.assertEqual(derive_feature_runtime_capabilities((), registry),
                         ("stock.ap78-enchantment-row.v1", HERO_INFO_TYPE))
        for count in range(len(data)):
            with self.assertRaises(ValueError):
                decode_runtime_feature_registry(data[:count])
        for field, value in (("feature_key", "../bad"), ("kind", "cast"), ("subject_id", "bad"),
            ("unlock_level", 0), ("unlock_level", True), ("image_id", "INTn"),
            ("image_set", 0x1000000), ("display_text", ""), ("tooltip_text", "x\0y")):
            with self.subTest(field=field), self.assertRaises(ValueError):
                parse_hero_info(dict(hero_info_mapping(ROW), **{field: value}))
        with self.assertRaisesRegex(ValueError, "legacy"):
            normalize_runtime_features((effect, EnchantmentRowFeature("ZE01", "Old")))
        with self.assertRaisesRegex(ValueError, "duplicate"):
            normalize_runtime_features((spell, replace(spell, feature_key="other")))

    def test_registry_v7_research_with_and_without_effect(self):
        from majesty_cam.kingdom_research import KingdomResearchRegistration
        for effect in ("", "Private_Active"):
            research = KingdomResearchRegistration("01"*16, 0x00475845, 0x7100, 0x13a6,
                0xd0000001, 3, 500, 5, 10, 0x7500, 0x7501, "Completed", effect)
            features = (ROW, research)
            self.assertEqual(decode_runtime_feature_registry(encode_runtime_feature_registry(features)),
                             normalize_runtime_features(features))

    def test_evidence_and_ownership(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            inv = inventory(root)
            validate_hero_info_evidence(inv, ROW)
            self.assertEqual(resolve_runtime_feature_registry((inv,)).hero_info_rows, (ROW,))
            other = SimpleNamespace(resources=inv.resources, descriptions=inv.descriptions,
                selected=SimpleNamespace(alias="other", package=inv.selected.package))
            with self.assertRaisesRegex(ValueError, "claimed by both"):
                resolve_runtime_feature_registry((inv, other))
            # A remapped TILE index is legal when it still points at the same
            # stock-shaped payload in the output archive.
            image, tile = inv.resources
            header, sets = _split_imag_sets(image.entry)
            data = sets[0][1][:-4] + struct.pack("<I", 19)
            moved = replace(image, entry=_join_imag_sets(image.entry, header, ((1019, data),)))
            inv.resources = (moved, replace(tile, entry_order=19))
            validate_hero_info_evidence(inv, ROW)
            inv.resources = (moved, tile)
            with self.assertRaisesRegex(ValueError, "TILE storage"):
                validate_hero_info_evidence(inv, ROW)
            inv.resources = (image, replace(tile, entry=replace(tile.entry, data=tile.entry.data[:-1])))
            with self.assertRaisesRegex(ValueError, "TILE storage"):
                validate_hero_info_evidence(inv, ROW)

    def test_native_timing_cannot_retype_stock_creature(self):
        from majesty_cam.compose import _validate_native_timing_stock_subjects
        from majesty_cam.runtime_features import NativeTimingFeature
        registry = normalize_runtime_features((NativeTimingFeature((), ("ZX01",)),))
        for subtype in ("Character", "Building"):
            stock = {("Unit", "ZX01"): (SimpleNamespace(to_element=lambda: ET.fromstring(
                f'<Description subType="{subtype}"/>')), "stock.xml")}
            with self.assertRaisesRegex(ValueError, "stock non-Overlay"):
                _validate_native_timing_stock_subjects(stock, registry)
        _validate_native_timing_stock_subjects({}, registry)
        _validate_native_timing_stock_subjects({("Unit", "ZX01"): (
            SimpleNamespace(to_element=lambda: ET.fromstring('<Description subType="Overlay"/>')), "stock.xml")}, registry)

    def test_literal_stock_icons(self):
        exe = os.environ.get("MAJESTY_BETA2_EXE")
        if not exe:
            self.skipTest("stock executable not provided")
        root = Path(exe).parent
        from majesty_cam.stock_cam import stock_image_ids
        keys = stock_image_ids(root)
        self.assertIn(b"INTn", keys)
        self.assertIn(b"IX93", keys)
        self.assertNotIn(b"ZI01", keys)
        with TemporaryDirectory() as tmp:
            for kind, relative, name in (("passive", "Data/interfacedata.cam", b"INTn"),
                                        ("enchantment", "DataMX/mx_interfacedata.cam", b"IX93")):
                row = replace(ROW, kind=kind, unlock_level=2 if kind == "passive" else 0)
                validate_hero_info_evidence(inventory(Path(tmp), row, stock=(read_cam(root/relative), name)), row)

    def test_audited_native_boundaries(self):
        path = os.environ.get("MAJESTY_BETA2_EXE")
        if not path:
            self.skipTest("stock executable not provided")
        image = PeImage(path)
        source = (Path(__file__).resolve().parents[1]/"runtime/HeroInfoRuntime.inl").read_text()
        hashes = re.findall(r'hash\((0x[0-9A-F]+), (0x[0-9A-F]+)\) == (0x[0-9A-F]+)u', source)
        self.assertEqual(len(hashes), 13)
        for rva, size, expected in hashes:
            actual = 2166136261
            for byte in image.read(int(rva, 16), int(size, 16)):
                actual = ((actual ^ byte)*16777619) & 0xffffffff
            self.assertEqual(actual, int(expected, 16), rva)
        for rva, target in ((0xa3e16, 0x272410), (0xa3e4b, 0x287f30), (0xa3e8d, 0x287770),
                            (0xa48ff, 0x287f30), (0xa4942, 0x287770)):
            self.assertEqual(image.target(rva), target)
        self.assertEqual(image.read(0xa407c, 7), bytes.fromhex("8b 74 24 18 8b 4e 24"))
        harness = (Path(__file__).resolve().parent/"HeroInfoRuntimeTests.h").read_text()
        literal = re.search(r"stockAppend\[\] = \{(.*?)\};", harness, re.S).group(1)
        append = bytes(int(value, 16) for value in re.findall(r"0x[0-9A-F]{2}", literal))
        self.assertEqual(len(append), 54)
        for rva in (0x272410, 0x272450):
            self.assertEqual(image.read(rva, len(append)), append)
        text = read_cam(Path(path).parent/'Data/textdata.cam')
        panel = next(e for s in text.sections if s.extension == b'SMNU'
                     for e in s.entries if e.name[:4] == b'AP78')
        changed = enable_native_tooltips(panel.data)
        differences = [(before, after) for before, after in zip(panel.data, changed) if before != after]
        self.assertEqual(differences, [(0, 4), (0, 4)])
