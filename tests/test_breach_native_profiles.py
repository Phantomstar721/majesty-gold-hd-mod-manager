"""Read-only native evidence; does not enable a paid command or execute the game."""
import hashlib
import os
import struct
import unittest
from pathlib import Path

from test_occupant_runtime_profiles import PeImage


class BreachNativeProfileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = os.environ.get("MAJESTY_BETA2_EXE")
        if not path:
            raise unittest.SkipTest("MAJESTY_BETA2_EXE not supplied")
        cls.image = PeImage(path)
        # Same beta2 layout; retain every consumed-byte/call assertion below.
        from majesty_cam.manager.qol_service import detect_majesty_branch, BETA2_BRANCH
        branch = detect_majesty_branch(Path(path))
        if branch is None or branch.key != BETA2_BRANCH.key:
            raise AssertionError("unreviewed executable; do not transfer these VAs")

    def at(self, va, expected):
        expected = bytes.fromhex(expected)
        self.assertEqual(self.image.read(va-self.image.base, len(expected)), expected)

    def call(self, va, target):
        self.assertEqual(self.image.target(va-self.image.base)+self.image.base, target)

    def test_cursor_setup_is_not_the_target_filter(self):
        self.at(0x45F563, "c706e44a7500")
        self.at(0x754AE4+0x48, "30fb4500")
        self.call(0x45FB5A, 0x5B1F90)
        self.at(0x45FE55, "8b168b524889463c895e40895e388b470453508bceffd2")
        self.call(0x466CFD, 0x5B65A0)
        self.call(0x466D1A, 0x466390)
        self.at(0x4665F0, "81fe53703233740c")  # Sp23 -> creature branch
        self.call(0x46661A, 0x45D760)
        self.call(0x467025, 0x4DA580)

    def test_seven_word_record_has_fixed_serializer_and_restore(self):
        table = struct.unpack("<5I", self.image.read(0x757F90-self.image.base, 20))
        self.assertEqual(table, (0x4CBEE0, 0x4DA500, 0x4DA350, 0x4DA540, 0x4C9590))
        self.at(0x4DA4AD, "6a1cb9f1030000")
        self.at(0x4DA4D9, "c746281c000000")
        self.at(0x4C952B, "6a1cb8f1030000")
        self.at(0x4DA524, "8b711c8972148b4920894a185ec3")
        self.at(0x4DA563, "8b501489511c8b4018894120c20400")

    def test_fixed_tag_factory_and_real_restore_caller(self):
        self.at(0x4D7DAE, "8b44242c0517fcffffc744240c0100000083f80c")
        self.at(0x4D7DC2, "0f8780030000ff24855c814d00")
        self.at(0x4D815C+8*4, "e87f4d00")  # 03F1 - 03E9 = 8
        self.at(0x4D7FE8, "6a30")
        self.call(0x4D8004, 0x4C94F0)
        self.call(0x5ABBEA, 0x4D7D70)
        self.at(0x5ABC3D, "8b4c24108b118b520c8d44242450ffd2")
        self.call(0x4CA07A, 0x4DB510)
        self.call(0x4DB55C, 0x4DA630)

    def test_birth_precedes_gold_mutation_and_null_creation_reaches_it(self):
        self.at(0x4DA6D4, "0f8ce30d0000")
        self.at(0x4DB2F7, "85f60f84a9000000")
        self.call(0x4DB39A, 0x5DAD00)
        self.call(0x4DB3A0, 0x4DFCB0)
        self.at(0x4DB3A8, "8b7c24148bb424a00100008b178b42185668415050008bcfffd0")
        self.call(0x4DB3C9, 0x505370)


class BreachTransportParityEvidenceTests(unittest.TestCase):
    """Independent fixed addresses, never a runtime signature scanner."""
    PROFILES = (
        ('public', 'd21ba8312433e3e8f784b71943bdc38ddde7590e57abfb29ef347330cc77612d',
         0x4D9EF0, 0x4C8C10, 0x4C9300, 0x4D6BA0, 0x4DAF00, 0x4DA020,
         0x4ADB76, 0x46574A, 0x598650),
        ('beta2', '05dbd67ae90b2cc14370dabcf3f9e4f9de5dd12c17f85730ac3d237fceec2f82',
         0x4DA500, 0x4C9590, 0x4C9E50, 0x4D7D70, 0x4DB510, 0x4DA630,
         0x4AE466, 0x46677A, 0x5AB5D0),
        ('gog-pristine', '65c6dd32c3d873c2e320bdaa2de1b00488af85b44573fd0fd82f79a2ffd37792',
         0x4DAC40, 0x4C9BE0, 0x4CA4A0, 0x4D8460, 0x4DBC50, 0x4DAD70,
         0x4AEA16, 0x46669A, 0x5AC950),
    )

    def test_record_family_dispatch_restore_header_and_level_two_descriptor(self):
        fixtures = Path(__file__).resolve().parents[2] / 'majesty-gold-hd-mod-manager-gog-support/local/fixtures'
        for label, digest, serialize, tag, root, factory, dispatch, execute, descriptor, branch, header in self.PROFILES:
            path = fixtures / label / 'MajestyHD.exe'
            if not path.is_file():
                self.skipTest('three-profile read-only executable fixtures unavailable')
            with self.subTest(profile=label):
                image = PeImage(path)
                self.assertEqual(hashlib.sha256(image.data).hexdigest(), digest)
                def at(va, hex_bytes):
                    expected = bytes.fromhex(hex_bytes)
                    self.assertEqual(image.read(va-image.base, len(expected)), expected)
                def call(va, destination):
                    self.assertEqual(image.target(va-image.base)+image.base, destination)
                at(serialize, '8b5124568b710889328b710c8d4124897204')
                at(serialize+0x40, '8b4424048b008b108951088b500489510c')
                at(tag, 'b8f1030000c3')
                at(factory+0x3E, '8b44242c0517fcffffc744240c0100000083f80c')
                at(root+0x2B, '8b4c24208b018b5010ffd20fb7c00517fcffff')
                call(root+0x22A, dispatch)
                call(dispatch+0x4C, execute)
                at(dispatch+0x78, 'c20800')
                # Serialized header: buffer, byte length, u16 tag, borrowed flag.
                at(header, '8b44241c8b088b700483c008894c244089442424894c2428668974242c')
                at(descriptor, 'bd5370323985c07421c70041425500895804c7400c02000000')
                # Sp29 -> broad visible-unit branch; this alone is not lair proof.
                at(branch, '81fe537031390f847efeffff81fe537032390f85fe000000')

class PaidProductionGuardTests(unittest.TestCase):
    def test_every_production_guard_matches_all_three_independent_images(self):
        import re
        source=(Path(__file__).parents[1]/'runtime/PaidSourceTargetProfiles.h').read_text()
        root=Path(__file__).parents[2]/'majesty-gold-hd-mod-manager-gog-support/local/fixtures'
        for section,count in [('Windows',19),('OwnershipWindows',8)]:
            body=source.split('constexpr NativeWindow '+section)[1].split('};',1)[0]
            records=re.findall(r'\{0x([0-9A-F]+)u,\s*0x([0-9A-F]+)u,\s*0x([0-9A-F]+)u\}',body)
            self.assertEqual(len(records),count*3)
            profiles = (
                (0, 'public', Path(os.environ.get('MAJESTY_PUBLIC_EXE',
                    'C:/Program Files (x86)/Steam/steamapps/common/Majesty HD/MajestyHD.exe')),
                 '255957fb09a4f8d5db6dde6d4127943dea965fa71c1da5db57951302b92e40b4'),
                (1, 'beta2', Path(os.environ.get('MAJESTY_BETA2_EXE', str(root/'beta2/MajestyHD.exe'))),
                 '05dbd67ae90b2cc14370dabcf3f9e4f9de5dd12c17f85730ac3d237fceec2f82'),
                (2, 'gog', Path(os.environ.get('MAJESTY_GOG_EXE', str(root/'gog-pristine/MajestyHD.exe'))),
                 '65c6dd32c3d873c2e320bdaa2de1b00488af85b44573fd0fd82f79a2ffd37792'),
            )
            for index,name,path,digest in profiles:
                self.assertTrue(path.is_file(), 'required profile missing: '+str(path))
                image=PeImage(path)
                self.assertEqual(hashlib.sha256(image.data).hexdigest(), digest, name)
                for address,size,expected in records[index*count:(index+1)*count]:
                    h=2166136261
                    for byte in image.read(int(address,16),int(size,16)):h=((h^byte)*16777619)&0xffffffff
                    self.assertEqual(h,int(expected,16),(name,section,address))
