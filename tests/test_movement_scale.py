from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import os
import re
import struct
import unittest

from majesty_cam.movement_scale import (OverlayMovementScale, MOVEMENT_SCALE_TYPE,
    movement_scale_mapping, parse_movement_scale, validate_movement_scale_evidence)
from majesty_cam.runtime_features import (normalize_runtime_features, encode_runtime_feature_registry,
    decode_runtime_feature_registry, derive_feature_runtime_capabilities, MovementQueryFeature)
from majesty_cam.package import parse_mod_definition, mod_definition_mapping, PackageFormatError
from majesty_cam.compose import resolve_runtime_feature_registry, ComposeError
from majesty_cam.manager.capabilities import DERIVED_RUNTIME_CAPABILITIES
from majesty_cam.manager.runtime_profiles import unsupported_runtime_capabilities
from majesty_cam.manager.qol_service import GOG_BRANCH
from test_occupant_runtime_profiles import PeImage
from test_hero_info import inventory, ROW


SCALE = OverlayMovementScale("ZE01", 115)


class MovementScaleTests(unittest.TestCase):
    def test_package_wire_and_capability_round_trip(self):
        definition = dict(schema_version=3, mod_id="39ee2697-33c8-42e2-a575-c26c00640f24",
                          internal_name="Example", display_name="Example", custom_buildings=[],
                          runtime_features=[movement_scale_mapping(SCALE)])
        self.assertEqual(mod_definition_mapping(parse_mod_definition(definition)), definition)
        features = (SCALE, MovementQueryFeature(), replace(SCALE, overlay_id="ZE02", percent=85))
        wire = encode_runtime_feature_registry(features)
        self.assertEqual(struct.unpack_from("<I", wire, 4)[0], 8)
        self.assertEqual(wire, encode_runtime_feature_registry(reversed(features)))
        self.assertEqual(decode_runtime_feature_registry(wire), normalize_runtime_features(features))
        self.assertEqual(derive_feature_runtime_capabilities((), normalize_runtime_features([SCALE])),
                         (MOVEMENT_SCALE_TYPE,))
        self.assertEqual(derive_feature_runtime_capabilities([MOVEMENT_SCALE_TYPE], normalize_runtime_features()), ())
        self.assertIn(MOVEMENT_SCALE_TYPE, DERIVED_RUNTIME_CAPABILITIES)
        self.assertEqual(unsupported_runtime_capabilities(GOG_BRANCH, [MOVEMENT_SCALE_TYPE]), (MOVEMENT_SCALE_TYPE,))

    def test_reject_bad_schema_and_wire(self):
        value = movement_scale_mapping(SCALE)
        for percent in (True, False, 0, -1, 1001, 1.15, "115", None):
            with self.subTest(percent=percent), self.assertRaises(ValueError):
                parse_movement_scale(dict(value, percent=percent))
        for key, replacement in (("overlay_id", ""), ("overlay_id", "TOOLONG"), ("extra", 1)):
            with self.assertRaises(ValueError):
                parse_movement_scale(dict(value, **{key: replacement}))
        self.assertEqual(normalize_runtime_features([SCALE, SCALE]).movement_scales, (SCALE,))
        with self.assertRaisesRegex(ValueError, "conflicting"):
            normalize_runtime_features([SCALE, replace(SCALE, percent=120)])
        wire = encode_runtime_feature_registry([SCALE])
        for count in range(len(wire)):
            with self.subTest(count=count), self.assertRaises(ValueError):
                decode_runtime_feature_registry(wire[:count])
        for offset, number in ((4, 9), (16, 0), (16, 128), (20, 257), (28, 0), (28, 1001)):
            bad = bytearray(wire)
            struct.pack_into("<I", bad, offset, number)
            with self.subTest(offset=offset, number=number), self.assertRaises(ValueError):
                decode_runtime_feature_registry(bytes(bad))
        with self.assertRaises(ValueError):
            decode_runtime_feature_registry(wire+b'junk')
        pair = encode_runtime_feature_registry([SCALE, replace(SCALE, overlay_id="ZE02")])
        for tail in (pair[24:32], struct.pack('<II', int.from_bytes(b'ZE00', 'little'), 115)):
            with self.assertRaises(ValueError):
                decode_runtime_feature_registry(pair[:32]+tail)

    def test_older_feature_sections_keep_v8_layout(self):
        from majesty_cam.kingdom_research import KingdomResearchRegistration
        from majesty_cam.runtime_features import NativeTimingFeature, EnchantmentRowFeature
        # Include research without visuals: v8 still has the v6 empty string field.
        from test_kingdom_research import FEATURE, UUID
        from majesty_cam.kingdom_research import registration
        item = registration(UUID, FEATURE, "EXG")
        features = (SCALE, ROW, NativeTimingFeature(), EnchantmentRowFeature('ZX01', 'Example'), item)
        wire = encode_runtime_feature_registry(features)
        self.assertEqual(decode_runtime_feature_registry(wire), normalize_runtime_features(features))

    def test_owned_overlay_evidence_and_conflicting_claims(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            item = inventory(root, replace(ROW, kind='enchantment', subject_id='ZE01', unlock_level=0))
            item.selected.package.definition.runtime_features = (SCALE,)
            self.assertEqual(resolve_runtime_feature_registry([item]).movement_scales, (SCALE,))
            validate_movement_scale_evidence(item, SCALE)
            second = SimpleNamespace(**vars(item))
            second.selected = SimpleNamespace(alias='other', package=item.selected.package)
            with self.assertRaisesRegex(ComposeError, 'claimed by both'):
                resolve_runtime_feature_registry([item, second])
            with self.assertRaises(ValueError):
                validate_movement_scale_evidence(item, replace(SCALE, overlay_id='NOPE'))
            item.descriptions[0].write_text('<Majesty><Description type="Unit" subType="Character" ID="ZE01"/></Majesty>')
            with self.assertRaises(ValueError):
                validate_movement_scale_evidence(item, SCALE)

    def test_native_audit_and_displaced_instructions(self):
        path = os.environ.get('MAJESTY_BETA2_EXE')
        if not path:
            self.skipTest('MAJESTY_BETA2_EXE not configured')
        image = PeImage(path)
        root = Path(__file__).resolve().parents[1]
        source = (root/'runtime/MovementScaleRuntime.inl').read_text()
        audits = re.findall(r'hash\((0x[0-9A-F]+), (0x[0-9A-F]+)\) == (0x[0-9A-F]+)u', source)
        self.assertEqual(len(audits), 7)
        for rva, count, expected in audits:
            value = 2166136261
            for byte in image.read(int(rva, 16), int(count, 16)):
                value = ((value ^ byte)*16777619) & 0xFFFFFFFF
            self.assertEqual(value, int(expected, 16), rva)
        self.assertEqual(image.read(0x1E31D2, 6), bytes.fromhex('8b 03 85 c0 7e 72'))
        self.assertEqual(image.read(0x1E3286, 6), bytes.fromhex('8b 1b 85 db 7e 1e'))
        self.assertEqual(image.target(0x1E31EA), 0x1E2910)
        fixtures = (root/'tests/MovementScaleRuntimeTests.h').read_text()
        for name, rva in (("order", 0x1E3120), ("multiply", 0x1E2910), ("divide", 0x1E2950),
                          ("fixedMultiply", 0x27D0F8), ("fixedDivide", 0x27D111), ("clamp", 0x1E3020)):
            literal = bytes.fromhex(re.search(r'const char\* ' + name + r'Hex = "([0-9a-f]+)";', fixtures)[1])
            self.assertEqual(image.read(rva, len(literal)), literal, name)


if __name__ == '__main__':
    unittest.main()
