"""Stock-resource integration checks for the isolated, unshipped art adapter."""
import copy
import json
import os
from pathlib import Path
import struct
import unittest

from majesty_cam.art import parse_stock_imag_tile_references
from majesty_cam.cam import read_cam
from majesty_cam.effect_sequence_art import bake_arrival


class EffectSequenceArtTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = os.environ.get('MAJESTY_SEQUENCE_STOCK_CAM')
        samples = os.environ.get('MAJESTY_SEQUENCE_SAMPLES')
        if not path or not samples:
            raise unittest.SkipTest('requires explicit stock CAM and exported C++ sequence samples')
        archive = read_cam(Path(path))
        imag = next(s for s in archive.sections if s.extension == b'IMAG')
        cls.tile_count = len(next(s for s in archive.sections if s.extension == b'TILE').entries)
        cls.projectile = next(e.data for e in imag.entries if e.name[:4] == b'WPg3')
        cls.impact = next(e.data for e in imag.entries if e.name[:4] == b'WRg2')
        cls.samples = json.loads(Path(samples).read_text(encoding='utf-8'))

    def bake(self, samples=None, projectile=None):
        return bake_arrival(self.projectile if projectile is None else projectile,
                            self.impact, self.samples if samples is None else samples,
                            tile_count=self.tile_count)

    def test_stream_major_frames_preserve_offsets_and_skip_absent_trails(self):
        output = self.bake()
        parsed = parse_stock_imag_tile_references(output, tile_count=self.tile_count)
        self.assertEqual(len(parsed.references), 81)
        self.assertEqual(len(output), 124 + 9 * 9 * 8)
        for frame, sample in enumerate(self.samples['frames']):
            for stream in range(9):
                x, y, word = struct.unpack_from('<hhI', output, 124 + (stream * 9 + frame) * 8)
                visible = stream == 0 or stream <= len(sample['trail'])
                self.assertEqual(bool(word & 0x40000000), not visible)
                if visible:
                    self.assertEqual([x, y], sample['xy'] if stream == 0 else sample['trail'][stream - 1])

    def test_malformed_samples_fail_before_resource_emission(self):
        mutations = [lambda s: s.update(schema=True),
                     lambda s: s.update(period=50),
                     lambda s: s['frames'].pop(),
                     lambda s: s['frames'][0].update(xy=[32768, 0]),
                     lambda s: s['frames'][5].update(trail=[[0, 0]]),
                     lambda s: s['frames'][5].update(xy=[1, 0]),
                     lambda s: s['frames'][8].update(phase=1)]
        for mutate in mutations:
            sample = copy.deepcopy(self.samples)
            mutate(sample)
            with self.subTest(sample=sample), self.assertRaises(ValueError):
                self.bake(samples=sample)

    def test_changed_stock_envelope_rejected(self):
        changed = bytearray(self.projectile)
        changed[108] = 1
        with self.assertRaises(ValueError):
            self.bake(projectile=bytes(changed))
