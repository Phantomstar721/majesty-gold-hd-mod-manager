import json
import os
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from verify_panel_engine_data_clients import verify as verify_clients, decode, import_identity
from verify_panel_engine_vtables import verify as verify_tables
from verify_panel_engine_constructors import verify as verify_constructors
from verify_panel_engine_navigation import verify as verify_navigation
from verify_panel_engine_ui_callers import verify as verify_ui_callers
from verify_panel_engine_agent_clients import verify as verify_agent_clients


class PanelEngineDataProfileTests(unittest.TestCase):
    def fixtures(self):
        return {name: Path(os.environ['MAJESTY_' + name.upper() + '_EXE']) for name in ('public', 'beta2', 'gog')}

    def test_complete_string_attribute_and_tree_clients(self):
        actual = verify_clients(self.fixtures())
        self.assertEqual(actual, json.loads((ROOT / 'profiles/panel-engine/data-clients.json').read_bytes()))
        for row in actual['profiles'].values():
            self.assertEqual(row['rawAttribute']['size'], 109)
            self.assertEqual(row['narrowAssign']['size'], 127)
            self.assertEqual(row['imports'][0][1], 'free')

    def test_class_identity_and_normal_constructor_handoff(self):
        tables = verify_tables(self.fixtures())
        constructors = verify_constructors(self.fixtures())
        self.assertEqual(tables, json.loads((ROOT / 'profiles/panel-engine/vtables.json').read_bytes()))
        self.assertEqual(constructors, json.loads((ROOT / 'profiles/panel-engine/constructors.json').read_bytes()))
        for branch in ('public', 'beta2', 'gog'):
            for name, row in constructors['profiles'][branch]['constructors'].items():
                self.assertEqual(row['primaryVtableVA'], tables['profiles'][branch]['classes'][name]['va'])
                self.assertEqual(row['returnStackBytes'], 8)

    def test_complete_body_check_rejects_outside_branch_and_partial_instruction(self):
        with self.assertRaises(ValueError):
            decode(b'\x75\x40\xc3', 0x401000)
        with self.assertRaises(ValueError):
            decode(b'\x8b', 0x401000)

    def test_absolute_reference_is_never_assumed_to_be_an_import(self):
        class Image:
            DIRECTORY_ENTRY_IMPORT = ()
        with self.assertRaisesRegex(ValueError, 'not a supported import'):
            import_identity(Image(), 0x745000)

    def test_stock_back_route_uses_its_real_branch_on_every_version(self):
        actual = verify_navigation(self.fixtures())
        self.assertEqual(actual, json.loads((ROOT / 'profiles/panel-engine/navigation.json').read_bytes()))
        self.assertIsNone(actual['profiles']['public']['extendedBackDispatch'])
        self.assertIsNotNone(actual['profiles']['beta2']['extendedBackDispatch'])
        self.assertIsNotNone(actual['profiles']['gog']['extendedBackDispatch'])
        for row in actual['profiles'].values():
            self.assertTrue(row['backArmBytes'].startswith('6a00e9'))

    def test_presenter_helpers_keep_typed_unit_name_argument_frame(self):
        actual = verify_ui_callers(self.fixtures())
        self.assertEqual(actual, json.loads((ROOT / 'profiles/panel-engine/ui-callers.json').read_bytes()))
        for row in actual['profiles'].values():
            self.assertTrue(row['unitNameCallBytes'].startswith('6a008d4c243c5751e8'))

    def test_borrowed_agent_lookup_keeps_stock_deleted_guard_before_unit_request(self):
        actual = verify_agent_clients(self.fixtures())
        self.assertEqual(actual, json.loads((ROOT / 'profiles/panel-engine/agent-clients.json').read_bytes()))
        for row in actual['profiles'].values():
            self.assertEqual(row['deletedByteOffset'], 0x38)
