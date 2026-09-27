from dataclasses import replace
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

from majesty_cam.compose import (GplComposeResult, _build_manifest, validate_composed_package,
                                  prepare_gpl_bundle, ComposeError)
from majesty_cam.gpl import parse_gpl, SemanticMergeResult, DefinitionKind
from majesty_cam.scoped_output import (partition, source_items, scoped_mod_id,
                                      load_generated_bundle, audit_scope_dependencies)
from majesty_cam.standard_scripts import Providers
from majesty_cam.dataset_dependencies import DatasetSymbols, close_dataset_dependencies
from majesty_cam.package import PackageFormatError, load_package
from majesty_cam.manager.build import (ManagerBuildResult, _remaining_generated_slots,
    refresh_standard_script_inputs, _generated_file_inventory, read_managed_build, MANAGER_OUTPUT_SENTINEL)
from majesty_cam.manager.controller import ManagerController
from majesty_cam.manager.compatibility import CompatibilityRegistry
from majesty_cam.manager.profile import normalize_guid
from majesty_cam.intent_text import INTENT_REGISTRY_RELATIVE_PATH, encode_intent_registry
from majesty_cam.runtime_capabilities import (RUNTIME_CAPABILITY_MANIFEST_RELATIVE_PATH,
                                             encode_runtime_capability_manifest)
from majesty_cam.runtime_features import RUNTIME_FEATURE_REGISTRY_RELATIVE_PATH, encode_runtime_feature_registry
from majesty_cam.stock_controller_registry import (CONTROLLER_REGISTRY_RELATIVE_PATH,
    encode_stock_controller_registry, resolve_stock_controller_registry)
from test_compose import _generated_cam_paths
from test_standard_scripts import provider
from test_manager_controller import (_manager_paths, _merge_plan, _managed_build,
    _set_required_qol_state, STANDARD_ID, GENERATED_ID, HAUNT_ID)


def result(text):
    return GplComposeResult(SemanticMergeResult(parse_gpl(text).items, ()).emit_project_source_set(), (), (), (), ())


def function(name, value=1):
    return f'function {name}() is integer\nbegin\nreturn {value};\nend\n'


COMMON_ID = '{00000000-0000-0000-0000-000000000001}'


def package_fixture(root, common, patches=()):
    cams = _generated_cam_paths(root)
    (root/'Data/Descriptions.xml').write_text('<Descriptions/>')
    for scope, output in (('Any', common), *patches):
        if not output.source_set.files:
            continue
        directory = root/'GPL' if scope == 'Any' else root/'GPL'/scope
        directory.mkdir(parents=True, exist_ok=True)
        for name, text in output.source_set.files.items():
            (directory/name).write_text(text)
        (root/'Data'/('Merged.bcd' if scope == 'Any' else f'Merged-{scope}.bcd')).write_bytes(b'compiled fixture')
    manifest = root/'CAMManager-fixture.mmxml'
    manifest.write_bytes(_build_manifest(mod_id=COMMON_ID, internal_name='Fixture', display_name='Fixture',
        cam_filenames=tuple(p.absolute_path.name for p in cams), description_filename='Descriptions.xml',
        source_set=common.source_set, scoped_sources=tuple((s, r.source_set) for s, r in patches)))
    (root/'mod-definition.json').write_text(json.dumps(dict(schema_version=2, mod_id=COMMON_ID,
        internal_name='Fixture', display_name='Fixture', custom_buildings=[], runtime_capabilities=[])))
    for path, data in (
        (INTENT_REGISTRY_RELATIVE_PATH, encode_intent_registry(())),
        (RUNTIME_CAPABILITY_MANIFEST_RELATIVE_PATH, encode_runtime_capability_manifest(())),
        (RUNTIME_FEATURE_REGISTRY_RELATIVE_PATH, encode_runtime_feature_registry(())),
        (CONTROLLER_REGISTRY_RELATIVE_PATH, encode_stock_controller_registry(resolve_stock_controller_registry((), {}))),
    ):
        target = root/Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    return manifest


class ScopedOutputTests(unittest.TestCase):
    def test_shared_and_differing_definitions_are_partitioned_without_loss(self):
        a = result(function('Shared') + function('Changed', 10) + function('BaseOnly'))
        b = result(function('Shared') + function('Changed', 20) + function('ExpansionOnly'))
        bundle = partition(a, b)
        self.assertEqual([i.name for i in source_items(bundle.common.source_set)], ['Shared'])
        self.assertEqual([scope for scope, _ in bundle.patches], ['Majesty', 'MajestyExpansion'])
        for original, (_, delta) in zip((a, b), bundle.patches):
            combined = {i.key:i.text for output in (bundle.common, delta) for i in source_items(output.source_set)}
            self.assertEqual(combined, {i.key:i.text for i in source_items(original.source_set)})

    def test_only_nonsemantic_unicode_comments_can_be_normalized_for_compiler(self):
        from majesty_cam.compose import _compiler_source_bytes
        source = '// \u2b50\n' + function('Example')
        self.assertEqual(_compiler_source_bytes(source), ('// ?\n' + function('Example')).encode('cp1252'))
        with self.assertRaisesRegex(ComposeError, 'string literal'):
            _compiler_source_bytes('expression #Title "\u2b50"\n')

    def test_equal_views_emit_no_patches_and_one_sided_definition_is_not_shared(self):
        a = result(function('Shared'))
        self.assertEqual(partition(a, a).patches, ())
        one = partition(a, result(function('Shared') + function('Extra')))
        self.assertEqual([s for s, _ in one.patches], ['MajestyExpansion'])
        self.assertNotIn('Extra', one.common.source_set.gpl_text)

    def test_no_standard_scripts_preserves_single_composition_fast_path(self):
        a = result(function('Common'))
        with patch('majesty_cam.compose.prepare_final_gpl_resources', return_value=a) as prepare:
            bundle = prepare_gpl_bundle(Path('.'), (), standard_script_inputs=())
        self.assertEqual(bundle.common, a)
        self.assertEqual(bundle.patches, ())
        prepare.assert_called_once_with(Path('.'), ())

    def test_stock_imports_are_needed_only_in_original_quest_view(self):
        caller = SemanticMergeResult(parse_gpl('function Call()\nbegin\n$Extra();\nend\n').items, ())
        helper = parse_gpl(function('Extra')).items[0]
        stock = DatasetSymbols(frozenset(), {}, frozenset(), frozenset(('extra',)), lambda _: helper)
        self.assertEqual(close_dataset_dependencies(caller, stock, dataset='majestyexpansion'), caller)
        self.assertEqual(close_dataset_dependencies(caller, stock, dataset='majesty').items[-1], helper)

    def test_native_opposite_scope_helper_is_not_silently_imported(self):
        native = replace(provider(function('NativeOnly')), bases=('majestyexpansion',))
        providers = Providers((native,), None, Path('compiler'), 'majesty')
        stock = DatasetSymbols(frozenset(), {}, frozenset(), frozenset())
        for text in ('function Call()\nbegin\n$NativeOnly();\nend\n',
                     'function Call(agent unit)\nbegin\nunit\'s "Script" = $NativeOnly;\nend\n'):
            with self.assertRaisesRegex(ValueError, 'available only in the other dataset'):
                audit_scope_dependencies(result(text), providers, stock)
        audit_scope_dependencies(result(function('Call')), providers, stock)
        audit_scope_dependencies(result('function Call()\ndeclare\ninteger NativeOnly;\nbegin\n'
                                        'NativeOnly = 1;\nend\n'), providers, stock)

    def test_manifest_and_validation_cover_both_effective_views(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            bundle = partition(result(function('Shared') + function('Change', 1)),
                               result(function('Shared') + function('Change', 2)))
            package_fixture(root, bundle.common, bundle.patches)
            packages = load_generated_bundle(root)
            self.assertEqual([p.datasets[0].base for p in packages], ['Any', 'Majesty', 'MajestyExpansion'])
            self.assertEqual(packages[1].mod_id, scoped_mod_id(COMMON_ID, 'Majesty'))
            with self.assertRaisesRegex(PackageFormatError, 'exactly one Mod'):
                load_package(root)
            with patch('majesty_cam.compose._validate_generated_runtime_evidence') as evidence:
                validation = validate_composed_package(root)
            self.assertEqual(len(validation['generated_records']), 3)
            self.assertEqual(evidence.call_count, 2)
            self.assertTrue(all(len(c.args[0].gpl_loads) == 2 for c in evidence.call_args_list))

    def test_empty_common_has_no_dummy_gpl_and_still_validates(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            package_fixture(root, result(''), (('MajestyExpansion', result(function('Extra'))),))
            self.assertFalse(load_generated_bundle(root)[0].datasets[0].loads[0].gpl)
            self.assertFalse((root/'Data/Merged.bcd').exists())
            validate_composed_package(root)

    def test_duplicate_common_and_patch_symbol_is_rejected(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            package_fixture(root, result(function('Same')), (('Majesty', result(function('Same', 2))),))
            with self.assertRaisesRegex(ComposeError, 'duplicate a definition'):
                validate_composed_package(root)

    def test_patch_identity_scope_and_path_tampering_are_rejected(self):
        for change in ('id', 'scope', 'path', 'duplicate', 'order'):
            with self.subTest(change=change), TemporaryDirectory() as tmp:
                root = Path(tmp)
                manifest = package_fixture(root, result(function('Shared')), (
                    ('Majesty', result(function('Change'))), ('MajestyExpansion', result(function('Change', 2)))))
                xml = ET.fromstring(manifest.read_bytes())
                node = xml.findall('Mod')[1]
                if change == 'id': node.set('id', '{00000000-0000-0000-0000-000000000002}')
                if change == 'scope': node.find('./DataConfiguration/Dataset').set('base', 'Any')
                if change == 'path': node.find('.//GPL/Target').text = 'Data/Merged.bcd'
                if change == 'duplicate': xml.append(node)
                if change == 'order': xml.remove(node); xml.append(node)
                manifest.write_bytes(ET.tostring(xml))
                with self.assertRaises(PackageFormatError): load_generated_bundle(root)

    def test_scoped_ids_launch_after_common_and_restore_sources(self):
        with TemporaryDirectory() as tmp:
            paths = _manager_paths(Path(tmp), runtime_ready=True)
            controller = ManagerController(paths=paths, registry=CompatibilityRegistry(specs={}))
            controller.plan = _merge_plan(paths, fingerprint='current')
            _set_required_qol_state(controller, installed=True)
            ids = (GENERATED_ID, *(normalize_guid(scoped_mod_id(GENERATED_ID, s)) for s in ('Majesty', 'MajestyExpansion')))
            managed = replace(_managed_build(paths, fingerprint='current'), generated_mod_ids=ids)
            managed.runtime_feature_registry.write_bytes(encode_runtime_feature_registry(()))
            managed.controller_registry.write_bytes(encode_stock_controller_registry(resolve_stock_controller_registry((), {})))
            with patch('majesty_cam.manager.controller.read_managed_build', return_value=managed), \
                 patch('majesty_cam.manager.controller._require_current_plan_sources'), \
                 patch('majesty_cam.manager.controller.launch_majesty') as launch:
                controller.launch()
            self.assertEqual(launch.call_args.args[1], [STANDARD_ID, *ids])
            self.assertEqual(controller._managed_build_result_from_cache(
                controller._managed_build_cache_payload(managed)), managed)
            (paths.merged_output_root/MANAGER_OUTPUT_SENTINEL).write_text(json.dumps({
                'mod_id': GENERATED_ID, 'generated_mod_ids': ids, 'selected_source_ids': [HAUNT_ID]}))
            self.assertEqual(controller._expand_generated_profile_ids((ids[2],)), (HAUNT_ID,))

    def test_active_id_limit_includes_every_generated_record(self):
        with TemporaryDirectory() as tmp:
            plan = _merge_plan(_manager_paths(Path(tmp)), fingerprint='current')
            plan = replace(plan, selected_standard_ids=tuple(str(i) for i in range(24)))
            self.assertEqual(_remaining_generated_slots(plan), 2)

    def test_owned_bundle_readback_requires_scope_report_and_every_file(self):
        import hashlib
        for scoped in (False, True):
            with self.subTest(scoped=scoped), TemporaryDirectory() as tmp:
                root = Path(tmp)
                package_fixture(root, result(function('Common')),
                    (('MajestyExpansion', result(function('Extra'))),) if scoped else ())
                packages = load_generated_bundle(root)
                ids = [normalize_guid(p.mod_id) for p in packages]
                def record(path, **fields):
                    return dict(path=str(path).replace('\\', '/'),
                                sha256=hashlib.sha256((root/path).read_bytes()).hexdigest(), **fields)
                capability = record(Path(RUNTIME_CAPABILITY_MANIFEST_RELATIVE_PATH), record_count=0)
                feature = record(Path(RUNTIME_FEATURE_REGISTRY_RELATIVE_PATH), name_generator_count=0, enchantment_row_count=0)
                controller = record(CONTROLLER_REGISTRY_RELATIVE_PATH, record_count=0)
                report = {'runtime': dict(capabilities=[], capability_manifest=capability,
                                          feature_registry=feature, controller_registry=controller)}
                if scoped:
                    report['generated_records'] = [dict(mod_id=p.mod_id, scope=p.datasets[0].base) for p in packages]
                report_path = root/'CAM-MERGE-REPORT.json'
                report_path.write_text(json.dumps(report))
                sentinel = dict(schema_version=5 if scoped else 4, fingerprint='fixture', mod_id=ids[0],
                    selected_source_ids=[], intent_registry=record(Path(INTENT_REGISTRY_RELATIVE_PATH), record_count=0),
                    capability_manifest=capability, runtime_feature_registry=feature, controller_registry=controller,
                    generated_files=_generated_file_inventory(root))
                if scoped: sentinel['generated_mod_ids'] = ids
                (root/MANAGER_OUTPUT_SENTINEL).write_text(json.dumps(sentinel))
                loaded = read_managed_build(root)
                self.assertIsNotNone(loaded)
                self.assertEqual(loaded.active_mod_ids, tuple(ids))
                if scoped:
                    (root/'Data/Merged-MajestyExpansion.bcd').write_bytes(b'altered')
                    self.assertIsNone(read_managed_build(root))


if __name__ == '__main__':
    unittest.main()
