from dataclasses import replace
import struct
import unittest
from majesty_cam.cam import CamEntry
from majesty_cam.placement_art import validate_image


def image():
    # Minimal eight-direction ordinary actor family, including frame-group tag.
    direction = struct.pack('<hhHHIIHHI', 0, 0, 1, 1, 0, 0, 0, 1, 0) + bytes(8)
    record = bytearray(0x60)
    struct.pack_into('<I', record, 0, 8)
    struct.pack_into('<I', record, 12, 0x10100)
    for i in range(8):struct.pack_into('<I', record, 0x40+4*i, 0x60+len(direction)*i)
    record.extend(direction*8)
    header = struct.pack('<5I', 4, 0, 0, 0, 0) + struct.pack('<I', 3)
    offset = len(header)+24
    table = b''.join(struct.pack('<II', key, offset+len(record)*i) for i,key in enumerate((8,65,66)))
    return CamEntry(name=b'PRIV'+bytes(16), data=header+table+bytes(record)*3)


class PlacementArtTests(unittest.TestCase):
    def test_ordinary_private_frames_and_reject_extra_metadata(self):
        entry=image();validate_image(entry)
        for offset,value in ((48+0x10,1),(48+0x2C,1),(48+0x60+12,4),
                             (48+0x60+16,1),(48+0x60+28,0x18000000)):
            data=bytearray(entry.data);struct.pack_into('<I',data,offset,value)
            with self.assertRaises(ValueError):validate_image(replace(entry,data=bytes(data)))
        with self.assertRaises(ValueError):validate_image(replace(entry,data=entry.data[:-1]))
