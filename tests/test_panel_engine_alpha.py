import os
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch, Mock

from majesty_cam.panel_engine import (parse_behavior, behaviors, rewrite_table, find_panels,
    PanelEngineError, PANEL_SERVICE, ACTION_SERVICE)
from majesty_cam.strt import StrtTable, StrtRecord, parse_strt
from majesty_cam.engine_dependencies import (PatchRequirement, RequirementEvidence,
    parse_requirements, aggregate, missing, from_verified_sources, from_effective_resources)


def table(*texts):
    return StrtTable(b"\x00\x02", tuple(StrtRecord(i + 1, text.encode("latin1")) for i, text in enumerate(texts)))


class PanelEngineTests(unittest.TestCase):
    def test_native_only_declarations_keep_expansion_standard_scope(self):
        import json
        from majesty_cam.cam import CamArchive,CamSection,CamEntry
        from majesty_cam.manager.catalog import scan_catalog,CatalogKind
        from majesty_cam.standard_scripts import read,for_dataset
        from majesty_cam.compose import inventory_package,SelectedMod,ComposeError
        from majesty_cam.package import load_package
        from test_manager_catalog import _write_mod,STANDARD_ID
        with TemporaryDirectory() as temporary, patch.dict(os.environ,{'MAJESTY_MANAGER_EDITION':'panel-engine-alpha'}):
            root=Path(temporary);package=root/'Native';(package/'Data').mkdir(parents=True)
            _write_mod(package,STANDARD_ID,'Expansion native panels',cam=True)
            manifest=package/'Mod.mmxml'
            manifest.write_text(manifest.read_text().replace('base="Any"','base="MajestyExpansion"')
                .replace('</Load>','<GPL><Target>Data/fixture.bcd</Target></GPL></Load>'))
            from test_bcd import compiled
            from majesty_cam.gpl import DefinitionKind
            (package/'Data/fixture.bcd').write_bytes(compiled((DefinitionKind.FUNCTION,'Example')))
            cam=CamArchive((CamSection(b'SMNU',(CamEntry(b'AB01'.ljust(20,b'\0'),b'layout'),)),
                            CamSection(b'STRT',(CamEntry(b'AB01'.ljust(20,b'\0'),table('WE|1|BASE|AP10').to_bytes()),))))
            (package/'Data/Content.cam').write_bytes(cam.to_bytes())
            definition=dict(schema_version=3,mod_id=STANDARD_ID,internal_name='Native',display_name='Native',
                custom_buildings=[],runtime_features=[],external_patches=[
                    {'service':PANEL_SERVICE},{'service':ACTION_SERVICE}])
            path=package/'mod-definition.json';path.write_text(json.dumps(definition))
            entry=scan_catalog(local_mods_root=root).entries[0]
            self.assertEqual(entry.kind,CatalogKind.STANDARD)
            self.assertTrue(entry.selectable)
            provider=read(entry)
            self.assertEqual(provider.package.datasets[0].base,'MajestyExpansion')
            self.assertEqual(for_dataset((provider,),'majesty'),())
            # Metadata does not bypass strict scoped Merge inventory admission.
            with self.assertRaisesRegex(ComposeError,'scoped CAM/GPL'):
                inventory_package(SelectedMod('native',load_package(package)))
            definition['custom_buildings']=[dict(local_name='Example',controller_base='AP10',panel_resource_template='AP10')]
            path.write_text(json.dumps(definition))
            self.assertEqual(scan_catalog(local_mods_root=root).entries[0].kind,CatalogKind.MERGE)
            definition['custom_buildings']=[];definition['mod_id']='22222222-2222-2222-2222-222222222222'
            path.write_text(json.dumps(definition))
            self.assertEqual(scan_catalog(local_mods_root=root).entries[0].kind,CatalogKind.MERGE)

    def test_native_engine_component_uses_standard_manifest_without_fake_metadata(self):
        from majesty_cam.cam import CamArchive,CamSection,CamEntry
        from majesty_cam.manager.catalog import scan_catalog,CatalogKind
        from test_manager_catalog import _write_mod,STANDARD_ID
        with TemporaryDirectory() as temporary:
            root=Path(temporary);package=root/'Native';(package/'Data').mkdir(parents=True)
            _write_mod(package,STANDARD_ID,'Native engine panel',cam=True)
            cam=CamArchive((CamSection(b'SMNU',(CamEntry(b'AB01'.ljust(20,b'\0'),b'layout'),)),
                            CamSection(b'STRT',(CamEntry(b'AB01'.ljust(20,b'\0'),table('WE|1|BASE|AP10').to_bytes()),))))
            (package/'Data/Content.cam').write_bytes(cam.to_bytes())
            with patch.dict(os.environ,{'MAJESTY_MANAGER_EDITION':'panel-engine-alpha'}):
                entry=scan_catalog(local_mods_root=root).entries[0]
                self.assertEqual(entry.kind,CatalogKind.STANDARD)
                self.assertTrue(entry.selectable)
            with patch.dict(os.environ,{'MAJESTY_MANAGER_EDITION':''}):
                entry=scan_catalog(local_mods_root=root).entries[0]
                self.assertEqual(entry.kind,CatalogKind.STANDARD)
                self.assertTrue(entry.selectable)
            self.assertFalse((package/'mod-definition.json').exists())

    def test_shared_standard_declarations_bind_only_the_selected_native_component(self):
        import json
        from majesty_cam.manager.engine_patches import discover
        one = '11111111-1111-1111-1111-111111111111'
        two = '22222222-2222-2222-2222-222222222222'
        three = '33333333-3333-3333-3333-333333333333'
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            data = dict(schema_version=3, mod_ids=[one,two], internal_name='Example',
                display_name='Example', custom_buildings=[], runtime_features=[],
                external_patches=[{'service':PANEL_SERVICE}])
            (root/'mod-definition.json').write_text(json.dumps(data), encoding='utf8')
            component = SimpleNamespace(datasets=(SimpleNamespace(base='Any', loads=()),))
            with patch('majesty_cam.manager.engine_patches.load_standard_component', return_value=component):
                selected = discover(SimpleNamespace(package_root=root,manifest_path=root/'example.mmxml',
                    content_id=two,display_name='Variant Two'))
                other = discover(SimpleNamespace(package_root=root,manifest_path=root/'example.mmxml',
                    content_id=three,display_name='Other'))
            self.assertEqual(selected.evidence[0].owner_id, two)
            self.assertEqual(selected.evidence[0].requirement.service, PANEL_SERVICE)
            self.assertEqual(other.evidence, ())

    def test_actual_named_merge_relocates_only_the_preferred_owners_typed_fields(self):
        from dataclasses import replace
        from test_compose import resource
        from majesty_cam.compose import merge_named_resources, ScopedNamedResourceResolution
        from majesty_cam.panel_engine_composition import text_relocator
        rows = table('Ordinary AB01 text', 'WE|1|PANEL|200|AB01', 'WE|1|LABEL|201|AB01')
        other = table('Other', 'WE|1|PANEL|200|AB01')
        first = replace(resource('one', b'AB01', rows.to_bytes()), section=b'STRT')
        second = replace(resource('two', b'AB01', other.to_bytes()), section=b'STRT')
        resources = (resource('one', b'AB01', b'layout'), resource('two', b'AB01', b'layout'), first, second)
        relocate = text_relocator(resources, (('one', b'AB01', b'CD01'), ('two', b'AB01', b'CD02')))
        entries, _ = merge_named_resources(resources, b'STRT', entry_transform=relocate,
            resolutions={(b'STRT', b'AB01'): ScopedNamedResourceResolution(first.entry, frozenset(('one','two')), 'one')})
        text = [r.text.decode('latin1') for r in parse_strt(entries[0].data).records]
        self.assertEqual(text, ['Ordinary AB01 text','WE|1|PANEL|200|CD01','WE|1|LABEL|201|AB01'])
        # Beta's default path never enters the optional adapter.
        unadapted, _ = merge_named_resources((first,), b'STRT')
        self.assertEqual(unadapted[0].data, rows.to_bytes())

    def test_ambiguous_resolution_owner_cannot_relocate_using_a_losing_namespace(self):
        from dataclasses import replace
        from test_compose import resource
        from majesty_cam.compose import merge_named_resources, ScopedNamedResourceResolution, ComposeError
        from majesty_cam.panel_engine_composition import text_relocator
        entry = table('WE|1|PANEL|200|AB01').to_bytes()
        resources = (resource('one', b'AB01', b'layout'), resource('two', b'AB01', b'layout'),
                     replace(resource('one', b'AB01', entry), section=b'STRT'),
                     replace(resource('two', b'AB01', entry), section=b'STRT'))
        relocate = text_relocator(resources, (('one', b'AB01', b'CD01'), ('two', b'AB01', b'CD02')))
        with self.assertRaisesRegex(ComposeError, 'selected owner'):
            merge_named_resources(resources, b'STRT', entry_transform=relocate,
                resolutions={(b'STRT',b'AB01'):ScopedNamedResourceResolution(resources[2].entry,frozenset(('one','two')))})

    def test_typed_remapping_preserves_prose_and_other_fields(self):
        source = table("Ordinary Price TX01 AB01 help", "WE|1|BASE|AP52",
            "WE|1|PANEL|200|AB01", "WE|1|TEXT|300|Price|Price AB01 TX01 = %d",
            "WE|1|TSEP|400|TX01|1000", "WE|1|TABLE|400|Units|500~1",
            "WE|1|LABEL|600|AB01 Price TX01")
        output = parse_strt(rewrite_table(source.to_bytes(), panels={"AB01":"CD02"},
            callbacks={"Price":"NewPrice", "Units":"NewUnits"},
            images={"TX01":"TY02"}, controls={"500":"501"}))
        text = [r.text.decode("latin1") for r in output.records]
        self.assertEqual(text[0], "Ordinary Price TX01 AB01 help")
        self.assertEqual(text[2], "WE|1|PANEL|200|CD02")
        self.assertEqual(text[3], "WE|1|TEXT|300|NewPrice|Price AB01 TX01 = %d")
        self.assertEqual(text[4], "WE|1|TSEP|400|TY02|1000")
        self.assertEqual(text[5], "WE|1|TABLE|400|NewUnits|501~1")
        self.assertEqual(text[6], "WE|1|LABEL|600|AB01 Price TX01")
        self.assertEqual([r.string_id for r in output.records], [r.string_id for r in source.records])
        self.assertEqual(rewrite_table(source.to_bytes()), source.to_bytes())

    def test_only_paired_effective_loaded_panels_supply_requirement(self):
        data = table("WE|1|CLASS|building", "WE|1|CLICK|200|Click").to_bytes()
        unused = {(b"STRT", b"AB01"):data}
        self.assertEqual(find_panels(unused), {})
        resolved = {**unused, (b"SMNU", b"AB01"):b"fixture layout"}
        result = from_effective_resources(resolved, owner_id="one", owner_name="One", dataset="MajestyExpansion")
        self.assertEqual(result[0].requirement.service, PANEL_SERVICE)
        self.assertEqual(result[0].dataset, "MajestyExpansion")
        # A winning stock/ordinary replacement has no WE dependency.
        resolved[b"STRT", b"AB01"] = table("Normal title").to_bytes()
        self.assertEqual(from_effective_resources(resolved, owner_id="one", owner_name="One", dataset="Any"), ())

    def test_malformed_or_unsupported_protocol_is_not_a_missing_patch(self):
        for text in ("WE|2|HIDE|200", "WE|1|CLASS|unknown", "WE|1|PANEL|0|AB01",
                     "WE|1|CLICK|200|" + "A" * 48, "WE|1|TABLE|200|Units|5~2"):
            with self.subTest(text=text), self.assertRaises(PanelEngineError):
                parse_behavior(text)
        with self.assertRaises(PanelEngineError):
            behaviors(table("WE|1|BASE|AP52", "WE|1|CLASS|building"))
        with self.assertRaises(PanelEngineError):
            behaviors(table(*("WE|1|TCOL|200|count|20" for _ in range(5))))

    def test_source_calls_exclude_comments_strings_and_noncall_symbols(self):
        context = dict(owner_id="one", owner_name="One", dataset="Any")
        self.assertEqual(from_verified_sources((("x.gpl", '// $SF_MapAction()\n"$SF_MapAction()"; $SF_MapAction;'),), **context), ())
        result = from_verified_sources((("x.gpl", "$SF_MapAction(\"flag\", what, spot, target, player, 500);"),), **context)
        self.assertEqual(result[0].requirement.service, ACTION_SERVICE)
        own='function SF_MapAction()\nbegin\nend SF_MapAction;\n'
        self.assertEqual(from_verified_sources((('own.gpl',own),('caller.gpl','$SF_MapAction();')),**context),())

    def test_version_union_preserves_mod_attribution(self):
        evidence = tuple(RequirementEvidence(PatchRequirement(PANEL_SERVICE, revision), owner, owner, "Any", "fixture")
                         for owner, revision in (("one", 1), ("two", 3)))
        result = aggregate(evidence)
        self.assertEqual(result[0][0].minimum_revision, 3)
        self.assertEqual(result[0][1], (("one","one"), ("two","two")))
        self.assertTrue(missing(evidence, {PANEL_SERVICE:2}))
        self.assertEqual(missing(evidence, {PANEL_SERVICE:3}), ())
        for raw in ([{"service":"unknown"}], [{"service":PANEL_SERVICE,"minimum_revision":True}]):
            with self.assertRaises(ValueError): parse_requirements(raw)

    def test_explicit_requirements_survive_package_serialization(self):
        from majesty_cam.package import parse_mod_definition, mod_definition_mapping
        for version in (2,3):
            data=dict(schema_version=version, mod_id="11111111-1111-1111-1111-111111111111",
                      internal_name="Example", display_name="Example", custom_buildings=[],
                      external_patches=[{"service":PANEL_SERVICE,"minimum_revision":2}])
            data['runtime_capabilities' if version==2 else 'runtime_features']=[]
            definition=parse_mod_definition(data)
            self.assertEqual(definition.external_patches,(PatchRequirement(PANEL_SERVICE,2),))
            self.assertEqual(parse_mod_definition(mod_definition_mapping(definition)),definition)

    def test_alpha_dependency_prompt_aggregates_without_editing_selection(self):
        from dataclasses import replace
        from test_manager_app import manager_app, _snapshot_with_required_qol
        from majesty_cam.manager.profile import ManagerProfile
        app=manager_app.QApplication.instance() or manager_app.QApplication([])
        with TemporaryDirectory() as temporary:
            root=Path(temporary)
            controller=SimpleNamespace(paths=SimpleNamespace(game_path=root/'Game',profile_path=root/'profile.json'),
                                       profile=ManagerProfile())
            with patch.dict(os.environ,{'MAJESTY_MANAGER_EDITION':'panel-engine-alpha'}), \
                 patch.object(manager_app.QTimer,'singleShot'):
                window=manager_app.ManagerWindow(controller)
            evidence=tuple(RequirementEvidence(PatchRequirement(service),owner,owner,'Any','fixture')
                for service,owner in ((PANEL_SERVICE,'One'),(PANEL_SERVICE,'Two'),(ACTION_SERVICE,'One')))
            window.snapshot=replace(_snapshot_with_required_qol('installed','installed'),
                                    selections={'one':True},engine_requirements=evidence)
            with patch.dict(os.environ,{'MAJESTY_MANAGER_EDITION':'panel-engine-alpha'}), \
                 patch.object(manager_app.QMessageBox,'exec',return_value=0), \
                 patch.object(manager_app.QMessageBox,'clickedButton',return_value=None):
                window._show_engine_dependencies()
            dialogs=window.findChildren(manager_app.QMessageBox)
            self.assertEqual(len(dialogs),1)
            self.assertIn('Custom Building Panels: One, Two',dialogs[0].text())
            self.assertIn('Scripted Ground Actions: One',dialogs[0].text())
            self.assertEqual(window.snapshot.selections,{'one':True})
            window.close()


class AlphaIsolationTests(unittest.TestCase):
    def test_output_guard_accepts_only_the_selected_edition_target(self):
        from majesty_cam.manager.build import _safe_manager_target,ManagerBuildError
        with TemporaryDirectory() as folder:
            mods=Path(folder)/'Mods'
            normal=mods/'Majesty Mod Manager - Merged'
            alpha=mods/'Majesty Mod Manager - Panel Engine Alpha'
            for edition,accepted,rejected in (('',normal,alpha),('panel-engine-alpha',alpha,normal)):
                with patch.dict(os.environ,{'MAJESTY_MANAGER_EDITION':edition}):
                    self.assertEqual(_safe_manager_target(mods,accepted),accepted.resolve())
                    for bad in (rejected,mods/'Unrelated',mods/'nested'/accepted.name):
                        with self.assertRaises(ManagerBuildError):_safe_manager_target(mods,bad)
            self.assertFalse(mods.exists())

    def test_alpha_cleanup_does_not_claim_normal_manager_staging(self):
        from majesty_cam.manager.build import _cleanup_stale_manager_artifacts
        with TemporaryDirectory() as folder,patch.dict(os.environ,{'MAJESTY_MANAGER_EDITION':'panel-engine-alpha'}):
            mods=Path(folder)
            normal=mods/'.MajestyModManager-build-normal'
            alpha=mods/'.MajestyModManagerAlpha-build-alpha'
            normal.mkdir();alpha.mkdir()
            _cleanup_stale_manager_artifacts(mods,mods/'Majesty Mod Manager - Panel Engine Alpha')
            self.assertTrue(normal.is_dir())
            self.assertFalse(alpha.exists())

    def test_native_status_cache_tracks_the_alpha_executable(self):
        from majesty_cam.manager.startup_cache import qol_input_signature
        from majesty_cam.manager.qol_service import QolService
        from majesty_cam.manager.alpha_executable import target_for
        with TemporaryDirectory() as temporary, patch.dict(os.environ,{'MAJESTY_MANAGER_EDITION':'panel-engine-alpha'}):
            root=Path(temporary);source=root/'MajestyHD.exe';source.write_bytes(b'original')
            service=QolService(repo_root=root,game_executable=source)
            initial=qol_input_signature(service)
            target_for(source).write_bytes(b'alpha')
            self.assertNotEqual(initial,qol_input_signature(service))
            self.assertEqual(source.read_bytes(),b'original')

    def test_all_manager_owned_state_is_in_alpha_namespace(self):
        from majesty_cam.manager.profile import default_profile_path, canonical_remembered_path
        from majesty_cam.manager.paths import detect_manager_paths, game_executable_selection_path
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            args = dict(repo_root=root, documents_root=root/"Documents", local_appdata=root/"AppData", game_path=root/"Game")
            with patch.dict(os.environ, {"MAJESTY_MANAGER_EDITION":""}):
                normal = detect_manager_paths(**args)
            with patch.dict(os.environ, {"MAJESTY_MANAGER_EDITION":"panel-engine-alpha"}):
                alpha = detect_manager_paths(**args)
                self.assertIn("MajestyModManagerPanelEngineAlpha", str(alpha.profile_path))
                self.assertNotEqual(alpha.profile_path, normal.profile_path)
                self.assertNotEqual(alpha.remembered_path, normal.remembered_path)
                self.assertNotEqual(alpha.merged_output_root, normal.merged_output_root)
                self.assertEqual(alpha.merged_output_root.parent,alpha.local_mods_root)
                self.assertNotEqual(alpha.launch_executable,normal.game_executable)
                self.assertEqual(game_executable_selection_path(root/"AppData").parent, alpha.profile_path.parent)
                self.assertEqual(canonical_remembered_path(root/"AppData").parent, alpha.profile_path.parent)
            self.assertFalse(alpha.profile_path.exists())
            self.assertFalse(alpha.merged_output_root.exists())

    def test_missing_native_inputs_cannot_launch_or_write_preferences(self):
        from majesty_cam.manager.launch import launch_majesty, ManagerLaunchError
        with TemporaryDirectory() as temporary, patch.dict(os.environ, {"MAJESTY_MANAGER_EDITION":"panel-engine-alpha"}), \
             patch("majesty_cam.manager.launch.write_remembered_mods") as write, \
             patch("majesty_cam.manager.launch.subprocess.Popen") as start:
            with self.assertRaises(ManagerLaunchError):
                launch_majesty(SimpleNamespace(repo_root=Path(temporary),game_executable=Path(temporary)/'MajestyHD.exe'), (), capability_manifest=Path("unused"),
                    runtime_feature_registry=Path("unused"), controller_registry=Path("unused"),
                    engine_requirements=(RequirementEvidence(PatchRequirement(PANEL_SERVICE), 'fixture', 'Fixture', 'Any', 'fixture'),))
            write.assert_not_called()
            start.assert_not_called()

    def test_optional_engine_rows_are_not_global_requirements(self):
        from majesty_cam.manager.qol_service import QolService, QOL_PATCHES
        with patch.dict(os.environ, {"MAJESTY_MANAGER_EDITION":"panel-engine-alpha"}):
            service = QolService(repo_root=Path("."), game_executable=Path("MajestyHD.exe"))
        optional = [spec for spec in service.specs if spec not in QOL_PATCHES]
        self.assertEqual(len(optional), 2)
        self.assertTrue(all(not spec.required_by_manager for spec in optional))
