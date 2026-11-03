"""Observe committed stock status transactions without changing tasks/timers."""
from dataclasses import replace
from pathlib import Path
import unittest

from majesty_cam.compose import _load_stock_gameplay_event_items
from majesty_cam.gameplay_events import add_gameplay_event_observers
from majesty_cam.gpl import SemanticMergeResult, parse_gpl
from majesty_cam.shared_features import parse_shared_feature

GAME = Path('C:/Program Files (x86)/Steam/steamapps/common/Majesty HD')


class StatusAppliedTests(unittest.TestCase):
    def setUp(self):
        self.stock = _load_stock_gameplay_event_items(GAME, {'status-applied': ('Observe',)})
        self.callback = parse_gpl('function Observe(agent Recipient, string Status) declare begin end').items[0]

    def compose(self, items=(), stock=None):
        return {i.normalized_name: i.text for i in add_gameplay_event_observers(
            SemanticMergeResult((self.callback, *items), ()),
            {'status-applied': ('Observe',)}, stock or self.stock).items}

    def test_source_contract_and_both_destination_datasets(self):
        feature = parse_shared_feature(dict(type='stock.gameplay-event-observer.v1',
            feature_key='status-use', event='status-applied', callback_symbol='Observe'))
        self.assertEqual(feature.event, 'status-applied')
        for dataset in ('majesty', 'majestyexpansion'):
            stock = _load_stock_gameplay_event_items(GAME, {'status-applied': ('Observe',)}, dataset=dataset)
            result = self.compose(stock=stock)
            for name, item in stock.items():
                recipient = 'hero' if name == 'plague_event' else 'target'
                notification = '\n\t$Observe(' + recipient + ', "Ratman_Plague_Icon");'
                self.assertEqual(result[name].count(notification), 1)
                self.assertEqual(result[name].replace(notification, ''), item.text)
                # No additional scheduling, scan, task rewrite or cleanup.
                self.assertEqual(result[name].lower().count('$newthread'), item.text.lower().count('$newthread'))
                self.assertEqual(result[name].lower().count('$listobjects'), item.text.lower().count('$listobjects'))

    def test_notification_follows_generation_in_contagion(self):
        text = self.compose()['ratman_plague_active'].lower()
        begin = text.index('$ratman_plague_begin')
        generation = text.index('$setattribute', begin)
        notify = text.index('$observe', generation)
        self.assertLess(begin, generation)
        self.assertLess(generation, notify)

    def test_additional_guards_and_existing_use_are_preserved(self):
        for name, item in self.stock.items():
            # Extra eligibility is author-owned, not a reason to discard the event.
            changed = replace(item, text=item.text.replace('begin',
                'begin\n if ($CustomAlreadyCured(thisagent)) return;', 1)) if name != 'plague_event' else item
            result = self.compose((changed,))[name]
            recipient = 'hero' if name == 'plague_event' else 'target'
            self.assertEqual(result.replace('\n\t$Observe('+recipient+', "Ratman_Plague_Icon");', ''), changed.text)

    def test_incomplete_rebound_or_duplicate_transactions_rejected(self):
        item = self.stock['ratman_plague_active']
        import re
        begin = re.search(r'\$Ratman_Plague_Begin\s*\([^;]+;', item.text, re.I).group()
        for replacement in ('', begin+begin, begin+' target = thisagent;', begin+' return;'):
            with self.subTest(replacement=replacement), self.assertRaises(ValueError):
                self.compose((replace(item, text=item.text.replace(begin, replacement)),))


if __name__ == '__main__':
    unittest.main()
