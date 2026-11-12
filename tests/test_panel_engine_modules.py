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


class HandoffEngineModules(EngineModules):
    def test_dependency_snapshot_retains_actual_revision(self):
        from types import SimpleNamespace
        from majesty_cam.manager.engine_patches import snapshot_revisions
        from majesty_cam.engine_dependencies import RequirementEvidence, PatchRequirement, missing
        evidence=(RequirementEvidence(PatchRequirement('window-engine.v1',2),'id','test','Any','test'),)
        rows=[SimpleNamespace(key='panel-engine',installed=True,installed_revision=2)]
        self.assertFalse(missing(evidence,snapshot_revisions(rows)))
        rows[0].installed_revision=1
        self.assertTrue(missing(evidence,snapshot_revisions(rows)))

    def bundle(self,service,branch):
        if service=='window-engine':
            return (ROOT/'local/panel-engine-alpha/handoff-native-modules'/(service+'-'+branch+'.mmne')).read_bytes()
        return super().bundle(service,branch)

    def test_handoff_extension_and_transactional_legacy_upgrade(self):
        from unittest.mock import patch
        from majesty_cam.manager.engine_patches import _install_revision
        from majesty_cam.manager.qol_service import SUPPORTED_BRANCHES
        for branch,original in self.images.items():
            profile=next(b for b in SUPPORTED_BRANCHES if ('gog' if b.key.startswith('gog') else b.key)==branch)
            for order in (('window-engine','script-functions'),('script-functions','window-engine')):
                data=original
                for service in order:
                    old=(ROOT/'local/fixtures/panel-engine-revision1'/(service+'-'+branch+'.mmne')).read_bytes()
                    self.assertEqual(module.decode_bundle(old)[0]['revision'],1)
                    data=module.install(data,old,branch)
                def bundled(_,key,unused,*,revision=None):
                    service='window-engine' if key=='panel-engine' else 'script-functions'
                    if revision==1:
                        return (ROOT/'local/fixtures/panel-engine-revision1'/(service+'-'+branch+'.mmne')).read_bytes(),branch
                    return self.bundle(service,branch),branch
                with patch('majesty_cam.manager.engine_patches.load_bundle',side_effect=bundled):
                    changed=_install_revision(ROOT,data,'panel-engine',profile,self.bundle('window-engine',branch),branch)
                h=module.inspect(changed,'window-engine',branch)
                self.assertEqual(h['revision'],2)
                self.assertLess(h['bindHandoff'],len(h['blob']))
                self.assertTrue(module.inspect(changed,'script-functions',branch)['active'])
                self.assertEqual(original,module.remove(module.remove(changed,'window-engine',branch),'script-functions',branch))
                for offset in (160,164,168):
                    bad=bytearray(changed);bad[h['section'].raw_offset+offset]^=1
                    with self.assertRaises(module.EngineModuleError):module.inspect(bad,'window-engine',branch)


if __name__=='__main__':unittest.main()
