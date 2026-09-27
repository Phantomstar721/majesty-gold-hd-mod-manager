from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
import copy
import unittest

from majesty_cam.potion_policy import (parse_feature, feature_mapping, Plan, Action, POTIONS,
    compose, prepare_descriptions)
from majesty_cam.private_phantom_policy import POLICY
from majesty_cam.gpl import parse_gpl, SemanticMergeResult, DefinitionKind
from majesty_cam.gameplay_events import add_gameplay_event_observers, EVENT_FUNCTIONS
from majesty_cam.compose import _load_stock_gameplay_event_items, compile_gpl, _load_effective_stock_descriptions
from majesty_cam.descriptions import merge_descriptions

GAME = Path('C:/Program Files (x86)/Steam/steamapps/common/Majesty HD')


class PotionPolicyTests(unittest.TestCase):
    def test_schema_round_trip_and_reject_invalid(self):
        self.assertEqual(feature_mapping(parse_feature(POLICY)), POLICY)
        for field, value in (("hero_title", 'Bad"Injection'), ("potions", {"speed": True}),
                             ("shapeshift", {"preset":"guess"}), ("private_actions", {"unknown":"Action"})):
            bad = copy.deepcopy(POLICY); bad[field] = value
            with self.assertRaises(ValueError): parse_feature(bad)

    def setUp(self):
        if not (GAME/'SDK/Gplbcc.exe').is_file():
            self.skipTest('requires stock SDK')
        paths = ('TaskModules/Subtasks/mx_Spells.gpl', 'TaskModules/Buildings/Magic_Bazaar.gpl',
                 'TaskModules/Subtasks/mx_heal_self.gpl')
        self.stock = {}
        for path in paths:
            for item in parse_gpl((GAME/'SDK/OriginalQuests/GPLMx'/path).read_text(encoding='cp1252')).items:
                self.stock[item.key] = item
        self.loader = lambda names: {key:item for key,item in self.stock.items() if key[1] in {n.casefold() for n in names}}
        self.actions = tuple(Action(k, name, name+'_Effect', '', 'P00'+str(i)) for i,(k,(_,name)) in enumerate(POTIONS.items()))

    def test_presets_and_observers_compile_without_lifecycle_replacement(self):
        callback = parse_gpl('function Observe(agent Actor, string Item)\ndeclare\nbegin\nend').items[0]
        plan = Plan((parse_feature(POLICY),), self.actions)
        result, evidence = compose(SemanticMergeResult((callback,),()), plan, self.loader,
            _load_stock_gameplay_event_items(GAME, {'potion-consumed':('Observe',)}))
        observed = add_gameplay_event_observers(result, {'potion-consumed':('Observe',)}, evidence)
        functions = {item.normalized_name:item.text for item in observed.items}
        shape = functions['shapeshift_potion_effect']
        self.assertIn('title == "Phantom"', shape)
        self.assertLess(shape.index('title == "Phantom"'), shape.index('"AttackType"'))
        self.assertEqual(shape.count('$Observe('),1)
        self.assertEqual(shape.lower().count('$createeffector'),2)
        self.assertIn('#ATTRIB_MaxHP, -30', functions['shapeshift_potion_end'])
        self.assertIn('$Done_Purchasing_Market_Stuff', functions['purchase_bazaar_item_four'])
        self.assertNotIn('MM_BP', functions['heal_self'])
        with TemporaryDirectory() as root:
            compile_gpl(observed.emit_project_source_set(), GAME/'SDK/Gplbcc.exe', Path(root)/'compiler')

    def test_custom_form_has_matched_deltas_and_no_second_effector(self):
        value = copy.deepcopy(POLICY)
        value['hero_title'] = 'CustomCaster'
        value['shapeshift'] = {'preset':'custom','unit_name':'Giant_Spider','heal':30,
            'adjustments':[{'attribute':'ATTRIB_Strength','amount':18,'mode':'magical'},
                           {'attribute':'ATTRIB_ActionRateModifier','amount':-50,'mode':'raw'},
                           {'attribute':'ATTRIB_MaxHP','amount':30,'mode':'raw'}]}
        result,_ = compose(SemanticMergeResult((),()),Plan((parse_feature(value),),self.actions),self.loader,{})
        functions = {i.normalized_name:i.text for i in result.items}
        self.assertIn('#ATTRIB_Strength, 18',functions['shapeshift_potion_effect'])
        self.assertIn('#ATTRIB_Strength, -18',functions['shapeshift_potion_end'])
        self.assertIn('#ATTRIB_ActionRateModifier, 50',functions['shapeshift_potion_end'])
        self.assertNotIn('#ATTRIB_HP, -30',functions['shapeshift_potion_end'])
        self.assertEqual(functions['shapeshift_potion_effect'].lower().count('$createeffector'),2)

    def test_legacy_cleanup_override_fails_closed(self):
        item = self.stock[(DefinitionKind.FUNCTION,'shapeshift_potion_end')]
        modified = replace(item,text=item.text.replace('#ATTRIB_MaxHP, -30','#ATTRIB_MaxHP, -99'))
        with self.assertRaisesRegex(ValueError,'migrate'):
            compose(SemanticMergeResult((modified,),()),Plan((parse_feature(POLICY),),self.actions),self.loader,{})

    def test_action_validators_and_private_consumption_observer(self):
        stock = {key:value[0] for key,value in _load_effective_stock_descriptions(GAME).items()}
        result, plan = prepare_descriptions(merge_descriptions(b'<Descriptions/>',()),stock,(parse_feature(POLICY),))
        self.assertEqual(len(plan.actions),6)
        for action in plan.actions:
            record = result.document.index[('Action',action.key)].to_element()
            self.assertEqual(record.find('./Game/ValidationScript').get('value'),action.validator)
            self.assertEqual(record.find('./Game/EffectorDuration').get('value'),
                             stock[('Action',action.key)].to_element().find('./Game/EffectorDuration').get('value'))
        # Private action ownership uses the same lifecycle with only names changed.
        original = self.stock[(DefinitionKind.FUNCTION,'shapeshift_potion_effect')]
        private = replace(original,name='PrivateShape',text=original.text.replace(
            'Shapeshift_Potion_Effect','PrivateShape').replace('"Shapeshift_Potion"','"PrivateShapeAction"'))
        callback = parse_gpl('function Observe(agent Actor, string Item)\ndeclare\nbegin\nend').items[0]
        plan = replace(plan,actions=(*plan.actions,Action('shapeshift','PrivateShapeAction','PrivateShape','','PS01')))
        # These integer validations live in a different stock file; use the
        # production read-only ancestor loader rather than inventing stubs.
        from majesty_cam.stock_gpl import load_stock_function_ancestors
        loader = lambda names: load_stock_function_ancestors(GAME,names)
        final,evidence = compose(SemanticMergeResult((private,callback),()),plan,loader,
                                _load_stock_gameplay_event_items(GAME,{'potion-consumed':('Observe',)}))
        observed = add_gameplay_event_observers(final,{'potion-consumed':('Observe',)},evidence,
                                               potion_aliases={'privateshape':'shapeshift_potion'})
        functions = {item.normalized_name:item.text for item in observed.items}
        self.assertEqual(functions['privateshape'].count('$Observe('),1)
        self.assertIn('"PrivateShapeAction"',functions['privateshape'])
        with TemporaryDirectory() as root:
            compile_gpl(observed.emit_project_source_set(),GAME/'SDK/Gplbcc.exe',Path(root)/'compiler')

    def test_private_bundle_policy_preserves_explicit_panel_identity(self):
        import json
        from majesty_cam.private_phantom_policy import apply
        from majesty_cam.package import parse_mod_definition, mod_definition_mapping
        source = Path(__file__).resolve().parents[1]/'payload/mods/CustomGuildPhantomsHauntExpanded/mod-definition.json'
        with TemporaryDirectory() as root:
            target = Path(root)/source.name
            target.write_bytes(source.read_bytes())
            before = json.loads(target.read_text())
            apply(root)
            apply(root)
            after = json.loads(target.read_text())
            self.assertEqual(after['custom_buildings'],before['custom_buildings'])
            self.assertEqual(after['schema_version'],before['schema_version'])
            self.assertEqual(mod_definition_mapping(parse_mod_definition(after)),after)

    def test_real_consumer_callbacks_and_declarations(self):
        from majesty_cam.package import load_package
        from majesty_cam.compose import SelectedMod, inventory_package, _parse_inventory_gpl_sources
        from majesty_cam.potion_policy import selected
        from majesty_cam.descriptions import parse_descriptions
        from majesty_cam.stock_gpl import load_stock_function_ancestors
        root = Path(__file__).resolve().parents[2]
        paths = (root/'majesty-gold-hd-custom-guild-bard/dist/CustomGuildBards-bazaar-policy-v1',
                 root/'majesty-gold-hd-custom-guild-alchemist/dist/CustomGuildAlchemist')
        if not all(path.is_dir() for path in paths):
            self.skipTest('consumer source packages unavailable')
        inventories = tuple(inventory_package(SelectedMod(str(i),load_package(path))) for i,path in enumerate(paths))
        policies = (*selected(inventories),parse_feature(POLICY))
        if not any(policy.hero_title == 'Alchemist' for policy in policies):
            self.skipTest('consumer has not migrated yet')
        stock = {key:value[0] for key,value in _load_effective_stock_descriptions(GAME).items()}
        records = dict(stock)
        functions = {}
        for inventory in inventories:
            for path in inventory.descriptions:
                records.update({r.key:r for r in parse_descriptions(path.read_bytes()).records})
            for source in _parse_inventory_gpl_sources(inventory):
                functions.update({i.key:i for i in source.items})
        _, plan = prepare_descriptions(merge_descriptions(b'<Descriptions/>',()), records, policies)
        names = {a.effect.casefold() for a in plan.actions} | {'shapeshift_potion_end','alchemist_bazaar_item_check'}
        selected_functions = [item for key,item in functions.items() if key[0] is DefinitionKind.FUNCTION and key[1] in names]
        # The stock shape reference must always come from stock, never from an
        # authored replacement. Production's loader has the same invariant.
        original_loader = lambda names: load_stock_function_ancestors(GAME,names)
        for a in plan.actions:
            if a.validation and (DefinitionKind.FUNCTION,a.validation.casefold()) in functions:
                selected_functions.append(functions[(DefinitionKind.FUNCTION,a.validation.casefold())])
        callback = parse_gpl('function Observe(agent Actor, string Item)\ndeclare\nbegin\nend').items[0]
        result,evidence = compose(SemanticMergeResult((*selected_functions,callback),()),plan,original_loader,
                                 _load_stock_gameplay_event_items(GAME,{'potion-consumed':('Observe',)}))
        observed = add_gameplay_event_observers(result,{'potion-consumed':('Observe',)},evidence,
            potion_aliases={a.effect.casefold():POTIONS[a.potion][1].casefold() for a in plan.actions
                            if a.effect.casefold() != POTIONS[a.potion][1].casefold()+'_effect'})
        text = '\n'.join(i.text for i in observed.items)
        self.assertIn('"Giant_Spider"',text)
        self.assertIn('title == "Blade_Dancer"',text)
        purchase_check = next(i.text for i in observed.items if i.normalized_name == 'bazaar_item_check')
        self.assertIn('$MM_BP_Eligibility',purchase_check)
