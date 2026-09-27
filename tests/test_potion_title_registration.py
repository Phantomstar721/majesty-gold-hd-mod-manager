"""Pure source-level observer composition; no user package is built."""
from dataclasses import replace
from pathlib import Path
import unittest

from majesty_cam.gameplay_events import add_gameplay_event_observers
from majesty_cam.gpl import parse_gpl, SemanticMergeResult

ROOT = Path(__file__).resolve().parents[2]
STOCK = ROOT / "external/BrandonWill-Majesty/SDK/OriginalQuests/GPLMx/TaskModules/Subtasks/mx_Spells.gpl"


class PotionTitleRegistrationTests(unittest.TestCase):
    def setUp(self):
        if not STOCK.is_file():
            self.skipTest("stock source unavailable")
        from majesty_cam.gameplay_events import EVENT_FUNCTIONS
        parsed = parse_gpl(STOCK.read_text(encoding="cp1252"))
        self.stock = {i.normalized_name: i for i in parsed.items}
        # Healing owners are irrelevant to this boundary fixture.
        for name in EVENT_FUNCTIONS["potion-consumed"]:
            if name.startswith("heal_self"):
                self.stock[name] = parse_gpl(f'function {name}(agent ThisAgent)\ndeclare\nbegin\n$AdjustAttribute(ThisAgent, #ATTRIB_NumHealingPotions, -1);\nend').items[0]
        self.callback = parse_gpl('function Observe(agent Actor, string Item)\ndeclare\nbegin\nend').items[0]

    def variant(self, name):
        item = self.stock[name]
        return replace(item, text=item.text.replace('title == "Healer"',
            'title == "Healer" || title == "Custom Caster A" || title == "Custom Caster B"'))

    def compose(self, *items):
        return add_gameplay_event_observers(SemanticMergeResult((self.callback, *items), ()),
                                            {"potion-consumed": ("Observe",)}, self.stock)

    def test_additive_pair_preserves_application_and_cleanup(self):
        effect, expiry = (self.variant(n) for n in ("shapeshift_potion_effect", "shapeshift_potion_end"))
        result = {i.normalized_name: i.text for i in self.compose(effect, expiry).items}
        self.assertEqual(result["shapeshift_potion_end"], expiry.text)
        observed = result["shapeshift_potion_effect"]
        self.assertEqual(observed.count('$Observe('), 1)
        self.assertGreater(observed.index('$Observe('), observed.index('$ForgetSpell'))
        self.assertEqual(observed.replace('\t$Observe(ThisAgent, "shapeshift_potion");\n', ''), effect.text)

    def test_reject_unmatched_cleanup_and_unrelated_changes(self):
        effect, expiry = (self.variant(n) for n in ("shapeshift_potion_effect", "shapeshift_potion_end"))
        with self.assertRaises(ValueError):
            self.compose(effect)
        for changed_effect, changed_expiry in (
            (replace(effect, text=effect.text.replace('"Wizard"', '"Other"')), expiry),
            (replace(effect, text=effect.text.replace('|| title == "Custom Caster A"', '&& title == "Custom Caster A"')), expiry),
            (replace(effect, text=effect.text.replace('#ATTRIB_MaxHP, 30', '#ATTRIB_MaxHP, 31')), expiry),
            (effect, replace(expiry, text=expiry.text.replace('#ATTRIB_MaxHP, -30', '#ATTRIB_MaxHP, -31'))),
            (effect, replace(expiry, text=expiry.text.replace('Custom Caster B', 'Another Caster'))),
        ):
            with self.subTest(effect=changed_effect.text, expiry=changed_expiry.text), self.assertRaises(ValueError):
                self.compose(changed_effect, changed_expiry)

    def test_actual_candidate_source(self):
        candidate = ROOT / "majesty-gold-hd-custom-guild-bard/dist/CustomGuildBards-bazaar-v1/GPL/Bards_Baseline.gpl"
        if not candidate.is_file():
            self.skipTest("candidate source unavailable")
        items = [i for i in parse_gpl(candidate.read_text(encoding="cp1252")).items
                 if i.normalized_name in ("shapeshift_potion_effect", "shapeshift_potion_end")]
        self.assertEqual(len(items), 2)
        self.compose(*items)
