import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from majesty_cam.manager.profile import ManagerProfile,save_profile,load_profile
from majesty_cam.manager.presets import Presets
from majesty_cam.manager.catalog_changes import detect_changes
from majesty_cam.manager.build import MANAGER_OUTPUT_SENTINEL
from majesty_cam.manager.controller import ManagerController
from majesty_cam.manager.catalog import Catalog,CatalogEntry,CatalogKind,CatalogSource
from majesty_cam.manager.paths import detect_manager_paths
from majesty_cam.manager.compatibility import CompatibilityRegistry

ONE="11111111-1111-1111-1111-111111111111"
TWO="22222222-2222-2222-2222-222222222222"

class PresetTests(unittest.TestCase):
    def test_presets_keep_choices_and_cached_package(self):
        with TemporaryDirectory() as temp:
            root=Path(temp)
            target=root/"Mods/Majesty Mod Manager - Merged"
            target.mkdir(parents=True)
            (target/MANAGER_OUTPUT_SENTINEL).write_text("fixture")
            (target/"evidence.txt").write_text("prepared A")
            paths=SimpleNamespace(profile_path=root/"manager/profile.json", merged_output_root=target)
            state=ManagerProfile(selections={ONE:True},order=(ONE,))
            store=Presets(paths)
            a=store.save(state,name="My usual mods")
            with patch("majesty_cam.manager.presets.read_managed_build",return_value=SimpleNamespace(fingerprint="A")):
                store.retain_build(state,"A")
                b=store.save(state.with_selections({TWO:True},(TWO,)),name="Other mods")
                (target/"evidence.txt").write_text("prepared B")
                store.retain_build(state.with_selections({TWO:True},(TWO,)),"A")
                with patch("majesty_cam.manager.build._is_manager_owned_output",return_value=True):
                    loaded=store.activate(a)
                self.assertEqual(loaded.selections,{ONE:True})
                self.assertEqual((target/"evidence.txt").read_text(),"prepared A")
                self.assertFalse(store.dirty(loaded.with_selections({ONE:True,TWO:False},(ONE,TWO))))
                self.assertTrue(store.dirty(loaded.with_selections({ONE:False,TWO:True},(ONE,TWO))))
            pending=store.root/"pending-switch.json"
            pending.write_text(json.dumps({"id": b}))
            from majesty_cam.manager.presets import recover_switch
            with patch("majesty_cam.manager.presets.read_managed_build",return_value=SimpleNamespace(fingerprint="A")),                  patch("majesty_cam.manager.build._is_manager_owned_output",return_value=True):
                recover_switch(paths)
            self.assertFalse(pending.exists())
            self.assertEqual(load_profile(paths.profile_path).selections,{TWO:True})
            for index in range(3):store.save(state,name=f"Extra {index}")
            with self.assertRaisesRegex(ValueError,"five"):
                store.save(state,name="Overflow")
            self.assertEqual(Presets(paths).state["active"],store.state["active"])

    def test_badges_expire_and_updates_are_detected(self):
        with TemporaryDirectory() as temp:
            root=Path(temp); package=root/"mod";package.mkdir()
            manifest=package/"mod.mmxml";manifest.write_text("initial")
            paths=SimpleNamespace(profile_path=root/"state/profile.json")
            entry=CatalogEntry(ONE,ONE,"Example",CatalogKind.STANDARD,CatalogSource.WORKSHOP,
                               package,manifest,False,False)
            self.assertEqual(detect_changes(paths,Catalog(())),{})
            self.assertEqual(detect_changes(paths,Catalog((entry,))),{ONE:"NEW"})
            self.assertEqual(detect_changes(paths,Catalog((entry,))),{})
            manifest.write_text("changed package data")
            self.assertEqual(detect_changes(paths,Catalog((entry,))),{ONE:"UPDATED"})
            self.assertEqual(detect_changes(paths,Catalog((entry,))),{})

    def test_classic_ignores_merge_plan_and_conflict_blockers(self):
        from test_manager_controller import _manager_paths
        from majesty_cam.manager.build import BuildIssue
        from dataclasses import replace
        with TemporaryDirectory() as temp:
            paths=_manager_paths(Path(temp))
            c=ManagerController(paths=paths,registry=CompatibilityRegistry(specs={}))
            entry=CatalogEntry(ONE,ONE,"Old mod",CatalogKind.STANDARD,CatalogSource.LOCAL_MODS,
                               paths.local_mods_root,paths.local_mods_root/"old.mmxml",False,False)
            c.catalog=Catalog((entry,));c.selections={ONE:True};c.order=(ONE,)
            c.plan=replace(c.plan,issues=(BuildIssue("overlap","intentional overlap"),))
            with patch.object(c,"snapshot",return_value=SimpleNamespace(can_launch=False,can_classic_launch=True)), \
                 patch.object(c,"_qol_cache_is_current",return_value=True), \
                 patch("majesty_cam.manager.controller.launch_majesty") as launch:
                launch.return_value=SimpleNamespace(warnings=())
                c._managed_build_cache_loaded=True
                c.launch(classic=True)
                self.assertEqual(launch.call_args.args[1],[ONE])
                self.assertEqual(launch.call_args.kwargs["capability_manifest"],paths.empty_runtime_capability_manifest)
                self.assertIsNone(launch.call_args.kwargs["acquired_profile_lock"])


    def test_profiles_restore_install_dataset_and_launch_mode(self):
        from dataclasses import replace
        from majesty_cam.manager.paths import read_game_executable_selection
        from majesty_cam.manager.quest_dataset import enabled, set_enabled
        with TemporaryDirectory() as temp:
            root=Path(temp)
            paths=SimpleNamespace(profile_path=root/"manager/profile.json",
                                  merged_output_root=root/"Mods/Majesty Mod Manager - Merged")
            paths.merged_output_root.parent.mkdir()
            steam=root/"Steam/MajestyHD.exe"
            gog=root/"GOG/MajestyHD.exe"
            for exe in (steam,gog):
                exe.parent.mkdir()
                exe.write_bytes(b"fixture")
            store=Presets(paths)
            original=ManagerProfile(selections={ONE:True},game_executable=str(steam),
                                    expansion_content=False,classic_launch=True)
            expansion=replace(original,game_executable=str(gog),expansion_content=True,
                              classic_launch=False)
            a=store.save(original,name="Original")
            b=store.save(expansion,name="Expansion")
            with patch("majesty_cam.manager.presets.detect_majesty_branch",return_value=object()):
                for identity,expected in ((a,original),(b,expansion),(a,original)):
                    restored=store.activate(identity)
                    self.assertEqual(restored,expected)
                    self.assertEqual(read_game_executable_selection(root/"manager/game-executable.txt"),
                                     Path(expected.game_executable))
                    self.assertEqual(enabled(paths),expected.expansion_content)
                    self.assertFalse(store.dirty(expected))
                    self.assertTrue(store.dirty(replace(expected,expansion_content=not expected.expansion_content)))
            old_index=store.index.read_bytes()
            gog.unlink()
            with self.assertRaises(FileNotFoundError):
                store.activate(b)
            self.assertEqual(store.index.read_bytes(),old_index)
            self.assertEqual(load_profile(paths.profile_path),original)
            self.assertFalse(enabled(paths))

    def test_controller_rebinds_services_before_scanning_restored_profile(self):
        from test_manager_controller import _manager_paths
        from majesty_cam.manager.qol_service import GOG_BRANCH
        from majesty_cam.manager.quest_dataset import enabled
        with TemporaryDirectory() as temp:
            root=Path(temp)
            paths=_manager_paths(root)
            executable=root/"Other Install/MajestyHD.exe"
            executable.parent.mkdir()
            executable.write_bytes(b"fixture")
            c=ManagerController(paths=paths,registry=CompatibilityRegistry(specs={}))
            chosen=ManagerProfile(game_executable=str(executable),expansion_content=True)
            store=Presets(paths);identity=store.save(chosen,name="Other install")
            def scan(**kwargs):
                self.assertEqual(c.paths.game_executable,executable)
                self.assertEqual(c.qol_service.game_executable,executable)
                self.assertTrue(enabled(c.paths))
                return "snapshot"
            with patch("majesty_cam.manager.presets.detect_majesty_branch",return_value=GOG_BRANCH),                  patch("majesty_cam.manager.controller.detect_majesty_branch",return_value=GOG_BRANCH),                  patch.object(c,"scan",side_effect=scan):
                self.assertEqual(c.activate_profile(identity),"snapshot")
