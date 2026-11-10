import json
import os
from pathlib import Path
import struct
import unittest
from majesty_cam.manager.alpha_ui import rewrite,names
from majesty_cam.manager.qol_service import detect_majesty_branch
from majesty_cam.engine_module import rva_offset

ROOT=Path(__file__).resolve().parents[1]


class AlphaUIProfiles(unittest.TestCase):
    def test_two_stock_format_callers_and_private_filename_on_all_builds(self):
        contract=json.loads((ROOT/'profiles/panel-engine/alpha-ui-layouts.json').read_bytes())
        for key in ('public','beta2','gog'):
            path=Path(os.environ['MAJESTY_'+key.upper()+'_EXE']);raw=path.read_bytes()
            profile=contract['profiles'][key];branch=detect_majesty_branch(path)
            changed,was_private=rewrite(raw,ROOT,branch,private=True)
            self.assertFalse(was_private)
            restored,was_private=rewrite(changed,ROOT,branch,private=False)
            self.assertTrue(was_private);self.assertEqual(restored,raw)
            self.assertEqual(len(profile['callFrames']),2)
            for frame in profile['callFrames']:
                data=bytes.fromhex(frame['bytes'])
                self.assertEqual(data[2:7],bytes.fromhex('8d44241c68'))
                self.assertEqual(struct.unpack_from('<I',data,7)[0],0x400000+profile['literalRva'])
                self.assertEqual(data[11:13],bytes.fromhex('50e8'))
            broken=bytearray(raw);at=rva_offset(broken,profile['callFrames'][0]['rva']);broken[at]^=1
            with self.assertRaises(ValueError):rewrite(broken,ROOT,branch,private=True)
        self.assertEqual(names('UIData_1920_1080.dat'),'UIAlfa_1920_1080.dat')
        with self.assertRaises(ValueError):names('../foreign.dat')
