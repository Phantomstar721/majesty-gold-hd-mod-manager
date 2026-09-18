from dataclasses import replace
from pathlib import Path
import struct
import sys
from tempfile import TemporaryDirectory
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from majesty_cam.runtime_features import (
    NativeTimingFeature, MapFogQueryFeature, MovementQueryFeature,
    normalize_runtime_features, encode_runtime_feature_registry,
    decode_runtime_feature_registry, derive_feature_runtime_capabilities,
    NATIVE_TIMING_RUNTIME_CAPABILITY,
)
from majesty_cam.package import ModDefinition, parse_mod_definition, mod_definition_mapping
from majesty_cam.manager.build import _canonical_mod_definition
from majesty_cam.manager.capabilities import DERIVED_RUNTIME_CAPABILITIES
from majesty_cam.compose import ComposeError, resolve_runtime_feature_registry
from test_runtime_features import _feature_inventory


class NativeTimingTests(unittest.TestCase):
    def test_schema_and_fingerprint(self):
        feature = NativeTimingFeature(("Za01",), ("Ze01",))
        definition = ModDefinition(3, "00000000-0000-4000-8000-000000000001", "Timing", "Timing", (),
                                   runtime_features=(feature,))
        value = mod_definition_mapping(definition)
        self.assertEqual(parse_mod_definition(value), definition)
        self.assertEqual(_canonical_mod_definition(definition), value)
        self.assertNotEqual(_canonical_mod_definition(replace(definition, runtime_features=())), value)
        value["runtime_features"][0]["address"] = "12345678"
        with self.assertRaises(ValueError):
            parse_mod_definition(value)

    def test_registry_and_opt_in(self):
        for feature in (NativeTimingFeature(), NativeTimingFeature(("Za01", "Za02"), ("Ze01",))):
            registry = normalize_runtime_features((feature, feature, MapFogQueryFeature(), MovementQueryFeature()))
            payload = encode_runtime_feature_registry(registry)
            self.assertEqual(payload[:20], struct.pack("<4s4I", b"MMFR", 3, 0, 0, 7))
            self.assertEqual(decode_runtime_feature_registry(payload), registry)
            self.assertIn(NATIVE_TIMING_RUNTIME_CAPABILITY, derive_feature_runtime_capabilities((), registry))
            for end in range(len(payload)):
                with self.subTest(truncated=end), self.assertRaises(ValueError):
                    decode_runtime_feature_registry(payload[:end])
            with self.assertRaises(ValueError):
                decode_runtime_feature_registry(payload+b"x")
        self.assertIn(NATIVE_TIMING_RUNTIME_CAPABILITY, DERIVED_RUNTIME_CAPABILITIES)
        self.assertNotIn(NATIVE_TIMING_RUNTIME_CAPABILITY, derive_feature_runtime_capabilities(
            (NATIVE_TIMING_RUNTIME_CAPABILITY,), normalize_runtime_features()))
        for flag in (0, 1, 2, 3, 8, 0xffffffff):
            with self.assertRaises(ValueError):
                decode_runtime_feature_registry(struct.pack("<4s6I", b"MMFR", 3, 0, 0, flag, 0, 0))
        for ids in (("x",), ("Za01", "Za01"), ("\0abc",), ("Ωabc",), ("Za01",)*1025):
            with self.assertRaises(ValueError):
                normalize_runtime_features((NativeTimingFeature(ids),))
        head = struct.pack("<4s5I", b"MMFR", 3, 0, 0, 4, 2)
        for body in (b"Za02Za01", b"Za01Za01"):
            with self.assertRaises(ValueError):
                decode_runtime_feature_registry(head+body+struct.pack("<I",0))

    def test_proves_owned_resource_kind_and_native_spell_timeout(self):
        feature = NativeTimingFeature(("Za01",), ("Ze01",))
        xml = ('<Majesty><Description type="Action" subType="Standard" ID="Za01" Name="ExampleSpell">'
               '<Game><Flags value="IsSpell"/><TimeoutDuration value="2000"/></Game></Description>'
               '<Description type="Unit" subType="Overlay" ID="Ze01" Name="ExampleEffect"/></Majesty>')
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "description.xml"
            path.write_text(xml)
            inventory = _feature_inventory("timing", root, path, (feature,))
            self.assertEqual(resolve_runtime_feature_registry((inventory,)).native_timing, feature)
            for source in (xml.replace("IsSpell", ""), xml.replace("2000", "-1"),
                           xml.replace("2000", "2147483648"), xml.replace("Overlay", "Building"),
                           xml.replace("Za01", "Za02"), xml.replace('Name="ExampleSpell"', 'Name=""'),
                           xml.replace('</Game>', '<TimeoutDuration value="1"/></Game>'),
                           xml.replace('</Majesty>', '<Description type="Action" subType="Standard" ID="Za02" Name="examplespell"/></Majesty>')):
                path.write_text(source)
                with self.subTest(source=source), self.assertRaises(ComposeError):
                    resolve_runtime_feature_registry((inventory,))
            path.write_text(xml)
            other = _feature_inventory("other", root, path, (feature,))
            with self.assertRaisesRegex(ComposeError, "claimed by both"):
                resolve_runtime_feature_registry((inventory,other))
