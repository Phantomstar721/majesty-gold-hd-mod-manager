from pathlib import Path
from types import SimpleNamespace
import json
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from majesty_cam.manager.build import BuildPlan, ManagerBuildError, ManagerBuildResult
from majesty_cam.manager.catalog import (
    Catalog,
    CatalogEntry,
    CatalogKind,
    CatalogSource,
)
from majesty_cam.manager.compatibility import CompatibilityRegistry
from majesty_cam.manager.controller import ManagerController
from majesty_cam.manager.launch import LaunchResult, ManagerLaunchError
from majesty_cam.manager.paths import ManagerPaths
from majesty_cam.manager.preflight import PreparedMergeMod
from majesty_cam.manager.qol import QolPatchStatus
from majesty_cam.intent_text import INTENT_REGISTRY_RELATIVE_PATH
from majesty_cam.runtime_capabilities import (
    RUNTIME_CAPABILITY_MANIFEST_RELATIVE_PATH,
    encode_runtime_capability_manifest,
)


HAUNT_ID = "8C48289E-7C70-4426-8913-133F3544A182"
ALCHEMIST_ID = "42BA4603-2B13-446D-A2A4-6CF3A55DDAC3"
STANDARD_ID = "48CDD934-B338-4373-A4A4-A99A8E7F917F"
GENERATED_ID = "A80596DA-60D7-5DF1-9D01-4D69F40D5D95"


class ManagerControllerTests(unittest.TestCase):
    def test_standard_only_launch_explicitly_omits_activity_registry(self):
        with TemporaryDirectory() as tmp:
            paths = _manager_paths(Path(tmp), runtime_ready=True)
            controller = ManagerController(
                paths=paths, registry=CompatibilityRegistry(specs={})
            )
            controller.plan = BuildPlan(
                selected_standard_ids=(STANDARD_ID,),
                selected_merge=(),
                resolution_owners={},
                semantic_resolutions={},
                runtime_capabilities=("generic-visitor-lists.v1",),
                fingerprint="standard-only",
                issues=(),
            )
            _set_required_qol_state(controller, installed=True)
            launched = LaunchResult(
                launcher_pid=123,
                active_mod_ids=(STANDARD_ID,),
                executable=paths.game_executable,
                runtime_dll=paths.runtime_dll,
            )
            with patch(
                "majesty_cam.manager.controller.launch_majesty",
                return_value=launched,
            ) as launch:
                controller.launch()

            self.assertIsNone(launch.call_args.kwargs["intent_registry"])
            capability_path = launch.call_args.kwargs["capability_manifest"]
            self.assertEqual(capability_path, paths.empty_runtime_capability_manifest)
            self.assertEqual(capability_path.read_bytes(), encode_runtime_capability_manifest(()))

    def test_scan_silently_restores_a_generated_profile_to_source_mods(self):
        with TemporaryDirectory() as tmp:
            paths = _manager_paths(Path(tmp))
            generated_root = paths.local_mods_root / "Old Generated Profile"
            generated_root.mkdir(parents=True)
            (generated_root / "CAM-MERGE-REPORT.json").write_text(
                json.dumps(
                    {
                        "inputs": [
                            {"mod_id": HAUNT_ID},
                            {"mod_id": ALCHEMIST_ID},
                        ]
                    }
                ),
                encoding="utf-8",
            )
            catalog = Catalog(
                entries=(
                    _entry(HAUNT_ID, "Phantoms Haunt", generated_root / "Haunt"),
                    _entry(
                        ALCHEMIST_ID,
                        "Alchemist Guild",
                        generated_root / "Alchemist",
                    ),
                    _entry(
                        GENERATED_ID,
                        "Previous Merged Profile",
                        generated_root,
                        generated=True,
                    ),
                )
            )
            controller = ManagerController(
                paths=paths, registry=CompatibilityRegistry(specs={})
            )

            with patch(
                "majesty_cam.manager.controller.scan_catalog", return_value=catalog
            ), patch(
                "majesty_cam.manager.controller.read_remembered_mods",
                return_value=(GENERATED_ID,),
            ), patch.object(controller, "_replan"):
                snapshot = controller.scan(inspect_qol=False)

            self.assertEqual(snapshot.selection_source, "remembered")
            self.assertEqual(
                snapshot.selections,
                {HAUNT_ID: True, ALCHEMIST_ID: True},
            )
            self.assertEqual(snapshot.notices, ())

    def test_unreadable_generated_profile_reports_only_a_player_action(self):
        with TemporaryDirectory() as tmp:
            paths = _manager_paths(Path(tmp))
            generated_root = paths.local_mods_root / "Old Generated Profile"
            generated_root.mkdir(parents=True)
            (generated_root / "CAM-MERGE-REPORT.json").write_text(
                "not-json", encoding="utf-8"
            )
            controller = ManagerController(
                paths=paths, registry=CompatibilityRegistry(specs={})
            )
            controller.catalog = Catalog(
                entries=(
                    _entry(
                        GENERATED_ID,
                        "Previous Merged Profile",
                        generated_root,
                        generated=True,
                    ),
                )
            )

            restored = controller._expand_generated_profile_ids((GENERATED_ID,))

            self.assertEqual(restored, ())
            self.assertEqual(
                controller.notices,
                [
                    "A previous combined setup could not be restored. "
                    "Review the Merge tab before preparing mods."
                ],
            )
            self.assertNotIn("source selections", controller.notices[0])

    def test_launch_activates_generated_profile_instead_of_merge_sources(self):
        with TemporaryDirectory() as tmp:
            paths = _manager_paths(Path(tmp), runtime_ready=True)
            controller = ManagerController(
                paths=paths, registry=CompatibilityRegistry(specs={})
            )
            controller.plan = _merge_plan(paths, fingerprint="current")
            _set_required_qol_state(controller, installed=True)
            managed = _managed_build(paths, fingerprint="current")
            launched = LaunchResult(
                launcher_pid=123,
                active_mod_ids=(STANDARD_ID, GENERATED_ID),
                executable=paths.game_executable,
                runtime_dll=paths.runtime_dll,
            )

            with patch(
                "majesty_cam.manager.controller.read_managed_build",
                return_value=managed,
            ), patch(
                "majesty_cam.manager.controller._require_current_plan_sources"
            ), patch(
                "majesty_cam.manager.controller.launch_majesty",
                return_value=launched,
            ) as launch:
                result, snapshot = controller.launch()

            self.assertEqual(result, launched)
            self.assertTrue(snapshot.can_launch)
            active_ids = launch.call_args.args[1]
            self.assertEqual(active_ids, [STANDARD_ID, GENERATED_ID])
            self.assertEqual(
                launch.call_args.kwargs["intent_registry"],
                managed.output_root / Path(INTENT_REGISTRY_RELATIVE_PATH),
            )
            self.assertEqual(
                launch.call_args.kwargs["capability_manifest"],
                managed.capability_manifest,
            )
            self.assertNotIn(HAUNT_ID, active_ids)
            self.assertNotIn(ALCHEMIST_ID, active_ids)

    def test_changed_merge_inputs_are_rejected_immediately_before_launch(self):
        with TemporaryDirectory() as tmp:
            paths = _manager_paths(Path(tmp), runtime_ready=True)
            controller = ManagerController(
                paths=paths, registry=CompatibilityRegistry(specs={})
            )
            controller.plan = _merge_plan(paths, fingerprint="current")
            _set_required_qol_state(controller, installed=True)
            managed = _managed_build(paths, fingerprint="current")

            for changed_input in ("package", "stock composition"):
                with self.subTest(changed_input=changed_input), patch(
                    "majesty_cam.manager.controller.read_managed_build",
                    return_value=managed,
                ), patch(
                    "majesty_cam.manager.controller._require_current_plan_sources",
                    side_effect=ManagerBuildError(
                        f"Selected {changed_input} inputs changed before launch."
                    ),
                ) as revalidate, patch(
                    "majesty_cam.manager.controller.launch_majesty"
                ) as launch:
                    with self.assertRaisesRegex(
                        ManagerLaunchError, "changed before launch"
                    ):
                        controller.launch()

                revalidate.assert_called_once_with(
                    controller.plan,
                    game_path=paths.game_path,
                    phase="before launch",
                )
                launch.assert_not_called()

    def test_build_and_launch_gates_track_missing_stale_and_current_output(self):
        with TemporaryDirectory() as tmp:
            paths = _manager_paths(Path(tmp), runtime_ready=True)
            controller = ManagerController(
                paths=paths, registry=CompatibilityRegistry(specs={})
            )
            controller.plan = _merge_plan(paths, fingerprint="current")
            _set_required_qol_state(controller, installed=True)

            with patch(
                "majesty_cam.manager.controller.read_managed_build",
                return_value=None,
            ):
                missing = controller.snapshot()
            self.assertTrue(missing.build_required)
            self.assertTrue(missing.can_build)
            self.assertFalse(missing.can_launch)

            current_build = _managed_build(paths, fingerprint="current")
            with patch(
                "majesty_cam.manager.controller.read_managed_build",
                return_value=current_build,
            ):
                current = controller.snapshot()
            self.assertFalse(current.build_required)
            self.assertTrue(current.can_build)
            self.assertTrue(current.can_launch)

            stale_build = _managed_build(paths, fingerprint="old")
            with patch(
                "majesty_cam.manager.controller.read_managed_build",
                return_value=stale_build,
            ):
                stale = controller.snapshot()
            self.assertTrue(stale.build_required)
            self.assertFalse(stale.can_launch)

            controller.plan = BuildPlan(
                selected_standard_ids=(STANDARD_ID,),
                selected_merge=(),
                resolution_owners={},
                semantic_resolutions={},
                runtime_capabilities=("generic-visitor-lists.v1",),
                fingerprint="standard-only",
                issues=(),
            )
            with patch(
                "majesty_cam.manager.controller.read_managed_build",
                return_value=current_build,
            ):
                standard_only = controller.snapshot()
            self.assertFalse(standard_only.build_required)
            self.assertFalse(standard_only.can_build)
            self.assertTrue(standard_only.can_launch)

    def test_checked_missing_qol_payload_disables_launch(self):
        with TemporaryDirectory() as tmp:
            paths = _manager_paths(Path(tmp), runtime_ready=True)
            controller = ManagerController(
                paths=paths, registry=CompatibilityRegistry(specs={})
            )
            controller.plan = BuildPlan(
                selected_standard_ids=(STANDARD_ID,),
                selected_merge=(),
                resolution_owners={},
                semantic_resolutions={},
                runtime_capabilities=("generic-visitor-lists.v1",),
                fingerprint="standard-only",
                issues=(),
            )
            controller._qol_checked = True
            controller.qol_status = (
                QolPatchStatus(
                    name="Generic Visitor Lists",
                    available=False,
                    installed=False,
                    detail="bundled installer missing",
                ),
            )

            snapshot = controller.snapshot()

            self.assertFalse(snapshot.can_launch)

    def test_required_qol_must_be_installed_not_just_available(self):
        with TemporaryDirectory() as tmp:
            paths = _manager_paths(Path(tmp), runtime_ready=True)
            controller = ManagerController(
                paths=paths, registry=CompatibilityRegistry(specs={})
            )
            controller.plan = _merge_plan(paths, fingerprint="current")
            managed = _managed_build(paths, fingerprint="current")

            for available, installed in (
                (False, False),
                (True, False),
            ):
                with self.subTest(available=available, installed=installed):
                    _set_required_qol_state(
                        controller,
                        available=available,
                        installed=installed,
                    )
                    with patch(
                        "majesty_cam.manager.controller.read_managed_build",
                        return_value=managed,
                    ):
                        snapshot = controller.snapshot()
                    self.assertFalse(snapshot.can_build)
                    self.assertFalse(snapshot.can_launch)

            _set_required_qol_state(controller, available=True, installed=True)
            with patch(
                "majesty_cam.manager.controller.read_managed_build",
                return_value=managed,
            ):
                snapshot = controller.snapshot()
            self.assertTrue(snapshot.can_build)
            self.assertTrue(snapshot.can_launch)

    def test_build_and_launch_refuse_unconfirmed_required_qol(self):
        with TemporaryDirectory() as tmp:
            paths = _manager_paths(Path(tmp), runtime_ready=True)
            controller = ManagerController(
                paths=paths, registry=CompatibilityRegistry(specs={})
            )
            controller.plan = _merge_plan(paths, fingerprint="current")
            managed = _managed_build(paths, fingerprint="current")
            _set_required_qol_state(controller, available=True, installed=False)

            with patch(
                "majesty_cam.manager.controller.build_merged_package"
            ) as build_package:
                with self.assertRaisesRegex(
                    ManagerBuildError, "Quality of Life tab"
                ):
                    controller.build()
            build_package.assert_not_called()

            with patch(
                "majesty_cam.manager.controller.read_managed_build",
                return_value=managed,
            ), patch(
                "majesty_cam.manager.controller.launch_majesty"
            ) as launch:
                with self.assertRaisesRegex(
                    ManagerLaunchError, "Quality of Life tab"
                ):
                    controller.launch()
            launch.assert_not_called()

    def test_skipping_qol_inspection_never_claims_runtime_readiness(self):
        with TemporaryDirectory() as tmp:
            paths = _manager_paths(Path(tmp), runtime_ready=True)
            controller = ManagerController(
                paths=paths, registry=CompatibilityRegistry(specs={})
            )
            controller.plan = _merge_plan(paths, fingerprint="current")
            managed = _managed_build(paths, fingerprint="current")

            with patch(
                "majesty_cam.manager.controller.read_managed_build",
                return_value=managed,
            ):
                snapshot = controller.snapshot()

            self.assertFalse(controller._qol_checked)
            self.assertFalse(snapshot.can_build)
            self.assertFalse(snapshot.can_launch)


def _manager_paths(root: Path, *, runtime_ready: bool = False) -> ManagerPaths:
    repo = root / "repo"
    game = root / "game"
    mods = root / "Mods"
    quests = root / "Quests"
    runtime = root / "runtime"
    for path in (repo, game, mods, quests, runtime):
        path.mkdir(parents=True, exist_ok=True)
    if runtime_ready:
        (game / "MajestyHD.exe").write_bytes(b"exe")
        (runtime / "MajestyBuildingRuntimeLauncher.exe").write_bytes(b"launcher")
        (runtime / "MajestyBuildingRuntime.dll").write_bytes(b"dll")
    return ManagerPaths(
        repo_root=repo,
        game_path=game,
        local_mods_root=mods,
        local_quests_root=quests,
        workshop_roots=(),
        runtime_root=runtime,
        generic_visitor_installer=root / "Install-GenericVisitorLists.ps1",
        remember_mods_installer=root / "Install-ModPersistence.ps1",
        remembered_path=root / "localappdata" / "MajestyHD" / "MajestyModPersistence.txt",
        profile_path=root / "localappdata" / "MajestyModManager" / "profile.json",
        merged_output_root=mods / "Majesty Mod Manager - Merged",
    )


def _set_required_qol_state(
    controller: ManagerController,
    *,
    available: bool = True,
    installed: bool,
) -> None:
    controller._qol_checked = True
    controller.qol_status = tuple(
        QolPatchStatus(
            name=spec.name,
            available=available,
            installed=installed,
            detail="Installed" if installed else "Available" if available else "Missing",
        )
        for spec in controller.qol_service.specs
        if spec.required_by_manager
    )


def _entry(
    content_id: str,
    display_name: str,
    root: Path,
    *,
    generated: bool = False,
) -> CatalogEntry:
    return CatalogEntry(
        content_id=content_id,
        raw_content_id=content_id,
        display_name=display_name,
        kind=CatalogKind.MERGE,
        source=CatalogSource.LOCAL_MODS,
        package_root=root,
        manifest_path=root / "package.mmxml",
        has_cam=True,
        merge_ready=not generated,
        generated=generated,
    )


def _prepared(content_id: str, display_name: str, root: Path) -> PreparedMergeMod:
    return PreparedMergeMod(
        content_id=content_id,
        display_name=display_name,
        source_root=root,
        effective_root=root,
        alias=display_name.casefold().replace(" ", "-"),
        package=SimpleNamespace(mod_id=content_id),
        priority=100,
        runtime_capabilities=("expanded-building-slots.cg-prefix",),
        badge=None,
        substituted=False,
        compatibility=None,
        issues=(),
    )


def _merge_plan(paths: ManagerPaths, *, fingerprint: str) -> BuildPlan:
    return BuildPlan(
        selected_standard_ids=(STANDARD_ID,),
        selected_merge=(
            _prepared(HAUNT_ID, "Phantoms Haunt", paths.local_mods_root / "Haunt"),
            _prepared(
                ALCHEMIST_ID,
                "Alchemist Guild",
                paths.local_mods_root / "Alchemist",
            ),
        ),
        resolution_owners={},
        semantic_resolutions={},
        runtime_capabilities=("generic-visitor-lists.v1",),
        fingerprint=fingerprint,
        issues=(),
    )


def _managed_build(paths: ManagerPaths, *, fingerprint: str) -> ManagerBuildResult:
    output = paths.merged_output_root
    output.mkdir(parents=True, exist_ok=True)
    manifest = output / "CAMManager-test.mmxml"
    report = output / "CAM-MERGE-REPORT.json"
    capability_manifest = output / Path(
        RUNTIME_CAPABILITY_MANIFEST_RELATIVE_PATH
    )
    capability_manifest.parent.mkdir(parents=True, exist_ok=True)
    capability_manifest.write_bytes(encode_runtime_capability_manifest(()))
    manifest.write_text("<ModPackage />", encoding="utf-8")
    report.write_text("{}", encoding="utf-8")
    return ManagerBuildResult(
        output_root=output,
        manifest=manifest,
        report=report,
        capability_manifest=capability_manifest,
        mod_id=GENERATED_ID,
        fingerprint=fingerprint,
        selected_source_ids=(HAUNT_ID, ALCHEMIST_ID),
    )


if __name__ == "__main__":
    unittest.main()
