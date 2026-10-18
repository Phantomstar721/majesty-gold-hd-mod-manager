from dataclasses import replace
import sys
from pathlib import Path
import struct
import unittest
import os
import hashlib

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from majesty_cam.hero_info import parse_hero_info, hero_info_mapping, INVENTORY_ITEM_DISPLAY_TYPE
from majesty_cam.runtime_features import encode_runtime_feature_registry, decode_runtime_feature_registry
from majesty_cam.package import parse_mod_definition, mod_definition_mapping


class InventoryDisplayTests(unittest.TestCase):
    def test_all_three_native_bodies_and_append_site(self):
        from test_occupant_runtime_profiles import PeImage
        profiles = (
            ("PUBLIC", 0xA2E30, "b8295e82657523a590a810330af4f76b6dc2155793777faff5874534d90cb32d", 0xB4750),
            ("BETA2", 0xA3710, "18afd99b9773ef2bce632bd3381f13f5c370ef6a6f357944fb1e758cea6fac06", 0xB5040),
            ("GOG", 0xA3CC0, "45da1c8b23b90fdc3722e6dbd7b981181d55a0e5f81d134e425fbcc9657602a9", 0xB5640))
        for name, rva, digest, append in profiles:
            path = os.environ.get(f"MAJESTY_{name}_EXE")
            if not path: self.skipTest(f"{name} fixture not provided")
            image = PeImage(path)
            self.assertEqual(hashlib.sha256(image.read(rva, 0x1A1)).hexdigest(), digest)
            self.assertEqual(image.read(rva+0x138, 7), bytes.fromhex("682d230000ffd0"))
            self.assertEqual(hashlib.sha256(image.read(append, 30)).hexdigest(),
                "217e1692b0f6bb14328ba53943c8ca07ef02fe1cdb1073bfd5f70280499ce721")

    def declaration(self, **changes):
        return dict(type=INVENTORY_ITEM_DISPLAY_TYPE, feature_key="private-dose", item_id=114,
                    display_text="Private dose", tooltip_text="Use this dose", image_id="DI01", image_set=1019, **changes)

    def test_registry_and_package_roundtrip(self):
        row = parse_hero_info(self.declaration())
        payload = encode_runtime_feature_registry((row,))
        self.assertEqual(struct.unpack_from("<I", payload, 4)[0], 12)
        decoded = decode_runtime_feature_registry(payload)
        self.assertEqual(decoded.hero_info_rows, (row,))
        value = dict(schema_version=3, mod_id="11111111-1111-1111-1111-111111111111",
            internal_name="Items", display_name="Items", custom_buildings=[], runtime_features=[self.declaration()])
        self.assertEqual(mod_definition_mapping(parse_mod_definition(value)), value)

    def test_no_save_attribute_or_unbounded_id(self):
        for item_id in (-1, 128, True, "114"):
            value = self.declaration();value["item_id"] = item_id
            with self.assertRaises(ValueError): parse_hero_info(value)
        value = self.declaration();value["attribute_symbol"] = "Dose"
        with self.assertRaises(ValueError): parse_hero_info(value)

    def test_rejects_development_and_duplicate_item(self):
        dose = parse_hero_info(self.declaration())
        with self.assertRaises(ValueError):
            parse_hero_info(dict(type="stock.ap78-saved-attribute-row.v1", feature_key="saved",
                attribute_symbol="Existing", display_text="Saved", tooltip_text="Owned", image_id="DI02", image_set=1019))
        with self.assertRaisesRegex(ValueError, "duplicate"):
            encode_runtime_feature_registry((dose, replace(dose, feature_key="other")))

if __name__ == "__main__": unittest.main()

