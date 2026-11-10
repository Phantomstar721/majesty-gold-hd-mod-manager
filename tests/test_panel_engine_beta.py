"""Beta integration uses disposable games; never prepares a Manager profile."""
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch
from majesty_cam import engine_module
from majesty_cam.manager.qol_service import QolService, PANEL_ENGINE_PATCHES, QOL_PATCHES
from majesty_cam.manager.engine_patches import installed_revisions

ROOT = Path(__file__).resolve().parents[1]


class BetaEngineIntegration(unittest.TestCase):
    def test_optional_services_keep_beta_paths_and_credit(self):
        from majesty_cam.manager.edition import output_directory_name, state_folder
        from majesty_cam.manager.paths import detect_manager_paths
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {'MAJESTY_MANAGER_EDITION': ''}):
            root = Path(folder)
            paths = detect_manager_paths(game_path=root/'game', documents_root=root/'documents', local_appdata=root/'appdata')
            self.assertEqual(output_directory_name(), 'Majesty Mod Manager - Merged')
            self.assertEqual(state_folder(), 'MajestyModManager')
            self.assertEqual(paths.launch_executable, paths.game_executable)
            self.assertNotIn('Alpha', str(paths.profile_path))
            service = QolService(repo_root=ROOT, game_executable=paths.game_executable)
            for spec in PANEL_ENGINE_PATCHES:
                self.assertIn(spec, service.specs)
                self.assertFalse(spec.required_by_manager)
                self.assertIn('Credit to mikmak300', spec.description)

    def test_real_install_restore_preserves_beta_helpers_all_versions(self):
        for branch in ('public', 'beta2', 'gog'):
            for order in (('panel-engine','scripted-ground-actions'), ('scripted-ground-actions','panel-engine')):
                with self.subTest(branch=branch, order=order), tempfile.TemporaryDirectory() as folder, \
                        patch.dict(os.environ, {'MAJESTY_MANAGER_EDITION': ''}):
                    root = Path(folder)
                    game = root/'game'; game.mkdir()
                    source = game/'MajestyHD.exe'
                    source.write_bytes(Path(os.environ['MAJESTY_'+branch.upper()+'_EXE']).read_bytes())
                    stock = Path(os.environ['MAJESTY_BCD_GOG_GAME' if branch=='gog' else 'MAJESTY_BCD_GAME'])
                    (game/'Data').mkdir()
                    for path in (stock/'Data').glob('UIData_*.dat'):
                        shutil.copyfile(path, game/'Data'/path.name)
                    backup = stock/'Data/_custom_quest_button_originals'
                    if backup.is_dir():
                        shutil.copytree(backup, game/'Data'/backup.name)
                    with patch('majesty_cam.manager.profile.default_profile_path', return_value=root/'state/profile.json'):
                        service = QolService(repo_root=ROOT, game_executable=source, prefs_path=root/'prefs',
                                             elevation_probe=lambda p: False)
                        def private_preferences(command):
                            command = list(command)
                            script = Path(command[command.index('-File')+1]).name.casefold()
                            if script in ('install-modpersistence.ps1', 'install-remembergamespeed.ps1',
                                          'install-remembercamerazoom.ps1'):
                                command.extend(('-PreferenceDirectory', str(root/'preferences')))
                            return service._run_command(command)
                        service._runner = private_preferences
                        for key in (spec.key for spec in QOL_PATCHES if not spec.preference_only):
                            status = service.inspect_patch(key)
                            self.assertTrue(status.applicable, status.detail)
                            if not status.installed:
                                service.apply(key, current=status)
                        before = source.read_bytes()
                        layouts = {p.name: p.read_bytes() for p in (game/'Data').glob('UIData_*.dat')}
                        for key in order:
                            self.assertTrue(service.apply(key).installed)
                            unchanged = source.read_bytes()
                            self.assertTrue(service.apply(key).installed)
                            self.assertEqual(source.read_bytes(), unchanged)
                        self.assertEqual(installed_revisions(ROOT, source),
                            {'window-engine.v1': 1, 'script-functions.map-action.v1': 1})
                        for key in order:
                            self.assertFalse(service.remove(key).installed)
                        self.assertEqual(source.read_bytes(), before)
                        self.assertEqual({p.name:p.read_bytes() for p in (game/'Data').glob('UIData_*.dat')}, layouts)
                        self.assertFalse((game/'MajestyHD.PanelEngineAlpha.exe').exists())
                        self.assertFalse(tuple((game/'Data').glob('UIAlfa_*.dat')))
                        self.assertFalse((root/'state/profile.json').exists())
                        self.assertFalse(tuple((root/'documents').rglob('*')))

    def test_publication_rejects_changed_or_locked_executable(self):
        import hashlib
        import subprocess
        from majesty_cam._subprocess import no_console_window_options
        script = ROOT/'payload/panel-engine/Publish-EngineExecutable.ps1'
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder); target=root/'MajestyHD.exe'; target.write_bytes(b'original')
            candidate=root/'candidate.exe'; candidate.write_bytes(b'candidate')
            command=['powershell.exe','-NoProfile','-File',str(script),'-Target',str(target),
                '-Candidate',str(candidate),'-CandidateHash',hashlib.sha256(candidate.read_bytes()).hexdigest(),
                '-PreviousHash',hashlib.sha256(b'not the current executable').hexdigest()]
            result=subprocess.run(command,capture_output=True,**no_console_window_options())
            self.assertNotEqual(result.returncode,0)
            self.assertEqual(target.read_bytes(),b'original')
            command[-1]=hashlib.sha256(target.read_bytes()).hexdigest()
            with target.open('rb'):
                # A deny-sharing handle is needed; ordinary Python reads permit replacement.
                import ctypes
                from ctypes import wintypes
                kernel=ctypes.WinDLL('kernel32',use_last_error=True)
                kernel.CreateFileW.argtypes=(wintypes.LPCWSTR,wintypes.DWORD,wintypes.DWORD,
                    wintypes.LPVOID,wintypes.DWORD,wintypes.DWORD,wintypes.HANDLE)
                kernel.CreateFileW.restype=wintypes.HANDLE
                handle=kernel.CreateFileW(str(target),0x80000000,1,None,3,0,None)
                self.assertNotEqual(handle,wintypes.HANDLE(-1).value)
                try:
                    result=subprocess.run(command,capture_output=True,**no_console_window_options())
                    self.assertNotEqual(result.returncode,0)
                    self.assertEqual(target.read_bytes(),b'original')
                finally:
                    kernel.CloseHandle.argtypes=(wintypes.HANDLE,)
                    kernel.CloseHandle(handle)


if __name__ == '__main__':
    unittest.main()
