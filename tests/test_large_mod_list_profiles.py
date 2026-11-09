"""The enlarged restore arena preserves the bundled stock restore implementation."""
import base64,os,re,struct
from pathlib import Path
import unittest
from test_occupant_runtime_profiles import PeImage

class LargeModListProfiles(unittest.TestCase):
    def test_profiles_and_complete_payload_match_bundled_helper(self):
        root=Path(__file__).parents[1]
        script=(root/"payload/qol/remember-active-mods/Install-ModPersistence.ps1").read_text()
        profiles=(root/"payload/qol/remember-active-mods/MajestyBuildProfiles.ps1").read_text()
        header=(root/"runtime/LargeModList.h").read_text()
        blob=base64.b64decode(re.search(r'\$loadRestoreBlob = .*?FromBase64String\("([^"]+)"',script)[1])
        expected=blob[:-2]+bytes.fromhex("b800000000ffd061c3")
        array=bytes(int(v,16) for v in re.search(r'payload\[\] = \{([^}]+)',header)[1].split(','))
        self.assertEqual(expected,array)
        self.assertEqual(array[47:52],bytes.fromhex("68ff030000"))
        names=['ModsOkHandlerVa','ActiveListInsertVa','ActiveListCommitVa','ApplyActiveModsVa',
               'FopenIat','FreadIat','FcloseIat','SscanfIat','InstalledListVa','ActiveListOwnerVa',
               'ActiveListVa','ActiveListDirtyVa']
        rows=re.findall(r'\{(0x[^}]+)\}',header[header.index('profiles[3]'):header.index('struct Move')])
        for index,name in enumerate(("PUBLIC","BETA2","GOG")):
            values=[int(v,16) for v in rows[index].split(',')]
            section=profiles.split('Id = ')[index+1]
            self.assertEqual(values,[int(re.search(n+r' = (0x[0-9A-Fa-f]+)',section)[1],16) for n in names])
            image=PeImage(os.environ["MAJESTY_"+name+"_EXE"])
            # Entry points are original game routines. The runtime preserves calls to them.
            for address in values[:4]:
                self.assertNotEqual(image.read(address-0x400000,8),bytes(8))
