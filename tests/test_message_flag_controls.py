"""Native-only admission and wire contract; never constructs a merged profile."""
import json
from pathlib import Path
import struct
from tempfile import TemporaryDirectory
import unittest

from majesty_cam.runtime_features import (
    MessageFlagControlsFeature, MESSAGE_FLAG_CONTROLS_CAPABILITY,
    NativeTimingFeature, encode_runtime_feature_registry,
    decode_runtime_feature_registry, derive_feature_runtime_capabilities,
)
from majesty_cam.package import parse_mod_definition, PackageFormatError
from majesty_cam.manager.catalog import scan_catalog, CatalogKind
from majesty_cam.manager.preflight import prepare_merge_package
from majesty_cam.manager.compatibility import CompatibilityRegistry
from majesty_cam.manager.runtime_profiles import unsupported_runtime_capabilities
from majesty_cam.manager.qol_service import PUBLIC_BRANCH, BETA2_BRANCH, GOG_BRANCH
from majesty_cam.compose import resolve_runtime_feature_registry


MOD_ID = "{51F3F0DB-81AB-42B4-9ACE-ABA863DE9917}"


def definition():
    return dict(schema_version=3, mod_id=MOD_ID, internal_name="MessageFlagControls",
                display_name="Message Controls", custom_buildings=[],
                runtime_features=[dict(type=MESSAGE_FLAG_CONTROLS_CAPABILITY)])


class MessageFlagControlsTests(unittest.TestCase):
    def test_wire_round_trip_and_all_profiles(self):
        for features in ((MessageFlagControlsFeature(),),
                         (MessageFlagControlsFeature(), NativeTimingFeature())):
            data = encode_runtime_feature_registry(features)
            self.assertEqual(struct.unpack_from('<I', data, 4)[0], 13)
            parsed = decode_runtime_feature_registry(data)
            self.assertTrue(parsed.message_flag_controls)
            self.assertEqual(encode_runtime_feature_registry(parsed), data)
            for length in range(len(data)):
                with self.assertRaises(ValueError):
                    decode_runtime_feature_registry(data[:length])
        for branch in (PUBLIC_BRANCH, BETA2_BRANCH, GOG_BRANCH):
            self.assertEqual(unsupported_runtime_capabilities(branch, (MESSAGE_FLAG_CONTROLS_CAPABILITY,)), ())
        for version, flags in ((12, 256), (13, 0), (13, 512), (14, 256)):
            with self.assertRaises(ValueError):
                decode_runtime_feature_registry(struct.pack('<4s4I', b'MMFR', version, 0, 0, flags))

    def test_no_package_addresses_or_paths(self):
        for key in ('address', 'path', 'patch', 'enabled'):
            value = definition()
            value['runtime_features'][0][key] = 1
            with self.assertRaises(PackageFormatError):
                parse_mod_definition(value)

    def test_real_minimal_package_without_cam_or_gpl(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / 'MessageFlagControls'
            root.mkdir()
            (root / 'MessageFlagControls.mmxml').write_text(
                f'<Majesty><Mod id="{MOD_ID}"><DisplayName lang="en_US">Message Controls</DisplayName>'
                '<DataConfiguration><Dataset base="Any"><Load/></Dataset></DataConfiguration></Mod></Majesty>')
            (root / 'mod-definition.json').write_text(json.dumps(definition()))
            entry = scan_catalog(local_mods_root=Path(tmp)).entries[0]
            self.assertEqual(entry.kind, CatalogKind.MERGE)
            self.assertTrue(entry.merge_ready, entry.issues)
            prepared = prepare_merge_package(content_id=MOD_ID, display_name='Message Controls',
                source_root=root, registry=CompatibilityRegistry({}))
            self.assertEqual(prepared.issues, ())
            self.assertEqual(prepared.inventory.cams, ())
            self.assertEqual(prepared.inventory.gpl_loads, ())
            registry = resolve_runtime_feature_registry((prepared.inventory,))
            self.assertTrue(registry.message_flag_controls)
            self.assertIn(MESSAGE_FLAG_CONTROLS_CAPABILITY,
                          derive_feature_runtime_capabilities((), registry))


if __name__ == '__main__':
    unittest.main()
