from __future__ import annotations

from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch

from majesty_cam.manager.qol_service import (
    GOG_BRANCH, BETA2_BRANCH, QOL_PATCHES, QolService, QolUtilityState,
    detect_majesty_branch,
)
from majesty_cam.manager.runtime_profiles import (
    runtime_installation_identity, unsupported_runtime_capabilities,
)
from majesty_cam.manager import paths
from test_manager_qol_service import _write_synthetic_exe


class GogSupportTests(unittest.TestCase):
    def test_same_version_is_not_same_profile(self):
        with tempfile.TemporaryDirectory() as temporary:
            executable = Path(temporary) / "MajestyHD.exe"
            for branch in (GOG_BRANCH, BETA2_BRANCH):
                _write_synthetic_exe(executable, branch, appended_section=True)
                self.assertEqual(detect_majesty_branch(executable), branch)
            _write_synthetic_exe(executable, GOG_BRANCH, alter_first_section=True)
            self.assertIsNone(detect_majesty_branch(executable))

    def test_installation_identity_invalidates_same_resources_at_other_path_or_build(self):
        with tempfile.TemporaryDirectory() as temporary:
            game = Path(temporary)
            executable = game / "MajestyHD.exe"
            _write_synthetic_exe(executable, GOG_BRANCH)
            gog = runtime_installation_identity(game)
            _write_synthetic_exe(executable, BETA2_BRANCH)
            self.assertNotEqual(gog, runtime_installation_identity(game))
            other = game / "other"
            other.mkdir()
            _write_synthetic_exe(other / "MajestyHD.exe", GOG_BRANCH)
            self.assertNotEqual(gog, runtime_installation_identity(other))

    def test_unknown_gog_capability_is_not_routed_to_beta2(self):
        self.assertEqual(unsupported_runtime_capabilities(GOG_BRANCH, (
            "stock.name-generator.v1", "stock.controller-recipes.v1", "stock.equipment.v1",
        )), ("stock.equipment.v1",))
        self.assertEqual(unsupported_runtime_capabilities(BETA2_BRANCH, (
            "stock.controller-recipes.v1",
        )), ())

    def test_newer_local_features_remain_guarded_until_gog_is_audited(self):
        capabilities = ("stock.equipment.v1", "manager.kingdom-research.v1", "stock.ap78-info-row.v1")
        self.assertEqual(unsupported_runtime_capabilities(GOG_BRANCH, capabilities),
                         tuple(sorted(capabilities)))
        self.assertEqual(unsupported_runtime_capabilities(BETA2_BRANCH, capabilities), ())

    def test_optional_utilities_use_their_guarded_gog_installers(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            executable = root / "MajestyHD.exe"
            _write_synthetic_exe(executable, GOG_BRANCH)
            for spec in QOL_PATCHES:
                if spec.preference_only or spec.required_by_manager:
                    continue
                with self.subTest(utility=spec.key):
                    scripts = root / "helpers" / spec.payload_slug / "scripts"
                    scripts.mkdir(parents=True)
                    for name in (spec.install_script_name, spec.remove_script_name):
                        (scripts / name).write_text("")
                    runner = Mock(return_value=subprocess.CompletedProcess([], 0, stdout="Would install", stderr=""))
                    service = QolService(repo_root=root, game_executable=executable, runner=runner)
                    status = service.inspect_patch(spec.key)
                    self.assertEqual(status.state, QolUtilityState.AVAILABLE)
                    runner.assert_called_once()
                    self.assertIn("-DryRun", runner.call_args.args[0])

    def test_both_installations_keep_redirected_documents_and_owned_helpers(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repo = Path(__file__).resolve().parents[1]
            results = [paths.detect_manager_paths(
                repo_root=repo, game_path=root / installation,
                documents_root=root / "OneDrive" / "Documents",
                local_appdata=root / "AppData",
            ) for installation in ("Steam", "GOG")]
            self.assertEqual(results[0].local_mods_root, results[1].local_mods_root)
            self.assertEqual(results[0].merged_output_root, results[1].merged_output_root)
            self.assertTrue(results[1].remember_mods_installer.is_relative_to(repo))


if __name__ == "__main__":
    unittest.main()
