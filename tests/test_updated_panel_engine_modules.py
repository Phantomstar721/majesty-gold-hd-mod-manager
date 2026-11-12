"""Updated native patch upgrades use executable fixtures and disposable bytes only."""
import json
import os
from pathlib import Path
import shutil
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
import sys

from majesty_cam import engine_module
from majesty_cam.manager.engine_patches import load_bundle, _install_revision
from majesty_cam.manager.qol_service import SUPPORTED_BRANCHES

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))


class UpdatedModules(unittest.TestCase):
    def test_original_map_action_binary_is_unchanged_inside_multipart_module(self):
        for branch in ('public','beta2','gog'):
            root=ROOT/'local/panel-engine-alpha/updated-native-modules'
            old_meta,old=engine_module.decode_bundle((root/('history/script-functions-'+branch+'-r1.mmne')).read_bytes())
            new_meta,new=engine_module.decode_bundle((root/('script-functions-'+branch+'.mmne')).read_bytes())
            self.assertEqual(new[:len(old)],old)
            self.assertEqual(old_meta['base'],new_meta['base'])

    def test_payload_copy_excludes_source_objects_and_private_receipts(self):
        from copy_engine_runtime_bundle import copy_runtime
        source=ROOT/'local/panel-engine-alpha/updated-native-modules'
        with TemporaryDirectory() as folder:
            target=Path(folder)/'modules'
            files=copy_runtime(source,target)
            self.assertEqual(set(files),{'modules.json',*[str(p.relative_to(target)).replace('\\','/')
                for p in target.rglob('*.mmne')]})
            self.assertFalse(list(target.rglob('*.cpp')))
            self.assertFalse(list(target.rglob('*.obj')))
            self.assertFalse((target/'source-bindings.json').exists())
            self.assertTrue((target/'history/window-engine-public-r2.mmne').is_file())

    def test_accepted_owner_handoff_survives_the_actual_updated_sdk(self):
        from verify_panel_engine_owner_fixture import verify
        from updated_panel_engine_sources import SDK_ROOT
        boundary=Path(os.environ.get('MMM_REGRESSION_TEMP',ROOT/'local/panel-engine-alpha'))
        result=verify(SDK_ROOT/'src/we_engine.cpp',boundary/'updated-owner-fixture',handoff=True,updated=True)
        self.assertTrue(result['handlerHandoff'] and result['updatedProtocol'])

    def test_real_both_order_upgrades_preserve_optional_peer_all_builds(self):
        source=ROOT/'local/panel-engine-alpha/updated-native-modules'
        with TemporaryDirectory() as folder:
            root=Path(folder)
            shutil.copytree(source,root/'local/panel-engine-alpha/native-modules')
            for branch in ('public','beta2','gog'):
                profile=next(b for b in SUPPORTED_BRANCHES if ('gog' if b.key.startswith('gog') else b.key)==branch)
                original=Path(os.environ['MAJESTY_'+branch.upper()+'_EXE']).read_bytes()
                for old_window in (1,2):
                    for order in (('panel-engine','scripted-ground-actions'),('scripted-ground-actions','panel-engine')):
                        with self.subTest(branch=branch,old=old_window,order=order):
                            data=original
                            for key,revision in (('panel-engine',old_window),('scripted-ground-actions',1)):
                                old,_=load_bundle(root,key,profile,revision=revision)
                                data=engine_module.install(data,old,branch)
                            first=order[0]; payload,_=load_bundle(root,first,profile)
                            data=_install_revision(root,data,first,profile,payload,branch)
                            peer='window-engine' if first=='scripted-ground-actions' else 'script-functions'
                            self.assertEqual(engine_module.inspect(data,peer,branch)['revision'],old_window if peer=='window-engine' else 1)
                            payload,_=load_bundle(root,order[1],profile)
                            data=_install_revision(root,data,order[1],profile,payload,branch)
                            self.assertEqual(engine_module.inspect(data,'window-engine',branch)['revision'],3)
                            script=engine_module.inspect(data,'script-functions',branch)
                            self.assertEqual(script['revision'],2)
                            self.assertEqual(script['bindHandoff'],0)
                            for key in order:
                                service='window-engine' if key=='panel-engine' else 'script-functions'
                                other='script-functions' if service=='window-engine' else 'window-engine'
                                self.assertEqual(engine_module.remove(engine_module.remove(data,service,branch),other,branch),original)

    def test_history_identity_is_checked_before_reconstructing_a_peer(self):
        from types import SimpleNamespace
        with TemporaryDirectory() as folder:
            root=Path(folder); bundle_root=root/'local/panel-engine-alpha/native-modules'
            shutil.copytree(ROOT/'local/panel-engine-alpha/updated-native-modules',bundle_root)
            index=json.loads((bundle_root/'modules.json').read_bytes())
            index['history']['script-functions-public-r1']['file']='../outside.mmne'
            (bundle_root/'modules.json').write_text(json.dumps(index))
            with self.assertRaisesRegex(ValueError,'identity'):
                load_bundle(root,'scripted-ground-actions',SimpleNamespace(key='public'),revision=1)
