"""Verify production constants, not a parallel profile, against all three images."""
import hashlib
import os
from pathlib import Path
import re
import struct
import unittest
from test_occupant_runtime_profiles import PeImage

ROOT=Path(__file__).resolve().parents[1]
FIXTURES=ROOT.parent/'majesty-gold-hd-mod-manager-gog-support/local/fixtures'


class MessageFlagProfileTests(unittest.TestCase):
    def test_three_production_profiles(self):
        source=(ROOT/'runtime/MessageFlagControls.inl').read_text()
        body=source.split('constexpr Profile profiles[] = {',1)[1].split('};',1)[0]
        numbers=[int(n,16) for n in re.findall(r'0x[0-9a-fA-F]+',body)]
        self.assertEqual(len(numbers),87)
        constructor_body=source.split('constexpr Construction constructions[] = {',1)[1].split('};',1)[0]
        constructor_numbers=[int(n,16) for n in re.findall(r'0x[0-9a-fA-F]+',constructor_body)]
        self.assertEqual(len(constructor_numbers),6)
        paths=(os.environ.get('MAJESTY_PUBLIC_EXE', 'C:/Program Files (x86)/Steam/steamapps/common/Majesty HD/MajestyHD.exe'),
               os.environ.get('MAJESTY_BETA2_EXE',str(FIXTURES/'beta2/MajestyHD.exe')),
               os.environ.get('MAJESTY_GOG_EXE',str(FIXTURES/'gog-pristine/MajestyHD.exe')))
        hashes=('255957fb09a4f8d5db6dde6d4127943dea965fa71c1da5db57951302b92e40b4',
                '05dbd67ae90b2cc14370dabcf3f9e4f9de5dd12c17f85730ac3d237fceec2f82',
                '65c6dd32c3d873c2e320bdaa2de1b00488af85b44573fd0fd82f79a2ffd37792')
        for index,path in enumerate(paths):
            with self.subTest(profile=index):
                image=PeImage(path)
                digest=hashlib.sha256(image.data).hexdigest()
                if index==0:
                    # Same audited Public image after the supported six-byte
                    # legacy suppression restore; no other bytes differ.
                    self.assertIn(digest,(hashes[index],
                        '1657fa3a3e16103c78708efc768cd69f7272cb2ade97cf659db20719e5579909'))
                else:
                    self.assertEqual(digest,hashes[index])
                p=numbers[index*29:(index+1)*29]
                def read(address,length):return image.read(address-image.base,length)
                for n,(field,length) in enumerate(((0,166),(8,0x97),(9,0x71),(10,0x78),(11,0x15D),(6,0x89))):
                    value=2166136261
                    for byte in read(p[field],length):value=((value^byte)*16777619)&0xFFFFFFFF
                    self.assertEqual(value,p[23+n],(index,field))
                self.assertEqual(struct.unpack('<9I',read(p[12],36)),tuple(p[14:23]))
                self.assertEqual(struct.unpack('<I',read(p[5]+0x30,4))[0],p[6])
                stock_table=(0x73A4FC,0x7535BC,0x752604)[index]
                for slot in (0x28,0x30):
                    self.assertEqual(read(stock_table+slot,4),read(p[5]+slot,4))
                self.assertIn(read(p[2],6),(bytes.fromhex('8B4C24105657'),bytes.fromhex('C39090909090')))
                self.assertEqual(read(p[2]+6,10),bytes.fromhex('8B7C240C6A006AFF83EC'))
                # Real quest menu construction calls this loader with four
                # arguments. The older MenuObject reader is not this path.
                caller=(0x4B3FCD,0x4B48BD,0x4B4EBD)[index]
                self.assertEqual(image.target(caller-image.base)+image.base,p[0])
                self.assertEqual(read(caller-0x22,7),bytes.fromhex('6A016A01576A00'))
                constructors=((0x646300,0x637EE0),(0x65B760,0x64D330),(0x65AC50,0x64C820))
                self.assertEqual(tuple(constructor_numbers[index*2:index*2+2]),constructors[index])
                for offset,target in ((0xB,constructors[index][0]),(0x64,constructors[index][1])):
                    self.assertEqual(image.target(p[0]+offset-image.base)+image.base,target)
                self.assertEqual(read(p[0]+0x97,3),bytes.fromhex('C21000'))

