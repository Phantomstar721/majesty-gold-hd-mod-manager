from pathlib import Path
import struct
import sys
import unittest
sys.path.insert(0,str(Path(__file__).parents[1]/'src'))
from majesty_cam.art import (parse_imag_tile_references, parse_stock_imag_tile_references,
    parse_best_imag_tile_references, rewrite_best_imag_entries, UnsupportedImagShapeError)
from majesty_cam.cam import CamEntry, pad_name


def fixture():
    data=bytearray(200)
    struct.pack_into('<I',data,0,4)
    struct.pack_into('<3I',data,20,1,1015,32)
    struct.pack_into('<I',data,32,1)
    struct.pack_into('<I',data,96,68)
    struct.pack_into('<10H',data,100,0,0,1,7,0,0,0,0,1,1)
    for n in range(7):
        struct.pack_into('<hhI',data,124+n*8,-3,12,0x80000000 | (201 if n%2==0 else 342))
    struct.pack_into('<5I',data,180,1,0,0,0,0)
    return bytes(data)


class TimedImagTests(unittest.TestCase):
    def test_both_parsers_use_native_fields_not_timing(self):
        data=fixture()
        for parser in (parse_imag_tile_references,parse_stock_imag_tile_references,parse_best_imag_tile_references):
            result=parser(data,tile_count=900,entry_name=b'TIME')
            self.assertEqual([r.offset for r in result.references],list(range(128,177,8)))
            self.assertEqual([r.tile_index for r in result.references],[201,342,201,342,201,342,201])
    def test_actual_remapper_preserves_every_other_byte(self):
        original=fixture()
        result=rewrite_best_imag_entries((CamEntry(pad_name(b'TIME'),original),),
            {201:805,342:806},tile_count=900,preferred_tile_indices=(805,806))
        expected=bytearray(original)
        for n,offset in enumerate(range(128,177,8)):
            struct.pack_into('<I',expected,offset,0x80000000 | (805 if n%2==0 else 806))
        self.assertEqual(result.entries[0].data,bytes(expected))
        self.assertEqual(result.entries[0].data[180:],original[180:])
    def test_malformed_timed_bounds_cannot_fall_back(self):
        for parser in (parse_imag_tile_references,parse_stock_imag_tile_references,parse_best_imag_tile_references):
            with self.assertRaises(UnsupportedImagShapeError):parser(fixture()[:-4],tile_count=900)
    def test_reference_middle_byte_is_not_a_flag(self):
        data=bytearray(fixture());struct.pack_into('<I',data,128,0x800100C9)
        with self.assertRaises(UnsupportedImagShapeError):parse_best_imag_tile_references(bytes(data),tile_count=900)
    def test_mapped_rectangle_and_unsupported_group(self):
        data=bytearray(fixture());data[120:120]=bytes(8)
        struct.pack_into('<H',data,108,1)
        parsed=parse_best_imag_tile_references(bytes(data),tile_count=900)
        self.assertEqual([r.offset for r in parsed.references],list(range(136,185,8)))
        struct.pack_into('<H',data,118,2)
        with self.assertRaises(UnsupportedImagShapeError):parse_best_imag_tile_references(bytes(data),tile_count=900)
