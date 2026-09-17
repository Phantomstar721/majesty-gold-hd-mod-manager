from dataclasses import replace
from pathlib import Path
import struct
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from majesty_cam.runtime_features import (
    MovementQueryFeature, MapFogQueryFeature, normalize_runtime_features,
    encode_runtime_feature_registry, decode_runtime_feature_registry,
    derive_feature_runtime_capabilities, MOVEMENT_QUERY_RUNTIME_CAPABILITY,
)
from majesty_cam.package import ModDefinition, parse_mod_definition, mod_definition_mapping
from majesty_cam.manager.build import _canonical_mod_definition
from majesty_cam.manager.capabilities import DERIVED_RUNTIME_CAPABILITIES


class MovementQueryTests(unittest.TestCase):
    def test_explicit_deduplicated_feature_and_canonical_fingerprint(self):
        definition = ModDefinition(3, "00000000-0000-4000-8000-000000000001", "Travel", "Travel", (),
                                   runtime_features=(MovementQueryFeature(),))
        value = mod_definition_mapping(definition)
        self.assertEqual(value["runtime_features"], [{"type": MOVEMENT_QUERY_RUNTIME_CAPABILITY}])
        self.assertEqual(parse_mod_definition(value), definition)
        self.assertEqual(_canonical_mod_definition(definition), value)
        self.assertNotEqual(_canonical_mod_definition(replace(definition, runtime_features=())), value)
        value["runtime_features"][0]["unit_type"] = "Ranger"
        with self.assertRaises(ValueError):
            parse_mod_definition(value)

    def test_registry_flags_coexist_without_enabling_unrequested_services(self):
        for features, flags in (((MovementQueryFeature(),)*2, 2),
                                ((MapFogQueryFeature(), MovementQueryFeature()), 3)):
            registry = normalize_runtime_features(features)
            payload = encode_runtime_feature_registry(registry)
            self.assertEqual(payload, struct.pack("<4s4I", b"MMFR", 2, 0, 0, flags))
            self.assertEqual(decode_runtime_feature_registry(payload), registry)
            self.assertEqual(len(registry.features), 1 if flags == 2 else 2)
            self.assertIn(MOVEMENT_QUERY_RUNTIME_CAPABILITY, derive_feature_runtime_capabilities((), registry))
        self.assertIn(MOVEMENT_QUERY_RUNTIME_CAPABILITY, DERIVED_RUNTIME_CAPABILITIES)
        self.assertNotIn(MOVEMENT_QUERY_RUNTIME_CAPABILITY, derive_feature_runtime_capabilities(
            (MOVEMENT_QUERY_RUNTIME_CAPABILITY,), normalize_runtime_features()))
        for invalid in (4, 0xffffffff):
            with self.assertRaises(ValueError):
                decode_runtime_feature_registry(struct.pack("<4s4I", b"MMFR", 2, 0, 0, invalid))
