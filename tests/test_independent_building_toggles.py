from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
import struct
import unittest
from majesty_cam.stock_controller_features import (StockMx22BuildingOpenToggle,
    StockMx22IndependentToggle, StockMx22PanelToggle, StockAp52RecruitmentPanel,
    parse_controller_feature, controller_feature_mapping,
    normalize_controller_features, ControllerFeatureError)
from majesty_cam.stock_controller_registry import (resolve_stock_controller_registry,
    encode_stock_controller_registry, decode_stock_controller_registry)
from majesty_cam.building_toggle_state import add_state_functions, validate_state_functions, validate_declarations
from majesty_cam.gpl import SemanticMergeResult, parse_gpl
from majesty_cam.compose import compile_gpl


class IndependentToggleTests(unittest.TestCase):
    def test_recruitment_child_binding_roundtrip_and_scope(self):
        panel = StockAp52RecruitmentPanel('recruit', 'library', 0x7301,
            source_dialog_id='RCRT', open_command_id=0x7302)
        toggle = StockMx22PanelToggle('hiring', 'library', 0x7340, 0x7341,
            state_attribute='HiringClosed', state_callback_symbol='Hiring_Closed',
            panel_key='recruit')
        self.assertEqual(parse_controller_feature(controller_feature_mapping(toggle)), toggle)
        parent, child = (int.from_bytes(x, 'little') for x in (b'PRNT', b'RCRT'))
        registry = resolve_stock_controller_registry((panel, toggle), {'recruit': (parent, child)},
            recruitment_parents={'recruit': parent}, toggle_parents={'hiring': (parent, 'AP52')})
        payload = encode_stock_controller_registry(registry)
        self.assertEqual(struct.unpack_from('<I', payload, 4)[0], 21)
        self.assertEqual(registry.building_open_toggles[0].panel_dialog_id, child)
        self.assertEqual(decode_stock_controller_registry(payload), registry)
        for bad in (replace(toggle, panel_key='missing'), replace(toggle, parent_building='foreign'),
                    replace(toggle, open_command_id=0x1F48), replace(toggle, close_command_id=0x7301)):
            with self.assertRaises(ControllerFeatureError):
                normalize_controller_features((panel, bad))
        for end in range(len(payload)):
            with self.assertRaises(ValueError):
                decode_stock_controller_registry(payload[:end])

    def setUp(self):
        self.legacy = StockMx22BuildingOpenToggle('z-open', 'library', 29000, 29001)
        self.private = StockMx22IndependentToggle('a-auto', 'library', 29002, 29003,
            state_attribute='ExampleAuto', state_callback_symbol='Example_Auto_Enabled')

    def test_same_parent_roundtrip_and_legacy_compatibility(self):
        features = (self.legacy, self.private)
        self.assertEqual(parse_controller_feature(controller_feature_mapping(self.private)), self.private)
        registry = resolve_stock_controller_registry(features, {}, toggle_parents={
            f.toggle_key: (int.from_bytes(b'B123','little'), 'AP08') for f in features})
        data = encode_stock_controller_registry(registry)
        self.assertEqual(struct.unpack_from('<I',data,4)[0],19)
        self.assertEqual(decode_stock_controller_registry(data),registry)
        old = resolve_stock_controller_registry((self.legacy,), {}, toggle_parents={
            self.legacy.toggle_key: (int.from_bytes(b'B123','little'),'AP08')})
        self.assertEqual(struct.unpack_from('<I',encode_stock_controller_registry(old),4)[0],4)

    def test_independent_state_and_control_ownership(self):
        other = replace(self.private,toggle_key='b-auto',open_command_id=29004,close_command_id=29005,
                        state_attribute='OtherAuto',state_callback_symbol='Other_Auto_Enabled')
        normalize_controller_features((self.legacy,self.private,other))
        for bad in (replace(other,state_attribute='exampleauto'),
                    replace(other,state_callback_symbol='example_auto_enabled'),
                    replace(other,open_command_id=29002)):
            with self.assertRaises(ControllerFeatureError):
                normalize_controller_features((self.private,bad))
        with self.assertRaises(ControllerFeatureError):
            normalize_controller_features((self.legacy,replace(self.legacy,toggle_key='other')))

    def test_generated_state_and_integer_boundary(self):
        result=add_state_functions(SemanticMergeResult((),()),(self.private,))
        funcs={i.normalized_name:i.text for i in result.items}
        counts={k:1 for k in funcs}
        validate_state_functions(self.private,funcs,counts)
        self.assertIn('is boolean',funcs['example_auto_enabled'])
        self.assertIn('is integer',funcs['mm_toggle_example_auto_enabled'])
        self.assertIn('$AddAttribute(Building, "ExampleAuto", "boolean", False)',
                      funcs['mm_toggle_example_auto_enabled'])
        self.assertNotIn('AddAttribute',funcs['example_auto_enabled'])
        with self.assertRaises(ValueError):
            add_state_functions(result,(self.private,))
        corrupt=dict(funcs);corrupt['example_auto_enabled']+='\nreturn True;'
        with self.assertRaises(ValueError):
            validate_state_functions(self.private,corrupt,counts)
        compiler=Path('C:/Program Files (x86)/Steam/steamapps/common/Majesty HD/SDK/Gplbcc.exe')
        if compiler.is_file():
            with TemporaryDirectory(prefix='manager-toggle-') as temp:
                compile_gpl(result.emit_project_source_set(),compiler,Path(temp)/'compile')

    def test_private_state_rejects_authored_or_stock_declarations(self):
        owners = (("example", (self.private,)),)
        validate_declarations(owners, (("example", ()),))
        for kind in ('boolean', 'integer'):
            parsed = parse_gpl(f'prototype Example\ndeclare\n{kind} ExampleAuto;\nend\n')
            for owner in ('example', 'foreign'):
                with self.assertRaisesRegex(ValueError, 'Manager-owned'):
                    validate_declarations(owners, ((owner, (parsed,)),))
            with self.assertRaisesRegex(ValueError, 'Manager-owned'):
                validate_declarations(owners, (), (parsed,))
        authored = parse_gpl('function Example_Auto_Enabled(agent Building) is boolean\ndeclare\nbegin\nreturn False;\nend\n')
        with self.assertRaisesRegex(ValueError, 'collides'):
            validate_declarations(owners, (("example", (authored,)),))
