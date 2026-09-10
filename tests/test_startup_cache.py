from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from majesty_cam.manager.catalog import (
    Catalog,
    CatalogEntry,
    CatalogIssue,
    CatalogKind,
    CatalogSource,
    IssueSeverity,
)
from majesty_cam.manager.compatibility import CompatibilityRegistry
from majesty_cam.manager.controller import ManagerController
from majesty_cam.manager.paths import ManagerPaths
from majesty_cam.manager.qol_service import (
    PUBLIC_BRANCH,
    QolCatalogSnapshot,
    QolPatchSpec,
    QolService,
    QolUtilityState,
    QolUtilityStatus,
    resolve_qol_patch,
)
from majesty_cam.manager.startup_cache import (
    StartupCache,
    catalog_input_signature,
    metadata_signature,
    qol_input_signature,
)


MOD_ID = "8C48289E-7C70-4426-8913-133F3544A182"


class StartupCacheTests(unittest.TestCase):
    def test_catalog_round_trip_and_installed_content_change_invalidation(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            mods = root / "Mods"
            quests = root / "Quests"
            workshop = root / "Workshop"
            for path in (mods, quests, workshop):
                path.mkdir()
            package = mods / "Fixture"
            package.mkdir()
            payload = package / "content.gpl"
            payload.write_text("function One() begin end", encoding="ascii")
            entry = CatalogEntry(
                content_id=MOD_ID,
                raw_content_id=MOD_ID,
                display_name="Fixture Mod",
                kind=CatalogKind.STANDARD,
                source=CatalogSource.LOCAL_MODS,
                package_root=package,
                manifest_path=package / "fixture.mmxml",
                has_cam=False,
                merge_ready=False,
                content_definitions=(("function:one", "abc"),),
            )
            registry = CompatibilityRegistry(specs={})
            signature = catalog_input_signature(
                local_mods_root=mods,
                local_quests_root=quests,
                workshop_roots=(workshop,),
                registry=registry,
            )
            cache_path = root / "startup-cache.json"
            cache = StartupCache.load(cache_path)
            cache.set_catalog(signature, Catalog(entries=(entry,)))
            cache.save()

            loaded = StartupCache.load(cache_path)
            self.assertEqual(loaded.get_catalog(signature), Catalog(entries=(entry,)))

            payload.write_text("function Two() begin end", encoding="ascii")
            changed = catalog_input_signature(
                local_mods_root=mods,
                local_quests_root=quests,
                workshop_roots=(workshop,),
                registry=registry,
            )
            self.assertNotEqual(changed, signature)
            self.assertIsNone(loaded.get_catalog(changed))

    def test_managed_build_cache_requires_matching_output_metadata(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            output = root / "Merged"
            output.mkdir()
            payload = output / "content.cam"
            payload.write_bytes(b"first")
            signature = metadata_signature(
                (output,),
                context=("managed-build-v1",),
                recursive_directories=True,
            )
            result = {
                "manifest_name": "CAMManager-test.mmxml",
                "report_name": "CAM-MERGE-REPORT.json",
                "mod_id": MOD_ID,
                "fingerprint": "fixture",
                "selected_source_ids": [MOD_ID],
            }
            cache = StartupCache.load(root / "startup-cache.json")
            cache.set_managed_build(signature, result)
            cache.save()

            loaded = StartupCache.load(root / "startup-cache.json")
            self.assertEqual(loaded.get_managed_build(signature), result)
            payload.write_bytes(b"changed")
            changed = metadata_signature(
                (output,),
                context=("managed-build-v1",),
                recursive_directories=True,
            )
            self.assertIsNone(loaded.get_managed_build(changed))

    def test_preflight_round_trip_and_metadata_change_invalidation(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            package = root / "package"
            package.mkdir()
            payload = package / "content.cam"
            payload.write_bytes(b"first")
            signature = metadata_signature(
                (package,), context=("fixture",), recursive_directories=True
            )
            issue = CatalogIssue(
                code="fixture_warning",
                message="Fixture warning",
                severity=IssueSeverity.WARNING,
                path=payload,
                content_id=MOD_ID,
            )
            cache_path = root / "startup-cache.json"
            cache = StartupCache.load(cache_path)
            cache.set_preflight(MOD_ID, signature, (issue,))
            cache.save()

            loaded = StartupCache.load(cache_path)
            self.assertEqual(loaded.get_preflight(MOD_ID, signature), (issue,))

            payload.write_bytes(b"changed-size")
            changed = metadata_signature(
                (package,), context=("fixture",), recursive_directories=True
            )
            self.assertNotEqual(changed, signature)
            self.assertIsNone(loaded.get_preflight(MOD_ID, changed))

    def test_qol_round_trip_and_executable_change_invalidation(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            repo = root / "repo"
            game_executable = root / "game/MajestyHD.exe"
            game_executable.parent.mkdir(parents=True)
            game_executable.write_bytes(b"game-v1")
            spec = QolPatchSpec(
                key="fixture",
                name="Fixture Helper",
                description="Fixture",
                repository="fixture-repo",
                bundle_directory="Fixture Helper",
                payload_slug="fixture-helper",
                install_script_name="Install-Fixture.ps1",
                remove_script_name="Remove-Fixture.ps1",
                installed_phrase="already installed",
            )
            utility_root = repo / "payload/qol/utilities/Fixture Helper"
            utility_root.mkdir(parents=True)
            (utility_root / "Install-Fixture.ps1").write_text("install")
            (utility_root / "Remove-Fixture.ps1").write_text("remove")
            service = QolService(
                repo_root=repo,
                game_executable=game_executable,
                prefs_path=root / "prefs",
                specs=(spec,),
            )
            patch = resolve_qol_patch(repo, spec)
            snapshot = QolCatalogSnapshot(
                game_executable=game_executable,
                branch=PUBLIC_BRANCH,
                utilities=(
                    QolUtilityStatus(
                        patch=patch,
                        state=QolUtilityState.INSTALLED,
                        supported=True,
                        applicable=True,
                        installed=True,
                        detail="Installed",
                    ),
                ),
            )
            signature = qol_input_signature(service)
            cache_path = root / "startup-cache.json"
            cache = StartupCache.load(cache_path)
            cache.set_qol(signature, snapshot)
            cache.save()

            restored = StartupCache.load(cache_path).get_qol(signature, service)
            self.assertIsNotNone(restored)
            assert restored is not None
            self.assertEqual(restored.branch, PUBLIC_BRANCH)
            self.assertTrue(restored.utilities[0].installed)

            game_executable.write_bytes(b"game-version-two")
            changed = qol_input_signature(service)
            self.assertNotEqual(changed, signature)
            self.assertIsNone(StartupCache.load(cache_path).get_qol(changed, service))

    def test_controller_reuses_unchanged_deep_preflight_but_force_refreshes(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            paths = _manager_paths(root)
            package = paths.local_mods_root / "Merge Mod"
            package.mkdir(parents=True)
            (package / "content.cam").write_bytes(b"fixture")
            entry = CatalogEntry(
                content_id=MOD_ID,
                raw_content_id=MOD_ID,
                display_name="Merge Mod",
                kind=CatalogKind.MERGE,
                source=CatalogSource.LOCAL_MODS,
                package_root=package,
                manifest_path=package / "fixture.mmxml",
                has_cam=True,
                merge_ready=True,
            )
            issue = CatalogIssue(
                code="fixture_warning",
                message="Fixture",
                severity=IssueSeverity.WARNING,
                path=package,
                content_id=MOD_ID,
            )

            def fake_scan(**kwargs):
                issues = kwargs["merge_preflight"](
                    MOD_ID, "Merge Mod", package
                )
                return Catalog(entries=(entry,), issues=tuple(issues))

            with patch(
                "majesty_cam.manager.controller.scan_catalog", side_effect=fake_scan
            ), patch(
                "majesty_cam.manager.controller.catalog_merge_preflight",
                return_value=(issue,),
            ) as deep:
                first = ManagerController(
                    paths=paths, registry=CompatibilityRegistry(specs={})
                )
                with patch.object(first, "_replan"):
                    first.scan(inspect_qol=False)
                second = ManagerController(
                    paths=paths, registry=CompatibilityRegistry(specs={})
                )
                with patch.object(second, "_replan"):
                    second.scan(inspect_qol=False)
                    second.scan(inspect_qol=False, force_refresh=True)

            self.assertEqual(deep.call_count, 2)

    def test_controller_reuses_unchanged_qol_inspection(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            paths = _manager_paths(root)
            paths.game_executable.write_bytes(b"game")
            spec = QolPatchSpec(
                key="fixture",
                name="Fixture Helper",
                description="Fixture",
                repository="fixture-repo",
                bundle_directory="Fixture Helper",
                payload_slug="fixture-helper",
                install_script_name="Install-Fixture.ps1",
                remove_script_name="Remove-Fixture.ps1",
                installed_phrase="already installed",
            )
            utility_root = paths.repo_root / "payload/qol/utilities/Fixture Helper"
            utility_root.mkdir(parents=True)
            (utility_root / "Install-Fixture.ps1").write_text("install")
            (utility_root / "Remove-Fixture.ps1").write_text("remove")
            service = QolService(
                repo_root=paths.repo_root,
                game_executable=paths.game_executable,
                prefs_path=root / "prefs",
                specs=(spec,),
            )
            snapshot = QolCatalogSnapshot(
                game_executable=paths.game_executable,
                branch=PUBLIC_BRANCH,
                utilities=(
                    QolUtilityStatus(
                        patch=resolve_qol_patch(paths.repo_root, spec),
                        state=QolUtilityState.INSTALLED,
                        supported=True,
                        applicable=True,
                        installed=True,
                        detail="Installed",
                    ),
                ),
            )

            first = ManagerController(
                paths=paths, registry=CompatibilityRegistry(specs={})
            )
            first.qol_service = service
            second = ManagerController(
                paths=paths, registry=CompatibilityRegistry(specs={})
            )
            second.qol_service = service
            with patch(
                "majesty_cam.manager.controller.scan_catalog",
                return_value=Catalog(entries=()),
            ), patch.object(service, "inspect", return_value=snapshot) as inspect:
                first.scan()
                second.scan()
                second.scan(force_refresh=True)

            # Rescan Content refreshes mod discovery, not unchanged executable
            # patch state. QOL mutations have their own targeted refresh path.
            self.assertEqual(inspect.call_count, 1)


def _manager_paths(root: Path) -> ManagerPaths:
    repo = root / "repo"
    game = root / "game"
    mods = root / "Mods"
    quests = root / "Quests"
    runtime = root / "runtime"
    for path in (repo, game, mods, quests, runtime):
        path.mkdir(parents=True, exist_ok=True)
    return ManagerPaths(
        repo_root=repo,
        game_path=game,
        local_mods_root=mods,
        local_quests_root=quests,
        workshop_roots=(),
        runtime_root=runtime,
        generic_visitor_installer=root / "Install-GenericVisitorLists.ps1",
        remember_mods_installer=root / "Install-ModPersistence.ps1",
        remembered_path=root / "localappdata/MajestyHD/MajestyModPersistence.txt",
        profile_path=root / "localappdata/MajestyModManager/profile.json",
        merged_output_root=mods / "Majesty Mod Manager - Merged",
    )


if __name__ == "__main__":
    unittest.main()
