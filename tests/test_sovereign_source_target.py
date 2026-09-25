from dataclasses import asdict, replace
from pathlib import Path
import struct
import unittest

from majesty_cam.stock_controller_features import (
    StockAp69SovereignTargetAction, StockAp69SourceTargetAction,
    legacy_alchemist_controller_features, parse_controller_feature,
    controller_feature_mapping, ControllerFeatureError,
)
from majesty_cam.stock_controller_registry import (
    resolve_stock_controller_registry, encode_stock_controller_registry,
    decode_stock_controller_registry, ControllerRegistryError,
)
from majesty_cam.compose import _require_source_target_callback_signature, ComposeError


class SourceTargetTests(unittest.TestCase):
    def fixture(self):
        features = legacy_alchemist_controller_features('PrivateBuilding')
        old = next(f for f in features if isinstance(f, StockAp69SovereignTargetAction))
        fields = asdict(old)
        fields.pop('type')
        new = StockAp69SourceTargetAction(**fields, callback_symbol='Private_Exact_Action')
        return tuple(new if f is old else f for f in features), new

    def test_v20_roundtrip_and_explicit_opt_in(self):
        features, new = self.fixture()
        self.assertEqual(parse_controller_feature(controller_feature_mapping(new)), new)
        registry = resolve_stock_controller_registry(features, {'brewing': (0x31425041, 0x32425041)})
        data = encode_stock_controller_registry(registry)
        self.assertEqual(struct.unpack_from('<I', data, 4)[0], 20)
        self.assertEqual(decode_stock_controller_registry(data), registry)
        for end in range(len(data)):
            with self.assertRaises(ControllerRegistryError):
                decode_stock_controller_registry(data[:end])
        legacy = resolve_stock_controller_registry(legacy_alchemist_controller_features('PrivateBuilding'),
                                                   {'brewing': (0x31425041, 0x32425041)})
        self.assertEqual(struct.unpack_from('<I', encode_stock_controller_registry(legacy), 4)[0], 2)
        with self.assertRaises(ControllerFeatureError):
            parse_controller_feature(controller_feature_mapping(replace(new, callback_symbol='')))

    def test_requires_three_agents_and_no_return(self):
        good = 'function Exact(agent Spell, agent Source, agent Target)\ndeclare\nbegin\nend'
        _require_source_target_callback_signature(good, 'Exact')
        for bad in (good.replace(', agent Target', ''), good.replace('agent Source', 'integer Source'),
                    good.replace(')\n', ') is boolean\n')):
            with self.assertRaises(ComposeError):
                _require_source_target_callback_signature(bad, 'Exact')

    def test_audited_stock_transport_boundaries(self):
        import pefile
        root = Path(__file__).resolve().parents[2] / 'majesty-gold-hd-mod-manager-gog-support/local/fixtures'
        profiles = (
            ('public', 0xDA020, 0x3C544C, 0x1A15F0, 0xDA093, 0xDAD8A, 0x1C5B20),
            ('beta2', 0xDA630, 0x3E3FD4, 0x1B65A0, 0xDA6A3, 0xDB39A, 0x1DAD00),
            ('gog-pristine', 0xDAD70, 0x3E426C, 0x1B58F0, 0xDADE3, 0xDBADA, 0x1DA050),
        )
        for name, entry, world, lookup, lookup_call, birth_call, birth in profiles:
            path = root / name / 'MajestyHD.exe'
            if not path.is_file():
                self.skipTest('local stock executable fixtures unavailable')
            pe = pefile.PE(str(path))
            image = pe.get_memory_mapped_image()
            base = pe.OPTIONAL_HEADER.ImageBase
            self.assertEqual(image[entry+0x34:entry+0x3C], b'\xA1' + struct.pack('<I',base+world) + b'\x8B\x68\x04')
            for call, target in ((lookup_call,lookup), (birth_call,birth)):
                self.assertEqual(image[call], 0xE8)
                self.assertEqual(call + 5 + struct.unpack_from('<i',image,call+1)[0], target)
            self.assertEqual(image[birth_call-8:birth_call], bytes.fromhex('57 56 8D 88 90 00 00 00'))


if __name__ == '__main__':
    unittest.main()
