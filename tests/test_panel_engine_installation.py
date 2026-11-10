"""Exercise real installers only on disposable three-build executable copies."""
import hashlib
import os
from pathlib import Path
import tempfile
import shutil
import unittest
from unittest.mock import patch
from majesty_cam.manager.qol_service import QolService, PANEL_ENGINE_PATCHES, QOL_PATCHES
from majesty_cam.manager.alpha_executable import target_for

ROOT=Path(__file__).resolve().parents[1]


class AlphaInstallation(unittest.TestCase):
    def test_independent_engines_and_canonical_helpers_preserve_original(self):
        for branch in ('public','beta2','gog'):
            with self.subTest(branch=branch), tempfile.TemporaryDirectory() as folder:
                root=Path(folder);source=root/'MajestyHD.exe'
                original=Path(os.environ['MAJESTY_'+branch.upper()+'_EXE']).read_bytes()
                source.write_bytes(original)
                with patch.dict(os.environ,{'MAJESTY_MANAGER_EDITION':'panel-engine-alpha'}), \
                     patch('majesty_cam.manager.profile.default_profile_path',return_value=root/'state/profile.json'):
                    service=QolService(repo_root=ROOT,game_executable=source,
                                       elevation_probe=lambda path:False)
                    self.assertFalse(target_for(source).exists())
                    for spec in PANEL_ENGINE_PATCHES:
                        self.assertFalse(service.inspect_patch(spec.key).installed)
                    self.assertFalse(target_for(source).exists())
                    for key in ('panel-engine','scripted-ground-actions'):
                        self.assertTrue(service.apply(key).installed)
                    for key in ('remember-mods','generic-visitors'):
                        status=service.inspect_patch(key)
                        if status.installed is not True:service.apply(key,current=status)
                        self.assertTrue(service.inspect_patch(key).installed)
                    self.assertTrue(service.remove('panel-engine').installed is False)
                    self.assertTrue(service.inspect_patch('scripted-ground-actions').installed)
                    self.assertTrue(service.apply('panel-engine').installed)
                    self.assertEqual(source.read_bytes(),original)
                    self.assertNotEqual(source,target_for(source))

    def test_resolution_qol_install_restore_and_original_data_isolation(self):
        from majesty_cam.manager.alpha_ui import names,rewrite
        from majesty_cam.manager.qol_service import detect_majesty_branch
        for branch in ('public','beta2','gog'):
            with self.subTest(branch=branch),tempfile.TemporaryDirectory() as folder:
                root=Path(folder);source=root/'MajestyHD.exe'
                original=Path(os.environ['MAJESTY_'+branch.upper()+'_EXE']).read_bytes()
                source.write_bytes(original)
                game=Path(os.environ['MAJESTY_BCD_GOG_GAME' if branch=='gog' else 'MAJESTY_BCD_GAME'])
                data=root/'Data';data.mkdir()
                for p in (game/'Data').glob('UIData_*.dat'):shutil.copyfile(p,data/p.name)
                backup=game/'Data/_custom_quest_button_originals'
                if backup.is_dir():shutil.copytree(backup,data/backup.name)
                before={p.name:p.read_bytes() for p in data.glob('UIData_*.dat')}
                self.assertTrue(before,'All three builds require actual resolution layouts')
                with patch.dict(os.environ,{'MAJESTY_MANAGER_EDITION':'panel-engine-alpha'}), \
                     patch('majesty_cam.manager.profile.default_profile_path',return_value=root/'state/profile.json'):
                    service=QolService(repo_root=ROOT,game_executable=source,elevation_probe=lambda p:False)
                    for key in ('quests-shortcut','lower-tracking','unlock-quests'):
                        status=service.inspect_patch(key)
                        self.assertTrue(status.applicable,status.detail)
                        if status.installed:service.remove(key)
                        service.apply(key)
                        self.assertTrue(service.inspect_patch(key).installed)
                    self.assertTrue(rewrite(target_for(source).read_bytes(),ROOT,detect_majesty_branch(source),private=True)[1])
                    for name in before:self.assertTrue((data/names(name)).is_file())
                    for key in ('panel-engine','scripted-ground-actions'):
                        self.assertTrue(service.apply(key).installed)
                    if branch=='public':
                        import ctypes
                        from ctypes import wintypes
                        from majesty_cam.manager.qol_service import QolServiceError
                        kernel=ctypes.WinDLL('kernel32',use_last_error=True)
                        kernel.CreateFileW.argtypes=(wintypes.LPCWSTR,wintypes.DWORD,wintypes.DWORD,
                            ctypes.c_void_p,wintypes.DWORD,wintypes.DWORD,wintypes.HANDLE)
                        kernel.CreateFileW.restype=wintypes.HANDLE
                        locked=data/names('UIData_1024_768.dat')
                        handle=kernel.CreateFileW(str(locked),0x80000000,1,None,3,0,None)
                        self.assertNotEqual(handle,ctypes.c_void_p(-1).value)
                        saved=target_for(source).read_bytes()
                        layouts={p.name:p.read_bytes() for p in data.glob('UIAlfa_*.dat')}
                        try:
                            with self.assertRaises(QolServiceError):service.remove('lower-tracking')
                            self.assertEqual(target_for(source).read_bytes(),saved)
                            self.assertEqual({p.name:p.read_bytes() for p in data.glob('UIAlfa_*.dat')},layouts)
                        finally:
                            kernel.CloseHandle.argtypes=(wintypes.HANDLE,)
                            kernel.CloseHandle(handle)
                    for key in ('unlock-quests','lower-tracking','quests-shortcut'):
                        self.assertFalse(service.remove(key).installed)
                    self.assertEqual(source.read_bytes(),original)
                    self.assertEqual({p.name:p.read_bytes() for p in data.glob('UIData_*.dat')},before)


if __name__=='__main__':unittest.main()
