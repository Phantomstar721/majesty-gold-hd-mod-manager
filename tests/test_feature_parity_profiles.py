"""Read-only checks of production profile constants against all three game PEs."""
import os
from pathlib import Path
import re
import struct
import unittest
from test_occupant_runtime_profiles import PeImage

ROOT = Path(__file__).parents[1]


class FeatureParityProfileTests(unittest.TestCase):
    def verify(self, variable, column):
        path = os.environ.get(variable)
        if not path:
            self.skipTest(variable + " is not set")
        image = PeImage(path)
        source = (ROOT / "runtime/FeatureParityProfiles.h").read_text()
        sites = {name: [int(a,16),int(b,16),int(c,16)][column]
                 for a,b,c,name in re.findall(r"\{(0x[0-9A-F]+), (0x[0-9A-F]+), (0x[0-9A-F]+)\}, // (\w+)",source)}
        ranges = re.findall(r"\{Feature::(\w+), Site::(\w+), (0x[0-9A-F]+), \{(0x[0-9A-F]+), (0x[0-9A-F]+), (0x[0-9A-F]+)\}\}",source)
        self.assertEqual({r[0] for r in ranges}, {"Equipment","HeroInfo","Movement","Research","ResearchVisual"})
        for group,name,size,*hashes in ranges:
            with self.subTest(feature=group,body=name):
                value = 2166136261
                for byte in image.read(sites[name],int(size,16)):
                    value = ((value ^ byte)*16777619)&0xFFFFFFFF
                self.assertEqual(value,int(hashes[column],16))
        def pointer(site,offset=0):
            return struct.unpack("<I",image.read(sites[site]+offset,4))[0]-image.base
        def call(site,offset,target):
            self.assertEqual(image.target(sites[site]+offset),sites[target],site)
        call("EnumCall",0,"EnumInit")
        call("EquipmentCall",0,"EquipmentCtor")
        call("EnumInit",0x37,"StringCtor")
        call("EnumInit",0x50,"EnumInsert")
        call("EnumInit",0x60,"StringDtor")
        self.assertEqual(pointer("EnumInit",0x25),sites["WeaponMap"])
        self.assertEqual(pointer("EnumInit",0x23A),sites["ArmorMap"])
        call("EquipmentCtor",0xAA,"NameInsert")
        call("EquipmentCtor",0xBA,"ResourceAcquire")
        call("EquipmentCtor",0x347,"IconInsert")
        for offset,target in ((0x33,"HeroSelected"),(0x216,"HeroAppend"),(0x221,"ImageCtor"),
                              (0x233,"ImageType"),(0x241,"ImageId"),(0x24B,"ImageSet"),
                              (0x255,"ImageFrame"),(0x264,"ImageFlags"),(0x28D,"ImageDtor")):
            call("HeroLearned",offset,target)
        self.assertEqual(image.read(sites["HeroLearned"]+0x47C,7),bytes.fromhex("8B7424188B4E24"))
        self.assertEqual(image.read(sites["HeroLearned"]+0xD9,9),bytes.fromhex("3858140F84B0010000"))
        call("HeroEffects",0x7EF,"ImageSet")
        call("HeroEffects",0x832,"ImageDtor")
        call("MoveExecute",0xCA,"MoveVector")
        self.assertEqual(image.read(sites["MoveExecute"]+0xB2,6),bytes.fromhex("8B0385C07E72"))
        self.assertEqual(pointer("ResearchSlot"),sites["ResearchExecute"])
        self.assertEqual(pointer("BuildingSetSlot"),sites["BuildingSet"])
        self.assertEqual(pointer("BuildingOwnerSlot"),sites["BuildingOwner"])
        self.assertEqual(pointer("BuildingOwnerSlot",0x160),sites["OrderGetter"])

    def test_beta2(self): self.verify("MAJESTY_BETA2_EXE",0)
    def test_public(self): self.verify("MAJESTY_PUBLIC_EXE",1)
    def test_gog(self): self.verify("MAJESTY_GOG_EXE",2)

    def test_all_derived_capabilities_have_version_parity(self):
        from majesty_cam.manager.capabilities import DERIVED_RUNTIME_CAPABILITIES
        from majesty_cam.manager.runtime_profiles import unsupported_runtime_capabilities
        from majesty_cam.manager.qol_service import PUBLIC_BRANCH,BETA2_BRANCH,GOG_BRANCH
        for branch in (PUBLIC_BRANCH,BETA2_BRANCH,GOG_BRANCH):
            self.assertEqual(unsupported_runtime_capabilities(branch,DERIVED_RUNTIME_CAPABILITIES),())
