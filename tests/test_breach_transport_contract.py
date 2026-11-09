"""Real composition scoping for the separately versioned paid recipe."""
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import TestCase
from test_compose import _v3_controller_inventory, _panel_pair
import test_sovereign_source_target as source_target_tests
from majesty_cam.stock_controller_features import controller_feature_mapping, parse_controller_feature
from majesty_cam.compose import resolve_controller_registry, ComposeError
from majesty_cam.stock_controller_registry import encode_stock_controller_registry, decode_stock_controller_registry

class BreachTransportContractTests(TestCase):
    def test_real_composition_scopes_paid_action_without_resource_meter(self):
        with TemporaryDirectory() as tmp:
            root=Path(tmp)
            inventory=_v3_controller_inventory(root,alias='paid',
                mod_id='{00000000-0000-0000-0000-000000000099}',local_name='PrivateBuilding',
                building_source=b'B001',family='ABC')
            _, old=source_target_tests.SourceTargetTests().fixture()
            fields=controller_feature_mapping(old)
            fields.update(type='stock.ap69-sovereign-target-action.v3',panel_key='shared-panel',
                          target_template_control_id=0x1138,stock_target_mode='Sp29',
                          required_level=2,sovereign_gold_cost=500)
            del fields['resource_key'],fields['resource_cost']
            action=parse_controller_feature(fields)
            definition=inventory.selected.package.definition
            inventory.selected.package.definition=replace(definition,runtime_features=(*definition.runtime_features,action))
            inventory.resources=(*_panel_pair('paid',b'B001',(0x4100,)),
                *_panel_pair('paid',b'P001',(action.visual_control_id,action.icon_control_id,action.price_control_id)))
            description=inventory.descriptions[0]
            description.write_text(description.read_text().replace('</Majesty>',
                '<Description type="Unit" ID="ALS1" subType="Character"><Game /></Description></Majesty>'))
            source=root/'callback.gpl'
            source.write_text('function Private_Exact_Action(agent Spell, agent Source, agent Target)\nbegin\nend\n')
            inventory.gpl_loads=(SimpleNamespace(sources=(SimpleNamespace(absolute_path=source),)),)
            # Actual consumer uses AP07 with the already cataloged AP10 layout.
            definition=inventory.selected.package.definition
            inventory.selected.package.definition=replace(definition,custom_buildings=(
                replace(definition.custom_buildings[0],controller_base="AP07"),))
            result=resolve_controller_registry((inventory,))
            self.assertFalse(result.registry.meters)
            row,=result.registry.sovereign_target_actions
            self.assertTrue(row.panel_key.startswith('m00000000000000000000000000000099.'))
            self.assertEqual((row.sovereign_gold_cost,row.callback_symbol,row.resource_key),(500,'Private_Exact_Action',''))
            self.assertEqual(decode_stock_controller_registry(encode_stock_controller_registry(result.registry)),result.registry)
            source.write_text('function Private_Exact_Action(agent Spell)\nbegin\nend\n')
            with self.assertRaisesRegex(ComposeError,'must take'):
                resolve_controller_registry((inventory,))
