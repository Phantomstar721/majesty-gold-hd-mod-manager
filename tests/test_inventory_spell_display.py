from dataclasses import replace
import struct
import unittest

from majesty_cam.inventory_spell_display import hidden_action_names, derive_hidden_action_ids, CAPABILITY
from majesty_cam.descriptions import parse_descriptions
from majesty_cam.runtime_features import (RuntimeFeatureRegistry, encode_runtime_feature_registry,
    decode_runtime_feature_registry, derive_feature_runtime_capabilities)


class InventorySpellDisplayTests(unittest.TestCase):
    def test_only_unambiguous_hidden_calls(self):
        source = '''$LearnSpell(Actor, "Hidden", FALSE);
        $LearnSpell(Actor, "Visible"); $LearnSpell(Actor, "Mixed", FALSE);
        $LearnSpell(Actor, "Mixed", TRUE); $LearnSpell(Actor, "Computed", Policy);
        // $LearnSpell(Actor, "Fake", FALSE);
        Text = "$LearnSpell(Actor, NotLiteral, FALSE)";
        '''
        self.assertEqual(hidden_action_names(source), ("hidden",))
        for addition in ('$LearnSpell(Actor, Name, FALSE);', '$LearnSpell(Actor, "Hidden", Policy);',
                         'Callback = $LearnSpell;'):
            self.assertEqual(hidden_action_names(source + addition), ())

    def test_resolved_description_ids_not_potion_names(self):
        records = parse_descriptions(b'<Descriptions><Description type="Action" subType="Standard" ID="ZZ01" Name="Arbitrary Item"><Game><Flags value="IsSpell"/></Game></Description></Descriptions>').records
        self.assertEqual(derive_hidden_action_ids('$LearnSpell(A, "Arbitrary Item", FALSE);', records), ('ZZ01',))
        self.assertEqual(derive_hidden_action_ids('$LearnSpell(A, "Arbitrary Item", FALSE);', (*records, *records)), ())

    def test_wire_roundtrip_and_capability(self):
        registry = RuntimeFeatureRegistry(hidden_inventory_actions=('A020', 'A021'))
        payload = encode_runtime_feature_registry(registry)
        self.assertEqual(struct.unpack_from('<I', payload, 4)[0], 9)
        self.assertEqual(decode_runtime_feature_registry(payload), registry)
        self.assertIn(CAPABILITY, derive_feature_runtime_capabilities((), registry))
        self.assertNotIn(CAPABILITY, derive_feature_runtime_capabilities((CAPABILITY,), RuntimeFeatureRegistry()))
        for malformed in (payload[:-1], payload+b'x', payload[:20]+struct.pack('<I',1025)+payload[24:],
                          payload[:28]+payload[24:28]):
            with self.assertRaises(ValueError):
                decode_runtime_feature_registry(malformed)
        for ids in (('A021','A020'), ('A020','A020')):
            with self.assertRaises(ValueError):
                encode_runtime_feature_registry(replace(registry, hidden_inventory_actions=ids))
