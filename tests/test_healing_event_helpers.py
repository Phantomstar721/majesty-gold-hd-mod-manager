"""Healing-event integration follows a proved extraction, not a mod name."""
from pathlib import Path
import re
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest

from majesty_cam.gameplay_events import EVENT_FUNCTIONS, add_gameplay_event_observers
from majesty_cam.gpl import DefinitionKind, SemanticMergeResult, parse_gpl
from majesty_cam.gpl_function_merge import _SourceParser, _tokens, same_function_instructions


GUARD = '$GetAttribute(ThisAgent, #ATTRIB_NumHealingPotions) > 0'
DEBIT = '$AdjustAttribute(ThisAgent, #ATTRIB_NumHealingPotions, -1);'
ROOTS = ('heal_self', 'heal_self_fleeing')
CALLBACK = 'function Observe(agent Hero, string Potion) declare begin end'
HELPER = '''function ApplyPotion(agent Hero)
declare integer amount;
begin
    $CreateEffector(Hero, "potion_healing_effector", 0);
    amount = #Heal_Potion_Recovery + ($GetAttribute(Hero, #ATTRIB_Vitality) / 2);
    $Heal(Hero, Hero, amount);
    $AdjustAttribute(Hero, #ATTRIB_NumHealingPotions, -1);
end
'''


def healing(name, body):
    return f'''function {name}(agent ThisAgent)
declare
begin
    if ({GUARD}) begin {body} end
    else $OtherHealing(ThisAgent);
end
'''


def stock_items():
    text = ''.join(healing(name, '$Heal(ThisAgent, ThisAgent, #Heal_Potion_Recovery);' + DEBIT)
                   for name in ROOTS)
    for name in EVENT_FUNCTIONS['potion-consumed'][2:]:
        text += f'''function {name}(agent ThisAgent) declare begin
    if ($IsDead(ThisAgent)) return;
    $DeleteInventoryItem(#Item, ThisAgent);
    $ForgetSpell(ThisAgent, "{name}");
end
'''
    return {item.normalized_name: item for item in parse_gpl(text).items}


class HealingHelperTests(unittest.TestCase):
    def observe(self, text, loader=None, stock=None):
        result = add_gameplay_event_observers(
            SemanticMergeResult(parse_gpl(CALLBACK + '\n' + text).items, ()),
            {'potion-consumed': ('Observe',)}, stock or stock_items(), source_loader=loader)
        return {item.normalized_name: item.text for item in result.items}

    def selected(self, helper=HELPER):
        return ''.join(healing(name, '$ApplyPotion(ThisAgent);') for name in ROOTS) + helper

    def assert_observed_roots(self, output, originals):
        for name in ROOTS:
            text = output[name]
            self.assertEqual(text.count('$Observe('), 1)
            restored = text.replace('\n\t$Observe(ThisAgent, "healing_potion");', '')
            self.assertTrue(same_function_instructions(restored, originals[name]))
            branch = next(node for node in _SourceParser(text).function()[2]
                          if node.head == _tokens(f'if ({GUARD})'))
            self.assertEqual(branch.body[-1].head[0], '$observe')
            self.assertEqual(branch.otherwise[0].head[0], '$otherhealing')

    def test_shared_helper_stays_unchanged_and_each_root_notifies_once(self):
        unrelated = 'function OtherUser(agent Hero) declare begin $ApplyPotion(Hero); end'
        text = self.selected() + unrelated
        originals = {i.normalized_name: i.text for i in parse_gpl(text).items}
        output = self.observe(text)
        self.assert_observed_roots(output, originals)
        self.assertEqual(output['applypotion'], originals['applypotion'])
        self.assertEqual(output['otheruser'], originals['otheruser'])
        self.assertEqual(set(output), {*stock_items(), *originals, 'observe'})

    def test_native_helper_loaded_without_copying_or_overriding_it(self):
        helper = parse_gpl(HELPER).items[0]
        calls = []
        def loader(name):
            calls.append(name)
            return helper if name == 'applypotion' else None
        text = self.selected('')
        output = self.observe(text, loader)
        self.assertNotIn('applypotion', output)
        self.assertEqual(set(calls), {'applypotion'})
        self.assert_observed_roots(output, {i.normalized_name: i.text for i in parse_gpl(text).items})

    def test_selected_helper_wins_over_loader_and_all_names_are_generic(self):
        def wrong_loader(name):
            self.fail('Must not load over the selected helper')
        text = self.selected().replace('ApplyPotion', 'DifferentName').replace('Hero', 'Consumer')
        output = self.observe(text, wrong_loader)
        self.assertEqual(output['heal_self'].count('$Observe('), 1)
        self.assertNotIn('$Observe', output['differentname'])

    def test_unbraced_branch_and_optional_terminal_return(self):
        text = self.selected(HELPER.replace('\nend', '\nreturn;\nend'))
        text = text.replace('begin $ApplyPotion(ThisAgent); end', '$ApplyPotion(ThisAgent);')
        output = self.observe(text)
        self.assert_observed_roots(output, {i.normalized_name: i.text for i in parse_gpl(text).items})

    def test_inline_stock_keeps_existing_notification_placement(self):
        originals = {name: item.text for name, item in stock_items().items()}
        self.assert_observed_roots(self.observe(''), originals)

    def test_unproven_helpers_do_not_silently_count_a_potion(self):
        debit = '$AdjustAttribute(Hero, #ATTRIB_NumHealingPotions, -1);'
        mutations = {
            'missing': '',
            'wrong recipient': HELPER.replace(debit, debit.replace('Hero,', 'Other,')),
            'wrong quantity': HELPER.replace(', -1);', ', -2);'),
            'wrong attribute': HELPER.replace('#ATTRIB_NumHealingPotions', '#ATTRIB_HitPoints'),
            'conditional': HELPER.replace(debit, 'if (Hero\'s "Ready") ' + debit),
            'early return': HELPER.replace(debit, 'return; ' + debit),
            'loop': HELPER.replace(debit, 'while (True) do begin ' + debit + ' end'),
            'duplicate': HELPER.replace(debit, debit + debit),
            'work after debit': HELPER.replace(debit, debit + '$Heal(Hero, Hero, 1);'),
            'reassignment': HELPER.replace(debit, '((Hero)) = Other; ' + debit),
            'prefix reassignment': HELPER.replace(debit, '++(Hero); ' + debit),
            'postfix reassignment': HELPER.replace(debit, '(Hero)++; ' + debit),
            'destruction': HELPER.replace(debit, '$DeleteGamepiece(Hero); ' + debit),
            'indirect': HELPER.replace(debit, 'Hero\'s "Work" = $Later; ' + debit),
            'recursive': HELPER.replace(debit, '$ApplyPotion(Hero); ' + debit),
            'local call': HELPER.replace('declare integer amount;', 'declare integer amount; function Later;')
                               .replace(debit, '$Later(Hero); ' + debit),
            'nested extraction': HELPER.replace(debit, '$SecondHelper(Hero);'),
            'return type': HELPER.replace('(agent Hero)', '(agent Hero) is boolean'),
            'extra argument': HELPER.replace('(agent Hero)', '(agent Hero, integer Amount)'),
            'shadowed recipient': HELPER.replace('declare integer amount;', 'declare agent Hero;'),
        }
        for label, helper in mutations.items():
            with self.subTest(label=label), self.assertRaises(ValueError):
                self.observe(self.selected(helper))

    def test_changed_caller_scope_or_argument_is_not_a_stock_extraction(self):
        for body in ('$ApplyPotion(Other);', '$ApplyPotion($OtherAgent());',
                     '$ApplyPotion(ThisAgent); $ApplyPotion(ThisAgent);',
                     'if (ThisAgent\'s "Ready") $ApplyPotion(ThisAgent);'):
            with self.subTest(body=body), self.assertRaises(ValueError):
                self.observe(healing('heal_self', body) + HELPER)
        with self.assertRaises(ValueError):
            self.observe(self.selected().replace(GUARD, GUARD.replace('> 0', '== 0')))
        with self.assertRaises(ValueError):
            self.observe(self.selected().replace('declare\nbegin', 'declare function ApplyPotion;\nbegin'))

    def test_installed_v3_source_against_both_stock_datasets(self):
        from majesty_cam.compose import _load_stock_gameplay_event_items, compile_gpl
        from majesty_cam.standard_scripts import Providers, read
        game = Path('C:/Program Files (x86)/Steam/steamapps/common/Majesty HD')
        source = game.parents[1]/'workshop/content/73230/1965892371/GPL/Vitality_v3.gpl'
        if not source.is_file() or not (game/'SDK/Gplbcc.exe').is_file():
            self.skipTest('requires installed source and SDK compiler')
        authored = parse_gpl(source.read_text(encoding='cp1252'), str(source)).items
        package = source.parent.parent
        native = read(SimpleNamespace(package_root=package,
            manifest_path=package/'Misc Enhancements.mmxml',
            content_id='D547A2B0-9CF3-467F-93FF-2DE6B5E3D35E', display_name='Attributes V3'))
        for dataset in ('majesty', 'majestyexpansion'):
            with self.subTest(dataset=dataset):
                stock = _load_stock_gameplay_event_items(game, {'potion-consumed': ('Observe',)}, dataset=dataset)
                originals = {i.normalized_name: i.text for i in authored}
                output = self.observe('\n'.join(i.text for i in authored), stock=stock)
                self.assertEqual(output['use_healing_potion'], originals['use_healing_potion'])
                for name in ROOTS:
                    self.assertEqual(output[name].count('$Observe('), 1)
                    restored = re.sub(r'\$Observe\(ThisAgent, "healing_potion"\);', '', output[name])
                    self.assertTrue(same_function_instructions(restored, originals[name]))
                result = SemanticMergeResult(parse_gpl('\n'.join(output.values())).items, ())
                with TemporaryDirectory(prefix='healing-helper-source-') as directory:
                    compile_gpl(result.emit_project_source_set(), game/'SDK/Gplbcc.exe', Path(directory)/'compiler')
                # Exercise the actual Standard provider: matching compiled/source
                # proof and native helper lookup, without preparing any profile.
                providers = Providers((native,), lambda names: {
                    (DefinitionKind.FUNCTION, name): stock[name] for name in names if name in stock},
                    game/'SDK/Gplbcc.exe', dataset)
                selected = providers.functions(ROOTS)
                native_output = self.observe('\n'.join(item.text for item in selected.values()),
                    lambda name: providers.functions((name,)).get((DefinitionKind.FUNCTION, name)), stock)
                self.assertNotIn('use_healing_potion', native_output)
                for name in ROOTS:
                    self.assertTrue(same_function_instructions(native_output[name], output[name]))
