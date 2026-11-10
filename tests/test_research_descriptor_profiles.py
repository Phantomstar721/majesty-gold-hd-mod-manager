"""Read-only checks against executable files; never runs Majesty."""
import os
from pathlib import Path
import struct
import unittest
from test_occupant_runtime_profiles import PeImage


NAMES = ("ResearchWeaponLevel_2", "ResearchArmorLevel_2", "ResearchWeaponLevel_3",
         "ResearchArmorLevel_3", "ResearchWeaponLevel_4", "ResearchArmorLevel_4")


class ResearchDescriptorProfileTests(unittest.TestCase):
    def verify(self, variable, timestamp, first, constructor):
        path = os.environ.get(variable)
        if not path: self.skipTest(variable + " not supplied")
        image = PeImage(path)
        self.assertEqual(image.timestamp, timestamp)
        # Six independently inspected registration call sites, not a runtime scan.
        offsets = (0, 0x69, 0xD1, 0x138, 0x19F, 0x206)
        rows = [(NAMES[n], offset, 5000+n, 195+n, 0x18+n, 1+n//2) for n,offset in enumerate(offsets)]
        rows += [('ResearchTournament',0x26D,5010,201,0x1E,1),
                 ('ResearchArrows',0x2D4,5020,202,0x2A,1),
                 ('ResearchGoodGuard',0x33B,5021,203,0x2B,2)]
        for name_text, offset, command, label, high, level in rows:
            with self.subTest(name=name_text):
                attribute = 0x00425041 + (high << 24)
                prefix = (b"\x68" + struct.pack("<I",command) + b"\x68" +
                          struct.pack("<I",label) + b"\x68" +
                          struct.pack("<I",attribute) + b"\x6a" + bytes([level]))
                self.assertEqual(image.read(first+offset,17),prefix)
                self.assertEqual(image.target(first+offset+27),constructor)
                # Bind the numeric FourCC to its actual GPL ATTRIB name.
                name = ("ATTRIB_" + name_text).encode() + b"\0"
                position = image.data.find(name)
                self.assertGreaterEqual(position,0)
                self.assertEqual(image.data.find(name,position+1),-1)
                name_rva = next(rva+position-raw for _,rva,size,raw in image.sections
                                if raw <= position < raw+size)
                reference = struct.pack("<I", image.base+name_rva)
                refs, position = [], 0
                while True:
                    position = image.data.find(reference, position)
                    if position < 0: break
                    refs.append(position)
                    position += 4
                self.assertEqual(len(refs),1)
                self.assertEqual(image.data[refs[0]-1],0x68)
                self.assertEqual(image.data[refs[0]+21:refs[0]+27],
                                 bytes((0x6a,high,0x6a,0x42,0x6a,0x50)))
                self.assertIn(b"\x6a\x41",image.data[refs[0]+27:refs[0]+35])
        # Constructor writes its fourth argument (attribute) into word 4.
        self.assertEqual(image.read(constructor+0xD4,28),bytes.fromhex(
            "8b4c242c8b5424308948048b4c2434891889780889501089480c8bf0"))

    def test_public(self): self.verify("MAJESTY_PUBLIC_EXE",0x5897B72F,0xA7C6C,0xA7AF0)
    def test_beta2(self): self.verify("MAJESTY_BETA2_EXE",0x5A8A11D5,0xA855C,0xA83E0)
    def test_gog(self): self.verify("MAJESTY_GOG_EXE",0x5BBB8DB8,0xA8B0C,0xA8990)

    def verify_empty_recruit(self, variable, control, produced, quote, submit):
        path = os.environ.get(variable)
        if not path: self.skipTest(variable + " not supplied")
        image = PeImage(path)
        # Normal AP10 recruit click calls quote, then the stock submit helper.
        self.assertEqual(image.target(control+0x10C), quote)
        self.assertEqual(image.target(control+0x135), submit)
        self.assertEqual(image.target(submit+0x36), produced)
        # Empty Produces iterator is the end sentinel: return ID zero without
        # dereferencing a nonexistent production record.
        self.assertEqual(image.read(produced+0x4A,4),bytes.fromhex("3bdd741c"))
        self.assertEqual(image.read(produced+0x6A,10),bytes.fromhex("5f5e5d33c05b83c408c3"))
        # Quote initializes its output to zero and has the same end check.
        self.assertEqual(image.read(quote+0xB,6),bytes.fromhex("c70000000000"))
        self.assertEqual(image.read(quote+0x55,4),bytes.fromhex("3bdd7443"))
        self.assertEqual(image.read(quote+0x9C,10),bytes.fromhex("5f5e5d33c05b83c408c2"))
        # A zero produced ID skips command allocation/submission to epilogue.
        self.assertEqual(image.read(submit+0x3B,15),bytes.fromhex("8be833f683c4083bee0f84a6000000"))

    def test_empty_recruit_public(self):
        self.verify_empty_recruit("MAJESTY_PUBLIC_EXE",0x968B0,0x95D50,0x96080,0x967A0)

    def test_empty_recruit_beta2(self):
        self.verify_empty_recruit("MAJESTY_BETA2_EXE",0x970C0,0x96560,0x96890,0x96FB0)

    def test_empty_recruit_gog(self):
        self.verify_empty_recruit("MAJESTY_GOG_EXE",0x97670,0x96B10,0x96E40,0x97560)

    def test_research_busy_controls_and_cancellation_profiles(self):
        for variable, table, activity, completion in (
            ("MAJESTY_PUBLIC_EXE", 0x33D184, 0x962E0, 0xDFE20),
            ("MAJESTY_BETA2_EXE", 0x355E5C, 0x96AF0, 0xE0430),
            ("MAJESTY_GOG_EXE", 0x354F94, 0x970A0, 0xE0B70),
        ):
            with self.subTest(profile=variable):
                path = os.environ.get(variable)
                if not path:
                    self.skipTest(variable + " not supplied")
                image = PeImage(path)
                self.assertEqual(struct.unpack("<I", image.read(table + 13*4, 4))[0],
                                 image.base + activity)
                # AP10 uses the same recruit/price/progress/caption control IDs.
                for offset, control in ((0x4C, 0x1F48), (0x5C, 0x1F51),
                                        (0x6C, 0x1F56), (0x7C, 0x1F57)):
                    self.assertEqual(image.read(activity+offset, 5),
                                     b"\x68" + struct.pack("<I", control))
                # Entire reason != 2 branch bypasses descriptor lookup/effects.
                self.assertEqual(image.read(completion+0x27, 11),
                                 bytes.fromhex("837c2450020f8504020000"))
                # Both reason branches converge on this exact EAX=0 epilogue.
                # Event completion/removal consumes the whole return word.
                epilogue = bytes.fromhex(
                    "33c08b4c243064890d00000000595f5e5d5b83c428c3")
                self.assertEqual(image.read(completion+0x236, len(epilogue)), epilogue)


if __name__ == "__main__": unittest.main()
