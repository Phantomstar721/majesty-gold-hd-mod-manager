"""Offline order evidence, not a claim of actor destruction/live acceptance."""
from pathlib import Path
import sys
import os
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from inspect_delayed_building_order import inspect, PROFILES
from trace_dawnfall_lifecycle import Image


class DelayedOrderProfileTests(unittest.TestCase):
    def test_three_exact_images_and_shared_processor(self):
        normalized = []
        for name, path, digest in PROFILES:
            path=Path(os.environ.get('MAJESTY_'+name.upper()+'_EXE',str(path)))
            record = inspect(path, digest)
            classes = record['classes']
            method = classes['GS_ResearchOrder']['methods']['6']
            self.assertEqual(method, classes['GS_BaseDelayedOrder']['methods']['6'])
            data = bytearray(Image(path).read(int(method['address'], 16), method['size']))
            self.assertEqual(data[0x36:0x38], b'\x8b\x0d')
            data[0x38:0x3c] = bytes(4)  # sole simulation-clock address operand
            normalized.append(data)
            # The research wrappers contain no subclass field serialization;
            # their direct delegate is the corresponding base delayed wrapper.
            for slot in ('1', '2'):
                delegate = classes['GS_BaseDelayedOrder']['methods'][slot]['address']
                self.assertTrue(any(line.endswith('call ' + delegate)
                    for line in classes['GS_ResearchOrder']['methods'][slot]['listing']))
        self.assertEqual(normalized[0], normalized[1])
        self.assertEqual(normalized[0], normalized[2])

    def test_unsupported_identity_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Unsupported executable'):
            inspect(PROFILES[0][1], '0' * 64)


if __name__ == '__main__':
    unittest.main()
