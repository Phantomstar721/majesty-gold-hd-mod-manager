"""Negative lifecycle mutations and unrelated selected-mod changes."""
from dataclasses import replace
from pathlib import Path
import re
import unittest

from majesty_cam.compose import _load_stock_gameplay_event_items
from majesty_cam.gameplay_events import add_gameplay_event_observers, EVENT_SIGNATURES
from majesty_cam.gpl import SemanticMergeResult, parse_gpl
from majesty_cam.gpl_function_merge import _SourceParser, _tokens, same_function_instructions


GAME = Path('C:/Program Files (x86)/Steam/steamapps/common/Majesty HD')


@unittest.skipUnless((GAME/'SDK/OriginalQuests/GPLMx').is_dir(), 'requires installed SDK')
class EventBoundaryContractTests(unittest.TestCase):
    def setup_event(self, event):
        self.event = event
        self.stock = _load_stock_gameplay_event_items(GAME, {event: ('Observe',)})
        args = ', '.join(f'{kind} Param{i}' for i, kind in enumerate(EVENT_SIGNATURES[event]))
        self.callback = parse_gpl(f'function Observe({args}) declare begin end').items[0]

    def observe(self, *items):
        return {item.normalized_name: item.text for item in add_gameplay_event_observers(
            SemanticMergeResult((self.callback, *items), ()),
            {self.event: ('Observe',)}, self.stock).items}

    def test_combat_observes_only_hero_branch_with_identical_award_elsewhere(self):
        self.setup_event('combat-experience-awarded')
        item = self.stock['attack_end']
        parser = _SourceParser(item.text)
        body = parser.function()[2]
        start, end = parser.node_spans[id(body[0])]
        hero = item.text[start:end]
        guards = hero.replace('"hero"', '"Henchman"')
        current = replace(item, text=item.text[:end] + '\n' + guards + item.text[end:])
        final = self.observe(current)['attack_end']
        self.assertIn(guards, final)
        self.assertEqual(final.count('$MM_Event_CombatXP'), 1)
        self.assertEqual(final.replace('$MM_Event_CombatXP', '$give_exp'), current.text)
        updated_formula = replace(item, text=item.text.replace('new_exp_div = 1;', 'new_exp_div = 2;'))
        self.assertNotEqual(updated_formula.text, item.text)
        final = self.observe(updated_formula)['attack_end']
        self.assertEqual(final.replace('$MM_Event_CombatXP', '$give_exp'), updated_formula.text)
        for changed in (hero + '\n' + hero, 'if (True) begin ' + hero + ' end'):
            self.assertNotEqual(changed, hero)
            with self.subTest(change=changed), self.assertRaises(ValueError):
                self.observe(replace(item, text=item.text[:start] + changed + item.text[end:]))

    def test_unrelated_nonarrival_and_nonpotion_choices_are_preserved(self):
        for event, name, before, after in (
            ('exploration-experience-awarded', 'travel_to_exp', '$heal_self(thisagent)', '$PrivateHeal(thisagent)'),
            ('potion-consumed', 'heal_self', '$last_stand(thisagent', '$PrivateLastStand(thisagent'),
        ):
            with self.subTest(event=event):
                self.setup_event(event)
                item = self.stock[name]
                changed = replace(item, text=item.text.replace(before, after))
                self.assertNotEqual(changed.text, item.text)
                final = self.observe(changed)[name]
                self.assertIn(after, final)
                self.assertEqual(final.count('$MM_Event_ExploreXP' if name == 'travel_to_exp' else '$Observe('), 1)

    def test_flag_success_protects_target_binding_order_scope_and_cardinality(self):
        self.setup_event('attack-flag-completed')
        for name in ('attack_flag_poll', 'attack_flag_death_callback'):
            item = self.stock[name]
            variants = (
                re.sub(r'target\s*=\s*\$agentnumber\s*\([^;]+;', 'target = ThisAgent;', item.text, flags=re.I),
                item.text.replace('"gavereward" != TRUE', '"gavereward" == TRUE'),
                re.sub(r'\$playsound\s*\([^;]+;', '$deletegamepiece(ThisAgent);', item.text, count=1, flags=re.I),
            )
            for changed in variants:
                self.assertNotEqual(changed, item.text)
                with self.subTest(owner=name, change=changed), self.assertRaises(ValueError):
                    self.observe(replace(item, text=changed))
        # A selected mod can privatize the payout implementation. Completion
        # still observes precisely the unchanged success region, not its name.
        item = self.stock['attack_flag_poll']
        changed = replace(item, text=item.text.replace('$dropgoldinradius', '$PrivatePayout'))
        final = self.observe(changed)['attack_flag_poll']
        self.assertIn('$PrivatePayout', final)
        self.assertEqual(final.replace('\t$Observe(ThisAgent, target);\n', ''), changed.text)

    def test_potion_effect_branch_can_change_without_changing_consumption(self):
        self.setup_event('potion-consumed')
        item = self.stock['fire_balm_effect']
        parser = _SourceParser(item.text)
        body = parser.function()[2]
        first = next(i for i, node in enumerate(body)
                     if node.head == _tokens('action = ThisAgent\'s "Attack_Action";'))
        start = parser.node_spans[id(body[first])][0]
        end = parser.node_spans[id(body[first + 2])][1]
        changes = ('if (ThisAgent\'s "Special_Attack_Action" != "") begin\n'
                   + item.text[start:end] + '\nend')
        changed = replace(item, text=item.text[:start] + changes + item.text[end:])
        final = self.observe(changed)['fire_balm_effect']
        self.assertEqual(final.count('$Observe('), 1)
        self.assertEqual(final.replace('\n\t$Observe(ThisAgent, "fire_balm");\n', ''), changed.text)

    def test_potion_observer_keeps_entry_guard_recipient_pair_and_completion_work(self):
        self.setup_event('potion-consumed')
        item = self.stock['speed_tonic_effect']
        parser = _SourceParser(item.text)
        body = parser.function()[2]
        guard_start, guard_end = parser.node_spans[id(body[0])]
        consume = next(node for node in body if node.head[:1] == ('$deleteinventoryitem',))
        consume_start, consume_end = parser.node_spans[id(consume)]
        pair = item.text[consume_start:parser.node_spans[id(body[-2])][1]]
        variants = (
            item.text[:guard_start] + item.text[guard_end:],
            item.text[:guard_end] + '\nThisAgent = Target;\n' + item.text[guard_end:],
            item.text[:consume_end] + '\n' + pair + item.text[consume_end:],
            item.text.replace('#Bazaar_Item_One', '#Bazaar_Item_Two'),
            item.text.replace('"Speed_Tonic"', '"OtherPotion"'),
        )
        for changed in variants:
            self.assertNotEqual(changed, item.text)
            with self.subTest(change=changed), self.assertRaises(ValueError):
                self.observe(replace(item, text=changed))

    def test_potion_tail_is_selected_gameplay_and_not_a_stock_identity_check(self):
        self.setup_event('potion-consumed')
        item = self.stock['speed_tonic_effect']
        altered = re.sub(r'\$TurnOnSpeedTrail\s*\([^;]+;',
                         'if (ThisAgent\'s "QuietPotion") return;\n$SelectedEffect(ThisAgent);',
                         item.text, flags=re.I)
        self.assertNotEqual(altered, item.text)
        final = self.observe(replace(item, text=altered))['speed_tonic_effect']
        self.assertEqual(final.count('$Observe('), 2)
        restored = re.sub(r'\$Observe\(ThisAgent, "speed_tonic"\);', '', final)
        self.assertTrue(same_function_instructions(restored, altered))
        parser = _SourceParser(final)
        body = parser.function()[2]
        branch = next(node for node in body if node.head == _tokens('if (ThisAgent\'s "QuietPotion")'))
        self.assertEqual(branch.body[-1].head, ('return', ';'))
        self.assertEqual(branch.body[-2].head[0], '$observe')

    def test_healing_single_statement_branch_retains_its_else(self):
        self.setup_event('potion-consumed')
        item = self.stock['heal_self']
        parser = _SourceParser(item.text)
        body = parser.function()[2]
        branch = next(node for node in body if node.head ==
                      _tokens('if ($GetAttribute(ThisAgent, #ATTRIB_NumHealingPotions) > 0)'))
        start, end = parser.body_spans[id(branch)]
        altered = item.text[:start] + '$AdjustAttribute(ThisAgent, #ATTRIB_NumHealingPotions, -1);' + item.text[end:]
        final = self.observe(replace(item, text=altered))['heal_self']
        result = _SourceParser(final).function()[2]
        composed = next(node for node in result if node.head == branch.head)
        self.assertEqual(composed.otherwise, branch.otherwise)
        self.assertEqual(len(composed.body), 2)
        self.assertEqual(composed.body[-1].head[0], '$observe')

    def test_potion_cannot_notify_with_destroyed_recipient(self):
        self.setup_event('potion-consumed')
        item = self.stock['speed_tonic_effect']
        for call in ('$DeleteGamepiece(ThisAgent);', '$Henchman_Dead(ThisAgent, ThisAgent);',
                     '$DeleteGamepiece((ThisAgent));', '$Henchman_Dead(((ThisAgent)), ThisAgent);'):
            altered = re.sub(r'\$TurnOnSpeedTrail\s*\([^;]+;', call, item.text, flags=re.I)
            with self.subTest(call=call), self.assertRaisesRegex(ValueError, 'destroys its notification recipient'):
                self.observe(replace(item, text=altered))

    def test_caravan_preserves_selected_quest_scoring_and_delivery_formula(self):
        self.setup_event('caravan-delivered')
        item = self.stock['caravan_go_trade']
        altered = item.text.replace('$henchman_dead(ThisAgent, ThisAgent);',
                                    '$CustomQuestScore(ThisAgent);\n$DeleteGamepiece(OtherUnit);\n$henchman_dead(ThisAgent, ThisAgent);')
        altered = altered.replace('* Target\'s "Level"', '* (Target\'s "Level" + 2)')
        self.assertNotEqual(altered, item.text)
        final = self.observe(replace(item, text=altered))['caravan_go_trade']
        self.assertEqual(final.replace('\t$Observe(ThisAgent, Target, Gold_To_Give);\n', ''), altered)

    def test_caravan_does_not_accept_overwritten_target_or_early_destruction(self):
        self.setup_event('caravan-delivered')
        item = self.stock['caravan_go_trade']
        for changed in (
            item.text.replace('Target = ThisAgent\'s "Target";', 'Target = ThisAgent;'),
            item.text.replace('$Transfer_Gold', '$NoTransfer'),
            item.text.replace('$henchman_dead', '$DifferentDeath'),
            item.text.replace('$henchman_dead', 'Target = ThisAgent;\n$henchman_dead'),
            item.text.replace('$henchman_dead', 'Gold_To_Give = 0;\n$henchman_dead'),
            item.text.replace('$henchman_dead', '++Gold_To_Give;\n$henchman_dead'),
            item.text.replace('$henchman_dead', '--(Gold_To_Give);\n$henchman_dead'),
            item.text.replace('$henchman_dead', '((Gold_To_Give))++;\n$henchman_dead'),
            item.text.replace('$henchman_dead', 'ThisAgent = Target;\n$henchman_dead'),
            item.text.replace('$Transfer_Gold', '$SetAttribute(ThisAgent, #ATTRIB_Gold, 17);\n$Transfer_Gold'),
            item.text.replace('$Transfer_Gold', '$AdjustAttribute(ThisAgent, #ATTRIB_Gold, 17);\n$Transfer_Gold'),
            item.text.replace('$Transfer_Gold', '$AdjustAttribute((ThisAgent), (#ATTRIB_Gold), 17);\n$Transfer_Gold'),
            item.text.replace('$henchman_dead', 'return;\n$henchman_dead'),
        ):
            self.assertNotEqual(changed, item.text)
            with self.subTest(change=changed), self.assertRaises(ValueError):
                self.observe(replace(item, text=changed))

    def test_tournament_keeps_selected_exit_prizes(self):
        self.setup_event('tournament-completed')
        item = self.stock['exit_fair']
        altered = replace(item, text=re.sub(r'\bbegin\b', 'begin\n$CustomPrize(ThisAgent);', item.text, count=1, flags=re.I))
        self.assertNotEqual(altered.text, item.text)
        final = self.observe(altered)
        self.assertEqual(final['exit_fair'], altered.text)
        self.assertIn('$Exit_Fair(ThisAgent);', final['mm_event_fairfinished'])
