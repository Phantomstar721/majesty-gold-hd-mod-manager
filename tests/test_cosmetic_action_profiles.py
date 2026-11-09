"""Three-build cancellation/normal-image bodies and concrete native call edges."""
import os
from pathlib import Path
import re
import struct
import unittest
from test_occupant_runtime_profiles import PeImage
from test_fade_persistence_profiles import fingerprint


class CosmeticActionProfilesTests(unittest.TestCase):
    def test_stock_single_part_animation_route(self):
        for env, processor in (('MAJESTY_PUBLIC_EXE',0x5F6E70),
                               ('MAJESTY_BETA2_EXE',0x60C1B0),('MAJESTY_GOG_EXE',0x60B500)):
            self.assertTrue(os.environ.get(env),env+' is required')
            image=PeImage(os.environ[env])
            # Record animation bit -> kind11, or first/index-zero ordinary
            # part with no earlier animation -> the identical kind11 branch.
            self.assertEqual(image.read(processor-image.base+0xA0,18),
                bytes.fromhex('8a400e2401754185ed7507807c2420007436'))
            self.assertEqual(image.read(processor-image.base+0xE8,17),
                bytes.fromhex('8b178b82880100006a0b8bcfc644242401'))

    def test_bodies_and_native_owner(self):
        text=(Path(__file__).parents[1]/'runtime/CosmeticActionProfiles.h').read_text()
        normalized=[]
        for env,name,unit,stack in (
            ('MAJESTY_PUBLIC_EXE','publicBuild',0x73A924,0x749C0C),
            ('MAJESTY_BETA2_EXE','betaBuild',0x7539E4,0x763CDC),
            ('MAJESTY_GOG_EXE','gogBuild',0x752A2C,0x762B9C),
        ):
            self.assertTrue(os.environ.get(env),env+' is required')
            im=PeImage(os.environ[env])
            def read(va,n):return im.read(va-im.base,n)
            def word(va):return struct.unpack('<I',read(va,4))[0]
            def target(va):return im.target(va-im.base)+im.base
            block=re.search(r'CosmeticActionProfile '+name+r'\{(.*?)\}\};',text,re.S)[1]
            values=[int(v,16) for v in re.findall(r'0x[0-9A-F]+',block)]
            self.assertEqual(len(values),10)
            addresses,hashes=values[:5],values[5:]
            references=(
                (0x20,0x51,0x61,0x8A,0xA0,0xB0,0xCA,0xED,0xF9,0x103,0x110,0x137,0x181,0x1A2),
                (0x3E,), (0x77,), (0xD,0x1D,0x46,0x4C,0x8F), (),
            )
            bodies=[]
            for va,n,digest,refs in zip(addresses,(0x1BF,0x4A,0x94,0xD1,0x44),hashes,references):
                body=bytearray(read(va,n));self.assertEqual(fingerprint(body),digest,(env,hex(va)))
                for offset in refs:body[offset:offset+4]=bytes(4)
                bodies.append(bytes(body))
            normalized.append(bodies)
            self.assertEqual(target(addresses[0]+0x1A1),addresses[1])
            self.assertEqual(target(addresses[1]+0x3D),addresses[2])
            self.assertEqual(target(addresses[0]+0x89),addresses[3])
            self.assertEqual(target(addresses[0]+0xC9),addresses[3])
            # Actual GS F8 refresh branch, and concrete OrderStack event1 slot.
            self.assertEqual(target(word(unit+0xF8)+0x13),addresses[0])
            self.assertEqual(word(stack+0x48),addresses[4])
            self.assertEqual(read(addresses[4],6),bytes.fromhex('568b74240857'))
            self.assertEqual(read(addresses[0]+0x1BE,1),b'\xc3') # cdecl, not thiscall
            block=re.search(r'CosmeticImageTypes '+name+r'\{(.*?)\};',text,re.S)[1]
            tables=[int(v,16) for v in re.findall(r'0x[0-9A-F]+',block)]
            self.assertEqual(len(tables),4)
            for table,type_name in zip(tables,('IsoUnitIMG','IsoUnitIMGPartEntry','ActionDesc_Std_Engine','OrderInitAction')):
                td=word(word(table-4)+12)
                expected=('.?AV'+type_name+'@@\0').encode()
                self.assertEqual(read(td+8,len(expected)),expected)
            getter=word(tables[0]+0x20)
            self.assertEqual(read(getter,13),bytes.fromhex('8b442404c1e00603411cc20400'))
            # Concrete selector stores the descriptor and full key at +4/+8.
            # This bounded witness does not certify the downstream art renderer.
            selector=word(tables[1]+0x3C)
            self.assertEqual(read(selector+0x22,0x1A),bytes.fromhex(
                '8bf18b4c241c8b0185c07403ff40148b44242050894e04894608'))
        self.assertEqual(normalized[0],normalized[1])
        self.assertEqual(normalized[0],normalized[2])
