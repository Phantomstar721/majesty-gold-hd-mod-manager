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
