from contextlib import ExitStack, contextmanager
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from majesty_cam.manager.compatibility import (
    default_registry_path,
    load_compatibility_registry,
)
import majesty_cam.manager.paths as manager_paths


MOD_ID = "42BA4603-2B13-446D-A2A4-6CF3A55DDAC3"


class FrozenManagerPathTests(unittest.TestCase):
    def test_player_selected_executable_is_remembered_and_preferred(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            resources = root / "repo"
            resources.mkdir()
            game = root / "alternate-library" / "Majesty HD"
            executable = game / "MajestyHD.exe"
            _touch(executable)
            local_appdata = root / "localappdata"
            selection = manager_paths.game_executable_selection_path(
                local_appdata
            )

            saved = manager_paths.save_game_executable_selection(
                selection, executable
            )
            self.assertEqual(
                manager_paths.read_game_executable_selection(selection), saved
            )
            with patch.object(
                manager_paths, "_steam_library_roots", return_value=()
            ):
                detected = manager_paths.detect_manager_paths(
                    repo_root=resources,
                    documents_root=root / "documents",
                    local_appdata=local_appdata,
                )

            self.assertEqual(detected.game_executable, executable.resolve())

    def test_stale_or_renamed_executable_selection_is_ignored(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            selection = root / "game-executable.txt"
            renamed = root / "Other.exe"
            _touch(renamed)
            selection.write_text(str(renamed), encoding="utf-8")
            self.assertIsNone(
                manager_paths.read_game_executable_selection(selection)
            )

    def test_application_root_uses_pyinstaller_meipass_without_leaking_sys_state(self):
        had_frozen = hasattr(sys, "frozen")
        old_frozen = getattr(sys, "frozen", None)
        had_meipass = hasattr(sys, "_MEIPASS")
        old_meipass = getattr(sys, "_MEIPASS", None)
        with TemporaryDirectory() as tmp:
            resource_root = Path(tmp).resolve()
            with _frozen_resources(resource_root):
                self.assertEqual(manager_paths.application_root(), resource_root)

        self.assertEqual(hasattr(sys, "frozen"), had_frozen)
        self.assertEqual(getattr(sys, "frozen", None), old_frozen)
        self.assertEqual(hasattr(sys, "_MEIPASS"), had_meipass)
        self.assertEqual(getattr(sys, "_MEIPASS", None), old_meipass)

    def test_frozen_path_detection_prefers_bundled_runtime_and_qol_payload(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            resources = root / "_MEI-fixture"
            game = root / "game"
            documents = root / "documents"
            local_appdata = root / "localappdata"
            resources.mkdir()
            _touch(resources / "payload/runtime/MajestyBuildingRuntimeLauncher.exe")
            _touch(resources / "payload/runtime/MajestyBuildingRuntime.dll")
            _touch(
                resources
                / "payload/qol/generic-visitor-lists/Install-GenericVisitorLists.ps1"
            )
            _touch(
                resources
                / "payload/qol/remember-active-mods/Install-ModPersistence.ps1"
            )

            with _frozen_resources(resources), patch.object(
                manager_paths, "_steam_library_roots", return_value=()
            ):
                result = manager_paths.detect_manager_paths(
                    game_path=game,
                    documents_root=documents,
                    local_appdata=local_appdata,
                )

            self.assertEqual(result.repo_root, resources.resolve())
            self.assertEqual(result.runtime_root, resources / "payload/runtime")
            self.assertEqual(
                result.generic_visitor_installer,
                resources
                / "payload/qol/generic-visitor-lists/Install-GenericVisitorLists.ps1",
            )
            self.assertEqual(
                result.remember_mods_installer,
                resources
                / "payload/qol/remember-active-mods/Install-ModPersistence.ps1",
            )
            self.assertEqual(
                result.local_mods_root,
                documents / "My Games/MajestyHD/Mods",
            )
            self.assertEqual(
                result.profile_path,
                local_appdata / "MajestyModManager/profile.json",
            )

    def test_default_frozen_registry_resolves_definition_resolution_and_payload(self):
        with TemporaryDirectory() as tmp:
            resources = Path(tmp) / "_MEI-fixture"
            registry_path = resources / "profiles/manager/compatibility.json"
            definition_path = resources / "profiles/poc/mod-definition.json"
            resolution_path = resources / "profiles/manager/resolutions/pair.gpl"
            replacement = resources / "payload/mods/Replacement"
            replacement.mkdir(parents=True)
            _touch(definition_path)
            _touch(resolution_path)
            registry_path.parent.mkdir(parents=True, exist_ok=True)
            registry_path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "mods": {
                            MOD_ID: {
                                "alias": "fixture",
                                "definition": "profiles/poc/mod-definition.json",
                                "replacement_roots": [
                                    "payload/mods/Replacement",
                                    "workspace:missing-source-fallback",
                                ],
                                "merge_priority": 10,
                                "badge": "Frozen fixture",
                                "runtime_capabilities": [],
                                "resolution_owners": [],
                            }
                        },
                        "combination_resolutions": [
                            {
                                "requires": [
                                    MOD_ID,
                                    "8C48289E-7C70-4426-8913-133F3544A182",
                                ],
                                "source": "profiles/manager/resolutions/pair.gpl",
                                "items": [
                                    {"kind": "function", "name": "Fixture_Function"}
                                ],
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            with _frozen_resources(resources):
                self.assertEqual(default_registry_path(), registry_path.resolve())
                registry = load_compatibility_registry()

            spec = registry.get(MOD_ID)
            self.assertIsNotNone(spec)
            self.assertEqual(spec.definition_path, definition_path.resolve())
            self.assertEqual(spec.available_replacement(), replacement.resolve())
            self.assertEqual(
                spec.replacement_roots[1],
                resources.resolve() / "missing-source-fallback",
            )
            self.assertEqual(
                registry.combination_resolutions[0].source_path,
                resolution_path.resolve(),
            )

    def test_frozen_detection_never_falls_back_to_extraction_parent_siblings(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            resources = root / "_MEI-fixture"
            resources.mkdir()
            external_runtime = (
                root
                / "majesty-gold-hd-expanded-building-slots"
                / "artifacts/runtime-intent-text"
            )
            external_visitor = (
                root
                / "majesty-gold-hd-generic-visitor-lists"
                / "scripts/Install-GenericVisitorLists.ps1"
            )
            external_remember = (
                root
                / "majesty-gold-hd-remember-active-mods"
                / "scripts/Install-ModPersistence.ps1"
            )
            _touch(external_runtime / "MajestyBuildingRuntimeLauncher.exe")
            _touch(external_visitor)
            _touch(external_remember)

            with _frozen_resources(resources), patch.object(
                manager_paths, "_steam_library_roots", return_value=()
            ):
                result = manager_paths.detect_manager_paths(
                    game_path=root / "game",
                    documents_root=root / "documents",
                    local_appdata=root / "localappdata",
                )

            self.assertEqual(result.runtime_root, resources / "payload/runtime")
            self.assertEqual(
                result.generic_visitor_installer,
                resources
                / "payload/qol/generic-visitor-lists/Install-GenericVisitorLists.ps1",
            )
            self.assertEqual(
                result.remember_mods_installer,
                resources
                / "payload/qol/remember-active-mods/Install-ModPersistence.ps1",
            )

    def test_source_checkout_retains_explicit_sibling_repository_fallbacks(self):
        with TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            repo = workspace / "majesty-gold-hd-mod-manager"
            repo.mkdir()
            runtime = (
                workspace
                / "majesty-gold-hd-expanded-building-slots"
                / "artifacts/runtime-intent-text"
            )
            visitor = (
                workspace
                / "majesty-gold-hd-generic-visitor-lists"
                / "scripts/Install-GenericVisitorLists.ps1"
            )
            remember = (
                workspace
                / "majesty-gold-hd-remember-active-mods"
                / "scripts/Install-ModPersistence.ps1"
            )
            _touch(runtime / "MajestyBuildingRuntimeLauncher.exe")
            _touch(visitor)
            _touch(remember)

            with patch.object(manager_paths, "_steam_library_roots", return_value=()):
                result = manager_paths.detect_manager_paths(
                    repo_root=repo,
                    game_path=workspace / "game",
                    documents_root=workspace / "documents",
                    local_appdata=workspace / "localappdata",
                )

            self.assertEqual(result.runtime_root, runtime.resolve())
            self.assertEqual(result.generic_visitor_installer, visitor.resolve())
            self.assertEqual(result.remember_mods_installer, remember.resolve())


@contextmanager
def _frozen_resources(root: Path):
    """Patch PyInstaller markers inside a strictly restored context."""

    with ExitStack() as stack:
        stack.enter_context(patch.object(sys, "frozen", True, create=True))
        stack.enter_context(patch.object(sys, "_MEIPASS", str(root), create=True))
        yield


def _touch(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"fixture")


if __name__ == "__main__":
    unittest.main()
