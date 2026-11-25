from pathlib import Path
import hashlib
import importlib.util
import json
import os
import struct
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

from majesty_cam.cam import CamArchive, CamEntry, CamSection
from majesty_cam.engine_module import rva_offset
from majesty_cam.manager import window_qol as w
from majesty_cam.manager.qol_service import QolService, WINDOW_QOL_PATCHES, detect_majesty_branch

ROOT = Path(__file__).resolve().parents[1]


class WindowQolTests(unittest.TestCase):
    def test_per_install_settings_defaults_atomic_roundtrip_and_strict_values(self):
        with TemporaryDirectory() as temp:
            path = Path(temp) / 'settings/window-qol.json'
            first, second = Path(temp) / 'first.exe', Path(temp) / 'other.exe'
            self.assertFalse(any(w.options(first, path).values()))
            w.change(first, 'borderless-window', True, path)
            w.change(first, 'cursor-confinement', True, path)
            w.change(first, 'borderless-window', False, path)
            self.assertEqual(w.options(first, path), {'borderless-window': False, 'cursor-confinement': True})
            self.assertFalse(any(w.options(second, path).values()))
            self.assertEqual(list(path.parent.glob('*.tmp')), [])
            path.write_text('{"schema":1,"installs":[]}')
            with self.assertRaises(ValueError): w.options(first, path)
            with self.assertRaises(ValueError): w.change(first, 'other', True, path)

    def test_native_profile_generated_from_one_source(self):
        spec = importlib.util.spec_from_file_location('generate_window_qol', ROOT / 'scripts/generate_window_qol_profiles.py')
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        self.assertEqual((ROOT / 'runtime/WindowQoLProfiles.h').read_text(), module.render(ROOT))

    def test_all_three_real_executable_guards_and_modified_inputs(self):
        rows = json.loads((ROOT / 'profiles/window-qol.json').read_bytes())['profiles']
        # Mandatory fixtures: a release/development check cannot silently skip.
        for key, variable in (('public', 'MAJESTY_PUBLIC_EXE'), ('beta2', 'MAJESTY_BETA2_EXE'), ('gog', 'MAJESTY_GOG_EXE')):
            with self.subTest(build=key):
                self.assertTrue(os.environ.get(variable), variable + ' is required')
                file = Path(os.environ[variable]); raw = file.read_bytes()
                self.assertEqual(hashlib.sha256(raw).hexdigest(), rows[key]['sha256'])
                w.verify(file, ROOT, key)
                with TemporaryDirectory() as temp:
                    copy = Path(temp) / 'MajestyHD.exe'
                    for rva in (rows[key]['creationRva'], rows[key]['creationRva'] + 1079,
                                rows[key]['mainWindowGuardRva'], rows[key]['windowedPreferenceGuardRva'], rows[key]['gogClipRva']):
                        if not rva: continue
                        changed = bytearray(raw); changed[rva_offset(raw, rva)] ^= 1; copy.write_bytes(changed)
                        with self.assertRaises(ValueError): w.verify(copy, ROOT, key)
                    copy.write_bytes(raw)
                    other = 'beta2' if key == 'public' else 'public'
                    with self.assertRaises(ValueError): w.verify(copy, ROOT, other)
                self.assertEqual(file.read_bytes(), raw)
        with self.assertRaises(ValueError): w.verify(Path('missing'), ROOT, 'unknown')

    def test_binary_and_text_binding_conflict_and_missing_resource_fail_safe(self):
        with TemporaryDirectory() as temp:
            game = Path(temp); (game / 'Data').mkdir()
            cam = game / 'Data/textdata.cam'
            def write(body):
                cam.write_bytes(CamArchive((CamSection(b'SMNU', (CamEntry(b'KEYS' + b'\0'*16, body),)),)).to_bytes())
            write(b'ordinary binding')
            self.assertIsNone(w.binding_conflict(game))
            write(struct.pack('<I', 0xCE01A)); self.assertEqual(w.binding_conflict(game), cam)
            write(b'KEY_GERMAN = F11, SHIFT, CONTROL\r\n'); self.assertEqual(w.binding_conflict(game), cam)
            write(b'KEY_USA = F11 SHIFT\n'); self.assertIsNone(w.binding_conflict(game))
            manifest = game / 'test.mmxml'
            manifest.write_text('<Majesty><Mod><Load><CAM>../bad.cam</CAM></Load></Mod></Majesty>')
            with self.assertRaises(ValueError): w.binding_conflict(game, [manifest])
            cam.unlink()
            with self.assertRaises(ValueError): w.binding_conflict(game)

    def test_legacy_quest_loads_scan_both_stock_aliases(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            game, package = root / 'game', root / 'quest'
            for directory in (game / 'Data', game / 'DataMX', package):
                directory.mkdir(parents=True)

            def write_cam(path, body):
                path.write_bytes(CamArchive((CamSection(b'SMNU', (CamEntry(b'KEYS' + b'\0'*16, body),)),)).to_bytes())

            write_cam(game / 'Data/textdata.cam', b'No shortcuts')
            original = game / 'Data/quest.cam'
            expansion = game / 'DataMX/quest.cam'
            manifest = package / 'quest.mqxml'
            manifest.write_bytes(b'''<Majesty><Quest><Description>Rabbit\x92s Oak</Description>
                <Load><CAM>$(MajestyDataPath)/quest.cam</CAM>
                <CAM><Target>$(MajestyExpansionDataPath)\\quest.cam</Target></CAM></Load>
                </Quest></Majesty>''')
            write_cam(original, b'No shortcuts')
            write_cam(expansion, b'No shortcuts')
            self.assertIsNone(w.binding_conflict(game, (manifest,)))
            write_cam(original, b'KEY = F11 SHIFT CONTROL')
            self.assertEqual(w.binding_conflict(game, (manifest,)), original)
            write_cam(original, b'No shortcuts')
            write_cam(expansion, struct.pack('<I', 0xCE01A))
            self.assertEqual(w.binding_conflict(game, (manifest,)), expansion)
            for invalid in ('$(MajestyDataPath)/../DataMX/quest.cam',
                            '$(MajestyDataPath)/C:quest.cam', '$(OtherPath)/quest.cam'):
                manifest.write_text(f'<Majesty><Load><CAM>{invalid}</CAM></Load></Majesty>')
                with self.subTest(path=invalid), self.assertRaises(ValueError):
                    w.binding_conflict(game, (manifest,))

    def test_manifest_fallback_preserves_xml_safety_and_declared_encoding(self):
        self.assertEqual(w._shortcut_manifest(b'<Quest>Rabbit\x92s Oak</Quest>').text, 'Rabbit\u2019s Oak')
        for xml in (b'<Quest>\x92</Other>', b'\xef\xbb\xbf<Quest>\x92</Quest>',
                    b'<?xml version="1.0" encoding="utf-8"?><Quest>\x92</Quest>'):
            with self.subTest(xml=xml), self.assertRaises(ET.ParseError):
                w._shortcut_manifest(xml)
        for encoding in ('utf-8', 'utf-16', 'cp1252'):
            xml = '<!DOCTYPE Quest [<!ENTITY e "Rabbit\u2019s Oak">]><Quest>&e;</Quest>'
            with self.subTest(encoding=encoding), self.assertRaisesRegex(ValueError, 'DTD/entity'):
                w._shortcut_manifest(xml.encode(encoding))

    def test_launch_clears_inherited_flags_and_independent_options_without_profile_edits(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            exe, dll = root / 'game.exe', root / 'runtime.dll'
            dll.write_bytes(w.ABI_MARKER)
            profile = root / 'profile.json'; profile.write_bytes(b'untouched')
            paths = SimpleNamespace(game_executable=exe, runtime_dll=dll, repo_root=ROOT,
                                    profile_path=profile, game_path=root)
            branch = SimpleNamespace(key='public')
            env = dict.fromkeys(w.ENVIRONMENT.values(), '1')
            self.assertEqual(w.configure(env, paths, branch), ())
            self.assertEqual(set(env.values()), {'0'})
            w.change(exe, 'borderless-window', True, root / 'window-qol.json')
            with patch.object(w, 'verify') as verify, patch.object(w, 'binding_conflict') as scan:
                w.configure(env, paths, branch)
                verify.assert_called_once(); scan.assert_not_called()
                self.assertEqual(env[w.ENVIRONMENT['borderless-window']], '1')
                w.change(exe, 'cursor-confinement', True, root / 'window-qol.json')
                scan.return_value = Path('conflict.cam')
                self.assertIn('off for this launch', w.configure(env, paths, branch)[0])
                self.assertEqual(env[w.ENVIRONMENT['cursor-confinement']], '0')
                scan.return_value = None; w.configure(env, paths, branch)
                self.assertEqual(env[w.ENVIRONMENT['cursor-confinement']], '1')
                dll.write_bytes(b'old runtime')
                with self.assertRaises(ValueError): w.configure(env, paths, branch)
            self.assertEqual(profile.read_bytes(), b'untouched')

    def test_qol_rows_do_not_mutate_game_or_majxpreferences(self):
        with TemporaryDirectory() as temp:
            root = Path(temp); exe = Path(os.environ['MAJESTY_PUBLIC_EXE'])
            prefs = root / 'MajXPrefs'; prefs.write_bytes(b'Windowed 1\nVSync 1\n')
            service = QolService(repo_root=ROOT, game_executable=exe, prefs_path=prefs,
                                 window_options_path=root / 'window-qol.json', specs=WINDOW_QOL_PATCHES)
            with patch.object(w, 'runtime_available', return_value=True):
                self.assertEqual(len(service.inspect().utilities), 2)
                for spec in WINDOW_QOL_PATCHES:
                    self.assertFalse(service.inspect_patch(spec.key).installed)
                    self.assertTrue(service.apply(spec.key).installed)
                    self.assertFalse(service.remove(spec.key).installed)
            self.assertEqual(prefs.read_bytes(), b'Windowed 1\nVSync 1\n')

    def test_production_launch_checks_ui_resources_with_held_profile_lock(self):
        from test_process_windows import _manager_paths, _capability_manifest, _feature_registry, _controller_registry
        from majesty_cam.manager.launch import launch_majesty
        from unittest.mock import Mock
        with TemporaryDirectory() as temp:
            root = Path(temp); paths = _manager_paths(root)
            for file in (paths.game_executable, paths.runtime_launcher, paths.runtime_dll):
                file.parent.mkdir(parents=True, exist_ok=True); file.write_bytes(b'fixture')
            paths.merged_output_root.mkdir(parents=True)
            manifest = paths.merged_output_root / 'Merged.mmxml'; manifest.write_bytes(b'fixture')
            lock = Mock(handle=123)
            with patch.object(w, 'configure', return_value=()) as configure, \
                 patch('majesty_cam.manager.launch.subprocess.Popen', return_value=SimpleNamespace(pid=123)), \
                 patch('majesty_cam.manager.launch.configure_launch'):
                launch_majesty(paths, (), acquired_profile_lock=lock, ensure_qol=False,
                    capability_manifest=_capability_manifest(root), runtime_feature_registry=_feature_registry(root),
                    controller_registry=_controller_registry(root))
                self.assertIn(manifest, configure.call_args.args[3])
                lock.close.assert_called_once()
                self.assertEqual(manifest.read_bytes(), b'fixture')


if __name__ == '__main__': unittest.main()
