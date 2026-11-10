"""Pure byte installation tests; never launch or modify an installed game."""
from pathlib import Path
import json
import os
import struct
import unittest
from majesty_cam import engine_module as module

ROOT=Path(__file__).resolve().parents[1]


class EngineModules(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bundles=ROOT/'local/panel-engine-alpha/native-modules'
        cls.images={b:Path(os.environ['MAJESTY_'+b.upper()+'_EXE']).read_bytes()
                    for b in module.BRANCH_IDS}

    def bundle(self,service,branch):
        return (self.bundles/(service+'-'+branch+'.mmne')).read_bytes()

    def test_all_builds_both_install_and_remove_orders(self):
        for branch,original in self.images.items():
            for first,second in (('window-engine','script-functions'),('script-functions','window-engine')):
                with self.subTest(branch=branch,first=first):
                    one=module.install(original,self.bundle(first,branch),branch)
                    both=module.install(one,self.bundle(second,branch),branch)
                    self.assertEqual(both,module.install(both,self.bundle(first,branch),branch))
                    self.assertEqual(original,module.remove(module.remove(both,first,branch),second,branch))
                    self.assertEqual(original,module.remove(module.remove(both,second,branch),first,branch))
                    inactive=module.remove(both,first,branch)
                    self.assertFalse(module.inspect(inactive,first,branch)['active'])
                    self.assertEqual(both,module.install(inactive,self.bundle(first,branch),branch))

    def test_wrong_build_and_changed_hook_rejected(self):
        for branch,original in self.images.items():
            wrong=next(b for b in self.images if b!=branch)
            with self.assertRaises(module.EngineModuleError):
                module.install(original,self.bundle('window-engine',wrong),branch)
            meta,_=module.decode_bundle(self.bundle('window-engine',branch))
            changed=bytearray(original)
            changed[module.rva_offset(changed,meta['hookRva'])]^=1
            with self.assertRaises(module.EngineModuleError):
                module.install(changed,self.bundle('window-engine',branch),branch)

    def test_descriptor_payload_and_hook_corruption_rejected(self):
        for branch,original in self.images.items():
            installed=module.install(original,self.bundle('window-engine',branch),branch)
            h=module.inspect(installed,'window-engine',branch)
            for at in (h['section'].raw_offset+100,h['section'].raw_offset+module.HEADER.size,
                       h['section'].raw_offset+256,module.rva_offset(installed,h['hook'])):
                with self.subTest(branch=branch,at=at):
                    changed=bytearray(installed);changed[at]^=1
                    with self.assertRaises(module.EngineModuleError):module.inspect(changed,'window-engine',branch)

    def test_unknown_section_and_corrupt_bundle_rejected(self):
        for branch,original in self.images.items():
            bundle=self.bundle('window-engine',branch)
            with self.assertRaises(module.EngineModuleError):module.decode_bundle(bundle[:-1])
            changed=bytearray(bundle);changed[-1]^=1
            with self.assertRaises(module.EngineModuleError):module.decode_bundle(changed)
            installed=bytearray(module.install(original,bundle,branch))
            s=module.inspect(installed,'window-engine',branch)['section']
            installed[s.raw_offset:s.raw_offset+8]=b'LEGACY01'
            with self.assertRaises(module.EngineModuleError):module.install(installed,bundle,branch)


if __name__=='__main__':unittest.main()
