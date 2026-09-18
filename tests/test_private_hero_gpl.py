from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
import sys
import unittest
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from majesty_cam.gpl import SemanticMergeResult, parse_gpl, add_hero_quest_lifecycle_callbacks
from majesty_cam.gpl_features import (StockHeroQuestParticipant, StockSpellEvaluationEquivalent,
                                     parse_gpl_feature, normalize_gpl_features)
from majesty_cam.private_hero_gpl import validate_bindings, add_spell_evaluation_equivalents
from majesty_cam.package import _runtime_feature_mapping as runtime_feature_mapping

GAME = Path("C:/Program Files (x86)/Steam/steamapps/common/Majesty HD")
SPELL = StockSpellEvaluationEquivalent("note", "Private_Note", "energy_blast", "Private_Caster")
STOCK = '''function spell_extra_value(agent thisagent) is integer
declare
    integer value;
begin
    if ($IsSpellAvailable(ThisAgent,"energy_blast",1)) value += 10;
    if ($IsSpellAvailable(ThisAgent,"sun_scorch",1)) value += 30;
    return value;
end
'''
CALLBACKS = '''function Resume(agent ThisAgent) is boolean
begin
    return FALSE;
end
function Consider(agent ThisAgent) is boolean
begin
    return FALSE;
end
function Reset(agent ThisAgent)
begin
end
function Death(agent ThisAgent)
begin
end
function reset_tasks(agent ThisAgent)
begin
    $StopMoving(ThisAgent);
end
function Unit_Call_Deathscript(agent ThisAgent)
begin
    $DeleteAllEffectors(ThisAgent);
    if ($ValidFunction(ThisAgent's "IGDeathScript") == TRUE)
        (ThisAgent's "IGDeathScript")(ThisAgent);
end
'''


def tree(name, healer=False):
    anchor = '$Purchase_Bazaar(ThisAgent,70)' if healer else '$Pursue_Entertainment(ThisAgent)'
    return parse_gpl(f'''function {name}(agent ThisAgent)
begin
    if ($Private_Hiring_Guard(ThisAgent)) return;
    if ($Check_Nearby(ThisAgent) == FALSE)
    if ($Check_rewards(ThisAgent,TRUE) == FALSE)
    if ({anchor} == FALSE)
        $Go_Home(ThisAgent,90);
end
''', name)


class PrivateHeroGplTests(unittest.TestCase):
    def test_schema_roundtrip_and_reserved_or_duplicate_bindings(self):
        participant = StockHeroQuestParticipant("hero", "Private_Tree", "mx_healer")
        for item in (participant, SPELL):
            self.assertEqual(parse_gpl_feature(runtime_feature_mapping(item)), item)
            with self.assertRaises(ValueError): parse_gpl_feature({**vars(item), "value": 999})
            with self.assertRaises(ValueError): normalize_gpl_features((item, replace(item, feature_key="other")))
        for script in ("mx_healer", "Healer_tree"):
            with self.assertRaises(ValueError): parse_gpl_feature(vars(replace(participant, hero_script=script)))
        with self.assertRaises(ValueError): parse_gpl_feature(vars(replace(SPELL, private_spell='bad"name')))

    def test_private_trees_receive_only_selected_analogue_providers(self):
        callbacks = parse_gpl(CALLBACKS, "provider")
        features = tuple(StockHeroQuestParticipant(name, name, stock) for name, stock in
                         (("Private_Support", "mx_healer"), ("Private_Caster", "mx_cultist"), ("Private_Fighter", "mx_rogue")))
        sources = tuple(tree(f.hero_script, f.stock_hero_script == "mx_healer") for f in features)
        private, _ = validate_bindings([("owner", features, sources, ())])
        original = SemanticMergeResult(tuple(item for source in sources for item in source.items), ())
        self.assertIs(add_hero_quest_lifecycle_callbacks(original, (), stock_hero_trees={}, private_hero_trees=private), original)
        self.assertNotIn("$Resume", "".join(item.text for item in original.items))
        initial = SemanticMergeResult((*original.items, *callbacks.items), ())
        stock = {f.stock_hero_script: tree(f.stock_hero_script + "_tree", f.stock_hero_script == "mx_healer").items[0] for f in features}
        result = add_hero_quest_lifecycle_callbacks(initial,
            [(tuple(stock), "Resume", "Consider", "Reset", "Death")], stock_hero_trees=stock, private_hero_trees=private)
        for feature in features:
            text = next(item.text for item in result.items if item.name == feature.hero_script)
            self.assertLess(text.index("$Private_Hiring_Guard"), text.index("$Check_Nearby"))
            self.assertLess(text.index("$Check_Nearby"), text.index("$Resume"))
            self.assertLess(text.index("$Resume"), text.index("$Check_rewards"))
            anchor = "$Purchase_Bazaar" if feature.stock_hero_script == "mx_healer" else "$Pursue_Entertainment"
            self.assertLess(text.index(anchor), text.index("$Consider"))
            self.assertLess(text.index("$Consider"), text.index("$Go_Home"))
        reset = next(item.text for item in result.items if item.name == "reset_tasks")
        self.assertEqual(reset.count("$Reset("), 1)
        only_rogue = add_hero_quest_lifecycle_callbacks(initial,
            [(("mx_rogue",), "Resume", "Consider", "Reset", "Death")], stock_hero_trees=stock, private_hero_trees=private)
        support = next(item.text for item in only_rogue.items if item.name == "Private_Support")
        self.assertEqual(support, sources[0].items[0].text)
        with self.assertRaises(ValueError): validate_bindings([("owner", features, (), ())])
        bad = replace(sources[0], items=(replace(sources[0].items[0], text=sources[0].items[0].text.replace("$Check_rewards", "$Private_rewards")),))
        with self.assertRaisesRegex(ValueError, "resume anchor"):
            validate_bindings([("owner", features[:1], (bad,), ())])

    def test_spell_weights_are_stock_derived_additive_and_fail_closed(self):
        stock = parse_gpl(STOCK, "stock").items[0]
        existing = replace(stock, text=stock.text.replace("return value;", "$Other_Mod_Contribution(ThisAgent);\n    return value;"))
        initial = SemanticMergeResult((existing,), ())
        features = (SPELL, replace(SPELL, feature_key="burst", private_spell="Private_Burst", stock_spell="sun_scorch"))
        result = add_spell_evaluation_equivalents(initial, features, stock)
        text = result.items[0].text
        self.assertIn("$Other_Mod_Contribution(ThisAgent);", text)
        self.assertIn('$IsSpellAvailable(ThisAgent,"Private_Note",1)', text)
        self.assertIn('$IsSpellAvailable(ThisAgent,"Private_Burst",1)', text)
        self.assertIn('ThisAgent\'s "title" == "Private_Caster"', text)
        self.assertEqual(text.count("value += 10;"), 2)
        self.assertEqual(text.count("value += 30;"), 2)
        self.assertEqual(text.count("return value;"), 1)
        for bad in (replace(SPELL, stock_spell="unknown"), replace(SPELL, private_spell="sun_scorch")):
            with self.assertRaises(ValueError): add_spell_evaluation_equivalents(initial, (bad,), stock)
        with self.assertRaisesRegex(ValueError, "already contains"):
            add_spell_evaluation_equivalents(result, (SPELL,), stock)
        early = replace(existing, text=existing.text.replace("begin", "begin\nif (TRUE) return 0;", 1))
        with self.assertRaisesRegex(ValueError, "terminal return"):
            add_spell_evaluation_equivalents(SemanticMergeResult((early,), ()), (SPELL,), stock)
        descriptions = tuple(ET.fromstring(s) for s in (
            '<Description type="Action" Name="Private_Note"/>',
            '<Description type="Unit" subType="Character" Name="Private_Caster"/>'))
        self.assertEqual(validate_bindings([("owner", (SPELL,), (), descriptions)])[1], (SPELL,))
        with self.assertRaisesRegex(ValueError, "package-owned"):
            validate_bindings([("owner", (SPELL,), (), descriptions[:1])])

    @unittest.skipUnless((GAME / "SDK/Gplbcc.exe").is_file(), "stock SDK required")
    def test_actual_stock_source_and_isolated_compiler(self):
        from majesty_cam.compose import _load_stock_spell_evaluation, compile_gpl
        stock = _load_stock_spell_evaluation(GAME)
        final = add_spell_evaluation_equivalents(SemanticMergeResult((), ()), (SPELL,), stock)
        with TemporaryDirectory(prefix="manager-private-spell-compiler-") as tmp:
            compile_gpl(final.emit_project_source_set("Fixture.gpl", "Fixture.dat"),
                        GAME / "SDK/Gplbcc.exe", Path(tmp) / "compiler", stem="Fixture")


if __name__ == "__main__": unittest.main()
