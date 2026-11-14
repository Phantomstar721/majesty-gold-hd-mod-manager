"""The gate itself must fail closed without touching installed game data."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

path = Path(__file__).resolve().parents[1] / "scripts/verify_regression.py"
spec = importlib.util.spec_from_file_location("regression_gate_under_test", path)
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)

class GateTests(unittest.TestCase):
    def test_bounded_runtime_reports_do_not_change_shipped_input_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            app = Path(tmp)
            runtime = app / '_internal/payload/runtime'
            runtime.mkdir(parents=True)
            dll = runtime / 'MajestyBuildingRuntime.dll'
            dll.write_bytes(b'production runtime')
            before = gate.artifact_files(app)
            for name in ('manager-launch.json', 'manager-launch.json.1', 'manager-launch.json.2',
                         'manager-error.txt', 'manager-error.txt.1',
                         'MajestyBuildingRuntime.log.fault.2', 'failure.mdmp'):
                (runtime / name).write_bytes(b'preserved user support evidence')
            self.assertEqual(gate.artifact_files(app), before)
            dll.write_bytes(b'changed runtime')
            self.assertNotEqual(gate.artifact_files(app), before)

    def test_similar_names_outside_owned_runtime_directories_remain_inputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            names = ('_internal/profiles/runtime/manager-launch.json',
                     '_internal/payload/mods/example/runtime/manager-launch.json',
                     '_internal/payload/runtime/manager-launch.json.3',
                     '_internal/payload/runtime/manager-error.txt.2',
                     '_internal/payload/runtime/generated.cpp')
            for name in names:
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b'checked input')
            self.assertEqual(set(gate.artifact_files(root)), {str(Path(p)) for p in names})

    def test_payload_proof_preserves_support_files_but_rejects_changed_runtime(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            app = root / 'app'
            for parent in (root / 'payload', app / '_internal/payload'):
                (parent / 'runtime').mkdir(parents=True)
                (parent / 'runtime/runtime.dll').write_bytes(b'runtime')
            (root / 'profiles').mkdir()
            (app / '_internal/profiles').mkdir()
            (app / '_internal/payload/runtime/manager-launch.json').write_text('user context')
            loader = object.__new__(gate.BundleLoader)
            with patch.object(gate, 'ROOT', root):
                loader.verify_data(app)
                (app / '_internal/payload/runtime/runtime.dll').write_bytes(b'changed')
                with self.assertRaisesRegex(ValueError, 'Packaged payload differs'):
                    loader.verify_data(app)

    def test_write_guard_allows_only_fixture_tree(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            audit = gate.write_guard(root)
            audit("open", (str(root / "fixture.bin"), "wb", 0))
            audit("open", (str(root.parent / "installed.bin"), "rb", 0))
            for event, args in (
                ("open", (str(root.parent / "installed.bin"), "wb", 0)),
                ("os.remove", (str(root.parent / "installed.bin"), -1)),
                ("os.rename", (str(root / "x"), str(root.parent / "installed.bin"))),
            ):
                with self.subTest(event=event), self.assertRaises(PermissionError):
                    audit(event, args)

    def test_missing_and_wrong_profile_are_errors(self):
        with patch.dict(gate.os.environ, {}, clear=True):
            with self.assertRaisesRegex(ValueError, "Missing required fixture"):
                gate.fixture_evidence()

    def test_skips_and_empty_suites_cannot_pass(self):
        class Skipped(unittest.TestCase):
            @unittest.skip("unavailable")
            def test_missing(self): pass
        for suite in (unittest.TestSuite(), unittest.defaultTestLoader.loadTestsFromTestCase(Skipped)):
            with patch.object(gate.unittest.defaultTestLoader, "loadTestsFromNames", return_value=suite):
                with self.assertRaises(RuntimeError):
                    gate.execute_tests(("fixture",))

    def test_code_normalization_does_not_hide_changed_constants(self):
        a = compile("answer = 1", "one.py", "exec")
        same = compile("answer = 1", "relocated.py", "exec")
        changed = compile("answer = 2", "one.py", "exec")
        self.assertEqual(gate.normalized(a), gate.normalized(same))
        self.assertNotEqual(gate.normalized(a), gate.normalized(changed))

    def test_missing_bundle_module_never_falls_back_to_source(self):
        loader = object.__new__(gate.BundleLoader)
        loader.archive = SimpleNamespace(toc={})
        with self.assertRaisesRegex(ImportError, 'absent from packaged'):
            loader.find_spec('majesty_cam.compose')

    def test_stale_bundle_code_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / 'src/majesty_cam/fixture.py'
            source.parent.mkdir(parents=True)
            source.write_text('value = 2')
            loader = object.__new__(gate.BundleLoader)
            loader.archive = SimpleNamespace(toc={'majesty_cam.fixture': (0, 0, 0)},
                extract=lambda name: compile('value = 1', 'fixture.py', 'exec'))
            with patch.object(gate, 'ROOT', root), self.assertRaisesRegex(ValueError, 'differs from current source'):
                loader.verify_source()

    def test_wrong_labeled_fixture_is_rejected(self):
        from majesty_cam.manager.qol_service import BETA2_BRANCH
        with tempfile.TemporaryDirectory() as tmp:
            fixture = Path(tmp) / 'fixture.exe'
            fixture.write_bytes(b'synthetic fixture')
            with patch.dict(gate.os.environ, {'MAJESTY_PUBLIC_EXE': str(fixture)}), patch(
                    'majesty_cam.manager.qol_service.detect_majesty_branch', return_value=BETA2_BRANCH):
                with self.assertRaisesRegex(ValueError, 'Wrong executable profile for PUBLIC'):
                    gate.fixture_evidence()

