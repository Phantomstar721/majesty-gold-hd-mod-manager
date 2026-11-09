"""Exact-image RTTI admission tables; no gameplay or factory execution."""
import hashlib
import os
import re
import struct
import unittest
from pathlib import Path
from test_occupant_runtime_profiles import PeImage

class TravelCastProfilesTests(unittest.TestCase):
    def test_concrete_movement_tables_all_profiles(self):
        text=(Path(__file__).parents[1]/'runtime/TravelCastAdmission.h').read_text()
        for env,label,sha in (
            ('MAJESTY_PUBLIC_EXE','publicBuild','255957fb09a4f8d5db6dde6d4127943dea965fa71c1da5db57951302b92e40b4'),
            ('MAJESTY_BETA2_EXE','betaBuild','05dbd67ae90b2cc14370dabcf3f9e4f9de5dd12c17f85730ac3d237fceec2f82'),
            ('MAJESTY_GOG_EXE','gogBuild','65c6dd32c3d873c2e320bdaa2de1b00488af85b44573fd0fd82f79a2ffd37792')):
            self.assertTrue(os.environ.get(env),env+' required')
            path=Path(os.environ[env]);self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),sha)
            image=PeImage(path)
            def word(va):return struct.unpack('<I',image.read(va-image.base,4))[0]
            values=re.search(label+r'\{\{([^}]+)',text)[1]
            tables=[int(v,16) for v in values.split(',')]
            for table,name in zip(tables,('OrderMove','GS_OrderMove','OrderFollowPath','OrderFollowUnit','OrderMovePath')):
                locator=word(table-4)
                self.assertEqual(image.read(locator-image.base,12),bytes(12))
                descriptor=word(locator+12)
                expected=('.?AV'+name+'@@\0').encode()
                self.assertEqual(image.read(descriptor+8-image.base,len(expected)),expected)
            # The stock CastSpell success tail forwards the original arguments
            # to PerformAction; it inserts no separate StopMoving operation.
            tail={'publicBuild':(0x430420,0x5BEC30),
                  'betaBuild':(0x431380,0x5D3E10),
                  'gogBuild':(0x431250,0x5D3160)}[label]
            prefix=bytes.fromhex('8b5424588945108b44245452894d0c8b4c24545051')
            self.assertEqual(image.read(tail[0]-image.base,len(prefix)),prefix)
            self.assertEqual(image.target(tail[0]+len(prefix)-image.base)+image.base,tail[1])
    def test_production_uses_local_admission_not_global_settlement_scan(self):
        text=(Path(__file__).parents[1]/'runtime/CheckedPlacementRuntime.cpp').read_text()
        self.assertEqual(text.count('TravelCastReady(SharedMemory()'),2)
        self.assertEqual(text.count('SharedDecisionContext()'),2)
        self.assertNotIn('SharedIdle(',text)
        admission=(Path(__file__).parents[1]/'runtime/TravelCastAdmission.h').read_text()
        self.assertNotIn('life.Query',admission)
        self.assertNotIn('allUnits',admission)
