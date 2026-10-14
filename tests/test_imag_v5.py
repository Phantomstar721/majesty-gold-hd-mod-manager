"""Independent serialized v5 oracle: coordinates/pairs followed by events."""
import struct
import unittest

from majesty_cam.art import (parse_imag_tile_references,
    parse_stock_imag_tile_references, parse_best_imag_tile_references,
    rewrite_best_imag_entries, UnsupportedImagShapeError)
from majesty_cam.cam import CamEntry, pad_name


def fixture(*, timing=0, rectangles=0, auxiliary=0, events=1, padding=b''):
    data = bytearray(124)
    struct.pack_into('<I', data, 0, 5)
    struct.pack_into('<3I', data, 20, 1, 240, 32)
    struct.pack_into('<I', data, 32, 1)
    struct.pack_into('<I', data, 96, 68)
    struct.pack_into('<hhHHIIHHI', data, 100, 0, 0, 1, 21,
                     rectangles, auxiliary, timing, 1, events)
    data.extend(bytes(8 * bin(rectangles).count('1')))
    for _ in range(bin(auxiliary).count('1')):
        data.extend(struct.pack('<I', 2) + bytes(16))
    data.extend(struct.pack('<I', 0))  # group tag
    offsets = []
    for n in range(21):
        offsets.append(len(data) + 4)
        data.extend(struct.pack('<hhI', -n, n, 0x80000000 | (20269 + n % 2)))
    if timing:
        data.extend(struct.pack('<5I', 1, 0, 50, 0, 0))
    for _ in range(bin(events).count('1')):
        # Deliberately TILE-like event words must never become dependencies.
        data.extend(struct.pack('<9I', 1, 5, 0, 1, 50, 0, 926175832, 64, 0))
    data.extend(padding)
    return bytes(data), offsets


class ImagV5Tests(unittest.TestCase):
    def test_native_order_not_direction_end(self):
        for options in ({}, {'timing': 1}, {'events': 0},
                        {'rectangles': 7, 'auxiliary': 1},
                        {'events': 3, 'padding': b'unreferenced old body'}):
            data, offsets = fixture(**options)
            for parser in (parse_imag_tile_references, parse_stock_imag_tile_references,
                           parse_best_imag_tile_references):
                parsed = parser(data, tile_count=65535)
                self.assertEqual([r.offset for r in parsed.references], offsets)
                self.assertEqual([r.tile_index for r in parsed.references],
                                 [20269+n%2 for n in range(21)])

    def test_only_reference_words_change(self):
        data, offsets = fixture(timing=1, rectangles=7, auxiliary=1, events=3)
        output = rewrite_best_imag_entries((CamEntry(pad_name(b'GEN5'), data),),
            {20269:25000, 20270:25001}, tile_count=65535,
            preferred_tile_indices=(20269, 20270))
        expected = bytearray(data)
        for n, offset in enumerate(offsets):
            struct.pack_into('<I', expected, offset, 0x80000000 | (25000+n%2))
        self.assertEqual(output.entries[0].data, bytes(expected))

    def test_truncated_event_cannot_fall_back_to_coordinates(self):
        data, _ = fixture()
        for parser in (parse_imag_tile_references, parse_stock_imag_tile_references,
                       parse_best_imag_tile_references):
            with self.assertRaises(UnsupportedImagShapeError):
                parser(data[:-1], tile_count=65535)

    def test_unsupported_groups_and_reference_bits(self):
        data, offsets = fixture()
        for offset, fmt, value in ((118, '<H', 2), (offsets[0], '<I', 0x80010000)):
            bad = bytearray(data)
            struct.pack_into(fmt, bad, offset, value)
            with self.assertRaises(UnsupportedImagShapeError):
                parse_best_imag_tile_references(bytes(bad), tile_count=65535)
