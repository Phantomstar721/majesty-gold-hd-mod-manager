import re
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from majesty_cam.building_employment import parse_feature, feature_mapping, query_source, validate_owner_callbacks, lifecycle_source, travel_source
from majesty_cam.gpl import parse_gpl, SemanticMergeResult
from majesty_cam.building_employment import compose_service
from gpl_sampler_harness import Agent, SamplerHarness

SDK = Path('C:/Program Files (x86)/Steam/steamapps/common/Majesty HD/SDK')


def stock_travel(dataset):
    root = SDK/'OriginalQuests'/dataset/'TaskModules/Characters'
    prefix = 'mx_' if dataset == 'GPLMx' else ''
    return '\n'.join((root/(prefix + name + '.gpl')).read_text(encoding='cp1252')
                     for name in ('use_building', 'travel_to'))


def declaration(**changes):
    return {"type": "stock.building-employment.v1", "feature_key": "forge.hire",
            "api_prefix": "ForgeHire", "parent_building": "Forge",
            "source_dialog_id": "FH01", "open_command_id": 8100,
            "gated_control_ids": [8009], "hero_titles": ["Ranger"],
            "minimum_level": 8, "eligibility_callback_symbol": "ForgeEligible",
            "cleanup_callback_symbol": "ForgeCleanup", "visitor_callback_symbol": "ForgeVisited",
            **changes}


class EmploymentContractTests(unittest.TestCase):
    def test_optional_travel_text_uses_existing_intent_resolver(self):
        from majesty_cam.building_employment import resolve_travel_text
        value = declaration(travel_text="Going to the workshop")
        feature = parse_feature(value)
        self.assertEqual(feature_mapping(feature), value)
        resolved = resolve_travel_text(feature, '16ecc2a0-df61-43a1-8776-0fe7d3a1c208')
        for dataset in ('GPL', 'GPLMx'):
            output = lifecycle_source(resolved, stock_travel(dataset))
            self.assertIn(f'$SpecifyIntent(Hero, {resolved.travel_text_id});', output)
            self.assertIn('Hero\'s "TaskName" = "";', output)
        for text in ('', 'bad\x00text', 'x'*97, '\u2603'):
            with self.assertRaises(ValueError):
                parse_feature(declaration(travel_text=text))

    def test_controller_and_registry_admission_use_the_generated_contract(self):
        from majesty_cam.stock_controller_features import (
            parse_controller_feature, controller_feature_mapping,
            encode_controller_features, decode_controller_features)
        from majesty_cam.stock_controller_registry import (
            resolve_stock_controller_registry, encode_stock_controller_registry,
            decode_stock_controller_registry, LiveAgentListTextIds)
        feature = parse_controller_feature(declaration())
        self.assertEqual(controller_feature_mapping(feature), declaration())
        self.assertEqual(decode_controller_features(encode_controller_features((feature,))), (feature,))
        registry = resolve_stock_controller_registry((feature,),
            {'forge.hire': (int.from_bytes(b'FG00', 'little'), int.from_bytes(b'FH01', 'little'))},
            list_text_ids={'forge.hire': LiveAgentListTextIds(0,0,0)})
        record = registry.live_agent_lists[0]
        self.assertEqual(record.admission_callback_symbol, 'MM_ForgeHire_Admit')
        self.assertEqual(record.gated_control_ids, (8009,))
        self.assertTrue(record.action_uses_pair)
        self.assertEqual(decode_stock_controller_registry(encode_stock_controller_registry(registry)), registry)

    def test_package_definition_roundtrip_keeps_author_fields_only(self):
        from majesty_cam.package import parse_mod_definition, mod_definition_mapping
        value = {'schema_version': 3, 'mod_id': '16ecc2a0-df61-43a1-8776-0fe7d3a1c208',
                 'internal_name': 'Forge', 'display_name': 'Forge',
                 'custom_buildings': [{'local_name': 'Forge', 'controller_base': 'AP10',
                                      'panel_resource_template': 'AP10'}],
                 'runtime_features': [declaration()]}
        self.assertEqual(mod_definition_mapping(parse_mod_definition(value)), value)

    def test_destination_composition_preserves_existing_functions(self):
        owner = parse_gpl(
            'function ForgeEligible(agent Hero,agent Building) is boolean declare begin return True; end\n'
            'function ForgeCleanup(agent Hero,agent Building) declare begin end\n'
            'function ForgeVisited(agent Hero) declare begin end')
        for dataset in ('GPL', 'GPLMx'):
            with self.subTest(dataset=dataset):
                stock = parse_gpl(stock_travel(dataset))
                original = SemanticMergeResult((*owner.items, *stock.items), ())
                loader = lambda names: {(i.kind, i.normalized_name): i for i in stock.items
                                         if i.normalized_name in names}
                result = compose_service(original, (parse_feature(declaration()),), loader)
                self.assertEqual(result.items[:len(original.items)], original.items)
                self.assertEqual(result.conflicts, original.conflicts)
                with self.assertRaisesRegex(ValueError, 'collides'):
                    compose_service(result, (parse_feature(declaration()),), loader)
                with self.assertRaisesRegex(ValueError, 'more than one owner'):
                    compose_service(original, (parse_feature(declaration()),) * 2, loader)
        self.assertIs(compose_service(original, (), None), original)
        with self.assertRaisesRegex(ValueError, 'destination stock'):
            compose_service(original, (parse_feature(declaration()),), None)
        with self.assertRaisesRegex(ValueError, 'source is missing'):
            compose_service(original, (parse_feature(declaration()),), lambda names: {})

    def test_actual_callback_api_and_return_types(self):
        source = ('function ForgeEligible(agent Hero,agent Building) is boolean declare begin return True; end\n'
                  'function ForgeCleanup(agent Hero,agent Building) declare begin end\n'
                  'function ForgeVisited(agent Hero) declare begin end')
        feature = parse_feature(declaration())
        validate_owner_callbacks(feature, (parse_gpl(source),))
        with self.assertRaises(ValueError):
            validate_owner_callbacks(feature, (parse_gpl(source.replace('is boolean', 'is integer')),))
        with self.assertRaises(ValueError):
            validate_owner_callbacks(feature, (parse_gpl(source), parse_gpl(source)))

    def test_round_trip(self):
        value = declaration()
        self.assertEqual(feature_mapping(parse_feature(value)), value)

    def test_rejects_upgrade_and_navigation_gates(self):
        for control in (0x1F47, 0x1F4D, 0x1F40, 0x1F41, 0x1388, 0x138B):
            with self.assertRaises(ValueError):
                parse_feature(declaration(gated_control_ids=[control]))

    def test_rejects_invalid_contracts(self):
        for changes in ({"minimum_level": True}, {"minimum_level": 0},
                        {"hero_titles": ["Ranger", "ranger"]}, {"hero_titles": []},
                        {"api_prefix": "MM_Intrude"}, {"source_dialog_id": "MX05"},
                        {"gated_control_ids": [8100]}, {"open_command_id": False},
                        {"cleanup_callback_symbol": 'Bad";'}, {"unknown": 1}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                parse_feature(declaration(**changes))

    def test_queries_are_not_a_gameplay_or_persistence_controller(self):
        source = query_source(parse_feature(declaration()))
        self.assertEqual(len(parse_gpl(source).items), 7)
        self.assertIn('#insideOtherUnits', source)
        self.assertIn('#MyPlayer', source)
        for forbidden in ("$AddAttribute", "$DeleteGamePiece", "$NewThread", "$RunThread",
                          "$KillThread", "$AdjustAttribute", "$StopMoving"):
            self.assertNotIn(forbidden, source)

    def test_eligibility_and_missing_state_without_writes(self):
        parsed = parse_gpl(query_source(parse_feature(declaration())))
        source = '\n'.join(i.text for i in parsed.items
                           if i.normalized_name in ('mm_forgehire_unlocked', 'mm_forgehire_eligible'))
        source = re.sub(r'#(\w+)', lambda m: '"' + m[1] + '"', source)
        vm = SamplerHarness(source)
        building = Agent()
        building.fields = {"Title": "Forge", "ATTRIB_FirstStageBuilt": 1, "player": 1}
        hero = Agent()
        hero.fields = {"Title": "Ranger", "Type": "hero", "ATTRIB_HP": 20,
                       "ATTRIB_ExperienceLevel": 8, "player": 1}
        calls = []
        vm.calls.update(getattribute=lambda a, k: a[k], getunitplayernumber=lambda a: a['player'],
                        forgeeligible=lambda h, b: calls.append((h, b)) or True)
        before = dict(building.fields)
        self.assertTrue(vm.call('mm_forgehire_eligible', hero, building))
        self.assertEqual(calls, [(hero, building)])
        self.assertEqual(building.fields, before)
        for key, value in (("ATTRIB_ExperienceLevel", 7), ("ATTRIB_HP", 0),
                           ("Title", "Wizard"), ("Type", "Dead"), ("player", 2)):
            original = hero[key]
            hero[key] = value
            self.assertFalse(vm.call('mm_forgehire_eligible', hero, building))
            hero[key] = original
        hero.alive = False
        self.assertFalse(vm.call('mm_forgehire_eligible', hero, building))
        hero.alive = True
        building['MM_ForgeHire_UnlockedState'] = True
        self.assertFalse(vm.call('mm_forgehire_eligible', hero, building))
        self.assertFalse(vm.call('mm_forgehire_eligible', None, building))
        self.assertFalse(vm.call('mm_forgehire_eligible', hero, None))


class EmploymentLifecycleTests(unittest.TestCase):
    def test_private_travel_is_literal_stock_with_only_binding_changes(self):
        from majesty_cam.gameplay_events import stock_tokens
        for dataset in ('GPL', 'GPLMx'):
            source = stock_travel(dataset)
            generated = travel_source(parse_feature(declaration()), source)
            names = {'Travel': 'use_building', 'TravelTo': 'travel_to',
                     'HasArrived': 'has_arrived', 'TargetRange': 'gettargetrange'}
            restored = generated.replace('$MM_ForgeHire_Arrive', 'target\'s "visited_script"')
            for suffix, stock in sorted(names.items(), key=lambda pair: -len(pair[0])):
                restored = restored.replace('MM_ForgeHire_' + suffix, stock)
            actual = {i.normalized_name: i for i in parse_gpl(restored).items}
            original = {i.normalized_name: i for i in parse_gpl(source).items}
            for name in names.values():
                self.assertEqual(stock_tokens(actual[name].text), stock_tokens(original[name].text))

    def test_both_destination_lifecycles_compile_in_isolation(self):
        from majesty_cam.gpl import SemanticMergeResult
        from majesty_cam.compose import compile_gpl
        for dataset in ('GPL', 'GPLMx'):
            source = lifecycle_source(parse_feature(declaration()), stock_travel(dataset))
            from majesty_cam.action_callback_bridge import bridge_source
            source += bridge_source('MM_ForgeHire_Action', paired=True)
            with TemporaryDirectory() as directory:
                compile_gpl(SemanticMergeResult(parse_gpl(source).items, ()).emit_project_source_set(),
                            SDK/'Gplbcc.exe', Path(directory)/'compiler', stem='EmploymentLifecycle')

    def runtime(self, **changes):
        source = lifecycle_source(parse_feature(declaration(**changes)), stock_travel('GPL'))
        wanted = ('mm_forgehire_select', 'mm_forgehire_arrive', 'mm_forgehire_admit')
        source = '\n'.join(i.text for i in parse_gpl(source).items if i.normalized_name in wanted)
        # The fixture models GPL list subtraction; the production source is unchanged.
        source = re.sub(r'''(\w+'s "\w+") -= (\w+);''', r'\1 = $FixtureRemove(\1, \2);', source)
        source = re.sub(r'#(\w+)', lambda m: '"' + m[1] + '"', source)
        vm = SamplerHarness(source)
        events = []
        building, hero, home = Agent(), Agent(), Agent()
        building.fields = {'Title': 'Forge', 'ATTRIB_FirstStageBuilt': 1, 'Occupants': []}
        home.fields = {'Members': [hero]}
        basic = lambda *args: None
        travel = lambda *args: None
        hero.fields = {'Target': None, 'Home': home, 'ActiveScript': basic,
                       'BackScript': basic, 'BasicScript': basic, 'TaskName': '', 'inside': False}
        def unlocked(b):
            return int(b.fields.get('MM_ForgeHire_UnlockedState', False))
        def reset(h):
            h['Target'] = None
            h['ActiveScript'] = h['BasicScript']
            h['BackScript'] = h['BasicScript']
        def exit_building(h, b):
            b['Occupants'].remove(h)
            h['inside'] = False
            reset(h)
        def remove(values, h):
            return [a for a in values if a is not h]
        vm.calls.update(mm_forgehire_travel=travel, mm_forgehire_unlocked=unlocked,
            mm_forgehire_eligible=lambda h, b: h.alive and b.alive and not unlocked(b),
            insidebuilding=lambda h: h['inside'], reset_tasks=reset, exit_building=exit_building,
            stopmoving=lambda h: events.append('stop'), agentinlist=lambda h, values: h in values,
            fixtureRemove=remove, getattribute=lambda a, k: a[k],
            forgecleanup=lambda h, b: events.append('cleanup'),
            cancelguildmembership=lambda h: events.append('membership'),
            hero_drop_quest_items=lambda h: events.append('quest-items'),
            killthread=lambda f: events.append('kill'),
            deletegamepiece=lambda h: (events.append('delete'), setattr(h, 'alive', False)))
        vm.calls['fixtureremove'] = remove
        return vm, building, hero, home, events

    def test_cancellation_and_ordinary_visits_cannot_consume(self):
        vm, b, h, home, events = self.runtime()
        self.assertEqual(vm.call('MM_ForgeHire_Select', b, h), 1)
        self.assertNotIn('MM_ForgeHire_UnlockedState', b.fields)
        vm.calls['reset_tasks'](h)
        # Same building on a later ordinary visit, even with a stale label.
        h['Target'] = b
        h['inside'] = True
        h['TaskName'] = 'Hire'
        b['Occupants'].append(h)
        vm.call('MM_ForgeHire_Arrive', h)
        self.assertTrue(h.alive)
        self.assertEqual(home['Members'], [h])
        self.assertNotIn('cleanup', events)

    def test_confirmed_entry_removes_once_and_unlocks(self):
        vm, b, h, home, events = self.runtime()
        vm.call('MM_ForgeHire_Select', b, h)
        h['ActiveScript'] = vm.calls['mm_forgehire_arrive']
        h['inside'] = True
        b['Occupants'].append(h)
        vm.call('MM_ForgeHire_Arrive', h)
        self.assertEqual(events, ['stop', 'cleanup', 'membership', 'quest-items', 'kill', 'delete'])
        self.assertEqual(home['Members'], [])
        self.assertEqual(b['Occupants'], [])
        self.assertTrue(b['MM_ForgeHire_UnlockedState'])
        vm.call('MM_ForgeHire_Arrive', h)
        self.assertEqual(events.count('delete'), 1)

    def test_death_missing_entry_and_concurrent_completion_do_not_consume(self):
        for condition in ('dead', 'outside', 'missing-occupant', 'already-unlocked', 'building-dead'):
            vm, b, h, home, events = self.runtime()
            vm.call('MM_ForgeHire_Select', b, h)
            h['ActiveScript'] = vm.calls['mm_forgehire_arrive']
            h['inside'] = condition != 'outside'
            if condition != 'missing-occupant': b['Occupants'].append(h)
            if condition == 'dead': h.alive = False
            if condition == 'building-dead': b.alive = False
            if condition == 'already-unlocked': b['MM_ForgeHire_UnlockedState'] = True
            vm.call('MM_ForgeHire_Arrive', h)
            self.assertNotIn('cleanup', events, condition)
            self.assertNotIn('delete', events, condition)
            self.assertEqual(home['Members'], [h], condition)

    def test_gates_do_not_change_upgrade_or_existing_research(self):
        vm, b, h, home, events = self.runtime()
        for unlocked in (False, True):
            b['MM_ForgeHire_UnlockedState'] = unlocked
            self.assertEqual(vm.call('MM_ForgeHire_Admit', b, 8100), int(not unlocked))
            self.assertEqual(vm.call('MM_ForgeHire_Admit', b, 8009), int(unlocked))
            self.assertEqual(vm.call('MM_ForgeHire_Admit', b, 0x1F47), 1)
            self.assertEqual(events, [])

    def test_optional_stock_visitors_uses_saved_unlock_without_side_effects(self):
        vm, b, h, home, events = self.runtime(gated_control_ids=[8009, 8021])
        for unlocked in (None, True, False):
            b.fields.pop('MM_ForgeHire_UnlockedState', None)
            if unlocked is not None:
                b['MM_ForgeHire_UnlockedState'] = unlocked
            self.assertEqual(vm.call('MM_ForgeHire_Admit', b, 8021), int(bool(unlocked)))
            self.assertEqual(vm.call('MM_ForgeHire_Admit', b, 8100), int(not unlocked))
            self.assertEqual(vm.call('MM_ForgeHire_Admit', b, 8009), int(bool(unlocked)))
            self.assertEqual(vm.call('MM_ForgeHire_Admit', b, 0x1F47), 1)
        b.alive = False
        self.assertEqual(vm.call('MM_ForgeHire_Admit', b, 8021), 0)
        self.assertEqual(events, [])


if __name__ == '__main__':
    unittest.main()
