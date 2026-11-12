"""Updated SDK data uses ordinary native discovery, without author sidecars."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from majesty_cam.panel_engine import parse_behavior, rewrite_table, PanelEngineError
from majesty_cam.strt import parse_strt
from majesty_cam.engine_dependencies import (from_effective_resources, from_verified_sources,
    missing, PANEL_SERVICE, ACTION_SERVICE)
from test_panel_engine_alpha import table


class UpdatedProtocol(unittest.TestCase):
    def test_classic_launch_derives_native_calls_only_after_loaded_source_proof(self):
        from types import SimpleNamespace as N
        from unittest.mock import patch
        from majesty_cam.cam import CamArchive,CamSection,CamEntry
        from majesty_cam.gpl import parse_gpl,DefinitionKind
        from majesty_cam.manager.catalog import scan_catalog
        from majesty_cam.manager.engine_patches import discover
        from majesty_cam.manager.controller import ManagerController
        from test_manager_catalog import _write_mod,STANDARD_ID
        from test_bcd import compiled
        with TemporaryDirectory() as folder:
            root=Path(folder); package=root/'Mods/Native'; (package/'Data').mkdir(parents=True)
            _write_mod(package,STANDARD_ID,'Native engine',cam=True)
            manifest=package/'Mod.mmxml'
            manifest.write_text(manifest.read_text().replace('</Load>',
                '<GPL><Target>Data/native.bcd</Target></GPL></Load>'))
            (package/'Data/native.bcd').write_bytes(compiled((DefinitionKind.FUNCTION,'Choose')))
            cam=CamArchive((CamSection(b'SMNU',(CamEntry(b'PN01'.ljust(20,b'\0'),b'layout'),)),
                CamSection(b'STRT',(CamEntry(b'PN01'.ljust(20,b'\0'),table('WE|1|BKG|1001|ART1').to_bytes()),))))
            (package/'Data/Content.cam').write_bytes(cam.to_bytes())
            entry,=scan_catalog(local_mods_root=root/'Mods').entries
            source=parse_gpl('function Choose(agent Who)\ndeclare coordinate Spot;\nbegin\n$SF_UnexploredArea(Who,64,Spot);\nend Choose;')
            source_path=package/'loaded.gpl'; source_path.write_text(source.text)
            compiler=root/'Game/SDK/Gplbcc.exe'; compiler.parent.mkdir(parents=True);compiler.write_bytes(b'compiler fixture')
            provider=N(items={item.key:item for item in source.items},paths=(source_path,),
                package=N(datasets=(N(base='Any'),)),loads=(N(target=N(relative_path='Data/native.bcd'),
                    discovery_directories=(),discovery_files=()),))
            with patch('majesty_cam.standard_scripts.read',return_value=provider), \
                    patch('majesty_cam.standard_scripts.verify',return_value=True) as prove:
                data=discover(entry)
                self.assertFalse(any(e.requirement.service==ACTION_SERVICE for e in data.evidence))
                prove.assert_not_called()
                controller=ManagerController.__new__(ManagerController)
                controller.paths=N(game_path=root/'Game'); controller.catalog=N(entries=(entry,))
                controller.selections={entry.content_id:True};controller._engine_dependency_cache={}
                evidence,_=controller._engine_dependencies(classic=True)
                self.assertEqual({e.requirement.service:e.requirement.minimum_revision for e in evidence},
                    {PANEL_SERVICE:3,ACTION_SERVICE:2})
                self.assertEqual(prove.call_count,1)
                controller._engine_dependencies(classic=True)
                self.assertEqual(prove.call_count,1)  # no repeated compile/read during rendering
            with patch('majesty_cam.standard_scripts.read',return_value=provider), \
                    patch('majesty_cam.standard_scripts.verify',return_value=False):
                result=discover(entry,compiler=compiler)
                self.assertFalse(any(e.requirement.service==ACTION_SERVICE for e in result.evidence))

    def test_script_panel_collision_rejects_only_the_unsafe_owner_and_native_call(self):
        from majesty_cam.panel_engine_composition import validate_script_panel_references
        from majesty_cam.gpl import parse_gpl
        def parsed(body):
            return (parse_gpl('function Choose(agent Who)\nbegin\n'+body+'\nend Choose;'),)
        renames=(('one',b'AB01',b'CD01'),)
        for body in ('$SF_SetWindow(Who,"AB01");','$SF_SetWindow(Who,ChosenWindow);',
                     r'$SF_SetWindow(Who,"\x41B01");'):
            with self.subTest(body=body),self.assertRaisesRegex(PanelEngineError,'SF_SetWindow'):
                validate_script_panel_references({'one':parsed(body)},renames)
        for body in ('$SF_SetWindow(Who,"EF01");','$SF_SetWindow(Who,(("EF01")));',
                     '// $SF_SetWindow(Who,"AB01");\n$DebugOut("AB01");',
                     '$DebugOut("$SF_SetWindow(Who,AB01)");'):
            validate_script_panel_references({'one':parsed(body)},renames)
        validate_script_panel_references({'two':parsed('$SF_SetWindow(Who,"AB01");')},renames)
        validate_script_panel_references({'one':parsed('$SF_SetWindow(Who,"AB01");')},())
        own=parse_gpl('function SF_SetWindow(agent Who,string Label)\nbegin\nend SF_SetWindow;')
        validate_script_panel_references({'one':(*parsed('$SF_SetWindow(Who,"AB01");'),own)},renames)

    def test_production_text_merge_checks_the_script_reference_before_renaming(self):
        from types import SimpleNamespace as N
        from unittest.mock import patch
        from majesty_cam.gpl import parse_gpl
        from majesty_cam.compose import merge_text_resources,ComposeError
        source=parse_gpl('function Choose(agent Who)\nbegin\n$SF_SetWindow(Who,"AB01");\nend Choose;')
        inventory=N(selected=N(alias='one'),resources=(),semantic_sources=(source,))
        with patch('majesty_cam.compose._dialog_renames',return_value=(('one',b'AB01',b'CD01'),)):
            with self.assertRaisesRegex(ComposeError,'SF_SetWindow targets renamed panel'):
                merge_text_resources(Path('.'),(inventory,),external_panel_behaviors=True)

    def test_new_kinds_have_typed_references_and_preserve_literals(self):
        records = (
            'WE|1|BKG|1001|ART1',
            'WE|1|PICTURE|200|@190206017|ART1',
            'WE|1|TEXTPICK|201|PickText|ART1~PickText',
            'WE|1|HINTPICK|201|@190206017|off~on',
            'WE|1|RTEXT|202|#|Row %d %t',
            'WE|1|RTEXTPICK|202|RowPick|off~on',
            'WE|1|RICON|202|RowIcon|ART1',
            'WE|1|RHINT|202|@190206017|Row %d',
            'WE|1|RHINTPICK|202|#|off~on',
            'WE|1|TITLE|8005',
            'WE|1|SPELL|8730|SP01|ART1~1002~ART1 SP01~PickText~0',
            'WE|1|EFFECT|8731|EF01|~~Effect~~1',
            'WE|1|TABLE|202|*spells+all+anylevel|203~2~26~28',
            'WE|1|TCOL|202|#|20',
            'WE|1|TEXT|204|@190206017|Name %t',
            'WE|1|BAR|205|Value|@190206017',
        )
        source = table(*records).to_bytes()
        self.assertEqual(rewrite_table(source), source)
        changed = [row.text.decode('latin1') for row in parse_strt(rewrite_table(source,
            images={'ART1':'ART2'}, callbacks={'PickText':'NewPick'},
            controls={'1001':'1009','203':'209'}, attributes={'190206017':'190206018'},
            codes={'SP01':'SP02'})).records]
        self.assertEqual(changed[0], 'WE|1|BKG|1001|ART2')  # key is not a control
        self.assertEqual(changed[1], 'WE|1|PICTURE|200|@190206018|ART2')
        self.assertEqual(changed[2], 'WE|1|TEXTPICK|201|NewPick|ART1~PickText')
        self.assertEqual(changed[10], 'WE|1|SPELL|8730|SP02|ART2~1002~ART1 SP01~PickText~0')
        self.assertEqual(changed[12], 'WE|1|TABLE|202|*spells+all+anylevel|209~2~26~28')
        self.assertTrue(all(parse_behavior(row).minimum_revision == 3 for row in records))

    def test_attributes_are_values_and_never_click_callbacks(self):
        for kind in ('CLICK','TCLICK','PICK','LIST'):
            with self.subTest(kind=kind), self.assertRaises(PanelEngineError):
                parse_behavior('WE|1|'+kind+'|200|@190206017')
        for suffix in ('*unknown|0~2', '*items|0~1', '*items+unknown|0~2',
                       '*items+all+all|0~2', 'Rows|0~2~101', 'Rows|0~2~-1'):
            with self.subTest(suffix=suffix), self.assertRaises(PanelEngineError):
                parse_behavior('WE|1|TABLE|200|'+suffix)
        for source in ('@', '@-1', '@4294967296'):
            with self.subTest(source=source), self.assertRaises(PanelEngineError):
                parse_behavior('WE|1|TEXT|200|'+source+'|text')

    def test_updated_panel_and_native_function_requirements_reject_old_revisions(self):
        context = dict(owner_id='id', owner_name='Example', dataset='MajestyExpansion')
        resources = {(b'SMNU', b'PN01'): b'layout',
            (b'STRT', b'PN01'): table('WE|1|BKG|1001|ART1').to_bytes()}
        evidence = from_effective_resources(resources, **context)
        self.assertEqual(evidence[0].requirement.minimum_revision, 3)
        self.assertTrue(missing(evidence, {PANEL_SERVICE: 2}))
        for text in ('%t','%d'):
            row = parse_behavior('WE|1|TEXT|200|Value|'+text)
            self.assertEqual(row.minimum_revision, 3 if text=='%t' else 1)
        for name, revision in (('SF_MapAction',1), ('SF_SetWindow',2),
                               ('SF_ResetWindow',2), ('SF_UnexploredArea',2)):
            inferred = from_verified_sources((('loaded.gpl', '$'+name+'();'),), **context)
            self.assertEqual(inferred[0].requirement.minimum_revision, revision)
            self.assertEqual(inferred[0].requirement.service, ACTION_SERVICE)
        local = 'function SF_MapAction()\nbegin\nend SF_MapAction;\n'
        inferred = from_verified_sources((('own.gpl',local),('call.gpl',
            '$SF_MapAction(); $SF_UnexploredArea();')), **context)
        self.assertEqual(inferred[0].requirement.minimum_revision, 2)
        self.assertTrue(missing(inferred, {ACTION_SERVICE:1}))
        self.assertEqual(from_verified_sources((('unused.gpl',
            '// $SF_SetWindow();\n"$SF_UnexploredArea()"; $SF_ResetWindow;'),), **context), ())

    def test_updated_native_protocol_is_standard_without_metadata(self):
        from majesty_cam.cam import CamArchive, CamSection, CamEntry
        from majesty_cam.manager.catalog import scan_catalog, CatalogKind
        from majesty_cam.manager.engine_patches import discover
        from test_manager_catalog import _write_mod, STANDARD_ID
        with TemporaryDirectory() as folder:
            root = Path(folder); package = root/'Native'; (package/'Data').mkdir(parents=True)
            _write_mod(package, STANDARD_ID, 'Native panels', cam=True)
            records = table('WE|1|CLASS|building', 'WE|1|BKG|1001|ART1',
                'WE|1|TEXTPICK|200|PickText|first~second')
            cam = CamArchive((CamSection(b'SMNU',(CamEntry(b'PN01'.ljust(20,b'\0'),b'layout'),)),
                CamSection(b'STRT',(CamEntry(b'PN01'.ljust(20,b'\0'),records.to_bytes()),))))
            (package/'Data/Content.cam').write_bytes(cam.to_bytes())
            entry, = scan_catalog(local_mods_root=root).entries
            self.assertEqual(entry.kind, CatalogKind.STANDARD)
            self.assertTrue(entry.selectable)
            self.assertEqual(discover(entry).evidence[0].requirement.minimum_revision, 3)
            self.assertFalse((package/'mod-definition.json').exists())
            unsupported=table('WE|1|CLASS|building','WE|1|FUTURE|200|Value')
            changed=CamArchive((cam.sections[0],CamSection(b'STRT',(
                CamEntry(b'PN01'.ljust(20,b'\0'),unsupported.to_bytes()),))))
            (package/'Data/Content.cam').write_bytes(changed.to_bytes())
            entry,=scan_catalog(local_mods_root=root).entries
            self.assertEqual(entry.kind,CatalogKind.STANDARD)
            self.assertFalse(entry.selectable)
            self.assertTrue(any(i.code=='invalid_native_panel_protocol' for i in entry.issues))
            self.assertFalse(any('mod-definition' in i.message for i in entry.issues))
